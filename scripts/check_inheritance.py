"""CI: every finding must be on the inheritance map, and the map must cover every original id.

    python scripts/check_inheritance.py
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "research" / "INHERITANCE.md"
LEDGER = ROOT / "strategy_ledger.csv"
ORIGINAL_IDS = [str(i) for i in range(1, 46)] + ["9b"]


def main() -> int:
    text = DOC.read_text()
    errors = []
    for oid in ORIGINAL_IDS:
        if not re.search(rf"^\| {re.escape(oid)} \|", text, re.M):
            errors.append(f"original id {oid} missing from the map")
    rows = list(csv.DictReader(LEDGER.open()))
    for r in rows:
        if not re.search(rf"\b{re.escape(r['id'])}\b", text):
            errors.append(f"ledger id {r['id']} ({r['strategy']}) not referenced")
    # every result document must be named on the map (stems normalised with hyphens)
    for doc in sorted((ROOT / "research").glob("RESULTS_*.md")):
        stem = doc.stem.replace("RESULTS_", "").replace("_", "-")
        if stem not in text and doc.name not in text:
            errors.append(f"result {doc.name} is not referenced as '{stem}'")
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"ok: {len(ORIGINAL_IDS)} originals, {len(rows)} ledger rows, "
          f"{len(list((ROOT / 'research').glob('RESULTS_*.md')))} results referenced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
