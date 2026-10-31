"""Copy new data from the maintainer's project folder into espero2. One way, no deletes.

    python scripts/sync_from_original.py               # copy what is new or changed
    python scripts/sync_from_original.py --dry-run     # say what would be copied
    python scripts/sync_from_original.py --source PATH

Semantics: a file is copied when it is missing here, or when the source is newer AND differs in
size. Nothing is ever deleted, a newer local file is never overwritten, and the source folder is
only read. Designed to run after the maintainer's 07:30 job, not at the same minute.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = pathlib.Path("/Users/fredp/Espero Trading QuantBot/espero")
# logs follow the destination, so a test run into a temp tree writes nothing here

# directories and files the research tests read; journals (*.db) are deliberately not mirrored
# only the directories that grow daily; the static archives are already in data_raw/
TREES = [
    "data/aggr/forward", "data/aggr/forward5m", "data/lows/forward", "data/hlcollect", "data/book",
]
FILES = [
    "liqfwd_trades.csv", "liqbreak_trades.csv", "liqhold_trades.csv", "lows_fwd_trades.csv",
    "postclose_days.csv", "settle_fwd.csv", "health.json",
]


def plan(source: pathlib.Path, dest: pathlib.Path) -> tuple[list[tuple[pathlib.Path, pathlib.Path]], int]:
    """(pairs to copy, count of files already current)."""
    todo, current = [], 0
    for rel in TREES:
        base = source / rel
        if not base.is_dir():
            continue
        for src in base.rglob("*"):
            if not src.is_file():
                continue
            dst = dest / src.relative_to(source)
            todo, current = _decide(src, dst, todo, current)
    for rel in FILES:
        src = source / rel
        if src.is_file():
            todo, current = _decide(src, dest / rel, todo, current)
    return todo, current


def _decide(src: pathlib.Path, dst: pathlib.Path, todo, current):
    if not dst.exists():
        return todo + [(src, dst)], current
    st, dt_ = src.stat(), dst.stat()
    if st.st_mtime > dt_.st_mtime and st.st_size != dt_.st_size:
        return todo + [(src, dst)], current
    return todo, current + 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(DEFAULT_SOURCE))
    ap.add_argument("--dest", default=str(ROOT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    source, dest = pathlib.Path(args.source), pathlib.Path(args.dest)
    if not source.is_dir():
        print(f"source not found: {source}", file=sys.stderr)
        return 2

    todo, current = plan(source, dest)
    copied = bytes_copied = 0
    for src, dst in todo:
        if args.dry_run:
            print(f"would copy {src.relative_to(source)}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
        bytes_copied += src.stat().st_size

    log = dest / "logs" / "sync.log"
    status = dest / "logs" / "sync-status.json"
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    summary = {"at": stamp, "source": str(source), "copied": copied, "already_current": current,
               "bytes": bytes_copied, "dry_run": args.dry_run}
    if not args.dry_run:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as f:
            f.write(f"{stamp} copied {copied} ({bytes_copied/1e6:.1f} MB), {current} current\n")
        status.write_text(json.dumps(summary, indent=1))
    print(f"{'would copy' if args.dry_run else 'copied'} {len(todo) if args.dry_run else copied} "
          f"file(s), {current} already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
