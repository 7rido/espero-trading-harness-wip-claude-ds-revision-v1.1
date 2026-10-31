"""Sequential monitoring plan for E1: O'Brien-Fleming boundaries and power at each look.

    python research/e1_monitor.py

E1 is the one forward test; looking at it monthly without a spending rule would itself be a
multiple-testing problem. Six monthly looks, two-sided 5%, Lan-DeMets OBF spending.
"""
from __future__ import annotations

import json
import math
import pathlib
from statistics import NormalDist

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATUS = ROOT / "research" / "e1_status.json"
OUT = ROOT / "research" / "e1_monitor.json"
K = 6                      # planned looks: Nov 30, Dec 31, Jan 31, Feb 28, Mar 31, Apr 30
ALPHA = 0.05
EFFECT_BPS = 32.0          # in-sample executable 4h bounce, gross
SD_BPS = 339.0             # 10-90 band of the long-liq 99th percentile 4h cell
EVENTS_PER_DAY = 3.7       # 11 events on day 1, ~1/3 forced
ND = NormalDist()


def boundaries() -> list[float]:
    z = []
    for k in range(1, K + 1):
        t = k / K
        spent = 2 * (1 - ND.cdf(ND.inv_cdf(1 - ALPHA / 2) / math.sqrt(t)))
        z.append(ND.inv_cdf(1 - spent / 2))
    return z


def power(bounds: list[float], reps: int = 20_000, seed: int = 7) -> list[float]:
    """P(cross at or before look k) if the true effect is EFFECT_BPS with SD_BPS noise."""
    rng = np.random.default_rng(seed)
    hit = [0] * K
    for _ in range(reps):
        n = 0
        total = 0.0
        done = False
        for k in range(K):
            add = rng.poisson(EVENTS_PER_DAY * 30)
            n += add
            total += float(rng.normal(EFFECT_BPS, SD_BPS, size=add).sum())
            if n < 10:
                continue
            z = (total / n) / (SD_BPS / math.sqrt(n))
            if not done and abs(z) >= bounds[k]:
                done = True
            hit[k] += done
    return [h / reps for h in hit]


def main() -> int:
    b = boundaries()
    p = power(b)
    st = json.loads(STATUS.read_text()) if STATUS.exists() else {}
    print(f"E1 sequential plan: {K} looks, two-sided {ALPHA:.0%}, O'Brien-Fleming\n")
    print(f"{'look':>4} {'z boundary':>10} {'P(stop by here)':>16} {'expected trades':>16}")
    for k in range(K):
        print(f"{k+1:>4} {b[k]:>10.2f} {p[k]:>16.1%} {(k+1)*30*EVENTS_PER_DAY:>16.0f}")
    print(f"\ncurrent: {st.get('events', 0)} events, {st.get('forced_down_breaks', 0)} forced trades, "
          f"scored {st.get('trades_scored', 'n/a')}")
    OUT.write_text(json.dumps({"looks": K, "boundaries": [round(x, 3) for x in b],
                               "power": [round(x, 3) for x in p]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
