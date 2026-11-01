"""Does volatility-target sizing beat fixed sizing on the same signal?

    python research/sizing_study.py

The SMA 20/50 regime is used only as a return stream (it is retired as a strategy). Both books see the
same signal, fills and 9 bps round-trip cost; only the position size rule differs.
"""
from __future__ import annotations

import json
import math
import pathlib

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
OUT = ROOT / "research" / "sizing_study.json"
COINS = ["BTC", "ETH", "BNB", "XRP", "ADA", "DOGE", "SOL", "LTC", "LINK", "AVAX"]
COST_BPS = 9.0
CAPITAL = 10_000.0
FIXED_NOTIONAL = 100.0
VOL_CAP = 500.0
RISK_PCT = 0.02
K_SIGMA = 2.0


def load() -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    rows = con.execute("""SELECT symbol, date, close FROM bars_daily
                          WHERE symbol IN ({}) ORDER BY date""".format(
        ",".join(f"'{c}USDT'" for c in COINS))).df()
    con.close()
    rows["date"] = pd.to_datetime(rows["date"])
    return rows.pivot(index="date", columns="symbol", values="close").dropna(how="all")


def signal(close: pd.DataFrame) -> pd.DataFrame:
    s = np.sign(close.rolling(20).mean() - close.rolling(50).mean())
    return s.fillna(0.0)


def vol_annual(close: pd.DataFrame) -> pd.DataFrame:
    r = close.pct_change()
    return r.rolling(20).std() * math.sqrt(365)


def simulate(close: pd.DataFrame, sig: pd.DataFrame, *, vol_target: bool,
             risk_pct: float = RISK_PCT, cap: float = VOL_CAP) -> tuple[pd.Series, pd.Series]:
    ret = close.pct_change().fillna(0.0)
    vol = vol_annual(close).shift(1).fillna(0.0)
    dates = close.index
    equity, pos = CAPITAL, pd.Series(0.0, index=close.columns)
    curve, gross = [], []
    for i, d in enumerate(dates):
        s = sig.loc[d].shift(1) if False else sig.shift(1).loc[d]   # signal known at previous close
        if i == 0:
            curve.append(equity)
            gross.append(0.0)
            continue
        if vol_target:
            notional = (equity * risk_pct / (K_SIGMA * vol.loc[d].replace(0, np.nan))).clip(upper=cap)
            notional = notional.fillna(0.0)
        else:
            notional = pd.Series(FIXED_NOTIONAL, index=close.columns) * (s.abs() > 0)
        target = s.fillna(0.0) * notional
        pnl = float((pos * ret.loc[d]).sum())
        cost = float((target - pos).abs().sum()) * COST_BPS / 1e4
        equity += pnl - cost
        pos = target
        curve.append(equity)
        gross.append(float(pos.abs().sum()))
    return pd.Series(curve, index=dates), pd.Series(gross, index=dates)


def stats(curve: pd.Series) -> dict:
    r = curve.pct_change().dropna()
    years = (curve.index[-1] - curve.index[0]).days / 365.25
    cagr = (curve.iloc[-1] / curve.iloc[0]) ** (1 / years) - 1 if years > 0 else float("nan")
    vol = r.std() * math.sqrt(365)
    sharpe = r.mean() / r.std() * math.sqrt(365) if r.std() else float("nan")
    dd = (curve / curve.cummax() - 1).min()
    return {"final": float(curve.iloc[-1]), "cagr": 100 * cagr, "vol": 100 * vol,
            "sharpe": float(sharpe), "max_dd": 100 * float(dd)}


def calibrate(close: pd.DataFrame, sig: pd.DataFrame) -> float:
    """Risk fraction whose vol-target book has the same average gross notional as the fixed book."""
    fixed_curve, fixed_gross = simulate(close, sig, vol_target=False)
    target = float(fixed_gross.mean())
    lo, hi = 1e-5, 0.05
    for _ in range(30):
        mid = (lo + hi) / 2
        _, g = simulate(close, sig, vol_target=True, risk_pct=mid)
        if g.mean() < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main() -> int:
    close = load()
    sig = signal(close)
    fixed_curve, fixed_gross = simulate(close, sig, vol_target=False)
    risk = calibrate(close, sig)
    cal_curve, cal_gross = simulate(close, sig, vol_target=True, risk_pct=risk)
    live_curve, live_gross = simulate(close, sig, vol_target=True)
    out = {"period": [str(close.index[0].date()), str(close.index[-1].date())],
           "coins": len(close.columns), "capital": CAPITAL, "cost_bps": COST_BPS,
           "fixed": {**stats(fixed_curve), "avg_gross": float(fixed_gross.mean())},
           "vol_target_matched": {**stats(cal_curve), "risk_pct": 100 * risk,
                                  "avg_gross": float(cal_gross.mean())},
           "vol_target_live": {**stats(live_curve), "risk_pct": 100 * RISK_PCT,
                               "avg_gross": float(live_gross.mean())}}
    OUT.write_text(json.dumps(out, indent=1))
    print(f"period {out['period'][0]} → {out['period'][1]} · {len(close.columns)} coins · "
          f"capital ${CAPITAL:,.0f} · cost {COST_BPS} bps\n")
    print(f"{'book':22s} {'final':>12s} {'CAGR':>8s} {'vol':>7s} {'Sharpe':>7s} {'maxDD':>8s} "
          f"{'avg gross':>10s}")
    for name, s in (("fixed $100", out["fixed"]),
                    (f"vol-target {100*risk:.3f}% (matched)", out["vol_target_matched"]),
                    (f"vol-target {100*RISK_PCT:.1f}% (live)", out["vol_target_live"])):
        print(f"{name:22s} ${s['final']:>11,.0f} {s['cagr']:>7.1f}% {s['vol']:>6.1f}% "
              f"{s['sharpe']:>7.2f} {s['max_dd']:>7.1f}% {s['avg_gross']:>9,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
