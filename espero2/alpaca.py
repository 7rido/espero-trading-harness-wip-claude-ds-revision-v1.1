"""Alpaca client: paper account, positions, clock, bars, orders. Live is refused by construction.

Keys come from the environment (APCA_API_KEY_ID / APCA_API_SECRET_KEY), loaded from .env without ever
printing a value. The only trading host in this module is the paper one.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any

from .coinbase import load_env

PAPER = "https://paper-api.alpaca.markets"
DATA = "https://data.alpaca.markets"
LIVE = "https://api.alpaca.markets"          # recognised and refused
HOSTS = {PAPER, DATA}
TIMEOUT = 20.0


class Refused(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    load_env()
    key, secret = os.environ.get("APCA_API_KEY_ID", ""), os.environ.get("APCA_API_SECRET_KEY", "")
    if not key or not secret:
        raise Refused("APCA_API_KEY_ID / APCA_API_SECRET_KEY are not set (add them to .env)")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json", "User-Agent": "espero2/0.1"}


def _call(base: str, path: str, params: dict | None = None, method: str = "GET",
          payload: dict | None = None) -> Any:
    if base not in HOSTS:
        raise Refused(f"only {PAPER} and {DATA} are allowed; {base} is not")
    url = f"{base}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(payload).encode() if payload is not None else None
    headers = _headers()
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:      # noqa: S310 - fixed https hosts
        return json.loads(r.read())


def clock() -> dict:
    return _call(PAPER, "/v2/clock")


def account() -> dict:
    return _call(PAPER, "/v2/account")


def positions() -> list[dict]:
    return _call(PAPER, "/v2/positions")


def orders(status: str = "open", limit: int = 20) -> list[dict]:
    return _call(PAPER, "/v2/orders", {"status": status, "limit": limit})


def bars(symbols: str | list[str], timeframe: str = "1Day", start: str | None = None,
         end: str | None = None, feed: str = "iex") -> dict:
    """Stock bars. Crypto uses /v1beta3/crypto/us/bars; this is the stock path."""
    syms = ",".join(symbols) if isinstance(symbols, list) else symbols
    params = {"symbols": syms, "timeframe": timeframe, "feed": feed}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return _call(DATA, "/v2/stocks/bars", params)


def crypto_bars(symbols: str | list[str], timeframe: str = "1Day", start: str | None = None,
                end: str | None = None) -> dict:
    """Crypto bars: Alpaca serves these on /v1beta3/crypto/us/bars (symbols like BTC/USD)."""
    syms = ",".join(symbols) if isinstance(symbols, list) else symbols
    params = {"symbols": syms, "timeframe": timeframe}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return _call(DATA, "/v1beta3/crypto/us/bars", params)


def place_order(symbol: str, qty: float, side: str, order_type: str = "market",
                limit_price: float | None = None, confirm: bool = False) -> dict:
    """Paper only, and only with an explicit confirm. There is no live path in this module."""
    if not confirm:
        raise Refused("pass confirm=True (--confirm-paper) to send a paper order")
    if order_type not in ("market", "limit"):
        raise Refused("order type is market or limit")
    if order_type == "limit" and limit_price is None:
        raise Refused("a limit order needs a price")
    payload = {"symbol": symbol, "qty": str(qty), "side": side.lower(),
               "type": order_type, "time_in_force": "day" if order_type == "market" else "gtc"}
    if limit_price is not None:
        payload["limit_price"] = str(limit_price)
    return _call(PAPER, "/v2/orders", method="POST", payload=payload)
