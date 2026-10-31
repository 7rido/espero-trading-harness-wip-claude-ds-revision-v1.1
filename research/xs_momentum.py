"""Cross-sectional momentum, deep (#2/#7): weekly quintile book, sealed design 2021-2022, holdout 2023.

Pre-registration: research/PREREGISTRATION_XS_MOMENTUM.md (seal 95005ac, universe 53ffbfc).
    python research/xs_momentum.py --window design
    python research/xs_momentum.py --window holdout   # once
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
RAW = ROOT / "data_xs"
OUT = ROOT / "research" / "xs_momentum.json"
UNIVERSE = [l.split(",")[0] for l in (ROOT / "research" / "xs_universe.csv").read_text().splitlines()[1:] if l]
FEE = 5e-4                      # 5 bps per unit of weight traded
LOOKBACK, HOLD_DAYS = 30, 7
QUINTILE = 5


def read_zip(path: pathlib.Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=None)
    if str(df.iloc[0, 0]) in {"open_time", "calc_time"}:
        df = df.iloc[1:].reset_index(drop=True)
    return df


def to_date(v) -> pd.Series:
    v = pd.to_numeric(v, errors="coerce")
    unit = "us" if v.max() > 1e14 else ("ms" if v.max() > 1e11 else "s")
    return pd.to_datetime(v, unit=unit).dt.normalize()


def load(sym: str, year_from: int, year_to: int) -> tuple[pd.Series, pd.Series]:
    closes, funds = [], []
    for y in range(year_from, year_to + 1):
        for m in range(1, 13):
            p = RAW / "perp" / sym / f"{y}-{m:02d}.zip"
            if p.exists():
                df = read_zip(p)
                df.columns = ["ts", "open", "high", "low", "close", "vol", "ct", "qvol", "n",
                              "tb", "tbq", "ignore"][: df.shape[1]]
                closes.append(pd.Series(pd.to_numeric(df["close"], errors="coerce").to_numpy(),
                                        index=to_date(df["ts"])))
            f = RAW / "funding" / sym / f"{y}-{m:02d}.zip"
            if f.exists():
                fd = read_zip(f)
                fd.columns = ["ts", "hours", "rate"][: fd.shape[1]]
                rate = pd.to_numeric(fd["rate"], errors="coerce")
                day = to_date(fd["ts"])
                funds.append(pd.Series(rate.to_numpy(), index=day).groupby(level=0).sum())
    close = pd.concat(closes).sort_index() if closes else pd.Series(dtype=float)
    fund = pd.concat(funds).sort_index() if funds else pd.Series(dtype=float)
    return close[~close.index.duplicated()], fund[~fund.index.duplicated()]


def panel(year_from: int, year_to: int):
    closes, funds = {}, {}
    for s in UNIVERSE:
        c, f = load(s, year_from, year_to)
        if len(c) > 60:
            closes[s], funds[s] = c, f
    px = pd.DataFrame(closes).sort_index()
    fu = pd.DataFrame(funds).sort_index().reindex(px.index).fillna(0.0)
    return px, fu


def run_window(year_from: int, year_to: int, lookback: int, hold: int,
               seed: int | None = None, flip: bool = False):
    px, fu = panel(year_from, year_to)
    rets = px.pct_change().fillna(0.0)
    dates = px.index
    signal = px / px.shift(lookback) - 1
    fridays = [d for d in dates if d.weekday() == 4]
    daily = pd.Series(0.0, index=dates)
    pos = pd.Series(dtype=float)
    rng = np.random.default_rng(seed) if seed is not None else None
    for f in fridays[:-1]:
        sig = signal.loc[f].dropna()
        sig = sig[np.isfinite(sig)]
        if len(sig) < 10:
            continue
        k = max(1, len(sig) // QUINTILE)
        if rng is not None:
            picks = rng.permutation(len(sig))
            longs, shorts = sig.index[picks[:k]], sig.index[picks[-k:]]
        else:
            longs, shorts = sig.nlargest(k).index, sig.nsmallest(k).index
            if flip:
                longs, shorts = shorts, longs
        new = pd.Series(0.0, index=px.columns)
        new[longs] = 1.0 / k
        new[shorts] = -1.0 / k
        turnover = float((new - pos).abs().sum())
        window = [d for d in dates if f < d <= f + pd.Timedelta(days=hold)]
        if not window:
            continue
        cost = turnover * FEE
        for d in window:
            r = float((new * rets.loc[d]).sum())
            fund = float((new * fu.loc[d].reindex(px.columns).fillna(0.0)).sum())
            daily.loc[d] += r - fund
        daily.loc[window[0]] -= cost
        pos = new
    weekly = daily.resample("W-FRI").sum()
    return weekly[weekly.index >= pd.Timestamp(f"{year_from}-01-01", tz=None)]


def stationary_bootstrap(x: np.ndarray, reps: int = 10000, block: int = 8, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    n = len(x)
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
    return {"lo": float(np.percentile(means, 2.5)), "hi": float(np.percentile(means, 97.5))}


def nw_t(x: np.ndarray, lags: int = 8) -> float:
    n = len(x); m = x.mean(); d = x - m
    var = float((d @ d) / n)
    for k in range(1, min(lags, n - 1) + 1):
        var += 2 * (1 - k / (lags + 1)) * float((d[k:] @ d[:-k]) / n)
    return m / np.sqrt(var / n) if var > 0 else float("nan")


def sharpe(weekly: pd.Series) -> float:
    return float(weekly.mean() / weekly.std(ddof=1) * np.sqrt(52)) if weekly.std(ddof=1) > 0 else float("nan")


def deflated_sharpe(sr_annual: float, n_trials: int, T: int) -> float:
    from math import sqrt
    from statistics import NormalDist
    if not np.isfinite(sr_annual):
        return float("nan")
    e = 0.5772156649
    sr = sr_annual / sqrt(52)
    z1 = NormalDist().inv_cdf(1 - 1 / max(n_trials, 2))
    z2 = NormalDist().inv_cdf(1 - 1 / (max(n_trials, 2) * e))
    sr0 = sqrt(1 / T) * ((1 - e) * z1 + e * z2)
    return float(NormalDist().cdf((sr - sr0) * sqrt(T - 1) / sqrt(max(1e-9, 1 - sr * sr / 4))))


def report(year_from: int, year_to: int, label: str) -> dict:
    weekly = run_window(year_from, year_to, LOOKBACK, HOLD_DAYS)
    w = weekly.to_numpy()
    w = w[np.isfinite(w)]
    if len(w) < 8:
        return {"label": label, "weeks": int(len(w)), "note": "too few weeks"}
    boot = stationary_bootstrap(w)
    ann = 52 * float(w.mean())
    variants = {
        "registered_30d_7d": {"ann_pct": 100 * ann, "sharpe": sharpe(weekly)},
        "lookback_7d": {"ann_pct": 100 * 52 * float(run_window(year_from, year_to, 7, HOLD_DAYS).mean())},
        "hold_14d": {"ann_pct": 100 * 52 * float(run_window(year_from, year_to, LOOKBACK, 14).mean())},
    }
    flipped = run_window(year_from, year_to, LOOKBACK, HOLD_DAYS, flip=True)
    flipped = pd.Series(flipped.to_numpy(), index=flipped.index)
    shuffled = run_window(year_from, year_to, LOOKBACK, HOLD_DAYS, seed=42)
    ac = float(weekly.autocorr()) if len(w) > 3 else float("nan")
    rep = {
        "label": label, "weeks": int(len(w)), "ann_net_pct": 100 * ann,
        "ci95_pct": [100 * 52 * boot["lo"], 100 * 52 * boot["hi"]],
        "nw_t": nw_t(w), "sharpe": sharpe(weekly),
        "variants": variants,
        "deflated_sharpe_p": deflated_sharpe(max(v.get("sharpe", np.nan) for v in variants.values()), len(variants), len(w)),
        "placebo_signflip_ann_pct": 100 * 52 * float(flipped.mean()),
        "placebo_shuffle_ann_pct": 100 * 52 * float(shuffled.mean()),
        "autocorr": ac,
        "half_life_weeks": float(np.log(0.5) / np.log(ac)) if 0 < ac < 1 else float("nan"),
    }
    return rep


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="both", choices=["design", "holdout", "both"])
    args = ap.parse_args(argv)
    out = {}
    if args.window in ("design", "both"):
        out["design"] = report(2021, 2022, "2021-2022 (design)")
    if args.window in ("holdout", "both"):
        out["holdout"] = report(2023, 2023, "2023 (holdout)")
    out["seal"] = "95005ac"
    OUT.write_text(json.dumps(out, indent=1, default=str))
    for k in ("design", "holdout"):
        if k in out:
            r = out[k]
            if r.get("note"):
                print(f"\n{r['label']}: {r['note']}")
                continue
            print(f"\n{r['label']}: {r['weeks']} weeks, annualised net {r['ann_net_pct']:+.1f}% "
                  f"CI95 {r['ci95_pct'][0]:+.1f}..{r['ci95_pct'][1]:+.1f}, NW t {r['nw_t']:.2f}, "
                  f"Sharpe {r['sharpe']:.2f}")
            print(f"  variants: " + ", ".join(f"{k} {v.get('ann_pct', float('nan')):+.1f}%" for k, v in r["variants"].items()))
            print(f"  placebo: sign-flip {r['placebo_signflip_ann_pct']:+.1f}%/yr, shuffling "
                  f"{r['placebo_shuffle_ann_pct']:+.1f}%/yr; signal autocorr {r['autocorr']:.2f} "
                  f"(half-life {r['half_life_weeks']:.1f} weeks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
