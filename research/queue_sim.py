"""Queue-aware execution: bookTicker + aggTrades for one day, maker fills and taker spread.

    python research/queue_sim.py fetch     # ~200 MB of bookTicker and trades samples
    python research/queue_sim.py run       # spread, fill probability, markouts, DuckDB ingest

Symbols are the depth-covered ones except BTC and ETH (their daily bookTicker exceeds 100 MB).
"""
from __future__ import annotations

import io
import json
import pathlib
import sys
import urllib.request
import zipfile

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data_exec"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
UA = {"User-Agent": "espero2-queue/1.0"}
SYMBOLS = ["ADAUSDT", "ARBUSDT", "AVAXUSDT", "BNBUSDT", "DOGEUSDT", "FILUSDT", "LINKUSDT",
           "NEARUSDT", "SOLUSDT", "SUIUSDT", "TIAUSDT", "WLDUSDT", "XRPUSDT"]
DAY = "2023-07-10"


def get(url: str, dest: pathlib.Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read()
    except Exception:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def fetch() -> None:
    for s in SYMBOLS:
        for kind, name in (("bookTicker", f"{s}-bookTicker-{DAY}.zip"),
                           ("aggTrades", f"{s}-aggTrades-{DAY}.zip")):
            url = f"{S3}/data/futures/um/daily/{kind}/{s}/{name}"
            ok = get(url, OUT / kind / name)
            print(f"{kind:11s} {s:10s} {'ok' if ok else 'missing'}")


def load(symbol: str, kind: str) -> pd.DataFrame | None:
    p = OUT / kind / f"{symbol}-{kind}-{DAY}.zip"
    if not p.exists():
        return None
    with zipfile.ZipFile(p) as z:
        df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])))
    return df


def run() -> None:
    import duckdb
    rows_spread, fills, markouts = [], [], []
    con = duckdb.connect(str(ROOT / "data_substrate" / "substrate.duckdb"))
    con.execute("""CREATE TABLE IF NOT EXISTS book_ticker(symbol VARCHAR, ts TIMESTAMP,
                    bid DOUBLE, ask DOUBLE, day DATE)""")
    con.execute("""CREATE TABLE IF NOT EXISTS trades(symbol VARCHAR, ts TIMESTAMP,
                    price DOUBLE, qty DOUBLE, buyer_is_maker BOOLEAN, day DATE)""")
    for sym in SYMBOLS:
        bt = load(sym, "bookTicker")
        tr = load(sym, "aggTrades")
        if bt is None or tr is None:
            continue
        bt.columns = ["update_id", "bid_px", "bid_qty", "ask_px", "ask_qty", "tx_time", "ev_time"]
        tr.columns = ["agg_id", "price", "qty", "first_id", "last_id", "tx_time", "buyer_maker"]
        def ts_of(v):
            v = pd.to_numeric(v, errors="coerce")
            unit = "us" if v.max() > 1e14 else ("ms" if v.max() > 1e11 else "s")
            return pd.to_datetime(v, unit=unit)
        bt["ts"] = ts_of(bt["tx_time"])
        tr["ts"] = ts_of(tr["tx_time"])
        for c in ("bid_px", "ask_px", "bid_qty", "ask_qty"):
            bt[c] = pd.to_numeric(bt[c], errors="coerce")
        tr["price"] = pd.to_numeric(tr["price"], errors="coerce")
        tr["qty"] = pd.to_numeric(tr["qty"], errors="coerce")
        mid = (bt["bid_px"] + bt["ask_px"]) / 2
        hs = ((bt["ask_px"] - bt["bid_px"]) / mid / 2).dropna()
        # effective half-spread actually paid: trade price against the last mid before it
        sample = tr.sort_values("ts").sample(n=min(2000, len(tr)), random_state=1).sort_values("ts")
        merged = pd.merge_asof(sample[["ts", "price", "buyer_maker"]],
                               bt.sort_values("ts")[["ts", "bid_px", "ask_px"]],
                               on="ts", direction="backward")
        midp = (merged["bid_px"] + merged["ask_px"]) / 2
        eff = np.where(merged["buyer_maker"], (midp - merged["price"]) / midp,
                       (merged["price"] - midp) / midp)
        rows_spread.append({"symbol": sym, "updates": int(len(bt)), "trades": int(len(tr)),
                            "median_half_spread_bps": float(1e4 * hs.median()),
                            "effective_half_spread_bps": float(1e4 * np.nanmedian(eff))})
        con.register("bt", bt[["ts", "bid_px", "ask_px"]].rename(columns={"bid_px": "bid", "ask_px": "ask"}).assign(symbol=sym, day=DAY))
        con.execute("INSERT INTO book_ticker SELECT symbol, ts, bid, ask, CAST(day AS DATE) FROM bt")
        con.register("tr", tr[["ts", "price", "qty", "buyer_maker"]].assign(symbol=sym, day=DAY))
        con.execute("INSERT INTO trades SELECT symbol, ts, price, qty, buyer_maker, CAST(day AS DATE) FROM tr")
        con.unregister("bt"); con.unregister("tr")

        # maker buy at the best bid: fills when sell-side volume at or below that bid exceeds the queue
        rng = np.random.default_rng(7)
        n_trials = 200
        idx = rng.integers(0, max(1, len(bt) - 10), n_trials)
        filled, times, mk = 0, [], []
        for i in idx:
            t0 = bt["ts"].iloc[i]
            bid = float(bt["bid_px"].iloc[i])
            queue = float(bt["bid_qty"].iloc[i])
            horizon = t0 + pd.Timedelta(seconds=60)
            sells = tr[(tr["ts"] > t0) & (tr["ts"] <= horizon) & (tr["price"] <= bid) & (~tr["buyer_maker"])]
            if sells.empty:
                continue
            cum = sells["qty"].cumsum()
            hit = sells[cum >= queue]
            if len(hit):
                filled += 1
                fill_ts = hit["ts"].iloc[0]
                times.append((fill_ts - t0).total_seconds())
                after = bt[bt["ts"] >= fill_ts].head(20)
                if len(after):
                    m = float((after["bid_px"] + after["ask_px"]).mean() / 2)
                    mk.append(1e4 * (m - bid) / bid)          # positive = adverse for a buyer
        fills.append({"symbol": sym, "trials": n_trials, "fill_rate_60s": filled / n_trials,
                      "median_fill_s": float(np.median(times)) if times else None})
        markouts.append({"symbol": sym, "median_markout_5s_bps": float(np.median(mk)) if mk else None})
    con.close()
    (ROOT / "research" / "queue_sim.json").write_text(json.dumps(
        {"day": DAY, "spreads": rows_spread, "fills": fills, "markouts": markouts}, indent=1))
    for r in rows_spread:
        print(f"{r['symbol']:10s} quoted half-spread {r['median_half_spread_bps']:.2f} bps, "
              f"effective {r['effective_half_spread_bps']:.2f} bps  ({r['updates']:,} updates, "
              f"{r['trades']:,} trades)")
    for r in fills:
        print(f"{r['symbol']:10s} maker fill within 60s: {r['fill_rate_60s']:.0%}  "
              f"median {r['median_fill_s'] if r['median_fill_s'] is None else round(r['median_fill_s'], 1)} s")


def main(argv: list[str]) -> int:
    what = argv[0] if argv else "run"
    if what == "fetch":
        fetch()
    elif what == "run":
        run()
    else:
        print("usage: fetch|run", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
