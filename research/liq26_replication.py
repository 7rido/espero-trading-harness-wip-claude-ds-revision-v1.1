"""Replicate #26 in-sample, then measure the executable (prior-day tag) variant.

Rule, from reference/PREREGISTRATION_LIQ2.md: 5-minute breaks closing 01:00-24:00 UTC, one per coin
per direction per hour, on Binance USD-S-M bars; forced share s = COIN-M liquidations on the break's
side in the hour before / the hour's quote volume; within-day terciles of s make forced vs organic;
D(day) = forced mean - organic mean of the 1-hour return in the break's direction.

    python research/liq26_replication.py                # all coins
    python research/liq26_replication.py --coins BTC,ETH,SOL
"""
from __future__ import annotations

import argparse
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
OUT = ROOT / "research" / "liq26_run.json"

BAR = 300
WINDOW = 12
HOLD_BARS = 12
MIN_DAY = 6
CONTRACT = {"BTC": 100.0}
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK", "DOT", "TRX", "LTC",
         "BCH", "ATOM", "ETC", "XLM", "NEAR", "OP", "FIL", "RUNE", "AAVE", "EOS", "THETA", "XTZ",
         "ALGO", "WLD"]
HORIZONS = {"4h": 48, "12h": 144, "1d": 288}
COST = 0.0009


def days() -> list[int]:
    out = []
    d = pd.Timestamp("2023-06-26", tz="UTC")
    end = pd.Timestamp("2024-10-14", tz="UTC")
    while d <= end:
        if not (d.day <= 2 or d.day in (28, 29, 30, 31) and (d + pd.Timedelta(days=1)).day == 1):
            out.append(int(d.timestamp()))
        d += pd.Timedelta(days=1)
    return out


def bars(coin: str) -> pd.DataFrame:
    sym = f"{coin}USDT"
    frames = []
    for z in sorted(LOWS.glob(f"{sym}/2023-0[4-9].zip")) + sorted(LOWS.glob(f"{sym}/2023-1*.zip")) \
            + sorted(LOWS.glob(f"{sym}/2024-*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                name = zf.namelist()[0]
                frames.append(pd.read_csv(io.BytesIO(zf.read(name))))
        except (zipfile.BadZipFile, IndexError):
            continue
    if not frames:
        return pd.DataFrame()
    k = pd.concat(frames, ignore_index=True).sort_values("open_time")
    k = k.drop_duplicates("open_time")
    ts = k["open_time"].to_numpy("int64") // 1000
    out = pd.DataFrame({
        "open": k["open"].to_numpy(float), "high": k["high"].to_numpy(float),
        "low": k["low"].to_numpy(float), "close": k["close"].to_numpy(float),
        "volume": k["volume"].to_numpy(float), "quote": k["quote_volume"].to_numpy(float),
    }, index=ts // BAR * BAR).sort_index()
    return out[~out.index.duplicated()]


def features(b: pd.DataFrame) -> pd.DataFrame:
    f = b.copy()
    close, high, low, vol = f["close"], f["high"], f["low"], f["volume"]
    f["burst"] = np.log(close / close.shift(HOLD_BARS))
    x = np.log(vol + 1.0)
    f["vol_z"] = (x - x.rolling(48, min_periods=48).mean()) / x.rolling(48, min_periods=48).std()
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    f["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    prior_high = high.shift(1).rolling(48).max()
    prior_low = low.shift(1).rolling(48).min()
    ok = (f["vol_z"] >= 2.0) & (f["atr"] > 0)
    f["up"] = (close > prior_high) & prior_high.notna() & ok & (f["burst"] > 0)
    f["down"] = (close < prior_low) & prior_low.notna() & ok & (f["burst"] < 0)
    return f


def liquidations(coin: str) -> dict[int, pd.DataFrame]:
    """ts -> rows for that UTC day, deduplicated, usd already computed."""
    out = {}
    sym = f"{coin}USD_PERP"
    for path in (LIQ2 / sym).glob("*.csv.gz"):
        day = int(pd.Timestamp(path.name.replace(".csv.gz", "")).timestamp())
        rows = pd.read_csv(gzip.open(path), header=0)
        rows = rows.drop_duplicates(subset=["time", "price", "last_fill_quantity"])
        side = rows["side"].map({"SELL": "sell", "BUY": "buy"})
        out[day] = pd.DataFrame({"ts": rows["time"].to_numpy("int64") // 1000,
                                 "side": side, "usd": rows["last_fill_quantity"].to_numpy(float)
                                 * CONTRACT.get(coin, 10.0)})
    return out


def events_for(coin: str, b: pd.DataFrame, liq: dict, day_starts: list[int]) -> pd.DataFrame:
    f = features(b)
    ts = f.index.to_numpy("int64")
    at = {int(t): i for i, t in enumerate(ts)}
    up_i = np.flatnonzero(f["up"].to_numpy())
    down_i = np.flatnonzero(f["down"].to_numpy())
    rows = []
    for day_start in day_starts:
        day_liq = liq.get(day_start)
        if day_liq is None or day_liq.empty:
            continue
        lo, hi = day_start + 3600 - BAR, day_start + 86400 - BAR
        cand = [(int(ts[i]), 1, "buy") for i in up_i if lo <= ts[i] <= hi]
        cand += [(int(ts[i]), -1, "sell") for i in down_i if lo <= ts[i] <= hi]
        cand.sort()
        last: dict[int, int] = {}
        for t, d, side in cand:
            if d in last and t - last[d] <= HOLD_BARS * BAR:
                continue
            last[d] = t
            close_t = t + BAR
            start = t - (WINDOW - 1) * BAR
            m = (day_liq["ts"] >= start) & (day_liq["ts"] < close_t) & (day_liq["side"] == side)
            forced = float(day_liq.loc[m, "usd"].sum())
            idx = [at.get(t - k * BAR) for k in range(WINDOW)]
            if any(j is None for j in idx):
                continue
            vol = float(b["quote"].iloc[idx].sum())
            entry_i = at.get(t + BAR)
            if vol <= 0 or entry_i is None:
                continue
            entry = float(b["open"].iat[entry_i])
            if not entry > 0:
                continue
            rec = {"coin": coin, "day": close_t // 86400, "ts": close_t, "direction": d,
                   "s": forced / vol}
            for name, k in HORIZONS.items():
                j = at.get(t + k * BAR)
                rec[name] = (float(b["close"].iat[j]) / entry - 1) if j is not None else np.nan
            j = at.get(t + HOLD_BARS * BAR)
            rec["r60"] = (float(b["close"].iat[j]) / entry - 1) if j is not None else np.nan
            rows.append(rec)
    return pd.DataFrame(rows)


def usable(ev: pd.DataFrame) -> pd.DataFrame:
    ev = ev.assign(y60=ev["direction"] * ev["r60"])
    ev = ev[np.isfinite(ev["s"]) & np.isfinite(ev["y60"])]
    return ev[ev.groupby("day")["s"].transform("size") >= MIN_DAY]


def tag_within_day(ev: pd.DataFrame) -> pd.Series:
    pct = ev.groupby("day")["s"].rank(pct=True)
    return pd.Series(np.where(pct > 2 / 3, "forced", np.where(pct <= 1 / 3, "organic", "middle")), index=ev.index)


def tag_prior_day(ev: pd.DataFrame) -> pd.Series:
    """Executable: today's events are tagged against yesterday's s distribution."""
    ev = ev.sort_values(["day", "ts"])
    prev = ev.groupby("day")["s"].apply(lambda x: (x.quantile(1 / 3), x.quantile(2 / 3))).to_dict()
    day_order = sorted(prev)
    prev_of = {d: prev[day_order[i - 1]] for i, d in enumerate(day_order) if i > 0}
    out = []
    for d, s in zip(ev["day"], ev["s"]):
        q = prev_of.get(d)
        if q is None:
            out.append("middle")
            continue
        lo, hi = q
        out.append("forced" if s > hi else ("organic" if s <= lo else "middle"))
    return pd.Series(out, index=ev.index)


def clustered(values: pd.Series) -> tuple[float, float, int]:
    v = values.dropna()
    if len(v) < 3:
        return float("nan"), float("nan"), len(v)
    return float(v.mean()), float(v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))), len(v)


def trade_weighted(df: pd.DataFrame, col: str) -> tuple[float, float, int]:
    g = df.groupby("day")[col].agg(["sum", "count"])
    m = g["sum"].sum() / g["count"].sum()
    k = len(g)
    se = np.sqrt(k / (k - 1) * ((g["sum"] - m * g["count"]) ** 2).sum()) / g["count"].sum()
    return float(m), float(m / se), k


def report(name: str, ev: pd.DataFrame, tagger) -> dict:
    u = usable(ev)
    t = tagger(u)
    d = (u.assign(tag=t).groupby(["day", "tag"])["y60"].mean().unstack())
    D = (d["forced"] - d["organic"]).dropna() if {"forced", "organic"} <= set(d) else pd.Series(dtype=float)
    m, tt, n = clustered(D)
    out = {"name": name, "events": int(len(u)), "days": int(u["day"].nunique()),
           "D_bps": 1e4 * m, "D_t": tt, "D_days": n}
    # the trade: buy after a forced DOWN-break, i.e. the bounce = -raw return
    leg = u.assign(tag=t, bounce=u["r60"])
    forced_down = leg[(leg["direction"] == -1) & (leg["tag"] == "forced")]
    daily = forced_down.groupby("day")["bounce"].mean()
    lm, lt, ln = clustered(daily)
    out["long_leg_bps"], out["long_leg_t"], out["long_leg_days"] = 1e4 * lm, lt, ln
    out["long_leg_events"] = int(len(forced_down))
    out["long_leg_daily_days"] = int(len(daily))
    for h in HORIZONS:
        sel = u.assign(tag=t, bounce=u[h])
        sel = sel[(sel["direction"] == -1) & (sel["tag"] == "forced")]
        tw, twt, _ = trade_weighted(sel, "bounce")
        out[f"tw_{h}_bps"], out[f"tw_{h}_t"] = 1e4 * tw, twt
        out[f"tw_{h}_net_bps"] = 1e4 * tw - 1e4 * COST / 2      # one side of the round trip
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default=",".join(COINS))
    args = ap.parse_args(argv)
    day_starts = days()
    all_events = []
    for coin in args.coins.split(","):
        b = bars(coin)
        if b.empty:
            print(f"{coin}: no bars")
            continue
        liq = liquidations(coin)
        ev = events_for(coin, b, liq, day_starts)
        print(f"{coin}: {len(ev)} events, {ev['day'].nunique() if len(ev) else 0} days")
        all_events.append(ev)
    ev = pd.concat(all_events, ignore_index=True)
    results = {
        "events": int(len(ev)), "coins": len(all_events),
        "window": "2023-06-26..2024-10-14",
        "within_day": report("within_day (the registered rule)", ev, tag_within_day),
        "prior_day": report("prior_day (executable)", ev, tag_prior_day),
    }
    OUT.write_text(json.dumps(results, indent=1))
    for k in ("within_day", "prior_day"):
        r = results[k]
        print(f"\n{k}: D {r['D_bps']:+.1f} bps (t {r['D_t']:.2f}, {r['D_days']} days); "
              f"long leg {r['long_leg_bps']:+.1f} bps (t {r['long_leg_t']:.2f})")
        for h in HORIZONS:
            print(f"   {h:>3}: trade-weighted {r[f'tw_{h}_bps']:+.1f} bps "
                  f"(t {r[f'tw_{h}_t']:.2f}), net {r[f'tw_{h}_net_bps']:+.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
