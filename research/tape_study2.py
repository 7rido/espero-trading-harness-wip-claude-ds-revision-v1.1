"""Tape study 2: seconds OFI, markout by print size, session structure (pre-registered)."""
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

OUT = ROOT / "research" / "tape_study2.json"
DAYS = sorted(p.stem.replace("-", "") for p in [])
CACHE = sorted((ROOT / "data_tape").glob("BTCUSDT-2026-*.zip"))
H5 = (30, 60, 180)
MARKS = (10, 60)
BINS = [(0, 10_000), (10_000, 100_000), (100_000, 1_000_000), (1_000_000, float("inf"))]


def tstat(vals: list[float]) -> tuple[float, float]:
    a = np.array([v for v in vals if np.isfinite(v)])
    if len(a) < 3:
        return float("nan"), float("nan")
    se = a.std(ddof=1) / math.sqrt(len(a))
    t = float(a.mean() / se) if se else float("nan")
    return t, math.erfc(abs(t) / math.sqrt(2))


def day_h5(df: pd.DataFrame, step: int) -> float:
    sec = df["ts"].astype("datetime64[ns]").astype("int64") // 1_000_000_000
    key = sec // step
    buy = df.loc[~df["buyer_maker"]].groupby(key[~df["buyer_maker"]])["quantity"].sum()
    sell = df.loc[df["buyer_maker"]].groupby(key[df["buyer_maker"]])["quantity"].sum()
    close = df.groupby(key)["price"].last()
    g = pd.DataFrame({"buy": buy, "sell": sell, "close": close}).dropna()
    g["ofi"] = (g["buy"] - g["sell"]) / (g["buy"] + g["sell"]).replace(0, np.nan)
    g = g.dropna(subset=["ofi"])
    g["fwd"] = g["close"].shift(-1) / g["close"] - 1
    g = g.dropna(subset=["fwd"])
    if len(g) < 100:
        return float("nan")
    try:
        q = pd.qcut(g["ofi"], 5, labels=False, duplicates="drop")
    except ValueError:
        return float("nan")
    if q.nunique() < 5:
        return float("nan")
    return float(g["fwd"][q == q.max()].mean() - g["fwd"][q == q.min()].mean())


def day_marks(df: pd.DataFrame) -> dict:
    ts = df["ts"].values.astype("datetime64[ns]").astype("int64")
    price = df["price"].to_numpy()
    notional = (df["price"] * df["quantity"]).to_numpy()
    sign = np.where(df["buyer_maker"].to_numpy(), -1.0, 1.0)   # taker buy = +1
    out = {}
    for mark in MARKS:
        target = ts + mark * 1_000_000_000
        idx = np.searchsorted(ts, target)
        valid = idx < len(ts)
        future = np.full(len(ts), np.nan)
        future[valid] = price[idx[valid]]
        ret = sign * (future / price - 1) * 1e4
        ret_dm = ret - np.nanmean(ret)          # drift-adjusted (post-hoc)
        for lo, hi in BINS:
            mask = (notional >= lo) & (notional < hi)
            out[(mark, lo, hi, "raw")] = float(np.nanmean(ret[mask])) if mask.sum() >= 50 else float("nan")
            out[(mark, lo, hi, "dm")] = float(np.nanmean(ret_dm[mask])) if mask.sum() >= 50 else float("nan")
    return out


def main() -> int:
    h5_per_day: dict[int, list[float]] = {s: [] for s in H5}
    marks_per_day: dict[tuple, list[float]] = {}
    session_rows = []
    used = 0
    for zip_path in CACHE:
        day = zip_path.name.replace("BTCUSDT-", "").replace(".zip", "")
        try:
            df = tape.fetch_binance(day, "BTCUSDT")
        except Exception as exc:                    # noqa: BLE001
            print(f"  {day}: skip {exc}")
            continue
        used += 1
        for step in H5:
            h5_per_day[step].append(day_h5(df, step))
        for key, val in day_marks(df).items():
            marks_per_day.setdefault(key, []).append(val)
        hour = df["ts"].dt.hour
        hstats = df.groupby(hour).apply(
            lambda g: pd.Series({"prints": len(g),
                                 "qty": g["quantity"].sum(),
                                 "absret": (g["price"].pct_change().abs()).mean() * 1e4}),
            include_groups=False)
        session_rows.append(hstats)
        print(f"  {day}: {len(df):,} prints")

    cells = []
    for step in H5:
        t, p = tstat(h5_per_day[step])
        cells.append({"family": "H5", "test": f"ofi_{step}s", "days": len(h5_per_day[step]),
                      "spread_bps": 1e4 * float(np.nanmean(h5_per_day[step]))
                      if h5_per_day[step] else float("nan"), "t": t, "p": p, "bh_pass": False})
    for (mark, lo, hi, kind), vals in marks_per_day.items():
        t, p = tstat(vals)
        fam = "H6" if kind == "raw" else "H6-posthoc"
        cells.append({"family": fam,
                      "test": f"markout_{mark}s_{int(lo)}-{hi if hi != float('inf') else 'inf'}_{kind}",
                      "days": len(vals), "spread_bps": float(np.nanmean(vals)) if vals else float("nan"),
                      "t": t, "p": p, "bh_pass": False})
    for family in ("H5", "H6"):
        fam = [c for c in cells if c["family"] == family and np.isfinite(c["p"])]
        order = sorted(range(len(fam)), key=lambda i: fam[i]["p"])
        k_max = 0
        for k, i in enumerate(order, start=1):
            if fam[i]["p"] <= 0.10 * k / len(fam):
                k_max = k
        for i in order[:k_max]:
            fam[i]["bh_pass"] = True

    session = pd.concat(session_rows).groupby(level=0).mean().round(2) if session_rows else pd.DataFrame()
    out = {"days": used, "cells": cells, "session": session.reset_index().to_dict("records")}
    OUT.write_text(json.dumps(out, indent=1))
    print(f"\n{used} days\n")
    print(f"{'test':32s} {'days':>5} {'bp':>9} {'t':>7} {'p':>8} BH")
    for c in cells:
        print(f"{c['test']:32s} {c['days']:>5} {c['spread_bps']:>+9.2f} {c['t']:>7.2f} "
              f"{c['p']:>8.4f} {'yes' if c['bh_pass'] else ''}")
    print("\nsession (hour · prints · qty · absret bp):")
    print(session.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
