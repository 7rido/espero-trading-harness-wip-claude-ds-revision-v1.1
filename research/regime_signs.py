"""Regime signs: trend x volatility x funding, and what follows each state.

    python research/regime_signs.py

States are built only from information available at the close (no look-ahead). Outcomes are
market-relative (coin minus that day's cross-section) at 5 and 20 days. Every cell reports n, the
full distribution and whether it survives BH FDR across all cells.
"""
from __future__ import annotations

import json
import pathlib

import duckdb
import math

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
OUT = ROOT / "research" / "regime_signs.json"


def load() -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    bars = con.execute("SELECT symbol, date, close FROM bars_daily ORDER BY date").df()
    rv = con.execute("SELECT symbol, date, rv FROM rv").df()
    fund = con.execute("SELECT symbol, CAST(ts AS DATE) AS date, rate FROM funding").df()
    con.close()
    for d in (bars, rv, fund):
        d["date"] = pd.to_datetime(d["date"])
    f = fund.groupby(["symbol", "date"])["rate"].mean().rename("funding").reset_index()
    df = bars.merge(rv, on=["symbol", "date"], how="left").merge(f, on=["symbol", "date"], how="left")
    return df.sort_values(["symbol", "date"])


def build(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("symbol")
    df["ret60"] = g["close"].transform(lambda s: s / s.shift(60) - 1)
    df["above200"] = g["close"].transform(lambda s: s > s.rolling(200).mean())
    df["vol_pct"] = df.groupby("symbol")["rv"].transform(
        lambda s: s.rolling(252, min_periods=60).rank(pct=True))
    df["fund7"] = g["funding"].transform(lambda s: s.rolling(7, min_periods=3).mean())
    df["fund_pct"] = df.groupby("symbol")["fund7"].transform(
        lambda s: s.rolling(252, min_periods=60).rank(pct=True))
    for h in (5, 20):
        df[f"f{h}"] = g["close"].shift(-h) / df["close"] - 1
        df[f"x{h}"] = df[f"f{h}"] - df.groupby("date")[f"f{h}"].transform("mean")
    return df


def cells(df: pd.DataFrame) -> list[dict]:
    d = df.dropna(subset=["ret60", "vol_pct", "fund_pct"]).copy()
    d["trend"] = np.where(d["ret60"] > 0, "up", "down")
    d["vol"] = np.where(d["vol_pct"] > 0.5, "high", "low")
    d["fund"] = np.where(d["fund_pct"] > 0.5, "high", "low")
    rows = []
    for (trend, vol, fund), grp in d.groupby(["trend", "vol", "fund"]):
        for h in (5, 20):
            v = grp[f"x{h}"].dropna()
            if len(v) < 200:
                continue
            rows.append({"state": f"{trend}/{vol}/{fund}", "h": h, "n": int(len(v)),
                         "mean_bps": 1e4 * float(v.mean()), "median_bps": 1e4 * float(v.median()),
                         "p10": 1e4 * float(v.quantile(0.1)), "p90": 1e4 * float(v.quantile(0.9)),
                         "share_up": float((v > 0).mean()), "fdr_pass": False})
    # BH with effective n (overlapping windows)
    pvals = []
    for r in rows:
        sd = (r["p90"] - r["p10"]) / 2.563
        n_eff = max(r["n"] / r["h"], 30)
        z = abs(r["mean_bps"]) / (sd / np.sqrt(n_eff)) if sd > 0 else 0.0
        pvals.append(math.erfc(abs(z) / math.sqrt(2)))
    order = np.argsort(pvals)
    m = len(pvals)
    k_max = 0
    for k, i in enumerate(order, start=1):
        if pvals[i] <= 0.10 * k / m:
            k_max = k
    for i in order[:k_max]:
        rows[i]["fdr_pass"] = True
    return rows


def main() -> int:
    df = build(load())
    rows = cells(df)
    OUT.write_text(json.dumps(rows, indent=1))
    print(f"{len(rows)} cells · FDR-pass {sum(r['fdr_pass'] for r in rows)}")
    print(f"{'state':18s} {'h':>2} {'n':>6} {'mean':>8} {'median':>8} {'p10':>8} {'p90':>8} {'up':>5} FDR")
    for r in sorted(rows, key=lambda r: r["mean_bps"]):
        print(f"{r['state']:18s} {r['h']:>2} {r['n']:>6} {r['mean_bps']:>+8.1f} "
              f"{r['median_bps']:>+8.1f} {r['p10']:>+8.0f} {r['p90']:>+8.0f} "
              f"{r['share_up']:>4.0%} {'yes' if r['fdr_pass'] else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
