"""Fresh spot snapshot from Coinbase Exchange (keyless) — price, spread, depth at size, recent trend.

    python research/spot.py --product SOL-USD --notional 1600
"""
from __future__ import annotations

import argparse
import json
import urllib.request

import numpy as np

EX = "https://api.exchange.coinbase.com"
UA = {"User-Agent": "espero2/0.1", "Accept": "application/json"}


def get(path: str):
    return json.loads(urllib.request.urlopen(urllib.request.Request(EX + path, headers=UA), timeout=20).read())


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default="SOL-USD")
    ap.add_argument("--notional", type=float, default=1600.0)
    args = ap.parse_args(argv)
    t = get(f"/products/{args.product}/ticker")
    s = get(f"/products/{args.product}/stats")
    b = get(f"/products/{args.product}/book?level=2")
    bid, ask = float(t["bid"]), float(t["ask"])
    mid = (bid + ask) / 2
    print(f"spot {args.product}  bid {bid:.3f} ask {ask:.3f}  spread {1e4*(ask-bid)/mid:.2f} bps  "
          f"last {float(t['price']):.2f}  24h vol {float(s['volume']):,.0f}")
    for side, book in (("buy", b["asks"]), ("sell", b["bids"])):
        spent, worst = 0.0, mid
        for price, size, *_ in book:
            px, sz = float(price), float(size)
            take = min(args.notional - spent, px * sz)
            spent += take
            worst = px
            if spent >= args.notional:
                break
        print(f"  {side:4s} ${args.notional:>10,.0f}: filled by {worst:.3f}  "
              f"slip {abs(worst-mid)/mid*1e4:5.2f} bps")
    c = get(f"/products/{args.product}/candles?granularity=3600")
    closes = np.array(sorted(c, key=lambda r: r[0]))[:, 4].astype(float)
    ret = np.diff(np.log(closes))
    print(f"hourly: {len(closes)} bars  last {closes[-1]:.3f}  "
          f"24h {1e2*(closes[-1]/closes[-25]-1):+.2f}%  7d {1e2*(closes[-1]/closes[-169]-1):+.2f}%  "
          f"realised vol {1e2*ret.std()*np.sqrt(24*365):.0f}%/yr")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
