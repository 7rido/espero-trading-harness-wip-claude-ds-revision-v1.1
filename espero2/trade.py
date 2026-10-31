"""One trade entry point across the paper venues: Alpaca paper, Coinbase sandbox, HL testnet.

Coordination only — every guard stays where it already lives:

- Alpaca: `place_order` targets `paper-api.alpaca.markets`; the live host is not in that module.
- Coinbase: `place_market` targets the sandbox, `policy.require_sandbox()` gates it, and the reply is
  flagged `mock`.
- Hyperliquid: `hl_signed.place` builds a testnet exchange; the mainnet host is not reachable.

Nothing here can place a real order; the three adapters contain no live host.
"""
from __future__ import annotations

import os

from . import alpaca, coinbase as cb, hl_signed, policy


class Refused(RuntimeError):
    pass


VENUES = ("alpaca", "coinbase", "hyperliquid")
MODES = {"alpaca": "paper", "coinbase": "sandbox (mock)", "hyperliquid": "testnet"}


def place(venue: str, symbol: str, side: str, *, qty: float | None = None,
          notional: float | None = None, order_type: str = "market",
          limit_price: float | None = None, confirm: bool = False) -> dict:
    """Route one order to a paper venue. Returns the adapter's response with a unified header."""
    venue = venue.lower()
    if venue not in VENUES:
        raise Refused(f"venue {venue!r} is not one of {VENUES}")
    side = side.lower()
    if side not in ("buy", "sell"):
        raise Refused(f"side {side!r} is not buy or sell")

    if venue == "alpaca":
        if "/" in symbol:                         # crypto pair: fractional qty, long-only
            if qty is None:
                raise Refused("crypto orders are sized in units: pass --qty")
            out = alpaca.place_crypto(symbol, qty, side, confirm=confirm)
            return {"venue": venue, "mode": "paper (crypto)", "symbol": symbol, "side": side,
                    "qty": qty, "response": out}
        if qty is None:
            raise Refused("alpaca orders are sized in shares/units: pass --qty")
        out = alpaca.place_order(symbol, qty, side, order_type=order_type,
                                 limit_price=limit_price, confirm=confirm)
        return {"venue": venue, "mode": MODES[venue], "symbol": symbol, "side": side,
                "qty": qty, "type": order_type, "limit_price": limit_price, "response": out}

    if venue == "coinbase":
        if notional is None:
            raise Refused("coinbase orders are sized in quote currency: pass --notional")
        try:
            policy.require_sandbox()
        except policy.Refused as exc:
            raise Refused(str(exc)) from exc
        out = cb.place_market(symbol, side.upper(), notional, confirm=confirm)
        return {"venue": venue, "mode": MODES[venue], "symbol": symbol, "side": side,
                "notional": notional, "mock": out.get("mock"), "order_id": out.get("order_id"),
                "response": out.get("response")}

    # hyperliquid
    if notional is None:
        raise Refused("hyperliquid orders are sized by notional: pass --notional")
    os.environ.setdefault("HL_NETWORK", "testnet")
    hl_signed.load_env()
    out = hl_signed.place(symbol, side, notional, confirm=confirm)
    return {"venue": venue, "mode": MODES[venue], "symbol": symbol, "side": side,
            "notional": notional, "response": out}
