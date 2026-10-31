"""Execution simulator: impact from the depth table, then reprice the XS and carry books.

    python research/execution_sim.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
OUT = ROOT / "research" / "execution_sim.json"
FEE = 5e-4
UNIVERSE = [l.split(",")[0] for l in (ROOT / "research" / "xs_universe.csv").read_text().splitlines()[1:] if l]

spec = importlib.util.spec_from_file_location("xm", ROOT / "research" / "xs_momentum.py")
xm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xm)


def depth_liquidity() -> dict[str, float]:
    """Median notional within 1% of mid, per symbol."""
    con = duckdb.connect(str(DB), read_only=True)
    df = con.execute("""SELECT symbol, MEDIAN(notional) AS n1 FROM depth WHERE pct = 1 GROUP BY symbol""").df()
    con.close()
    return dict(zip(df["symbol"], df["n1"]))


def impact_bps(notional: float, n1: float) -> float:
    """Linear within the 1% band: notional that would move 1% costs proportionally."""
    if not n1 or n1 <= 0:
        return 100.0
    return min(100.0, 100.0 * notional / n1)


def xs_trades(year_from: int, year_to: int) -> tuple[list[dict], float]:
    """The exact weekly trades of the registered book, and the gross weekly return."""
    px, fu = xm.panel(year_from, year_to)
    rets = px.pct_change().fillna(0.0)
    signal = px / px.shift(30) - 1
    dates = px.index
    fridays = [d for d in dates if d.weekday() == 4]
    pos = pd.Series(0.0, index=px.columns)
    weeks = []
    gross = []
    for f in fridays[:-1]:
        sig = signal.loc[f].dropna()
        sig = sig[np.isfinite(sig)]
        if len(sig) < 10:
            continue
        k = max(1, len(sig) // 5)
        new = pd.Series(0.0, index=px.columns)
        new[sig.nlargest(k).index] = 1.0 / k
        new[sig.nsmallest(k).index] = -1.0 / k
        window = [d for d in dates if f < d <= f + pd.Timedelta(days=7)]
        if not window:
            continue
        wret = 0.0
        for d in window:
            wret += float((new * rets.loc[d]).sum()) - float((new * fu.loc[d].reindex(px.columns).fillna(0.0)).sum())
        gross.append(wret)
        traded = (new - pos).abs()
        weeks.append({s: float(traded[s]) for s in traded.index if traded[s] > 1e-12})
        pos = new
    return weeks, float(np.mean(gross)) * 52


def reprice_xs(year_from: int, year_to: int, capital_per_leg: float, liq: dict) -> tuple[float, float]:
    weeks, gross = xs_trades(year_from, year_to)
    fallback = float(np.median(list(liq.values()))) if liq else 0.0
    covered = total = 0
    costs = []
    for trades in weeks:
        c = 0.0
        for sym, dw in trades.items():
            total += 1
            if sym in liq:
                covered += 1
            n1 = liq.get(sym, fallback)          # peer median for symbols without a depth file
            notional = dw * capital_per_leg
            c += (FEE + impact_bps(notional, n1) / 1e4) * dw
        costs.append(c)
    return gross - 52 * float(np.mean(costs)), covered / max(total, 1)


def carry_reprice(capital_per_position: float, liq: dict, trades_per_year: float = 8.0) -> dict:
    """Impact added to the 30 bps round trip, per position, annualised."""
    extra = []
    for sym in xm.UNIVERSE[:15]:
        n1 = liq.get(sym, 0.0)
        bps = impact_bps(capital_per_position, n1)
        extra.append(2 * bps)                       # entry and exit
    add_bps = float(np.median(extra))
    drag = trades_per_year * add_bps / 1e4
    return {"median_added_bps_per_round_trip": add_bps, "annual_drag_pct": 100 * drag}


def main() -> int:
    liq = depth_liquidity()
    print(f"depth: {len(liq)} symbols; median 1%-band notional ${np.median(list(liq.values())):,.0f}")
    out = {"liquidity_symbols": len(liq),
           "median_1pct_notional_usd": float(np.median(list(liq.values())))}
    out["xs"] = {}
    for label, (y0, y1) in (("design", (2021, 2022)), ("holdout", (2023, 2023))):
        weeks, gross = xs_trades(y0, y1)
        row = {"gross_ann_pct": 100 * gross}
        for cap in (100_000, 1_000_000, 5_000_000, 10_000_000):
            net, cov = reprice_xs(y0, y1, cap, liq)
            row[f"net_at_{cap//1000}k"] = 100 * net
            row["depth_coverage"] = cov
        out["xs"][label] = row
    out["carry"] = {f"{c//1000}k": carry_reprice(c, liq) for c in (100_000, 1_000_000, 5_000_000)}
    (ROOT / "research" / "execution_sim.json").write_text(json.dumps(out, indent=1))
    for label, row in out["xs"].items():
        print(f"{label}: gross {row['gross_ann_pct']:+.1f}%/yr -> " +
              ", ".join(f"{k.replace('net_at_','')}: {v:+.1f}%" for k, v in row.items() if k.startswith("net_at_")))
    for k, v in out["carry"].items():
        print(f"carry at ${k}/position: +{v['median_added_bps_per_round_trip']:.0f} bps per round trip "
              f"-> {v['annual_drag_pct']:.1f}%/yr drag")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
