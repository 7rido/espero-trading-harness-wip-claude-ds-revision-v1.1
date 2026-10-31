"""Live E1-condition check on proxy data (Coinbase 5m + OKX liquidations).

    python research/live_signal.py --coins BTC,SOL

E1's real rule runs on Binance 5m bars and the daily aggr liquidation feed, which arrive after the UTC
day closes. This checker uses live proxies so "is there a signal right now?" can be answered between
feeds — and labels exactly which conditions pass, fail, or cannot be evaluated.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.request

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
EX = "https://api.exchange.coinbase.com"
OKX = "https://www.okx.com/api/v5/public/liquidation-orders"
UA = {"User-Agent": "espero2/0.1"}


def candles(product: str) -> pd.DataFrame:
    raw = json.loads(urllib.request.urlopen(
        urllib.request.Request(f"{EX}/products/{product}/candles?granularity=300", headers=UA),
        timeout=30).read())
    df = pd.DataFrame(sorted(raw, key=lambda r: r[0]), columns=["ts", "low", "high", "open", "close", "vol"])
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("ts").reset_index(drop=True)


def okx_liq(coin: str) -> pd.DataFrame:
    url = f"{OKX}?instType=SWAP&instFamily={coin}-USDT&state=filled&limit=100"
    data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())
    rows = [{"ts": int(d["ts"]), "side": d.get("posSide"), "usd": float(d["bkPx"]) * float(d["sz"])}
            for block in data.get("data", []) for d in block.get("details", [])]
    return pd.DataFrame(rows)


def check(coin: str) -> dict:
    df = candles(f"{coin}-USD")
    close, high, low, vol = df["close"], df["high"], df["low"], df["vol"]
    burst = np.log(close / close.shift(12))
    x = np.log(vol + 1.0)
    vol_z = (x - x.rolling(48).mean()) / x.rolling(48).std()
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    prior_low = low.shift(1).rolling(48).min()
    down = bool(close.iloc[-1] < prior_low.iloc[-1] and vol_z.iloc[-1] >= 2 and atr.iloc[-1] > 0
                and burst.iloc[-1] < 0)
    liq = okx_liq(coin)
    now = int(pd.Timestamp.now("UTC").timestamp() * 1000)
    last6 = liq[liq["ts"] > now - 6 * 3600_000] if not liq.empty else liq
    long_liq = float(last6[last6["side"] == "long"]["usd"].sum()) if not last6.empty else 0.0
    short_liq = float(last6[last6["side"] == "short"]["usd"].sum()) if not last6.empty else 0.0
    qvol = float((df["vol"].tail(72) * df["close"].tail(72)).sum())       # 6h proxy quote volume
    s = long_liq / qvol if qvol > 0 else float("nan")
    return {"coin": coin, "price": float(close.iloc[-1]), "down_break": down,
            "close_vs_48low": float(1e4 * (close.iloc[-1] / prior_low.iloc[-1] - 1)),
            "vol_z": float(vol_z.iloc[-1]), "burst": float(1e4 * burst.iloc[-1]),
            "long_liq_6h": long_liq, "short_liq_6h": short_liq, "s_proxy": float(s)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default="BTC,SOL")
    args = ap.parse_args(argv)
    print(f"{'coin':5s} {'price':>10s} {'48-low brk':>10s} {'vol z':>6s} {'burst bp':>9s} "
          f"{'long liq 6h':>12s} {'short liq':>10s} {'s proxy':>8s} verdict")
    for coin in args.coins.split(","):
        r = check(coin)
        if not r["down_break"]:
            verdict = "no E1 setup (no down-break)"
        elif r["s_proxy"] > 0.01:
            verdict = "PROXY SIGNAL: down-break with heavy long liqs"
        else:
            verdict = "down-break but liquidation share low"
        print(f"{r['coin']:5s} {r['price']:>10,.2f} {r['close_vs_48low']:>+9.1f}bp {r['vol_z']:>6.2f} "
              f"{r['burst']:>+9.1f} {r['long_liq_6h']/1e3:>10,.0f}k {r['short_liq_6h']/1e3:>8,.0f}k "
              f"{r['s_proxy']:>8.4f} {verdict}")
    print("\nproxy data: Coinbase 5m candles + OKX liquidations. The real rule uses Binance 5m bars and "
          "the daily aggr feed (arrives after the UTC close); tags need the prior day's distribution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
