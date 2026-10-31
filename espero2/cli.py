"""espero2 — a paper-trading harness on Hyperliquid testnet market data.

    python -m espero2.cli run --coin BTC --once
    python -m espero2.cli run --coin BTC --loop --interval 60
    python -m espero2.cli report
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import hl, ledger, policy
from .paper import Costs, catch_up, tick
from .store import Store


def _cmd_run(args: argparse.Namespace) -> int:
    ledger.require(args.strategy, allow_plumbing=args.allow_plumbing)
    store = Store(args.state)
    coins = args.coin or ["BTC"]
    every = max(1, args.every)
    store.set_state(every=every)
    next_due = time.monotonic()
    while True:
        now = time.monotonic()
        if now >= next_due:
            gap = now - next_due
            if gap > 1.5 * every:                      # the process was asleep
                for coin in coins:
                    try:
                        cu = catch_up(store, coin, interval=args.interval)
                    except Exception as exc:           # noqa: BLE001
                        print(f"{time.strftime('%H:%M:%S')} {coin} catch-up error: {exc}", flush=True)
                        continue
                    if cu["marks"]:
                        print(f"{time.strftime('%H:%M:%S')} catch-up {coin}: {cu['marks']} mark(s) "
                              f"for the {int(gap)}s gap", flush=True)
            for coin in coins:
                try:
                    r = tick(store, coin, notional=args.notional,
                             costs=Costs(args.taker_bps, args.slippage_bps),
                             interval=args.interval, kill=Path(args.kill),
                             allow_short=not args.long_only)
                except hl.Refused as exc:
                    print(f"refused: {exc}", file=sys.stderr)
                    return 2
                except Exception as exc:  # a transient venue/network error must not kill the loop
                    print(f"{time.strftime('%H:%M:%S')} {coin} error: {type(exc).__name__}: {exc}",
                          file=sys.stderr, flush=True)
                    continue
                ts = time.strftime("%H:%M:%S")
                act = "; ".join(r["actions"]) or "hold"
                print(f"{ts} {coin} mid={r['mid']:.2f} spread={r['spread_bps']:.1f}bps "
                      f"signal={r['signal'].side or '-'} | {act} | "
                      f"qty={r['qty']:.6f} equity={r['equity']:.2f}", flush=True)
            store.beat()
            if args.dashboard:
                _write_dashboard(store)
            if args.once:
                return 0
            next_due = time.monotonic() + every
        time.sleep(min(5.0, max(0.2, next_due - time.monotonic())))


def _cmd_report(args: argparse.Namespace) -> int:
    store = Store(args.state)
    print(f"journal   {args.state}")
    total = 0.0
    for coin in store.coins() or ["BTC"]:
        s = store.summary(coin)
        if not s["last"]:
            continue
        ts, eq = s["last"]
        start = s["first"][1] if s["first"] else eq
        total += eq
        print(f"  {coin:4s} equity {eq:9.2f}  (start {start:8.2f}, {100 * (eq / start - 1):+6.2f}%)  "
              f"orders {s['orders']}  fees {s['fees']:.2f}  "
              f"at {time.strftime('%m-%d %H:%M', time.localtime(ts))}")
    if total:
        print(f"  total  {total:9.2f}")
    return 0


def _cmd_ui(args: argparse.Namespace) -> int:
    from .ui import main as ui_main
    return ui_main(args.state)


def _write_dashboard(store: Store, out: str = "dashboard.html", address: str | None = None) -> Path:
    """Render the page, attaching the public testnet account when an address is known."""
    from .dashboard import render, resolve_address
    addr = address or resolve_address()
    state = None
    if addr:
        try:
            state = hl.clearinghouse_state(addr)
        except Exception:                                   # noqa: BLE001 - page must still render
            state = None
    return render(store, Path(out), address=addr, account_state=state)


def _cmd_dashboard(args: argparse.Namespace) -> int:
    store = Store(args.state)
    out = _write_dashboard(store, args.out, args.address)
    print(f"wrote {out.resolve()}")
    if args.open:
        import subprocess
        subprocess.run(["open", str(out.resolve())], check=False)
    return 0


def _cmd_state(args: argparse.Namespace) -> int:
    from . import hl_signed
    hl_signed.load_env()
    try:
        ex, account = hl_signed.exchange(confirm=True)
    except hl_signed.Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    st = hl_signed.state(account)
    margin = st.get("marginSummary", {})
    print(f"account {account}  value {margin.get('accountValue')}  "
          f"withdrawable {st.get('withdrawable')}")
    for p in st.get("assetPositions", []):
        pos = p["position"]
        print(f"  {pos['coin']:8s} szi={pos['szi']} entry={pos['entryPx']} upnl={pos['unrealizedPnl']}")
    return 0


def _cmd_order(args: argparse.Namespace) -> int:
    from . import hl_signed
    hl_signed.load_env()
    try:
        out = hl_signed.place(args.coin, args.side, args.notional,
                               confirm=args.confirm_testnet, allow_short=args.allow_short)
    except hl_signed.Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    Path("account.txt").write_text(out["account"] + "\n")   # public address, for the dashboard
    print(f"testnet order: {out['side'].upper()} {out['sz']} {out['coin']} @ {out['px']} "
          f"(account {out['account']})")
    print(out["response"])
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    from .backtest import Costs as BTCosts, format_report, run_panel
    costs = BTCosts(args.fee_bps, args.slip_bps)
    r = run_panel(Path(args.panel), costs=costs, long_only=args.long_only)
    if not r["books"]:
        print(f"no data under {args.panel}", file=sys.stderr)
        return 2
    print(format_report(r))
    if args.json:
        Path(args.json).write_text(json.dumps({k: v for k, v in r.items() if k != "dates"}, indent=1))
        print(f"wrote {args.json}")
    return 0


def _cmd_cb(args: argparse.Namespace) -> int:
    from . import coinbase as cb
    if args.what == "ticker":
        t = cb.ticker(args.product)
        print(f"{t['product']}  bid {t['bid']:,.2f}  ask {t['ask']:,.2f}  'last' {t['last']:,.2f}  "
              f"({t['time']})")
    elif args.what == "products":
        print(" ".join(cb.products()[:60]))
    elif args.what == "accounts":
        for a in cb.accounts():
            bal = a.get("available_balance", {})
            print(f"{a['uuid'][:8]}  {a['name']:28s} {bal.get('value'):>12s} {bal.get('currency')}")
    elif args.what == "portfolios":
        for p in cb.portfolios():
            print(f"{p['uuid']}  {p['type']:8s} {p['name']}")
    elif args.what == "account":   # alpaca
        from . import alpaca as ap
        try:
            print(json.dumps(ap.account(), indent=1)[:800])
        except ap.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr); return 2
    elif args.what == "positions":
        from . import alpaca as ap
        try:
            for p in ap.positions():
                print(f"{p.get('symbol'):8s} qty {p.get('qty'):>10s} "
                      f"value ${p.get('market_value')} pnl {p.get('unrealized_pl')}")
        except ap.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr); return 2
    elif args.what == "clock":
        from . import alpaca as ap
        try:
            c = ap.clock()
            print(f"market open: {c.get('is_open')}  next open {c.get('next_open')}")
        except ap.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr); return 2
    elif args.what == "bars":
        from . import alpaca as ap
        try:
            fn = ap.crypto_bars if args.crypto else ap.bars
            out = fn(args.symbols, args.timeframe, args.start, args.end)
            bars = (out.get("bars") or {})
            for sym, rows in bars.items():
                print(f"{sym}: {len(rows)} bars, last {rows[-1] if rows else None}")
        except ap.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr); return 2
    elif args.what == "orders":
        from . import alpaca as ap
        try:
            for o in ap.orders(args.status):
                print(f"{o.get('symbol'):8s} {o.get('side'):4s} {o.get('qty'):>8s} "
                      f"{o.get('type'):6s} {o.get('status')}")
        except ap.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr); return 2
    elif args.what == "order":
        from . import alpaca as ap
        try:
            out = ap.place_order(args.symbol, args.qty, args.side, confirm=args.confirm_paper)
            print(f"paper order {out.get('id')} {out.get('symbol')} {out.get('side')} {out.get('qty')}")
        except ap.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr); return 2
    elif args.what == "paper":
        from . import cbpaper
        store = Store(args.state)
        while True:
            try:
                r = cbpaper.tick(store, args.product, notional=args.quote,
                                 send_mock_order=args.send_mock)
            except Exception as exc:  # noqa: BLE001
                print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
                return 2
            act = "; ".join(r["actions"]) or "hold"
            print(f"{time.strftime('%H:%M:%S')} {r['product']} mid={r['mid']:,.2f} "
                  f"signal={r['signal'].side or '-':4s} | {act} | qty={r['qty']:.6f} "
                  f"equity={r['equity']:.2f}", flush=True)
            if args.once:
                return 0
            time.sleep(args.every)
    elif args.what == "live":
        try:
            acc = cb.live_accounts()
        except cb.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        print(f"authenticated read-only · {len(acc)} accounts")
        rows = []
        for a in acc:
            bal = a.get("available_balance") or {}
            try:
                v = float(bal.get("value") or 0)
            except ValueError:
                v = 0.0
            if v > 0:
                rows.append((v, a.get("currency", ""), bal.get("value")))
        for v, cur, val in sorted(rows, reverse=True)[:args.limit]:
            print(f"  {cur:8s} {val}")
        if not rows:
            print("  no non-zero balances")
    elif args.what == "fees":
        try:
            kp = cb.key_permissions()
            tier = cb.fee_tier()
        except cb.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr); return 2
        print(f"key: view={kp['can_view']} trade={kp['can_trade']} transfer={kp['can_transfer']}")
        print(f"tier {tier['tier']}: taker {tier['taker_bps']:.0f} bps · maker {tier['maker_bps']:.0f} bps")
    elif args.what == "product":
        p = cb.product_detail(args.product)
        for k in ("product_id", "status", "base_min_size", "quote_min_size", "price_increment",
                  "base_increment", "trading_disabled"):
            print(f"{k:16s} {p.get(k)}")
    elif args.what == "futures":
        s = cb.futures_status()
        print("US derivatives:", ", ".join(s["venues"]))
        print("retired:", "; ".join(s["retired"]))
        print("futures endpoints (need a CDP JWT):", " ".join(s["futures_endpoints"]))
        print("sandbox:", s["sandbox"])
        print("public market data:", " ".join(s["public_market"]))
    elif args.what == "perps":
        intx = next((p for p in cb.portfolios() if p["type"] == "INTX"), None)
        if not intx:
            print("no INTX (perpetuals) portfolio in the sandbox")
            return 1
        s = cb.perp_portfolio(intx["uuid"])
        print(f"perps portfolio {intx['name']} {intx['uuid'][:8]}")
        print(json.dumps(s, indent=1)[:600])
        for pos in cb.perp_positions(intx["uuid"])[:10]:
            print("  position:", pos)
    elif args.what == "fills":
        for f in cb.fills(args.limit):
            print(f"{f.get('trade_time','')[:19]}  {f.get('product_id'):9s} {f.get('price'):>12s} "
                  f"{f.get('size'):>12s} fee {f.get('commission')}")
    elif args.what == "orders":
        for o in cb.orders(args.limit):
            print(f"{o.get('created_time','')[:19]}  {o.get('product_id'):9s} {o.get('side'):4s} "
                  f"{o.get('status'):10s} {o.get('order_id','')[:8]}")
    elif args.what == "order":
        try:
            policy.require_sandbox()
        except policy.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 3
        try:
            out = cb.place_market(args.product, args.side, args.quote,
                                   confirm=args.confirm_sandbox, sandbox_case=args.sandbox_case)
        except cb.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        print(f"sent: {out['request']['side']} {out['request']['product_id']} "
              f"${args.quote:.2f} (client {out['client_id']})")
        if not out["ok"]:
            print(f"sandbox refused: {out['error']}")
            return 1
        print(f"sandbox answered order {str(out['order_id'])[:8]}"
              f"{'  ** MOCK: it did not echo our client id **' if out['mock'] else ''}")
    return 0


def _cmd_health(args: argparse.Namespace) -> int:
    h = Store(args.state).health()
    if h["age"] is None:
        print("no heartbeat: the loop has never run against this journal")
        return 1
    state = "STALE" if h["stale"] else "ok"
    print(f"heartbeat {h['age']}s ago (every {h['every']}s) — {state}")
    return 1 if h["stale"] else 0


def _cmd_ledger(args: argparse.Namespace) -> int:
    rows = ledger.load()
    print(f"{'strategy':12s} {'status':12s} {'statistic':10s} {'cost bar':9s} note")
    for name, r in rows.items():
        print(f"{name:12s} {r.status:12s} {r.estimator_matches_claim:10s} {r.economic_bar:9s} {r.note}")
    return 0


def _cmd_book(args: argparse.Namespace) -> int:
    b = hl.book(args.coin)
    print(f"{args.coin}  bid {b.bid:.2f}  ask {b.ask:.2f}  mid {b.mid:.2f}  spread {b.spread_bps:.1f} bps")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="espero2", description=__doc__)
    p.add_argument("--state", default="paper.db", help="sqlite journal (default paper.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="one decision cycle, or a loop")
    r.add_argument("--coin", action="append", help="repeatable: --coin BTC --coin ETH")
    r.add_argument("--strategy", default="sma")
    r.add_argument("--long-only", action="store_true", help="ignore short signals")
    r.add_argument("--dashboard", action="store_true",
                   help="rewrite dashboard.html after every cycle (the page reloads it)")
    r.add_argument("--allow-plumbing", action="store_true",
                   help="permit a strategy whose ledger row is plumbing/trial")
    r.add_argument("--interval", default="1h", choices=["1m", "5m", "15m", "1h", "1d"])
    r.add_argument("--notional", type=float, default=100.0)
    r.add_argument("--taker-bps", type=float, default=4.5)
    r.add_argument("--slippage-bps", type=float, default=2.0)
    r.add_argument("--kill", default="KILL")
    r.add_argument("--once", action="store_true")
    r.add_argument("--loop", action="store_true")
    r.add_argument("--every", type=int, default=60, help="seconds between cycles when looping")
    r.set_defaults(func=_cmd_run)

    rep = sub.add_parser("report", help="journal summary")
    rep.set_defaults(func=_cmd_report)

    o = sub.add_parser("order", help="signed TESTNET order (needs env + --confirm-testnet)")
    o.add_argument("--coin", default="BTC")
    o.add_argument("--side", choices=["buy", "sell"], default="buy")
    o.add_argument("--notional", type=float, default=10.0)
    o.add_argument("--confirm-testnet", action="store_true")
    o.add_argument("--allow-short", action="store_true",
                   help="permit a sell that opens a short (off by default)")
    o.set_defaults(func=_cmd_order)

    s = sub.add_parser("state", help="testnet account state (read-only)")
    s.set_defaults(func=_cmd_state)

    u = sub.add_parser("ui", help="interactive terminal home screen")
    u.set_defaults(func=_cmd_ui)

    d = sub.add_parser("dashboard", help="write a self-contained HTML page")
    d.add_argument("--out", default="dashboard.html")
    d.add_argument("--open", action="store_true")
    d.add_argument("--address", help="public address to show (default: env or account.txt)")
    d.set_defaults(func=_cmd_dashboard)

    bt = sub.add_parser("backtest", help="the paper rule on the committed panel (step two)")
    bt.add_argument("--panel", default="data/panel")
    bt.add_argument("--fee-bps", type=float, default=4.5)
    bt.add_argument("--slip-bps", type=float, default=2.0)
    bt.add_argument("--long-only", action="store_true")
    bt.add_argument("--json", default="")
    bt.set_defaults(func=_cmd_backtest)

    cb = sub.add_parser("cb", help="Coinbase: real public prices, sandbox (mock) orders")
    cb.add_argument("what", choices=["ticker", "products", "accounts", "orders", "order",
                                     "portfolios", "perps", "fills", "futures", "live", "paper",
                                     "fees", "product", "account", "positions", "clock", "bars",
                                     "orders"])
    cb.add_argument("--product", default="BTC-USD")
    cb.add_argument("--side", choices=["BUY", "SELL"], default="BUY")
    cb.add_argument("--quote", type=float, default="1")
    cb.add_argument("--limit", type=int, default=10)
    cb.add_argument("--confirm-sandbox", action="store_true")
    cb.add_argument("--once", action="store_true")
    cb.add_argument("--every", type=int, default=60)
    cb.add_argument("--state", default="cb-paper.db")
    cb.add_argument("--send-mock", action="store_true",
                    help="also send the order to the sandbox (shape check; it records nothing)")
    cb.add_argument("--sandbox-case", default=None,
                    help="X-Sandbox header, e.g. PostOrder_insufficient_fund")
    cb.add_argument("--symbols", nargs="+", default=["AAPL"])
    cb.add_argument("--symbol", default="AAPL")
    cb.add_argument("--qty", type=float, default=1.0)
    cb.add_argument("--timeframe", default="1Day")
    cb.add_argument("--start", default=None)
    cb.add_argument("--end", default=None)
    cb.add_argument("--status", default="open")
    cb.add_argument("--confirm-paper", action="store_true")
    cb.add_argument("--crypto", action="store_true", help="crypto bars (BTC/USD) instead of stocks")
    cb.set_defaults(func=_cmd_cb)

    h = sub.add_parser("health", help="is the loop alive? (exit 1 if stale)")
    h.set_defaults(func=_cmd_health)

    g = sub.add_parser("ledger", help="what is allowed to run")
    g.set_defaults(func=_cmd_ledger)

    b = sub.add_parser("book", help="current testnet book")
    b.add_argument("--coin", default="BTC")
    b.set_defaults(func=_cmd_book)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
