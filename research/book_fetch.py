"""bookTicker (best bid/ask with sizes) -> per-minute order-book imbalance in the substrate.

    python research/book_fetch.py --day 2024-01-02 --symbols GALAUSDT,DOGEUSDT,SUIUSDT
"""
from __future__ import annotations

import argparse
import io
import pathlib
import urllib.request
import zipfile

import duckdb
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
CACHE = ROOT / "data_book"
BASE = "https://data.binance.vision/data/futures/um/daily/bookTicker"
UA = {"User-Agent": "espero2/0.1"}
MAX_MB = 80


def fetch(symbol: str, day: str) -> pd.DataFrame | None:
    dest = CACHE / f"{symbol}-{day}.zip"
    if not dest.exists():
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(f"{BASE}/{symbol}/{symbol}-bookTicker-{day}.zip", headers=UA)
            dest.write_bytes(urllib.request.urlopen(req, timeout=300).read())
        except Exception:
            return None
    if dest.stat().st_size > MAX_MB * 1024 * 1024:
        return None                       # too large for the sample; skip, do not fail
    try:
        with zipfile.ZipFile(dest) as z:
            df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])))
    except Exception:
        return None
    df.columns = ["update_id", "bid", "bid_qty", "ask", "ask_qty", "ts", "ev"]
    for c in ("bid", "bid_qty", "ask", "ask_qty", "ts"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["bid", "ask", "ts"]).sort_values("ts")
    df["minute"] = pd.to_datetime(df["ts"], unit="ms").dt.floor("min")
    last = df.groupby("minute").tail(1)
    mid = (last["bid"] + last["ask"]) / 2
    obi = (last["bid_qty"] - last["ask_qty"]) / (last["bid_qty"] + last["ask_qty"]).replace(0, pd.NA)
    return pd.DataFrame({"symbol": symbol, "minute": last["minute"].to_numpy(),
                         "bid": last["bid"].to_numpy(), "ask": last["ask"].to_numpy(),
                         "bid_qty": last["bid_qty"].to_numpy(), "ask_qty": last["ask_qty"].to_numpy(),
                         "obi": obi.to_numpy(), "spread_bps": (1e4 * (last["ask"] - last["bid"]) / mid).to_numpy()})


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2024-01-02")
    ap.add_argument("--symbols", default="GALAUSDT,DOGEUSDT,SUIUSDT")
    args = ap.parse_args(argv)
    frames = []
    for sym in args.symbols.split(","):
        d = fetch(sym.strip(), args.day)
        if d is not None and not d.empty:
            frames.append(d)
            print(f"  {sym}: {len(d)} minutes · median OBI {d['obi'].median():+.3f} · "
                  f"median spread {d['spread_bps'].median():.2f} bps")
    if not frames:
        print("no bookTicker files fetched"); return 1
    data = pd.concat(frames, ignore_index=True)
    con = duckdb.connect(str(DB))
    con.execute("""CREATE TABLE IF NOT EXISTS obi(symbol VARCHAR, minute TIMESTAMP, bid DOUBLE,
        ask DOUBLE, bid_qty DOUBLE, ask_qty DOUBLE, obi DOUBLE, spread_bps DOUBLE,
        PRIMARY KEY (symbol, minute))""")
    con.register("d", data)
    con.execute("INSERT OR IGNORE INTO obi SELECT symbol, minute, bid, ask, bid_qty, ask_qty, obi, spread_bps FROM d")
    con.unregister("d")
    n = con.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM obi").fetchone()
    con.close()
    print(f"obi table: {n[0]} rows · {n[1]} symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
