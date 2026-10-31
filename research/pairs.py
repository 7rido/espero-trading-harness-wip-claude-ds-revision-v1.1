"""Phase 1b: co-integration pairs scanner and validation backtest.

    python research/pairs.py scan        # design 2020-2022: find and freeze pairs
    python research/pairs.py validate    # 2023 evidence for the frozen pairs
The holdout window (2025-07..2026-03) is never touched here.
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
FROZEN = ROOT / "research" / "pairs_frozen.csv"
OUT = ROOT / "research" / "pairs_scan.json"
DESIGN = ("2020-01-01", "2022-12-31")
VALID = ("2023-01-01", "2023-12-31")
WINDOW = 180
FEE = 5e-4


def loads() -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    df = con.execute("""SELECT symbol, date, close, qvol FROM bars_daily ORDER BY date""").df()
    con.close()
    df["date"] = pd.to_datetime(df["date"])
    return df


def panel(df: pd.DataFrame) -> pd.DataFrame:
    return df.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()


def universe(df: pd.DataFrame, n: int = 30) -> list[str]:
    d = df[(df["date"] >= DESIGN[0]) & (df["date"] <= DESIGN[1])]
    vol = d.groupby("symbol")["qvol"].median().sort_values(ascending=False)
    return vol.head(n).index.tolist()


def half_life(spread: np.ndarray) -> float:
    s = spread[np.isfinite(spread)]
    if len(s) < 30:
        return float("nan")
    x, y = s[:-1], np.diff(s)
    beta = float(np.polyfit(x - x.mean(), y, 1)[0])
    rho = 1 + beta
    if 0 < rho < 1:
        return float(-np.log(2) / np.log(rho))
    return float("nan")


def eg_test(lp: pd.DataFrame, a: str, b: str, end: pd.Timestamp) -> dict | None:
    w = lp.loc[:end].iloc[-WINDOW:]
    if a not in w or b not in w:
        return None
    sub = w[[a, b]].replace([np.inf, -np.inf], np.nan).dropna()
    sub = sub[(sub > 0).all(axis=1)]
    if len(sub) < 120:
        return None
    y, x = np.log(sub[a].to_numpy()), np.log(sub[b].to_numpy())
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    spread = y - X @ beta
    try:
        with np.errstate(all="ignore"):
            p = float(adfuller(spread, maxlag=1, regression="c", autolag="AIC",
                                result_object=False)[1])
    except Exception:
        return None
    return {"alpha": float(beta[0]), "beta": float(beta[1]), "adf_p": p,
            "half_life": half_life(spread)}


def scan() -> None:
    df = loads()
    lp = panel(df).apply(np.log)
    names = universe(df)
    ends = pd.date_range("2022-01-31", "2022-12-31", freq="ME")
    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            tests = [eg_test(lp, a, b, e) for e in ends]
            tests = [t for t in tests if t]
            if len(tests) < 6:
                continue
            med_p = float(np.median([t["adf_p"] for t in tests]))
            med_hl = float(np.nanmedian([t["half_life"] for t in tests]))
            rows.append({"a": a, "b": b, "median_adf_p": med_p, "median_half_life": med_hl,
                         "last_beta": tests[-1]["beta"], "last_alpha": tests[-1]["alpha"],
                         "share_significant": float(np.mean([t["adf_p"] < 0.05 for t in tests]))})
    res = pd.DataFrame(rows).sort_values("median_adf_p")
    res.to_csv(ROOT / "research" / "pairs_all.csv", index=False)
    # Benjamini-Hochberg at 10% over every pair tested
    m = len(res)
    res["bh_rank"] = np.arange(1, m + 1)
    res["bh_threshold"] = 0.10 * res["bh_rank"] / m
    res["fdr_pass"] = res["median_adf_p"] <= res["bh_threshold"]
    keep = res[res["fdr_pass"] & res["median_half_life"].between(5, 30) &
               (res["share_significant"] >= 0.5)]
    keep.to_csv(FROZEN.with_suffix(".csv.tmp"), index=False)
    keep[["a", "b", "median_adf_p", "median_half_life", "last_beta", "last_alpha"]].to_csv(FROZEN, index=False)
    FROZEN.with_suffix(".csv.tmp").unlink(missing_ok=True)
    OUT.write_text(json.dumps({"tested": m, "fdr_pass": int(res["fdr_pass"].sum()),
                               "frozen": int(len(keep)), "design": DESIGN}, indent=1))
    print(f"tested {m} pairs, {int(res['fdr_pass'].sum())} FDR-pass, {len(keep)} frozen")
    print("top by median ADF p:")
    print(res[["a", "b", "median_adf_p", "median_half_life", "share_significant"]].head(8).to_string(index=False))


def zscore(spread: pd.Series, lookback: int = 60) -> pd.Series:
    return (spread - spread.rolling(lookback).mean()) / spread.rolling(lookback).std()


def backtest_pair(lp: pd.DataFrame, a: str, b: str, beta: float, alpha: float,
                  start: str, end: str) -> pd.Series:
    sub = lp[[a, b]].loc[start:end].replace([np.inf, -np.inf], np.nan).dropna()
    sub = sub[(sub > 0).all(axis=1)]
    if len(sub) < 90:
        return pd.Series(dtype=float)
    spread = np.log(sub[a]) - (alpha + beta * np.log(sub[b]))
    z = zscore(spread)
    pos = pd.Series(0.0, index=z.index)
    ret_a = np.log(sub[a]).diff()
    ret_b = np.log(sub[b]).diff()
    held, leg = 0, 0
    pnl = []
    for i in range(1, len(z)):
        t = z.index[i]
        if leg == 0:
            if z.iloc[i] > 2:
                leg, held = -1, 0            # short a, long b
            elif z.iloc[i] < -2:
                leg, held = 1, 0
            else:
                pnl.append(0.0)
                continue
            pnl.append(-abs(FEE))            # entry cost on both legs
        if leg != 0:
            daily = leg * (ret_a.iloc[i] - beta * ret_b.iloc[i])
            held += 1
            exit_now = abs(z.iloc[i]) < 0.5 or held >= 30
            pnl.append(float(daily) - (2 * FEE if exit_now else 0.0))
            if exit_now:
                leg = 0
        else:
            pnl.append(0.0)
    return pd.Series(pnl, index=z.index[1:])


def validate() -> None:
    if not FROZEN.exists():
        print("no frozen pairs: run scan first")
        return
    frozen = pd.read_csv(FROZEN)
    df = loads()
    lp = panel(df).apply(np.log)
    series = []
    for _, r in frozen.iterrows():
        s = backtest_pair(lp, r["a"], r["b"], float(r["last_beta"]), float(r["last_alpha"]),
                          VALID[0], VALID[1])
        if len(s):
            series.append(s.rename(f"{r['a']}|{r['b']}"))
    if not series:
        print("no trades in validation")
        return
    book = pd.concat(series, axis=1).mean(axis=1).dropna()
    mean = float(book.mean())
    t = mean / (book.std(ddof=1) / np.sqrt(len(book))) if len(book) > 2 else float("nan")
    out = {"pairs": len(series), "days": int(len(book)), "mean_daily_bps": 1e4 * mean,
           "annualised_pct": 100 * 52 * mean if False else 100 * 365 * mean, "t": t}
    (ROOT / "research" / "pairs_validate.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main(argv: list[str]) -> int:
    what = argv[0] if argv else "scan"
    if what == "scan":
        scan()
    elif what == "validate":
        validate()
    else:
        print("usage: scan|validate", file=__import__("sys").stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
