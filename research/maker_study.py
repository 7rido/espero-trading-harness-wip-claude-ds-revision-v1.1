"""Maker-execution pilot: passive fills, spread captured and post-fill markout (one day)."""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOK = ROOT / "data_tardis" / "book_ticker" / "SOLUSDT-2026-10-01.csv.gz"
TRADES = ROOT / "data_tardis" / "trades" / "SOLUSDT-2026-10-01.csv.gz"
OUT = ROOT / "research" / "maker_study.json"


def main() -> int:
    book = pd.read_csv(BOOK, usecols=["timestamp", "ask_amount", "ask_price", "bid_price", "bid_amount"])
    book["minute"] = pd.to_datetime(book["timestamp"], unit="us").dt.floor("min")
    snap = book.sort_values("timestamp").groupby("minute").tail(1).set_index("minute").sort_index()
    mid = (snap["bid_price"] + snap["ask_price"]) / 2
    tr = pd.read_csv(TRADES)
    tr["minute"] = pd.to_datetime(tr["timestamp"], unit="us").dt.floor("min")
    sell = tr[tr["side"] == "sell"].groupby(["minute", "price"])["amount"].sum()
    buy = tr[tr["side"] == "buy"].groupby(["minute", "price"])["amount"].sum()
    minutes = list(snap.index[:-6])           # leave room for the 5-minute markout
    fills = []
    for m in minutes:
        row = snap.loc[m]
        bid, ask = float(row["bid_price"]), float(row["ask_price"])
        mmid = (bid + ask) / 2
        s = sell.get(m, pd.Series(dtype=float))
        b = buy.get(m, pd.Series(dtype=float))
        s = float(s[s.index <= bid].sum()) if len(s) else 0.0
        bb = float(b[b.index >= ask].sum()) if len(b) else 0.0
        for side, filled, price, qty in (("buy", s >= float(row["bid_amount"]), bid, float(row["bid_amount"])),
                                         ("sell", bb >= float(row["ask_amount"]), ask, float(row["ask_amount"]))):
            if not filled:
                continue
            i = minutes.index(m)
            def mid_at(k: int) -> float:
                nxt = minutes[min(i + k, len(minutes) - 1)]
                r = snap.loc[nxt]
                return (float(r["bid_price"]) + float(r["ask_price"])) / 2
            if side == "buy":
                capture = (mmid - price) / price
                m1 = (mid_at(1) - price) / price
                m5 = (mid_at(5) - price) / price
            else:
                capture = (price - mmid) / price
                m1 = (price - mid_at(1)) / price
                m5 = (price - mid_at(5)) / price
            fills.append({"side": side, "minute": str(m), "capture_bps": 1e4 * capture,
                          "mark1_bps": 1e4 * m1, "mark5_bps": 1e4 * m5,
                          "spread_bps": 1e4 * (ask - bid) / mmid})
    f = pd.DataFrame(fills)
    out = {"day": "2026-10-01", "symbol": "SOLUSDT", "minutes": len(minutes),
           "fill_rate": float(len(f) / (2 * len(minutes))) if minutes else 0.0,
           "fills": int(len(f))}
    if not f.empty:
        f["q"] = pd.qcut(f["spread_bps"], 4, labels=False, duplicates="drop")
        out["capture_median_bps"] = float(f["capture_bps"].median())
        out["mark1_mean_bps"] = float(f["mark1_bps"].mean())
        out["mark5_mean_bps"] = float(f["mark5_bps"].mean())
        out["net_1m_bps"] = out["capture_median_bps"] + out["mark1_mean_bps"]
        out["net_5m_bps"] = out["capture_median_bps"] + out["mark5_mean_bps"]
        out["by_spread_quartile"] = f.groupby("q").agg(
            fills=("capture_bps", "size"), capture=("capture_bps", "median"),
            mark1=("mark1_bps", "mean"), mark5=("mark5_bps", "mean")).round(2).reset_index().to_dict("records")
        out["adverse_share"] = float((f["mark1_bps"] < 0).mean())
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
