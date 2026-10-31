"""Hyperliquid testnet, public endpoints only.

No key is read, stored or sent from this module. It refuses any host that is not the
testnet API, so a wrong environment cannot silently become mainnet.
"""
from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

TESTNET = "https://api.hyperliquid-testnet.xyz"
MAINNET = "https://api.hyperliquid.xyz"


class Refused(RuntimeError):
    """Raised instead of doing something that is not testnet-public."""


def _post(path: str, payload: dict[str, Any], *, base: str = TESTNET, timeout: float = 15.0) -> Any:
    # Reading is allowed from either venue; nothing here can sign, and orders live in hl_signed.py
    # which is pinned to the testnet constant.
    if base not in (TESTNET, MAINNET):
        raise Refused(f"not a Hyperliquid endpoint: {base}")
    req = urllib.request.Request(
        f"{base}{path}", data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - fixed host, https
        return json.loads(r.read())


@dataclass(frozen=True)
class Book:
    coin: str
    bid: float
    ask: float

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread_bps(self) -> float:
        return 1e4 * (self.ask - self.bid) / self.mid if self.mid else float("nan")


def mids(base: str = TESTNET) -> dict[str, float]:
    raw = _post("/info", {"type": "allMids"}, base=base)
    return {k: float(v) for k, v in raw.items()}


def book(coin: str, base: str = TESTNET) -> Book:
    raw = _post("/info", {"type": "l2Book", "coin": coin}, base=base)
    bids, asks = raw["levels"]
    if not bids or not asks:
        raise Refused(f"empty book for {coin}")
    return Book(coin=coin, bid=float(bids[0]["px"]), ask=float(asks[0]["px"]))


def candles(coin: str, interval: str = "1h", bars: int = 200, base: str = TESTNET) -> list[dict]:
    """Most recent `bars` candles, oldest first. The last one may still be forming."""
    step = STEP_S[interval] * 1000
    end = int(time.time() * 1000)
    raw = _post("/info", {"type": "candleSnapshot",
                          "req": {"coin": coin, "interval": interval,
                                  "startTime": end - bars * step, "endTime": end}}, base=base)
    rows = [{"ts": int(c["t"]) // 1000, "open": float(c["o"]), "high": float(c["h"]),
             "low": float(c["l"]), "close": float(c["c"]), "volume": float(c["v"])} for c in raw]
    return rows[-bars:]


STEP_S = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}


def clearinghouse_state(address: str, venue: str = "testnet") -> dict:
    """Public account state by address: value, withdrawable, positions. No key, read-only."""
    base = MAINNET if venue == "mainnet" else TESTNET
    return _post("/info", {"type": "clearinghouseState", "user": address}, base=base)


def funding_history(coin: str, since_s: int, venue: str = "testnet") -> list[tuple[int, float]]:
    """Realised hourly funding: [(unix seconds, rate per hour)]. Venue is testnet or mainnet.

    Mainnet rates are the realistic ones (testnet funding is synthetic and often pinned at a cap);
    paper fills still come from the testnet book.
    """
    base = MAINNET if venue == "mainnet" else TESTNET
    raw = _post("/info", {"type": "fundingHistory", "coin": coin,
                          "startTime": int(since_s) * 1000}, base=base)
    return [(int(r["time"]) // 1000, float(r["fundingRate"])) for r in raw]


def closed_only(rows: list[dict], step_s: int, now_s: int, bars: int) -> list[dict]:
    """Keep only bars whose window has ended, newest last. Pure, so it can be tested."""
    return [r for r in rows if r["ts"] + step_s <= now_s][-bars:]


def closed_candles(coin: str, interval: str = "1h", bars: int = 200, base: str = TESTNET) -> list[dict]:
    """Drop the bar that has not finished forming, so a signal cannot see a live close."""
    rows = candles(coin, interval, bars + 2, base=base)
    return closed_only(rows, STEP_S[interval], int(time.time()), bars)
