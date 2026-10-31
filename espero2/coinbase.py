"""Coinbase Advanced Trade sandbox — a **mock** execution venue, plus real public prices.

What is real: the ticker and product data, from `api.exchange.coinbase.com` (public, no key).
What is not: orders. `api-sandbox.coinbase.com` answers every order with the same canned payload
(`client_order_id: "sandbox_success_order"`) and serves a static 2024 order list. It is an
integration fixture for request/response shape, not a fill source, and nothing here can reach
mainnet. Every order response is marked `mock` when the sandbox does not echo our client id.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

SANDBOX = "https://api-sandbox.coinbase.com/api/v3/brokerage"
EXCHANGE = "https://api.exchange.coinbase.com"


class Refused(RuntimeError):
    pass


def _get(url: str, timeout: float = 15.0, sandbox_case: str | None = None) -> Any:
    allowed = (EXCHANGE, SANDBOX)
    if not any(url.startswith(a) for a in allowed):
        raise Refused(f"not a Coinbase endpoint: {url}")
    headers = {"Accept": "application/json", "User-Agent": "espero2/0.1"}
    if sandbox_case:
        headers["X-Sandbox"] = sandbox_case      # documented switch for a pre-defined error
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - fixed hosts, https
        return json.loads(r.read())


def _post(url: str, payload: dict, timeout: float = 15.0,
          sandbox_case: str | None = None) -> Any:
    if not url.startswith(SANDBOX):
        raise Refused(f"orders go to the sandbox only, not {url}")
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "User-Agent": "espero2/0.1"}
    if sandbox_case:
        headers["X-Sandbox"] = sandbox_case
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - fixed host, https
        return json.loads(r.read())


# ------------------------------------------------------------------ auth (read-only)
API = "https://api.coinbase.com/api/v3/brokerage"


def load_env(path: Path = Path(".env")) -> None:
    """KEY=VALUE into os.environ, never printed. Existing environment wins."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def _jwt(method: str, path: str) -> str:
    """CDP JWT. EdDSA from the 64-byte secret (what this key is), ES256 if a PEM is given."""
    import jwt as pyjwt                                    # noqa: PLC0415
    name = os.environ.get("COINBASE_API_KEY", "")
    secret = os.environ.get("COINBASE_API_SECRET", "")
    if not name or not secret:
        raise Refused("COINBASE_API_KEY / COINBASE_API_SECRET are not set")
    now = int(time.time())
    claims = {"sub": name, "iss": "cdp", "nbf": now, "exp": now + 120,
              "uri": f"{method} api.coinbase.com{path}"}
    headers = {"kid": name, "nonce": uuid.uuid4().hex}
    if "BEGIN" in secret:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key  # noqa: PLC0415
        key = load_pem_private_key(secret.encode().replace("\\n", "\n"), password=None)
        return pyjwt.encode(claims, key, algorithm="ES256", headers=headers)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415
    raw = base64.b64decode(secret + "=" * (-len(secret) % 4))
    key = Ed25519PrivateKey.from_private_bytes(raw[:32])
    return pyjwt.encode(claims, key, algorithm="EdDSA", headers=headers)


def authed_get(path: str, timeout: float = 20.0) -> Any:
    """Authenticated read against production. No order path exists here on purpose."""
    load_env()
    url = f"{API}{path}"
    token = _jwt("GET", f"/api/v3/brokerage{path}")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                               "Accept": "application/json",
                                               "User-Agent": "espero2/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - fixed host, https
        return json.loads(r.read())


def key_permissions() -> dict:
    return authed_get("/key_permissions")


_TIER: dict | None = None


def fee_tier(force: bool = False) -> dict:
    """The account's real fee tier, from the venue. Cached per process."""
    global _TIER
    if _TIER is None or force:
        fee = authed_get("/transaction_summary").get("fee_tier", {})
        _TIER = {"tier": fee.get("pricing_tier", "?"),
                 "taker_bps": 1e4 * float(fee.get("taker_fee_rate", 0.012)),
                 "maker_bps": 1e4 * float(fee.get("maker_fee_rate", 0.006))}
    return _TIER


def product_detail(product_id: str) -> dict:
    return authed_get(f"/products/{urllib.parse.quote(product_id)}")


def live_accounts() -> list[dict]:
    return authed_get("/accounts").get("accounts", [])


# ------------------------------------------------------------------- real data
def product(product_id: str = "BTC-USD") -> dict:
    return _get(f"{EXCHANGE}/products/{urllib.parse.quote(product_id)}")


def ticker(product_id: str = "BTC-USD") -> dict:
    t = _get(f"{EXCHANGE}/products/{urllib.parse.quote(product_id)}/ticker")
    return {"product": product_id, "bid": float(t["bid"]), "ask": float(t["ask"]),
            "last": float(t["price"]), "time": t["time"],
            "mid": (float(t["bid"]) + float(t["ask"])) / 2}


def products() -> list[str]:
    rows = _get(f"{EXCHANGE}/products")
    return sorted(r["id"] for r in rows if r.get("status") == "online" and r["quote_currency"] == "USD")


def futures_status() -> dict:
    """US derivatives on Advanced Trade are CFM futures, not INTX perps.

    `/cfm/*` needs a CDP JWT, and the sandbox does not implement it (404), so this project can
    describe the path but cannot exercise it without a production key.
    """
    return {"venues": ["spot", "US futures (CFM)"],
            "retired": ["INTX perpetuals - trading ended 2026-10-01; read endpoints kept for history"],
            "futures_endpoints": ["/cfm/balance_summary", "/cfm/positions",
                                  "/cfm/positions/{product_id}", "/cfm/sweeps",
                                  "/cfm/intraday/margin_setting", "/cfm/intraday/current_margin_window"],
            "auth": "CDP JWT with view/trade permission",
            "sandbox": "accounts/orders/portfolios/intx only - /cfm and /market return 404",
            "public_market": ["/market/products", "/market/products/{id}", "/market/product_book",
                              "/market/products/{id}/ticker (a trade tape, not a quote)"]}


# ----------------------------------------------------------------- mock exchange
def accounts() -> list[dict]:
    return _get(f"{SANDBOX}/accounts").get("accounts", [])


def portfolios() -> list[dict]:
    return _get(f"{SANDBOX}/portfolios").get("portfolios", [])


def perp_portfolio(uuid: str) -> dict:
    return _get(f"{SANDBOX}/intx/portfolio/{uuid}")


def perp_positions(uuid: str) -> list[dict]:
    return _get(f"{SANDBOX}/intx/positions/{uuid}").get("positions", [])


def fills(limit: int = 10) -> list[dict]:
    return _get(f"{SANDBOX}/orders/historical/fills?limit={limit}").get("fills", [])


def orders(limit: int = 10) -> list[dict]:
    return _get(f"{SANDBOX}/orders/historical/batch?limit={limit}").get("orders", [])


def place_market(product_id: str, side: str, quote_usd: float,
                 client_id: str | None = None, confirm: bool = False,
                 sandbox_case: str | None = None) -> dict:
    """Market order into the sandbox. Canned response; `mock` says whether it echoed our id."""
    if side.upper() not in ("BUY", "SELL"):
        raise Refused("side must be BUY or SELL")
    if not confirm:
        raise Refused("pass confirm=True (--confirm-sandbox) to send a sandbox order")
    cid = client_id or f"espero2-{uuid.uuid4().hex[:12]}"
    payload = {"client_order_id": cid, "product_id": product_id, "side": side.upper(),
               "order_configuration": {"market_market_ioc": {"quote_size": f"{quote_usd:.2f}"}}}
    res = _post(f"{SANDBOX}/orders", payload, sandbox_case=sandbox_case)
    echoed = (res.get("success_response") or {}).get("client_order_id")
    err = (res.get("error_response") or {}).get("error")
    return {"request": payload, "response": res, "mock": echoed != cid,
            "ok": bool(res.get("success")), "error": err,
            "order_id": (res.get("success_response") or {}).get("order_id"), "client_id": cid}
