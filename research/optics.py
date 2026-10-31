"""Universal operator optics: every connected market, every data source, one live snapshot.

    python research/optics.py

Markets are discovered from Hyperliquid perps intersected with Coinbase USD spot, ranked by open
interest, so the panel grows with the venues instead of a hard-coded list. Each market carries price,
state, funding (Binance history + HL live), OI, liquidations and the live E1 break check. The
connections block records every endpoint, whether it answered, and how fast; the sources block records
the freshness of everything already in the substrate.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
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
TOP_N = 10


def get(url: str):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read())


def timed(name: str, via: str, fn) -> tuple[dict, object]:
    start = time.perf_counter()
    try:
        value = fn()
        return {"name": name, "via": via, "ok": True,
                "latency_ms": round(1000 * (time.perf_counter() - start)),
                "detail": ""}, value
    except Exception as exc:                       # noqa: BLE001 - a dead source is data
        return {"name": name, "via": via, "ok": False,
                "latency_ms": round(1000 * (time.perf_counter() - start)),
                "detail": f"{type(exc).__name__}: {exc}"[:120]}, None


def coinbase_markets() -> dict[str, str]:
    products = get("https://api.exchange.coinbase.com/products")
    out = {}
    for p in products:
        if p.get("quote_currency") == "USD" and p.get("status") == "online" and not p.get("trading_disabled"):
            out.setdefault(p["base_currency"], p["id"])
    return out


def coinbase_ticker(product: str) -> dict:
    t = get(f"https://api.exchange.coinbase.com/products/{product}/ticker")
    bid, ask = float(t["bid"]), float(t["ask"])
    return {"price": float(t["price"]), "spread_bps": 1e4 * (ask - bid) / ((ask + bid) / 2) if bid and ask else float("nan")}


def candles(product: str, granularity: int) -> np.ndarray:
    raw = get(f"https://api.exchange.coinbase.com/products/{product}/candles?granularity={granularity}")
    return np.array(sorted(raw, key=lambda r: r[0]))[:, 4].astype(float)


def five_min(product: str) -> pd.DataFrame:
    raw = get(f"https://api.exchange.coinbase.com/products/{product}/candles?granularity=300")
    df = pd.DataFrame(sorted(raw, key=lambda r: r[0]), columns=["ts", "low", "high", "open", "close", "vol"])
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("ts").reset_index(drop=True)


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


def hl_funding_rate(coin: str) -> float:
    """24-hour mean of Hyperliquid's hourly funding, annualised."""
    now = int(time.time() * 1000)
    try:
        hist = hl._post("/info", {"type": "fundingHistory", "coin": coin,  # noqa: SLF001
                                  "startTime": now - 86400_000}, base=hl.MAINNET)
        rates = [float(x["fundingRate"]) for x in hist if int(x["time"]) > now - 86400_000]
        return 1e2 * (sum(rates) / len(rates)) * 8760 if rates else 0.0
    except Exception:                              # noqa: BLE001
        return 0.0


def funding_series(con, symbol: str) -> pd.Series:
    df = con.execute("SELECT ts, rate FROM funding_multi WHERE venue='binance' AND symbol=? ORDER BY ts",
                     [symbol]).df()
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["rate"].to_numpy(), index=pd.to_datetime(df["ts"]))


def freshness(con) -> list[dict]:
    rows = []
    for table, col in (("funding_multi", "ts"), ("metrics", "ts"), ("tardis_derivative", "ts"),
                       ("tardis_liquidations", "ts"), ("bars_daily", "date")):
        try:
            lo, hi = con.execute(f'SELECT MIN("{col}"), MAX("{col}") FROM {table}').fetchone()
            n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            rows.append({"source": f"substrate.{table}", "ok": True,
                         "detail": f"{n:,} rows · {str(lo)[:10]} → {str(hi)[:10]}"})
        except Exception as exc:                   # noqa: BLE001
            rows.append({"source": f"substrate.{table}", "ok": False, "detail": str(exc)[:80]})
    feed = sorted((ROOT / "data" / "aggr" / "forward5m").glob("*.csv.gz"))
    rows.append({"source": "aggr.forward5m", "ok": bool(feed),
                 "detail": feed[-1].name.replace(".csv.gz", "") if feed else "no files"})
    try:
        p = ROOT / "paper.db"
        last = con_ts(p) if p.exists() else ""
        rows.append({"source": "paper.db marks", "ok": bool(last), "detail": last})
    except Exception:                              # noqa: BLE001
        rows.append({"source": "paper.db marks", "ok": False, "detail": "unavailable"})
    return rows


def con_ts(path: pathlib.Path) -> str:
    import sqlite3
    d = sqlite3.connect(path)
    ts = d.execute("SELECT MAX(ts) FROM equity").fetchone()[0]
    d.close()
    return pd.to_datetime(ts, unit="s").strftime("%Y-%m-%d %H:%M") if ts else ""


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    out: dict = {"at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
                 "markets": [], "connections": [], "sources": [], "flags": []}

    conn, products = timed("coinbase products", "GET /products", coinbase_markets)
    out["connections"].append(conn)
    conn, hl_data = timed("hyperliquid perps", "POST /info metaAndAssetCtxs",
                          lambda: hl._post("/info", {"type": "metaAndAssetCtxs"}, base=hl.MAINNET))  # noqa: SLF001
    out["connections"].append(conn)
    conn, spot_book = timed("hyperliquid spot UBTC/USDC", "POST /info l2Book @142",
                            lambda: hl._post("/info", {"type": "l2Book", "coin": "@142"}, base=hl.MAINNET))  # noqa: SLF001
    out["connections"].append(conn)
    conn, _ = timed("okx liquidations", "GET /public/liquidation-orders",
                    lambda: okx_liq("BTC"))
    out["connections"].append(conn)

    perps: list[tuple[str, float, float]] = []
    if hl_data:
        meta, ctxs = hl_data
        for u, c in zip(meta["universe"], ctxs):
            oi = float(c.get("openInterest", 0) or 0)
            mark = float(c.get("markPx", 0) or 0)
            perps.append((u["name"], oi, mark))
    perps.sort(key=lambda x: x[1] * x[2], reverse=True)
    picked = [(n, oi, mk) for n, oi, mk in perps if products and n in products][:TOP_N]

    for coin, oi, mark in picked:
        product = products[coin]
        t = coinbase_ticker(product)
        px = candles(product, 86400)
        ret60 = float(px[-1] / px[-61] - 1) if len(px) > 61 else float("nan")
        r = np.diff(np.log(px[-300:]))
        vol20 = float(pd.Series(r).rolling(20).std().iloc[-1])
        vol_pct = float((pd.Series(r).rolling(20).std().dropna() <= vol20).mean())
        fr = funding_series(con, f"{coin}USDT")
        if len(fr):
            roll = fr.rolling("7D").mean().dropna()
            fund_ann = float(100 * roll.iloc[-1] * 1095)
            fund_pct = float((roll <= roll.iloc[-1]).mean())
            f_state = "high" if fund_pct > 0.5 else "low"
        else:
            fund_ann = fund_pct = float("nan")
            f_state = "n/a"
        ctx = next((c for u, c in zip(hl_data[0]["universe"], hl_data[1]) if u["name"] == coin), {}) if hl_data else {}
        hl_fund = hl_funding_rate(coin) or float(ctx.get("funding", 0) or 0) * 8760 * 100
        premium = 1e4 * float(ctx.get("premium", 0) or 0)
        long_liq, short_liq = okx_liq(coin)
        e1 = e1_check(five_min(product))
        out["markets"].append({
            "coin": coin, "product": product, "price": t["price"], "spread_bps": t["spread_bps"],
            "ret60": ret60, "vol_pct": vol_pct, "fund_pct": fund_pct,
            "funding_binance": fund_ann, "funding_hl": hl_fund, "oi_hl": oi, "premium_bp": premium,
            "state": f"{'up' if ret60 > 0 else 'down'}/{'high' if vol_pct > .5 else 'low'}/{f_state}",
            "liq_long": long_liq, "liq_short": short_liq, "e1": e1})

    if spot_book and spot_book.get("levels") and spot_book["levels"][0]:
        mid = (float(spot_book["levels"][0][0]["px"]) + float(spot_book["levels"][1][0]["px"])) / 2
        out["flags"].append(f"HL spot UBTC/USDC mid {mid:,.2f}; book-only, spot ctx reports wrong px")
    if len(out["markets"]) == 0:
        out["flags"].append("no markets discovered — check the connections block")
    out["sources"] = freshness(con)
    con.close()
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)} · {len(out['markets'])} markets · "
          f"{sum(c['ok'] for c in out['connections'])}/{len(out['connections'])} connections up")
    for m in out["markets"]:
        print(f"  {m['coin']:5s} ${m['price']:>10,.2f} {m['state']:>14s} "
              f"B {m['funding_binance']:+6.1f}% HL {m['funding_hl']:+6.1f}% OI {m['oi_hl']:>12,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
