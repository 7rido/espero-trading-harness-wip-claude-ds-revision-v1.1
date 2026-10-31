"""Operator optics: one live snapshot of the measurements that decide a trade.

    python research/optics.py

Writes research/optics.json, which the dashboard renders. Everything here is read-only: prices from
Coinbase, funding from the substrate, OI/premium from Hyperliquid, liquidations from OKX.
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from espero2 import hl  # noqa: E402

OUT = ROOT / "research" / "optics.json"
DB = ROOT / "data_substrate" / "substrate.duckdb"
UA = {"User-Agent": "espero2/0.1"}
COINS = ["BTC", "ETH", "SOL"]


def get(url: str):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read())


def ticker(coin: str) -> dict:
    t = get(f"https://api.exchange.coinbase.com/products/{coin}-USD/ticker")
    bid, ask = float(t["bid"]), float(t["ask"])
    return {"price": float(t["price"]), "bid": bid, "ask": ask,
            "spread_bps": 1e4 * (ask - bid) / ((ask + bid) / 2) if bid and ask else float("nan")}


def daily_candles(coin: str) -> np.ndarray:
    raw = get(f"https://api.exchange.coinbase.com/products/{coin}-USD/candles?granularity=86400")
    return np.array(sorted(raw, key=lambda r: r[0]))[:, 4].astype(float)


def five_min(coin: str) -> pd.DataFrame:
    raw = get(f"https://api.exchange.coinbase.com/products/{coin}-USD/candles?granularity=300")
    df = pd.DataFrame(sorted(raw, key=lambda r: r[0]), columns=["ts", "low", "high", "open", "close", "vol"])
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("ts").reset_index(drop=True)


def funding_rows(con, symbol: str) -> pd.Series:
    df = con.execute("SELECT ts, rate FROM funding_multi WHERE venue='binance' AND symbol=? ORDER BY ts",
                     [symbol]).df()
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["rate"].to_numpy(), index=pd.to_datetime(df["ts"]))


def okx_liq(coin: str) -> tuple[float, float]:
    data = get(f"https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP"
               f"&instFamily={coin}-USDT&state=filled&limit=100")
    long_usd = short_usd = 0.0
    for block in data.get("data", []):
        for d in block.get("details", []):
            usd = float(d["bkPx"]) * float(d["sz"])
            if d.get("posSide") == "long":
                long_usd += usd
            else:
                short_usd += usd
    return long_usd, short_usd


def hl_ctx(coin: str) -> dict:
    meta, ctxs = hl._post("/info", {"type": "metaAndAssetCtxs"}, base=hl.MAINNET)  # noqa: SLF001
    names = [u["name"] for u in meta["universe"]]
    return ctxs[names.index(coin)] if coin in names else {}


def hl_spot_basis(coin: str) -> float | None:
    if coin != "BTC":
        return None
    book = hl._post("/info", {"type": "l2Book", "coin": "@142"}, base=hl.MAINNET)  # noqa: SLF001
    bids, asks = book["levels"]
    if not bids or not asks:
        return None
    return (float(bids[0]["px"]) + float(asks[0]["px"])) / 2


def e1_check(df: pd.DataFrame) -> dict:
    close, high, low, vol = df["close"], df["high"], df["low"], df["vol"]
    burst = float(np.log(close.iloc[-1] / close.iloc[-13]))
    x = np.log(vol + 1.0)
    vol_z = float((x.iloc[-1] - x.tail(48).mean()) / x.tail(48).std())
    prior_low = float(low.tail(49).iloc[:-1].min())
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
    return {"down_break": bool(close.iloc[-1] < prior_low and vol_z >= 2 and atr > 0 and burst < 0),
            "close_vs_low_bp": 1e4 * (close.iloc[-1] / prior_low - 1),
            "vol_z": vol_z, "burst_bp": 1e4 * burst}


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    out = {"at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"), "coins": [], "flags": []}
    for coin in COINS:
        t = ticker(coin)
        px = daily_candles(coin)
        ret60 = float(px[-1] / px[-61] - 1) if len(px) > 61 else float("nan")
        r = np.diff(np.log(px[-300:]))
        vol20 = float(pd.Series(r).rolling(20).std().iloc[-1])
        vol_pct = float((pd.Series(r).rolling(20).std().dropna() <= vol20).mean())
        fr = funding_rows(con, f"{coin}USDT")
        if len(fr):
            roll = fr.rolling("7D").mean().dropna()
            fund_ann = float(100 * roll.iloc[-1] * 1095)
            fund_pct = float((roll <= roll.iloc[-1]).mean())
        else:
            fund_ann, fund_pct = float("nan"), float("nan")
        ctx = hl_ctx(coin)
        hl_fund = float(ctx.get("funding", 0) or 0) * 8760 * 100
        oi = float(ctx.get("openInterest", 0) or 0)
        premium = 1e4 * float(ctx.get("premium", 0) or 0)
        long_liq, short_liq = okx_liq(coin)
        e1 = e1_check(five_min(coin))
        state = (f"{'up' if ret60 > 0 else 'down'}/{'high' if vol_pct > .5 else 'low'}/"
                 f"{'high' if fund_pct > .5 else 'low'}")
        out["coins"].append({"coin": coin, "price": t["price"], "spread_bps": t["spread_bps"],
                             "ret60": ret60, "vol_pct": vol_pct, "fund_pct": fund_pct,
                             "funding_binance": fund_ann, "funding_hl": hl_fund,
                             "oi_hl": oi, "premium_bp": premium, "state": state,
                             "liq_long": long_liq, "liq_short": short_liq, "e1": e1})
    spot = hl_spot_basis("BTC")
    if spot:
        out["flags"].append(f"HL spot UBTC/USDC mid {spot:,.2f} (book-only: spot ctx reports wrong px)")
    if not funding_rows(con, "BTCUSDT").empty:
        out["flags"].append("funding percentile from 2025-07..2026-09 history")
    con.close()
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)} · {len(out['coins'])} coins")
    for c in out["coins"]:
        print(f"  {c['coin']:4s} ${c['price']:>10,.2f} {c['state']:>14s} "
              f"fund B {c['funding_binance']:+.1f}% / HL {c['funding_hl']:+.1f}% "
              f"OI {c['oi_hl']:,.0f} liq L ${c['liq_long']/1e3:,.0f}k S ${c['liq_short']/1e3:,.0f}k "
              f"{'BREAK' if c['e1']['down_break'] else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
