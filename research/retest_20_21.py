"""Forecast retest of #21 (liquidation spikes) and #20 (new 4-hour lows).

    python research/retest_20_21.py

Registration: research/PREREGISTRATION_2026-11-01-lows21-forecast.md.
Reads the published event files under data_raw/events and the daily panel under data_raw/panel.
No fetch; no forward window. Writes research/retest_20_21.json.

The question is not whether the average event reverses/bounces — the published tests and the #44
re-estimate already judge that. It is whether the event cross-section is forecastable out of time
from information known at entry.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.remaining_forecasts import (
    bh,
    block_bootstrap,
    load_panel,
    normal_p,
    nw_t,
    rank_ic,
)

DATA = ROOT / "data_raw"
OUT = ROOT / "research" / "retest_20_21.json"

COST_BPS = 9.0
MAX_ABS = 0.50
# the local #21 replication's published baselines, fixed before this forecast test
BASE_24 = 0.0023886236851763382
BASE_4 = 0.0004112102349750879


def evaluate_events(df: pd.DataFrame, date_col: str, signal: str, target: str,
                    min_n: int = 5) -> dict:
    """Rank IC and top-vs-all spread from one row per event, with days as blocks."""
    ics, dates, tops, alls, top_hits = [], [], [], [], []
    n_events = 0
    for d, g in df.groupby(date_col, sort=True):
        g = g[[signal, target]].dropna()
        if len(g) < min_n:
            continue
        ic = rank_ic(g[signal], g[target])
        if not np.isfinite(ic):
            continue
        ics.append(ic)
        dates.append(d)
        n_events += len(g)
        thr = g[signal].quantile(0.8)
        top = g.loc[g[signal] >= thr, target].mean()
        tops.append(top)
        alls.append(g[target].mean())
        top_hits.append(float(top > 0))
    if len(ics) < 5:
        return {"verdict": "NO DATA", "n_days": len(ics)}
    ic_s = pd.Series(ics, index=pd.Index(dates))
    ic_boot = block_bootstrap(ic_s)
    t_ic = nw_t(ic_s, lags=1)
    # primary spread: the pre-registration's pooled top quintile across validation events
    d = df[[date_col, signal, target]].dropna()
    d = d[d.groupby(date_col)[target].transform("count") >= min_n]
    thr = d[signal].quantile(0.8)
    top = d.loc[d[signal] >= thr, target]
    allv = d[target]
    g = d.groupby(date_col)
    top_day = d[d[signal] >= thr].groupby(date_col)[target].agg(["sum", "count"]).reindex(
        g.size().index, fill_value=0)
    all_day = g[target].agg(["sum", "count"])
    days = all_day.index.to_numpy()
    rng = np.random.default_rng(7)
    idx = rng.integers(0, len(days), (1000, len(days)))
    ts = top_day["sum"].to_numpy()[idx].sum(axis=1)
    tn = top_day["count"].to_numpy()[idx].sum(axis=1)
    asu = all_day["sum"].to_numpy()[idx].sum(axis=1)
    acn = all_day["count"].to_numpy()[idx].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        top_means = ts / tn
        all_means = asu / acn
    spread_means = top_means - all_means
    pooled_top = float(top.mean())
    pooled_all = float(allv.mean())
    pooled_spread = pooled_top - pooled_all
    top_lo, top_hi = np.percentile(top_means * 1e4, [2.5, 97.5])
    sp_lo, sp_hi = np.percentile(spread_means * 1e4, [2.5, 97.5])
    # information only: the old within-day top-versus-all average
    day_sp = pd.Series(np.asarray(tops) - np.asarray(alls), index=pd.Index(dates))
    day_boot = block_bootstrap(day_sp)
    return {
        "n_days": int(len(ic_s)),
        "n_events": int(n_events),
        "ic": ic_boot["mean"], "ic_lo": ic_boot["lo"], "ic_hi": ic_boot["hi"],
        "ic_t": float(t_ic), "ic_p": normal_p(float(t_ic)),
        "ic_hit": float((ic_s > 0).mean()),
        "spread_bps": pooled_spread * 1e4,
        "spread_lo_bps": float(sp_lo),
        "spread_hi_bps": float(sp_hi),
        "spread_net_bps": pooled_spread * 1e4 - COST_BPS,
        "top_bps": pooled_top * 1e4,
        "top_lo_bps": float(top_lo),
        "top_hi_bps": float(top_hi),
        "all_bps": pooled_all * 1e4,
        "top_hit": float(pd.Series(top_hits).mean()),
        "day_spread_bps": day_boot["mean"] * 1e4,
        "day_spread_lo_bps": day_boot["lo"] * 1e4,
        "day_spread_hi_bps": day_boot["hi"] * 1e4,
    }


def classify(r: dict) -> str:
    if r.get("verdict") == "NO DATA":
        return "NO DATA"
    ic_ok = r["ic"] > 0 and r["ic_lo"] > 0
    spread_ok = r["spread_net_bps"] > 0
    if ic_ok and spread_ok:
        return "FORECASTS"
    if ic_ok:
        return "WEAK FORECAST"
    return "NO FORECAST"


# --------------------------------------------------------------------------- #21
def load_21() -> pd.DataFrame:
    e = pd.read_csv(DATA / "events" / "liqspike_events.csv")
    e["day"] = pd.to_datetime(e["day"]).dt.normalize()
    e["t"] = pd.to_datetime(e["t"], utc=True)
    e["hour"] = e["t"].dt.hour
    sign = np.where(e["side"] == "long", 1.0, -1.0)
    e["signed24"] = (e["r24"] - BASE_24) * sign
    e["signed4"] = (e["r4"] - BASE_4) * sign
    e["abs_r0"] = e["r0"].abs()
    e["log_usd"] = np.log1p(e["usd"].clip(lower=0))
    e["side_num"] = (e["side"] == "long").astype(int)
    return e


def test_21() -> dict:
    e = load_21()
    design = e[e["day"] <= "2026-08-31"]
    valid = e[e["day"] >= "2026-09-01"]
    signals = ["share", "abs_r0", "log_usd", "side_num"]
    out = {"events": int(len(e)), "design_events": int(len(design)),
           "validation_events": int(len(valid)), "signals": {}}
    for s in signals:
        r24 = evaluate_events(valid, "day", s, "signed24")
        r24["verdict"] = classify(r24)
        r4 = evaluate_events(valid, "day", s, "signed4")
        r4["verdict"] = classify(r4)
        d = evaluate_events(design, "day", s, "signed24")
        out["signals"][s] = {"primary_24h": r24, "secondary_4h": r4,
                             "design_24h": d, "role": "primary" if s == "share" else "secondary"}
    out["primary"] = out["signals"]["share"]["primary_24h"]
    return out


# --------------------------------------------------------------------------- #20
def load_panel_features() -> pd.DataFrame:
    p = load_panel()
    close, vol = p["close"], p["volume"]
    ret = close.pct_change(fill_method=None)
    x = np.log(vol.clip(lower=0) + 1.0)
    features = {
        "vol_30": ret.rolling(30, min_periods=20).std().shift(1),
        "ret_1": ret.shift(1),
        "ret_5": close.pct_change(5, fill_method=None).shift(1),
        "ret_20": close.pct_change(20, fill_method=None).shift(1),
        "vol_z": ((x - x.rolling(30, min_periods=20).mean()).div(
            x.rolling(30, min_periods=20).std())).shift(1),
    }
    long = []
    for name, frame in features.items():
        s = frame.stack(future_stack=True).rename(name).reset_index()
        s.columns = ["day", "coin", name]
        long.append(s)
    out = long[0]
    for s in long[1:]:
        out = out.merge(s, on=["day", "coin"], how="outer")
    out["day"] = pd.to_datetime(out["day"]).dt.normalize()
    # market and BTC context, broadcast to every coin
    mkt = ret.mean(axis=1).shift(1).rename("mkt_ret_1")
    btc = ret["BTC"].shift(1).rename("btc_ret_1")
    ctx = pd.concat([mkt, btc], axis=1).reset_index()
    ctx.columns = ["day", "mkt_ret_1", "btc_ret_1"]
    ctx["day"] = pd.to_datetime(ctx["day"]).dt.normalize()
    return out.merge(ctx, on="day", how="left")


def test_20() -> dict:
    low = pd.read_csv(DATA / "events" / "lows_events.csv.gz")
    low = low[low["direction"] == "down"].copy()
    low["day"] = pd.to_datetime(low["day"]).dt.normalize()
    low["ts"] = pd.to_datetime(low["ts"], unit="s", utc=True)
    low["hour"] = low["ts"].dt.hour
    low = low[(low["r60"].abs() <= MAX_ABS) & (low["r240"].abs() <= MAX_ABS)]
    feat = load_panel_features()
    low = low.merge(feat, on=["day", "coin"], how="inner")
    low = low[low["day"] >= "2021-10-27"]
    design = low[low["day"] <= "2023-12-31"]
    valid = low[low["day"] >= "2024-01-01"]
    signals = ["vol_30", "ret_1", "ret_5", "ret_20", "vol_z", "mkt_ret_1", "btc_ret_1"]
    out = {"events": int(len(low)), "design_events": int(len(design)),
           "validation_events": int(len(valid)), "signals": {}}
    for s in signals:
        r60 = evaluate_events(valid, "day", s, "r60")
        r60["verdict"] = classify(r60)
        r240 = evaluate_events(valid, "day", s, "r240")
        r240["verdict"] = classify(r240)
        d = evaluate_events(design, "day", s, "r60")
        out["signals"][s] = {"primary_1h": r60, "secondary_4h": r240,
                             "design_1h": d, "role": "primary" if s == "vol_30" else "secondary"}
    out["primary"] = out["signals"]["vol_30"]["primary_1h"]
    return out


def main() -> int:
    missing = [p for p in ("events", "panel") if not (DATA / p).exists()]
    if missing:
        raise SystemExit(f"data_raw archives missing: {missing}; this script does not fetch data")
    tests = {"21": test_21(), "20": test_20()}
    pvals = [tests["21"]["primary"].get("ic_p", float("nan")),
             tests["20"]["primary"].get("ic_p", float("nan"))]
    qs = bh(pvals)
    for k, p, q in zip(("21", "20"), pvals, qs):
        tests[k]["p_primary"] = float(p) if p is not None else float("nan")
        tests[k]["q_primary"] = float(q) if q is not None else float("nan")
    payload = {
        "preregistration": "research/PREREGISTRATION_2026-11-01-lows21-forecast.md",
        "cost_bps": COST_BPS,
        "max_abs_target": MAX_ABS,
        "baselines": {"24h": BASE_24, "4h": BASE_4},
        "tests": tests,
    }
    OUT.write_text(json.dumps(payload, indent=1, default=str) + "\n")
    for k, label in (("21", "#21 share -> 24h signed excess"),
                     ("20", "#20 vol_30 -> 1h bounce")):
        r = tests[k]["primary"]
        print(f"{label:38s} {r.get('verdict','?'):14s} IC {r.get('ic',float('nan')):+.3f} "
              f"[{r.get('ic_lo',float('nan')):+.3f},{r.get('ic_hi',float('nan')):+.3f}] "
              f"t {r.get('ic_t',float('nan')):+.2f} spread {r.get('spread_bps',float('nan')):+.1f} bps "
              f"q {tests[k]['q_primary']:.3f}")
    print(f"[written {OUT.relative_to(ROOT)}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
