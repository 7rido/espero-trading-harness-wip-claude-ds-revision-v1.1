"""Backtest the paper rule on the committed panel — the step the paper loop skipped.

Rule (identical to `strategy.sma_regime` and `paper.tick`): at each close, long if SMA20 > SMA50,
short if below. Fills at the **next open** (never the signal bar), taker cost per side, one signed
position per coin, each coin its own $1,000 book, 1x notional, liquidation at ~1.99x against a short.
Daily marks keyed by date, so late listings and gaps do not shift the portfolio. Funding is not
included — the panel is daily and the paper engine's funding is hourly.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

Series = List[Optional[float]]
Equity = Dict[str, float]


@dataclass
class Costs:
    fee_bps: float = 4.5
    slip_bps: float = 2.0


@dataclass
class Book:
    coin: str
    equity: Equity = field(default_factory=dict)
    trades: int = 0
    fees: float = 0.0
    liquidations: int = 0


def load_panel(panel: Path) -> tuple[List[str], Dict[str, Dict[str, Series]]]:
    out: Dict[str, Dict[str, Series]] = {}
    dates: List[str] = []
    for name in ("open", "close"):
        with (panel / f"{name}.csv").open() as f:
            rows = list(csv.reader(f))
        dates = [r[0] for r in rows[1:]]
        cols: Dict[str, Series] = {}
        for j, coin in enumerate(rows[0][1:]):
            series: Series = []
            for r in rows[1:]:
                v = r[j + 1].strip()
                try:
                    series.append(float(v) if v else None)
                except ValueError:
                    series.append(None)
            cols[coin] = series
        out[name] = cols
    return dates, out


def sma(series: Series, i: int, n: int) -> Optional[float]:
    if i + 1 < n:
        return None
    window = series[i + 1 - n: i + 1]
    if any(v is None for v in window):
        return None
    return sum(window) / n  # type: ignore[arg-type]


def regime(closes: Series, i: int, fast: int = 20, slow: int = 50) -> int:
    f, s = sma(closes, i, fast), sma(closes, i, slow)
    if f is None or s is None or f == s:
        return 0
    return 1 if f > s else -1


def run_coin(coin: str, dates: List[str], opens: Series, closes: Series,
             costs: Costs, initial: float = 1000.0, long_only: bool = False) -> Book:
    book = Book(coin)
    cash, qty, entry = initial, 0.0, 0.0
    for i in range(len(closes) - 1):
        mark = closes[i + 1]
        if closes[i] is None or mark is None:
            continue
        want = regime(closes, i)
        if long_only and want < 0:
            want = 0
        px = opens[i + 1] if opens[i + 1] is not None else mark
        held = 1 if qty > 0 else (-1 if qty < 0 else 0)

        if want != held:
            if held:                                          # close, paying one side
                fill = px * (1 - costs.slip_bps / 1e4) if held > 0 else px * (1 + costs.slip_bps / 1e4)
                fee = abs(qty) * fill * costs.fee_bps / 1e4
                cash += qty * fill - fee
                book.fees += fee
                book.trades += 1
                qty = 0.0
            if want:                                          # open the other side, one side
                fill = px * (1 + costs.slip_bps / 1e4) if want > 0 else px * (1 - costs.slip_bps / 1e4)
                qty = (cash / fill) * want
                fee = abs(qty) * fill * costs.fee_bps / 1e4
                cash -= qty * fill + fee
                book.fees += fee
                book.trades += 1
                entry = fill

        # the venue closes a 1x short at ~1.99x (a long at ~0.01x) before equity can go negative
        if qty != 0:
            liq = entry * 1.99 if qty < 0 else entry * 0.01
            if (qty < 0 and mark >= liq) or (qty > 0 and mark <= liq):
                fee = abs(qty) * liq * costs.fee_bps / 1e4
                cash += qty * liq - fee
                book.fees += fee
                book.trades += 1
                book.liquidations += 1
                qty = 0.0
        book.equity[dates[i + 1]] = cash + qty * mark
    return book


def stats(equity: List[float]) -> dict:
    if len(equity) < 2 or not equity[0] or equity[0] <= 0:
        return {"total_pct": 0.0, "cagr_pct": 0.0, "sharpe": 0.0, "maxdd_pct": 0.0, "n": len(equity)}
    rets = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity)) if equity[i - 1]]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)
    sd = math.sqrt(var)
    sharpe = (mean / sd * math.sqrt(365)) if sd else 0.0
    peak, maxdd = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        maxdd = min(maxdd, v / peak - 1)
    years = len(equity) / 365
    total = equity[-1] / equity[0] - 1
    ratio = equity[-1] / equity[0]
    cagr = (ratio ** (1 / years) - 1) if years > 0 and ratio > 0 else -1.0
    return {"total_pct": 100 * total, "cagr_pct": 100 * cagr, "sharpe": sharpe,
            "maxdd_pct": 100 * maxdd, "n": len(equity)}


def _series_on(dates: List[str], per_date: Dict[str, float]) -> List[float]:
    return [per_date[d] for d in dates if d in per_date]


def run_panel(panel: Path, costs: Costs = Costs(), long_only: bool = False) -> dict:
    dates, data = load_panel(panel)
    books: Dict[str, Book] = {}
    for coin, closes in data["close"].items():
        opens = data["open"].get(coin, [None] * len(closes))
        book = run_coin(coin, dates, opens, closes, costs, long_only=long_only)
        if len(book.equity) > 1:
            books[coin] = book

    all_dates = sorted({d for b in books.values() for d in b.equity})
    portfolio = []
    for d in all_dates:
        vals = [b.equity[d] for b in books.values() if d in b.equity]
        if vals:
            portfolio.append(sum(vals) / len(vals))

    benchmarks = {}
    btc = data["close"].get("BTC", [])
    first = next((v for v in btc if v is not None), None)
    if first:
        b = {d: 1000 * v / first for d, v in zip(dates, btc) if v is not None}
        benchmarks["BTC buy & hold"] = stats(_series_on(all_dates, b))
    ewm: Dict[str, List[float]] = {}
    for coin, closes in data["close"].items():
        f = next((v for v in closes if v is not None), None)
        if not f:
            continue
        for d, v in zip(dates, closes):
            if v is None:
                continue
            ewm.setdefault(d, []).append(1000 * v / f)
    if ewm:
        avg = {d: sum(v) / len(v) for d, v in ewm.items()}
        benchmarks["equal-weight hold"] = stats(_series_on(all_dates, avg))

    per_coin = {c: stats(list(b.equity.values())) for c, b in books.items()}
    ranked = sorted(per_coin.items(), key=lambda kv: kv[1]["cagr_pct"], reverse=True)
    return {"dates": all_dates, "portfolio": portfolio, "stats": stats(portfolio),
            "books": {c: {"trades": b.trades, "fees": b.fees, "liquidations": b.liquidations}
                      for c, b in books.items()},
            "per_coin": dict(ranked), "benchmarks": benchmarks, "long_only": long_only,
            "costs": {"fee_bps": costs.fee_bps, "slip_bps": costs.slip_bps}}


def format_report(r: dict) -> str:
    s = r["stats"]
    lines = [
        f"panel: {len(r['portfolio'])} dates · {len(r['books'])} coins · "
        f"{r['costs']['fee_bps']}+{r['costs']['slip_bps']} bps/side"
        f"{' · long-only' if r['long_only'] else ' · long/short'}",
        "",
        f"{'book':18s} {'total%':>10s} {'cagr%':>8s} {'sharpe':>7s} {'maxdd%':>8s}",
        f"{'portfolio':18s} {s['total_pct']:10.1f} {s['cagr_pct']:8.2f} {s['sharpe']:7.2f} {s['maxdd_pct']:8.1f}",
    ]
    for name, b in r.get("benchmarks", {}).items():
        lines.append(f"{name:18s} {b['total_pct']:10.1f} {b['cagr_pct']:8.2f} {b['sharpe']:7.2f} {b['maxdd_pct']:8.1f}")
    best = list(r["per_coin"].items())[:5]
    worst = list(r["per_coin"].items())[-5:]
    lines += ["",
              "best coins:  " + ", ".join(f"{c} {v['cagr_pct']:+.1f}%" for c, v in best),
              "worst coins: " + ", ".join(f"{c} {v['cagr_pct']:+.1f}%" for c, v in worst)]
    trades = sum(b["trades"] for b in r["books"].values())
    fees = sum(b["fees"] for b in r["books"].values())
    liq = sum(b["liquidations"] for b in r["books"].values())
    lines.append(f"trades {trades} · fees ${fees:,.0f} · liquidations {liq} across {len(r['books'])} books")
    return "\n".join(lines)
