#!/usr/bin/env bash
# Restart the paper loop when it dies. Stop it with `touch KILL`.
#
#   ./scripts/supervise.sh                    # 60 s cadence, BTC/ETH/SOL
#   STATE=demo.db EVERY=10 ./scripts/supervise.sh
set -u
cd "$(dirname "$0")/.."
if [ -z "${PY:-}" ]; then
    [ -x "$(dirname "$0")/../.venv/bin/python" ] && PY="$(dirname "$0")/../.venv/bin/python" || PY="python3"
fi
STATE="${STATE:-paper.db}"
EVERY="${EVERY:-60}"
INTERVAL="${INTERVAL:-1h}"
COINS="${COINS:---coin BTC --coin ETH --coin SOL}"
VOL_TARGET="${VOL_TARGET:-2}"        # risk % of equity per position, sized by realised vol
MAX_FUNDING="${MAX_FUNDING:-25}"     # skip entries paying more than this annual funding %
MAX_NOTIONAL="${MAX_NOTIONAL:-500}"  # hard cap per position so vol sizing can operate
backoff=5
while true; do
    if [ -f KILL ]; then echo "$(date -u +%FT%TZ) KILL present, supervisor exiting"; exit 0; fi
    started=$(date +%s)
    # shellcheck disable=SC2086
    FLAG=""
    [ -f PLUMBING.md ] && FLAG="--allow-plumbing"     # no window, no plumbing loop
    # shellcheck disable=SC2086
    "$PY" -u -m espero2.cli --state "$STATE" run $COINS --interval "$INTERVAL" \
        --loop --every "$EVERY" $FLAG --dashboard \
        --vol-target "$VOL_TARGET" --max-funding "$MAX_FUNDING" --max-notional "$MAX_NOTIONAL"
    code=$?
    ran=$(( $(date +%s) - started ))
    [ "$ran" -gt 180 ] && backoff=5        # a long run resets the backoff
    echo "$(date -u +%FT%TZ) loop exited $code after ${ran}s; restarting in ${backoff}s"
    sleep "$backoff"
    backoff=$(( backoff < 60 ? backoff * 2 : 60 ))
done
