"""Pre-registered tape-edge study: sweep exhaustion, absorption, block continuation, divergence.

    python research/tape_edges.py --design
    python research/tape_edges.py --holdout     # only after the design result is sealed

Design: the cached 2026-10-01..2026-10-30 days. Holdout: 2026-08-01..2026-09-30, fetched at holdout
time and read once. No network in the design run beyond cached files.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tape_mod", ROOT / "research" / "tape.py")
tape = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tape)

DESIGN_DAYS = [f"2026-10-{d:02d}" for d in range(1, 31)]
HOLDOUT_DAYS = [str(d.date()) for d in pd.date_range("2026-08-01", "2026-09-30", freq="D")]
DESIGN_OUT = ROOT / "research" / "tape_edges_design.json"
HOLDOUT_OUT = ROOT / "research" / "tape_edges_holdout.json"
SEAL = ROOT / "research" / ".tape_edges_seal.json"
COST_BPS = 9.0
CELLS = [("sweep", 15), ("sweep", 60), ("absorp", 30), ("absorp", 60),
         ("block", 5), ("block", 15), ("div", 60)]


def tstat(vals):
    a = np.array([v for v in vals if np.isfinite(v)])
    if len(a) < 3:
        return float("nan"), float("nan")
    se = a.std(ddof=1) / math.sqrt(len(a))
    t = float(a.mean() / se) if se else float("nan")
    return t, math.erfc(abs(t) / math.sqrt(2))


def frames(day: str):
    df = tape.fetch_binance(day, "BTCUSDT")
    df["minute"] = df["ts"].dt.floor("min")
    df["notional"] = df["price"] * df["quantity"]
    m = tape.minute_table(df).set_index("minute")
    m = m[m["qty"] > 0]
    g = df.groupby(["minute", "ts", "price"]).size()
    sweeps = g[g >= 3].groupby(level=0).size()
    m["sweeps"] = m.index.map(sweeps).fillna(0).astype(int)
    blk = df[df["notional"] >= 1_000_000].groupby("minute").agg(
        side=("buyer_maker", "first"), usd=("notional", "sum")).sort_index()
    return df, m, blk


def forward(m: pd.DataFrame, i: int, h: int) -> float:
    if i + 1 + h >= len(m):
        return float("nan")
    base = float(m["close"].iloc[i + 1])
    return float(m["close"].iloc[i + 1 + h]) / base - 1


def day_events(day: str) -> list[dict]:
    df, m, blk = frames(day)
    ret = m["ret_bp"]
    sigma = float(ret.std())
    med_abs = float(ret.abs().median())
    events: list[dict] = []
    if sigma > 0:
        for i in range(60, len(m) - 61):
            r = float(ret.iloc[i])
            if m["sweeps"].iloc[i] >= 2 and abs(r) >= 2 * sigma:
                buy_share = float(m["buy_qty"].iloc[i] / max(m["buy_qty"].iloc[i] + m["sell_qty"].iloc[i], 1e-12))
                confirms = (r > 0 and buy_share > 0.5) or (r < 0 and buy_share < 0.5)
                if confirms:
                    d = -1 if r > 0 else 1
                    events.append({"feature": "sweep", "i": i, "dir": d,
                                   "r15": 1e4 * d * forward(m, i, 15), "r60": 1e4 * d * forward(m, i, 60)})
            if m["vol_z"].iloc[i] >= 3 and abs(r) <= 0.5 * med_abs and i >= 15:
                prior = float(m["close"].iloc[i] / m["close"].iloc[i - 15] - 1)
                d = -1 if prior > 0 else 1
                events.append({"feature": "absorp", "i": i, "dir": d,
                               "r30": 1e4 * d * forward(m, i, 30), "r60": 1e4 * d * forward(m, i, 60)})
            # divergence at a 60-minute extreme
            lo60 = float(m["low"].iloc[i - 60:i].min())
            hi60 = float(m["high"].iloc[i - 60:i].max())
            if float(m["low"].iloc[i]) <= lo60 or float(m["high"].iloc[i]) >= hi60:
                tail = m.iloc[i - 60:i + 1].reset_index()
                div = tape.divergence(tail.rename(columns={"minute": "t"}), window=61)
                if div == "bullish":
                    events.append({"feature": "div", "i": i, "dir": 1, "r60": 1e4 * forward(m, i, 60)})
                elif div == "bearish":
                    events.append({"feature": "div", "i": i, "dir": -1, "r60": -1e4 * forward(m, i, 60)})
    last = None
    for minute, row in blk.iterrows():
        if last is not None and (minute - last) < pd.Timedelta(minutes=10):
            last = minute
            continue
        last = minute
        if minute in m.index:
            i = m.index.get_loc(minute)
            d = 1 if not bool(row["side"]) else -1
            events.append({"feature": "block", "i": i, "dir": d,
                           "r5": 1e4 * d * forward(m, i, 5), "r15": 1e4 * d * forward(m, i, 15)})
    return events


def run(days: list[str], label: str) -> dict:
    per_day: dict[tuple, list[float]] = {c: [] for c in CELLS}
    counts = {c: 0 for c in CELLS}
    used = 0
    for day in days:
        try:
            ev = day_events(day)
        except Exception as exc:                    # noqa: BLE001
            print(f"  {day}: skipped ({type(exc).__name__}: {exc})")
            continue
        used += 1
        for c in CELLS:
            vals = [e.get(f"r{c[1]}") for e in ev if e["feature"] == c[0]
                    and e.get(f"r{c[1]}") is not None and np.isfinite(e.get(f"r{c[1]}", np.nan))]
            if vals:
                per_day[c].append(float(np.mean(vals)))
                counts[c] += len(vals)
        print(f"  {day}: {len(ev)} events")
    cells = []
    for c in CELLS:
        t, p = tstat(per_day[c])
        mean = float(np.nanmean(per_day[c])) if per_day[c] else float("nan")
        cells.append({"feature": c[0], "h": c[1], "days": len(per_day[c]), "events": counts[c],
                      "mean_bps": mean, "t": t, "p": p, "bh_pass": False,
                      "net_bps": mean - COST_BPS if np.isfinite(mean) else float("nan")})
    valid = [c for c in cells if np.isfinite(c["p"]) and c["days"] >= 10]
    order = sorted(range(len(valid)), key=lambda i: valid[i]["p"])
    k_max = 0
    for k, i in enumerate(order, start=1):
        if valid[i]["p"] <= 0.10 * k / len(valid):
            k_max = k
    for i in order[:k_max]:
        valid[i]["bh_pass"] = True
    out = {"label": label, "days": used, "cost_bps": COST_BPS, "cells": cells}
    path = DESIGN_OUT if label == "design" else HOLDOUT_OUT
    path.write_text(json.dumps(out, indent=1))
    print(f"\n{used} days · {label}")
    print(f"{'feature':8s} {'h':>3} {'days':>5} {'events':>7} {'mean':>8} {'t':>7} {'p':>8} {'net':>8} BH")
    for c in cells:
        print(f"{c['feature']:8s} {c['h']:>3} {c['days']:>5} {c['events']:>7} {c['mean_bps']:>+8.1f} "
              f"{c['t']:>7.2f} {c['p']:>8.4f} {c['net_bps']:>+8.1f} {'yes' if c['bh_pass'] else ''}")
    return out


def seal_design() -> None:
    digest = hashlib.sha256(DESIGN_OUT.read_bytes()).hexdigest()
    SEAL.write_text(json.dumps({"design_sha256": digest}, indent=1))
    print(f"sealed design sha256 {digest}")


def holdout_allowed() -> bool:
    if not DESIGN_OUT.exists() or not SEAL.exists():
        return False
    want = json.loads(SEAL.read_text()).get("design_sha256")
    got = hashlib.sha256(DESIGN_OUT.read_bytes()).hexdigest()
    return bool(want) and want == got


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", action="store_true")
    ap.add_argument("--holdout", action="store_true")
    args = ap.parse_args(argv)
    if args.holdout:
        if not holdout_allowed():
            print("holdout refused: design result missing or not sealed (run --design, then seal)",
                  file=sys.stderr)
            return 4
        out = run(HOLDOUT_DAYS, "holdout")
        return 0 if out else 3
    out = run(DESIGN_DAYS, "design")
    if not out["cells"]:
        return 3
    if any(c["bh_pass"] and abs(c["mean_bps"]) > COST_BPS for c in out["cells"]):
        seal_design()
    else:
        print("\nno design cell passed BH and the cost bar: holdout will not be run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
