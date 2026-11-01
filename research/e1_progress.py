"""E1 progress only: calendar, event count and the next registered boundary. No statistic.

    python research/e1_progress.py

The distinction matters: this file never computes a return, a t-statistic or a z-score. It says how much
of the window has elapsed and how many forced trades exist, so the window can be watched filling without
reading the score early.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATUS = ROOT / "research" / "e1_status.json"
MONITOR = ROOT / "research" / "e1_monitor.json"
OUT = ROOT / "research" / "e1_progress.json"
LOOKS = ["2026-11-30", "2026-12-31", "2027-01-31", "2027-02-28", "2027-03-31", "2027-04-30"]
START = dt.date(2026, 10, 31)
END = dt.date(2027, 4, 30)


def progress(today: dt.date, forced: int, events: int) -> dict:
    elapsed = max(0, (today - START).days)
    total = (END - START).days
    nxt = next((d for d in LOOKS if dt.date.fromisoformat(d) >= today), None)
    idx = LOOKS.index(nxt) if nxt else len(LOOKS) - 1
    boundary = None
    if MONITOR.exists():
        b = json.loads(MONITOR.read_text()).get("boundaries") or []
        boundary = b[idx] if idx < len(b) else None
    return {"window": [START.isoformat(), END.isoformat()], "today": today.isoformat(),
            "elapsed_days": elapsed, "total_days": total,
            "pct": round(100 * elapsed / total, 1) if total else 0.0,
            "events": events, "forced": forced,
            "next_look": nxt, "look_number": idx + 1 if nxt else len(LOOKS),
            "boundary": boundary,
            "note": "progress only — no return, t or z is computed here"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=dt.date.today().isoformat())
    args = ap.parse_args(argv)
    st = json.loads(STATUS.read_text()) if STATUS.exists() else {}
    out = progress(dt.date.fromisoformat(args.today), int(st.get("forced_down_breaks", 0) or 0),
                   int(st.get("events", 0) or 0))
    OUT.write_text(json.dumps(out, indent=1))
    print(f"E1 progress {out['pct']}% ({out['elapsed_days']}/{out['total_days']} days) · "
          f"{out['events']} events · {out['forced']} forced · next look {out['next_look']} "
          f"(boundary {out['boundary']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
