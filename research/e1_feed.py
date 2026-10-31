"""Derive E1's events locally from the raw aggr feed + Binance 5m bars.

The maintainer's `liqbreak` job failed on the first window day, so `liqbreak_trades.csv` is empty.
This recomputes the same rule from the raw inputs we now sync:

    python research/e1_feed.py

Rule (identical to #26/#27): a 5-minute down-break = close below the prior 48-bar low, volume z >= 2
and burst < 0; forced share s = long liquidations (USD) on the break's side in the prior hour divided by
that hour's Binance quote volume; one event per coin per direction per hour, entries only after 01:00 UTC.
Writes research/e1_events.csv with prior-day tercile tags.
"""
from __future__ import annotations

import gzip
import io
import json
import pathlib
import zipfile

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "aggr" / "forward5m"
LOWS = ROOT / "data" / "lows" / "forward"
OUT = ROOT / "research" / "e1_events.csv"
STATUS = ROOT / "research" / "e1_feed_status.json"
BAR = 300
COINS = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK", "DOT", "TRX", "LTC",
         "HBAR", "SHIB"}


def coin_of(market: str) -> str | None:
    m = market.upper()
    for prefix in ("BINANCE_FUTURES:", "BYBIT:", "OKEX:"):
        if m.startswith(prefix):
            m = m[len(prefix):]
    m = m.replace("-USDT-SWAP", "").replace("USDT", "").replace("-USD", "").replace("_PERP", "")
    m = m.replace("1000", "")
    return m if m in COINS else None


def liquidations(day: str) -> pd.DataFrame:
    path = FEED / f"{day}.csv.gz"
    if not path.exists():
        return pd.DataFrame()
    with gzip.open(path, "rt") as f:
        df = pd.read_csv(f)
    df["coin"] = df["market"].map(coin_of)
    df = df.dropna(subset=["coin"])
    g = df.groupby(["coin", "time"])[["lbuy", "lsell"]].sum()
    return g.reset_index()


def bars(coin: str, day: str) -> pd.DataFrame | None:
    sym = "1000SHIBUSDT" if coin == "SHIB" else f"{coin}USDT"
    frames = []
    for d in (pd.Timestamp(day) - pd.Timedelta(days=1), pd.Timestamp(day)):
        p = LOWS / sym / f"{d.date()}.zip"
        if not p.exists():
            continue
        try:
            with zipfile.ZipFile(p) as z:
                raw = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=None)
        except Exception:
            continue
        if str(raw.iloc[0, 0]) == "open_time":
            raw = raw.iloc[1:]
        raw.columns = ["ts", "open", "high", "low", "close", "vol", "ct", "qvol", "n", "tb", "tbq", "ig"][: raw.shape[1]]
        for c in ("ts", "open", "high", "low", "close", "vol", "qvol"):
            raw[c] = pd.to_numeric(raw[c], errors="coerce")
        frames.append(raw[["ts", "open", "high", "low", "close", "vol", "qvol"]])
    if not frames:
        return None
    b = pd.concat(frames, ignore_index=True).dropna(subset=["ts", "close"]).sort_values("ts")
    b = b.drop_duplicates("ts")
    return b.set_index((b["ts"] // 1000).astype("int64") // BAR * BAR)


def events_for(coin: str, day: str, liq: pd.DataFrame) -> list[dict]:
    b = bars(coin, day)
    if b is None or len(b) < 60:
        return []
    close, high, low, vol = b["close"], b["high"], b["low"], b["vol"]
    burst = np.log(close / close.shift(12))
    x = np.log(vol + 1.0)
    vol_z = (x - x.rolling(48).mean()) / x.rolling(48).std()
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    prior_low = low.shift(1).rolling(48).min()
    down = (close < prior_low) & prior_low.notna() & (vol_z >= 2) & (atr > 0) & (burst < 0)
    day_start = int(pd.Timestamp(day).timestamp())
    liq = liq[liq["coin"] == coin]
    idx = {int(t): i for i, t in enumerate(b.index)}
    rows, last = [], {}
    for i, t in enumerate(b.index):
        if not down.iloc[i]:
            continue
        close_t = int(t) + BAR
        if not (day_start + 3600 <= close_t <= day_start + 86400):
            continue
        if -1 in last and int(t) - last[-1] <= 3600:
            continue
        last[-1] = int(t)
        window = liq[(liq["time"] >= int(t) - 3300) & (liq["time"] < close_t)]
        forced = float(window["lsell"].sum()) if len(window) else float("nan")
        j = [idx.get(int(t) - k * BAR) for k in range(12)]
        if any(x is None for x in j):
            continue
        qvol = float(b["qvol"].iloc[j].sum())
        if qvol <= 0 or not np.isfinite(forced):
            continue
        rows.append({"day": day, "coin": coin, "ts": close_t, "direction": -1,
                     "s": forced / qvol})
    return rows


def tag(rows: list[dict]) -> list[dict]:
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    df = df.sort_values(["day", "ts"])
    q = df.groupby("day")["s"].apply(lambda x: (x.quantile(1 / 3), x.quantile(2 / 3))).to_dict()
    order = sorted(q)
    prev = {order[i]: q[order[i - 1]] for i in range(1, len(order))}
    tags = []
    for _, r in df.iterrows():
        bounds = prev.get(r["day"])
        if bounds is None:
            tags.append("middle")
        else:
            lo, hi = bounds
            tags.append("forced" if r["s"] > hi else ("organic" if r["s"] <= lo else "middle"))
    df["tag"] = tags
    return df.to_dict("records")


def main() -> int:
    days = sorted(p.name.replace(".csv.gz", "") for p in FEED.glob("*.csv.gz"))
    all_rows = []
    for day in days:
        liq = liquidations(day)
        if liq.empty:
            continue
        for coin in sorted(liq["coin"].unique()):
            all_rows += events_for(coin, day, liq)
    tagged = tag(all_rows)
    if tagged:
        pd.DataFrame(tagged).to_csv(OUT, index=False)
    forced = sum(1 for r in tagged if r.get("tag") == "forced")
    STATUS.write_text(json.dumps({"days": days, "events": len(tagged), "forced": forced,
                                  "organic": sum(1 for r in tagged if r.get("tag") == "organic")},
                                 indent=1))
    print(f"days {days}: {len(tagged)} down-break events, {forced} tagged forced (prior-day)")
    if tagged:
        print(pd.DataFrame(tagged).head(6).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
