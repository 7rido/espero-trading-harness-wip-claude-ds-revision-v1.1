"""Measured round-trip cost on the recorded books, against E1's 9 bps assumption.

    python research/cost_check.py

Quoted spread is measured from every snapshot in data/book/*.jsonl; the fee is the Hyperliquid
taker rate at 4.5 bps a side. Writes research/cost_check.json.
"""
from __future__ import annotations

import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
FEE_BPS = 4.5


def main() -> int:
    spreads, products = [], set()
    for path in sorted((ROOT / "data" / "book").glob("*.jsonl")):
        with path.open() as f:
            for line in f:
                o = json.loads(line)
                if not o.get("bids") or not o.get("asks"):
                    continue
                bid, ask = float(o["bids"][0][0]), float(o["asks"][0][0])
                mid = (bid + ask) / 2
                if mid > 0 and ask > bid:
                    spreads.append((ask - bid) / mid)
                    products.add(o.get("product", "?"))
    if not spreads:
        print("no book snapshots to measure"); return 1
    s = sorted(spreads)
    out = {"snapshots": len(spreads), "products": sorted(products),
           "median_spread_bps": 1e4 * statistics.median(spreads),
           "p90_spread_bps": 1e4 * s[int(0.9 * len(s))],
           "fee_round_trip_bps": 2 * FEE_BPS,
           "all_in_round_trip_bps": 1e4 * statistics.median(spreads) + 2 * FEE_BPS}
    (ROOT / "research" / "cost_check.json").write_text(json.dumps(out, indent=1))
    print(f"{out['snapshots']} snapshots on {', '.join(out['products'])}")
    print(f"median spread {out['median_spread_bps']:.2f} bps, p90 {out['p90_spread_bps']:.2f} bps")
    print(f"fees {out['fee_round_trip_bps']:.1f} bps round trip -> all-in "
          f"{out['all_in_round_trip_bps']:.2f} bps (E1 assumes 9.0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
