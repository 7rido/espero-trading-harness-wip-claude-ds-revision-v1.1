"""How much of our best result is selection? Family-wise thresholds over every trial we ran.

    python research/selection_cost.py

Given N trials, the expected maximum |t| under the null is simulated, and the best observed t is
compared against it, against Bonferroni, and against the probability that the family produces a
result at least this large by chance.
"""
from __future__ import annotations

import pathlib

import math

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRIALS = ROOT / "research" / "trials.csv"
OUT = ROOT / "research" / "selection_cost.json"
REGISTERED = 9          # R1..R9 in the ledger
FULL_FAMILY = 121       # 9 registered + 51 conditional-suite + 16 regime + 35 conditional-study + 10 variants


def norm_sf(x: float) -> float:
    """Two-sided tail: P(|Z| >= |x|), exact via erfc."""
    return float(math.erfc(abs(x) / math.sqrt(2.0)))


def expected_max(n: int, reps: int = 200_000, seed: int = 7) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    draws = np.abs(rng.standard_normal((reps, n)))
    maxima = draws.max(axis=1)
    return float(maxima.mean()), float(np.percentile(maxima, 95))


def main() -> int:
    df = pd.read_csv(TRIALS)
    df["p"] = df["t"].abs().map(norm_sf)          # already two-sided
    df = df.sort_values("p")
    best = df.iloc[0]
    rows = []
    for n in (REGISTERED, FULL_FAMILY):
        e_max, q95 = expected_max(n, 200_000)
        fw_p = 1 - (1 - best["p"]) ** n
        bonferroni = 0.05 / n
        rows.append({"n": n, "expected_max_abs_t": round(e_max, 2), "null_95pct": round(q95, 2),
                     "best_trial": best["trial"], "best_t": best["t"], "best_p": round(best["p"], 5),
                     "familywise_p": round(float(fw_p), 4), "bonferroni_p": bonferroni,
                     "survives": bool(best["p"] < bonferroni)})
    OUT.write_text(pd.DataFrame(rows).to_json(orient="records", indent=1))
    print(f"trials with reported t: {len(df)} · registered family: {REGISTERED} · full family: {FULL_FAMILY}\n")
    print(df[["trial", "t", "n_obs", "p"]].to_string(index=False))
    print()
    for r in rows:
        print(f"N={r['n']:>3}: E[max|t|]={r['expected_max_abs_t']:>4.2f} (null 95% {r['null_95pct']:>4.2f}) "
              f"· best {r['best_trial']} t={r['best_t']:>5.2f} p={r['best_p']:.5f} "
              f"· family-wise p={r['familywise_p']:.4f} · survives: {r['survives']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
