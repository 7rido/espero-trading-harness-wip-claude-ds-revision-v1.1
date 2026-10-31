"""Fetch recent perp liquidations (OKX public feed) and ingest into the substrate.

    python research/liquidation_fetch.py --coin SOL --pages 6

Binance's USDT-M liquidation archive does not exist (only COIN-M, which ends 2024-10); OKX publishes
recent filled liquidations keyless, so this fetches the last few hours and keeps them.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import urllib.request

import duckdb
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
OKX = "https://www.okx.com/api/v5/public/liquidation-orders"


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "espero2/0.1"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def fetch(coin: str, pages: int) -> pd.DataFrame:
    inst = f"{coin}-USDT"
    rows, before = [], None
    for _ in range(pages):
        url = f"{OKX}?instType=SWAP&instFamily={inst}&state=filled&limit=100"
        if before:
            url += f"&before={before}"
        payload = _get(url)
        data = payload.get("data") or []
        if not data:
            break
        oldest = None
        for block in data:
            for d in block.get("details", []):
                ts = int(d["ts"])
                price = float(d["bkPx"])
                qty = float(d["sz"])            # OKX SOL-USDT-SWAP is 1 SOL per contract
                rows.append({"venue": "okx", "symbol": f"{coin}-USDT-SWAP", "ts": ts,
                             "price": price, "qty": qty, "usd": price * qty,
                             "side": d.get("posSide", "")})
                oldest = ts if oldest is None else min(oldest, ts)
        if oldest is None:
            break
        before = oldest
    df = pd.DataFrame(rows)
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"], unit="ms").dt.tz_localize(None)
    return df


def ingest(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"rows": 0}
    con = duckdb.connect(str(DB))
    con.execute("""CREATE TABLE IF NOT EXISTS liquidation_multi(venue VARCHAR, symbol VARCHAR,
        ts TIMESTAMP, price DOUBLE, qty DOUBLE, usd DOUBLE, side VARCHAR,
        PRIMARY KEY (venue, symbol, ts, price, qty))""")
    con.register("d", df)
    con.execute("INSERT OR IGNORE INTO liquidation_multi SELECT venue, symbol, ts, price, qty, usd, side FROM d")
    con.unregister("d")
    summary = con.execute("""
        SELECT COUNT(*) AS n, MIN(ts) AS first_ts, MAX(ts) AS last_ts, SUM(usd) AS usd,
               SUM(CASE WHEN side = 'long' THEN usd ELSE 0 END) AS long_usd,
               SUM(CASE WHEN side = 'short' THEN usd ELSE 0 END) AS short_usd
        FROM liquidation_multi WHERE venue = 'okx'""").df().to_dict("records")[0]
    top = con.execute("""
        SELECT date_trunc('hour', ts) AS hour, SUM(usd) AS usd FROM liquidation_multi
        WHERE venue='okx' GROUP BY 1 ORDER BY usd DESC LIMIT 3""").df().to_dict("records")
    con.close()
    return {"rows": len(df), "summary": summary, "top_hours": top}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default="SOL")
    ap.add_argument("--pages", type=int, default=6)
    args = ap.parse_args(argv)
    df = fetch(args.coin, args.pages)
    res = ingest(df)
    s = res.get("summary", {})
    print(f"fetched {res['rows']} liquidation fills")
    if res["rows"]:
        print(f"  span {str(s['first_ts'])[:19]} → {str(s['last_ts'])[:19]}  "
              f"total ${s['usd']/1e6:,.2f}M  long ${s['long_usd']/1e6:,.2f}M / "
              f"short ${s['short_usd']/1e6:,.2f}M")
        for h in res["top_hours"]:
            print(f"  top hour {str(h['hour'])[:16]}  ${h['usd']/1e3:,.0f}k")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
