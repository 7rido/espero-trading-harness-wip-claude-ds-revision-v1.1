"""RP2: regime-conditioned residual pairs. Seal c1ec15b.

    python research/residual_pairs.py scan        # design only: discover and freeze
    python research/residual_pairs.py validate    # 2023 evidence for the frozen pairs
Holdout 2025-07..2026-03 is never touched here.
"""
from __future__ import annotations

import json
import pathlib

import duckdb
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
FROZEN = ROOT / "research" / "pair_regime_frozen.csv"
OUT = ROOT / "research" / "residual_pairs.json"
DESIGN = ("2020-01-01", "2022-12-31")
VALID = ("2023-01-01", "2023-12-31")
WINDOW = 180
FEE = 5e-4
N_UNIVERSE = 30


def load() -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    df = con.execute("SELECT symbol, date, close, qvol FROM bars_daily ORDER BY date").df()
    con.close()
    df["date"] = pd.to_datetime(df["date"])
    return df


def half_life(spread: np.ndarray) -> float:
    s = spread[np.isfinite(spread)]
    if len(s) < 30:
        return float("nan")
    x, y = s[:-1], np.diff(s)
    beta = float(np.polyfit(x - x.mean(), y, 1)[0])
    rho = 1 + beta
    return float(-np.log(2) / np.log(rho)) if 0 < rho < 1 else float("nan")


def adf_p(x: np.ndarray) -> float:
    try:
        return float(adfuller(x, maxlag=1, regression="c", autolag="AIC", result_object=False)[1])
    except Exception:
        return float("nan")


def residuals(window: pd.DataFrame, mkt: pd.Series) -> dict[str, np.ndarray]:
    """log p_i on log M over the window -> residual series, symbol keyed."""
    out = {}
    lm = np.log(mkt.reindex(window.index).to_numpy())
    for c in window.columns:
        y = np.log(window[c].to_numpy())
        ok = np.isfinite(y) & np.isfinite(lm)
        if ok.sum() < 120:
            continue
        X = np.column_stack([np.ones(ok.sum()), lm[ok]])
        beta = np.linalg.lstsq(X, y[ok], rcond=None)[0]
        out[c] = y - (beta[0] + beta[1] * lm)
    return out


def scan() -> None:
    df = load()
    px = df.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    px = px.replace([np.inf, -np.inf], np.nan).where(lambda x: x > 0)
    design = px.loc[DESIGN[0]:DESIGN[1]]
    vol = df[(df["date"] >= DESIGN[0]) & (df["date"] <= DESIGN[1])].groupby("symbol")["qvol"].median()
    names = [s for s in vol.sort_values(ascending=False).head(N_UNIVERSE).index if s in px.columns]
    mkt = np.exp(np.log(px[names]).mean(axis=1)).rename("M")
    ends = pd.date_range("2022-01-31", "2022-12-31", freq="ME")
    rows = []
    for e in ends:
        w = px.loc[:e].iloc[-WINDOW:]
        if len(w) < 120:
            continue
        res = residuals(w, mkt.loc[w.index])
        for i, a in enumerate(names):
            if a not in res:
                continue
            for b in names[i + 1:]:
                if b not in res:
                    continue
                ea, eb = res[a], res[b]
                ok = np.isfinite(ea) & np.isfinite(eb)
                if ok.sum() < 120:
                    continue
                X = np.column_stack([np.ones(ok.sum()), eb[ok]])
                beta = np.linalg.lstsq(X, ea[ok], rcond=None)[0]
                spread = ea[ok] - X @ beta
                rows.append({"end": e, "a": a, "b": b, "adf_p": adf_p(spread),
                             "half_life": half_life(spread), "pair_beta": float(beta[1]),
                             "pair_alpha": float(beta[0])})
    allf = pd.DataFrame(rows)
    allf.to_csv(ROOT / "research" / "residual_pairs_all.csv", index=False)
    agg = (allf.groupby(["a", "b"])
           .agg(median_adf_p=("adf_p", "median"), median_half_life=("half_life", "median"),
                share_sig=("adf_p", lambda s: float(np.mean(np.asarray(s) < 0.05))),
                last_beta=("pair_beta", "last"), last_alpha=("pair_alpha", "last"),
                n=("adf_p", "size"))
           .reset_index().sort_values("median_adf_p"))
    m = len(agg)
    agg["bh_rank"] = np.arange(1, m + 1)
    agg["fdr_pass"] = agg["median_adf_p"] <= 0.10 * agg["bh_rank"] / m
    keep = agg[agg["fdr_pass"] & agg["median_half_life"].between(5, 30) & (agg["share_sig"] >= 0.6)]
    keep[["a", "b", "median_adf_p", "median_half_life", "last_beta", "last_alpha"]].to_csv(FROZEN, index=False)
    OUT.write_text(json.dumps({"windows": len(ends), "rows": len(allf), "pairs": m,
                               "fdr_pass": int(agg["fdr_pass"].sum()), "frozen": int(len(keep))}, indent=1))
    print(f"{m} pairs tested, {int(agg['fdr_pass'].sum())} FDR-pass, {len(keep)} frozen")
    print(agg[["a", "b", "median_adf_p", "median_half_life", "share_sig"]].head(10).to_string(index=False))


def regime(mkt: pd.Series, design_threshold: float) -> pd.Series:
    return (mkt.pct_change(20).abs() <= design_threshold)


def backtest_pair(px: pd.DataFrame, mkt: pd.Series, a: str, b: str, beta: float, alpha: float,
                  start: str, end: str, gate: pd.Series) -> pd.Series:
    sub = px[[a, b]].loc[start:end].replace([np.inf, -np.inf], np.nan).dropna()
    sub = sub[(sub > 0).all(axis=1)]
    if len(sub) < 90:
        return pd.Series(dtype=float)
    # market residuals with a rolling 180-day beta, re-estimated monthly
    lm = np.log(mkt.reindex(sub.index).to_numpy())
    ea = np.full(len(sub), np.nan)
    eb = np.full(len(sub), np.nan)
    for i in range(179, len(sub), 20):
        w0 = max(0, i - 179)
        for j, (col, target) in enumerate(((a, ea), (b, eb))):
            y = np.log(sub[col].to_numpy())
            ok = np.isfinite(y) & np.isfinite(lm)
            if ok.sum() < 60:
                continue
            X = np.column_stack([np.ones(ok.sum()), lm[ok]])
            beta_m = np.linalg.lstsq(X, y[ok], rcond=None)[0]
            seg = np.arange(w0, min(len(sub), i + 20))
            okseg = np.isfinite(np.log(sub[col].to_numpy()[seg])) & np.isfinite(lm[seg])
            target[seg[okseg]] = np.log(sub[col].to_numpy()[seg][okseg]) - (
                beta_m[0] + beta_m[1] * lm[seg][okseg])
    spread = pd.Series(ea - (alpha + beta * eb), index=sub.index)
    z = (spread - spread.rolling(60).mean()) / spread.rolling(60).std()
    r_a = np.log(sub[a]).diff()
    r_b = np.log(sub[b]).diff()
    leg, held, pnl = 0, 0, []
    for i in range(1, len(z)):
        t = z.index[i]
        g = bool(gate.reindex([t]).fillna(False).iloc[0])
        if leg == 0:
            if g and z.iloc[i] > 2:
                leg, held = -1, 0
            elif g and z.iloc[i] < -2:
                leg, held = 1, 0
            else:
                pnl.append(0.0)
                continue
            pnl.append(-2 * FEE)
        if leg != 0:
            daily = leg * (r_a.iloc[i] - beta * r_b.iloc[i])
            held += 1
            exit_now = abs(z.iloc[i]) < 0.5 or held >= 30
            pnl.append(float(daily) - (2 * FEE if exit_now else 0.0))
            if exit_now:
                leg = 0
        else:
            pnl.append(0.0)
    return pd.Series(pnl, index=z.index[1:])


def validate() -> None:
    if not FROZEN.exists() or FROZEN.stat().st_size < 10:
        print("no frozen pairs")
        return
    frozen = pd.read_csv(FROZEN)
    df = load()
    px = df.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    px = px.replace([np.inf, -np.inf], np.nan).where(lambda x: x > 0)
    design = px.loc[DESIGN[0]:DESIGN[1]]
    vol = df[(df["date"] >= DESIGN[0]) & (df["date"] <= DESIGN[1])].groupby("symbol")["qvol"].median()
    names = [s for s in vol.sort_values(ascending=False).head(N_UNIVERSE).index if s in px.columns]
    mkt = np.exp(np.log(px[names]).mean(axis=1)).rename("M")
    thr = float(mkt.loc[DESIGN[0]:DESIGN[1]].pct_change(20).abs().median())
    gate = regime(mkt, thr)
    series = []
    for _, r in frozen.iterrows():
        s = backtest_pair(px, mkt, r["a"], r["b"], float(r["last_beta"]), float(r["last_alpha"]),
                          VALID[0], VALID[1], gate)
        if len(s):
            series.append(s.rename(f"{r['a']}|{r['b']}"))
    if not series:
        print("no trades"); return
    book = pd.concat(series, axis=1).mean(axis=1).dropna()
    mean = float(book.mean())
    t = mean / (book.std(ddof=1) / np.sqrt(len(book)))
    half = len(book) // 2
    out = {"pairs": len(series), "days": int(len(book)), "mean_daily_bps": 1e4 * mean,
           "annualised_pct": 100 * 365 * mean, "t": float(t),
           "first_half_pct": 100 * 365 * float(book.iloc[:half].mean()),
           "second_half_pct": 100 * 365 * float(book.iloc[half:].mean())}
    (ROOT / "research" / "residual_pairs_validate.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main(argv: list[str]) -> int:
    what = argv[0] if argv else "scan"
    if what == "scan":
        scan()
    elif what == "validate":
        validate()
    else:
        print("usage: scan|validate", file=__import__("sys").stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
