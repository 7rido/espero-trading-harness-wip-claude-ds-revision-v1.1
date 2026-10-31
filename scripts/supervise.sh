#!/usr/bin/env bash
# Restart the paper loop when it dies. Stop it with `touch KILL`.
#
#   ./scripts/supervise.sh                    # 60 s cadence, BTC/ETH/SOL
#   STATE=demo.db EVERY=10 ./scripts/supervise.sh
set -u
cd "$(dirname "$0")/.."
PY="${PY:-python3}"
STATE="${STATE:-paper.db}"
EVERY="${EVERY:-60}"
INTERVAL="${INTERVAL:-1h}"
COINS="${COINS:---coin BTC --coin ETH --coin SOL}"
backoff=5
while true; do
    if [ -f KILL ]; then echo "$(date -u +%FT%TZ) KILL present, supervisor exiting"; exit 0; fi
    started=$(date +%s)
    # shellcheck disable=SC2086
    FLAG=""
    [ -f PLUMBING.md ] && FLAG="--allow-plumbing"     # no window, no plumbing loop
    # shellcheck disable=SC2086
    "$PY" -u -m espero2.cli --state "$STATE" run $COINS --interval "$INTERVAL" \
        --loop --every "$EVERY" $FLAG --dashboard
    code=$?
    ran=$(( $(date +%s) - started ))
    [ "$ran" -gt 180 ] && backoff=5        # a long run resets the backoff
    echo "$(date -u +%FT%TZ) loop exited $code after ${ran}s; restarting in ${backoff}s"
    sleep "$backoff"
    backoff=$(( backoff < 60 ? backoff * 2 : 60 ))
done
