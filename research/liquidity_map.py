"""Order flow and liquidity map: book pools, taker flow, and Hyperliquid's exact liquidation ladder.

    python research/liquidity_map.py                 # BTC, ETH, SOL
    python research/liquidity_map.py --coins SOL     # one market
    python research/liquidity_map.py --hl-dir data/hlcollect --out /tmp/map.json

Three descriptive layers, no signal and no order path:

- **Resting pools**: Coinbase spot L2 depth, aggregated into price buckets. A pool is the largest
  notional bucket on each side of the mid, away from the touch, inside +/-2 %.
- **Order flow**: Coinbase spot trades from the last 30 minutes (or the last 1,000 prints when the
  window is thinner): taker buy share, net taker notional and the largest print.
- **Liquidation clusters**: Hyperliquid's public per-position `liquidationPx` for the top-2,000
  accounts by account value, grouped by price. This is the venue's own liquidation ladder, not an
  estimate from leverage or open interest. It is a **sample** of large accounts; coverage against
  venue open interest is written into every snapshot.

The two venues are labelled because they are not the same book. Distances for resting pools use the
Coinbase mid; distances for liquidation clusters use the Hyperliquid mark. The basis between them is
recorded. Nothing here reaches the ledger or the paper loop.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import math
import pathlib
import sys
import urllib.request
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "liquidity_map.json"
HL_DIRS = (ROOT / "data" / "hlcollect", ROOT / "recordings" / "hlcollect")
COINBASE = "https://api.exchange.coinbase.com"
COINS = ("BTC", "ETH", "SOL")
PRODUCTS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"}
UA = {"User-Agent": "espero2/0.1"}

POOL_BUCKET_BPS = 10.0       # 0.10 % price buckets for resting depth
POOL_TOP_N = 3               # per side
POOL_MIN_DIST_BPS = 5.0      # ignore the touch
POOL_MAX_DIST_PCT = 2.0      # the book has far-away orders; keep the map local

LIQ_BUCKET_BPS = 25.0        # 0.25 % price buckets for liquidation prices
LIQ_MIN_SEP_BPS = 50.0       # nearest-neighbour suppression between clusters
LIQ_TOP_N = 3                # per side
LIQ_MAX_DIST_PCT = 30.0      # far liquidation walls are recorded but not mapped

FLOW_MIN = 30
FLOW_MIN_PRINTS = 20
TRADE_LIMIT = 1000


# ------------------------------------------------------------------ primitives
def _get(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _iso(ts: int | float | None) -> str | None:
    if not isinstance(ts, (int, float)) or not math.isfinite(ts) or ts <= 0:
        return None
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


def _age_min(ts) -> float:
    try:
        stamp = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return (dt.datetime.now(dt.timezone.utc) - stamp).total_seconds() / 60
    except (TypeError, ValueError):
        return float("inf")


def _display_path(path: pathlib.Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# ------------------------------------------------------------------ snapshots
def _slot_key(path: pathlib.Path) -> tuple:
    """Sort key for positions/YYYY-MM-DD/HHMM.csv.gz (newest last)."""
    try:
        day = dt.date.fromisoformat(path.parent.name)
        slot = path.name.split(".")[0]
        return (day, int(slot[:2]), int(slot[2:4]), path.stat().st_mtime)
    except (ValueError, OSError):
        return (dt.date.min, -1, -1, 0.0)


def newest_snapshot(roots) -> pathlib.Path | None:
    """The newest position snapshot across every local hlcollect tree."""
    best = None
    for root in roots:
        for path in pathlib.Path(root).glob("positions/*/*.csv.gz"):
            key = _slot_key(path)
            if best is None or key > best[0]:
                best = (key, path)
    return best[1] if best else None


def newest_ctx(roots) -> pathlib.Path | None:
    """The newest context snapshot (mark, open interest) across every local tree."""
    best = None
    for root in roots:
        for path in pathlib.Path(root).glob("ctx/*/*.csv.gz"):
            key = _slot_key(path)
            if best is None or key > best[0]:
                best = (key, path)
    return best[1] if best else None


def load_positions(path: pathlib.Path) -> list[dict]:
    """Every open position with the venue's own liquidation price, skip bad rows."""
    rows = []
    with gzip.open(path, "rt", newline="") as fh:
        for r in csv.DictReader(fh):
            szi = _float(r.get("szi"))
            if not math.isfinite(szi) or szi == 0:
                continue
            value = _float(r.get("value"))
            if not math.isfinite(value) or value <= 0:
                entry = _float(r.get("entry"))
                value = abs(szi) * entry if math.isfinite(entry) else 0.0
            rows.append({
                "ts": int(_float(r.get("ts"))) if math.isfinite(_float(r.get("ts"))) else 0,
                "address": r.get("address", ""),
                "coin": r.get("coin", ""),
                "side": "long" if szi > 0 else "short",
                "szi": szi,
                "entry": _float(r.get("entry")),
                "value": value,
                "liq": _float(r.get("liq")),
                "lev": _float(r.get("lev")),
            })
    return rows


def load_ctx(path: pathlib.Path) -> dict[str, dict]:
    """Per-coin mark, mid and open interest from one context snapshot."""
    out = {}
    with gzip.open(path, "rt", newline="") as fh:
        for r in csv.DictReader(fh):
            coin = r.get("coin", "")
            mark, mid = _float(r.get("mark")), _float(r.get("mid"))
            out[coin] = {
                "mark": mark if math.isfinite(mark) else mid,
                "mid": mid if math.isfinite(mid) else mark,
                "open_interest": _float(r.get("open_interest")),
                "funding": _float(r.get("funding")),
                "day_volume": _float(r.get("day_volume")),
            }
    return out


# ------------------------------------------------------------------ market data
def fetch_book(product: str, depth: int = 2) -> dict:
    """Coinbase spot L2 book; level 2 is the full aggregated book, not just the touch."""
    d = _get(f"{COINBASE}/products/{product}/book?level={depth}")
    bids = [(float(p), float(s)) for p, s, *_ in d.get("bids", [])]
    asks = [(float(p), float(s)) for p, s, *_ in d.get("asks", [])]
    return {"bids": bids, "asks": asks}


def fetch_trades(product: str, limit: int = TRADE_LIMIT) -> list[dict]:
    """Coinbase spot trades, oldest first. `side` is the taker side (checked for agreement)."""
    d = _get(f"{COINBASE}/products/{product}/trades?limit={limit}")
    rows = []
    for t in d:
        try:
            stamp = dt.datetime.fromisoformat(str(t["time"]).replace("Z", "+00:00")).timestamp()
            rows.append({"ts": stamp, "price": float(t["price"]), "size": float(t["size"]),
                         "side": str(t["side"]).lower()})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(rows, key=lambda x: x["ts"])


def flow_stats(trades: list[dict], *, now: float | None = None, window_min: int = FLOW_MIN,
               min_prints: int = FLOW_MIN_PRINTS) -> dict:
    """Taker buy share and net notional, over the window or the available prints."""
    if not trades:
        return {"prints": 0, "span_min": 0.0, "window_min": window_min, "buy_share": float("nan"),
                "net_usd": 0.0, "largest_usd": 0.0, "side_verified": False, "side_agreement": float("nan")}
    now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    cutoff = now - window_min * 60
    rows = [t for t in trades if t["ts"] >= cutoff]
    if len(rows) < min_prints:
        rows = trades[-TRADE_LIMIT:]
    buys = [t["price"] * t["size"] for t in rows if t["side"] == "buy"]
    sells = [t["price"] * t["size"] for t in rows if t["side"] == "sell"]
    buy_usd, sell_usd = sum(buys), sum(sells)
    total = buy_usd + sell_usd
    span = (rows[-1]["ts"] - rows[0]["ts"]) / 60 if len(rows) > 1 else 0.0
    # A taker buy should print at or above the previous print more often than not.
    agree = sum(1 for i in range(1, len(rows))
                if (rows[i]["side"] == "buy" and rows[i]["price"] >= rows[i - 1]["price"])
                or (rows[i]["side"] == "sell" and rows[i]["price"] <= rows[i - 1]["price"]))
    rate = agree / max(len(rows) - 1, 1)
    return {"prints": len(rows), "span_min": round(span, 1), "window_min": window_min,
            "buy_share": buy_usd / total if total else float("nan"),
            "net_usd": buy_usd - sell_usd,
            "largest_usd": max((t["price"] * t["size"] for t in rows), default=0.0),
            "side_verified": rate >= 0.55, "side_agreement": round(rate, 3)}


# ------------------------------------------------------------------ pools
def _book_zones(levels, mid: float, side: str, *, bucket_bps: float = POOL_BUCKET_BPS,
                top_n: int = POOL_TOP_N, min_dist_bps: float = POOL_MIN_DIST_BPS,
                max_dist_pct: float = POOL_MAX_DIST_PCT) -> list[dict]:
    if not levels or not math.isfinite(mid) or mid <= 0:
        return []
    width = mid * bucket_bps / 1e4
    buckets = defaultdict(lambda: {"usd": 0.0, "qty": 0.0, "wsum": 0.0, "levels": 0})
    total = 0.0
    for price, qty in levels:
        if not (math.isfinite(price) and math.isfinite(qty)) or price <= 0 or qty <= 0:
            continue
        if abs(price / mid - 1) * 100 > max_dist_pct:
            continue
        notional = price * qty
        total += notional
        if abs(1e4 * (price / mid - 1)) < min_dist_bps:
            continue
        key = int(price // width)
        bucket = buckets[key]
        bucket["usd"] += notional
        bucket["qty"] += qty
        bucket["wsum"] += price * notional
        bucket["levels"] += 1
    if not buckets:
        return []
    candidates = sorted(buckets, key=lambda k: buckets[k]["usd"], reverse=True)[:top_n * 3]
    groups, current = [], []
    for key in sorted(candidates):
        if current and key - current[-1] <= 1:
            current.append(key)
        else:
            if current:
                groups.append(current)
            current = [key]
    if current:
        groups.append(current)
    zones = []
    for group in groups:
        usd = sum(buckets[k]["usd"] for k in group)
        wsum = sum(buckets[k]["wsum"] for k in group)
        qty = sum(buckets[k]["qty"] for k in group)
        levels_n = sum(buckets[k]["levels"] for k in group)
        if usd <= 0:
            continue
        price = wsum / usd
        zones.append({"side": side, "price": price,
                      "distance_pct": 100 * (price / mid - 1),
                      "usd": usd, "qty": qty, "share": usd / total if total else float("nan"),
                      "levels": levels_n, "bucket_low": min(group) * width,
                      "bucket_high": (max(group) + 1) * width})
    zones.sort(key=lambda z: z["usd"], reverse=True)
    return zones[:top_n]


def book_pools(bids, asks, mid: float, **kwargs) -> list[dict]:
    """Largest resting bid and ask pools within the local book window."""
    return (_book_zones(bids, mid, "bid", **kwargs)
            + _book_zones(asks, mid, "ask", **kwargs))


# ------------------------------------------------------------------ liquidations
def liquidation_clusters(positions: list[dict], mid: float, *,
                         bucket_bps: float = LIQ_BUCKET_BPS, min_sep_bps: float = LIQ_MIN_SEP_BPS,
                         top_n: int = LIQ_TOP_N, max_dist_pct: float = LIQ_MAX_DIST_PCT) -> list[dict]:
    """The venue's exact liquidation prices, grouped into separated clusters per side."""
    if not positions or not math.isfinite(mid) or mid <= 0:
        return []
    width = mid * bucket_bps / 1e4
    out = []
    for side in ("long", "short"):
        buckets = defaultdict(lambda: {"usd": 0.0, "wsum": 0.0, "count": 0})
        total = 0.0
        for p in positions:
            if p.get("side") != side:
                continue
            liq, value = _float(p.get("liq")), _float(p.get("value"))
            if not (math.isfinite(liq) and liq > 0 and math.isfinite(value) and value > 0):
                continue
            if side == "long" and not (mid * (1 - max_dist_pct / 100) <= liq < mid):
                continue
            if side == "short" and not (mid < liq <= mid * (1 + max_dist_pct / 100)):
                continue
            total += value
            bucket = buckets[int(liq // width)]
            bucket["usd"] += value
            bucket["wsum"] += liq * value
            bucket["count"] += 1
        if not buckets:
            continue
        ranked = sorted(buckets.values(), key=lambda b: b["usd"], reverse=True)
        picked = []
        for bucket in ranked:
            price = bucket["wsum"] / bucket["usd"]
            if any(abs(price - q) / mid * 1e4 < min_sep_bps for q in picked):
                continue
            picked.append(price)
            out.append({"side": side, "price": price,
                        "distance_pct": 100 * (price / mid - 1),
                        "usd": bucket["usd"],
                        "long_usd": bucket["usd"] if side == "long" else 0.0,
                        "short_usd": bucket["usd"] if side == "short" else 0.0,
                        "count": bucket["count"],
                        "share": bucket["usd"] / total if total else float("nan")})
            if len(picked) >= top_n:
                break
    out.sort(key=lambda z: (0 if z["side"] == "long" else 1, abs(z["distance_pct"])))
    return out


def _fuel(positions: list[dict], mid: float, side: str, max_dist_pct: float) -> tuple[float, float | None]:
    """Total sampled notional and the nearest liquidation distance on one side."""
    total, nearest = 0.0, None
    for p in positions:
        if p.get("side") != side:
            continue
        liq, value = _float(p.get("liq")), _float(p.get("value"))
        if not (math.isfinite(liq) and liq > 0 and math.isfinite(value) and value > 0):
            continue
        dist = 100 * (liq / mid - 1)
        if side == "long" and not (-max_dist_pct <= dist < 0):
            continue
        if side == "short" and not (0 < dist <= max_dist_pct):
            continue
        total += value
        nearest = abs(dist) if nearest is None else min(nearest, abs(dist))
    return total, nearest


def ladder_summary(positions: list[dict], mid: float, *, max_dist_pct: float = LIQ_MAX_DIST_PCT) -> dict:
    """Coverage and fuel totals for the sampled liquidation ladder."""
    sample = sum(max(0.0, _float(p.get("value"))) for p in positions)
    with_liq = sum(1 for p in positions
                   if math.isfinite(_float(p.get("liq"))) and _float(p.get("liq")) > 0)
    long_usd, nearest_long = _fuel(positions, mid, "long", max_dist_pct)
    short_usd, nearest_short = _fuel(positions, mid, "short", max_dist_pct)
    at = max((int(_float(p.get("ts"))) for p in positions
              if math.isfinite(_float(p.get("ts")))), default=0)
    return {"positions": len(positions), "with_liq": with_liq, "sample_usd": sample,
            "long_usd": long_usd, "short_usd": short_usd,
            "nearest_long_pct": nearest_long, "nearest_short_pct": nearest_short,
            "positions_at": _iso(at), "age_min": round(_age_min(_iso(at)), 1) if at else None}


# ------------------------------------------------------------------ assembly
def market_snapshot(coin: str, book: dict, trades: list[dict], positions: list[dict],
                    ctx: dict | None = None, *, now: float | None = None,
                    flow_min: int = FLOW_MIN, max_dist_pct: float = LIQ_MAX_DIST_PCT) -> dict:
    """One coin's three layers, all distances from their own venue's mid/mark."""
    bids, asks = book.get("bids") or [], book.get("asks") or []
    best_bid = max((p for p, _ in bids), default=float("nan"))
    best_ask = min((p for p, _ in asks), default=float("nan"))
    mid = (best_bid + best_ask) / 2 if math.isfinite(best_bid) and math.isfinite(best_ask) else float("nan")
    spread_bps = 1e4 * (best_ask - best_bid) / mid if mid and math.isfinite(mid) else float("nan")
    mark = _float((ctx or {}).get("mark", mid))
    if not math.isfinite(mark) or mark <= 0:
        mark = mid
    basis_bps = 1e4 * (mark / mid - 1) if mid and math.isfinite(mid) else float("nan")
    pools = book_pools(bids, asks, mid)
    flow = flow_stats(trades, now=now, window_min=flow_min)
    clusters = liquidation_clusters(positions, mark, max_dist_pct=max_dist_pct)
    ladder = ladder_summary(positions, mark, max_dist_pct=max_dist_pct)
    oi_usd = None
    if ctx and math.isfinite(_float(ctx.get("open_interest"))) and math.isfinite(mark):
        oi_usd = _float(ctx.get("open_interest")) * mark
    coverage = 100 * ladder["sample_usd"] / oi_usd if oi_usd else None
    ladder.update({"oi_usd": oi_usd, "coverage_pct": coverage})
    return {"coin": coin, "product": PRODUCTS.get(coin, coin), "mid": mid, "mark": mark,
            "spread_bps": spread_bps, "basis_bps": basis_bps, "flow": flow,
            "pools": pools, "clusters": clusters, "ladder": ladder}


def build(coins=COINS, hl_dirs=HL_DIRS, *, flow_min: int = FLOW_MIN,
          max_dist_pct: float = LIQ_MAX_DIST_PCT, now: float | None = None) -> dict:
    """Fetch the live book/flow, load the newest local HL snapshot, and write the map document."""
    now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    snap = newest_snapshot(hl_dirs)
    ctx_path = newest_ctx(hl_dirs)
    positions = load_positions(snap) if snap else []
    ctx = load_ctx(ctx_path) if ctx_path else {}
    markets, errors = [], []
    for coin in coins:
        try:
            book = fetch_book(PRODUCTS[coin])
        except Exception as exc:                       # noqa: BLE001 - one venue must not stop the map
            errors.append(f"{coin} book: {type(exc).__name__}: {exc}")
            markets.append({"coin": coin, "error": str(exc)[:160]})
            continue
        try:
            trades = fetch_trades(PRODUCTS[coin])
        except Exception as exc:                       # noqa: BLE001 - pools still render without flow
            errors.append(f"{coin} trades: {type(exc).__name__}: {exc}")
            trades = []
        try:
            m = market_snapshot(coin, book, trades, [p for p in positions if p["coin"] == coin],
                                ctx.get(coin), now=now, flow_min=flow_min, max_dist_pct=max_dist_pct)
            markets.append(m)
        except Exception as exc:                       # noqa: BLE001 - malformed data must not stop the map
            errors.append(f"{coin} map: {type(exc).__name__}: {exc}")
            markets.append({"coin": coin, "error": str(exc)[:160]})
    doc = {"at": _iso(now), "venues": {"pools": "coinbase-spot", "flow": "coinbase-spot",
                                       "liquidations": "hyperliquid-perps"},
           "positions_at": _iso(max((p.get("ts", 0) for p in positions), default=0)),
           "positions_source": _display_path(snap),
           "ctx_source": _display_path(ctx_path),
           "windows": {"flow_min": flow_min, "pools_pct": POOL_MAX_DIST_PCT,
                       "liquidation_pct": max_dist_pct},
           "markets": markets, "errors": errors,
           "read": ("Resting depth is where limit orders sit; forced liquidation prices are the "
                    "venue's own ladder for a sample of large accounts. Neither is a forecast.")}
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="order flow and liquidity map")
    ap.add_argument("--coins", nargs="+", default=list(COINS))
    ap.add_argument("--hl-dir", action="append", default=None,
                    help="hlcollect root (repeatable); default data/hlcollect then recordings/hlcollect")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--flow-min", type=int, default=FLOW_MIN)
    ap.add_argument("--liq-pct", type=float, default=LIQ_MAX_DIST_PCT,
                    help="liquidation map window around the mark, percent")
    args = ap.parse_args(argv)
    roots = [pathlib.Path(p) for p in args.hl_dir] if args.hl_dir else list(HL_DIRS)
    doc = build(tuple(c.upper() for c in args.coins), roots, flow_min=args.flow_min,
                max_dist_pct=args.liq_pct)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1))
    shown = _display_path(out)
    parts = []
    for m in doc["markets"]:
        if m.get("error"):
            parts.append(f"{m['coin']} error")
        else:
            pools = m.get("pools") or []
            bids = sum(1 for p in pools if p.get("side") == "bid")
            asks = sum(1 for p in pools if p.get("side") == "ask")
            parts.append(f"{m['coin']} {bids}b/{asks}a {len(m.get('clusters') or [])}liq")
    print(f"wrote {shown} · {' · '.join(parts)} · positions {doc['positions_at'] or 'none'}")
    if doc["errors"]:
        for err in doc["errors"]:
            print(f"  {err}", file=sys.stderr)
    return 0 if any(not m.get("error") for m in doc["markets"]) else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
