"""A suite of state-conditional event studies over all the data we hold.

    python research/conditional_suite.py

Sample D: daily bars, 42 symbols, 2020-2026 (from the substrate), joined with funding, premium,
breadth and correlation regimes. Outcomes: 1/3/7-day forward returns, reported as quantiles and hit
rates — risk, not direction.  Every cell reports n, the 10-90 band, and whether it survives FDR.
"""
from __future__ import annotations

import json
import pathlib

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
OUT = ROOT / "research" / "conditional_suite.json"
MIN_N = 100


def load() -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    bars = con.execute("SELECT symbol, date, close, high, low, qvol FROM bars_daily ORDER BY date").df()
    fund = con.execute("SELECT symbol, CAST(ts AS DATE) AS date, rate FROM funding").df()
    prem = con.execute("SELECT symbol, date, premium FROM premium").df()
    con.close()
    for d in (bars, fund, prem):
        d["date"] = pd.to_datetime(d["date"])
    f = fund.groupby(["symbol", "date"])["rate"].sum().rename("funding").reset_index()
    df = bars.merge(f, on=["symbol", "date"], how="left").merge(prem, on=["symbol", "date"], how="left")
    reg = pd.read_csv(ROOT / "research" / "regimes.csv", index_col=0, parse_dates=True)
    df = df.merge(reg[["breadth", "corr"]].reset_index().rename(columns={"index": "date"}),
                  on="date", how="left")
    return df


def features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["symbol", "date"]).copy()
    g = df.groupby("symbol")
    df["ret"] = g["close"].pct_change()
    df["run_down"] = 0
    run = 0
    for i, r in enumerate(df["ret"].to_numpy()):
        run = run + 1 if np.isfinite(r) and r < 0 else 0
        df.iloc[i, df.columns.get_loc("run_down")] = min(run, 7)
    df["high20"] = g["close"].transform(lambda s: s.rolling(20).max())
    df["dist_high"] = df["close"] / df["high20"] - 1
    df["vol20"] = g["ret"].transform(lambda s: s.rolling(20).std())
    df["vol_pct"] = g["vol20"].transform(lambda s: s.rolling(252, min_periods=60).rank(pct=True))
    df["qvol_pct"] = g["qvol"].transform(lambda s: s.rolling(252, min_periods=60).rank(pct=True))
    df["funding_pct"] = g["funding"].transform(lambda s: s.rolling(252, min_periods=60).rank(pct=True))
    for h in (1, 3, 7):
        df[f"f{h}"] = g["close"].shift(-h) / df["close"] - 1
        # market-relative outcome: this coin's forward return minus the same day's cross-section
        df[f"x{h}"] = df[f"f{h}"] - df.groupby("date")[f"f{h}"].transform("mean")
    return df


def quantiles(v: pd.Series) -> dict:
    v = v.dropna()
    if len(v) < MIN_N:
        return {}
    return {"mean_bps": 1e4 * float(v.mean()), "median_bps": 1e4 * float(v.median()),
            "p10": 1e4 * float(v.quantile(0.10)), "p25": 1e4 * float(v.quantile(0.25)),
            "p75": 1e4 * float(v.quantile(0.75)), "p90": 1e4 * float(v.quantile(0.90)),
            "share_up": float((v > 0).mean()), "n": int(len(v))}


def main() -> int:
    df = features(load())
    states: dict[str, pd.Series] = {}
    for run in (1, 2, 3, 4, 5):
        states[f"run_down={run}"] = df["run_down"] == run
    states["10% below 20d high"] = df["dist_high"] < -0.10
    states["3% below 20d high"] = df["dist_high"] < -0.03
    states["vol top quintile"] = df["vol_pct"] > 0.8
    states["vol bottom quintile"] = df["vol_pct"] < 0.2
    states["volume top quintile"] = df["qvol_pct"] > 0.8
    states["funding negative"] = df["funding"] < 0
    states["funding top quintile"] = df["funding_pct"] > 0.8
    states["funding bottom quintile"] = df["funding_pct"] < 0.2
    states["premium negative"] = df["premium"] < 0
    states["premium top quintile"] = df["premium"] > df.groupby("symbol")["premium"].transform(
        lambda s: s.rolling(252, min_periods=60).quantile(0.8))
    states["down run>=3 and vol high"] = (df["run_down"] >= 3) & (df["vol_pct"] > 0.8)
    states["down run>=3 and funding high"] = (df["run_down"] >= 3) & (df["funding_pct"] > 0.8)

    rows = []
    for name, mask in states.items():
        sel = df[mask.fillna(False)]
        for h in (1, 3, 7):
            q = quantiles(sel[f"x{h}"])
            if q:
                rows.append({"state": name, "horizon_d": h, "fdr_pass": False, **q})
    # BH over cells, using the normal tail of mean/(implied SE from the 10-90 band)
    pvals = []
    for r in rows:
        sd = (r["p90"] - r["p10"]) / 2.563                 # implied cross-sectional dispersion
        n_eff = max(r["n"] / r["horizon_d"], 30)           # overlapping windows
        se = sd / np.sqrt(n_eff)
        z = abs(r["mean_bps"]) / se if se > 0 else 0.0
        # two-sided normal tail
        pvals.append(float(2 * (1 - 0.5 * (1 + np.tanh(z / np.sqrt(2) * 0.7978845608)))))
    order = np.argsort(pvals)
    m = len(pvals)
    k_max = 0
    for k, i in enumerate(order, start=1):
        if pvals[i] <= 0.10 * k / m:
            k_max = k
    for idx in order[:k_max]:
        rows[idx]["fdr_pass"] = True

    OUT.write_text(json.dumps(rows, indent=1))
    print(f"{len(states)} states x 3 horizons = {len(rows)} cells; "
          f"FDR-pass {sum(1 for r in rows if r['fdr_pass'])}")
    print(f"{'state':34s} {'h':>2} {'n':>6} {'mean':>8} {'median':>8} {'p10':>8} {'p90':>8} {'up':>5} {'FDR'}")
    for r in sorted(rows, key=lambda r: abs(r["mean_bps"] / max((r["p90"] - r["p10"]) / 2.563, 1e-9)),
                    reverse=True)[:22]:
        print(f"{r['state']:34s} {r['horizon_d']:>2} {r['n']:>6} {r['mean_bps']:>+8.1f} "
              f"{r['median_bps']:>+8.1f} {r['p10']:>+8.1f} {r['p90']:>+8.1f} {r['share_up']:>4.0%} "
              f"{'yes' if r['fdr_pass'] else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
