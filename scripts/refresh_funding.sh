#!/usr/bin/env bash
# Refresh perp funding for the live universe (Binance archive + Hyperliquid + OKX) once a day.
# Keeps funding_multi fresh enough for the optics funding percentile on every discovered market.
set -euo pipefail
cd "$(dirname "$0")/.."
COINS="BTC ETH SOL XRP DOGE ADA AVAX LINK DOT LTC HYPE ZEC NEAR PUMP ENA XPL UNI"
for c in $COINS; do
    .venv/bin/python research/funding_fetch.py --coin "$c" >/dev/null 2>&1 \
        && echo "funding $c ok" || echo "funding $c failed" >&2
done
