"""Fetch perp funding from three venues and ingest it into the substrate.

    python research/funding_fetch.py --coin SOL --binance-from 2025-07 --binance-to 2026-10 --hl-days 90

Writes table funding_multi(venue, symbol, ts, rate, interval_hours, known_time) and prints the
annualised cross-venue picture. Keyless: Binance archive, Hyperliquid, OKX.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import pathlib
import urllib.request
import zipfile

import duckdb
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
CACHE = ROOT / "data_funding"
UA = {"User-Agent": "espero2/0.1"}
BINANCE = "https://data.binance.vision/data/futures/um/monthly/fundingRate"
HL = "https://api.hyperliquid.xyz/info"
OKX = "https://www.okx.com/api/v5/public"


def _get(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()


def _post(url: str, body: dict) -> list:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={**UA, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def binance(coin: str, start: str, end: str) -> pd.DataFrame:
    sym = f"{coin}USDT"
    rows = []
    for month in pd.period_range(start, end, freq="M"):
        m = str(month)
        dest = CACHE / "binance" / sym / f"{m}.zip"
        if not dest.exists():
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(_get(f"{BINANCE}/{sym}/{sym}-fundingRate-{m}.zip"))
            except Exception:
                continue
        try:
            with zipfile.ZipFile(dest) as z:
                df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])))
        except Exception:
            continue
        for _, r in df.iterrows():
            rows.append({"venue": "binance", "symbol": sym,
                         "ts": pd.to_datetime(int(r["calc_time"]), unit="ms"),
                         "rate": float(r["last_funding_rate"]),
                         "interval_hours": float(r.get("funding_interval_hours", 8)),
                         "known_time": pd.Timestamp.now("UTC")})
    return pd.DataFrame(rows)


def hyperliquid(coin: str, days: int) -> tuple[pd.DataFrame, dict]:
    """The API caps a response at 500 hourly rows; page forward until the window is covered."""
    now = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    start = now - days * 86400_000
    rows = []
    for _ in range(12):
        hist = _post(HL, {"type": "fundingHistory", "coin": coin, "startTime": start})
        if not hist:
            break
        rows += [{"venue": "hyperliquid", "symbol": coin,
                  "ts": pd.to_datetime(int(x["time"]), unit="ms"),
                  "rate": float(x["fundingRate"]), "interval_hours": 1.0,
                  "known_time": pd.Timestamp.now("UTC")} for x in hist]
        if len(hist) < 500:
            break
        start = int(hist[-1]["time"]) + 1
    meta, ctxs = _post(HL, {"type": "metaAndAssetCtxs"})
    names = [u["name"] for u in meta["universe"]]
    ctx = ctxs[names.index(coin)] if coin in names else {}
    snapshot = {k: ctx.get(k) for k in ("funding", "openInterest", "markPx", "oraclePx", "premium")}
    return pd.DataFrame(rows), snapshot


def okx(coin: str, pages: int = 3) -> pd.DataFrame:
    inst = f"{coin}-USDT-SWAP"
    rows, after = [], None
    for _ in range(pages):
        url = f"{OKX}/funding-rate-history?instId={inst}&limit=100" + (f"&after={after}" if after else "")
        data = json.loads(_get(url))["data"]
        if not data:
            break
        for x in data:
            rows.append({"venue": "okx", "symbol": inst,
                         "ts": pd.to_datetime(int(x["fundingTime"]), unit="ms"),
                         "rate": float(x["fundingRate"]), "interval_hours": 8.0,
                         "known_time": pd.Timestamp.now("UTC")})
        after = data[-1]["fundingTime"]
    return pd.DataFrame(rows)


def ingest(frames: list[pd.DataFrame]) -> dict:
    data = pd.concat([f for f in frames if f is not None and not f.empty], ignore_index=True)
    if data.empty:
        return {"rows": 0}
    data["ts"] = pd.to_datetime(data["ts"]).dt.tz_localize(None)
    data["known_time"] = pd.to_datetime(data["known_time"]).dt.tz_localize(None)
    con = duckdb.connect(str(DB))
    con.execute("""CREATE TABLE IF NOT EXISTS funding_multi(venue VARCHAR, symbol VARCHAR,
        ts TIMESTAMP, rate DOUBLE, interval_hours DOUBLE, known_time TIMESTAMP,
        PRIMARY KEY (venue, symbol, ts))""")
    con.register("d", data)
    con.execute("INSERT OR IGNORE INTO funding_multi SELECT venue, symbol, ts, rate, interval_hours, known_time FROM d")
    con.unregister("d")
    out = con.execute("""SELECT venue, symbol, COUNT(*) AS n, MIN(ts) AS first_ts,
                                MAX(ts) AS last_ts, AVG(rate) AS mean_rate
                         FROM funding_multi GROUP BY venue, symbol ORDER BY venue""").df()
    con.close()
    return {"rows": len(data), "summary": out.to_dict("records")}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default="SOL")
    ap.add_argument("--binance-from", default="2025-07")
    ap.add_argument("--binance-to", default="2026-10")
    ap.add_argument("--hl-days", type=int, default=90)
    args = ap.parse_args(argv)
    b = binance(args.coin, args.binance_from, args.binance_to)
    h, snapshot = hyperliquid(args.coin, args.hl_days)
    o = okx(args.coin)
    res = ingest([b, h, o])
    print(f"fetched {res['rows']} rows")
    for r in res.get("summary", []):
        mult = 8760 / (1 if r["venue"] == "hyperliquid" else 8)
        print(f"  {r['venue']:12s} {r['symbol']:14s} {int(r['n']):>6} rows  "
              f"{str(r['first_ts'])[:10]} → {str(r['last_ts'])[:10]}  "
              f"mean {1e4*r['mean_rate']:+.4f} bp/interval ≈ {100*r['mean_rate']*mult:+.1f}%/yr")
    print("HL snapshot:", snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
