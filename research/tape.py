"""BTC tape: aggressor flow, CVD, blocks, sweeps, volume profile, absorption and divergence.

    python research/tape.py --day 2026-10-29 --symbol BTCUSDT     # Binance UM daily aggTrades
    python research/tape.py --live                                # Coinbase last 30 minutes

Descriptive only: tape reading explains flow, it does not predict direction, and nothing here reaches
the ledger or an order path. Binance aggTrades encode the aggressor as `is_buyer_maker == False`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import io
import json
import pathlib
import sys
import urllib.request
import zipfile

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "data_tape"
OUT = ROOT / "research" / "tape.json"
LIVE_OUT = ROOT / "research" / "tape_live.json"
SERIES = ROOT / "research" / "tape_series.csv.gz"
BINANCE = "https://data.binance.vision/data/futures/um/daily/aggTrades"
UA = {"User-Agent": "espero2/0.1"}
BLOCK_USD = 100_000.0
COINBASE = "https://api.exchange.coinbase.com"


def fetch_binance(day: str, symbol: str) -> pd.DataFrame:
    dest = CACHE / f"{symbol}-{day}.zip"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"{BINANCE}/{symbol}/{symbol}-aggTrades-{day}.zip"
        req = urllib.request.Request(url, headers=UA)
        dest.write_bytes(urllib.request.urlopen(req, timeout=180).read())
    with zipfile.ZipFile(dest) as z:
        raw = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])))
    raw = raw.rename(columns={"transact_time": "ts_ms", "is_buyer_maker": "buyer_maker"})
    raw["ts"] = pd.to_datetime(raw["ts_ms"], unit="ms")
    raw["buyer_maker"] = raw["buyer_maker"].astype(bool)
    return raw[["ts", "price", "quantity", "buyer_maker"]]


def minute_table(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["minute"] = d["ts"].dt.floor("min")
    d["notional"] = d["price"] * d["quantity"]
    d["taker_buy"] = ~d["buyer_maker"]
    g = d.groupby("minute")
    out = pd.DataFrame({
        "open": g["price"].first(), "high": g["price"].max(), "low": g["price"].min(),
        "close": g["price"].last(), "prints": g["price"].size(),
        "qty": g["quantity"].sum(), "notional": g["notional"].sum()})
    out["buy_qty"] = d[d["taker_buy"]].groupby("minute")["quantity"].sum()
    out["sell_qty"] = d[~d["taker_buy"]].groupby("minute")["quantity"].sum()
    out = out.fillna({"buy_qty": 0.0, "sell_qty": 0.0})
    out["cvd"] = (out["buy_qty"] - out["sell_qty"]).cumsum()
    out["buy_share"] = out["buy_qty"] / (out["buy_qty"] + out["sell_qty"]).replace(0, np.nan)
    out["vwap"] = out["notional"] / out["qty"].replace(0, np.nan)
    out["ret_bp"] = 1e4 * (out["close"] / out["open"] - 1)
    out["vol_z"] = (out["qty"] - out["qty"].rolling(60, min_periods=10).mean()) / \
                   out["qty"].rolling(60, min_periods=10).std()
    return out.reset_index()


def profile(df: pd.DataFrame, bucket_pct: float = 0.001) -> dict:
    vwap = float((df["price"] * df["quantity"]).sum() / df["quantity"].sum())
    width = vwap * bucket_pct
    idx = np.floor(df["price"].to_numpy() / width).astype(np.int64)
    vol = df.groupby(idx)["quantity"].sum().sort_index()
    if vol.empty:
        return {}
    poc_i = int(vol.idxmax())
    poc = (poc_i + 0.5) * width
    total = float(vol.sum())
    order = list(vol.index)
    pos = order.index(poc_i)
    lo = hi = pos
    acc = float(vol.loc[poc_i])
    while acc < 0.70 * total and (lo > 0 or hi < len(order) - 1):
        left = float(vol.loc[order[lo - 1]]) if lo > 0 else -1.0
        right = float(vol.loc[order[hi + 1]]) if hi < len(order) - 1 else -1.0
        if right >= left:
            hi += 1
            acc += right
        else:
            lo -= 1
            acc += left
    va_lo = order[lo] * width
    va_hi = (order[hi] + 1) * width
    hvn = [float((int(i) + 0.5) * width) for i in vol.nlargest(3).index]
    close = float(df["price"].iloc[-1])
    return {"poc": poc, "va70": [va_lo, va_hi], "hvn": hvn,
            "poc_distance_pct": 100 * (close / poc - 1) if poc else float("nan")}


def block_stats(df: pd.DataFrame, block_usd: float) -> dict:
    notional = df["price"] * df["quantity"]
    blocks = df[notional >= block_usd]
    return {"count": int(len(blocks)), "usd": float(notional[notional >= block_usd].sum())}


def sweep_stats(df: pd.DataFrame) -> dict:
    agg = df.groupby(["ts", "price"])["quantity"].agg(["size", "sum"])
    sweeps = agg[agg["size"] >= 3]
    return {"count": int(len(sweeps)), "usd": float(sweeps["sum"].sum())}


def absorption(minute: pd.DataFrame) -> dict:
    z = minute["vol_z"].dropna()
    r = minute["ret_bp"].abs().dropna()
    if z.empty or r.empty:
        return {"share": float("nan"), "return_bp": float("nan"), "baseline_bp": float("nan")}
    active = minute[(minute["vol_z"] >= 2) & minute["ret_bp"].notna()]
    if active.empty:
        return {"share": 0.0, "return_bp": float("nan"), "baseline_bp": float(r.median())}
    calm = active[active["ret_bp"].abs() < float(r.median())]
    return {"share": float(len(calm) / len(active)), "return_bp": float(calm["ret_bp"].abs().median())
            if len(calm) else float("nan"), "baseline_bp": float(r.median())}


def divergence(minute: pd.DataFrame, window: int = 60) -> str:
    tail = minute.tail(window)
    if len(tail) < 20:
        return "none"
    half = len(tail) // 2
    a, b = tail.iloc[:half], tail.iloc[half:]
    price_lower = b["low"].min() < a["low"].min()
    price_higher = b["high"].max() > a["high"].max()
    cvd_lower = b["cvd"].iloc[-1] < a["cvd"].iloc[-1]
    cvd_higher = b["cvd"].iloc[-1] > a["cvd"].iloc[-1]
    if price_lower and cvd_higher:
        return "bullish"
    if price_higher and cvd_lower:
        return "bearish"
    return "none"


def summarise(df: pd.DataFrame, source: str, symbol: str, day: str, block_usd: float,
              side_verified: bool = True) -> dict:
    m = minute_table(df)
    prof = profile(df)
    bs = block_stats(df, block_usd)
    sw = sweep_stats(df)
    ab = absorption(m)
    div = divergence(m)
    buy_share = float(df.loc[~df["buyer_maker"], "quantity"].sum() /
                       max(df["quantity"].sum(), 1e-12))
    cvd = float((df.loc[~df["buyer_maker"], "quantity"].sum() -
                 df.loc[df["buyer_maker"], "quantity"].sum()))
    read = (f"taker buys {buy_share:.0%} of volume, CVD {cvd:+.1f} {symbol[:-4]}; "
            f"{bs['count']} blocks (${bs['usd']/1e6:,.1f}M), {sw['count']} sweeps; "
            f"price {prof.get('poc_distance_pct', float('nan')):+.2f}% from POC; "
            f"absorption {ab['share']:.0%} of high-volume minutes; divergence {div}.")
    return {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "source": source, "symbol": symbol, "day": day, "side_verified": side_verified,
            "prints": int(len(df)), "buy_share": buy_share, "cvd": cvd,
            "blocks": bs, "sweeps": sw, "profile": prof, "absorption": ab,
            "divergence": div, "read": read}


def write_series(m: pd.DataFrame) -> None:
    m.to_csv(SERIES, index=False, compression="gzip")


def _get(url: str):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())


def live() -> int:
    try:
        trades = _get(f"{COINBASE}/products/BTC-USD/trades?limit=1000")
    except Exception as exc:                        # noqa: BLE001
        print(f"live tape unavailable: {exc}", file=sys.stderr)
        return 2
    df = pd.DataFrame(trades)
    df["ts"] = pd.to_datetime(df["time"])
    df["price"] = df["price"].astype(float)
    df["quantity"] = df["size"].astype(float)
    df["buyer_maker"] = df["side"].str.lower() == "sell"   # a sell-side print was a taker sell
    cutoff = df["ts"].max() - pd.Timedelta(minutes=30)
    df = df[df["ts"] >= cutoff]
    if len(df) < 50:
        print(f"live tape too thin: {len(df)} prints", file=sys.stderr)
        return 2
    # Side semantics: a taker buy should print at or above the previous print more often than not.
    # This is a time-independent sign test (the current book may have moved away from old prints).
    s = df.sort_values("ts").reset_index(drop=True)
    agree = int(sum(1 for i in range(1, len(s))
                    if (s.loc[i, "side"].lower() == "buy" and s.loc[i, "price"] >= s.loc[i-1, "price"])
                    or (s.loc[i, "side"].lower() == "sell" and s.loc[i, "price"] <= s.loc[i-1, "price"])))
    rate = agree / max(len(s) - 1, 1)
    verified = rate >= 0.55
    out = summarise(df, "coinbase-spot", "BTCUSD", df["ts"].max().strftime("%Y-%m-%d"),
                    BLOCK_USD, side_verified=verified)
    out["side_agreement"] = round(rate, 3)
    LIVE_OUT.write_text(json.dumps(out, indent=1))
    try:
        shown = LIVE_OUT.relative_to(ROOT)
    except ValueError:
        shown = LIVE_OUT
    print(f"wrote {shown} · {out['prints']} prints · side verified {verified}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=(dt.datetime.now(dt.timezone.utc).date() -
                                      dt.timedelta(days=1)).isoformat())
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--block-usd", type=float, default=BLOCK_USD)
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args(argv)
    if args.live:
        return live()
    try:
        df = fetch_binance(args.day, args.symbol)
    except Exception as exc:                        # noqa: BLE001
        print(f"no tape for {args.symbol} {args.day}: {exc}", file=sys.stderr)
        return 3
    if df.empty:
        print("empty tape", file=sys.stderr)
        return 3
    out = summarise(df, "binance-um", args.symbol, args.day, args.block_usd)
    OUT.write_text(json.dumps(out, indent=1))
    write_series(minute_table(df))
    print(f"wrote {OUT.relative_to(ROOT)} · {out['prints']:,} prints · {out['read']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
