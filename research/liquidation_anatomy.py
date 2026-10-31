"""Liquidation anatomy: what does a liquidation actually do to price, conditioned on the shape of
the hours before it?

Descriptive statistics, not a strategy. For every hourly liquidation spike we record the shape of the
preceding hours (1h/2h/4h direction, consecutive bearish candles) and the return over the following
1/2/4/24 hours, then report the conditional distribution with day-clustered bootstrap intervals.

    python research/liquidation_anatomy.py
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
LOWS = ROOT / "data_raw" / "lows"
LIQ2 = ROOT / "data_raw" / "liq2"
OUT = ROOT / "research" / "liquidation_anatomy.json"
CONTRACT = {"BTC": 100.0}
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK", "LTC"]
START, END = "2023-01-01", "2024-11-01"
Q = 0.99


def hourly_bars(coin: str) -> pd.DataFrame | None:
    sym = f"{coin}USDT"
    frames = []
    for z in sorted(LOWS.glob(f"{sym}/2023-*.zip")) + sorted(LOWS.glob(f"{sym}/2024-*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                df = pd.read_csv(io.BytesIO(zf.read(zf.namelist()[0])), header=None)
        except (zipfile.BadZipFile, IndexError, OSError):
            continue
        if df.empty:
            continue
        if str(df.iloc[0, 0]) == "open_time":
            df = df.iloc[1:]
        df.columns = ["ts", "open", "high", "low", "close", "vol", "ct", "qvol", "n", "tb", "tbq", "ig"][: df.shape[1]]
        frames.append(df[["ts", "open", "high", "low", "close", "vol", "qvol"]])
    if not frames:
        return None
    d = pd.concat(frames, ignore_index=True)
    for c in ("ts", "open", "high", "low", "close", "vol", "qvol"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["ts", "close"])
    d["hour"] = (d["ts"] // 1000 // 3600) * 3600
    g = d.groupby("hour")
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                        "close": g["close"].last(), "vol": g["vol"].sum(), "qvol": g["qvol"].sum()})
    return out


def hourly_liq(coin: str) -> pd.DataFrame:
    rows = []
    for path in sorted((LIQ2 / f"{coin}USD_PERP").glob("*.csv.gz")):
        try:
            df = pd.read_csv(gzip.open(path), header=0)
        except Exception:
            continue
        if df.empty:
            continue
        ts = pd.to_numeric(df["time"], errors="coerce") // 1000
        side = df["side"].map({"SELL": "sell", "BUY": "buy"})
        usd = pd.to_numeric(df["last_fill_quantity"], errors="coerce") * CONTRACT.get(coin, 10.0)
        rows.append(pd.DataFrame({"hour": (ts // 3600).astype("int64") * 3600, "side": side, "usd": usd}))
    if not rows:
        return pd.DataFrame(columns=["hour", "long_liq", "short_liq"])
    d = pd.concat(rows, ignore_index=True)
    long_liq = d[d["side"] == "sell"].groupby("hour")["usd"].sum()
    short_liq = d[d["side"] == "buy"].groupby("hour")["usd"].sum()
    return pd.DataFrame({"long_liq": long_liq, "short_liq": short_liq}).fillna(0.0)


def bootstrap_mean(values: pd.Series, days: pd.Series, reps: int = 2000, seed: int = 7) -> tuple[float, float]:
    v = pd.DataFrame({"v": values.to_numpy(), "d": days.to_numpy()})
    if len(v) < 10:
        return float("nan"), float("nan")
    g = v.groupby("d")["v"].agg(["sum", "count"])
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(reps):
        idx = rng.integers(0, len(g), len(g))
        sel = g.iloc[idx]
        means.append(sel["sum"].sum() / sel["count"].sum())
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def build() -> pd.DataFrame:
    rows = []
    for coin in COINS:
        bars = hourly_bars(coin)
        liq = hourly_liq(coin)
        if bars is None or liq.empty:
            continue
        d = bars.join(liq, how="inner")
        d.index = pd.to_datetime(d.index, unit="s")
        d = d.loc[START:END]
        if len(d) < 500:
            continue
        d["ret1"] = d["close"] / d["close"].shift(1) - 1
        d["ret2"] = d["close"] / d["close"].shift(2) - 1
        d["ret4"] = d["close"] / d["close"].shift(4) - 1
        d["down_run"] = 0
        run = 0
        for i, r in enumerate(d["ret1"].to_numpy()):
            run = run + 1 if (np.isfinite(r) and r < 0) else 0
            d.iloc[i, d.columns.get_loc("down_run")] = min(run, 6)
        for h in (1, 2, 4, 24):
            d[f"fwd{h}"] = d["close"].shift(-h) / d["close"] - 1
        d["coin"] = coin
        d["day"] = d.index.normalize()
        rows.append(d)
    return pd.concat(rows).reset_index(names="ts")


def patterns(df: pd.DataFrame, side: str) -> pd.DataFrame:
    ev = df.copy()
    thr = ev.groupby("coin")[f"{side}_liq"].quantile(Q)
    ev = ev[ev[f"{side}_liq"] > ev["coin"].map(thr)]
    ev = ev.dropna(subset=["ret1", "ret2", "ret4", "fwd1", "fwd4", "fwd24"])
    ev["d1"] = ev["ret1"] < 0
    ev["d2"] = ev["ret2"] < 0
    ev["d4"] = ev["ret4"] < 0
    ev["bear_run"] = ev["down_run"].clip(upper=4).astype(int)
    return ev


def summarise(ev: pd.DataFrame, label: str) -> list[dict]:
    out = []
    for name, mask in (
        ("aligned_bear (1h,2h,4h down)", ev["d1"] & ev["d2"] & ev["d4"]),
        ("1h down only", ev["d1"] & ~ev["d2"] & ~ev["d4"]),
        ("mixed", (ev["d1"].astype(int) + ev["d2"].astype(int) + ev["d4"].astype(int)).isin([1, 2])),
        ("aligned_bull (1h,2h,4h up)", ~ev["d1"] & ~ev["d2"] & ~ev["d4"]),
    ):
        sel = ev[mask]
        for h in (1, 4, 24):
            v = sel[f"fwd{h}"]
            lo, hi = bootstrap_mean(v, sel["day"])
            out.append({"side": label, "pattern": name, "horizon_h": h, "n": int(len(sel)),
                        "mean_bps": 1e4 * float(v.mean()) if len(v) else float("nan"),
                        "median_bps": 1e4 * float(v.median()) if len(v) else float("nan"),
                        "share_up": float((v > 0).mean()) if len(v) else float("nan"),
                        "ci_lo_bps": 1e4 * lo, "ci_hi_bps": 1e4 * hi})
    # consecutive down candles after a long-liquidation spike
    for k in (1, 2, 3, 4):
        sel = ev[ev["bear_run"] == k]
        v = sel["fwd1"]
        lo, hi = bootstrap_mean(v, sel["day"])
        out.append({"side": label, "pattern": f"{k} consecutive down hours", "horizon_h": 1,
                    "n": int(len(sel)), "mean_bps": 1e4 * float(v.mean()) if len(v) else float("nan"),
                    "median_bps": 1e4 * float(v.median()) if len(v) else float("nan"),
                    "share_up": float((v > 0).mean()) if len(v) else float("nan"),
                    "ci_lo_bps": 1e4 * lo, "ci_hi_bps": 1e4 * hi})
    return out


def main() -> int:
    df = build()
    long_ev = patterns(df, "long")
    short_ev = patterns(df, "short")
    rows = summarise(long_ev, "long liquidations") + summarise(short_ev, "short liquidations")
    OUT.write_text(json.dumps({"events": {"long": len(long_ev), "short": len(short_ev)},
                               "table": rows}, indent=1))
    for side in ("long liquidations", "short liquidations"):
        print(f"\n{side}:")
        for r in [x for x in rows if x["side"] == side]:
            print(f"  {r['pattern']:30s} {r['horizon_h']:>2}h  n {r['n']:>5}  "
                  f"mean {r['mean_bps']:+7.1f} bps  med {r['median_bps']:+7.1f}  "
                  f"up {r['share_up']:.0%}  CI {r['ci_lo_bps']:+.1f}..{r['ci_hi_bps']:+.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
