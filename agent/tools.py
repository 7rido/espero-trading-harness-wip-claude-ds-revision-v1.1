"""The only executor an agent gets. Subprocess, no shell, allowlist, audit log.

    python -m agent.tools list
    python -m agent.tools run --name ledger
    python -m agent.tools run --name cb bars --arg symbols=AAPL --arg timeframe=1Day
    python -m agent.tools run --name run            # refused: privileged
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import pathlib
import subprocess
import sys

from agent import catalog

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "agent.jsonl"
LOCK = ROOT / "logs" / "agent.lock"
SPILL = ROOT / "logs"
MAX_OUT = 256 * 1024
SECRET_ENV = ("HL_PRIVATE_KEY", "COINBASE_API_SECRET", "APCA_API_SECRET_KEY",
              "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ESPERO_WEBHOOK_URL")


class Refused(RuntimeError):
    pass


def clean_env() -> dict[str, str]:
    """Everything the tools need except secrets; secrets are only exposed to specs that declare it."""
    keep = {k: v for k, v in os.environ.items() if k not in SECRET_ENV and "SECRET" not in k.upper()}
    keep["PYTHONDONTWRITEBYTECODE"] = "1"
    return keep


def resolve(spec: catalog.ToolSpec, args: dict[str, str]) -> list[str]:
    values = catalog.validate_args(spec, args)
    values.setdefault("python", sys.executable)
    argv = []
    for part in spec.argv:
        if part == "{python}":
            argv.append(sys.executable)
            continue
        if part.startswith("{") and part.endswith("}"):
            key = part[1:-1]
            if key not in values:
                raise Refused(f"{spec.name}: no value for {part}")
            argv.append(values[key])
        else:
            argv.append(part)
    for part in argv:
        if any(ch in part for ch in (";", "|", "&", "$(", "`", ">", "<")):
            raise Refused(f"{spec.name}: refusing shell metacharacters in {part!r}")
    return argv


def run_tool(name: str, args: dict[str, str] | None = None, *, mode: str = "agent",
             dry_run: bool = False) -> dict:
    spec = catalog.get(name)
    if spec.klass == "privileged" and mode == "agent":
        raise Refused(f"{name!r} is privileged: an agent may not place orders, start loops or open the UI")
    argv = resolve(spec, args or {})
    if dry_run:
        return {"tool": name, "argv": argv, "dry_run": True, "ok": True}

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise Refused("another agent tool call is running") from exc
        started = dt.datetime.now(dt.timezone.utc)
        try:
            proc = subprocess.run(argv, cwd=ROOT, env=clean_env(), capture_output=True,
                                  timeout=spec.timeout, text=True)      # noqa: S603 - allowlisted argv
            code, out, err = proc.returncode, proc.stdout, proc.stderr
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            code, out, err, timed_out = 124, (exc.stdout or ""), (exc.stderr or ""), True
    digest = hashlib.sha256(((out or "") + (err or "")).encode()).hexdigest()[:16]
    spill = None
    if len(out or "") > MAX_OUT:
        spill = SPILL / f"spill-{digest}.txt"
        spill.write_text(out)
        out = out[:MAX_OUT] + f"\n[... truncated, full output at {spill.relative_to(ROOT)}]"
    record = {"at": started.isoformat(timespec="seconds"), "tool": name, "argv": argv,
              "mode": mode, "exit": code, "timed_out": timed_out, "output_sha": digest,
              "duration_s": round((dt.datetime.now(dt.timezone.utc) - started).total_seconds(), 2)}
    with LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return {"tool": name, "argv": argv, "exit": code, "timed_out": timed_out,
            "stdout": out, "stderr": err, "ok": code == 0 and not timed_out, "spill": str(spill) if spill else None}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="agent.tools")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("--name", required=True)
    r.add_argument("--arg", action="append", default=[], metavar="KEY=VALUE")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--mode", default="agent", choices=["agent", "human"])
    args = ap.parse_args(argv)

    if args.cmd == "list":
        for t in catalog.AGENT_VISIBLE:
            print(f"{t.name:20s} {t.klass:9s} {t.description}")
        return 0

    kv = {}
    for pair in args.arg:
        if "=" not in pair:
            print(f"bad --arg {pair!r}: expected KEY=VALUE", file=sys.stderr)
            return 2
        k, v = pair.split("=", 1)
        kv[k] = v
    try:
        out = run_tool(args.name, kv, mode=args.mode, dry_run=args.dry_run)
    except (Refused, KeyError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if out.get("dry_run"):
        print(" ".join(out["argv"]))
        return 0
    if out["stdout"]:
        print(out["stdout"], end="")
    if out["stderr"]:
        print(out["stderr"], end="", file=sys.stderr)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
