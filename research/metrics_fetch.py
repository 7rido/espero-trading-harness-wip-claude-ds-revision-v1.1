"""Binance USD-M daily metrics -> substrate (open interest, positioning, taker imbalance).

    python research/metrics_fetch.py --symbol SOLUSDT --days 365
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import pathlib
import urllib.request
import zipfile

import duckdb
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
CACHE = ROOT / "data_metrics"
BASE = "https://data.binance.vision/data/futures/um/daily/metrics"
UA = {"User-Agent": "espero2/0.1"}


def fetch(symbol: str, days: int) -> pd.DataFrame:
    rows = []
    today = dt.date.today()
    for back in range(days, -1, -1):
        day = today - dt.timedelta(days=back)
        dest = CACHE / symbol / f"{day.isoformat()}.zip"
        if not dest.exists():
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                req = urllib.request.Request(f"{BASE}/{symbol}/{symbol}-metrics-{day}.zip", headers=UA)
                dest.write_bytes(urllib.request.urlopen(req, timeout=60).read())
            except Exception:
                continue
        try:
            with zipfile.ZipFile(dest) as z:
                df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])))
        except Exception:
            continue
        for _, r in df.iterrows():
            rows.append({"symbol": symbol, "ts": pd.to_datetime(r["create_time"]),
                         "oi": float(r["sum_open_interest"]),
                         "oi_value": float(r["sum_open_interest_value"]),
                         "top_ls": float(r["sum_toptrader_long_short_ratio"]),
                         "global_ls": float(r["count_long_short_ratio"]),
                         "taker_ratio": float(r["sum_taker_long_short_vol_ratio"])})
    return pd.DataFrame(rows)


def ingest(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"rows": 0}
    con = duckdb.connect(str(DB))
    con.execute("""CREATE TABLE IF NOT EXISTS metrics(symbol VARCHAR, ts TIMESTAMP, oi DOUBLE,
        oi_value DOUBLE, top_ls DOUBLE, global_ls DOUBLE, taker_ratio DOUBLE,
        PRIMARY KEY (symbol, ts))""")
    con.register("d", df)
    con.execute("INSERT OR IGNORE INTO metrics SELECT symbol, ts, oi, oi_value, top_ls, global_ls, taker_ratio FROM d")
    con.unregister("d")
    s = con.execute("SELECT COUNT(*) AS n, MIN(ts), MAX(ts), AVG(oi) FROM metrics WHERE symbol=?",
                    [df["symbol"].iloc[0]]).fetchone()
    con.close()
    return {"rows": len(df), "n": s[0], "first": str(s[1])[:16], "last": str(s[2])[:16], "oi_avg": s[3]}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="SOLUSDT")
    ap.add_argument("--days", type=int, default=365)
    args = ap.parse_args(argv)
    res = ingest(fetch(args.symbol, args.days))
    print(f"metrics {args.symbol}: fetched {res['rows']} rows; table now {res.get('n')} rows "
          f"{res.get('first')} → {res.get('last')} · mean OI {res.get('oi_avg', 0)/1e6:,.2f}M")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
