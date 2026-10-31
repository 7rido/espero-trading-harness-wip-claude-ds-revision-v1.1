"""Validate the maker-fill assumption against real book and trades: Tardis SOL 2026-10-01.

    python research/maker_fill.py

For every minute we place a passive buy at the best bid with the visible queue ahead, and a passive
sell at the best ask. A fill requires cumulative aggressive volume at or through our price to exceed
the queue within 60 s. Reports fill rates by spread quartile and compares to the 22-87% assumption.
"""
from __future__ import annotations

import gzip
import importlib.util
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DAY, SYM = "2026-10-01", "SOLUSDT"
BOOK = ROOT / "data_tardis" / "book_ticker" / f"{SYM}-{DAY}.csv.gz"


def main() -> int:
    spec = importlib.util.spec_from_file_location("tf", ROOT / "research" / "tardis_fetch.py")
    tf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tf)

    book = pd.read_csv(BOOK, usecols=["timestamp", "ask_amount", "ask_price", "bid_price", "bid_amount"])
    book["minute"] = pd.to_datetime(book["timestamp"], unit="us").dt.floor("min")
    snap = book.sort_values("timestamp").groupby("minute").tail(1).reset_index(drop=True)
    print(f"book snapshots: {len(snap):,} minutes from {len(book):,} updates")
    del book

    tr = tf.sample("trades", DAY, SYM)
    if tr is None or tr.empty:
        print("no trades sample"); return 1
    tr["minute"] = pd.to_datetime(tr["timestamp"], unit="us").dt.floor("min")
    sell = tr[tr["side"] == "sell"].groupby(["minute", "price"])["amount"].sum()
    buy = tr[tr["side"] == "buy"].groupby(["minute", "price"])["amount"].sum()
    print(f"trades: {len(tr):,}")

    spread = 1e4 * (snap["ask_price"] - snap["bid_price"]) / ((snap["ask_price"] + snap["bid_price"]) / 2)
    snap = snap.assign(spread_bps=spread)
    snap["q"] = pd.qcut(snap["spread_bps"], 4, labels=False, duplicates="drop")

    filled = []
    for _, r in snap.iterrows():
        m, bid, ask = r["minute"], r["bid_price"], r["ask_price"]
        s = sell.get(m, pd.Series(dtype=float))
        s = s[s.index <= bid].sum() if len(s) else 0.0
        b = buy.get(m, pd.Series(dtype=float))
        b = b[b.index >= ask].sum() if len(b) else 0.0
        filled.append({"q": r["q"], "buy_fill": s >= r["bid_amount"], "sell_fill": b >= r["ask_amount"],
                       "bid_amt": r["bid_amount"], "ask_amt": r["ask_amount"]})
    f = pd.DataFrame(filled)
    print(f"\npassive buy at bid: {f['buy_fill'].mean():.1%}   passive sell at ask: {f['sell_fill'].mean():.1%}")
    print(f"{'spread quartile':>15} {'n':>5} {'buy fill':>9} {'sell fill':>10}")
    for q, g in f.groupby("q"):
        print(f"{int(q):>15} {len(g):>5} {g['buy_fill'].mean():>9.1%} {g['sell_fill'].mean():>10.1%}")
    print("\nassumption in use: 22-87% maker fills within 60 s (project cost model)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
