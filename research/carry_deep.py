"""The deep carry test (#12): funding harvest, registered before the holdout was read.

Pre-registration: research/PREREGISTRATION_CARRY_DEEP.md (seal commit ac0bc24).
Universe: research/carry_universe.csv (25 symbols, frozen from 2024).

    python research/carry_deep.py --window design     # 2024
    python research/carry_deep.py --window holdout    # 2025-01..2025-06, once
    python research/carry_deep.py --window both
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import zipfile

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data_carry"
OUT = ROOT / "research" / "carry_deep.json"
UNIVERSE = [l.split(",")[0] for l in (ROOT / "research" / "carry_universe.csv").read_text().splitlines()[1:] if l]

ENTRY, EXIT, MAX_HOLD = 0.20, 0.05, 30          # registered thresholds
COST = 0.0030                                   # 30 bps round trip, split between entry and exit
VARIANTS = {"registered": (0.20, 0.05), "loose": (0.10, 0.00), "always": (0.0, 0.0)}


def read_zip(path: pathlib.Path, header: bool = True) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=None)
    if str(df.iloc[0, 0]) in {"open_time", "calc_time", "timestamp"}:
        df = df.iloc[1:].reset_index(drop=True)
    return df


def to_date(values) -> pd.Series:
    """Timestamps arrive in seconds, milliseconds or microseconds depending on the archive."""
    v = pd.to_numeric(values, errors="coerce")
    unit = "us" if v.max() > 1e14 else ("ms" if v.max() > 1e11 else "s")
    return pd.to_datetime(v, unit=unit).dt.date


def daily(symbol: str, year: int, months: int) -> pd.DataFrame:
    """date -> perp close, spot close, daily funding sum, per-day quote volume."""
    frames = []
    for m in range(1, months + 1):
        month = f"{year}-{m:02d}"
        paths = [RAW / k / symbol / f"{month}.zip" for k in ("perp", "spot", "funding")]
        if not all(p.exists() for p in paths):
            continue                      # a delisted symbol keeps its history and adds no zeros
        perp = read_zip(paths[0])
        spot = read_zip(paths[1])
        fund = read_zip(paths[2], header=False)
        perp = perp.iloc[:, [0, 4, 7]]
        perp.columns = ["ts", "perp", "qvol"]
        spot = spot.iloc[:, [0, 4]]
        spot.columns = ["ts", "spot"]
        fund = fund.iloc[:, [0, 2]]
        fund.columns = ["fts", "rate"]
        fund["rate"] = pd.to_numeric(fund["rate"], errors="coerce")
        perp["date"] = to_date(perp["ts"])
        spot["date"] = to_date(spot["ts"])
        fund["date"] = to_date(fund["fts"])
        d = perp[["date", "perp", "qvol"]].merge(spot[["date", "spot"]], on="date", how="inner")
        fr = fund.groupby("date")["rate"].agg(["sum", "count"]).reset_index()
        fr.columns = ["date", "fund_sum", "fund_n"]
        frames.append(d.merge(fr, on="date", how="left"))
    out = pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True)
    for c in ("perp", "spot", "qvol", "fund_sum"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out["fund_sum"] = out["fund_sum"].fillna(0.0)
    return out


def signal_table(df: pd.DataFrame) -> pd.DataFrame:
    """f3 annualised (last 9 intervals), basis, forward returns."""
    df = df.copy()
    df["rate"] = df["fund_sum"] / 3.0
    df["f3"] = df["rate"].rolling(3).mean() * 3 * 365       # 3 days = 9 intervals
    df["basis"] = df["perp"] / df["spot"] - 1
    df["spot_ret"] = df["spot"].pct_change()
    df["perp_ret"] = df["perp"].pct_change()
    df["basis_pnl"] = df["spot_ret"] - df["perp_ret"]
    return df


def run_symbol(df: pd.DataFrame, entry: float, exit_: float) -> pd.Series:
    """Daily net return of the delta-neutral harvest. Decisions at close t act from t+1:
    the entry day never earns the funding and basis move that produced the signal."""
    df = signal_table(df).dropna(subset=["f3", "basis", "spot_ret"]).reset_index(drop=True)
    pnl: dict = {}
    in_pos, held = False, 0
    for i in range(len(df)):
        day = df.at[i, "date"]
        if in_pos:
            pnl[day] = pnl.get(day, 0.0) + float(df.at[i, "fund_sum"] + df.at[i, "basis_pnl"])
            held += 1
            if df.at[i, "f3"] < exit_ or held >= MAX_HOLD:
                pnl[day] -= COST / 2                     # exit cost, paid on the exit day
                in_pos, held = False, 0
        if not in_pos and df.at[i, "f3"] > entry and df.at[i, "basis"] > 0:
            in_pos, held = True, 0
            pnl[day] = pnl.get(day, 0.0) - COST / 2      # entry cost, paid at the close of t
    return pd.Series(pnl).sort_index()


def portfolio(series: dict[str, pd.Series]) -> pd.DataFrame:
    daily = pd.concat(series, axis=1).sort_index()
    active = daily.notna().sum(axis=1)
    ret = daily.mean(axis=1, skipna=True)
    return pd.DataFrame({"ret": ret, "active": active}).dropna()


def stationary_bootstrap(x: np.ndarray, reps: int = 10000, block: int = 10, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    n = len(x)
    if n < 30:
        return {"lo": None, "hi": None, "mean": None}
    means = np.empty(reps)
    for i in range(reps):
        idx = np.empty(n, dtype=int)
        t = 0
        while t < n:
            start = rng.integers(0, n)
            length = min(int(rng.geometric(1 / block)), n - t)
            idx[t:t + length] = (start + np.arange(length)) % n
            t += length
        means[i] = x[idx].mean()
    return {"lo": float(np.percentile(means, 2.5)), "hi": float(np.percentile(means, 97.5)),
            "mean": float(x.mean())}


def nw_t(x: np.ndarray, lags: int = 10) -> float:
    n = len(x)
    m = x.mean()
    d = x - m
    var = float((d @ d) / n)
    for k in range(1, min(lags, n - 1) + 1):
        w = 1 - k / (lags + 1)
        var += 2 * w * float((d[k:] @ d[:-k]) / n)
    return m / np.sqrt(var / n) if var > 0 else float("nan")


def ar1_half_life(x: pd.Series) -> float:
    y = x.dropna().to_numpy()
    if len(y) < 30:
        return float("nan")
    phi = np.corrcoef(y[:-1], y[1:])[0, 1]
    return float(np.log(0.5) / np.log(phi)) if 0 < phi < 1 else float("nan")


def sharpe(r: pd.Series) -> float:
    return float(r.mean() / r.std(ddof=1) * np.sqrt(365)) if r.std(ddof=1) > 0 else float("nan")


def deflated_sharpe(sr_annual: float, n_trials: int, T: int) -> float:
    """Bailey & Lopez de Prado: P(true Sharpe > 0) after n_trials attempts, sr annualised."""
    from math import sqrt
    from statistics import NormalDist
    if not np.isfinite(sr_annual):
        return float("nan")
    e = 0.5772156649
    sr = sr_annual / sqrt(365)                       # per-period Sharpe for the formula
    z1 = NormalDist().inv_cdf(1 - 1 / max(n_trials, 2))
    z2 = NormalDist().inv_cdf(1 - 1 / (max(n_trials, 2) * e))
    sr0 = sqrt(1 / T) * ((1 - e) * z1 + e * z2)
    denom = sqrt(max(1e-9, 1 - sr * sr / 4))         # zero skew, zero excess kurtosis
    return float(NormalDist().cdf((sr - sr0) * sqrt(T - 1) / denom))


def placebo(prepared: dict, real_ann: float, reps: int = 1000, seed: int = 11) -> dict:
    """Random entry days on the same symbols, same 30-day hold; the real rule must beat 95%."""
    rng = np.random.default_rng(seed)
    usable = [(s["fund"], s["basis"]) for s in prepared.values()
              if len(s["fund"]) > MAX_HOLD + 5]
    if not usable:
        return {"mean": None, "p_value": None, "draws": 0}
    out = np.empty(reps)
    for i in range(reps):
        totals = []
        for fund, basis in usable:
            start = rng.integers(0, len(fund) - MAX_HOLD)
            totals.append(fund[start:start + MAX_HOLD].sum() + basis[start:start + MAX_HOLD].sum() - COST)
        out[i] = np.mean(totals)
    return {"mean": float(out.mean()), "p_value": float((out >= real_ann).mean()), "draws": reps}


def window_report(year: int, months: int, label: str) -> dict:
    dfs = {s: daily(s, year, months) for s in UNIVERSE}
    dfs = {s: d for s, d in dfs.items() if len(d) > 40}
    serials = {s: run_symbol(d, ENTRY, EXIT) for s, d in dfs.items()}
    port = portfolio(serials)
    r = port["ret"].to_numpy()
    if len(port) == 0:
        return {"label": label, "symbols": len(dfs), "days": 0, "entries": 0,
                "annualised_net_pct": 0.0, "ci95_annualised_pct": None, "nw_t": None,
                "sharpe": None, "avg_active_positions": 0.0,
                "funding_half_life_days": None, "gross_funding_annual_pct": None,
                "variants": {}, "deflated_sharpe_p": None,
                "placebo": {"mean": None, "p_value": None, "draws": 0},
                "note": "no entry signals in this window: the rule stayed flat"}
    boot = stationary_bootstrap(r)
    ann = float(r.mean() * 365)
    fund_daily = pd.concat([signal_table(d).set_index("date")["rate"] for d in dfs.values()], axis=1).mean(axis=1)
    rep = {
        "label": label, "symbols": len(dfs), "days": int(len(r)),
        "entries": int(sum(len(x) for x in serials.values())),
        "annualised_net_pct": 100 * ann,
        "ci95_annualised_pct": [100 * 365 * boot["lo"], 100 * 365 * boot["hi"]] if boot["lo"] is not None else None,
        "nw_t": nw_t(r), "sharpe": sharpe(port["ret"]),
        "avg_active_positions": float(port["active"].mean()),
        "funding_half_life_days": ar1_half_life(fund_daily),
        "gross_funding_annual_pct": 100 * float(fund_daily.mean() * 3 * 365),
    }
    variants = {}
    for name, (e, x) in VARIANTS.items():
        p = portfolio({s: run_symbol(d, e, x) for s, d in dfs.items()})
        variants[name] = {"annualised_net_pct": 100 * float(p["ret"].mean() * 365),
                          "sharpe": sharpe(p["ret"]), "days": int(len(p))}
    best = max(v["sharpe"] for v in variants.values() if np.isfinite(v["sharpe"]))
    rep["variants"] = variants
    rep["deflated_sharpe_p"] = deflated_sharpe(best, len(variants), len(r))
    prepared = {s: {"fund": signal_table(d)["fund_sum"].to_numpy(),
                    "basis": signal_table(d)["basis_pnl"].to_numpy()}
                for s, d in dfs.items()}
    rep["placebo"] = placebo(prepared, ann)
    return rep


def capacity(days: tuple[str, ...] = ("2024-03-15", "2024-06-15", "2024-09-15", "2024-12-15")) -> dict:
    """$ notional that moves the book by 0.46% (half a 30-day gross carry), from bookDepth."""
    rows = []
    for sym in UNIVERSE[:15]:
        for day in days:
            p = RAW / "depth" / sym / f"{day}.zip"
            if not p.exists():
                continue
            df = read_zip(p)
            df.columns = ["ts", "pct", "depth", "notional"]
            df["pct"] = pd.to_numeric(df["pct"], errors="coerce")
            df["notional"] = pd.to_numeric(df["notional"], errors="coerce")
            one = df[df["pct"] == 1]["notional"]
            if len(one):
                rows.append({"symbol": sym, "notional_at_1pct": float(one.median()),
                             "capacity_half_carry": float(one.median()) * 0.46})
    if not rows:
        return {}
    by = pd.DataFrame(rows).groupby("symbol")["capacity_half_carry"].median()
    return {"symbols": len(by), "median_capacity_usd": float(by.median()),
            "total_usd": float(by.sum())}


def reconcile(year: int, months: int) -> dict:
    """Published funding against the premium index's 8-hour mean.

    Binance's rule is funding = premium + clamp(interest - premium, +/-5 bps), so equality is not
    expected: what must hold is correlation, sign agreement where the premium is large, and the
    clamp showing up as a ~-5 bps gap when the premium exceeds the interest rate.
    """
    rates, prem, agree_big, gaps = [], [], [], []
    for sym in UNIVERSE[:6]:
        d = daily(sym, year, months).set_index("date")
        frames = []
        for m in range(1, months + 1):
            p = RAW / "premium1h" / sym / f"{year}-{m:02d}.zip"
            if not p.exists():
                continue
            pr = read_zip(p)
            pr.columns = ["ts", "open", "high", "low", "close", "vol", "close_time", "qvol",
                          "count", "tb", "tbq", "ignore"]
            pr["premium"] = pd.to_numeric(pr["close"], errors="coerce")
            pr["t"] = pd.to_datetime(pd.to_numeric(pr["ts"], errors="coerce") // 1000, unit="s")
            frames.append(pr[["t", "premium"]])
        if not frames:
            continue
        pr = pd.concat(frames).set_index("t")["premium"]
        for day, row in d.iterrows():
            rate = row["fund_sum"] / 3.0
            if rate == 0 or pd.isna(rate):
                continue
            for h in (0, 8, 16):
                start = pd.Timestamp(f"{day} {h:02d}:00")
                mean_prem = pr.loc[start:start + pd.Timedelta(hours=8)].mean()
                if pd.isna(mean_prem):
                    continue
                rates.append(rate)
                prem.append(mean_prem)
                if abs(mean_prem) > 0.0005:
                    agree_big.append(np.sign(rate) == np.sign(mean_prem))
                    gaps.append(rate - mean_prem)
    if not rates:
        return {}
    return {"intervals": len(rates),
            "correlation": float(pd.Series(rates).corr(pd.Series(prem))),
            "sign_agreement_large_premium": float(np.mean(agree_big)) if agree_big else None,
            "large_premium_intervals": len(agree_big),
            "median_funding_minus_premium_bps": float(1e4 * np.median(gaps)) if gaps else None}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="both", choices=["design", "holdout", "both"])
    args = ap.parse_args(argv)
    out = {}
    if args.window in ("design", "both"):
        out["design"] = window_report(2024, 12, "2024 (design)")
    if args.window in ("holdout", "both"):
        out["holdout"] = window_report(2025, 6, "2025H1 (holdout)")
    out["seal"] = "ac0bc24"
    out["capacity"] = capacity()
    out["reconciliation"] = reconcile(2024, 12)
    OUT.write_text(json.dumps(out, indent=1, default=str))
    for k in ("design", "holdout"):
        if k in out:
            r = out[k]
            if r.get("note"):
                print(f"\n{r['label']}: {r['note']} ({r['symbols']} symbols, {r['entries']} entries)")
                continue
            print(f"\n{r['label']}: {r['symbols']} symbols, {r['days']} days")
            print(f"  annualised net {r['annualised_net_pct']:+.1f}%  "
                  f"CI95 {r['ci95_annualised_pct'][0]:+.1f}..{r['ci95_annualised_pct'][1]:+.1f}%  "
                  f"NW t {r['nw_t']:.2f}  Sharpe {r['sharpe']:.2f}")
            print(f"  funding {r['gross_funding_annual_pct']:+.1f}%/yr, half-life "
                  f"{r['funding_half_life_days']:.1f} days, avg positions {r['avg_active_positions']:.2f}")
            print(f"  variants: " + ", ".join(f"{k} {v['annualised_net_pct']:+.1f}%/yr" for k, v in r["variants"].items()))
            print(f"  deflated Sharpe p {r['deflated_sharpe_p']:.3f}; placebo p {r['placebo']['p_value']}")
    if out.get("capacity"):
        c = out["capacity"]
        print(f"\ncapacity: median ${c['median_capacity_usd']:,.0f} per symbol at half-carry impact; "
              f"${c['total_usd']:,.0f} across {c['symbols']}")
    r = out["reconciliation"]
    print(f"reconciliation: {r['intervals']} intervals, corr {r['correlation']:.2f}, "
          f"sign agreement (|premium|>5bps) {r['sign_agreement_large_premium']:.1%} over "
          f"{r['large_premium_intervals']}, funding-premium median "
          f"{r['median_funding_minus_premium_bps']:+.1f} bps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
