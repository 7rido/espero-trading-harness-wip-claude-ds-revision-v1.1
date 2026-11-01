"""Pre-registered tape study: OFI, absorption, sweeps, blocks and intensity vs 5/15/60-minute outcomes.

    python research/tape_study.py

Reads research/PREREGISTRATION_tape.md. One run, all cells reported, BH at 10% over the 12 return cells.
"""
from __future__ import annotations

import importlib.util
import json
import math
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tape_mod", ROOT / "research" / "tape.py")
tape = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tape)

DAYS = pd.date_range("2026-10-01", "2026-10-30", freq="D").strftime("%Y-%m-%d").tolist()
HORIZONS = (5, 15, 60)
BLOCK_USD = 100_000.0
OUT = ROOT / "research" / "tape_study.json"
COST_BPS = 9.0


def load_day(day: str) -> pd.DataFrame:
    df = tape.fetch_binance(day, "BTCUSDT")
    df["minute"] = df["ts"].dt.floor("min")
    df["notional"] = df["price"] * df["quantity"]
    m = tape.minute_table(df)[["minute", "open", "high", "low", "close", "prints", "qty",
                               "buy_qty", "sell_qty", "cvd", "ret_bp", "vol_z"]].copy()
    m["ofi"] = (m["buy_qty"] - m["sell_qty"]) / (m["buy_qty"] + m["sell_qty"]).replace(0, np.nan)
    blocks = df[df["notional"] >= BLOCK_USD].groupby("minute").size()
    m["block_flag"] = m["minute"].map(blocks).fillna(0).gt(0)
    grouped = df.groupby(["minute", "ts", "price"]).size()
    sweeps = grouped[grouped >= 3].groupby(level=0).size()
    m["sweep_flag"] = m["minute"].map(sweeps).fillna(0).gt(0)
    # trailing absorption threshold: no look-ahead
    m["abs_thr"] = m["ret_bp"].abs().rolling(60, min_periods=10).median().shift(1)
    m["absorption"] = (m["vol_z"] >= 2) & (m["ret_bp"].abs() < m["abs_thr"])
    m = m[m["qty"] > 0].reset_index(drop=True)
    for h in HORIZONS:
        m[f"fwd{h}"] = m["close"].shift(-h) / m["close"] - 1
    logret = np.log(m["close"]).diff()
    m["fwd_rv60"] = logret.rolling(60).std().shift(-60)   # std of the NEXT 60 one-minute returns
    return m.dropna(subset=[f"fwd{h}" for h in HORIZONS]).reset_index(drop=True)


def daily_spread(m: pd.DataFrame, feature: str, horizon: int, quantile: bool = True) -> list[float]:
    out = []
    for _, day in m.groupby(m["minute"].dt.date):
        f = day[feature]
        if quantile:
            try:
                q = pd.qcut(f, 5, labels=False, duplicates="drop")
            except ValueError:
                continue
            if q.nunique() < 5:
                continue
            hi, lo = day[f"fwd{horizon}"][q == q.max()], day[f"fwd{horizon}"][q == q.min()]
            if len(hi) < 10 or len(lo) < 10:
                continue
            out.append(float(hi.mean() - lo.mean()))
        else:
            hi = day.loc[day[feature], f"fwd{horizon}"]
            lo = day.loc[~day[feature], f"fwd{horizon}"]
            if len(hi) < 5 or len(lo) < 50:
                continue
            out.append(float(hi.mean() - lo.mean()))
    return out


def tstat(values: list[float]) -> tuple[float, float]:
    a = np.array([v for v in values if np.isfinite(v)])
    if len(a) < 3:
        return float("nan"), float("nan")
    se = a.std(ddof=1) / math.sqrt(len(a))
    t = float(a.mean() / se) if se else float("nan")
    p = math.erfc(abs(t) / math.sqrt(2))
    return t, p


def main() -> int:
    frames = []
    for day in DAYS:
        try:
            frames.append(load_day(day))
            print(f"  {day}: {len(frames[-1])} minutes")
        except Exception as exc:                    # noqa: BLE001
            print(f"  {day}: skipped ({type(exc).__name__}: {exc})")
    m = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if m.empty:
        print("no data"); return 3
    cells = []
    for feature, kind in (("ofi", True), ("absorption", False), ("sweep_flag", False), ("block_flag", False)):
        for h in HORIZONS:
            vals = daily_spread(m, feature, h, quantile=kind)
            t, p = tstat(vals)
            cells.append({"feature": feature, "h": h, "days": len(vals),
                          "spread_bps": 1e4 * float(np.nanmean(vals)) if vals else float("nan"),
                          "t": t, "p": p, "bh_pass": False})
    valid = [c for c in cells if np.isfinite(c["p"])]
    order = sorted(range(len(valid)), key=lambda i: valid[i]["p"])
    k_max = 0
    for k, i in enumerate(order, start=1):
        if valid[i]["p"] <= 0.10 * k / len(valid):
            k_max = k
    for i in order[:k_max]:
        valid[i]["bh_pass"] = True

    # H4: intensity -> next-hour realised variance
    rv = []
    for _, day in m.groupby(m["minute"].dt.date):
        d = day.dropna(subset=["fwd_rv60", "prints"])
        if len(d) < 200:
            continue
        try:
            q = pd.qcut(d["prints"], 5, labels=False, duplicates="drop")
        except ValueError:
            continue
        if q.nunique() < 5:
            continue
        rv.append(float(d.loc[q == q.max(), "fwd_rv60"].mean() / d.loc[q == q.min(), "fwd_rv60"].mean()))
    rv_ratio = float(np.nanmean(rv)) if rv else float("nan")
    out = {"prereg": "research/PREREGISTRATION_tape.md", "days": len(frames),
           "minutes": len(m), "cost_bps": COST_BPS, "cells": cells,
           "h4_rv_top_over_bottom": rv_ratio, "h4_days": len(rv)}
    OUT.write_text(json.dumps(out, indent=1))
    print(f"\n{len(m):,} minutes over {len(frames)} days\n")
    print(f"{'feature':14s} {'h':>3} {'days':>5} {'spread bp':>10} {'t':>7} {'p':>8} BH")
    for c in cells:
        print(f"{c['feature']:14s} {c['h']:>3} {c['days']:>5} {c['spread_bps']:>+10.1f} "
              f"{c['t']:>7.2f} {c['p']:>8.4f} {'yes' if c['bh_pass'] else ''}")
    print(f"\nH4 intensity -> next-60m RV, top/bottom quintile ratio: {rv_ratio:.3f} "
          f"({len(rv)} days)")
    print(f"tradeable cells: "
          f"{sum(1 for c in cells if c['bh_pass'] and abs(c['spread_bps']) > COST_BPS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
