"""The tool catalog: every operation an agent may run, classified.

Nothing executes here; `agent.tools` is the only executor and it refuses anything not in this file.
The CLI entries are checked against `espero2.cli.build_parser()` by tests, so a new subcommand cannot
silently appear without a classification.
"""
from __future__ import annotations

import dataclasses
import re


@dataclasses.dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    argv: tuple[str, ...]          # "{python}" is replaced by sys.executable; "{arg}" by a validated arg
    klass: str                     # read | research | write | privileged
    args: tuple[str, ...] = ()
    required: tuple[str, ...] = ()
    timeout: int = 300
    outputs: tuple[str, ...] = ()


# Verbs that can move money or start a loop are never offered to the model.
PRIVILEGED = ("run", "order", "trade", "cb order", "ui")

TOOLS: tuple[ToolSpec, ...] = (
    # ---- reads -------------------------------------------------------------
    ToolSpec("state", "testnet account and positions (read-only)",
             ("{python}", "-m", "espero2.cli", "state"), "read", timeout=60),
    ToolSpec("report", "paper journal summary",
             ("{python}", "-m", "espero2.cli", "report"), "read", timeout=120),
    ToolSpec("ledger", "strategy ledger: what may run and why",
             ("{python}", "-m", "espero2.cli", "ledger"), "read", timeout=60),
    ToolSpec("health", "is the paper loop alive (exit 1 if stale)",
             ("{python}", "-m", "espero2.cli", "health"), "read", timeout=120),
    ToolSpec("book", "current testnet book for a coin",
             ("{python}", "-m", "espero2.cli", "book", "--coin", "{coin}"), "read",
             args=("coin",), required=("coin",), timeout=60),
    ToolSpec("backtest", "the SMA rule on the committed panel",
             ("{python}", "-m", "espero2.cli", "backtest"), "read", timeout=300),
    ToolSpec("cb account", "Alpaca paper account",
             ("{python}", "-m", "espero2.cli", "cb", "account"), "read", timeout=60),
    ToolSpec("cb positions", "Alpaca paper positions",
             ("{python}", "-m", "espero2.cli", "cb", "positions"), "read", timeout=60),
    ToolSpec("cb clock", "Alpaca market clock",
             ("{python}", "-m", "espero2.cli", "cb", "clock"), "read", timeout=60),
    ToolSpec("cb bars", "Alpaca bars for one or more symbols",
             ("{python}", "-m", "espero2.cli", "cb", "bars", "--symbols", "{symbols}",
              "--timeframe", "{timeframe}"), "read",
             args=("symbols", "timeframe"), required=("symbols",), timeout=120),
    ToolSpec("cb orders", "Alpaca open or all orders",
             ("{python}", "-m", "espero2.cli", "cb", "orders", "--status", "{status}"), "read",
             args=("status",), timeout=60),
    # ---- research (writes only under research/) ----------------------------
    ToolSpec("metrics fetch", "Binance daily metrics (OI, positioning) into the substrate",
             ("{python}", "research/metrics_fetch.py", "--symbol", "{symbol}"), "write",
             args=("symbol",), required=("symbol",), timeout=1800,
             outputs=("data_substrate/substrate.duckdb",)),
    ToolSpec("book fetch", "bookTicker -> per-minute order-book imbalance",
             ("{python}", "research/book_fetch.py", "--day", "{day}"), "write",
             args=("day",), required=("day",), timeout=900,
             outputs=("data_substrate/substrate.duckdb",)),
    ToolSpec("liquidations fetch", "fetch recent perp liquidations (OKX public feed) into the substrate",
             ("{python}", "research/liquidation_fetch.py", "--coin", "{coin}"), "write",
             args=("coin",), required=("coin",), timeout=600,
             outputs=("data_substrate/substrate.duckdb",)),
    ToolSpec("funding fetch", "fetch perp funding (Binance archive, Hyperliquid, OKX) into the substrate",
             ("{python}", "research/funding_fetch.py", "--coin", "{coin}"), "write",
             args=("coin",), required=("coin",), timeout=600,
             outputs=("data_substrate/substrate.duckdb",)),
    ToolSpec("spot", "fresh keyless spot snapshot (Coinbase Exchange): price, spread, depth at size",
             ("{python}", "research/spot.py", "--product", "{product}", "--notional", "{notional}"),
             "read", args=("product", "notional"), required=("product",), timeout=120),
    ToolSpec("coin report", "per-coin research snapshot from the substrate",
             ("{python}", "research/coin_report.py", "--coin", "{coin}"), "read",
             args=("coin",), required=("coin",), timeout=300),
    ToolSpec("signals", "read-only SMA-regime snapshot for a coin list",
             ("{python}", "research/signals.py", "--coins", "{coins}"), "read",
             args=("coins",), required=("coins",), timeout=120),
    ToolSpec("audit check", "verify the 46-id audit citations",
             ("{python}", "research/audit_by_number.py", "--check"), "research",
             timeout=120, outputs=()),
    ToolSpec("e1 status", "E1 recording status (never the score)",
             ("{python}", "research/e1_recorder.py"), "research",
             timeout=120, outputs=("research/e1_status.json",)),
    ToolSpec("regimes build", "rebuild the regime state table",
             ("{python}", "research/regimes.py", "build"), "research",
             timeout=300, outputs=("research/regimes.csv",)),
    ToolSpec("conditional suite", "recompute the state-conditional distributions",
             ("{python}", "research/conditional_suite.py"), "research",
             timeout=600, outputs=("research/conditional_suite.json",)),
    # ---- writes (inside the repo only) -------------------------------------
    ToolSpec("dashboard", "rewrite dashboard.html (no browser launch)",
             ("{python}", "-m", "espero2.cli", "dashboard", "--out", "dashboard.html"), "write",
             timeout=120, outputs=("dashboard.html",)),
    # ---- privileged: present so the catalog is complete; refused to agents --
    ToolSpec("run", "start or continue the paper loop", ("{python}", "-m", "espero2.cli", "run"),
             "privileged"),
    ToolSpec("order", "Hyperliquid testnet order", ("{python}", "-m", "espero2.cli", "order"),
             "privileged"),
    ToolSpec("trade", "one paper order across venues", ("{python}", "-m", "espero2.cli", "trade"),
             "privileged"),
    ToolSpec("cb order", "Coinbase sandbox order (mock)", ("{python}", "-m", "espero2.cli", "cb", "order"),
             "privileged"),
    ToolSpec("ui", "interactive terminal UI", ("{python}", "-m", "espero2.cli", "ui"),
             "privileged"),
)

BY_NAME = {t.name: t for t in TOOLS}
AGENT_VISIBLE = tuple(t for t in TOOLS if t.klass != "privileged")

# A CLI subcommand is either represented above or listed here with the reason it is not.
CLI_COVERAGE = {
    "run": "run", "order": "order", "trade": "trade", "ui": "ui", "state": "state",
    "report": "report", "ledger": "ledger", "health": "health", "book": "book",
    "backtest": "backtest", "dashboard": "dashboard", "cb": "cb order",
}
CLI_EXTRA = {"cb": ("account", "positions", "clock", "bars", "orders", "order")}

SAFE_ARG = re.compile(r"^[A-Za-z0-9_.,/=:+-]{1,120}$")   # no spaces, no shell metacharacters


def get(name: str) -> ToolSpec:
    if name not in BY_NAME:
        raise KeyError(f"unknown tool {name!r}; known: {', '.join(sorted(BY_NAME))}")
    return BY_NAME[name]


def validate_args(spec: ToolSpec, args: dict[str, str]) -> dict[str, str]:
    """Only declared args, all values matching SAFE_ARG, everything required present."""
    unknown = set(args) - set(spec.args)
    if unknown:
        raise ValueError(f"{spec.name}: unknown arguments {sorted(unknown)}")
    missing = [a for a in spec.required if not args.get(a)]
    if missing:
        raise ValueError(f"{spec.name}: missing required arguments {missing}")
    for key, value in args.items():
        v = str(value)
        if not SAFE_ARG.match(v):
            raise ValueError(f"{spec.name}: argument {key!r} has unsafe characters")
        if ".." in v or v.startswith("/") or v.startswith("~"):
            raise ValueError(f"{spec.name}: argument {key!r} may not reference paths outside the repo")
    return {k: str(v) for k, v in args.items()}
