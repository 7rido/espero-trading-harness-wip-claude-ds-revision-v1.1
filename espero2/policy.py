"""Execution policy — Coinbase only.

Hyperliquid testnet orders are not governed here: they are testnet money, and their five guards
already exist in `hl_signed.py`.

    mock  (default)  Coinbase sandbox orders only
    live             recognised, and refused: this project has no authenticated order path

Missing file means `mock`; an unknown value is refused rather than guessed.
"""
from __future__ import annotations

from pathlib import Path

MODES = {"mock", "live"}
FILE = Path("EXECUTION")


class Refused(RuntimeError):
    pass


def mode(path: Path = FILE) -> str:
    raw = path.read_text().strip().lower() if path.exists() else "mock"
    if raw not in MODES:
        raise Refused(f"EXECUTION says {raw!r}; expected one of {sorted(MODES)}")
    return raw


def require_sandbox(path: Path = FILE) -> None:
    """Called before a Coinbase order. Live is recognised and refused."""
    current = mode(path)
    if current == "live":
        raise Refused("EXECUTION=live, but this project has no authenticated Coinbase order path; "
                      "use mock (sandbox) or place the order yourself")
