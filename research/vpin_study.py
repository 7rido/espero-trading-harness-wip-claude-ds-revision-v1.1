"""Pre-registered VPIN study: toxicity vs next-hour variance and next-30-minute absolute return."""
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

OUT = ROOT / "research" / "vpin_study.json"
CACHE = sorted((ROOT / "data_tape").glob("BTCUSDT-2026-*.zip"))
BUCKETS = 500
WINDOW = 50


def tstat(vals):
    a = np.array([v for v in vals if np.isfinite(v)])
    if len(a) < 3:
        return float("nan"), float("nan")
    se = a.std(ddof=1) / math.sqrt(len(a))
    t = float(a.mean() / se) if se else float("nan")
    return t, math.erfc(abs(t) / math.sqrt(2))


def day_spread(df: pd.DataFrame, outcome: pd.Series, minute_index: pd.DatetimeIndex) -> float:
    qty = df["quantity"].to_numpy()
    buy = (~df["buyer_maker"]).to_numpy()
    bucket_size = qty.sum() / BUCKETS
    if bucket_size <= 0:
        return float("nan")
    b = (np.cumsum(qty) // bucket_size).astype(np.int64)
    buy_vol = np.bincount(b, weights=qty * buy)
    vol = np.bincount(b, weights=qty)
    imb = np.abs(2 * buy_vol - vol) / np.where(vol == 0, 1, vol)
    ts_ns = df["ts"].astype("datetime64[ns]").astype("int64").to_numpy()
    end = np.zeros(len(vol), dtype=np.int64)
    np.maximum.at(end, b, ts_ns)
    keep = end > 0
    vpin = pd.Series(imb[keep], index=pd.to_datetime(end[keep], unit="ns")).rolling(WINDOW).mean()
    series = vpin.dropna()
    if len(series) < 20:
        return float("nan")
    right = pd.DataFrame({"ts": pd.to_datetime(series.index).astype("datetime64[ns]"),
                          "vpin": series.values}).sort_values("ts")
    left = pd.DataFrame({"minute": pd.to_datetime(minute_index).astype("datetime64[ns]")}).sort_values("minute")
    mapped = pd.merge_asof(left, right, left_on="minute", right_on="ts", direction="backward")
    mapped = mapped.set_index("minute")["vpin"]
    panel = pd.DataFrame({"vpin": mapped, "out": outcome}).dropna()
    if len(panel) < 100:
        return float("nan")
    try:
        q = pd.qcut(panel["vpin"], 5, labels=False, duplicates="drop")
    except ValueError:
        return float("nan")
    if q.nunique() < 5:
        return float("nan")
    return float(panel["out"][q == q.max()].mean() - panel["out"][q == q.min()].mean())


def main() -> int:
    rows = []
    used = 0
    for zp in CACHE:
        day = zp.name.replace("BTCUSDT-", "").replace(".zip", "")
        try:
            df = tape.fetch_binance(day, "BTCUSDT")
        except Exception as exc:                    # noqa: BLE001
            print(f"  {day}: skip {exc}")
            continue
        used += 1
        m = tape.minute_table(df).set_index("minute")
        m = m[m["qty"] > 0]
        logret = np.log(m["close"]).diff()
        rv60 = logret.rolling(60).std().shift(-60)
        abs30 = (m["close"].shift(-30) / m["close"] - 1).abs()
        rows.append({"day": day, "h1": day_spread(df, rv60, m.index), "h2": day_spread(df, abs30, m.index)})
        print(f"  {day}: h1 {rows[-1]['h1']:.3e}  h2 {rows[-1]['h2']:.4f}")
    cells = []
    for key, name in (("h1", "vpin_rv60"), ("h2", "vpin_abs30")):
        vals = [r[key] for r in rows]
        t, p = tstat(vals)
        cells.append({"test": name, "days": len(vals), "spread": float(np.nanmean(vals)),
                      "t": t, "p": p, "bh_pass": False})
    valid = [c for c in cells if np.isfinite(c["p"])]
    order = sorted(range(len(valid)), key=lambda i: valid[i]["p"])
    k_max = 0
    for k, i in enumerate(order, start=1):
        if valid[i]["p"] <= 0.10 * k / len(valid):
            k_max = k
    for i in order[:k_max]:
        valid[i]["bh_pass"] = True
    OUT.write_text(json.dumps({"days": used, "cells": cells}, indent=1))
    print(f"\n{used} days\n{'test':14s} {'days':>5} {'spread':>12} {'t':>7} {'p':>8} BH")
    for c in cells:
        print(f"{c['test']:14s} {c['days']:>5} {c['spread']:>12.3e} {c['t']:>7.2f} {c['p']:>8.4f} "
              f"{'yes' if c['bh_pass'] else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
