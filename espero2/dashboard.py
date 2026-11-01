"""A self-contained HTML page for the paper books. No server, no JS dependency.

    python -m espero2.cli dashboard --open
"""
from __future__ import annotations

import html
import json
import time
from pathlib import Path

import os

from . import hl, ledger
from .store import Store

OPTICS = Path(__file__).resolve().parents[1] / "research" / "optics.json"
FORECAST = Path(__file__).resolve().parents[1] / "research" / "forecast.json"
TAPE = Path(__file__).resolve().parents[1] / "research" / "tape.json"
TAPE_LIVE = Path(__file__).resolve().parents[1] / "research" / "tape_live.json"
LIQUIDITY_MAP = Path(__file__).resolve().parents[1] / "research" / "liquidity_map.json"
CARRY = Path(__file__).resolve().parents[1] / "research" / "carry_sleeve.json"
E1PROG = Path(__file__).resolve().parents[1] / "research" / "e1_progress.json"
LIQUIDITY = Path(__file__).resolve().parents[1] / "research" / "forecast_liquidity.json"
LIQDB = Path(__file__).resolve().parents[1] / "research" / "forecast_liquidity.duckdb"

CSS = """
:root{--bg:#0e1116;--card:#161b22;--ink:#e6edf3;--dim:#8b949e;--up:#3fb950;--down:#f85149;--line:#30363d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:20px 24px;border-bottom:1px solid var(--line);display:flex;gap:16px;align-items:baseline}
h1{font-size:16px;margin:0;font-weight:600;letter-spacing:.02em}
.muted{color:var(--dim)}main{padding:20px 24px;display:grid;gap:16px;
grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.coin{font-weight:600;display:flex;justify-content:space-between}
.eq{font-size:26px;font-variant-numeric:tabular-nums;margin:6px 0 2px}
.pos{color:var(--dim);font-size:12px}
table{width:100%;border-collapse:collapse;font-size:12px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:4px 6px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:500}
.up{color:var(--up)}.down{color:var(--down)}
section{grid-column:1/-1}
.map-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.map-coin{border:1px solid var(--line);border-radius:8px;padding:10px}
.map-coin table{margin-top:8px}
.bar{background:#21262d;height:5px;border-radius:3px;overflow:hidden}
.bar span{display:block;height:100%}
"""


def sparkline(values: list[float], width: int = 260, height: int = 48) -> str:
    if len(values) < 2:
        return f'<svg width="{width}" height="{height}"></svg>'
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    step = width / (len(values) - 1)
    pts = " ".join(f"{i * step:.1f},{height - (v - lo) / span * (height - 6) - 3:.1f}"
                   for i, v in enumerate(values))
    colour = "#3fb950" if values[-1] >= values[0] else "#f85149"
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<polyline fill="none" stroke="{colour}" stroke-width="1.6" points="{pts}"/></svg>')


def resolve_address() -> str | None:
    """The public address to show. No key is read: env first, then a plain account.txt."""
    for key in ("ESPERO2_ACCOUNT", "HL_WALLET_ADDRESS"):
        v = (os.environ.get(key) or "").strip()
        if v.startswith("0x"):
            return v
    p = Path("account.txt")
    if p.exists():
        v = p.read_text().strip()
        if v.startswith("0x"):
            return v
    return None


def _account_card(state: dict | None, address: str | None) -> str:
    if not address:
        return ('<div class="card"><div class="coin"><span>testnet account</span></div>'
                '<div class="pos">set HL_WALLET_ADDRESS or write account.txt to show it</div></div>')
    if state is None:
        return ('<div class="card"><div class="coin"><span>testnet account</span></div>'
                f'<div class="pos">{html.escape(address[:10])}… · unavailable right now</div></div>')
    margin = state.get("marginSummary", {})
    value = float(margin.get("accountValue", 0) or 0)
    rows = []
    for p in state.get("assetPositions", []):
        pos = p["position"]
        sz = float(pos.get("szi", 0) or 0)
        if not sz:
            continue
        pnl = float(pos.get("unrealizedPnl", 0) or 0)
        cls = "up" if pnl >= 0 else "down"
        rows.append(f"<tr><td>{html.escape(pos['coin'])}</td><td>{sz:+.6g}</td>"
                    f"<td>{float(pos.get('entryPx') or 0):,.2f}</td><td class={cls}>{pnl:+.2f}</td></tr>")
    body = ("<table><thead><tr><th>coin</th><th>size</th><th>entry</th><th>uPnL</th></tr></thead>"
            f"<tbody>{''.join(rows) or '<tr><td colspan=4 class=muted>flat</td></tr>'}</tbody></table>")
    return (f'<div class="card"><div class="coin"><span>testnet account</span>'
            f'<span class="muted">{html.escape(address[:6])}…{html.escape(address[-4:])}</span></div>'
            f'<div class="eq">${value:,.2f}</div><div class="pos">read-only · public address</div>{body}</div>')


def _equity(store: Store, coin: str) -> list[tuple[int, float]]:
    rows = store.db.execute("SELECT ts, equity FROM equity WHERE coin=? ORDER BY ts", (coin,)).fetchall()
    return [(int(t), float(e)) for t, e in rows]


def _orders(store: Store, limit: int = 20) -> list[tuple]:
    return store.db.execute(
        "SELECT ts, coin, side, qty, px, fee, note FROM orders ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()


RESEARCH = Path(__file__).resolve().parents[1] / "research"


def research_state(root: Path | None = None) -> dict:
    """What the project is waiting on: E1's window and the ledger's gate counts."""
    root = Path(root) if root else RESEARCH
    state: dict = {"e1": {}, "ledger": {}}
    p = root / "e1_status.json"
    if p.exists():
        try:
            e1 = json.loads(p.read_text())
            state["e1"] = {k: e1.get(k) for k in
                           ("window", "window_state", "events", "days_with_events",
                            "forced_down_breaks", "complete_holds")}
        except ValueError:
            state["e1"] = {"error": "unreadable"}
    try:
        rows = ledger.load().values()
        counts: dict[str, int] = {}
        for r in rows:
            counts[r.status] = counts.get(r.status, 0) + 1
        state["ledger"] = {"counts": counts, "holds": counts.get("holds", 0),
                           "strategies": {r.strategy: r.status for r in rows}}
    except Exception:                              # noqa: BLE001 - dashboard must never crash on state
        state["ledger"] = {}
    return state


def alpaca_state() -> dict:
    """Paper account, positions and open orders. A dashboard must never crash on a venue outage."""
    try:
        from . import alpaca
        acct = alpaca.account()
        return {"account": {"cash": acct.get("cash"), "buying_power": acct.get("buying_power"),
                            "portfolio_value": acct.get("portfolio_value"),
                            "status": acct.get("status")},
                "positions": alpaca.positions(), "orders": alpaca.orders("open")}
    except Exception:                              # noqa: BLE001
        return {}


def _alpaca_card(st: dict) -> str:
    if not st:
        return "<section class=\"card\"><h1>alpaca</h1><p class=muted>unavailable</p></section>"
    a = st.get("account", {})

    def direction(p: dict) -> tuple[str, str]:
        side = str(p.get("side") or "").lower()
        if side not in ("long", "short"):
            side = "long" if float(p.get("qty") or 0) >= 0 else "short"
        return side.upper(), ("up" if side == "long" else "down")

    pos = "".join(
        f"<tr><td>{html.escape(str(p.get('symbol')))}</td>"
        f"<td class=\"{cls}\"><b>{side}</b></td>"
        f"<td>{html.escape(str(p.get('qty')))}</td>"
        f"<td>${html.escape(str(p.get('market_value')))}</td>"
        f"<td class=\"{'up' if float(p.get('unrealized_pl') or 0) >= 0 else 'down'}\">"
        f"{html.escape(str(p.get('unrealized_pl')))}</td></tr>"
        for p in st.get("positions", []) for side, cls in [direction(p)])

    orders = "".join(
        f"<tr><td>{html.escape(str(o.get('symbol')))}</td>"
        f"<td class=\"{'down' if str(o.get('side')).lower() == 'sell' else 'up'}\">"
        f"<b>{html.escape(str(o.get('side')).upper())}</b></td>"
        f"<td>{html.escape(str(o.get('qty')))}</td><td>{html.escape(str(o.get('type')))}</td>"
        f"<td>{html.escape(str(o.get('status')))}</td></tr>"
        for o in st.get("orders", []))

    return f"""
    <section class="card"><h1 style="margin-bottom:8px">alpaca · paper</h1>
      <table><thead><tr><th>metric</th><th>value</th></tr></thead><tbody>
        <tr><td>cash</td><td>${html.escape(str(a.get('cash')))}</td></tr>
        <tr><td>buying power</td><td>${html.escape(str(a.get('buying_power')))}</td></tr>
        <tr><td>portfolio value</td><td>${html.escape(str(a.get('portfolio_value')))}</td></tr>
        <tr><td>status</td><td>{html.escape(str(a.get('status')))}</td></tr>
      </tbody></table>
      <h2>positions</h2>
      <table><thead><tr><th>symbol</th><th>direction</th><th>qty</th><th>value</th><th>P&amp;L</th></tr></thead>
      <tbody>{pos or '<tr><td colspan=5 class=muted>flat</td></tr>'}</tbody></table>
      <h2>open orders</h2>
      <table><thead><tr><th>symbol</th><th>side</th><th>qty</th><th>type</th><th>status</th></tr></thead>
      <tbody>{orders or '<tr><td colspan=5 class=muted>none</td></tr>'}</tbody></table>
    </section>"""


def _px(v: float) -> str:
    return f"${v:,.2f}" if v >= 1 else f"${v:,.5f}"


def _big(v: float) -> str:
    if v >= 1e9:
        return f"{v/1e9:,.2f}B"
    if v >= 1e6:
        return f"{v/1e6:,.2f}M"
    return f"{v/1e3:,.1f}k"


def _num(v: float) -> str:
    return "—" if v != v else f"{v:+.1f}%"


def _optics_card() -> str:
    """Universal decision optics written by research/optics.py; empty when the snapshot is missing."""
    try:
        d = json.loads(OPTICS.read_text())
    except (OSError, ValueError):
        return ""
    rows = []
    for m in d.get("markets", []):
        e1 = m.get("e1", {})
        pct = m.get("oi_pct")
        pct_s = "—" if pct is None else f"{pct:.0%}"
        rows.append(
            f"<tr><td><b>{html.escape(m['coin'])}</b><br><span class=muted>{html.escape(m.get('product',''))}</span></td>"
            f"<td>{_px(m['price'])}</td><td>{html.escape(m['state'])}</td>"
            f"<td>{_num(m['funding_binance'])} / {_num(m['funding_hl'])}</td>"
            f"<td>{_big(m['oi_hl'])}</td>"
            f"<td>{pct_s}</td>"
            f"<td>{'<b>CASCADE</b>' if m.get('cascade') else ('BREAK' if e1.get('down_break') else '—')}</td></tr>")
    conns = "".join(
        f"<tr><td>{html.escape(c['name'])}</td><td class=muted>{html.escape(c.get('via',''))}</td>"
        f"<td class={'' if c['ok'] else 'down'}>{'ok' if c['ok'] else 'fail'}</td>"
        f"<td>{c.get('latency_ms','—')} ms</td><td class=muted>{html.escape(c.get('detail',''))}</td></tr>"
        for c in d.get("connections", []))
    srcs = "".join(
        f"<tr><td>{html.escape(s['source'])}</td><td class={'' if s['ok'] else 'down'}>{'ok' if s['ok'] else 'fail'}</td>"
        f"<td class=muted>{html.escape(s.get('detail',''))}</td></tr>"
        for s in d.get("sources", []))
    flags = " · ".join(d.get("flags", []))
    return (f'<section class="card" style="grid-column:1/-1"><h1 style="margin-bottom:8px">'
            f'operator optics · markets</h1><table><thead><tr><th>coin / product</th><th>px</th>'
            f'<th>state</th><th>funding B / HL</th><th>OI (HL)</th><th>OI %ile</th><th>risk</th></tr></thead>'
            f'<tbody>{"".join(rows) or "<tr><td colspan=7 class=muted>no markets</td></tr>"}</tbody></table>'
            f'<h1 style="margin:12px 0 8px">connections</h1>'
            f'<table><thead><tr><th>source</th><th>via</th><th>status</th><th>latency</th><th>detail</th></tr></thead>'
            f'<tbody>{conns}</tbody></table>'
            f'<h1 style="margin:12px 0 8px">data sources</h1>'
            f'<table><thead><tr><th>source</th><th>status</th><th>freshness</th></tr></thead>'
            f'<tbody>{srcs}</tbody></table>'
            f'<div class="muted" style="margin-top:8px">{html.escape(str(d.get("at", "")))}'
            f' · {html.escape(flags)}</div></section>')


def _age_min(ts) -> float:
    try:
        from datetime import datetime, timezone
        stamp = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - stamp).total_seconds() / 60
    except (TypeError, ValueError):
        return float("inf")


def _forecast_card() -> str:
    """Forecasts and gated labels; the banner states the cap, the rows never exceed it."""
    try:
        d = json.loads(FORECAST.read_text())
    except (OSError, ValueError):
        return ""
    rows = []
    for r in d.get("rows", []):
        label = str(r.get("label", ""))
        muted = ' class="muted"' if label in ("UNMAPPED", "CONTEXT ONLY") else ""
        e1style = ' style="color:#d29922"' if label == "E1-FORWARD" else ""
        share = "—" if r["share_up"] != r["share_up"] else f"{r['share_up']:.0%}"
        ci = "" if r["ci_lo"] != r["ci_lo"] else f" ({r['ci_lo']:.0%}–{r['ci_hi']:.0%})"

        def num(v: float) -> str:
            return "—" if v != v else f"{v:+.0f}"

        rows.append(
            f"<tr><td><b>{html.escape(str(r.get('coin')))}</b></td>"
            f"<td>{html.escape(str(r.get('state')))}</td><td>{int(r.get('n', 0)):,}</td>"
            f"<td>{num(r.get('median5', float('nan')))}</td>"
            f"<td>{num(r.get('median20', float('nan')))}</td>"
            f"<td>{share}{ci}</td><td>{num(r.get('net_median20', float('nan')))}</td>"
            f"<td{muted}{e1style}>{html.escape(label)}</td>"
            f"<td class=muted>{html.escape(str(r.get('reason', '')))}</td></tr>")
    g = d.get("guardrails", {})
    stale = _age_min(d.get("at")) > 30 or _age_min(d.get("optics_at")) > 20
    banner = (f'no strategy in holds ({g.get("holds", "?")}) · labels capped at '
              f'<b>{html.escape(str(g.get("max_label", "WATCH")))}</b> · forecasts are conditional '
              f'historical frequencies, market-relative, not advice')
    stale_line = ('<div class="down"><b>stale</b> — snapshot or optics older than the refresh '
                  'window</div>' if stale else "")
    return (f'<section class="card" style="grid-column:1/-1">'
            f'<h1 style="margin-bottom:8px">forecasts &amp; recommendations</h1>'
            f'<div class="muted" style="margin-bottom:8px">{banner}</div>{stale_line}'
            f'<table><thead><tr><th>coin</th><th>state</th><th>n</th><th>med 5d</th><th>med 20d</th>'
            f'<th>P(up) 20d</th><th>net 20d</th><th>label</th><th>reason</th></tr></thead>'
            f'<tbody>{"".join(rows) or "<tr><td colspan=9 class=muted>no rows</td></tr>"}</tbody>'
            f'</table></section>')


def _tape_card() -> str:
    """BTC tape: descriptive flow metrics; live slice preferred when fresh, daily otherwise."""
    def load(p: Path):
        try:
            return json.loads(p.read_text())
        except (OSError, ValueError):
            return None

    live, daily = load(TAPE_LIVE), load(TAPE)
    d = live if live and _age_min(live.get("at")) <= 20 else daily
    if not d:
        return ""
    is_live = d is live
    stale = _age_min(d.get("at")) > (20 if is_live else 360)
    prof = d.get("profile", {}) or {}
    blocks = d.get("blocks", {}) or {}
    sweeps = d.get("sweeps", {}) or {}
    ab = d.get("absorption", {}) or {}

    def fnum(v, fmt: str = "{:+.2f}") -> str:
        return "—" if not isinstance(v, (int, float)) or v != v else fmt.format(v)

    flags = ("<div class='down'><b>stale</b> — tape snapshot older than the refresh window</div>"
             if stale else "")
    banner = (f"descriptive flow · venue <b>{html.escape(str(d.get('source')))}</b> · "
              f"{html.escape(str(d.get('day')))} · not a signal")
    row = (f"<tr><td>{d.get('symbol')}</td><td>{int(d.get('prints', 0)):,}</td>"
           f"<td>{float(d.get('buy_share', 0)):.0%}</td><td>{fnum(d.get('cvd'))}</td>"
           f"<td>{int(blocks.get('count', 0)):,} (${float(blocks.get('usd', 0))/1e6:,.1f}M)</td>"
           f"<td>{int(sweeps.get('count', 0)):,}</td>"
           f"<td>{fnum(prof.get('poc_distance_pct'))}%</td>"
           f"<td>{float(ab.get('share', 0)):.0%}</td>"
           f"<td>{html.escape(str(d.get('divergence', 'none')))}</td></tr>")
    return (f'<section class="card" style="grid-column:1/-1">'
            f'<h1 style="margin-bottom:8px">BTC tape</h1>'
            f'<div class="muted" style="margin-bottom:8px">{banner}</div>{flags}'
            f'<table><thead><tr><th>symbol</th><th>prints</th><th>taker buy</th><th>CVD</th>'
            f'<th>blocks</th><th>sweeps</th><th>POC dist</th><th>absorption</th>'
            f'<th>divergence</th></tr></thead><tbody>{row}</tbody></table>'
            f'<div class="muted" style="margin-top:8px">{html.escape(str(d.get("read", "")))}</div>'
            f'</section>')


def _order_flow_liquidity_card() -> str:
    """Order flow and liquidity map: resting depth, taker flow and the HL liquidation ladder."""
    try:
        d = json.loads(LIQUIDITY_MAP.read_text())
    except (OSError, ValueError):
        return ""
    markets = d.get("markets") or []
    if not markets:
        return ""

    def fnum(v, fmt: str = "{:+.2f}") -> str:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return "—"
        return "—" if f != f else fmt.format(f)

    def usd(v) -> str:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return "—"
        return "—" if f != f else f"${_big(abs(f))}"

    def signed_usd(v) -> str:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return "—"
        return "—" if f != f else f"{'+' if f >= 0 else '-'}${_big(abs(f))}"

    stale = _age_min(d.get("at")) > 30
    flags = ("<div class='down'><b>stale</b> — liquidity snapshot older than the refresh window</div>"
             if stale else "")
    errors = d.get("errors") or []
    if errors:
        flags += (f"<div class='down'>{html.escape('; '.join(str(e) for e in errors)[:300])}</div>")
    at = str(d.get("at", ""))
    banner = (f"liquidity pools: <b>coinbase spot book</b> · order flow: <b>coinbase spot trades</b> · "
              f"liquidation clusters: <b>hyperliquid perp ladder</b> · "
              f"snapshot {html.escape(at[11:19])}Z · not a signal")
    blocks = []
    for m in markets:
        coin = html.escape(str(m.get("coin", "?")))
        mid = m.get("mid")
        if not isinstance(mid, (int, float)) or float(mid) != float(mid):
            reason = str(m.get("error") or "no mid")[:160]
            blocks.append(f"<div class=map-coin><div class=coin><span>{coin}</span>"
                          f"<span class=down>unavailable</span></div>"
                          f"<div class=muted>{html.escape(reason)}</div></div>")
            continue
        mark = m.get("mark")
        if not isinstance(mark, (int, float)) or float(mark) != float(mark):
            mark = mid
        flow = m.get("flow") or {}
        pools = m.get("pools") or []
        clusters = m.get("clusters") or []
        ladder = m.get("ladder") or {}
        head = (f"spot {_px(float(mid))} · spread {fnum(m.get('spread_bps'), '{:.2f}')} bps · "
                f"HL mark {_px(float(mark))}")
        flow_line = (f"{int(flow.get('prints', 0) or 0):,} prints / "
                     f"{fnum(flow.get('span_min'), '{:.1f}')}m · "
                     f"{fnum(flow.get('buy_share'), '{:.0%}')} taker buys · "
                     f"net {signed_usd(flow.get('net_usd', 0))}")
        npos = int(ladder.get("positions", 0) or 0)
        if npos:
            age = _age_min(ladder.get("positions_at"))
            age_txt = ("no timestamp" if age == float("inf")
                       else f"{age / 60:.1f}h ago" if age >= 120 else f"{age:.0f}m ago")
            ladder_line = (f"HL ladder: {npos} pos · sample {usd(ladder.get('sample_usd'))} / "
                           f"OI {usd(ladder.get('oi_usd'))} "
                           f"({fnum(ladder.get('coverage_pct'), '{:.0f}')}%) · "
                           f"nearest any L {fnum(ladder.get('nearest_long_pct'), '{:.1f}')}% / "
                           f"S {fnum(ladder.get('nearest_short_pct'), '{:.1f}')}% · "
                           f"<span class=\"{'down' if age > 120 else 'muted'}\">{age_txt}</span>")
        else:
            ladder_line = "<span class=down>no local Hyperliquid position snapshot</span>"

        max_pool = max((float(p.get("usd", 0) or 0) for p in pools), default=0.0)
        pool_rows = []
        for p in sorted(pools, key=lambda z: (0 if z.get("side") == "ask" else 1,
                                              abs(float(z.get("distance_pct", 0) or 0)))):
            side = str(p.get("side", ""))
            cls = "up" if side == "bid" else "down"
            width = 100 * float(p.get("usd", 0) or 0) / max_pool if max_pool else 0
            pool_rows.append(
                f"<tr><td class={cls}>{html.escape(side)} {_px(float(p.get('price', 0) or 0))}</td>"
                f"<td>{fnum(p.get('distance_pct'), '{:+.2f}')}%</td><td>{usd(p.get('usd'))}</td>"
                f"<td><div class=bar><span style='width:{width:.0f}%;"
                f"background:var(--{cls})'></span></div></td></tr>")
        max_liq = max((float(c.get("usd", 0) or 0) for c in clusters), default=0.0)
        liq_rows = []
        for c in clusters:
            side = str(c.get("side", ""))
            cls = "down" if side == "long" else "up"
            width = 100 * float(c.get("usd", 0) or 0) / max_liq if max_liq else 0
            liq_rows.append(
                f"<tr title='{int(c.get('count', 0) or 0)} position(s)'>"
                f"<td class={cls}>{html.escape(side)} liq {_px(float(c.get('price', 0) or 0))}</td>"
                f"<td>{fnum(c.get('distance_pct'), '{:+.2f}')}%</td><td>{usd(c.get('usd'))}</td>"
                f"<td><div class=bar><span style='width:{width:.0f}%;"
                f"background:var(--{cls})'></span></div></td></tr>")
        blocks.append(
            f"<div class=map-coin><div class=coin><span>{coin}</span>"
            f"<span class=muted>{fnum(m.get('basis_bps'), '{:+.1f}')} bps basis</span></div>"
            f"<div class=pos>{head}</div><div class=pos>{flow_line}</div>"
            f"<div class=pos>{ladder_line}</div>"
            f"<table><thead><tr><th>resting pool</th><th>dist</th><th>notional</th><th></th>"
            f"</tr></thead><tbody>{''.join(pool_rows) or '<tr><td colspan=4 class=muted>no book</td></tr>'}"
            f"</tbody></table>"
            f"<table><thead><tr><th>liq cluster</th><th>dist</th><th>USD</th><th></th></tr></thead>"
            f"<tbody>{''.join(liq_rows) or '<tr><td colspan=4 class=muted>no clusters</td></tr>'}"
            f"</tbody></table></div>")
    return (f'<section class="card" style="grid-column:1/-1">'
            f'<h1 style="margin-bottom:8px">order flow &amp; liquidity map</h1>'
            f'<div class="muted" style="margin-bottom:8px">{banner}</div>{flags}'
            f'<div class="map-grid">{"".join(blocks)}</div>'
            f'<div class="muted" style="margin-top:10px">{html.escape(str(d.get("read", "")))}</div>'
            f'</section>')


def _carry_card() -> str:
    """Paper delta-neutral carry sleeve; live state written by research/carry_sleeve.py."""
    try:
        d = json.loads(CARRY.read_text())
    except (OSError, ValueError):
        return ""
    rows = []
    for coin, p in (d.get("positions") or {}).items():
        rows.append(f"<tr><td><b>{html.escape(coin)}</b></td>"
                    f"<td>${p['spot_entry']:,.2f} / ${p['perp_entry']:,.2f}</td>"
                    f"<td>{p.get('funding_cum', 0):+.2f}</td><td>{p.get('fees', 0):.2f}</td>"
                    f"<td>{p.get('net', 0):+.2f}</td></tr>")
    closed = "".join(f"<li>{html.escape(c['coin'])}: {html.escape(str(c['reason']))} "
                     f"({c['net']:+.2f})</li>" for c in d.get("closed", []))
    banner = (f"paper delta-neutral · {len(d.get('positions') or {})} open · "
              f"net {d.get('net', 0):+.2f} · not authorised")
    return (f'<section class="card" style="grid-column:1/-1">'
            f'<h1 style="margin-bottom:8px">carry sleeve</h1>'
            f'<div class="muted" style="margin-bottom:8px">{banner}</div>'
            f'<table><thead><tr><th>coin</th><th>spot / perp entry</th><th>funding</th>'
            f'<th>fees</th><th>net</th></tr></thead><tbody>'
            f'{"".join(rows) or "<tr><td colspan=5 class=muted>flat</td></tr>"}</tbody></table>'
            f'{"<ul class=muted>" + closed + "</ul>" if closed else ""}</section>')


def _e1_card() -> str:
    """E1 progress: calendar and counts only. Never a return, t or z."""
    try:
        d = json.loads(E1PROG.read_text())
    except (OSError, ValueError):
        return ""
    nxt = d.get("next_look") or "—"
    boundary = d.get("boundary")
    b_s = "—" if boundary is None else f"{boundary:.2f}"
    return (f'<section class="card" style="grid-column:1/-1">'
            f'<h1 style="margin-bottom:8px">E1 progress</h1>'
            f'<div class="muted" style="margin-bottom:8px">progress only — no statistic is computed '
            f'here; the window is read at the registered looks</div>'
            f'<table><thead><tr><th>window</th><th>elapsed</th><th>events</th>'
            f'<th>forced trades</th><th>next look</th><th>boundary (z)</th></tr></thead>'
            f'<tbody><tr><td>{html.escape(str(d.get("window")))}</td>'
            f'<td>{d.get("pct", 0):.1f}% ({d.get("elapsed_days")}/{d.get("total_days")} d)</td>'
            f'<td>{int(d.get("events", 0)):,}</td><td><b>{int(d.get("forced", 0)):,}</b></td>'
            f'<td>{html.escape(str(nxt))} (look {d.get("look_number")})</td>'
            f'<td>{html.escape(b_s)}</td></tr></tbody></table>'
            f'<div class="muted" style="margin-top:8px">{html.escape(str(d.get("note", "")))}</div>'
            f'</section>')


def _liquidity_card() -> str:
    """Hyperliquid venue liquidity (candidate feature) + the forecast audit verdict."""
    try:
        d = json.loads(LIQUIDITY.read_text())
    except (OSError, ValueError):
        return ""
    stale = _age_min(d.get("fetched_at")) > 30
    try:
        import duckdb
        con = duckdb.connect(str(LIQDB), read_only=True)
        exch = con.execute("SELECT COUNT(*) FROM exchange_snapshots").fetchone()[0]
        coins = con.execute("SELECT COUNT(*) FROM coin_snapshots").fetchone()[0]
        con.close()
    except Exception:                                  # noqa: BLE001
        exch = coins = 0
    top = sorted(d.get("coins", []), key=lambda c: c.get("oi_usd", 0), reverse=True)[:5]
    rows = "".join(
        f"<tr><td>{html.escape(c['coin'])}</td><td>${c['price']:,.2f}</td>"
        f"<td>{_big(c['oi_usd'])}</td><td>{c.get('funding_pct', 0):+.4f}%</td></tr>" for c in top)
    flags = ("<div class='down'><b>stale</b> — liquidity snapshot older than 30 min</div>"
             if stale else "")
    banner = (f"candidate feature · no history yet · <b>not used</b> in the forecast · "
              f"{html.escape(str(d.get('exchange')))} · {html.escape(str(d.get('fetched_at'))) }")
    return (f'<section class="card" style="grid-column:1/-1">'
            f'<h1 style="margin-bottom:8px">HL venue liquidity &amp; forecast audit</h1>'
            f'<div class="muted" style="margin-bottom:8px">{banner}</div>{flags}'
            f'<table><thead><tr><th>metric</th><th>value</th><th>metric</th><th>value</th></tr></thead>'
            f'<tbody><tr><td>open interest</td><td>{_big(d.get("open_interest_usd", 0))}</td>'
            f'<td>24 h volume</td><td>{_big(d.get("volume_24h_usd", 0))}</td></tr>'
            f'<tr><td>24 h liquidations</td><td>{_big(d.get("liq_24h_usd", 0))} '
            f'(L {d.get("long_share", 0):.0%})</td>'
            f'<td>contracts</td><td>{int(d.get("contracts", 0))}</td></tr>'
            f'<tr><td>taker / maker fee</td><td>{d.get("taker_fee_pct", 0):.1f} / '
            f'{d.get("maker_fee_pct", 0):.1f} bps</td>'
            f'<td>history</td><td>{exch} exchange · {coins} coin snapshots</td></tr></tbody></table>'
            f'<h1 style="margin:12px 0 8px;font-size:14px">top open interest</h1>'
            f'<table><thead><tr><th>coin</th><th>px</th><th>OI</th><th>funding</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
            f'<div class="muted" style="margin-top:8px">forecast audit: all models tested, '
            f'<b>no model promoted</b> (16-state CRPS 0.08051 vs unconditional 0.08030) — '
            f'see research/FORECAST_AUDIT.md</div></section>')


def render(store: Store, out: Path, *, address: str | None = None,
           account_state: dict | None = None, alpaca_override: dict | None = None) -> Path:
    h = store.health()
    coins = store.coins()
    cards = []
    total_now, total_start = 0.0, 0.0
    for coin in coins:
        eq = _equity(store, coin)
        if not eq:
            continue
        start, now = eq[0][1], eq[-1][1]
        total_now += now
        total_start += start
        pct = (now / start - 1) * 100 if start else 0.0
        st = store.get_state(coin)
        cls = "up" if pct >= 0 else "down"
        if st["qty"] > 0:
            pos = f"long {st['qty']:.6f} @ {st['entry_px']:.2f}"
        elif st["qty"] < 0:
            pos = f"short {abs(st['qty']):.6f} @ {st['entry_px']:.2f}"
        else:
            pos = "flat"
        cards.append(f"""
        <div class="card">
          <div class="coin"><span>{html.escape(coin)}</span>
            <span class="muted">{time.strftime('%H:%M', time.localtime(eq[-1][0]))}</span></div>
          <div class="eq">${now:,.2f}</div>
          <div class="{cls}">{pct:+.2f}% · {pos}</div>
          {sparkline([e for _, e in eq])}
        </div>""")

    rows = "".join(
        f"<tr><td>{time.strftime('%m-%d %H:%M', time.localtime(t))}</td><td>{html.escape(c)}</td>"
        f"<td class=\"{'up' if s == 'buy' else 'down'}\">{s}</td><td>{q:.6f}</td><td>{p:,.2f}</td>"
        f"<td>{f:.4f}</td><td class=muted>{html.escape(n or '')}</td></tr>"
        for t, c, s, q, p, f, n in _orders(store))

    alp = alpaca_override if alpaca_override is not None else alpaca_state()
    rs = research_state()
    e1 = rs.get("e1", {})
    counts = ", ".join(f"{k} {v}" for k, v in sorted(rs.get("ledger", {}).get("counts", {}).items()))
    research_rows = f"""
      <thead><tr><th>research</th><th>value</th></tr></thead>
      <tr><td>E1 window</td><td>{html.escape(str(e1.get('window')))}</td></tr>
      <tr><td>E1 state</td><td>{html.escape(str(e1.get('window_state')))}</td></tr>
      <tr><td>days recorded</td><td>{html.escape(str(e1.get('days_with_events')))}</td></tr>
      <tr><td>events</td><td>{html.escape(str(e1.get('events')))}</td></tr>
      <tr><td>ledger</td><td>{html.escape(counts or 'none')}</td></tr>
      <tr><td>holds</td><td>{html.escape(str(rs.get('ledger', {}).get('holds', 0)))}</td></tr>
    """
    led = "".join(f"<tr><td>{html.escape(r.id)}</td><td>{html.escape(r.strategy)}</td>"
                  f"<td>{html.escape(r.status)}</td><td>{html.escape(r.estimator_matches_claim)}</td>"
                  f"<td>{html.escape(r.economic_bar)}</td><td class=muted>{html.escape(r.note)}</td></tr>"
                  for r in ledger.load().values())

    beat = f"heartbeat {h['age']}s ago" if h["age"] is not None else "no heartbeat"
    state = "stale" if h["stale"] else "ok"
    total = (f"${total_now:,.2f} · {100 * (total_now / total_start - 1):+.2f}%"
             if total_start else "—")
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<title>espero2 · paper</title><style>{CSS}</style></head>
<body>
<header><h1>espero2 · paper</h1>
  <span class="muted">testnet data · {time.strftime('%Y-%m-%d %H:%M:%S')}</span>
  <span class="muted">{html.escape(beat)} — {state}</span>
  <span class="muted">total {total}</span></header>
<main>
{_account_card(account_state, address)}
{''.join(cards)}
<section class="card"><h1 style="margin-bottom:8px">orders</h1>
<table><thead><tr><th>time</th><th>coin</th><th>side</th><th>qty</th><th>px</th><th>fee</th><th>note</th></tr></thead>
<tbody>{rows or '<tr><td colspan=7 class=muted>none yet</td></tr>'}</tbody></table></section>
{_alpaca_card(alp)}
{_optics_card()}
{_forecast_card()}
{_tape_card()}
{_order_flow_liquidity_card()}
{_carry_card()}
{_e1_card()}
{_liquidity_card()}
    <section class="card"><h1 style="margin-bottom:8px">research state</h1>
    <table>{research_rows}</table>
    </section>
    <section class="card"><h1 style="margin-bottom:8px">strategy ledger</h1>
<table><thead><tr><th>id</th><th>strategy</th><th>status</th><th>statistic</th><th>cost bar</th><th>note</th></tr></thead>
<tbody>{led}</tbody></table></section>
</main></body></html>"""
    out.write_text(page)
    return out
