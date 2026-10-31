"""Strategies are pure functions of closed bars. They return a side, never an order.

The reference strategy here is plumbing, not evidence: a long-only 20/50 SMA cross with a
3% stop. It exists so the loop has something to decide. Anything promoted to a real test
must first pass the ledger gate (`reference/` has the old one; this project will have its own).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    side: str          # "buy" | "sell" | None
    reason: str


def sma(values: list[float], n: int) -> float:
    if len(values) < n:
        return float("nan")
    return sum(values[-n:]) / n


def sma_cross(bars: list[dict], fast: int = 20, slow: int = 50) -> Signal:
    """Long when the fast SMA is above the slow one, flat otherwise.

    Uses closed bars only. Truncation-invariant: the signal at bar t is unchanged if you
    delete every bar after t (there is a test for it).
    """
    closes = [b["close"] for b in bars]
    if len(closes) < slow + 1:
        return Signal(None, "not enough bars")
    f, s = sma(closes, fast), sma(closes, slow)
    f_prev, s_prev = sma(closes[:-1], fast), sma(closes[:-1], slow)
    if f > s and f_prev <= s_prev:
        return Signal("buy", f"SMA{fast} crossed above SMA{slow}")
    if f < s and f_prev >= s_prev:
        return Signal("sell", f"SMA{fast} crossed below SMA{slow}")
    return Signal(None, "no cross")


def sma_regime(bars: list[dict], fast: int = 20, slow: int = 50) -> Signal:
    """The same SMAs, read as a regime: long above, short below, flat when equal."""
    closes = [b["close"] for b in bars]
    if len(closes) < slow + 1:
        return Signal(None, "not enough bars")
    f, s = sma(closes, fast), sma(closes, slow)
    if f > s:
        return Signal("long", f"SMA{fast} above SMA{slow}")
    if f < s:
        return Signal("short", f"SMA{fast} below SMA{slow}")
    return Signal(None, "SMA cross exactly flat")


def stop_hit_long(entry_px: float, mark: float, stop_pct: float = 0.03) -> bool:
    return entry_px > 0 and mark <= entry_px * (1 - stop_pct)


def stop_hit_short(entry_px: float, mark: float, stop_pct: float = 0.03) -> bool:
    return entry_px > 0 and mark >= entry_px * (1 + stop_pct)


def stop_hit(entry_px: float, mark: float, stop_pct: float = 0.03) -> bool:
    """Long-side alias kept for callers that predate shorts."""
    return stop_hit_long(entry_px, mark, stop_pct)
