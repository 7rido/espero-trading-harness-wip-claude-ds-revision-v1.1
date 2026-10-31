"""Health check for the anything-unattended parts: the 07:45 copy and the E1 feed.

    python scripts/health_check.py            # human lines, exit 1 on any FAIL
    python scripts/health_check.py --json     # machine-readable

Checks, in order:
  sync    the 07:45 copy ran within 30 h and its source still exists
  feed    the aggr 5-minute feed is arriving while the E1 window is open
  ledger  #27's ledger is growing (no breaks for 7 days inside the window is a FAIL)
  window  where E1 is: not opened, open with N days left, or closed

A WARN never fails the run; a FAIL always does. Writes logs/health.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SYNC_STATUS = "logs/sync-status.json"
FEED = "data/aggr/forward5m"
LEDGER = "liqbreak_trades.csv"
WINDOW_FROM = dt.date(2026, 10, 31)
WINDOW_TO = dt.date(2027, 4, 30)
SYNC_MAX_AGE_H = 30.0
FEED_MAX_AGE_H = 48.0
LEDGER_SILENT_DAYS = 7


def _sync(root: pathlib.Path, now: dt.datetime) -> tuple[str, str]:
    p = root / SYNC_STATUS
    if not p.exists():
        return "FAIL", "no sync-status.json: the 07:45 copy has never run"
    try:
        st = json.loads(p.read_text())
        at = dt.datetime.fromisoformat(st["at"])
    except (ValueError, KeyError):
        return "FAIL", "sync-status.json unreadable"
    age = (now - at.astimezone(dt.timezone.utc)).total_seconds() / 3600
    src = pathlib.Path(st.get("source", ""))
    if not src.is_dir():
        return "FAIL", f"sync source missing: {src}"
    if age > SYNC_MAX_AGE_H:
        return "FAIL", f"last copy {age:.1f} h ago (limit {SYNC_MAX_AGE_H:.0f} h)"
    return "OK", f"last copy {age:.1f} h ago, {st.get('copied', 0)} files"


def _feed(root: pathlib.Path, now: dt.datetime) -> tuple[str, str]:
    d = root / FEED
    open_days = (now.date() - WINDOW_FROM).days if now.date() >= WINDOW_FROM else -1
    grace = 0 <= open_days <= 1          # the first day's file arrives at the next 07:30 run
    if not d.is_dir() or not any(d.glob("*")):
        if open_days < 0:
            return "WARN", f"{FEED} not created yet (window not open)"
        if grace:
            return "WARN", f"{FEED} empty; first file expected after the next 07:30 run"
        return "FAIL", f"{FEED} empty {open_days} days into the window"
    files = sorted(d.glob("*"))
    newest = max(f.stat().st_mtime for f in files)
    age = (now.timestamp() - newest) / 3600
    if age > FEED_MAX_AGE_H:
        return "FAIL", f"newest feed file {age:.1f} h old (limit {FEED_MAX_AGE_H:.0f} h)"
    return "OK", f"{len(files)} files, newest {age:.1f} h old"


def _ledger(root: pathlib.Path, now: dt.datetime) -> tuple[str, str]:
    p = root / LEDGER
    if not p.exists():
        return "WARN", "no liqbreak_trades.csv yet"
    rows = p.read_text().strip().splitlines()
    n = max(0, len(rows) - 1) if rows else 0
    if WINDOW_FROM <= now.date() <= WINDOW_TO:
        elapsed = (now.date() - WINDOW_FROM).days
        if n == 0 and elapsed >= LEDGER_SILENT_DAYS:
            return "FAIL", f"no breaks recorded in {elapsed} days of the open window"
    if n == 0:
        return "OK", "ledger present, no breaks yet"
    return "OK", f"{n} breaks"


def _window(now: dt.datetime) -> tuple[str, str]:
    if now.date() < WINDOW_FROM:
        return "OK", f"not opened ({WINDOW_FROM}); {(WINDOW_FROM - now.date()).days} days to go"
    if now.date() <= WINDOW_TO:
        return "OK", f"open; {(WINDOW_TO - now.date()).days} days left"
    return "OK", "closed; score with --score"


def run(root: pathlib.Path = ROOT, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    checks = {"sync": _sync(root, now), "feed": _feed(root, now),
              "ledger": _ledger(root, now), "window": _window(now)}
    failed = [k for k, (state, _) in checks.items() if state == "FAIL"]
    out = {"at": now.isoformat(timespec="seconds"),
           "checks": {k: {"state": s, "detail": d} for k, (s, d) in checks.items()},
           "failures": failed, "ok": not failed}
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "health.json").write_text(json.dumps(out, indent=1))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args(argv)
    out = run(pathlib.Path(args.root))
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        for name, c in out["checks"].items():
            print(f"{c['state']:4s} {name:7s} {c['detail']}")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
