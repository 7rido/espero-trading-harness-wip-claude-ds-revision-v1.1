"""Build a research-only daily bar/RV overlay for the live forecast universe.

    python research/forecast_coverage.py

Fetches public Coinbase daily candles, computes trailing features, and writes
`research/forecast_overlay.duckdb` (gitignored). It does not modify the
substrate, forecast, paper books, ledger or any order path. The overlay is a
coverage probe: it answers whether a live coin has enough price history to map
to a historical state cell, and what its two-dimensional trend/vol state is.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "forecast_overlay.duckdb"
SUMMARY = ROOT / "research" / "forecast_coverage.json"
FORECAST = ROOT / "research" / "forecast.json"
UA = {"User-Agent": "espero2-forecast-coverage/0.1"}
WINDOW_DAYS = 299
COINS = ("BTC", "ETH", "SOL", "XRP", "ZEC", "NEAR", "HYPE", "PUMP", "ENA", "UNI")


def fetch_window(product: str, start: dt.date, end: dt.date) -> list[list[float]]:
    query = urllib.parse.urlencode({
        "granularity": 86400,
        "start": f"{start.isoformat()}T00:00:00Z",
        "end": f"{end.isoformat()}T00:00:00Z",
    })
    url = f"https://api.exchange.coinbase.com/products/{product}/candles?{query}"
    try:
        raw = json.loads(urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=30).read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return []
        raise
    return raw


def fetch_daily(product: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    rows: list[list[float]] = []
    cursor = start
    while cursor < end:
        stop = min(cursor + dt.timedelta(days=WINDOW_DAYS), end)
        rows.extend(fetch_window(product, cursor, stop))
        cursor = stop
        time.sleep(0.2)
    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows, columns=["ts", "low", "high", "open", "close", "volume"])
    df["date"] = pd.to_datetime(df["ts"], unit="s", utc=True).dt.tz_convert(None).dt.normalize()
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.drop(columns=["ts"]).dropna(subset=["date", "close"]).drop_duplicates("date").sort_values("date")


def features(bars: pd.DataFrame) -> pd.DataFrame:
    df = bars.copy()
    df["ret"] = np.log(df["close"]).diff()
    df["ret60"] = df["close"] / df["close"].shift(60) - 1.0
    df["rv"] = df["ret"].pow(2).rolling(20, min_periods=20).mean() * 365.0
    df["rv_w"] = df["ret"].pow(2).rolling(5, min_periods=5).mean() * 365.0
    df["rv_m"] = df["ret"].pow(2).rolling(22, min_periods=22).mean() * 365.0
    df["vol_pct"] = df["rv"].rolling(252, min_periods=60).rank(pct=True)
    df["trend"] = np.where(df["ret60"] > 0, "up", "down")
    df["vol"] = np.where(df["vol_pct"] > 0.5, "high", "low")
    df["state2"] = df["trend"] + "/" + df["vol"]
    df["known_time"] = df["date"] + pd.Timedelta(days=1)
    return df


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coins", default=",".join(COINS))
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default=dt.date.today().isoformat())
    args = ap.parse_args()
    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    coins = [c.strip().upper() for c in args.coins.split(",") if c.strip()]

    con = duckdb.connect(str(OUT))
    con.execute("CREATE OR REPLACE TABLE daily (coin VARCHAR, date DATE, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE)")
    con.execute("CREATE OR REPLACE TABLE features (coin VARCHAR, date DATE, ret60 DOUBLE, rv DOUBLE, rv_w DOUBLE, rv_m DOUBLE, vol_pct DOUBLE, trend VARCHAR, vol VARCHAR, state2 VARCHAR, known_time TIMESTAMP)")

    summary: dict[str, dict] = {}
    for coin in coins:
        product = f"{coin}-USD"
        try:
            bars = fetch_daily(product, start, end)
        except Exception as exc:
            print(f"{coin:5s} fetch error: {type(exc).__name__}: {exc}")
            summary[coin] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        if bars.empty or len(bars) < 60:
            print(f"{coin:5s} no usable history ({len(bars)} bars)")
            summary[coin] = {"bars": int(len(bars)), "first": None, "last": None, "state2": None}
            continue
        bars.insert(0, "coin", coin)
        feat = features(bars)
        con.register("bars_df", bars)
        con.register("feat_df", feat)
        con.execute("INSERT INTO daily SELECT coin, date, open, high, low, close, volume FROM bars_df")
        con.execute("INSERT INTO features SELECT coin, date, ret60, rv, rv_w, rv_m, vol_pct, trend, vol, state2, known_time FROM feat_df")
        last = feat.dropna(subset=["state2"]).tail(1)
        current = last.iloc[0] if len(last) else None
        summary[coin] = {
            "bars": int(len(bars)),
            "first": str(bars["date"].min().date()),
            "last": str(bars["date"].max().date()),
            "state2": str(current["state2"]) if current is not None else None,
            "ret60": float(current["ret60"]) if current is not None else None,
            "vol_pct": float(current["vol_pct"]) if current is not None else None,
        }
        print(f"{coin:5s} bars={len(bars):>4} {bars['date'].min().date()} -> {bars['date'].max().date()} "
              f"state2={summary[coin]['state2']}")
    con.close()

    if FORECAST.exists():
        live = json.loads(FORECAST.read_text())
        for row in live.get("rows", []):
            coin = str(row.get("coin"))
            if coin in summary:
                summary[coin]["live_state"] = row.get("state")
                summary[coin]["live_label"] = row.get("label")
    SUMMARY.write_text(json.dumps({"start": str(start), "end": str(end), "coins": summary}, indent=1))
    print(f"wrote {SUMMARY.relative_to(ROOT)} and {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
