"""One paper-trading tick: long or short, on testnet market data, with costs charged.

A position is a signed quantity: `qty > 0` long, `qty < 0` short. Stops mirror, funding accrues
at a stated constant rate (positive = longs pay shorts), and every fill records whether it opened
or closed. Nothing here can sign or read a key.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from . import hl
from .store import Store
from .strategy import Signal, sma_regime, stop_hit_long, stop_hit_short


@dataclass(frozen=True)
class Costs:
    taker_bps: float = 4.5     # Hyperliquid base tier
    slippage_bps: float = 2.0  # adverse, assumed on every fill


@dataclass(frozen=True)
class Rules:
    stop_pct: float = 0.03
    funding_bps_hour: float = 1.0   # fallback only: 1 bp/h ≈ 8.8%/yr, positive = longs pay
    funding_source: str = "venue"   # "venue" = realised hourly rates; "constant" = the bps above
    funding_venue: str = "mainnet"  # which venue's realised rates to use for paper books
    leverage: float = 1.0           # notional / margin; 1x = no borrowing
    maintenance: float = 0.01       # fraction of notional kept as maintenance margin
    max_notional: float = 100.0


def _fill_px(px: float, side: str, costs: Costs) -> float:
    slip = costs.slippage_bps / 1e4
    return px * (1 + slip) if side == "buy" else px * (1 - slip)


def liquidation_px(entry_px: float, side: int, leverage: float, maintenance: float) -> float:
    """Where the venue would close the book. side=+1 long, -1 short."""
    if leverage <= 0:
        return float("nan")
    move = 1.0 / leverage - maintenance
    return entry_px * (1 - move) if side > 0 else entry_px * (1 + move)


def _funding(store: Store, coin: str, st: dict, mark: float, hours: float, rate_bps: float) -> float:
    """Cash change from funding. Longs pay when the rate is positive, shorts receive."""
    if st["qty"] == 0 or hours <= 0:
        return 0.0
    return -st["qty"] * mark * (rate_bps / 1e4) * hours


def _open(store: Store, coin: str, side: str, px: float, st: dict, rules: Rules,
          costs: Costs, note: str) -> dict:
    """Open a long (side='buy') or a short (side='sell'), sized by max_notional."""
    notional = min(rules.max_notional, st["cash"])
    if notional <= 0:
        return st
    qty = notional / px * (1 if side == "buy" else -1)
    fee = notional * costs.taker_bps / 1e4
    store.order(int(time.time()), coin, side, abs(qty), px, fee, "taker", f"open {note}")
    # a long pays for the asset, a short receives the proceeds: cash -= signed qty * price
    store.set_state(coin, cash=st["cash"] - qty * px - fee, qty=qty, entry_px=px,
                    entry_ts=int(time.time()), last_funding=int(time.time()))
    return store.get_state(coin)


def _close(store: Store, coin: str, px: float, st: dict, costs: Costs, note: str) -> dict:
    """Close whatever is open, either side, at the touch."""
    side = "sell" if st["qty"] > 0 else "buy"
    qty = abs(st["qty"])
    fee = qty * px * costs.taker_bps / 1e4
    store.order(int(time.time()), coin, side, qty, px, fee, "taker", f"close {note}")
    cash = st["cash"] + st["qty"] * px - fee        # signed: a short buy-back subtracts
    store.set_state(coin, cash=cash, qty=0.0, entry_px=0.0, entry_ts=0)
    return store.get_state(coin)


def tick(store: Store, coin: str, *, notional: float = 100.0, costs: Costs = Costs(),
         rules: Rules = Rules(), interval: str = "1h", kill: Path = Path("KILL"),
         allow_short: bool = True) -> dict:
    """Run one decision cycle and return what happened."""
    bars = hl.closed_candles(coin, interval=interval, bars=300)
    new = store.add_bars(coin, bars)
    book = hl.book(coin)
    mid = book.mid
    now = int(time.time())
    st = store.get_state(coin)
    actions: list[str] = []

    # 0. funding accrual since the last cycle (capped at a day, so a long sleep is not free)
    last_f = int(float(st.get("last_funding", 0) or 0)) or now
    fund, source = 0.0, "constant"
    if st["qty"] != 0:
        points = []
        if rules.funding_source == "venue":
            try:
                points = [(ts, rate) for ts, rate in
                          hl.funding_history(coin, last_f, venue=rules.funding_venue) if ts > last_f]
            except Exception:                                # noqa: BLE001 - fall back, and say so
                points = []
                source = "constant (venue unavailable)"
        for _, rate in points:                               # one point per settled hour
            fund += -st["qty"] * mid * rate
        if points:
            source = f"venue-{rules.funding_venue}"
        if fund == 0.0:                                      # no settled hour in this window yet
            hours = max(0.0, min(24.0, (now - last_f) / 3600))
            fund = _funding(store, coin, st, mid, hours, rules.funding_bps_hour)
            if points == [] and source == "constant":
                source = "constant (no venue point)"
    if fund:
        st = dict(st, cash=st["cash"] + fund)
        store.set_state(coin, cash=st["cash"], last_funding=now)
        actions.append(f"funding {fund:+.4f} ({source})")
    elif st["qty"] != 0:
        store.set_state(coin, last_funding=now)

    # a real venue closes the book when maintenance margin is gone. At 1x that is a ~2x move
    # against a short (or the whole stake against a long); the fill is the mark or the liquidation
    # price, whichever is worse, so a gap through it can still leave a negative balance.
    if st["qty"] != 0:
        side = 1 if st["qty"] > 0 else -1
        liq = liquidation_px(st["entry_px"], side, rules.leverage, rules.maintenance)
        breached = (side > 0 and mid <= liq) or (side < 0 and mid >= liq)
        if breached:
            px = min(mid, liq) if side > 0 else max(mid, liq)
            st = _close(store, coin, px, st, costs, "liquidated")
            block = "long" if side > 0 else "short"
            store.set_state(coin, blocked=block)
            st = dict(st, blocked=block)
            actions.append(f"LIQUIDATED at {px:,.2f}")
            equity = st["cash"]



    # 1. stops first, mirrored
    stopped = ""
    if st["qty"] > 0 and stop_hit_long(st["entry_px"], mid, rules.stop_pct):
        st = _close(store, coin, _fill_px(book.bid, "sell", costs), st, costs, "stop")
        stopped = "long"
        store.set_state(coin, blocked=stopped)     # no re-entry on the signal that just stopped out
        st = dict(st, blocked=stopped)
        actions.append("stop closed long")
    elif st["qty"] < 0 and stop_hit_short(st["entry_px"], mid, rules.stop_pct):
        st = _close(store, coin, _fill_px(book.ask, "buy", costs), st, costs, "stop")
        stopped = "short"
        store.set_state(coin, blocked=stopped)
        st = dict(st, blocked=stopped)
        actions.append("stop closed short")

    # 2. the strategy's regime
    sig: Signal = sma_regime(bars)
    if sig.side:
        store.signal(now, coin, sig.side, mid, sig.reason)

    want = 1 if sig.side == "long" else (-1 if sig.side == "short" else 0)
    held = 1 if st["qty"] > 0 else (-1 if st["qty"] < 0 else 0)
    if sig.side and st.get("blocked") and sig.side != st["blocked"]:
        store.set_state(coin, blocked="")          # the regime changed: the block is lifted

    # 3. act only when the book is on the wrong side
    if not kill.exists() and want and want != held and sig.side != st.get("blocked"):
        if held:                                   # flip: close first, then open
            closing_px = _fill_px(book.bid if held > 0 else book.ask,
                                  "sell" if held > 0 else "buy", costs)
            st = _close(store, coin, closing_px, st, costs, "flip")
            actions.append(f"closed {'long' if held > 0 else 'short'}")
        if want > 0:
            st = _open(store, coin, "buy", _fill_px(book.ask, "buy", costs), st, rules, costs, sig.reason)
            actions.append(f"opened long {abs(st['qty']):.6f}")
        elif allow_short:
            st = _open(store, coin, "sell", _fill_px(book.bid, "sell", costs), st, rules, costs, sig.reason)
            actions.append(f"opened short {abs(st['qty']):.6f}")
        else:
            actions.append("short signal ignored (long-only)")

    st = store.get_state(coin)
    equity = st["cash"] + st["qty"] * mid

    store.mark(coin, now, st["cash"], st["qty"], st["entry_px"], mid)
    return {"coin": coin, "mid": mid, "spread_bps": book.spread_bps, "new_bars": new,
            "signal": sig, "actions": actions, "qty": st["qty"], "cash": st["cash"],
            "equity": equity}


def catch_up(store: Store, coin: str, *, interval: str = "1h") -> dict:
    """Mark the equity series over bars that closed while the process was asleep. No trades."""
    bars = hl.closed_candles(coin, interval=interval, bars=300)
    store.add_bars(coin, bars)
    if not store.has_marks(coin):
        return {"coin": coin, "marks": 0, "first": bars[0]["ts"] if bars else 0}
    last = store.last_mark_ts(coin)
    st = store.get_state(coin)
    marks = 0
    for b in bars:
        if b["ts"] > last:
            store.mark(coin, b["ts"], st["cash"], st["qty"], st["entry_px"], b["close"])
            marks += 1
    return {"coin": coin, "marks": marks, "first": bars[0]["ts"] if bars else 0}
