#!/usr/bin/env bash
# Commit the daily E1 recorder outputs, so the event log is a dated audit trail.
# Runs at the end of the 07:45 sync chain; pushes a small data commit when anything changed.
set -euo pipefail
cd "$(dirname "$0")/.."
FILES="research/e1_events.csv research/e1_status.json research/e1_progress.json research/e1_feed_status.json"
git add -- $FILES 2>/dev/null || true
if git diff --cached --quiet; then
    echo "e1 commit: no changes"
    exit 0
fi
DAY="$(date -u -v-1d +%Y-%m-%d)"
git commit -q -m "data: E1 events for ${DAY}"
if git push -q origin main; then
    echo "e1 commit: pushed ${DAY}"
else
    echo "e1 commit: push failed (will retry next run)" >&2
    exit 1
fi
