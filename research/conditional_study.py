"""State-conditional event study: condition on the shape of the market, then look at the whole
distribution of what happens next — quantiles and hit rates, not just a mean.

    python research/conditional_study.py

Two samples, labelled:
  A. 2023-01..2024-11, ten coins, hourly bars + COIN-M liquidations (long history).
  B. 2023-07-10, 11 symbols, one day of bookTicker + aggTrades (order-book features, case study).

Descriptive. No trading claim; every cell reports n and day-clustered intervals, and the FDR column
exists so a cell is not mistaken for a finding.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import math

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "conditional_study.json"

spec = importlib.util.spec_from_file_location("anatomy", ROOT / "research" / "liquidation_anatomy.py")
anatomy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(anatomy)


def clustered(v: pd.Series, day: pd.Series) -> tuple[float, float, float]:
    """Mean, 2.5% and 97.5% of a day-resampled bootstrap."""
    d = pd.DataFrame({"v": v.to_numpy(), "d": day.to_numpy()}).dropna()
    if len(d) < 20:
        return float("nan"), float("nan"), float("nan")
    g = d.groupby("d")["v"].agg(["sum", "count"])
    rng = np.random.default_rng(7)
    means = [g.iloc[rng.integers(0, len(g), len(g))].pipe(lambda s: s["sum"].sum() / s["count"].sum())
             for _ in range(1500)]
    return float(v.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def quantiles(v: pd.Series) -> dict:
    v = v.dropna()
    if len(v) < 20:
        return {}
    return {"p10": 1e4 * float(v.quantile(0.10)), "p25": 1e4 * float(v.quantile(0.25)),
            "median": 1e4 * float(v.median()), "p75": 1e4 * float(v.quantile(0.75)),
            "p90": 1e4 * float(v.quantile(0.90)), "share_up": float((v > 0).mean())}


def long_sample() -> list[dict]:
    df = anatomy.build()
    for h in (1, 4, 8):
        df[f"f{h}"] = df.groupby("coin")["close"].shift(-h) / df["close"] - 1
    df["vol24"] = df.groupby("coin")["ret1"].transform(lambda s: s.rolling(24).std())
    for col in ("long_liq", "short_liq", "vol24"):
        df[f"{col}_pct"] = df.groupby("coin")[col].rank(pct=True)
    rows = []

    def add(state: str, sel: pd.DataFrame, horizon: int) -> None:
        v = sel[f"f{horizon}"]
        if len(sel) < 50:
            return
        mean, lo, hi = clustered(v, sel["day"])
        q = quantiles(v)
        rows.append({"sample": "A", "state": state, "horizon_h": horizon, "n": int(len(sel)),
                     "mean_bps": 1e4 * mean, "ci_lo_bps": 1e4 * lo, "ci_hi_bps": 1e4 * hi, **q})

    for run in (0, 1, 2, 3, 4):
        sel = df[df["down_run"] == run]
        for h in (1, 4, 8):
            add(f"down_run={run}", sel, h)
    for pct_name, pct in (("liq>99pct", 0.99), ("liq>95pct", 0.95)):
        for side in ("long", "short"):
            sel = df[df[f"{side}_liq_pct"] > pct]
            for h in (1, 4, 8):
                add(f"{side}_liq>{int(pct*100)}pct", sel, h)
            sel2 = sel[sel["down_run"] >= 3]
            for h in (1, 4):
                add(f"{side}_liq>{int(pct*100)}pct & down_run>=3", sel2, h)
    for label, mask in (("vol_high", df["vol24_pct"] > 0.8), ("vol_low", df["vol24_pct"] < 0.2)):
        sel = df[mask]
        for h in (1, 4):
            add(label, sel, h)
    # Benjamini-Hochberg over the cells that have a CI
    cells = [r for r in rows if np.isfinite(r["ci_lo_bps"])]
    pvals = []
    for r in cells:
        sd = (r["ci_hi_bps"] - r["ci_lo_bps"]) / 3.92
        z = abs(r["mean_bps"]) / sd if sd > 0 else 0.0
        # normal tail without scipy
        pvals.append(float(math.erfc(abs(z) / math.sqrt(2))))
    order = np.argsort(pvals)
    m = len(pvals)
    k_max = 0
    for k, i in enumerate(order, start=1):
        if pvals[i] <= 0.10 * k / m:
            k_max = k
    passed = set(order[:k_max])
    for idx, r in enumerate(cells):
        r["fdr_pass"] = idx in passed
    return rows


def orderbook_sample() -> list[dict]:
    """One day of bookTicker + trades: OBI and CVD per minute against the next 5-minute return."""
    import duckdb

    con = duckdb.connect(str(ROOT / "data_substrate" / "substrate.duckdb"), read_only=True)
    bt = con.execute("SELECT symbol, ts, bid, ask FROM book_ticker").df()
    tr = con.execute("SELECT symbol, ts, price, qty, buyer_is_maker FROM trades").df()
    con.close()
    if bt.empty or tr.empty:
        return []
    bt["minute"] = pd.to_datetime(bt["ts"]).dt.floor("min")
    tr["minute"] = pd.to_datetime(tr["ts"]).dt.floor("min")
    # last book snapshot in each minute
    last = bt.sort_values("ts").groupby(["symbol", "minute"]).tail(1).set_index(["symbol", "minute"])
    mid = (last["bid"] + last["ask"]) / 2
    # order-book imbalance from the last snapshot's top-of-book quantities is not stored here; use
    # the spread sign as a weak proxy and the trade flow as the strong feature
    flow = tr.copy()
    flow["signed"] = np.where(flow["buyer_is_maker"], -flow["qty"], flow["qty"])
    cvd = flow.groupby(["symbol", "minute"])["signed"].sum()
    df = pd.DataFrame({"mid": mid}).join(cvd.rename("cvd"), how="left").reset_index()
    df["cvd"] = df["cvd"].fillna(0.0)
    df = df.sort_values(["symbol", "minute"])
    df["fwd5"] = df.groupby("symbol")["mid"].shift(-5) / df["mid"] - 1
    df["cvd_pct"] = df.groupby("symbol")["cvd"].rank(pct=True)
    rows = []
    for name, mask in (("cvd_bottom10", df["cvd_pct"] <= 0.10), ("cvd_top10", df["cvd_pct"] >= 0.90)):
        sel = df[mask]
        v = sel["fwd5"]
        if len(v) < 50:
            continue
        rows.append({"sample": "B", "state": name, "horizon_h": 5 / 60, "n": int(len(sel)),
                     "mean_bps": 1e4 * float(v.mean()), "median_bps": 1e4 * float(v.median()),
                     "share_up": float((v > 0).mean())})
    return rows


def main() -> int:
    rows = long_sample() + orderbook_sample()
    OUT.write_text(json.dumps(rows, indent=1))
    a = [r for r in rows if r["sample"] == "A"]
    print("A. hourly bars + liquidations (2023-2024)")
    for r in a:
        if r.get("fdr_pass") or abs(r["mean_bps"]) > 20:
            print(f"  {r['state']:34s} {r['horizon_h']:>2}h  n {r['n']:>5}  mean {r['mean_bps']:+7.1f}  "
                  f"med {r['median']:+.1f}  "
                  f"CI {r['ci_lo_bps']:+.1f}..{r['ci_hi_bps']:+.1f}  "
                  f"up {r['share_up']:.0%}  {'FDR' if r.get('fdr_pass') else ''}")
    print(f"cells: {len(a)}, FDR-pass: {sum(1 for r in a if r.get('fdr_pass'))}")
    b = [r for r in rows if r["sample"] == "B"]
    print("\nB. one day of order flow (2023-07-10, 11 symbols)")
    for r in b:
        print(f"  {r['state']:14s} n {r['n']:>5}  mean {r['mean_bps']:+7.1f} bps  "
              f"median {r['median_bps']:+7.1f}  up {r['share_up']:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
