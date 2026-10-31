"""A self-contained HTML page for the paper books. No server, no JS dependency.

    python -m espero2.cli dashboard --open
"""
from __future__ import annotations

import html
import time
from pathlib import Path

import os

from . import hl, ledger
from .store import Store

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


def render(store: Store, out: Path, *, address: str | None = None,
           account_state: dict | None = None) -> Path:
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
<section class="card"><h1 style="margin-bottom:8px">strategy ledger</h1>
<table><thead><tr><th>id</th><th>strategy</th><th>status</th><th>statistic</th><th>cost bar</th><th>note</th></tr></thead>
<tbody>{led}</tbody></table></section>
</main></body></html>"""
    out.write_text(page)
    return out
