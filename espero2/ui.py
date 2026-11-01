"""`espero2 ui` — the terminal home screen, in the same grammar as the original espero UI.

Status panels on top, one action per choice, every action also a plain command. Reads only
`paper.db` (three coin books), never the old project's journals.

    python -m espero2.cli ui
"""
from __future__ import annotations

import subprocess
import json
import time
from pathlib import Path
from typing import List, Optional

from . import hl, ledger
from .paper import Costs, tick
from .strategy import sma_cross
from .store import Store

ACCENT = "#d97757"
MUTED = "grey58"
BLOCKS = "▁▂▃▄▅▆▇█"

# the mascot: the Claude Code blob, stretched into a dog, looking right — the original app's.
MASCOT = [
    "▗▄▄▄▄▄▄▄▐▛██▜▌ ",
    "▝▜██████▜████▛▘",
    "  ▘▘ ▝▝  ▘▘ ▝▝ ",
]

try:  # the TUI extra is optional: the plain CLI must work without it
    import questionary
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    STYLE = questionary.Style([
        ("qmark", f"fg:{ACCENT} bold"),
        ("question", "bold"),
        ("pointer", f"fg:{ACCENT} bold"),
        ("highlighted", f"fg:{ACCENT} bold"),
        ("selected", f"fg:{ACCENT}"),
        ("answer", f"fg:{ACCENT} bold"),
        ("instruction", "fg:#8b8f94"),
    ])
except ImportError:  # pragma: no cover
    questionary = None


# ------------------------------------------------------------------- helpers
def spark(vals: List[float], width: int = 32) -> str:
    if not vals:
        return ""
    vals = vals[-width:]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    return "".join(BLOCKS[min(7, int((v - lo) / span * 7))] for v in vals)


def _ago(ts: Optional[int]) -> str:
    if not ts:
        return "never"
    d = max(0, int(time.time()) - int(ts))
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if d >= size:
            return f"{d // size}{unit} ago"
    return f"{d}s ago"


def _series(store: Store, coin: str) -> list[tuple[int, float]]:
    rows = store.db.execute("SELECT ts, equity FROM equity WHERE coin=? ORDER BY ts", (coin,)).fetchall()
    return [(int(t), float(e)) for t, e in rows]


def _holds(store: Store, coin: str) -> str:
    st = store.get_state(coin)
    if st["qty"] > 0:
        return f"long {st['qty']:.6f} @ {st['entry_px']:,.2f}"
    if st["qty"] < 0:
        return f"short {abs(st['qty']):.6f} @ {st['entry_px']:,.2f}"
    return "flat"


# --------------------------------------------------------------------- panels
def header(store: Store) -> "Panel":
    h = store.health()
    coins = store.coins()
    total = sum(s[-1][1] for c in coins if (s := _series(store, c)))
    paused = Path("KILL").exists()

    line1 = Text()
    line1.append("espero2", style="bold")
    line1.append("  paper accounts  ", style=MUTED)
    line1.append(f"${total:,.2f}", style=f"bold {ACCENT}")
    if paused:
        line1.append("   PAUSED (KILL file)", style="bold red")

    line2 = Text()
    line2.append("heartbeat ", style=MUTED)
    line2.append(_ago(h["heartbeat"]), style="green" if not h["stale"] else "bold red")
    line2.append("  ·  ", style=MUTED)
    line2.append("ok" if not h["stale"] else "STALE", style="green" if not h["stale"] else "bold red")
    line2.append(f"  ·  every {h['every']}s  ·  journal paper.db", style=MUTED)

    line3 = Text()
    line3.append("books  ", style=MUTED)
    line3.append("  ·  ".join(f"{c} {len(_series(store, c))} marks" for c in coins) or "none yet",
                 style=MUTED)

    art = Text("\n".join(MASCOT), style=f"bold {ACCENT}")
    body = Text.assemble(line1, "\n", line2, "\n", line3)
    grid = Table.grid(padding=(0, 2))
    grid.add_column(no_wrap=True)
    grid.add_column()
    grid.add_row(art, body)
    return Panel(grid, border_style=MUTED, padding=(0, 1))


def accounts_table(store: Store) -> "Table":
    tbl = Table(show_header=True, header_style=MUTED, box=None, padding=(0, 2), expand=False)
    for col, just in (("account", "left"), ("equity", "right"), ("day", "right"),
                      ("P&L", "right"), ("curve", "left"), ("holds", "left")):
        tbl.add_column(col, justify=just)
    for coin in store.coins():
        rows = _series(store, coin)
        if not rows:
            tbl.add_row(coin, "-", "", "", "", "not started")
            continue
        eq = rows[-1][1]
        prev = rows[-2][1] if len(rows) > 1 else eq
        start = rows[0][1]
        day = eq - prev
        pnl = (eq / start - 1) * 100 if start else 0.0
        colour = "green" if day >= 0 else "red"
        tbl.add_row(coin, f"${eq:,.2f}", Text(f"{day:+,.2f}", style=colour),
                    Text(f"{pnl:+.2f}%", style="green" if pnl >= 0 else "red"),
                    Text(spark([e for _, e in rows]), style=ACCENT), _holds(store, coin))
    return tbl


def orders_table(store: Store, limit: int = 8) -> "Table":
    tbl = Table(show_header=True, header_style=MUTED, box=None, padding=(0, 2), expand=False)
    for col, just in (("time", "left"), ("coin", "left"), ("side", "left"), ("qty", "right"),
                      ("price", "right"), ("fee", "right"), ("why", "left")):
        tbl.add_column(col, justify=just)
    rows = store.db.execute(
        "SELECT ts, coin, side, qty, px, fee, note FROM orders ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    for ts, coin, side, qty, px, fee, note in rows:
        tbl.add_row(time.strftime("%m-%d %H:%M", time.localtime(ts)), coin,
                    Text(side, style="green" if side == "buy" else "red"),
                    f"{qty:.6f}", f"{px:,.2f}", f"{fee:.4f}", note or "")
    if not rows:
        tbl.add_row("—", "", "", "", "", "", "none yet")
    return tbl


def ledger_table() -> "Table":
    tbl = Table(show_header=True, header_style=MUTED, box=None, padding=(0, 2), expand=False)
    for col in ("id", "strategy", "status", "statistic", "cost bar", "note"):
        tbl.add_column(col)
    for r in ledger.load().values():
        style = {"plumbing": "yellow", "trial": "yellow", "holds": "green", "retired": "red"}.get(r.status, "")
        note = r.note if len(r.note) <= 60 else r.note[:57] + "..."
        tbl.add_row(r.id, r.strategy, Text(r.status, style=style), r.estimator_matches_claim,
                    r.economic_bar, note)
    return tbl


def render(console: "Console", store: Store) -> None:
    console.print(header(store))
    console.print(accounts_table(store))
    console.print()
    console.print(Text("recent orders", style="bold"))
    console.print(orders_table(store))
    console.print()
    console.print(Text("strategy ledger", style="bold"))
    console.print(ledger_table())


# -------------------------------------------------------------------- actions
def _cycle(console: "Console", store: Store, coins: list[str]) -> None:
    for coin in coins:
        try:
            r = tick(store, coin, notional=100.0, costs=Costs(4.5, 2.0))
        except hl.Refused as exc:
            console.print(f"[red]refused:[/] {exc}")
            return
        except Exception as exc:  # noqa: BLE001 - one coin must not stop the others
            console.print(f"[red]{coin} error:[/] {type(exc).__name__}: {exc}")
            continue
        act = "; ".join(r["actions"]) or "hold"
        console.print(f"{time.strftime('%H:%M:%S')} {coin:4s} mid={r['mid']:,.2f} "
                      f"signal={r['signal'].side or '-':4s} | {act} | equity ${r['equity']:,.2f}")
    store.beat()


def _toggle_pause(console: "Console") -> None:
    kill = Path("KILL")
    if kill.exists():
        kill.unlink()
        console.print("resumed (KILL removed)")
    else:
        kill.write_text("paused from the ui\n")
        console.print("paused (KILL created)")



# ------------------------------------------------------- paper actions (manual)
def _book_usd(store: Store, coin: str, px: float) -> float:
    st = store.get_state(coin)
    return st["cash"] + st["qty"] * px


def buy_manual(console, store: Store, coin: str, usd: float,
               costs: Costs = Costs()) -> None:
    from .strategy import Signal
    book = hl.book(coin)
    px = book.ask * (1 + costs.slippage_bps / 1e4)
    st = store.get_state(coin)
    if st["qty"] != 0:
        console.print(f"[yellow]{coin}: a position is open — close it first[/]")
        return
    if usd > st["cash"]:
        console.print(f"[yellow]{coin}: only ${st['cash']:,.2f} in cash[/]")
        return
    qty = usd / px
    fee = usd * costs.taker_bps / 1e4
    store.order(int(time.time()), coin, "buy", qty, px, fee, "taker", "manual buy")
    store.set_state(coin, cash=st["cash"] - qty * px - fee, qty=qty, entry_px=px,
                    entry_ts=int(time.time()))
    store.mark(coin, int(time.time()), store.get_state(coin)["cash"], qty, px, book.mid)
    console.print(f"bought {qty:.6f} {coin} @ {px:,.2f} (fee ${fee:.4f})")


def close_manual(console, store: Store, coin: str, costs: Costs = Costs()) -> None:
    st = store.get_state(coin)
    if st["qty"] == 0:
        console.print(f"[yellow]{coin}: no position[/]")
        return
    book = hl.book(coin)
    qty = st["qty"]
    if qty > 0:                                  # sell a long at the bid
        px = book.bid * (1 - costs.slippage_bps / 1e4)
        fee = qty * px * costs.taker_bps / 1e4
        pnl = (px - st["entry_px"]) * qty - fee
        side = "sell"
    else:                                        # buy back a short at the ask
        px = book.ask * (1 + costs.slippage_bps / 1e4)
        fee = abs(qty) * px * costs.taker_bps / 1e4
        pnl = (st["entry_px"] - px) * abs(qty) - fee
        side = "buy"
    store.order(int(time.time()), coin, side, abs(qty), px, fee, "taker", "manual close")
    store.set_state(coin, cash=st["cash"] + qty * px - fee, qty=0.0, entry_px=0.0, entry_ts=0)
    store.mark(coin, int(time.time()), store.get_state(coin)["cash"], 0.0, 0.0, book.mid)
    console.print(f"closed {coin} @ {px:,.2f} (fee ${fee:.4f}, P&L ${pnl:+,.2f})")


def reset_book(console, store: Store, coin: str, cash: float = 1000.0) -> None:
    store.set_state(coin, cash=cash, qty=0.0, entry_px=0.0, entry_ts=0)
    store.mark(coin, int(time.time()), cash, 0.0, 0.0, 0.0)
    console.print(f"{coin}: reset to ${cash:,.2f}")



def _paper_menu(console, store: Store, coins: list[str]) -> None:
    what = questionary.select("Paper", pointer="❯", style=STYLE, choices=[
        "Buy by hand", "Close by hand", "Back"]).ask()
    if not what or what == "Back":
        return
    coin = questionary.select("Which book?", choices=coins, style=STYLE, pointer="❯").ask()
    if not coin:
        return
    if what == "Buy by hand":
        usd = questionary.text("Dollars:", default="100", style=STYLE).ask() or "100"
        try:
            buy_manual(console, store, coin, float(usd))
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]{exc}[/]")
    else:
        close_manual(console, store, coin)


def _tail_log(console, n: int = 25) -> None:
    for name in ("sup.log", "loop.log"):
        p = Path(name)
        if p.exists():
            for line in p.read_text().splitlines()[-n:]:
                style = "red" if " error" in line.lower() else None
                console.print(Text(line, style=style))
            return
    console.print(Text("no log yet (sup.log / loop.log)", style=MUTED))




# ---------------------------------------------------------------- research state
def _json(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def e1_rows(d: dict) -> list[tuple[str, str]]:
    if not d:
        return [("state", "no progress file")]
    return [("window", " → ".join(d.get("window", ["?", "?"]))),
            ("elapsed", f"{d.get('pct', 0):.1f}% ({d.get('elapsed_days')}/{d.get('total_days')} d)"),
            ("events", f"{d.get('events', 0):,}"),
            ("forced trades", f"{d.get('forced', 0):,}"),
            ("next look", f"{d.get('next_look')} (look {d.get('look_number')})"),
            ("boundary (z)", "—" if d.get("boundary") is None else f"{d['boundary']:.2f}")]


def carry_rows(d: dict) -> list[tuple[str, ...]]:
    rows = []
    for coin, pos in (d.get("positions") or {}).items():
        rows.append((coin, f"${pos['spot_entry']:,.2f} / ${pos['perp_entry']:,.2f}",
                     f"{pos.get('funding_cum', 0):+.2f}", f"{pos.get('fees', 0):.2f}",
                     f"{pos.get('net', 0):+.2f}"))
    return rows


def optics_rows(d: dict, limit: int = 6) -> list[tuple[str, ...]]:
    rows = []
    for m in (d.get("markets") or [])[:limit]:
        risk = "CASCADE" if m.get("cascade") else ("BREAK" if (m.get("e1") or {}).get("down_break") else "—")
        rows.append((m.get("coin", "?"), m.get("state", "?"),
                     f"{m.get('funding_binance', float('nan')):+.1f}% / "
                     f"{m.get('funding_hl', float('nan')):+.1f}%",
                     f"{m.get('oi_hl', 0):,.0f}", risk))
    return rows


def forecast_rows(d: dict, limit: int = 6) -> list[tuple[str, ...]]:
    rows = []
    for r in (d.get("rows") or [])[:limit]:
        rows.append((r.get("coin", "?"), r.get("state", "?"), f"{r.get('median20', 0):+.0f}",
                     "—" if r.get("share_up") != r.get("share_up") else f"{r['share_up']:.0%}",
                     r.get("label", "?")))
    return rows


def tape_row(d: dict) -> list[tuple[str, ...]]:
    if not d:
        return []
    return [(d.get("source", "?"), f"{int(d.get('prints', 0)):,}", f"{d.get('buy_share', 0):.0%}",
             f"{d.get('cvd', 0):+.2f}", d.get("divergence", "—"))]


def _table(title: str, headers: list[str], rows: list[tuple]) -> "Table":
    tbl = Table(title=title, title_style="bold", show_header=True, header_style=MUTED,
                box=None, padding=(0, 2), expand=False)
    for h in headers:
        tbl.add_column(h)
    for r in rows:
        tbl.add_row(*[str(x) for x in r])
    if not rows:
        tbl.add_row(*["—"] * len(headers))
    return tbl


def research_view(console: "Console") -> None:
    console.print(Text("E1 progress — counts only, no statistic", style="bold"))
    console.print(_table("", ["field", "value"], e1_rows(_json("research/e1_progress.json"))))
    console.print()
    console.print(Text("carry sleeve — paper, delta-neutral", style="bold"))
    console.print(_table("", ["coin", "spot / perp entry", "funding", "fees", "net"],
                         carry_rows(_json("research/carry_sleeve.json"))))
    console.print()
    console.print(Text("market optics", style="bold"))
    console.print(_table("", ["coin", "state", "funding B/HL", "OI", "risk"],
                         optics_rows(_json("research/optics.json"))))
    console.print()
    console.print(Text("forecasts — capped at WATCH while no holds", style="bold"))
    console.print(_table("", ["coin", "state", "med 20d", "P(up)", "label"],
                         forecast_rows(_json("research/forecast.json"))))
    tape = tape_row(_json("research/tape_live.json")) or tape_row(_json("research/tape.json"))
    console.print()
    console.print(Text("BTC tape", style="bold"))
    console.print(_table("", ["source", "prints", "taker buy", "CVD", "divergence"], tape))


def _research(console) -> None:
    from rich.markdown import Markdown
    docs = sorted(list(Path("research").glob("RESULTS_*.md")) +
                  list(Path("research").glob("PREREGISTRATION_*.md")))
    if not docs:
        console.print(Text("no research documents", style=MUTED))
        return
    pick = questionary.select("Read which?", pointer="❯", style=STYLE,
                              choices=[d.name[:-3] for d in docs] + ["Back"]).ask()
    if not pick or pick == "Back":
        return
    path = Path("research") / f"{pick}.md"
    with console.pager(styles=True):
        console.print(Markdown(path.read_text()))


def main(state: str = "paper.db") -> int:
    if questionary is None:
        print("the home screen needs the tui extra: pip install rich questionary")
        return 2
    console = Console()
    try:
        ledger.require("sma", allow_plumbing=True)
    except SystemExit as exc:
        console.print(f"[red]gate:[/] {exc}")
        return 1
    store = Store(state)
    coins = ["BTC", "ETH", "SOL"]
    try:
        while True:
            console.clear()
            render(console, store)
            choice = questionary.select(
                "What do you want to do?", pointer="❯", style=STYLE, choices=[
                    "Status & health",
                    "Open the dashboard",
                    "Preview the next decision (no writes)",
                    "Paper trading: buy, close, reset",
                    "Deposit / reset a book",
                    "Pause / resume",
                    "Show the log",
                    "Market optics & research state",
                    "Research documents (research/)",
                    "Run the tests",
                    "Quit",
                ]).ask()
            if choice in (None, "Quit"):
                return 0
            if choice == "Open the dashboard":
                from .dashboard import render as render_html
                out = render_html(store, Path("dashboard.html"))
                console.print(f"wrote {out.resolve()}")
                subprocess.run(["open", str(out.resolve())], check=False)
            elif choice == "Preview the next decision (no writes)":
                for coin in coins:
                    try:
                        bars = hl.closed_candles(coin, bars=300)
                        sig = sma_cross(bars)
                        b = hl.book(coin)
                        console.print(f"{coin:4s} mid {b.mid:,.2f}  spread {b.spread_bps:5.1f}bps  "
                                      f"→ {sig.side or 'hold'}  ({sig.reason})")
                    except Exception as exc:  # noqa: BLE001
                        console.print(f"[red]{coin}: {exc}[/]")
            elif choice == "Paper trading: buy, close, reset":
                _paper_menu(console, store, coins)
            elif choice == "Deposit / reset a book":
                coin = questionary.select("Which book?", choices=coins, style=STYLE, pointer="❯").ask()
                if coin:
                    amt = questionary.text("Cash to set (USD):", default="1000", style=STYLE).ask()
                    if amt:
                        reset_book(console, store, coin, float(amt))
            elif choice == "Pause / resume":
                _toggle_pause(console)
            elif choice == "Show the log":
                _tail_log(console)
            elif choice == "Market optics & research state":
                research_view(console)
            elif choice == "Research documents (research/)":
                _research(console)
            elif choice == "Run the tests":
                subprocess.run([__import__("sys").executable, "-m", "unittest", "discover",
                                "-s", "tests", "-t", "."], cwd=Path.cwd())
            elif choice == "Status & health":
                h = store.health()
                console.print(f"heartbeat {_ago(h['heartbeat'])} (every {h['every']}s) — "
                              f"{'STALE' if h['stale'] else 'ok'}")
            if choice not in ("Refresh",):
                questionary.press_any_key_to_continue(style=STYLE).ask()
    finally:
        store.close()
