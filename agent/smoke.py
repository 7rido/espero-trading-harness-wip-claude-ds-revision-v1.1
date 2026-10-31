"""A scripted operator session: what an agent does in practice, with the guards live.

    python -m agent.smoke

It plays the five-step loop an operator runs — see the surface, check health, read the gate, check the
recording, draft the briefing — then tries to trade and is refused. Every step goes through
`agent.tools`, so the audit log proves what happened.
"""
from __future__ import annotations

import json
import pathlib
import sys

from agent import catalog, tools

ROOT = pathlib.Path(__file__).resolve().parents[1]


def show(label: str, out: dict, lines: int = 3) -> None:
    body = (out.get("stdout") or out.get("stderr") or "").strip().splitlines()
    print(f"\n[{label}] exit {out['exit']}  ({out.get('duration_s', '?')}s)")
    for line in body[:lines]:
        print("  " + line[:160])
    if len(body) > lines:
        print(f"  … {len(body) - lines} more lines")


def main() -> int:
    print("agent operator smoke test")
    print(f"surface: {len(catalog.AGENT_VISIBLE)} tools visible, "
          f"{len(catalog.PRIVILEGED)} privileged and never offered")
    print("  " + ", ".join(t.name for t in catalog.AGENT_VISIBLE))

    show("1. health — is the loop alive", tools.run_tool("health"), 2)
    show("2. ledger — what may run", tools.run_tool("ledger"), 1)
    show("3. e1 status — is it recording", tools.run_tool("e1 status"), 4)
    show("4. report — the paper book", tools.run_tool("report"), 3)

    print("\n[5. briefing] deterministic, no model")
    from agent import brief
    print("\n".join("  " + l for l in brief.render().splitlines()[:8]))

    print("\n[6. guard] an operator that tries to trade")
    for name in ("trade", "run"):
        try:
            tools.run_tool(name, {"coin": "BTC", "side": "buy", "qty": "1", "confirm": "true"})
            print(f"  {name}: NOT REFUSED — this is a bug")
            return 1
        except tools.Refused as exc:
            print(f"  {name}: refused — {exc}")

    log = tools.LOG.read_text().splitlines() if tools.LOG.exists() else []
    print(f"\naudit: {len(log)} calls recorded in logs/agent.jsonl")
    if log:
        rec = json.loads(log[-1])
        print(f"  last: {rec['tool']} exit={rec['exit']} sha={rec['output_sha']} at {rec['at']}")
    print("\noperator session complete: read-only work succeeded, trading refused.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
