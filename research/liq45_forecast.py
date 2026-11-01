"""Retest #45: can pre-entry price, flow and signal features forecast the forced-liquidation bounce?

    python research/liq45_forecast.py

Registration: research/PREREGISTRATION_2026-11-01-liq45-forecast.md.
The primary event set is the #26 replication's continuous sample (26 COIN-M coins, 2023-06-26 ->
2024-10-14). The model is fitted on 2023-06-26 -> 2024-03-31 and scored once on 2024-04-01 ->
2024-10-14. A month-start archive and a stock-market analog are reported as exploratory cross-checks;
neither is a clean #45 replication.

No data is fetched. The script reads the local archives under data_raw/ and writes
research/liq45_forecast.json. It never writes a ledger row or an order.
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
MONTHLY = ROOT / "data_raw" / "liq"
FUND = ROOT / "data_raw" / "settle" / "funding"
TREND = ROOT / "data_raw" / "trend"
OUT = ROOT / "research" / "liq45_forecast.json"

BAR = 300
WINDOW = 12                 # 1 hour of 5-minute bars
HOLD = 12                   # the 1 h burst window
MIN_DAY = 6
COST = 0.0009               # 9 bps round trip, E1's cost
HORIZONS = {"4h": 48, "12h": 144, "1d": 288}
CONTRACT = {"BTC": 100.0}   # COIN-M contract size in USD; others are 10
CUT = "2024-10-14"          # continuous sample ends here
VALID_FROM = "2024-04-01"   # the one scoring window
MONTHLY_TRAIN_END = "2023-12-31"
MONTHLY_VALID_FROM = "2024-01-01"
MONTHLY_CUT = "2026-10-03"  # before the #45 forward window
STOCK_TRAIN_END = "2022-12-31"
STOCK_VALID_FROM = "2023-01-01"

COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK", "DOT", "TRX", "LTC",
         "BCH", "ATOM", "ETC", "XLM", "NEAR", "OP", "FIL", "RUNE", "AAVE", "EOS", "THETA", "XTZ",
         "ALGO", "WLD"]
FEATURES = ["s", "liq_count", "taker_imb", "vol_z", "ret_1h", "atr_pct", "funding_ann", "btc_ret_1h"]
F1 = [("s", 1), ("atr_pct", 1), ("ret_1h", -1)]


# --------------------------------------------------------------------------- small statistics
def percentile(train: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Empirical CDF of `train`, evaluated at `values`. Ties are counted as <=."""
    t = np.sort(np.asarray(train, dtype=float))
    v = np.asarray(values, dtype=float)
    if len(t) == 0:
        return np.full(len(v), np.nan)
    return np.searchsorted(t, v, side="right") / len(t)


def composite(frame: pd.DataFrame, train: pd.DataFrame, specs: list[tuple[str, int]]) -> np.ndarray:
    """Equal-weight percentile composite. Signs are applied to the value, not the percentile."""
    parts = []
    for name, sign in specs:
        p = percentile(train[name].to_numpy(float) * sign, frame[name].to_numpy(float) * sign)
        parts.append(p)
    return np.mean(np.column_stack(parts), axis=1)


def rank_ic(pred: np.ndarray, y: np.ndarray) -> float:
    p = pd.Series(pred, dtype=float)
    r = pd.Series(y, dtype=float)
    ok = p.notna() & r.notna()
    if ok.sum() < 3 or p[ok].nunique() < 2 or r[ok].nunique() < 2:
        return float("nan")
    return float(p[ok].rank().corr(r[ok].rank(), method="pearson"))


def auc(y: np.ndarray, pred: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(pred, dtype=float)
    ok = np.isfinite(p)
    y, p = y[ok], p[ok]
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    return float((np.sum(pos[:, None] > neg[None, :]) + 0.5 * np.sum(pos[:, None] == neg[None, :]))
                 / (len(pos) * len(neg)))


def top_quantile(y: np.ndarray, pred: np.ndarray, threshold: float) -> dict:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    ok = np.isfinite(y) & np.isfinite(pred)
    sel = y[ok & (pred >= threshold)]
    allv = y[ok]
    return {"n": int(len(sel)), "mean": float(sel.mean()) if len(sel) else float("nan"),
            "all_mean": float(allv.mean()) if len(allv) else float("nan"),
            "hit": float((sel > 0).mean()) if len(sel) else float("nan")}


def day_block_bootstrap(pred: np.ndarray, y: np.ndarray, days: np.ndarray, threshold: float,
                        reps: int = 1000, seed: int = 17) -> dict:
    """Resample UTC days, not events. Returns 95% percentile intervals for IC and top-quantile mean."""
    rng = np.random.default_rng(seed)
    pred = np.asarray(pred, dtype=float)
    y = np.asarray(y, dtype=float)
    days = np.asarray(days)
    uniq = np.unique(days)
    ics, tops = [], []
    for _ in range(reps):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([np.flatnonzero(days == d) for d in pick])
        ic = rank_ic(pred[idx], y[idx])
        if np.isfinite(ic):
            ics.append(ic)
        top = top_quantile(y[idx], pred[idx], threshold)["mean"]
        if np.isfinite(top):
            tops.append(top)
    out = {"reps": reps, "days": int(len(uniq))}
    for name, vals in (("ic", ics), ("top_mean", tops)):
        if len(vals) >= 20:
            out[name] = {"lo": float(np.percentile(vals, 2.5)),
                         "hi": float(np.percentile(vals, 97.5)),
                         "p_gt_0": float(np.mean(np.asarray(vals) > 0))}
        else:
            out[name] = None
    return out


# --------------------------------------------------------------------------- model fitting
def ridge_fit(X: np.ndarray, y: np.ndarray, lam: float = 10.0) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    A = np.column_stack([np.ones(len(X)), X])
    gram = A.T @ A
    pen = np.eye(A.shape[1]) * lam
    pen[0, 0] = 0.0
    return np.linalg.solve(gram + pen, A.T @ y)


def ridge_predict(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    return np.column_stack([np.ones(len(X)), X]) @ np.asarray(w, dtype=float)


def standardise(train: pd.DataFrame, frame: pd.DataFrame, cols: list[str]) -> tuple[np.ndarray, np.ndarray, dict]:
    mu = train[cols].mean()
    sd = train[cols].std(ddof=0).replace(0, 1.0)
    return (((train[cols] - mu) / sd).to_numpy(float),
            ((frame[cols] - mu) / sd).to_numpy(float),
            {c: {"mean": float(mu[c]), "std": float(sd[c])} for c in cols})


# --------------------------------------------------------------------------- data loading
def _bars_from_zips(coin: str, start: str, end: str) -> pd.DataFrame | None:
    sym = f"{coin}USDT"
    frames = []
    for z in sorted(LOWS.glob(f"{sym}/*.zip")):
        month = z.stem
        if not (start <= month <= end):
            continue
        try:
            with zipfile.ZipFile(z) as zf:
                raw = pd.read_csv(io.BytesIO(zf.read(zf.namelist()[0])))
        except (zipfile.BadZipFile, IndexError, OSError):
            continue
        frames.append(raw)
    if not frames:
        return None
    raw = pd.concat(frames, ignore_index=True).sort_values("open_time").drop_duplicates("open_time")
    ts = raw["open_time"].to_numpy("int64") // 1000
    out = pd.DataFrame({
        "open": raw["open"].to_numpy(float), "high": raw["high"].to_numpy(float),
        "low": raw["low"].to_numpy(float), "close": raw["close"].to_numpy(float),
        "volume": raw["volume"].to_numpy(float), "quote": raw["quote_volume"].to_numpy(float),
        "taker": raw["taker_buy_quote_volume"].to_numpy(float),
    }, index=ts // BAR * BAR).sort_index()
    return out[~out.index.duplicated()]


def _bars_from_monthly(coin: str) -> pd.DataFrame | None:
    frames = []
    for d in sorted(p.name for p in MONTHLY.iterdir() if p.is_dir()):
        p = MONTHLY / d / f"{coin}_bars.csv.gz"
        if not p.exists():
            continue
        with gzip.open(p, "rt") as f:
            raw = pd.read_csv(f)
        raw["day"] = d
        frames.append(raw)
    if not frames:
        return None
    raw = pd.concat(frames, ignore_index=True).sort_values("ts").drop_duplicates("ts")
    ts = raw["ts"].to_numpy("int64")
    out = pd.DataFrame({
        "open": raw["open"].to_numpy(float), "high": raw["high"].to_numpy(float),
        "low": raw["low"].to_numpy(float), "close": raw["close"].to_numpy(float),
        "volume": raw["volume"].to_numpy(float), "quote": raw["quote_volume"].to_numpy(float),
        "taker": raw["taker_buy_quote"].to_numpy(float),
    }, index=ts // BAR * BAR).sort_index()
    return out[~out.index.duplicated()]


def _liq2(coin: str) -> pd.DataFrame:
    sym = f"{coin}USD_PERP"
    frames = []
    for path in sorted((LIQ2 / sym).glob("*.csv.gz")):
        try:
            rows = pd.read_csv(gzip.open(path), header=0)
        except Exception:
            continue
        rows = rows.drop_duplicates(subset=["time", "price", "last_fill_quantity"])
        rows["side"] = rows["side"].map({"SELL": "sell", "BUY": "buy"})
        rows["usd"] = rows["last_fill_quantity"].to_numpy(float) * CONTRACT.get(coin, 10.0)
        frames.append(rows[["time", "side", "usd"]])
    if not frames:
        return pd.DataFrame(columns=["ts", "side", "usd"])
    lq = pd.concat(frames, ignore_index=True)
    lq["ts"] = lq["time"].to_numpy("int64") // 1000
    return lq.sort_values("ts")


def _liq_monthly(coin: str) -> pd.DataFrame:
    frames = []
    for d in sorted(p.name for p in MONTHLY.iterdir() if p.is_dir()):
        p = MONTHLY / d / f"{coin}_liq.csv.gz"
        if not p.exists():
            continue
        with gzip.open(p, "rt") as f:
            rows = pd.read_csv(f)
        rows["day"] = d
        frames.append(rows)
    if not frames:
        return pd.DataFrame(columns=["ts", "side", "usd", "day"])
    return pd.concat(frames, ignore_index=True).sort_values("ts")


def _funding(coin: str) -> tuple[np.ndarray, np.ndarray]:
    p = FUND / f"{coin}USDT.json"
    if not p.exists():
        return np.array([], dtype="int64"), np.array([], dtype=float)
    rows = json.load(open(p))
    ts = np.array([r["fundingTime"] // 1000 for r in rows], dtype="int64")
    rate = np.array([float(r["fundingRate"]) for r in rows], dtype=float)
    order = np.argsort(ts)
    return ts[order], rate[order]


def _btc_map(bars: pd.DataFrame) -> dict[int, float]:
    if bars is None or len(bars) < 13:
        return {}
    ret = np.log(bars["close"] / bars["close"].shift(12))
    return {int(t): float(v) for t, v in ret.items() if np.isfinite(v)}


# --------------------------------------------------------------------------- event construction
def _day_allowed(day: int) -> bool:
    """#26's calendar filter: the first three days and the last day of a month are dropped."""
    d = pd.Timestamp(day * 86400, unit="s")
    return not (d.day <= 2 or (d.day in (28, 29, 30, 31) and (d + pd.Timedelta(days=1)).day == 1))


def build_events(coin: str, bars: pd.DataFrame, liq: pd.DataFrame, *, start: str, end: str,
                 monthly: bool, btc_map: dict[int, float], funding: tuple[np.ndarray, np.ndarray],
                 allow_days: set[int] | None = None) -> pd.DataFrame:
    """One row per break, with entry-time features and forward returns.

    The rule is #26's. `bars` is indexed by aligned epoch seconds. `liq` has ts/side/usd.
    `allow_days` is an optional set of UTC day numbers that have liquidation data.
    """
    if bars is None or len(bars) < 300:
        return pd.DataFrame()
    close = bars["close"].to_numpy(float)
    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    vol = bars["volume"].to_numpy(float)
    quote = bars["quote"].to_numpy(float)
    taker = bars["taker"].to_numpy(float)
    ts = bars.index.to_numpy("int64")

    s = pd.Series(close)
    h = pd.Series(high)
    l = pd.Series(low)
    v = pd.Series(vol)
    burst = np.log(s / s.shift(HOLD))
    x = np.log(v + 1.0)
    vz = (x - x.rolling(48, min_periods=48).mean()) / x.rolling(48, min_periods=48).std()
    tr = pd.concat([h - l, (h - s.shift()).abs(), (l - s.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    prior_high = h.shift(1).rolling(48).max()
    prior_low = l.shift(1).rolling(48).min()
    ok = (vz >= 2.0) & (atr > 0)
    up = ((s > prior_high) & prior_high.notna() & ok & (burst > 0)).to_numpy()
    down = ((s < prior_low) & prior_low.notna() & ok & (burst < 0)).to_numpy()

    lq_ts = liq["ts"].to_numpy(float) if len(liq) else np.array([], dtype=float)
    lq_usd = liq["usd"].to_numpy(float) if len(liq) else np.array([], dtype=float)
    lq_sell = (liq["side"] == "sell").to_numpy() if len(liq) else np.array([], dtype=bool)
    lq_days = set((liq["ts"].to_numpy("int64") // 86400).tolist()) if len(liq) else set()
    fts, frate = funding

    day_from = int(pd.Timestamp(start, tz="UTC").timestamp()) // 86400
    day_to = int(pd.Timestamp(end, tz="UTC").timestamp()) // 86400
    rows = []
    last: dict[int, int] = {}
    for i in np.flatnonzero(up | down):
        t = int(ts[i])
        day = t // 86400
        if not (day_from <= day <= day_to):
            continue
        if day not in lq_days:
            continue
        if allow_days is not None and day not in allow_days:
            continue
        if monthly:
            pass
        else:
            if not _day_allowed(day):
                continue
        day_start = day * 86400
        if not (day_start + 3600 <= t + BAR <= day_start + 86400):
            continue
        direction = 1 if up[i] else -1
        if direction in last and t - last[direction] <= HOLD * BAR:
            continue
        last[direction] = t
        close_t = t + BAR
        start_t = t - (WINDOW - 1) * BAR
        ei = i + 1
        if ei >= len(bars):
            continue
        entry = float(bars["open"].iat[ei])
        if not np.isfinite(entry) or entry <= 0:
            continue
        side_sell = bool(down[i])
        a = np.searchsorted(lq_ts, start_t, "left")
        z = np.searchsorted(lq_ts, close_t, "left")
        if z > a:
            m = lq_sell[a:z] == side_sell
            forced = float(lq_usd[a:z][m].sum())
            cnt = int(m.sum())
        else:
            forced, cnt = 0.0, 0
        idx = [i - k for k in range(WINDOW)]
        if min(idx) < 0:
            continue
        qvol = float(quote[idx].sum())
        if qvol <= 0:
            continue
        last_f = np.nan
        if len(fts):
            k = int(np.searchsorted(fts, close_t, "right") - 1)
            if k >= 0:
                last_f = float(frate[k]) * 3.0 * 365.0   # 8 h interval -> annual
        rec = {
            "coin": coin, "day": close_t // 86400, "ts": t, "close_t": close_t,
            "direction": direction, "s": forced / qvol, "liq_usd": forced, "liq_count": cnt,
            "ret_1h": float(np.log(close[i] / close[i - 12])) if i >= 12 else np.nan,
            "ret_4h": float(np.log(close[i] / close[i - 48])) if i >= 48 else np.nan,
            "vol_z": float(vz.iat[i]), "atr_pct": float(atr.iat[i] / entry),
            "range_pct": float((high[i] - low[i]) / close[i]),
            "close_loc": float((close[i] - low[i]) / (high[i] - low[i])) if high[i] > low[i] else np.nan,
            "taker_imb": float(2 * taker[i] / quote[i] - 1) if quote[i] > 0 else np.nan,
            "funding_ann": last_f, "btc_ret_1h": btc_map.get(t, np.nan),
        }
        for name, k in HORIZONS.items():
            j = i + k
            if j >= len(bars):
                rec[name], rec[name + "_gross"], rec[name + "_funding"] = np.nan, np.nan, np.nan
                continue
            exit_ts = int(ts[j]) + BAR
            gross = float(close[j] / entry - 1)
            fs = 0.0
            if len(fts):
                aa = int(np.searchsorted(fts, int(ts[ei]), "right"))
                zz = int(np.searchsorted(fts, exit_ts, "right"))
                if zz > aa:
                    fs = float(frate[aa:zz].sum())
            rec[name + "_gross"] = gross
            rec[name] = gross - COST - fs
            rec[name + "_funding"] = fs
        rows.append(rec)
    return pd.DataFrame(rows)


def prior_day_tags(ev: pd.DataFrame) -> pd.Series:
    """Today's s against the previous *observed* event day's terciles (E1's convention)."""
    if ev.empty:
        return pd.Series(dtype=object)
    ev = ev.sort_values(["day", "ts"])
    q = ev.groupby("day")["s"].apply(lambda x: (x.quantile(1 / 3), x.quantile(2 / 3))).to_dict()
    order = sorted(q)
    prev = {order[i]: q[order[i - 1]] for i in range(1, len(order))}
    tags = []
    for day, value in zip(ev["day"], ev["s"]):
        bounds = prev.get(day)
        if bounds is None:
            tags.append("middle")
        else:
            lo, hi = bounds
            tags.append("forced" if value > hi else ("organic" if value <= lo else "middle"))
    return pd.Series(tags, index=ev.index)


def forced_down(ev: pd.DataFrame) -> pd.DataFrame:
    if ev.empty:
        return ev
    ev = ev.assign(tag=prior_day_tags(ev))
    out = ev[(ev["direction"] == -1) & (ev["tag"] == "forced")].copy()
    out["date"] = pd.to_datetime(out["day"] * 86400, unit="s")
    return out.sort_values(["date", "ts"]).reset_index(drop=True)


# --------------------------------------------------------------------------- evaluation
def evaluate_continuous() -> dict:
    btc_bars = _bars_from_zips("BTC", "2023-04", "2024-10")
    btc_map = _btc_map(btc_bars)
    frames = []
    for coin in COINS:
        bars = _bars_from_zips(coin, "2023-04", "2024-10")
        liq = _liq2(coin)
        ev = build_events(coin, bars, liq, start="2023-06-26", end=CUT, monthly=False,
                          btc_map=btc_map, funding=_funding(coin))
        frames.append(ev)
    events = pd.concat(frames, ignore_index=True)
    events = events[events.groupby("day")["ts"].transform("size") >= MIN_DAY].reset_index(drop=True)
    trade = forced_down(events)
    design = trade[trade["date"] < pd.Timestamp(VALID_FROM)].copy()
    valid = trade[trade["date"] >= pd.Timestamp(VALID_FROM)].copy()
    out = {
        "events_all": int(len(events)), "days_all": int(events["day"].nunique()),
        "forced_down": int(len(trade)), "forced_days": int(trade["day"].nunique()),
        "design": {"events": int(len(design)), "days": int(design["day"].nunique())},
        "validation": {"events": int(len(valid)), "days": int(valid["day"].nunique())},
        "unconditional": {},
        "models": {},
        "layers": {},
    }
    for name, frame in (("design", design), ("validation", valid)):
        block = {}
        for h in HORIZONS:
            vals = frame[h].dropna()
            daily = frame.groupby("day")[h].mean().dropna()
            block[h] = {
                "n": int(len(vals)),
                "mean_bps": float(1e4 * vals.mean()) if len(vals) else None,
                "median_bps": float(1e4 * vals.median()) if len(vals) else None,
                "hit": float((vals > 0).mean()) if len(vals) else None,
                "day_mean_bps": float(1e4 * daily.mean()) if len(daily) else None,
                "day_t": float(daily.mean() / (daily.std(ddof=1) / np.sqrt(len(daily))))
                if len(daily) > 2 and daily.std(ddof=1) > 0 else None,
            }
        out["unconditional"][name] = block

    # models, fitted only on design
    y_train = design["4h"].to_numpy(float)
    f1_train_threshold = float(np.percentile(composite(design, design, F1), 80))
    f1t_specs = F1 + [("taker_imb", 1)]
    f1t_train_threshold = float(np.percentile(composite(design, design, f1t_specs), 80))
    X_train, X_valid, scaler = standardise(design, valid, FEATURES)
    w = ridge_fit(X_train, y_train, 10.0)
    f2_train = ridge_predict(w, X_train)
    f2_valid = ridge_predict(w, X_valid)
    f2_train_threshold = float(np.percentile(f2_train, 80))

    specs = {
        "F1": (composite(valid, design, F1), f1_train_threshold, dict(F1)),
        "F1T": (composite(valid, design, f1t_specs), f1t_train_threshold, dict(f1t_specs)),
        "F2": (f2_valid, f2_train_threshold, {c: float(x) for c, x in zip(["intercept"] + FEATURES, w)}),
    }
    for name, (pred, threshold, meta) in specs.items():
        block = {"threshold": threshold, "coef": meta, "horizons": {}}
        for h in HORIZONS:
            y = valid[h].to_numpy(float)
            block["horizons"][h] = {
                "n": int(np.isfinite(y).sum()),
                "ic": rank_ic(pred, y),
                "auc": auc((y > 0).astype(int), pred),
                "top": top_quantile(y, pred, threshold),
                "bootstrap": day_block_bootstrap(pred, y, valid["day"].to_numpy(), threshold,
                                                 reps=1000, seed=17),
            }
        out["models"][name] = block

    # layer read-outs: each feature alone, through the training CDF
    for feature in FEATURES:
        sign = -1 if feature == "ret_1h" else 1
        p = percentile(design[feature].to_numpy(float) * sign,
                       valid[feature].to_numpy(float) * sign)
        y = valid["4h"].to_numpy(float)
        threshold = float(np.percentile(percentile(design[feature].to_numpy(float) * sign,
                                                   design[feature].to_numpy(float) * sign), 80))
        out["layers"][feature] = {
            "ic_4h": rank_ic(p, y),
            "top_4h": top_quantile(y, p, threshold),
        }

    # calibration by score quintile, 4 h net
    p = specs["F1"][0]
    y = valid["4h"].to_numpy(float)
    ok = np.isfinite(y) & np.isfinite(p)
    q = pd.qcut(pd.Series(p[ok]), 5, labels=False, duplicates="drop")
    cal = []
    for k in sorted(pd.Series(q).dropna().unique()):
        m = q == k
        cal.append({"quintile": int(k) + 1, "n": int(m.sum()),
                    "score": float(np.mean(p[ok][m])),
                    "net_bps": float(1e4 * np.mean(y[ok][m])),
                    "hit": float(np.mean(y[ok][m] > 0))})
    out["calibration"] = cal
    out["split"] = {"design": "2023-06-26..2024-03-31", "validation": f"{VALID_FROM}..{CUT}"}
    return out


def evaluate_monthly() -> dict:
    btc_map = _btc_map(_bars_from_monthly("BTC"))
    frames = []
    for coin in sorted({p.name.replace("_bars.csv.gz", "") for p in (MONTHLY / "2023-06-01").glob("*_bars.csv.gz")}):
        bars = _bars_from_monthly(coin)
        liq = _liq_monthly(coin)
        if liq.empty:
            continue
        ev = build_events(coin, bars, liq, start="2020-01-01", end=MONTHLY_CUT, monthly=True,
                          btc_map=btc_map, funding=_funding(coin))
        frames.append(ev)
    events = pd.concat(frames, ignore_index=True)
    events = events[events.groupby("day")["ts"].transform("size") >= MIN_DAY].reset_index(drop=True)
    trade = forced_down(events)
    design = trade[trade["date"] <= pd.Timestamp(MONTHLY_TRAIN_END)].copy()
    valid = trade[trade["date"] >= pd.Timestamp(MONTHLY_VALID_FROM)].copy()
    out = {"events_all": int(len(events)), "forced_down": int(len(trade)),
           "design": {"events": int(len(design)), "days": int(design["day"].nunique())},
           "validation": {"events": int(len(valid)), "days": int(valid["day"].nunique())},
           "models": {}}
    if len(design) < 100 or len(valid) < 100:
        out["note"] = "not enough events for the cross-check"
        return out
    f1_valid = composite(valid, design, F1)
    threshold = float(np.percentile(composite(design, design, F1), 80))
    for h in HORIZONS:
        y = valid[h].to_numpy(float)
        out["models"][h] = {
            "ic": rank_ic(f1_valid, y),
            "auc": auc((y > 0).astype(int), f1_valid),
            "top": top_quantile(y, f1_valid, threshold),
            "bootstrap": day_block_bootstrap(f1_valid, y, valid["day"].to_numpy(), threshold,
                                             reps=1000, seed=23),
        }
    out["note"] = ("month-start three-day samples, not #26's day sample; exploratory only")
    return out


def _etf_ret(symbol: str) -> pd.DataFrame:
    p = TREND / f"{symbol}.csv"
    d = pd.read_csv(p, parse_dates=["dt"]).sort_values("dt")
    d["ret"] = np.log(pd.to_numeric(d["close"], errors="coerce")
                      / pd.to_numeric(d["close"], errors="coerce").shift(1))
    return d[["dt", "ret"]].rename(columns={"dt": "date", "ret": f"{symbol.lower()}_ret_1d"})


def evaluate_stocks() -> dict:
    frames = []
    for symbol in ("SPY", "QQQ", "IWM"):
        p = TREND / f"{symbol}.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p, parse_dates=["dt"]).sort_values("dt").reset_index(drop=True)
        d["close"] = pd.to_numeric(d["close"], errors="coerce")
        d["high"] = pd.to_numeric(d["high"], errors="coerce")
        d["low"] = pd.to_numeric(d["low"], errors="coerce")
        d["open"] = pd.to_numeric(d["open"], errors="coerce")
        d["volume"] = pd.to_numeric(d["volume"], errors="coerce")
        close, high, low, vol = d["close"], d["high"], d["low"], d["volume"]
        ret_1d = np.log(close / close.shift(1))
        ret_5d = np.log(close / close.shift(5))
        ret_20d = np.log(close / close.shift(20))
        x = np.log(vol + 1.0)
        vol_z = (x - x.rolling(60).mean()) / x.rolling(60).std()
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
                       axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
        prior_low = low.shift(1).rolling(20).min()
        event = (close < prior_low) & prior_low.notna() & (vol_z >= 2) & (atr > 0)
        entry = d["open"].shift(-1)
        exit_ = close.shift(-5)
        target = exit_ / entry - 1
        frame = pd.DataFrame({
            "date": d["dt"], "symbol": symbol, "event": event,
            "ret_1d": ret_1d, "ret_5d": ret_5d, "ret_20d": ret_20d,
            "atr_pct": atr / close, "vol_z": vol_z,
            "range_pct": (high - low) / close,
            "close_loc": (close - low) / (high - low),
            "target_5d": target,
        })
        frames.append(frame)
    if not frames:
        return {"note": "no stock data"}
    allf = pd.concat(frames, ignore_index=True)
    for symbol in ("TLT", "GLD"):
        allf = allf.merge(_etf_ret(symbol), on="date", how="left")
    ev = allf[allf["event"]].dropna(subset=["ret_1d", "ret_5d", "ret_20d", "atr_pct", "vol_z",
                                             "range_pct", "close_loc", "tlt_ret_1d",
                                             "gld_ret_1d", "target_5d"]).copy()
    train = ev[ev["date"] <= pd.Timestamp(STOCK_TRAIN_END, tz="UTC")]
    valid = ev[ev["date"] >= pd.Timestamp(STOCK_VALID_FROM, tz="UTC")]
    feats = ["ret_1d", "ret_5d", "ret_20d", "atr_pct", "vol_z", "range_pct", "close_loc",
             "tlt_ret_1d", "gld_ret_1d"]
    out = {"events": int(len(ev)), "design": int(len(train)), "validation": int(len(valid)),
           "by_symbol": ev.groupby("symbol").size().to_dict(),
           "unconditional": {"mean": float(ev["target_5d"].mean()),
                             "hit": float((ev["target_5d"] > 0).mean()),
                             "mean_bps": float(1e4 * ev["target_5d"].mean()),
                             "validation_mean_bps": float(1e4 * valid["target_5d"].mean()),
                             "validation_hit": float((valid["target_5d"] > 0).mean())},
           "models": {}}
    if len(train) < 50 or len(valid) < 20:
        out["note"] = "not enough stock events for a forecast test"
        return out
    X_train, X_valid, _ = standardise(train, valid, feats)
    w = ridge_fit(X_train, train["target_5d"].to_numpy(float), 10.0)
    pred = ridge_predict(w, X_valid)
    out["models"]["ridge"] = {
        "ic": rank_ic(pred, valid["target_5d"].to_numpy(float)),
        "top": top_quantile(valid["target_5d"].to_numpy(float), pred,
                            float(np.percentile(ridge_predict(w, X_train), 80))),
    }
    f1 = composite(valid, train, [("ret_20d", -1), ("atr_pct", 1), ("vol_z", 1)])
    out["models"]["composite"] = {
        "ic": rank_ic(f1, valid["target_5d"].to_numpy(float)),
        "top": top_quantile(valid["target_5d"].to_numpy(float), f1,
                            float(np.percentile(composite(train, train,
                                                          [("ret_20d", -1), ("atr_pct", 1),
                                                           ("vol_z", 1)]), 80))),
    }
    out["note"] = ("daily down-break + volume analog, not a forced-liquidation test; "
                   "equities have no equivalent liquidation feed")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)
    if not (LOWS.exists() and LIQ2.exists() and MONTHLY.exists()):
        raise SystemExit("data_raw archives are missing; this script does not fetch data")
    result = {
        "registration": "research/PREREGISTRATION_2026-11-01-liq45-forecast.md",
        "generated": "2026-11-01",
        "continuous": evaluate_continuous(),
        "monthly": evaluate_monthly(),
        "stocks": evaluate_stocks(),
    }
    pathlib.Path(args.out).write_text(json.dumps(result, indent=1, default=float) + "\n")
    print(json.dumps({k: result[k] for k in ("continuous", "monthly", "stocks")}, indent=1,
                     default=float)[:4000])
    print(f"[written {args.out}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
