"""Classify today's market against the historical regime states and show what followed them.

    python research/regime_now.py --coins SOL,BTC

Uses live data: Coinbase daily candles (trend/vol), Binance funding_multi (funding percentile),
Hyperliquid snapshot (funding, OI, premium), OKX recent liquidations, and the substrate metrics (OI z).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import urllib.request

import duckdb
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from espero2 import hl  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
STATES = ROOT / "research" / "regime_signs.json"
EX = "https://api.exchange.coinbase.com"
UA = {"User-Agent": "espero2/0.1"}


def candles(product: str, n: int = 300) -> np.ndarray:
    url = f"{EX}/products/{product}/candles?granularity=86400"
    raw = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())
    arr = np.array(sorted(raw, key=lambda r: r[0]))
    return arr[:, 4].astype(float)[-n:]


def funding_state(con, symbol: str) -> tuple[float, float]:
    df = con.execute("SELECT ts, rate FROM funding_multi WHERE venue='binance' AND symbol=? ORDER BY ts",
                     [symbol]).df()
    if df.empty:
        return float("nan"), float("nan")
    s = pd.Series(df["rate"].to_numpy(), index=pd.to_datetime(df["ts"]))
    roll = s.rolling("7D").mean().dropna()
    if roll.empty:
        return float("nan"), float("nan")
    cur = float(roll.iloc[-1])
    pct = float((roll <= cur).mean())
    return 100 * cur * 1095, pct          # annualised, percentile


def hl_ctx(coin: str) -> dict:
    meta, ctxs = hl._post("/info", {"type": "metaAndAssetCtxs"}, base=hl.MAINNET)  # noqa: SLF001
    names = [u["name"] for u in meta["universe"]]
    return ctxs[names.index(coin)] if coin in names else {}


def okx_liquidations(coin: str) -> tuple[float, float]:
    url = (f"https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP"
           f"&instFamily={coin}-USDT&state=filled&limit=100")
    data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())
    long_usd = short_usd = 0.0
    for block in data.get("data", []):
        for d in block.get("details", []):
            usd = float(d["bkPx"]) * float(d["sz"])
            if d.get("posSide") == "long":
                long_usd += usd
            else:
                short_usd += usd
    return long_usd, short_usd


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default="SOL,BTC")
    args = ap.parse_args(argv)
    hist = json.loads(STATES.read_text()) if STATES.exists() else []
    con = duckdb.connect(str(DB), read_only=True)
    print(f"{'coin':5s} {'price':>10s} {'ret60':>8s} {'vol%ile':>7s} {'fund%ile':>8s} "
          f"{'fund/yr':>8s} {'state':>16s} {'hist n':>6s} {'med 5d':>8s} {'med 20d':>8s}")
    for coin in args.coins.split(","):
        px = candles(f"{coin}-USD")
        if len(px) < 80:
            print(f"{coin}: not enough candles"); continue
        ret60 = px[-1] / px[-61] - 1
        r = np.diff(np.log(px))
        vol20 = float(pd.Series(r).rolling(20).std().iloc[-1])
        vol_hist = pd.Series(r).rolling(20).std().dropna()
        vol_pct = float((vol_hist <= vol20).mean())
        fund_ann, fund_pct = funding_state(con, f"{coin}USDT")
        ctx = hl_ctx(coin)
        hl_fund = float(ctx.get("funding", 0) or 0) * 8760 * 100
        long_usd, short_usd = okx_liquidations(coin)
        state = f"{'up' if ret60 > 0 else 'down'}/{'high' if vol_pct > 0.5 else 'low'}/" \
                f"{'high' if fund_pct > 0.5 else 'low'}"
        cells = [c for c in hist if c["state"] == state]
        med5 = next((c["median_bps"] for c in cells if c["h"] == 5), float("nan"))
        med20 = next((c["median_bps"] for c in cells if c["h"] == 20), float("nan"))
        n = next((c["n"] for c in cells if c["h"] == 20), 0)
        print(f"{coin:5s} {px[-1]:>10,.2f} {ret60:>+7.1%} {vol_pct:>7.0%} {fund_pct:>8.0%} "
              f"{fund_ann:>+7.1f}% {state:>16s} {n:>6} {med5:>+8.1f} {med20:>+8.1f}")
        print(f"       HL funding {hl_fund:+.1f}%/yr · OI {float(ctx.get('openInterest', 0))/1e6:.2f}M "
              f"{coin} · premium {1e4*float(ctx.get('premium', 0)):+.1f}bp · "
              f"OKX liq 24h long ${long_usd/1e3:,.0f}k / short ${short_usd/1e3:,.0f}k")
    con.close()
    print("\nStates from 2023-01..2025-06, market-relative, 16 cells, none survive FDR — this is context, "
          "not a forecast.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
