"""Read-only audit of the testnet/sandbox accounts.

    python research/auth_data_audit.py

Reads the Hyperliquid testnet account (address only) and the Coinbase Advanced
Trade sandbox (signed GETs). It writes counts to `research/auth_data_audit.json`
and never prints keys, balances, order ids or fills. No order is placed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import pathlib
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
OUT = ROOT / "research" / "auth_data_audit.json"
HL_DEFAULT = "https://api.hyperliquid-testnet.xyz"
CB_SANDBOX = "https://api-sandbox.coinbase.com"
UA = {"User-Agent": "espero2-auth-audit/0.1", "Content-Type": "application/json"}


def load_env(path: pathlib.Path = ENV) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def sign_coinbase(secret: str, timestamp: str, method: str, path: str) -> str:
    message = f"{timestamp}{method}{path}".encode()
    digest = hmac.new(base64.b64decode(secret), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _get_json(url: str, headers: dict | None = None, data: dict | None = None) -> dict:
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


def hyperliquid(env: dict[str, str]) -> dict:
    network = env.get("HL_NETWORK", "")
    address = env.get("HL_WALLET_ADDRESS", "")
    if network != "testnet":
        return {"network": network or None, "error": "HL_NETWORK is not testnet"}
    if not address:
        return {"network": network, "error": "HL_WALLET_ADDRESS missing"}
    base = env.get("HL_API_URL") or HL_DEFAULT
    out: dict = {"network": network, "address_present": True}
    try:
        state = _get_json(f"{base}/info", UA, {"type": "clearinghouseState", "user": address})
        positions = state.get("assetPositions", []) if isinstance(state, dict) else []
        out["positions"] = len(positions)
        out["open_orders"] = len(_get_json(
            f"{base}/info", UA, {"type": "openOrders", "user": address}))
        out["fills"] = len(_get_json(
            f"{base}/info", UA, {"type": "userFills", "user": address}))
        out["funding_payments"] = len(_get_json(
            f"{base}/info", UA, {"type": "userFunding", "user": address, "startTime": 0}))
        out["portfolio_periods"] = len(_get_json(
            f"{base}/info", UA, {"type": "portfolio", "user": address}))
    except urllib.error.HTTPError as exc:
        out["error"] = f"HTTP {exc.code}"
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def coinbase(env: dict[str, str]) -> dict:
    key = env.get("COINBASE_API_KEY", "")
    secret = env.get("COINBASE_API_SECRET", "")
    if not (key and secret):
        return {"environment": "sandbox", "error": "Coinbase Advanced Trade key/secret missing"}
    out: dict = {"environment": "sandbox"}

    def get(path: str) -> dict:
        ts = str(int(time.time()))
        headers = {
            "CB-ACCESS-KEY": key,
            "CB-ACCESS-SIGN": sign_coinbase(secret, ts, "GET", path),
            "CB-ACCESS-TIMESTAMP": ts,
            "User-Agent": UA["User-Agent"],
        }
        return _get_json(CB_SANDBOX + path, headers)

    try:
        out["accounts"] = len(get("/api/v3/brokerage/accounts").get("accounts", []))
        out["portfolios"] = len(get("/api/v3/brokerage/portfolios").get("portfolios", []))
        out["orders"] = len(get("/api/v3/brokerage/orders/historical/batch?limit=100").get("orders", []))
        out["fills"] = len(get("/api/v3/brokerage/orders/historical/fills?limit=100").get("fills", []))
    except urllib.error.HTTPError as exc:
        out["error"] = f"HTTP {exc.code}"
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def main() -> int:
    env = load_env()
    payload = {
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hyperliquid": hyperliquid(env),
        "coinbase": coinbase(env),
        "note": "counts only; no balances, keys, order ids or fills are written",
    }
    OUT.write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
