"""Retest the remaining audit findings as forecasts: #1, #4, #8, #9b, #15, #43.

    python research/remaining_forecasts.py

Registration: research/PREREGISTRATION_2026-11-01-remaining-findings.md.
Reads the local archives under data_raw/ (gitignored). No fetch; no forward window is read.
Writes research/remaining_forecasts.json and prints a summary.

The five panel tests use the same forecast protocol: a causal signal, a target that starts at the
next bar's open, a design/validation split fixed in the registration, rank IC with day-block
bootstrap and Newey-West t, a top-minus-bottom spread net of 9 bps, and BH across the six primary
tests. #43 re-estimates the published #20 event file trade-weighted against its own deflated bar.
"""
from __future__ import annotations

import json
import math
import pathlib
from statistics import NormalDist

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data_raw"
OUT = ROOT / "research" / "remaining_forecasts.json"

COST_BPS = 9.0
# reference/ERRATA.md: these Yahoo tickers switch tokens mid-history; their prices are not one
# series. They are dropped from the daily cross-section, and any |forward return| > 50% is a data
# error (splits, ticker switches), not a market move. Amendment recorded in the registration.
COLLISIONS = {"ARB", "TIA", "WLD", "OP"}
MAX_ABS_FWD = 0.50
DAILY_DESIGN_END = "2023-12-31"
DAILY_VALID_FROM = "2024-01-01"
DAILY_CUT = "2026-10-27"
# #8's own split from the original registration
MF_DESIGN_END = "2024-06-30"
MF_VALID_FROM = "2024-07-01"
# hourly #9b split
H_DESIGN_END = "2026-04-30"
H_VALID_FROM = "2026-05-01"
TREND_DESIGN_END = "2020-12-31"
TREND_VALID_FROM = "2021-01-01"


# --------------------------------------------------------------------------- statistics
def rank_ic(x: pd.Series, y: pd.Series) -> float:
    """Spearman correlation of two series, ties averaged. NaN for degenerate ranks."""
    m = x.notna() & y.notna()
    x, y = x[m], y[m]
    if len(x) < 3:
        return float("nan")
    xr, yr = x.rank(), y.rank()
    if xr.std() == 0 or yr.std() == 0:
        return float("nan")
    return float(xr.corr(yr))


def nw_t(values, lags: int = 1) -> float:
    """Newey-West t of the mean of a serially correlated series."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return float("nan")
    mu = float(x.mean())
    e = x - mu
    s = float(e @ e) / n
    for lag in range(1, min(lags, n - 1) + 1):
        gl = float(e[lag:] @ e[:-lag]) / n
        s += 2.0 * (1.0 - lag / (lags + 1.0)) * gl
    if s <= 0:
        return float("nan")
    return mu / math.sqrt(s / n)


def block_bootstrap(values, reps: int = 1000, seed: int = 7) -> dict:
    """Mean and 95% percentile CI from day-block resampling of a per-date series."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 5:
        return {"mean": float(x.mean()) if len(x) else float("nan"),
                "lo": float("nan"), "hi": float("nan"), "n": int(len(x))}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), (reps, len(x)))
    means = x[idx].mean(axis=1)
    return {"mean": float(x.mean()), "lo": float(np.percentile(means, 2.5)),
            "hi": float(np.percentile(means, 97.5)), "n": int(len(x))}


def normal_p(t: float) -> float:
    if not np.isfinite(t):
        return float("nan")
    return float(2.0 * (1.0 - NormalDist().cdf(abs(t))))


def bh(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg q-values, NaNs passed through."""
    p = np.asarray(pvals, dtype=float)
    q = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    if ok.sum() == 0:
        return q.tolist()
    pv = p[ok]
    order = np.argsort(pv)
    m = len(pv)
    adj = pv[order] * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.clip(adj, 0.0, 1.0)
    q[ok] = out
    return q.tolist()


def max_drawdown(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) == 0:
        return float("nan")
    curve = (1.0 + r).cumprod()
    return float((curve / curve.cummax() - 1.0).min())


def sharpe(returns: pd.Series, periods: int) -> float:
    r = returns.dropna()
    if len(r) < 3 or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * math.sqrt(periods))


def deflated_sharpe(sr_annual: float, n_trials: int, T: int, periods: int) -> float:
    """Bailey & Lopez de Prado: P(true Sharpe > 0) after n_trials, for a per-period Sharpe."""
    if not np.isfinite(sr_annual):
        return float("nan")
    e = 0.5772156649
    sr = sr_annual / math.sqrt(periods)
    z1 = NormalDist().inv_cdf(1 - 1 / max(n_trials, 2))
    z2 = NormalDist().inv_cdf(1 - 1 / (max(n_trials, 2) * e))
    sr0 = math.sqrt(1 / T) * ((1 - e) * z1 + e * z2)
    denom = math.sqrt(max(1e-9, 1 - sr * sr / 4))
    return float(NormalDist().cdf((sr - sr0) * math.sqrt(T - 1) / denom))


def hac_alpha(y: pd.Series, x: pd.Series, lags: int = 1) -> dict:
    """Intercept and HAC t from a regression of y on x."""
    d = pd.concat([y, x], axis=1).dropna()
    if len(d) < 8:
        return {"alpha": float("nan"), "t": float("nan"), "n": int(len(d))}
    yy = d.iloc[:, 0]
    xx = sm.add_constant(d.iloc[:, 1])
    fit = sm.OLS(yy, xx).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {"alpha": float(fit.params.iloc[0]), "t": float(fit.tvalues.iloc[0]),
            "n": int(len(d))}


def mad_winsor_row(row: pd.Series, k: float = 3.0) -> pd.Series:
    r = row.dropna()
    if len(r) < 5:
        return row
    med = r.median()
    mad = (r - med).abs().median() * 1.4826
    if not np.isfinite(mad) or mad == 0:
        return row
    return row.clip(med - k * mad, med + k * mad)


def pct_rank(df: pd.DataFrame, min_names: int = 5) -> pd.DataFrame:
    """Cross-sectional percentile rank per row; rows with too few names are NaN."""
    rank = df.rank(axis=1, pct=True)
    rank[df.notna().sum(axis=1) < min_names] = np.nan
    return rank


# --------------------------------------------------------------------------- evaluation
def evaluate_cross_section(df: pd.DataFrame, date_col: str, signal: str, target: str,
                           min_n: int = 5, quantiles: int = 5,
                           spread_mode: str = "q5q1") -> dict:
    """Rank IC and spread from a long-format frame with one row per date/name."""
    ics, spreads, tops, alls, top_hits, dates = [], [], [], [], [], []
    for d, g in df.groupby(date_col, sort=True):
        g = g[[signal, target]].dropna()
        if len(g) < min_n:
            continue
        ic = rank_ic(g[signal], g[target])
        if not np.isfinite(ic):
            continue
        ics.append(ic)
        dates.append(d)
        if spread_mode == "q5q1":
            try:
                bins = pd.qcut(g[signal].rank(method="first"), quantiles, labels=False,
                               duplicates="drop")
            except ValueError:
                continue
            if pd.Series(bins).nunique() < 2:
                continue
            top = g.loc[bins == bins.max(), target].mean()
            bot = g.loc[bins == bins.min(), target].mean()
            spreads.append(top - bot)
            tops.append(top)
        else:  # top vs all
            thr = g[signal].quantile(0.8)
            top = g.loc[g[signal] >= thr, target].mean()
            spreads.append(top - g[target].mean())
            tops.append(top)
        alls.append(g[target].mean())
        top_hits.append(float(top > 0))
    if len(ics) < 5:
        return {"n": len(ics), "verdict": "NO DATA"}
    ic_s = pd.Series(ics, index=pd.Index(dates))
    sp_s = pd.Series(spreads, index=pd.Index(dates))
    ic_boot = block_bootstrap(ic_s)
    sp_boot = block_bootstrap(sp_s)
    top_boot = block_bootstrap(tops)
    t_ic = nw_t(ic_s, lags=max(1, 4))
    return {
        "n_dates": int(len(ic_s)),
        "ic": ic_boot["mean"], "ic_lo": ic_boot["lo"], "ic_hi": ic_boot["hi"],
        "ic_t": float(t_ic), "ic_p": normal_p(float(t_ic)),
        "ic_hit": float((ic_s > 0).mean()),
        "spread_bps": sp_boot["mean"] * 1e4,
        "spread_lo_bps": sp_boot["lo"] * 1e4,
        "spread_hi_bps": sp_boot["hi"] * 1e4,
        "spread_net_bps": sp_boot["mean"] * 1e4 - COST_BPS,
        "top_bps": top_boot["mean"] * 1e4,
        "top_lo_bps": top_boot["lo"] * 1e4,
        "top_hi_bps": top_boot["hi"] * 1e4,
        "all_bps": float(pd.Series(alls).mean() * 1e4),
        "top_hit": float(pd.Series(top_hits).mean()),
    }


def classify_cross_section(r: dict) -> str:
    if r.get("verdict") == "NO DATA":
        return "NO DATA"
    ic_ok = r["ic"] > 0 and r["ic_lo"] > 0
    spread_ok = r["spread_net_bps"] > 0
    if ic_ok and spread_ok:
        return "FORECASTS"
    if ic_ok:
        return "WEAK FORECAST"
    return "NO FORECAST"


# --------------------------------------------------------------------------- loaders
def load_panel() -> dict[str, pd.DataFrame]:
    out = {}
    for name in ("open", "high", "low", "close", "volume"):
        df = pd.read_csv(DATA / "panel" / f"{name}.csv", index_col=0, parse_dates=True)
        df.index = df.index.normalize()
        out[name] = df.sort_index()
    return out


def load_hourly(name: str) -> dict[str, pd.DataFrame]:
    out = {}
    for field in ("open", "close", "volume"):
        df = pd.read_csv(DATA / name / f"{field}.csv", index_col=0, parse_dates=True)
        out[field] = df.sort_index()
    out["open"] = out["open"].astype(float)
    out["close"] = out["close"].astype(float)
    out["volume"] = out["volume"].astype(float)
    return out


def load_trend(symbols: list[str]) -> pd.DataFrame:
    etfs = {"SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "SLV", "USO", "UNG",
            "DBA", "CPER", "BIL"}
    cols = {}
    for s in symbols:
        path = DATA / "trend" / f"{s}.csv"
        if not path.exists():
            continue
        d = pd.read_csv(path)
        d["date"] = pd.to_datetime(d["dt"], utc=True).dt.tz_convert(None).dt.normalize()
        col = "adj_close" if s in etfs else "close"
        cols[s] = d.groupby("date")[col].last()
    px = pd.DataFrame(cols).sort_index()
    spy = px["SPY"].dropna().index if "SPY" in px else px.dropna(how="all").index
    return px.reindex(spy, method="ffill")


def load_funding(coins: list[str]) -> pd.DataFrame:
    rows = []
    for c in coins:
        path = DATA / "settle" / "funding" / f"{c}USDT.json"
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        f = pd.DataFrame(raw)
        if f.empty or "fundingTime" not in f:
            continue
        f["date"] = pd.to_datetime(f["fundingTime"], unit="ms", utc=True).dt.tz_convert(
            None).dt.normalize()
        f["rate"] = pd.to_numeric(f["fundingRate"], errors="coerce")
        g = f.dropna(subset=["rate"]).groupby("date")["rate"].agg(["sum", "count"])
        if g.empty:
            continue
        # normalise a partial day to three 8-hour settlements
        g["ann"] = g["sum"] / g["count"] * 3.0 * 365.0
        g["coin"] = c
        rows.append(g.reset_index()[["date", "coin", "ann"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


# --------------------------------------------------------------------------- tests
def test_1_funding(panel: dict[str, pd.DataFrame]) -> dict:
    close, op, vol = panel["close"], panel["open"], panel["volume"]
    funding = load_funding(list(close.columns))
    if funding.empty:
        return {"verdict": "NO DATA"}
    # signal at the close of day t from funding settled during day t
    sig = funding.pivot(index="date", columns="coin", values="ann").reindex(close.index)
    sig = sig.ffill(limit=2)
    med = sig.rolling(30, min_periods=20).median().shift(0)
    mad = (sig - med).abs().rolling(30, min_periods=20).median() * 1.4826
    z = (sig - med) / mad.replace(0, np.nan)
    score = -z
    dollar = (close * vol).rolling(30, min_periods=20).mean()
    eligible = close.notna() & op.notna() & (dollar >= 1e6)
    targets = {}
    for h in (1, 3):
        targets[h] = close.shift(-h) / op.shift(-1) - 1.0
    out = {}
    for h in (1, 3):
        rows = []
        for d in close.index:
            if not (pd.Timestamp(DAILY_VALID_FROM) <= d <= pd.Timestamp(DAILY_CUT)):
                continue
            m = eligible.loc[d]
            names = m[m].index
            for c in names:
                if c in COLLISIONS:
                    continue
                s, y = score.at[d, c], targets[h].at[d, c]
                if pd.notna(s) and pd.notna(y) and abs(y) <= MAX_ABS_FWD:
                    rows.append({"date": d, "coin": c, "signal": s, "target": y})
        df = pd.DataFrame(rows)
        out[f"{h}d"] = evaluate_cross_section(df, "date", "signal", "target",
                                             spread_mode="top") if len(df) else {"verdict": "NO DATA"}
    primary = out["1d"]
    if primary.get("verdict") != "NO DATA":
        primary["verdict"] = classify_cross_section(primary)
    # design window, same construction, information only
    rows = []
    for d in close.index:
        if not (close.index.min() <= d <= pd.Timestamp(DAILY_DESIGN_END)):
            continue
        m = eligible.loc[d]
        for c in m[m].index:
            if c in COLLISIONS:
                continue
            s, y = score.at[d, c], targets[1].at[d, c]
            if pd.notna(s) and pd.notna(y) and abs(y) <= MAX_ABS_FWD:
                rows.append({"date": d, "coin": c, "signal": s, "target": y})
    design = evaluate_cross_section(pd.DataFrame(rows), "date", "signal", "target",
                                   spread_mode="top") if rows else {"verdict": "NO DATA"}
    return {"primary": primary, "secondary_3d": out["3d"], "design_1d": design,
            "coins": int(funding["coin"].nunique())}


def test_4_tsmom() -> dict:
    symbols = ["SPY", "TLT", "GLD", "USO", "BTC-USD", "ETH-USD"]
    px = load_trend(symbols).dropna(how="all")
    px = px.loc["2016-10-31":]
    monthly = px.resample("ME").last()
    ret_next = monthly.pct_change().shift(-1)
    # the 252-day lookback is on daily closes, then read at the month end
    sig = (px / px.shift(252) - 1.0).resample("ME").last()
    eligible = monthly.notna() & (monthly.notna().cumsum() >= 1) & sig.notna()
    long = (sig > 0) & eligible
    w = long.div(long.sum(axis=1).replace(0, np.nan), axis=0).clip(upper=1 / 6)
    w = w.fillna(0.0)
    bench = eligible.div(eligible.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    costs = (w - w.shift(1)).abs().sum(axis=1) * 10 / 1e4
    bcosts = (bench - bench.shift(1)).abs().sum(axis=1) * 10 / 1e4
    port = (w * ret_next).sum(axis=1) - costs
    bmk = (bench * ret_next).sum(axis=1) - bcosts
    valid = pd.Timestamp(TREND_VALID_FROM)
    pv = port.loc[valid:].dropna()
    bv = bmk.loc[valid:].dropna()
    idx = pv.index.intersection(bv.index)
    pv, bv = pv.loc[idx], bv.loc[idx]
    if len(pv) < 12:
        return {"verdict": "NO DATA"}
    exp = bv * (pv.std() / bv.std()) if bv.std() > 0 else bv
    alpha = hac_alpha(pv, bv, lags=1)
    # forecast: pooled asset-month rank IC
    rows = []
    for d in monthly.index:
        if d < pd.Timestamp(TREND_VALID_FROM):
            continue
        for s in symbols:
            a, b = sig.at[d, s], ret_next.at[d, s]
            if pd.notna(a) and pd.notna(b):
                rows.append({"date": d, "coin": s, "signal": a, "target": b})
    fc = evaluate_cross_section(pd.DataFrame(rows), "date", "signal", "target",
                               min_n=3, spread_mode="top") if rows else {"verdict": "NO DATA"}
    sr = sharpe(pv, 12)
    pass_ = bool(sr > sharpe(exp, 12) and alpha["t"] >= 2.0)
    return {
        "verdict": "PASS" if pass_ else "FAIL",
        "validation_months": int(len(pv)),
        "cagr": float((1 + pv).prod() ** (12 / len(pv)) - 1),
        "sharpe": sr,
        "bench_sharpe": sharpe(bv, 12),
        "exposure_matched_sharpe": sharpe(exp, 12),
        "maxdd": max_drawdown(pv),
        "bench_maxdd": max_drawdown(bv),
        "deflated_sharpe_p": deflated_sharpe(sr, 4, len(pv), 12),
        "alpha": alpha,
        "alpha_t": alpha["t"],
        "forecast": fc,
        "design_sharpe": sharpe(port.loc[:pd.Timestamp(TREND_DESIGN_END)], 12),
        "design_bench_sharpe": sharpe(bmk.loc[:pd.Timestamp(TREND_DESIGN_END)], 12),
    }


def test_8_multifactor(panel: dict[str, pd.DataFrame]) -> dict:
    close, op, vol = panel["close"], panel["open"], panel["volume"]
    ret = close.pct_change(fill_method=None)
    mom30 = (close / close.shift(30) - 1.0).shift(1)
    rev3 = -(close / close.shift(3) - 1.0)
    lowvol = -ret.rolling(30, min_periods=30).std() * np.sqrt(365)
    dollar = (close * vol).rolling(30, min_periods=30).mean()
    eligible = close.notna() & (dollar >= 1e6) & (close.notna().cumsum() >= 365)
    factors = [mom30, rev3, lowvol]
    ranks = []
    for f in factors:
        w = f.apply(mad_winsor_row, axis=1)
        ranks.append(pct_rank(w.where(eligible)))
    comp = sum(ranks) / len(ranks)
    target = close.shift(-5) / op.shift(-1) - 1.0
    # weekly, Sunday close
    days = close.index[close.index.dayofweek == 6]
    days = [d for d in days if d <= pd.Timestamp(DAILY_CUT)]
    rows = []
    for d in days:
        if d < pd.Timestamp(MF_VALID_FROM):
            continue
        m = eligible.loc[d]
        for c in m[m].index:
            if c in COLLISIONS:
                continue
            s, y = comp.at[d, c], target.at[d, c]
            if pd.notna(s) and pd.notna(y) and abs(y) <= MAX_ABS_FWD:
                rows.append({"date": d, "coin": c, "signal": s, "target": y})
    fc = evaluate_cross_section(pd.DataFrame(rows), "date", "signal", "target",
                                min_n=5, spread_mode="q5q1") if rows else {"verdict": "NO DATA"}
    if fc.get("verdict") != "NO DATA":
        fc_ok = fc["ic"] > 0 and fc["ic_lo"] > 0 and fc["spread_net_bps"] > 0
        fc["verdict"] = "FORECASTS" if fc_ok else ("WEAK FORECAST" if
                                                   (fc["ic"] > 0 and fc["ic_lo"] > 0) else
                                                   "NO FORECAST")
    # design window
    drows = []
    for d in days:
        if d > pd.Timestamp(MF_DESIGN_END):
            continue
        m = eligible.loc[d]
        for c in m[m].index:
            if c in COLLISIONS:
                continue
            s, y = comp.at[d, c], target.at[d, c]
            if pd.notna(s) and pd.notna(y) and abs(y) <= MAX_ABS_FWD:
                drows.append({"date": d, "coin": c, "signal": s, "target": y})
    design = evaluate_cross_section(pd.DataFrame(drows), "date", "signal", "target",
                                   min_n=5, spread_mode="q5q1") if drows else {"verdict": "NO DATA"}
    # alphabetical control: alphabetical rank in place of the composite
    arows = []
    for d in days:
        if d < pd.Timestamp(MF_VALID_FROM):
            continue
        m = eligible.loc[d]
        names = sorted(c for c in m[m].index if c not in COLLISIONS)
        if len(names) < 5:
            continue
        score = pd.Series(np.arange(len(names)) / max(1, len(names) - 1), index=names)
        for c in names:
            y = target.at[d, c]
            if pd.notna(y) and abs(y) <= MAX_ABS_FWD:
                arows.append({"date": d, "coin": c, "signal": float(score[c]), "target": y})
    alpha_ctl = evaluate_cross_section(pd.DataFrame(arows), "date", "signal", "target",
                                      min_n=5, spread_mode="q5q1") if arows else {"verdict": "NO DATA"}
    return {"primary": fc, "design": design, "alphabetical_control": alpha_ctl,
            "coins": int(eligible.iloc[-1].sum())}


def test_9b_leadlag() -> dict:
    h = load_hourly("panel_hourly")
    close, op, vol = h["close"], h["open"], h["volume"]
    ret = close.pct_change(fill_method=None)
    if "BTC" not in ret.columns:
        return {"verdict": "NO DATA"}
    btc = ret["BTC"]
    beta = ret.rolling(168).cov(btc).div(btc.rolling(168).var(), axis=0)
    # #9b's signal is the beta-scaled gap: beta * r_BTC - r_i, not the raw leader return
    lead = beta.mul(btc, axis=0) - ret
    rev1 = -ret
    leadlag_1h = pd.DataFrame({c: btc - ret[c] for c in ret.columns})
    target = close.shift(-3) / op.shift(-1) - 1.0
    dollar = (close * vol).rolling(168, min_periods=168).mean()
    eligible = (close.notna() & (close.notna().cumsum() >= 720) & (dollar >= 50_000)
                & (close.columns != "BTC"))
    if isinstance(eligible, pd.Series):
        eligible = pd.DataFrame({c: eligible for c in close.columns})
    eligible = eligible.loc[:, close.columns != "BTC"]
    out = {}
    for label, sig in (("leadlag_beta_1h", lead), ("leadlag_1h", leadlag_1h), ("rev_1", rev1)):
        rows = []
        for d in close.index:
            if not (pd.Timestamp(H_VALID_FROM) <= d):
                continue
            m = eligible.loc[d]
            for c in m[m].index:
                s, y = sig.at[d, c], target.at[d, c]
                if pd.notna(s) and pd.notna(y) and np.isfinite(s):
                    rows.append({"date": d, "coin": c, "signal": s, "target": y})
        df = pd.DataFrame(rows)
        if df.empty:
            out[label] = {"verdict": "NO DATA"}
            continue
        # non-overlapping: keep every third hour of the validation window
        df = df[df["date"].dt.hour % 3 == 0]
        ev = evaluate_cross_section(df, "date", "signal", "target", min_n=5,
                                    spread_mode="q5q1")
        # full hourly series for the NW t (overlapping labels)
        full = pd.DataFrame(rows)
        ics = []
        for d, g in full.groupby("date"):
            g = g[["signal", "target"]].dropna()
            if len(g) >= 5:
                ic = rank_ic(g["signal"], g["target"])
                if np.isfinite(ic):
                    ics.append(ic)
        ev["nw_t_hourly"] = nw_t(pd.Series(ics), lags=4) if len(ics) > 3 else float("nan")
        if ev.get("verdict") != "NO DATA":
            ev["verdict"] = classify_cross_section(ev)
        out[label] = ev
    primary = out["leadlag_beta_1h"]
    return {"primary": primary, "leadlag_1h": out["leadlag_1h"], "rev_1": out["rev_1"],
            "hours": int(close.shape[0])}


def test_15_trend() -> dict:
    symbols = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "SLV", "USO", "UNG",
               "DBA", "CPER", "BTC-USD", "ETH-USD", "SOL-USD"]
    px = load_trend(symbols).dropna(how="all")
    px = px.loc["2016-10-31":]
    weekly = px.resample("W-FRI").last()
    daily_ret = px.pct_change(fill_method=None)
    vol = daily_ret.rolling(30, min_periods=20).std() * np.sqrt(252)
    vol_w = vol.resample("W-FRI").last()
    r1 = weekly / weekly.shift(4) - 1.0     # ~1 month of weeks
    r3 = weekly / weekly.shift(13) - 1.0
    r12 = weekly / weekly.shift(52) - 1.0
    score = (np.sign(r1) + np.sign(r3) + np.sign(r12)) / 3.0
    ret_next = weekly.pct_change().shift(-1)
    long = (score > 0)
    size = (0.20 / vol_w).clip(upper=2.0)
    nlong = long.sum(axis=1).replace(0, np.nan)
    w = (size * long).div(nlong, axis=0)
    gross = w.sum(axis=1)
    w = w.div(gross.where(gross <= 1.0, gross), axis=0).fillna(0.0)
    bench = size.div(size.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    costs = (w - w.shift(1)).abs().sum(axis=1) * 10 / 1e4
    bcosts = (bench - bench.shift(1)).abs().sum(axis=1) * 10 / 1e4
    port = (w * ret_next).sum(axis=1) - costs
    bmk = (bench * ret_next).sum(axis=1) - bcosts
    valid = pd.Timestamp(TREND_VALID_FROM)
    pv = port.loc[valid:].dropna()
    bv = bmk.loc[valid:].dropna()
    idx = pv.index.intersection(bv.index)
    pv, bv = pv.loc[idx], bv.loc[idx]
    if len(pv) < 12:
        return {"verdict": "NO DATA"}
    diff = pv - bv * (pv.std() / bv.std()) if bv.std() > 0 else pv - bv
    t = nw_t(diff, lags=4)
    # forecast: pooled asset-week rank IC
    rows = []
    for d in weekly.index:
        if d < valid:
            continue
        for s in symbols:
            a, b = score.at[d, s], ret_next.at[d, s]
            if pd.notna(a) and pd.notna(b):
                rows.append({"date": d, "coin": s, "signal": a, "target": b})
    fc = evaluate_cross_section(pd.DataFrame(rows), "date", "signal", "target",
                               min_n=5, spread_mode="top") if rows else {"verdict": "NO DATA"}
    return {
        "verdict": "ADDS RETURN" if (diff.mean() > 0 and t >= 2.0) else "NO RETURN BEYOND VOL",
        "weeks": int(len(pv)),
        "trend_sharpe": sharpe(pv, 52),
        "bench_sharpe": sharpe(bv, 52),
        "mean_diff_bps": float(diff.mean() * 1e4),
        "diff_t": float(t),
        "trend_cagr": float((1 + pv).prod() ** (52 / len(pv)) - 1),
        "bench_cagr": float((1 + bv).prod() ** (52 / len(bv)) - 1),
        "forecast": fc,
        "design_diff_t": float(nw_t((port.loc[:pd.Timestamp(TREND_DESIGN_END)] -
                                     bmk.loc[:pd.Timestamp(TREND_DESIGN_END)]).dropna(), 4)),
    }


def clustered_mean(df: pd.DataFrame, col: str, day_col: str = "day") -> dict:
    g = df.dropna(subset=[col]).groupby(day_col)[col].agg(["sum", "count"])
    if len(g) < 3:
        return {"mean_bps": float("nan"), "t": float("nan"), "days": int(len(g))}
    total = g["count"].sum()
    m = g["sum"].sum() / total
    k = len(g)
    se = math.sqrt(k / (k - 1) * ((g["sum"] - m * g["count"]) ** 2).sum()) / total
    day_mean = (g["sum"] / g["count"]).mean()
    day_t = nw_t((g["sum"] / g["count"]), lags=1)
    return {"mean_bps": float(m * 1e4), "t": float(m / se), "days": int(k),
            "day_mean_bps": float(day_mean * 1e4), "day_t": float(day_t),
            "events": int(total)}


def test_43_horizons() -> dict:
    lows = pd.read_csv(DATA / "events" / "lows_events.csv.gz")
    lows = lows[lows["direction"] == "down"]
    h1 = clustered_mean(lows, "r60")
    h4 = clustered_mean(lows, "r240")
    trades = pd.read_csv(DATA / "events" / "horizons_s1_12h_trades.csv.gz")
    trades["day"] = pd.to_datetime(trades["day"])
    holdout = trades[trades["day"] >= "2025-01-01"]
    selection = trades[trades["day"] < "2025-01-01"]
    h12 = clustered_mean(holdout, "net")
    h12_sel = clustered_mean(selection, "net")
    cells = pd.read_csv(DATA / "events" / "horizons_cells.csv")
    s1 = cells[(cells["signal"] == "S1") & (cells["h"] == "12h")]
    bar = 4.09
    survives = bool(h12["mean_bps"] > 0 and h12["t"] >= bar)
    return {
        "verdict": "CONFIRMED STANDS" if survives else "CONFIRMED DOES NOT SURVIVE",
        "s1_1h": h1, "s1_4h": h4, "s1_12h": h12, "s1_12h_selection": h12_sel,
        "deflated_bar": bar,
        "published": s1.to_dict("records")[0] if len(s1) else None,
        "note": "12 h uses the published trade file's net return; 1 h and 4 h are gross event returns",
    }


# --------------------------------------------------------------------------- main
def main() -> int:
    missing = [p for p in ("panel", "panel_hourly", "trend", "settle/funding", "events")
               if not (DATA / p).exists()]
    if missing:
        raise SystemExit(f"data_raw archives missing: {missing}; this script does not fetch data")
    panel = load_panel()
    tests = {
        "1_funding": test_1_funding(panel),
        "4_tsmom": test_4_tsmom(),
        "8_multifactor": test_8_multifactor(panel),
        "9b_leadlag": test_9b_leadlag(),
        "15_trend": test_15_trend(),
        "43_horizons": test_43_horizons(),
    }
    # BH across the six primary tests
    pvals = []
    keys = ["1_funding", "4_tsmom", "8_multifactor", "9b_leadlag", "15_trend", "43_horizons"]
    for k in keys:
        t = tests[k]
        if k == "1_funding":
            p = t.get("primary", {}).get("ic_p")
        elif k == "4_tsmom":
            p = normal_p(t.get("alpha_t", float("nan")))
        elif k == "8_multifactor":
            p = t.get("primary", {}).get("ic_p")
        elif k == "9b_leadlag":
            p = t.get("primary", {}).get("ic_p")
        elif k == "15_trend":
            p = normal_p(t.get("diff_t", float("nan")))
        else:
            p = normal_p(t.get("s1_12h", {}).get("t", float("nan")))
        pvals.append(float(p) if p is not None else float("nan"))
    qs = bh(pvals)
    for k, p, q in zip(keys, pvals, qs):
        tests[k]["p_primary"] = p
        tests[k]["q_primary"] = q
    payload = {
        "preregistration": "research/PREREGISTRATION_2026-11-01-remaining-findings.md",
        "cost_bps": COST_BPS,
        "data_filter": {"collision_tickers": sorted(COLLISIONS), "max_abs_forward_return": MAX_ABS_FWD},
        "data": {
            "panel": "data_raw/panel 42 coins 2021-10-27..2026-10-27",
            "panel_hourly": "data_raw/panel_hourly 39 coins 2025-10-27..2026-10-27",
            "trend": "data_raw/trend 56 series 2016-10..2026-10",
            "funding": "data_raw/settle/funding 42 coins 2019-12..2026-10",
            "events": "data_raw/events original event outputs",
        },
        "tests": tests,
    }
    OUT.write_text(json.dumps(payload, indent=1, default=str) + "\n")
    # short console summary
    for k in keys:
        t = tests[k]
        if k in ("1_funding", "8_multifactor"):
            r = t.get("primary", {})
            print(f"{k:16s} {r.get('verdict','?'):14s} IC {r.get('ic',float('nan')):+.3f} "
                  f"[{r.get('ic_lo',float('nan')):+.3f},{r.get('ic_hi',float('nan')):+.3f}] "
                  f"spread {r.get('spread_bps',float('nan')):+.1f} bps "
                  f"t {r.get('ic_t',float('nan')):+.2f} q {t.get('q_primary',float('nan')):.3f}")
        elif k == "9b_leadlag":
            r = t.get("primary", {})
            print(f"{k:16s} {r.get('verdict','?'):14s} IC {r.get('ic',float('nan')):+.3f} "
                  f"[{r.get('ic_lo',float('nan')):+.3f},{r.get('ic_hi',float('nan')):+.3f}] "
                  f"spread {r.get('spread_bps',float('nan')):+.1f} bps "
                  f"NW {r.get('nw_t_hourly',float('nan')):+.2f} q {t.get('q_primary',float('nan')):.3f}")
        elif k == "4_tsmom":
            print(f"{k:16s} {t.get('verdict','?'):14s} Sharpe {t.get('sharpe',float('nan')):.2f} "
                  f"exp-match {t.get('exposure_matched_sharpe',float('nan')):.2f} "
                  f"alpha t {t.get('alpha_t',float('nan')):+.2f} q {t.get('q_primary',float('nan')):.3f}")
        elif k == "15_trend":
            print(f"{k:16s} {t.get('verdict','?'):20s} diff {t.get('mean_diff_bps',float('nan')):+.1f} bps "
                  f"t {t.get('diff_t',float('nan')):+.2f} q {t.get('q_primary',float('nan')):.3f}")
        else:
            r = t.get("s1_12h", {})
            print(f"{k:16s} {t.get('verdict','?'):30s} 12h {r.get('mean_bps',float('nan')):+.1f} bps "
                  f"t {r.get('t',float('nan')):+.2f} q {t.get('q_primary',float('nan')):.3f}")
    print(f"[written {OUT.relative_to(ROOT)}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
