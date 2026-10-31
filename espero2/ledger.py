"""The gate: a strategy cannot run in this project until it has a row.

A row says what the strategy is (`status`), whether its statistic matches the claim, and
whether the money was measured after costs. Only `holds` may trade without a flag; `plumbing`
and `trial` need --allow-plumbing, which is the difference between "the loop works" and
"there is an edge".
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "strategy_ledger.csv"
PLUMBING = Path("PLUMBING.md")
STATUSES = {"plumbing", "trial", "replication", "holds", "retired", "audit"}
YESNO = {"yes", "partly", "no", "na"}


@dataclass(frozen=True)
class Row:
    id: str
    strategy: str
    status: str
    estimator: str
    estimator_matches_claim: str
    economic_bar: str
    basis: str
    note: str


def load(path: Path = LEDGER) -> dict[str, Row]:
    if not path.exists():
        raise SystemExit(f"no ledger at {path}")
    rows: dict[str, Row] = {}
    for r in csv.DictReader(path.open()):
        row = Row(**r)
        if row.status not in STATUSES:
            raise SystemExit(f"ledger: {row.id} has status {row.status!r}")
        if row.estimator_matches_claim not in YESNO or row.economic_bar not in YESNO:
            raise SystemExit(f"ledger: {row.id} has an invalid yes/no field")
        if row.status == "holds" and not (row.estimator_matches_claim == "yes" and row.economic_bar == "yes"):
            raise SystemExit(f"ledger: {row.id} claims holds without a valid statistic and a cost bar")
        rows[row.strategy] = row
    return rows


def plumbing_window(strategy: str, path: Path = PLUMBING) -> dict:
    """Parse the active plumbing window. Raises SystemExit when there is none or it is stale."""
    if not path.exists():
        raise SystemExit("no PLUMBING.md: a plumbing run needs a dated window "
                         "(strategy, purpose, started, expires)")
    block: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if ":" in line and not line.startswith("#"):
            k, v = line.split(":", 1)
            block[k.strip().lower()] = v.strip()
    if block.get("strategy") != strategy:
        raise SystemExit(f"PLUMBING.md is for {block.get('strategy')!r}, not {strategy!r}")
    if not block.get("purpose"):
        raise SystemExit("PLUMBING.md needs a purpose")
    expires = block.get("expires", "")
    import datetime as dt
    try:
        end = dt.date.fromisoformat(expires)
    except ValueError:
        raise SystemExit("PLUMBING.md needs expires: YYYY-MM-DD") from None
    if end < dt.date.today():
        raise SystemExit(f"plumbing window for {strategy!r} expired {expires}; "
                         "close the books and backtest before running it again")
    return block


def require(strategy: str, *, allow_plumbing: bool = False, path: Path = LEDGER,
            plumbing: Path = PLUMBING) -> Row:
    """Return the row or raise SystemExit. This is the only way a strategy reaches the loop."""
    rows = load(path)
    if strategy not in rows:
        raise SystemExit(f"strategy {strategy!r} is not in the ledger ({path.name}); "
                         "add a row before it can run")
    row = rows[strategy]
    if row.status == "retired":
        raise SystemExit(f"strategy {strategy!r} is retired")
    if row.status in {"plumbing", "trial"}:
        if not allow_plumbing:
            raise SystemExit(f"strategy {strategy!r} is {row.status}: pass --allow-plumbing to run it "
                             "as plumbing, or produce a trial/result row first")
        plumbing_window(strategy, plumbing)
    return row
