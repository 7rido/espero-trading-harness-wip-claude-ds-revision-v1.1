"""RG1: do regime states separate forward market returns?

    python research/regimes.py build     # compute the nine state series, save regimes.csv
    python research/regimes.py test      # validation 2023 + holdout (sealed once, per the prereg)

Seal: 71fc5ea. Definitions and thresholds are in research/PREREGISTRATION_REGIMES.md.
"""
from __future__ import annotations

import gzip
import json
import pathlib
import sys

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
LIQ2 = ROOT / "data_raw" / "liq2"
OUT = ROOT / "research" / "regimes.csv"
RES = ROOT / "research" / "regimes.json"
DESIGN = ("2020-01-01", "2022-12-31")
VALID = ("2023-01-01", "2023-12-31")
HOLDOUT = ("2025-07-01", "2026-03-31")


def load():
    con = duckdb.connect(str(DB), read_only=True)
    bars = con.execute("SELECT symbol, date, close, qvol FROM bars_daily ORDER BY date").df()
    rv = con.execute("SELECT symbol, date, rv FROM rv ORDER BY date").df()
    fund = con.execute("SELECT symbol, ts, rate FROM funding").df()
    con.close()
    for d in (bars, rv):
        d["date"] = pd.to_datetime(d["date"])
    fund["date"] = pd.to_datetime(fund["ts"]).dt.normalize()
    return bars, rv, fund


def market_index(bars: pd.DataFrame) -> pd.Series:
    px = bars.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    px = px.replace([np.inf, -np.inf], np.nan).where(lambda x: x > 0)
    return np.log(px).mean(axis=1).rename("M")


def build() -> pd.DataFrame:
    bars, rv, fund = load()
    M = market_index(bars)
    px = bars.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    px = px.replace([np.inf, -np.inf], np.nan).where(lambda x: x > 0)

    mkt_rv = rv.pivot_table(index="date", columns="symbol", values="rv", aggfunc="mean").mean(axis=1)
    mkt_rv = mkt_rv.reindex(M.index).interpolate(limit=3)

    s = pd.DataFrame(index=M.index)
    s["M"] = M
    s["trend_sma"] = (M.rolling(20).mean() > M.rolling(50).mean())
    s["trend_200"] = (M > M.rolling(200).mean())
    s["trend_20d"] = (M / M.shift(20) - 1 > 0)
    s["rv"] = mkt_rv
    s["rv_w"] = mkt_rv.rolling(5).mean()
    s["rv_m"] = mkt_rv.rolling(22).mean()
    s["volofvol"] = mkt_rv.rolling(20).std()
    s["dd"] = M / M.rolling(90).max() - 1
    above = (px > px.rolling(50).mean()).sum(axis=1) / px.notna().sum(axis=1)
    s["breadth"] = above
    rets = np.log(px).diff()
    top = list(rets.columns[:20])
    corr_by_date = {}
    for i in range(30, len(M.index), 5):
        win = rets[top].iloc[i - 30:i]
        c = win.corr().to_numpy()
        iu = np.triu_indices(c.shape[0], 1)
        corr_by_date[M.index[i]] = float(np.nanmean(c[iu])) if c.shape[0] > 1 else np.nan
    s["corr"] = pd.Series(corr_by_date).reindex(M.index).ffill()
    s["liquidity"] = bars.groupby("date")["qvol"].median().reindex(M.index)
    fu = fund.groupby(["date", "symbol"])["rate"].sum().reset_index()
    s["funding"] = fu.groupby("date")["rate"].median().reindex(M.index).fillna(0.0)

    design = s.loc[DESIGN[0]:DESIGN[1]]
    # HAR on the market RV, fitted on design only
    d = design.dropna(subset=["rv", "rv_w", "rv_m"])
    y = np.log(d["rv"].shift(-1)).to_numpy()
    X = np.column_stack([np.ones(len(d)), np.log(d["rv"]), np.log(d["rv_w"]), np.log(d["rv_m"])])
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)   # logs of positive rv only; isfinite rejects 0
    beta, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
    Xall = np.column_stack([np.ones(len(s)), np.log(s["rv"]), np.log(s["rv_w"]), np.log(s["rv_m"])])
    s["har_forecast"] = np.exp(Xall @ beta)
    design = s.loc[DESIGN[0]:DESIGN[1]]        # refreshed: it now carries har_forecast
    for col, name in (("har_forecast", "vol_har"), ("volofvol", "volofvol_low"), ("breadth", "breadth_high"),
                      ("corr", "corr_high"), ("liquidity", "liq_high")):
        thr = float(design[col].median())
        s[name] = s[col] < thr if name in ("vol_har", "volofvol_low") else s[col] > thr
    s["funding_pos"] = s["funding"] >= 0
    s["dd_ok"] = s["dd"] > -0.10
    s["har_trend"] = s["vol_har"] & s["trend_200"]
    s["liq_stress_low"] = np.nan          # no design-window liquidations: descriptive only
    s.to_csv(OUT)
    return s


def nw_t(x: np.ndarray, lags: int = 5) -> float:
    x = x[np.isfinite(x)]
    if len(x) < 10:
        return float("nan")
    m, d = x.mean(), x - x.mean()
    var = float(d @ d) / len(x)
    for k in range(1, min(lags, len(x) - 1) + 1):
        var += 2 * (1 - k / (lags + 1)) * float(d[k:] @ d[:-k]) / len(x)
    return m / np.sqrt(var / len(x)) if var > 0 else float("nan")


FAMILIES = ["trend_sma", "trend_200", "trend_20d", "vol_har", "volofvol_low", "breadth_high",
            "corr_high", "funding_pos", "dd_ok", "liq_high", "har_trend"]


def ols_nw(f: np.ndarray, s: np.ndarray, lags: int = 5) -> tuple[float, float]:
    """Coefficient on the state and its Newey-West t from f = a + b*s."""
    X = np.column_stack([np.ones(len(s)), s])
    beta, *_ = np.linalg.lstsq(X, f, rcond=None)
    resid = f - X @ beta
    n = len(f)
    S = (resid[:, None] * X).T @ (resid[:, None] * X)          # sum of (x e)(x e)'
    for k in range(1, min(lags, n - 1) + 1):
        w = 1 - k / (lags + 1)
        G = (resid[k:, None] * X[k:]).T @ (resid[:-k, None] * X[:-k])
        S += w * (G + G.T)
    XtX_inv = np.linalg.inv(X.T @ X)
    cov = XtX_inv @ S @ XtX_inv
    se = float(np.sqrt(max(cov[1, 1], 1e-18)))
    return float(beta[1]), float(beta[1] / se)


def test(s: pd.DataFrame, window: tuple[str, str], label: str, seed: int = 11) -> list[dict]:
    w = s.loc[window[0]:window[1]].copy()
    fwd = (w["M"].shift(-5) / w["M"] - 1).rename("fwd")
    rows = []
    rng = np.random.default_rng(seed)
    for fam in FAMILIES:
        if fam not in w.columns or w[fam].dtype == object:
            continue
        frame = pd.DataFrame({"f": fwd, "s": w[fam].astype(float)}).dropna()
        on, off = frame[frame["s"] > 0.5], frame[frame["s"] <= 0.5]
        if len(on) < 20 or len(off) < 20:
            rows.append({"window": label, "family": fam, "on_days": int(len(on)), "off_days": int(len(off)),
                         "diff_bps": float("nan"), "t": float("nan"), "p_perm": float("nan"),
                         "h1_bps": float("nan"), "h2_bps": float("nan"), "same_sign": False,
                         "fdr_pass": False, "note": "one state has fewer than 20 days"})
            continue
        diff = float(on["f"].mean() - off["f"].mean())
        _, tstat = ols_nw(frame["f"].to_numpy(), frame["s"].to_numpy())
        half = len(frame) // 2
        halves = []
        for part in (frame.iloc[:half], frame.iloc[half:]):
            a, b = part[part["s"] > 0.5]["f"], part[part["s"] <= 0.5]["f"]
            halves.append(float(a.mean() - b.mean()) if len(a) >= 5 and len(b) >= 5 else float("nan"))
        sv = frame["s"].to_numpy()
        null = []
        for _ in range(500):
            perm = rng.permutation(sv)
            null.append(frame["f"].to_numpy()[perm > 0.5].mean() - frame["f"].to_numpy()[perm <= 0.5].mean())
        p_perm = float(np.mean(np.abs(null) >= abs(diff)))
        rows.append({"window": label, "family": fam, "on_days": int(len(on)), "off_days": int(len(off)),
                     "diff_bps": 1e4 * diff, "t": tstat, "p_perm": p_perm,
                     "h1_bps": 1e4 * halves[0], "h2_bps": 1e4 * halves[1],
                     "same_sign": bool(np.sign(halves[0]) == np.sign(halves[1]))
                     if np.isfinite(halves[0]) and np.isfinite(halves[1]) else False,
                     "note": ""})
    return rows


def bh(rows: list[dict]) -> None:
    """Benjamini-Hochberg at 10%: p_(k) <= 0.10*k/m for the largest k, then all rank <= k pass."""
    m = len(rows)
    order = sorted(range(m), key=lambda i: rows[i]["p_perm"])
    k_max = 0
    for k, i in enumerate(order, start=1):
        if rows[i]["p_perm"] <= 0.10 * k / m:
            k_max = k
    passed = set(order[:k_max])
    for idx, r in enumerate(rows):
        r["fdr_pass"] = idx in passed


def main(argv: list[str]) -> int:
    what = argv[0] if argv else "build"
    if what == "build":
        s = build()
        print(f"regimes: {len(s)} days, {int(s['M'].notna().sum())} with a market index; saved {OUT.name}")
        print("states:", {c: int(s[c].sum()) for c in FAMILIES if c in s and s[c].dtype == bool})
        return 0
    s = pd.read_csv(OUT, index_col=0, parse_dates=True)
    val = test(s, VALID, "validation 2023")
    bh(val)
    hold = test(s, HOLDOUT, "holdout 2025-07..2026-03")
    bh(hold)
    out = {"validation": val, "holdout": hold}
    RES.write_text(json.dumps(out, indent=1))
    for label, rows in (("validation 2023", val), ("holdout", hold)):
        print(f"\n{label}:")
        for r in sorted(rows, key=lambda r: -abs(r["t"] if np.isfinite(r["t"]) else 0)):
            print(f"  {r['family']:14s} diff {r['diff_bps']:+7.1f} bps  t {r['t']:+.2f}  "
                  f"p_perm {r['p_perm']:.3f}  fdr {'PASS' if r['fdr_pass'] else 'fail'}  "
                  f"halves {r['h1_bps']:+.1f}/{r['h2_bps']:+.1f}  "
                  f"on/off {r['on_days']}/{r['off_days']}d {r['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
