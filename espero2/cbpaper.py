"""Coinbase spot paper book: real public prices, sandbox-shaped order requests, our own fills.

The sandbox cannot fill anything (it returns one canned payload and records nothing), so fills are
simulated here from the Exchange's public book — taker at the far touch plus slippage and the venue
fee — and recorded in our SQLite journal. Spot is long-only: no borrowing, no shorts.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from . import coinbase as cb
from .store import Store
from .strategy import Signal, sma_regime, stop_hit_long


@dataclass(frozen=True)
class Costs:
    fee_bps: float = 90.0       # fallback; the live tier is read from the venue
    slip_bps: float = 2.0


def live_costs(slip_bps: float = 2.0) -> Costs:
    """The account's actual taker rate; falls back to 90 bps if the read fails."""
    try:
        return Costs(fee_bps=cb.fee_tier()["taker_bps"], slip_bps=slip_bps)
    except Exception:                                   # noqa: BLE001 - a stale tier must not stop the book
        return Costs(slip_bps=slip_bps)


def candles(product: str, bars: int = 300, granularity: int = 3600) -> list[dict]:
    """Exchange candles, oldest first: [time, low, high, open, close, volume]."""
    url = f"{cb.EXCHANGE}/products/{product}/candles?granularity={granularity}"
    raw = cb._get(url)
    rows = [{"ts": int(r[0]), "low": float(r[1]), "high": float(r[2]),
             "open": float(r[3]), "close": float(r[4]), "volume": float(r[5])} for r in raw]
    return sorted(rows, key=lambda r: r["ts"])[-bars:]


def tick(store: Store, product: str = "BTC-USD", *, notional: float = 100.0,
         costs: Costs | None = None, stop_pct: float = 0.03,
         send_mock_order: bool = False) -> dict:
    costs = costs or live_costs()
    bars = candles(product)
    store.add_bars(product, bars)
    t = cb.ticker(product)
    mid = t["mid"]
    st = store.get_state(product)
    now = int(time.time())
    actions: list[str] = []

    if st["qty"] > 0 and stop_hit_long(st["entry_px"], mid, stop_pct):
        px = t["bid"] * (1 - costs.slip_bps / 1e4)
        fee = st["qty"] * px * costs.fee_bps / 1e4
        store.order(now, product, "sell", st["qty"], px, fee, "taker", "stop")
        store.set_state(product, cash=st["cash"] + st["qty"] * px - fee, qty=0.0,
                        entry_px=0.0, entry_ts=0)
        st = store.get_state(product)
        store.set_state(product, blocked="long")     # do not re-enter on the signal that stopped out
        st = dict(st, blocked="long")
        actions.append("STOP closed the long")

    sig: Signal = sma_regime(bars)
    if sig.side:
        store.signal(now, product, sig.side, mid, sig.reason)

    if sig.side == "short" and st.get("blocked"):
        store.set_state(product, blocked="")         # regime flipped: the block lifts
        st = dict(st, blocked="")

    min_usd = 1.0
    try:
        min_usd = float(cb.product_detail(product).get("quote_min_size") or 1.0)
    except Exception:                                   # noqa: BLE001
        pass
    if sig.side == "long" and st["qty"] == 0 and sig.side != st.get("blocked") \
            and min(notional, st["cash"]) < min_usd:
        actions.append(f"below the venue minimum (${min_usd:,.2f})")
    elif sig.side == "long" and st["qty"] == 0 and sig.side != st.get("blocked"):
        px = t["ask"] * (1 + costs.slip_bps / 1e4)
        qty = min(notional, st["cash"]) / px
        fee = qty * px * costs.fee_bps / 1e4
        store.order(now, product, "buy", qty, px, fee, "taker", sig.reason)
        store.set_state(product, cash=st["cash"] - qty * px - fee, qty=qty, entry_px=px, entry_ts=now)
        actions.append(f"BUY {qty:.6f} @ {px:,.2f}")
        if send_mock_order:
            out = cb.place_market(product, "BUY", min(notional, st["cash"]), confirm=True)
            actions.append(f"sandbox mock {str(out['order_id'])[:8]}")
    elif sig.side in ("short", "flat") and st["qty"] > 0:
        px = t["bid"] * (1 - costs.slip_bps / 1e4)
        fee = st["qty"] * px * costs.fee_bps / 1e4
        store.order(now, product, "sell", st["qty"], px, fee, "taker", sig.reason)
        store.set_state(product, cash=st["cash"] + st["qty"] * px - fee, qty=0.0,
                        entry_px=0.0, entry_ts=0)
        actions.append(f"SELL {st['qty']:.6f} @ {px:,.2f}")

    st = store.get_state(product)
    store.mark(product, now, st["cash"], st["qty"], st["entry_px"], mid)
    return {"product": product, "mid": mid, "signal": sig, "actions": actions,
            "qty": st["qty"], "equity": st["cash"] + st["qty"] * mid}
