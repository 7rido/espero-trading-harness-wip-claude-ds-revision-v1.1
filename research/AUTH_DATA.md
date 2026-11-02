# Authenticated testnet data audit

`python research/auth_data_audit.py` is a read-only check of the testnet and sandbox accounts. It
writes counts only — no balances, keys, order ids or fills — and places no orders.

## What it reads

| Source | Environment | Data |
|---|---|---|
| Hyperliquid | testnet | clearinghouse positions, open orders, fills, funding payments, portfolio periods |
| Coinbase Advanced Trade | sandbox | accounts, portfolios, orders, fills |

Hyperliquid reads use `HL_WALLET_ADDRESS`; the private key is not used. Coinbase reads use a signed
GET against `https://api-sandbox.coinbase.com` with `COINBASE_API_KEY` / `COINBASE_API_SECRET`.
Coinbase production returns 401 for these keys, confirming they are sandbox-only.

## Why it is separate from the forecast

Testnet/sandbox fills and balances are execution data. They are not market history and must not be
used as forecast features. The forecast audit uses mainnet public market data; this audit is for
reconciliation, execution checks and carry/funding bookkeeping.

No order path is added or changed.
