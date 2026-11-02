"""Fetch Hyperliquid funding history for the live coverage universe.

    python research/forecast_funding.py

Binance and Bybit public endpoints are geo-blocked from this machine, while
Hyperliquid's public `fundingHistory` endpoint answers. The script paginates the
500-row API limit, writes a research-only DuckDB overlay, and reports the
current 7-day funding percentile used by the regime state.

It does not modify the substrate, forecast, paper books, ledger or order path.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import time
import urllib.error
import urllib.request

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "forecast_funding.duckdb"
SUMMARY = ROOT / "research" / "forecast_funding_coverage.json"
COINS = ("ZEC", "NEAR", "ENA", "UNI", "HYPE", "PUMP")
URL = "https://api.hyperliquid.xyz/info"
PAGE = 500
WEEK_HOURS = 7 * 24
YEAR_HOURS = 365 * 24


def _post(payload: dict) -> list[dict]:
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "espero2-funding-coverage/0.1"},
    )
    for attempt in range(5):
        try:
            raw = json.loads(urllib.request.urlopen(req, timeout=30).read())
            return raw if isinstance(raw, list) else []
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 4:
                raise
            time.sleep(2 ** attempt)
    return []


def fetch(coin: str, start_ms: int, max_pages: int = 120) -> pd.DataFrame:
    rows: list[dict] = []
    cursor = start_ms
    for _ in range(max_pages):
        page = _post({"type": "fundingHistory", "coin": coin, "startTime": cursor})
        if not page:
            break
        rows.extend(page)
        last = max(int(r["time"]) for r in page)
        if len(page) < PAGE or last <= cursor:
            break
        cursor = last + 1
        time.sleep(0.8)
    if not rows:
        return pd.DataFrame(columns=["coin", "ts", "rate", "interval_hours"])
    df = pd.DataFrame(rows)
    df["coin"] = coin
    df["ts"] = pd.to_datetime(df["time"].astype("int64"), unit="ms", utc=True).dt.tz_convert(None)
    df["rate"] = pd.to_numeric(df["fundingRate"], errors="coerce")
    df["interval_hours"] = 1.0
    df = df.drop_duplicates("ts").sort_values("ts")
    return df[["coin", "ts", "rate", "interval_hours"]]


def state(coin: str, df: pd.DataFrame) -> dict:
    rates = df.set_index("ts")["rate"].astype(float).sort_index()
    fund7 = rates.rolling(WEEK_HOURS, min_periods=WEEK_HOURS // 2).mean()
    pct = fund7.rolling(YEAR_HOURS, min_periods=60 * 24).rank(pct=True)
    last = rates.index[-1]
    return {
        "coin": coin,
        "rows": int(len(df)),
        "first": str(df["ts"].min()),
        "last": str(df["ts"].max()),
        "last_rate_bps_hour": float(rates.iloc[-1] * 1e4),
        "fund7_bps_hour": float(fund7.iloc[-1] * 1e4) if pd.notna(fund7.iloc[-1]) else None,
        "fund7_annual_pct": float(fund7.iloc[-1] * 24 * 365 * 100) if pd.notna(fund7.iloc[-1]) else None,
        "fund_pct": float(pct.iloc[-1]) if pd.notna(pct.iloc[-1]) else None,
        "fund_state": ("high" if pct.iloc[-1] > 0.5 else "low") if pd.notna(pct.iloc[-1]) else None,
        "stale_days": (pd.Timestamp.now("UTC").tz_localize(None) - last).total_seconds() / 86400,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coins", default=",".join(COINS))
    ap.add_argument("--start", default="2025-01-01")
    args = ap.parse_args()
    start = pd.Timestamp(args.start, tz="UTC")
    start_ms = int(start.timestamp() * 1000)
    coins = [c.strip().upper() for c in args.coins.split(",") if c.strip()]

    con = duckdb.connect(str(OUT))
    con.execute("CREATE OR REPLACE TABLE funding (coin VARCHAR, ts TIMESTAMP, rate DOUBLE, interval_hours DOUBLE, venue VARCHAR, known_time TIMESTAMP)")
    summary: dict[str, dict] = {}
    for coin in coins:
        try:
            df = fetch(coin, start_ms)
        except Exception as exc:
            print(f"{coin:5s} fetch error: {type(exc).__name__}: {exc}")
            summary[coin] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        if df.empty:
            print(f"{coin:5s} no funding history")
            summary[coin] = {"rows": 0}
            continue
        df.insert(0, "venue", "hyperliquid")
        df["known_time"] = df["ts"] + pd.Timedelta(hours=1)
        con.register("funding_df", df)
        con.execute("INSERT INTO funding SELECT coin, ts, rate, interval_hours, venue, known_time FROM funding_df")
        s = state(coin, df)
        summary[coin] = s
        print(f"{coin:5s} n={s['rows']:>6} {s['first']} -> {s['last']} "
              f"fund7={s['fund7_annual_pct']:+.1f}%/yr pct={s['fund_pct']:.2f} "
              f"state={s['fund_state']}")
    con.close()
    SUMMARY.write_text(json.dumps({"start": str(start), "venue": "hyperliquid", "coins": summary}, indent=1))
    print(f"wrote {SUMMARY.relative_to(ROOT)} and {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
