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
    <section class="card"><h1 style="margin-bottom:8px">research state</h1>
    <table>{research_rows}</table>
    </section>
    <section class="card"><h1 style="margin-bottom:8px">strategy ledger</h1>
<table><thead><tr><th>id</th><th>strategy</th><th>status</th><th>statistic</th><th>cost bar</th><th>note</th></tr></thead>
<tbody>{led}</tbody></table></section>
</main></body></html>"""
    out.write_text(page)
    return out
