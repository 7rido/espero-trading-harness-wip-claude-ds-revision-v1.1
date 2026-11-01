#!/usr/bin/env bash
# Everything that must hold before a change is trusted: tests, audit citations, ledger validity.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
echo "== tests"
LOG="$(mktemp)"
if ! "$PY" -m unittest discover -s tests -t . > "$LOG" 2>&1; then
    echo "tests failed:"
    grep -E "^(FAIL|ERROR):" "$LOG" | head -20
    tail -5 "$LOG"
    rm -f "$LOG"
    exit 1
fi
tail -2 "$LOG"
rm -f "$LOG"
echo "== audit"
"$PY" research/audit_by_number.py --check
echo "== inheritance"
"$PY" scripts/check_inheritance.py
echo "== ledger"
"$PY" -m espero2.cli ledger > /dev/null
echo "all checks passed"
