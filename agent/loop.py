"""Optional LLM loop. Off by default; needs DEEPSEEK_API_KEY. Tools come from the catalog and
`privileged` tools are never offered, no matter what the model asks for.

    python -m agent.loop --dry-run          # show the offered tools, no model call
    python -m agent.loop --task "..."       # one turn, max 12 tool calls
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.request

from agent import catalog, tools

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAX_CALLS = 12
MAX_TURNS = 3
ENDPOINT = "https://api.deepseek.com/chat/completions"


def tool_schema() -> list[dict]:
    return [{"type": "function", "function": {
        "name": t.name.replace(" ", "_"),
        "description": t.description,
        "parameters": {"type": "object", "properties": {
            a: {"type": "string"} for a in t.args}, "required": list(t.required)}}} for t in catalog.AGENT_VISIBLE]


def _by_function_name() -> dict[str, catalog.ToolSpec]:
    return {t.name.replace(" ", "_"): t for t in catalog.AGENT_VISIBLE}


def call_model(messages: list[dict], key: str) -> dict:
    payload = {"model": "deepseek-chat", "messages": messages, "tools": tool_schema()}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=120) as r:          # noqa: S310 - fixed https host
        return json.loads(r.read())


def run(task: str, client=None, key: str | None = None) -> dict:
    if client is None and not key:
        raise SystemExit("no DEEPSEEK_API_KEY: the loop is off by default; use --dry-run or agent.brief")
    messages = [{"role": "system", "content":
                 "You operate a trading research project. You may only call the offered tools. "
                 "Never place orders; privileged tools are refused by the executor. Cite artifacts."},
                {"role": "user", "content": task}]
    calls = 0
    transcript = []
    for _turn in range(MAX_TURNS):
        resp = client(messages) if client else call_model(messages, key)
        msg = resp["choices"][0]["message"]
        messages.append(msg)
        wanted = msg.get("tool_calls") or []
        if not wanted:
            return {"answer": msg.get("content", ""), "calls": calls, "transcript": transcript}
        for call in wanted:
            if calls >= MAX_CALLS:
                raise SystemExit("tool-call cap reached")
            fn = call["function"]["name"]
            spec = _by_function_name().get(fn)
            if spec is None:
                raise SystemExit(f"model asked for {fn!r}, which is not in the agent catalog")
            args = json.loads(call["function"].get("arguments") or "{}")
            out = tools.run_tool(spec.name, args, mode="agent")
            calls += 1
            transcript.append({"tool": spec.name, "args": args, "exit": out["exit"]})
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": (out["stdout"] or out["stderr"] or "")[:4000]})
    return {"answer": "turn cap reached", "calls": calls, "transcript": transcript}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="agent.loop")
    ap.add_argument("--task", default="Give me the current briefing: E1, paper book, ledger.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.dry_run:
        print(json.dumps({"tools": [t.name for t in catalog.AGENT_VISIBLE],
                          "privileged_never_offered": [t.name for t in catalog.TOOLS
                                                       if t.klass == "privileged"]}, indent=1))
        return 0
    out = run(args.task, key=os.environ.get("DEEPSEEK_API_KEY"))
    print(out["answer"])
    print(f"[{out['calls']} tool calls]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
