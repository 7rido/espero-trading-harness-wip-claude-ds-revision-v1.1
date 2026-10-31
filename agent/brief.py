"""Deterministic daily briefing. No LLM, no network except the repo's own files.

    python -m agent.brief            # markdown to stdout + research/agent/brief-YYYY-MM-DD.md
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sqlite3
import sys

from espero2 import ledger

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "agent"


def e1() -> dict:
    p = ROOT / "research" / "e1_status.json"
    if not p.exists():
        return {"state": "no status file"}
    try:
        d = json.loads(p.read_text())
    except ValueError:
        return {"state": "unreadable"}
    return {"window": d.get("window"), "state": d.get("window_state"),
            "days": d.get("days_with_events"), "events": d.get("events"),
            "trades": d.get("forced_down_breaks")}


def paper() -> list[dict]:
    p = ROOT / "paper.db"
    if not p.exists():
        return []
    con = sqlite3.connect(p)
    rows = con.execute("""
        SELECT e.coin, e.equity FROM equity e
        JOIN (SELECT coin, MAX(ts) AS ts FROM equity GROUP BY coin) m ON m.coin = e.coin AND m.ts = e.ts
        ORDER BY e.coin""").fetchall()
    con.close()
    return [{"coin": c, "equity": round(v, 2)} for c, v in rows]


def health() -> dict:
    p = ROOT / "logs" / "health.json"
    if not p.exists():
        return {"ok": None}
    try:
        return json.loads(p.read_text())
    except ValueError:
        return {"ok": None}


def render() -> str:
    rows = ledger.load()
    counts: dict[str, int] = {}
    for r in rows.values():
        counts[r.status] = counts.get(r.status, 0) + 1
    e = e1()
    h = health()
    lines = [f"# Briefing — {dt.date.today().isoformat()}", "",
             "## Research that is waiting",
             f"- E1 window: {e.get('window')} · state {e.get('state')} · "
             f"{e.get('days')} days recorded · {e.get('events')} events",
             f"- holds: {counts.get('holds', 0)} · statuses: "
             + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())),
             "", "## Paper book"]
    for p in paper():
        lines.append(f"- {p['coin']}: {p['equity']}")
    if not paper():
        lines.append("- none")
    lines += ["", "## Unattended jobs",
              f"- health ok: {h.get('ok')} · failures: {h.get('failures', [])}",
              "", "## The question that matters",
              "- Has anything cleared the gate since the last briefing? "
              "If no: nothing new is authorised, and the paper books are void plumbing data."]
    return "\n".join(lines) + "\n"


def main() -> int:
    text = render()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"brief-{dt.date.today().isoformat()}.md"
    path.write_text(text)
    print(text)
    print(f"[written {path.relative_to(ROOT)}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
