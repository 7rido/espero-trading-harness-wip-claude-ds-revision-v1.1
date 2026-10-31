"""Signed orders on Hyperliquid **testnet** only. The one place in this project that uses a key.

Guards, checked in order, every time:
  1. the base URL is the testnet constant — mainnet cannot be reached from here;
  2. HL_NETWORK, if set, must be "testnet";
  3. ESPERO2_ALLOW_TESTNET=1 (or the old ESPERO_ALLOW_HL_TESTNET=1) must be set;
  4. HL_PRIVATE_KEY must be present — it is read here and never printed;
  5. the caller must pass --confirm-testnet.

Nothing in this module runs by default; `espero2 run` never imports it.
"""
from __future__ import annotations

import os
from pathlib import Path

TESTNET = "https://api.hyperliquid-testnet.xyz"


class Refused(RuntimeError):
    pass


def load_env(path: Path = Path(".env")) -> None:
    """Parse KEY=VALUE lines into os.environ without printing anything."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def check(confirm: bool) -> dict:
    env = os.environ
    if env.get("HL_NETWORK", "testnet").lower() != "testnet":
        raise Refused("HL_NETWORK is not testnet")
    if env.get("ESPERO2_ALLOW_TESTNET") != "1" and env.get("ESPERO_ALLOW_HL_TESTNET") != "1":
        raise Refused("set ESPERO2_ALLOW_TESTNET=1 to allow testnet signing")
    if not env.get("HL_PRIVATE_KEY"):
        raise Refused("HL_PRIVATE_KEY is not set")
    if not confirm:
        raise Refused("pass --confirm-testnet to sign and send")
    return env


def exchange(confirm: bool):
    """Build a testnet Exchange. Imports the SDK lazily so the paper loop never needs it."""
    env = check(confirm)
    from eth_account import Account                      # noqa: PLC0415
    from hyperliquid.exchange import Exchange            # noqa: PLC0415

    wallet = Account.from_key(env["HL_PRIVATE_KEY"])
    account = env.get("HL_WALLET_ADDRESS") or wallet.address
    return Exchange(wallet, base_url=TESTNET, account_address=account), account


def info():
    from hyperliquid.info import Info                    # noqa: PLC0415

    return Info(TESTNET, skip_ws=True)


def state(account: str) -> dict:
    return info().user_state(account)


def guard_side(side: str, szi: float, allow_short: bool = False) -> bool:
    """The account is long-only by default. Returns reduce_only for the order.

    A sell with no long position would open a short on a perp — refused unless
    --allow-short is passed explicitly.
    """
    if side == "sell":
        if szi > 0:
            return True                    # closing the long
        if not allow_short:
            raise Refused("no long position to close; shorts are off (pass --allow-short)")
        return False
    return False                           # buy: open (or cover, which is not tracked here)


def position_size(account: str, coin: str) -> float:
    for p in state(account).get("assetPositions", []):
        pos = p["position"]
        if pos["coin"] == coin:
            return float(pos["szi"])
    return 0.0


def place(coin: str, side: str, notional: float, confirm: bool,
          allow_short: bool = False) -> dict:
    """Market-ish IOC order at the touch, sized by notional. Testnet only, long-only by default."""
    ex, account = exchange(confirm)
    szi = position_size(account, coin) if side == "sell" else 0.0
    reduce_only = guard_side(side, szi, allow_short)
    inf = info()
    decimals = next((u["szDecimals"] for u in inf.meta()["universe"] if u["name"] == coin), 4)
    book = inf.l2_snapshot(coin)
    bids, asks = book["levels"]
    px = float(asks[0]["px"] if side == "buy" else bids[0]["px"])
    sz = round(notional / px, decimals)
    res = ex.order(coin, side == "buy", sz, px,
                   order_type={"limit": {"tif": "Ioc"}}, reduce_only=reduce_only)
    statuses = (res.get("response") or {}).get("data", {}).get("statuses", [])
    errors = [s["error"] for s in statuses if isinstance(s, dict) and "error" in s]
    if errors:
        raise Refused("; ".join(errors))
    return {"account": account, "coin": coin, "side": side, "sz": sz, "px": px, "response": res}
