"""Read-only signal snapshot for a list of coins: SMA regime, price, spread. No orders, no writes.

    python research/signals.py --coins BTC,ETH,SOL,XRP,DOGE
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from espero2 import hl  # noqa: E402
from espero2.strategy import sma_regime


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default="BTC,ETH,SOL")
    ap.add_argument("--interval", default="1h")
    args = ap.parse_args(argv)
    coins = [c.strip() for c in args.coins.split(",") if c.strip()]
    print(f"{'coin':6s} {'mid':>12s} {'spread':>8s} {'sma20':>12s} {'sma50':>12s} {'regime':>7s}")
    for coin in coins:
        try:
            b = hl.book(coin)
            bars = hl.candles(coin, args.interval, 200)
            sig = sma_regime(bars)
            from espero2.strategy import sma
            closes = [float(x["close"]) for x in bars]
            s20, s50 = sma(closes, 20), sma(closes, 50)
            print(f"{coin:6s} {b.mid:>12,.2f} {b.spread_bps:>7.1f}b {s20:>12,.4f} {s50:>12,.4f} "
                  f"{sig.side or 'flat':>7s}")
        except Exception as exc:                 # noqa: BLE001 - a dead coin is data, not a crash
            print(f"{coin:6s} unavailable: {type(exc).__name__}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
