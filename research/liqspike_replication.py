"""Replication of #21 (liquidation spikes reverse) on the sealed months.

Implements research/PREREGISTRATION_2026-10-30-liqspike.md exactly: hourly liquidation share, spike =
top 2% of the previous 720 observed hours, excess over the all-coin-hour baseline, R signed so a
reversal is positive, day-mean estimator, the original's four criteria.

    python research/liqspike_replication.py
"""
from __future__ import annotations

import gzip
import json
import math
import pathlib
import statistics
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
AGGR = ROOT / "data" / "aggr"
HOLDOUT_START = 1782864000            # 2026-07-01 00:00 UTC
HALF_SPLIT = 1786838400               # 2026-08-16 00:00 UTC
HORIZONS = (1, 4, 24)
WINDOW = 720
SPIKE_Q = 0.98

COINS = {}
for c, venues in {"BTC": "BYO", "ETH": "BYO", "SOL": "BYO", "BNB": "BYO", "XRP": "BO", "ADA": "BYO",
                  "DOGE": "BYO", "AVAX": "BYO", "LINK": "BYO", "TRX": "BO", "LTC": "BYO", "XLM": "BO",
                  "HBAR": "BYO", "SHIB": "O"}.items():
    m = {"B": f"BINANCE_FUTURES:{c.lower()}usdt", "Y": f"BYBIT:{c}USDT", "O": f"OKEX:{c}-USDT-SWAP"}
    COINS[c] = {"price": m["B"] if "B" in venues else m["O"], "all": [m[v] for v in venues]}

# one market can appear in both lists; the price market wins, the rest are liquidation sources
MARKET = {}
for _c, _v in COINS.items():
    MARKET[_v["price"]] = (_c, "price")
    for _m in _v["all"]:
        if _m != _v["price"]:
            MARKET[_m] = (_c, "all")


def load() -> dict:
    """part -> coin -> kind -> ts -> [close, dollar volume, lsell, lbuy]"""
    out = {"explore": defaultdict(lambda: defaultdict(dict)),
           "holdout": defaultdict(lambda: defaultdict(dict))}
    for part in ("explore", "holdout"):
        for path in sorted((AGGR / part).glob("*.csv.gz")):
            with gzip.open(path, "rt") as f:
                header = f.readline().rstrip("\n").split(",")
                col = {k: i for i, k in enumerate(header)}
                for line in f:
                    r = line.rstrip("\n").split(",")
                    hit = MARKET.get(r[col["market"]])
                    if hit is None:
                        continue
                    coin, kind = hit
                    ts = int(r[col["time"]])
                    close = float(r[col["close"]] or 0)
                    vol = float(r[col["vbuy"]] or 0) + float(r[col["vsell"]] or 0)
                    cur = out[part][coin][kind].get(ts)
                    ls, lb = float(r[col["lsell"]] or 0), float(r[col["lbuy"]] or 0)
                    if cur is None:
                        out[part][coin][kind][ts] = [close, vol, ls, lb]
                    else:
                        cur[2] += ls
                        cur[3] += lb
    return out


def series(coin: str, data) -> dict:
    """Union of price hours across explore+holdout, with liquidations summed over venues."""
    rows: dict[int, dict] = {}
    for part, hold in (("explore", False), ("holdout", True)):
        price = data[part][coin].get("price", {})
        for ts, (close, vol, ls, lb) in price.items():
            rows[ts] = {"close": close, "vol": vol, "ls": ls, "lb": lb, "holdout": hold}
        for ts, (close, vol, ls, lb) in data[part][coin].get("all", {}).items():
            row = rows.get(ts)
            if row is not None:                      # liquidations only matter where there is a price
                row["ls"] += ls
                row["lb"] += lb
    ts = sorted(rows)
    return {"ts": ts, "rows": rows}


def quantile(values, q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


def day_stats(values, days):
    by_day = defaultdict(list)
    for v, d in zip(values, days):
        by_day[d].append(v)
    daily = [sum(v) / len(v) for v in by_day.values()]
    if len(daily) < 3:
        return float("nan"), float("nan"), len(daily)
    m = sum(daily) / len(daily)
    return m, m / (statistics.stdev(daily) / math.sqrt(len(daily))), len(daily)


def main() -> None:
    data = load()
    events = []
    base_sum, base_n = defaultdict(float), defaultdict(int)

    for coin in COINS:
        s = series(coin, data)
        ts, rows = s["ts"], s["rows"]
        closes = [rows[t]["close"] for t in ts]
        vol = [rows[t]["vol"] for t in ts]
        ls = [rows[t]["ls"] for t in ts]
        lb = [rows[t]["lb"] for t in ts]
        hold = [rows[t]["holdout"] for t in ts]

        # baseline over every holdout coin-hour with a forward return
        for i, t in enumerate(ts):
            if not hold[i]:
                continue
            for h in HORIZONS:
                if i + h < len(ts) and hold[i + h] and closes[i] > 0 and closes[i + h] > 0:
                    base_sum[h] += closes[i + h] / closes[i] - 1
                    base_n[h] += 1

        for i, t in enumerate(ts):
            if not hold[i] or t < HOLDOUT_START or i < WINDOW:
                continue
            for side, liq in (("long", ls), ("short", lb)):
                hist = [liq[j] / vol[j] for j in range(i - WINDOW, i) if vol[j] > 0]
                if len(hist) < WINDOW // 2 or vol[i] <= 0 or liq[i] <= 0:
                    continue
                if liq[i] / vol[i] < quantile(hist, SPIKE_Q):
                    continue
                rec = {"coin": coin, "ts": t, "side": side}
                for h in HORIZONS:
                    ok = i + h < len(ts) and closes[i] > 0 and closes[i + h] > 0
                    rec[f"r{h}"] = (closes[i + h] / closes[i] - 1) if ok else None
                events.append(rec)

    baseline = {h: base_sum[h] / base_n[h] for h in HORIZONS if base_n[h]}
    print(f"coins {len(COINS)} · events {len(events)} · "
          f"baseline 24h {1e4 * baseline[24]:+.1f} bps")

    def excess(e, h):
        r = e.get(f"r{h}")
        if r is None:
            return None
        x = r - baseline[h]
        return x if e["side"] == "long" else -x

    ev = [e for e in events if excess(e, 24) is not None]
    m, t, n = day_stats([excess(e, 24) for e in ev], [e["ts"] // 86400 for e in ev])
    print(f"1) revert: mean R {1e4 * m:+.1f} bps, t {t:.2f}, {n} days")

    halves = {}
    for name, lo, hi in (("h1", HOLDOUT_START, HALF_SPLIT), ("h2", HALF_SPLIT, 10 ** 12)):
        sel = [e for e in ev if lo <= e["ts"] < hi]
        halves[name] = day_stats([excess(e, 24) for e in sel], [e["ts"] // 86400 for e in sel])
        print(f"   {name}: mean R {1e4 * halves[name][0]:+.1f} bps, t {halves[name][1]:.2f}, "
              f"{halves[name][2]} days")

    sides = {}
    for side in ("long", "short"):
        sel = [e for e in ev if e["side"] == side]
        days_side = [e["ts"] // 86400 for e in sel]
        # criterion 2 is about the RAW excess sign: longs up, shorts down. R flips the short sign.
        raw = day_stats([e["r24"] - baseline[24] for e in sel], days_side)
        sides[side] = raw
        print(f"   {side}: raw excess 24h {1e4 * raw[0]:+.1f} bps, t {raw[1]:.2f}, {raw[2]} days")

    long_ev = [e for e in ev if e["side"] == "long" and e.get("r24") is not None]
    lm, lt, ln = day_stats([e["r24"] for e in long_ev], [e["ts"] // 86400 for e in long_ev])
    print(f"4) pays: raw 24h after long spikes {1e4 * lm:+.1f} bps, t {lt:.2f}, {ln} days")

    # information only, fixed in the pre-registration: trade-weighted mean with day-clustered SE
    from collections import defaultdict as _dd
    num, den = _dd(float), _dd(int)
    vals = []
    for e in ev:
        x = excess(e, 24)
        vals.append(x)
        num[e["ts"] // 86400] += x
        den[e["ts"] // 86400] += 1
    k = len(num)
    tw = sum(num.values()) / sum(den.values())
    se = math.sqrt(k / (k - 1) * sum((num[d] - tw * den[d]) ** 2 for d in num)) / sum(den.values())
    print(f"   (information) trade-weighted R {1e4 * tw:+.1f} bps, day-clustered t {tw / se:.2f}, "
          f"{k} days, {len(vals)} events")

    c1 = bool(m > 0 and t >= 3)
    c2 = bool(sides["long"][0] > 0 and sides["short"][0] < 0)
    c3 = bool(halves["h1"][0] > 0 and halves["h2"][0] > 0)
    c4 = bool(lm > 0.0018 and lt > 2)
    verdict = "PASS" if all((c1, c2, c3, c4)) else "FAIL"
    print("\ncriteria:", {"1": c1, "2": c2, "3": c3, "4": c4}, "→", verdict)

    (ROOT / "research" / "liqspike_run.json").write_text(json.dumps({
        "events": len(events), "baseline_bps": {str(k): 1e4 * v for k, v in baseline.items()},
        "c1": {"mean_bps": 1e4 * m, "t": t, "days": n,
               "trade_weighted_bps": float(1e4 * tw), "trade_weighted_t": float(tw / se)},
        "halves": {k: {"mean_bps": 1e4 * v[0], "t": v[1], "days": v[2]} for k, v in halves.items()},
        "sides_R": {k: {"mean_bps": 1e4 * v[0], "t": v[1], "days": v[2]} for k, v in sides.items()},
        "sides": {k: {"raw_excess_bps": 1e4 * v[0], "t": v[1], "days": v[2]} for k, v in sides.items()},
        "c4": {"mean_bps": 1e4 * lm, "t": lt, "days": ln},
        "criteria": [c1, c2, c3, c4], "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
