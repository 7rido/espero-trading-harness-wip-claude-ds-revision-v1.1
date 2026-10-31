#!/usr/bin/env bash
# Everything that must hold before a change is trusted: tests, audit citations, ledger validity.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
echo "== tests"
"$PY" -m unittest discover -s tests -t . 2>&1 | tail -3
echo "== audit"
"$PY" research/audit_by_number.py --check
echo "== ledger"
"$PY" -m espero2.cli ledger > /dev/null
echo "all checks passed"
