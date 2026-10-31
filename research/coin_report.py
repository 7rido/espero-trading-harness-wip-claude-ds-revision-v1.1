"""Per-coin research snapshot from the substrate: coverage, price, vol, funding, liquidations and
what happens after that coin's liquidation spikes. Descriptive; no signal, no order path.

    python research/coin_report.py --coin SOL
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import pathlib
import sys

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
LIQ2 = ROOT / "data_raw" / "liq2"
CONTRACT = {"BTC": 100.0}


def load_coin(coin: str):
    con = duckdb.connect(str(DB), read_only=True)
    bars = con.execute("SELECT date, close, qvol FROM bars_daily WHERE symbol=? ORDER BY date",
                       [f"{coin}USDT"]).df()
    rv = con.execute("SELECT date, rv FROM rv WHERE symbol=? ORDER BY date", [f"{coin}USDT"]).df()
    fund = con.execute("SELECT CAST(ts AS DATE) AS date, rate FROM funding WHERE symbol=?",
                       [f"{coin}USDT"]).df()
    con.close()
    for d in (bars, rv, fund):
        if "date" in d:
            d["date"] = pd.to_datetime(d["date"])
    return bars, rv, fund


def liquidation_stats(coin: str) -> dict:
    folder = LIQ2 / f"{coin}USD_PERP"
    if not folder.exists():
        return {"available": False}
    rows = []
    for path in sorted(folder.glob("*.csv.gz")):
        try:
            df = pd.read_csv(gzip.open(path), header=0)
        except Exception:
            continue
        if df.empty:
            continue
        ts = pd.to_numeric(df["time"], errors="coerce") // 1000
        side = df["side"].map({"SELL": "sell", "BUY": "buy"})
        usd = pd.to_numeric(df["last_fill_quantity"], errors="coerce") * CONTRACT.get(coin, 10.0)
        rows.append(pd.DataFrame({"hour": (ts // 3600).astype("int64"), "side": side, "usd": usd}))
    if not rows:
        return {"available": False}
    d = pd.concat(rows, ignore_index=True)
    hourly = d.groupby(["hour", "side"])["usd"].sum().unstack(fill_value=0.0)
    return {"available": True, "events": int(len(d)), "total_usd": float(d["usd"].sum()),
            "hours_with_long_liq": int((hourly.get("sell", 0) > 0).sum()),
            "max_hour_usd": float(hourly.sum(axis=1).max())}


def spike_outcomes(coin: str, q: float = 0.99) -> dict:
    """Next-hour return after the coin's own top-1% long-liquidation hours (2023-2024)."""
    spec = importlib.util.spec_from_file_location("anatomy", ROOT / "research" / "liquidation_anatomy.py")
    anatomy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(anatomy)
    if coin not in anatomy.COINS:
        return {"available": False}
    bars = anatomy.hourly_bars(coin)
    liq = anatomy.hourly_liq(coin)
    if bars is None or liq.empty:
        return {"available": False}
    d = bars.join(liq, how="inner")
    d.index = pd.to_datetime(d.index, unit="s")
    d = d.loc["2023-01-01":"2024-11-01"]
    if len(d) < 500:
        return {"available": False}
    d["fwd1"] = d["close"].shift(-1) / d["close"] - 1
    thr = d["long_liq"].quantile(q)
    ev = d[d["long_liq"] > thr].dropna(subset=["fwd1"])
    if ev.empty:
        return {"available": False}
    return {"available": True, "events": int(len(ev)),
            "mean_bps": 1e4 * float(ev["fwd1"].mean()),
            "median_bps": 1e4 * float(ev["fwd1"].median()),
            "share_up": float((ev["fwd1"] > 0).mean()),
            "p10_bps": 1e4 * float(ev["fwd1"].quantile(0.1)),
            "p90_bps": 1e4 * float(ev["fwd1"].quantile(0.9))}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", required=True)
    args = ap.parse_args(argv)
    coin = args.coin.upper()
    bars, rv, fund = load_coin(coin)
    if bars.empty:
        print(f"{coin}: no daily bars in the substrate")
        return 1
    bars = bars.dropna().set_index("date")
    ret = bars["close"].pct_change().dropna()
    ann_vol = float(ret.std() * np.sqrt(365))
    f = fund.dropna()
    liq = liquidation_stats(coin)
    spikes = spike_outcomes(coin)

    print(f"# {coin} — research snapshot\n")
    print(f"data        {bars.index.min().date()} → {bars.index.max().date()} · {len(bars)} days "
          f"· last close {bars['close'].iloc[-1]:,.2f}")
    if len(ret) > 90:
        print(f"returns     30d {1e2*(bars['close'].iloc[-1]/bars['close'].iloc[-31]-1):+.1f}% · "
              f"90d {1e2*(bars['close'].iloc[-1]/bars['close'].iloc[-91]-1):+.1f}% · "
              f"annualised vol {1e2*ann_vol:.0f}%")
    if not rv.empty:
        print(f"realised vol median {1e4*float(rv['rv'].median()):.1f} bp²/day "
              f"({len(rv)} days with 5m data)")
    if not f.empty:
        print(f"funding     mean {1e4*float(f['rate'].mean()):+.3f} bp/8h · "
              f"positive on {1e2*float((f['rate'] > 0).mean()):.0f}% of intervals · "
              f"top decile {1e4*float(f['rate'].quantile(0.9)):+.2f} bp")
    if liq.get("available"):
        print(f"liq (COIN-M) {liq['events']:,} fills · ${liq['total_usd']/1e6:,.1f}M total · "
              f"max hour ${liq['max_hour_usd']/1e6:,.1f}M · {liq['hours_with_long_liq']:,} hours with a long liq")
    else:
        print("liq (COIN-M) no COIN-M liquidation archive for this coin")
    if spikes.get("available"):
        print(f"after top-1% long-liq hours ({spikes['events']} events, 2023–24):")
        print(f"            next 1h mean {spikes['mean_bps']:+.1f} bp · median {spikes['median_bps']:+.1f} bp "
              f"· up {spikes['share_up']:.0%} · p10 {spikes['p10_bps']:+.0f} / p90 {spikes['p90_bps']:+.0f}")
    print("\nDescriptive only. No ledger row, no signal, no position. The paper loop trades the SMA rule, "
          "not this table.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
