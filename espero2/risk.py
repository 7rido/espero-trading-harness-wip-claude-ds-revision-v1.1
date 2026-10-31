"""Risk primitives: ATR, volatility-target sizing, funding gate. Pure functions, no I/O.

Volatility targeting is the one measure in this project with repeatable forecasting skill (HAR-RV beat
EWMA on 35/38 symbols). Here it sizes a position so that a k-sigma adverse move costs ~risk_pct of
equity — it does not predict direction.
"""
from __future__ import annotations

import math


def true_range(bars: list[dict]) -> list[float]:
    out = []
    for i, b in enumerate(bars):
        high, low = float(b["high"]), float(b["low"])
        prev = float(bars[i - 1]["close"]) if i else float(b["close"])
        out.append(max(high - low, abs(high - prev), abs(low - prev)))
    return out


def atr(bars: list[dict], period: int = 14) -> float:
    """Wilder's ATR; 0.0 when there is not enough data."""
    tr = true_range(bars)
    if len(tr) < period:
        return 0.0
    value = sum(tr[:period]) / period
    for x in tr[period:]:
        value = (value * (period - 1) + x) / period
    return value


def realized_vol(bars: list[dict], periods_per_year: float) -> float:
    """Annualised close-to-close volatility from the bars as given."""
    closes = [float(b["close"]) for b in bars]
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
    if len(rets) < 5:
        return 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var * periods_per_year)


def stop_from_atr(bars: list[dict], k: float = 2.0, period: int = 14) -> float:
    """Absolute price distance for a stop, in the same units as the bars."""
    return k * atr(bars, period)


def vol_target_notional(equity: float, risk_pct: float, vol_annual: float,
                        horizon_days: float = 1.0, k: float = 2.0) -> float:
    """Notional such that a k-sigma move over the horizon loses ~risk_pct of equity."""
    if equity <= 0 or vol_annual <= 0 or risk_pct <= 0:
        return 0.0
    sigma = vol_annual * math.sqrt(horizon_days / 365.0)
    return k and (equity * risk_pct) / max(k * sigma, 1e-9)


def funding_annual_pct(funding_bps_hour: float) -> float:
    return 1e2 * funding_bps_hour / 1e4 * 24 * 365


def funding_gate(side: str, funding_bps_hour: float, max_annual_pct: float | None) -> bool:
    """True when the trade should be skipped: a long paying more than the cap, or a short paying it."""
    if max_annual_pct is None:
        return False
    ann = funding_annual_pct(funding_bps_hour)
    return (side == "long" and ann > max_annual_pct) or (side == "short" and ann < -max_annual_pct)
