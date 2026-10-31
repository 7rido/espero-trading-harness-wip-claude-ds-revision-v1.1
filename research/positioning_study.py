"""Positioning measurements (open interest, taker flow, long/short ratios) vs forward returns.

    python research/positioning_study.py

Only SOL has 5-minute positioning data (2025-10-31 -> 2026-10-30), and daily prices overlap it until
2026-03-31, so the sample is ~150 days. Weak by construction; reported so it can be rated, not used.
"""
from __future__ import annotations

import pathlib

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    m = con.execute("""SELECT CAST(ts AS DATE) AS date, AVG(oi) AS oi, AVG(top_ls) AS top_ls,
                              AVG(global_ls) AS global_ls, AVG(taker_ratio) AS taker
                       FROM metrics WHERE symbol='SOLUSDT' GROUP BY 1 ORDER BY 1""").df()
    px = con.execute("SELECT date, close FROM bars_daily WHERE symbol='SOLUSDT' ORDER BY date").df()
    con.close()
    m["date"] = pd.to_datetime(m["date"]); px["date"] = pd.to_datetime(px["date"])
    d = m.merge(px, on="date", how="inner").dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if len(d) < 60:
        print(f"overlap only {len(d)} days"); return 0
    d["oi_chg"] = d["oi"].pct_change()
    d["oi_z"] = (d["oi_chg"] - d["oi_chg"].rolling(30).mean()) / d["oi_chg"].rolling(30).std()
    for c in ("taker", "top_ls"):
        d[f"{c}_z"] = (d[c] - d[c].rolling(30).mean()) / d[c].rolling(30).std()
    for h in (1, 5):
        d[f"f{h}"] = d["close"].shift(-h) / d["close"] - 1
    d = d.dropna(subset=["oi_z", "taker_z", "top_ls_z", "f1", "f5"])
    print(f"sample: {len(d)} days {d['date'].min().date()} -> {d['date'].max().date()}\n")
    rows = []
    for feat in ("oi_z", "taker_z", "top_ls_z"):
        hi = d[d[feat] >= d[feat].quantile(0.8)]
        lo = d[d[feat] <= d[feat].quantile(0.2)]
        for h in (1, 5):
            for label, sel in (("top", hi), ("bottom", lo)):
                v = sel[f"f{h}"]
                if len(v) < 10:
                    continue
                se = v.std() / np.sqrt(max(len(v) / h, 5))
                rows.append({"feature": feat, "side": label, "h": h, "n": len(v),
                             "mean_bps": 1e4 * v.mean(), "median_bps": 1e4 * v.median(),
                             "up": (v > 0).mean(), "t": (1e4 * v.mean()) / (1e4 * se) if se else 0})
    out = pd.DataFrame(rows)
    print(out.to_string(index=False, float_format=lambda x: f"{x:+.2f}"))
    print(f"\ncells: {len(out)} · |t|>=2: {(out['t'].abs() >= 2).sum()} "
          f"(expected by chance at 0.05: {0.05*len(out):.1f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
