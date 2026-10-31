"""Tardis.dev free monthly samples (first day of each month, no API key) -> substrate.

    python research/tardis_fetch.py --symbols SOLUSDT --from 2025-01 --to 2026-10
    python research/tardis_fetch.py --symbols SOLUSDT --book 2026-10-01

derivative_ticker carries funding rate, predicted funding, open interest, mark and index price.
liquidations is Binance forceOrder. book_ticker (with amounts) is optional because it is ~96 MB/day.
"""
from __future__ import annotations

import argparse
import gzip
import io
import pathlib
import urllib.request

import duckdb
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
CACHE = ROOT / "data_tardis"
BASE = "https://datasets.tardis.dev/v1/binance-futures"
UA = {"User-Agent": "espero2/0.1"}


def sample(channel: str, day: str, symbol: str) -> pd.DataFrame | None:
    y, m, d = day.split("-")
    dest = CACHE / channel / f"{symbol}-{day}.csv.gz"
    if not dest.exists():
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(f"{BASE}/{channel}/{y}/{m}/{d}/{symbol}.csv.gz", headers=UA)
            dest.write_bytes(urllib.request.urlopen(req, timeout=300).read())
        except Exception:
            return None
    try:
        return pd.read_csv(gzip.open(dest))
    except Exception:
        return None


def months(start: str, end: str) -> list[str]:
    return [str(p) + "-01" for p in pd.period_range(start, end, freq="M")]


def ingest_derivative(frames: list[pd.DataFrame]) -> int:
    if not frames:
        return 0
    d = pd.concat(frames, ignore_index=True)
    d["ts"] = pd.to_datetime(d["timestamp"], unit="us")
    d = d.rename(columns={"funding_rate": "funding", "predicted_funding_rate": "predicted",
                          "open_interest": "oi", "mark_price": "mark", "index_price": "index"})
    d = d[["symbol", "ts", "funding", "predicted", "oi", "mark", "index"]].drop_duplicates(["symbol", "ts"])
    con = duckdb.connect(str(DB))
    con.execute("""CREATE TABLE IF NOT EXISTS tardis_derivative(symbol VARCHAR, ts TIMESTAMP,
        funding DOUBLE, predicted DOUBLE, oi DOUBLE, mark DOUBLE, index DOUBLE,
        PRIMARY KEY (symbol, ts))""")
    con.register("d", d)
    con.execute("INSERT OR IGNORE INTO tardis_derivative SELECT symbol, ts, funding, predicted, oi, mark, index FROM d")
    con.unregister("d")
    con.close()
    return len(d)


def ingest_liquidations(frames: list[pd.DataFrame]) -> int:
    if not frames:
        return 0
    d = pd.concat(frames, ignore_index=True)
    d["ts"] = pd.to_datetime(d["timestamp"], unit="us")
    d["usd"] = d["price"] * d["amount"]
    d = d[["symbol", "ts", "side", "price", "amount", "usd"]].drop_duplicates(["symbol", "ts", "side", "price", "amount"])
    con = duckdb.connect(str(DB))
    con.execute("""CREATE TABLE IF NOT EXISTS tardis_liquidations(symbol VARCHAR, ts TIMESTAMP,
        side VARCHAR, price DOUBLE, amount DOUBLE, usd DOUBLE,
        PRIMARY KEY (symbol, ts, side, price, amount))""")
    con.register("d", d)
    con.execute("INSERT OR IGNORE INTO tardis_liquidations SELECT symbol, ts, side, price, amount, usd FROM d")
    con.unregister("d")
    con.close()
    return len(d)


def ingest_book(day: str, symbol: str) -> int:
    d = sample("book_ticker", day, symbol)
    if d is None or d.empty:
        return 0
    d["minute"] = pd.to_datetime(d["timestamp"], unit="us").dt.floor("min")
    last = d.sort_values("timestamp").groupby("minute").tail(1)
    mid = (last["bid_price"] + last["ask_price"]) / 2
    out = pd.DataFrame({"symbol": symbol, "minute": last["minute"].to_numpy(),
                        "bid": last["bid_price"].to_numpy(), "ask": last["ask_price"].to_numpy(),
                        "bid_amt": last["bid_amount"].to_numpy(), "ask_amt": last["ask_amount"].to_numpy(),
                        "obi": ((last["bid_amount"] - last["ask_amount"]) /
                                (last["bid_amount"] + last["ask_amount"]).replace(0, pd.NA)).to_numpy()})
    out["spread_bps"] = (1e4 * (out["ask"] - out["bid"]) / mid.to_numpy()).round(3)
    con = duckdb.connect(str(DB))
    con.execute("""CREATE TABLE IF NOT EXISTS tardis_book(symbol VARCHAR, minute TIMESTAMP, bid DOUBLE,
        ask DOUBLE, bid_amt DOUBLE, ask_amt DOUBLE, obi DOUBLE, spread_bps DOUBLE,
        PRIMARY KEY (symbol, minute))""")
    con.register("d", out)
    con.execute("INSERT OR IGNORE INTO tardis_book SELECT symbol, minute, bid, ask, bid_amt, ask_amt, obi, spread_bps FROM d")
    con.unregister("d")
    con.close()
    return len(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="SOLUSDT")
    ap.add_argument("--from", dest="start", default="2025-01")
    ap.add_argument("--to", dest="end", default="2026-10")
    ap.add_argument("--book", default=None, help="single day to sample book_ticker, e.g. 2026-10-01")
    args = ap.parse_args(argv)
    days = months(args.start, args.end)
    der, liq = [], []
    for sym in args.symbols.split(","):
        for day in days:
            dd = sample("derivative_ticker", day, sym)
            if dd is not None:
                der.append(dd)
            dl = sample("liquidations", day, sym)
            if dl is not None and not dl.empty:
                liq.append(dl)
    n_der = ingest_derivative(der)
    n_liq = ingest_liquidations(liq)
    print(f"derivative rows {n_der} · liquidation rows {n_liq} · days sampled {len(days)}")
    if args.book:
        for sym in args.symbols.split(","):
            print(f"book {args.book} {sym}: {ingest_book(args.book, sym)} minutes")
    con = duckdb.connect(str(DB), read_only=True)
    print(con.execute("""SELECT symbol, COUNT(*), MIN(ts)::DATE, MAX(ts)::DATE,
                                AVG(oi) FROM tardis_derivative GROUP BY symbol""").df().to_string(index=False))
    print(con.execute("""SELECT symbol, COUNT(*), MIN(ts)::DATE, MAX(ts)::DATE,
                                SUM(CASE WHEN side='sell' THEN usd ELSE 0 END) AS long_usd,
                                SUM(CASE WHEN side='buy' THEN usd ELSE 0 END) AS short_usd
                         FROM tardis_liquidations GROUP BY symbol""").df().to_string(index=False))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
