"""Forecasts and gated recommendations from the conditional historical distributions.

    python research/forecast.py

For each market in the live optics snapshot, look up its regime state in the historical study and
report the 5/20-day distribution. The label rubric is fixed here and hard-capped: while no strategy is
in `holds`, the strongest label the card can produce is WATCH. Nothing here can order, and no label is
a buy/sell recommendation.

Exit codes: 0 ok · 3 optics snapshot missing or empty (previous forecast is kept).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OPTICS = ROOT / "research" / "optics.json"
STATES = ROOT / "research" / "regime_signs.json"
SELECTION = ROOT / "research" / "selection_cost.json"
E1 = ROOT / "research" / "e1_status.json"
LEDGER = ROOT / "strategy_ledger.csv"
OUT = ROOT / "research" / "forecast.json"

COST_BPS = 9.0                 # measured round-trip cost, Binance books
RANK = {"UNMAPPED": 0, "CONTEXT ONLY": 1, "E1-BREAK": 2, "E1-FORWARD": 2.5, "WATCH": 3}
STALE_MIN = 20


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return float("nan"), float("nan")
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def holdings() -> int:
    try:
        rows = list(csv.DictReader(LEDGER.open()))
    except OSError:
        return 0
    return sum(1 for r in rows if (r.get("status") or "").strip() == "holds")


def cap(label: str, holds: int) -> str:
    """The single enforcement point: no label may outrank WATCH while holds is zero."""
    rank = RANK.get(label, 99)          # unknown labels are treated as the strongest claim
    if holds == 0 and rank > RANK["WATCH"]:
        return "WATCH"
    return label


def build_rows(markets: list[dict], states: dict, e1: dict, holds: int) -> list[dict]:
    """Rubric in one place: every label passes through cap() before it is emitted."""
    window_open = e1.get("window_state") == "open"
    forced = int(e1.get("forced_down_breaks", 0) or 0)
    last_day = str(e1.get("last_day") or "")
    confirmed = forced > 0 and last_day >= (dt.date.today() - dt.timedelta(days=2)).isoformat()
    rows = []
    for m in markets:
        state = m.get("state", "n/a")
        c20 = states.get((state, 20))
        c5 = states.get((state, 5))
        spread = m.get("spread_bps")
        cost = COST_BPS + (spread if isinstance(spread, (int, float)) and spread == spread else 0.0)
        share = float(c20["share_up"]) if c20 else float("nan")
        n = int(c20["n"]) if c20 else 0
        lo, hi = wilson(share, n) if c20 else (float("nan"), float("nan"))
        med20 = float(c20["median_bps"]) if c20 else float("nan")
        net20 = med20 - cost if c20 else float("nan")
        e1_break = bool((m.get("e1") or {}).get("down_break"))

        if not c20:
            label, reason = "UNMAPPED", f"no historical cell for state {state!r}; no forecast"
        elif e1_break and window_open and confirmed:
            label = "E1-FORWARD"
            reason = (f"E1 confirmed forced trade recorded ({last_day}); forward test, NOT authorised. "
                      f"cell: {med20:+.0f} bps median 20d, {share:.0%} up (n={n:,})")
        elif e1_break and window_open:
            label = "E1-BREAK"
            reason = (f"down-break on the live proxy, forced tag NOT yet confirmed "
                      f"({forced} forced trades recorded; last {last_day or 'n/a'})")
        elif not c20.get("fdr_pass"):
            label = "CONTEXT ONLY"
            reason = (f"{med20:+.0f} bps median 20d, {share:.0%} up (n={n:,}, CI {lo:.0%}-{hi:.0%}); "
                      f"fails multiplicity; cost {cost:.1f} bps -> no trade")
        else:
            label = "WATCH"
            reason = (f"cell passes FDR; capped at WATCH because no strategy is in holds "
                      f"({med20:+.0f} bps median 20d)")
        label = cap(label, holds)
        rows.append({
            "coin": m.get("coin"), "product": m.get("product"), "state": state,
            "price": m.get("price"), "n": n,
            "median5": float(c5["median_bps"]) if c5 else float("nan"),
            "median20": med20, "p10": float(c20["p10"]) if c20 else float("nan"),
            "p90": float(c20["p90"]) if c20 else float("nan"),
            "share_up": share, "ci_lo": lo, "ci_hi": hi,
            "cost_bps": cost, "net_median20": net20,
            "e1_break": e1_break, "label": label, "reason": reason})
    return rows


def main() -> int:
    if not OPTICS.exists():
        print("no optics snapshot; forecast left unchanged")
        return 3
    optics = json.loads(OPTICS.read_text())
    markets = optics.get("markets") or []
    if not markets:
        print(f"optics snapshot has 0 markets ({optics.get('at')}); forecast left unchanged")
        return 3
    states = {(c["state"], c["h"]): c for c in json.loads(STATES.read_text())} if STATES.exists() else {}
    e1 = json.loads(E1.read_text()) if E1.exists() else {}
    holds = holdings()

    rows = build_rows(markets, states, e1, holds)

    out = {"at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
           .isoformat(timespec="seconds"),
           "optics_at": optics.get("at"),
           "guardrails": {"holds": holds, "max_label": "WATCH", "cost_bps": COST_BPS,
                          "source": "regime_signs 2023-01..2025-06, market-relative",
                          "note": "conditional historical frequencies, not advice; no order path"},
           "rows": rows}
    OUT.write_text(json.dumps(out, indent=1))
    from collections import Counter
    counts = Counter(r["label"] for r in rows)
    print(f"wrote {OUT.relative_to(ROOT)} · {len(rows)} markets · holds {holds} · "
          f"{dict(counts)}")
    for r in rows:
        print(f"  {str(r['coin']):5s} {r['state']:>14s} {r['median20']:+8.0f} bps 20d  "
              f"{r['share_up']:>4.0%} up  {r['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
