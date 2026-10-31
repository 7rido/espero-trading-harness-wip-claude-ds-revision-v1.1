#!/usr/bin/env bash
set -u
PY="$1"
rm -f scratch.db scratch.log
"$PY" -u -m espero2.cli --state scratch.db run --coin BTC --interval 1m --loop --every 60 --allow-plumbing > scratch.log 2>&1 &
PID=$!
echo "pid $PID"
sleep 75
kill -STOP "$PID"; echo "paused $(date +%H:%M:%S)"
sleep 140
kill -CONT "$PID"; echo "resumed $(date +%H:%M:%S)"
sleep 30
echo "--- catch-up lines ---"; grep -i "catch-up" scratch.log || echo "(none)"
echo "--- last ticks ---"; tail -3 scratch.log
kill "$PID" 2>/dev/null
