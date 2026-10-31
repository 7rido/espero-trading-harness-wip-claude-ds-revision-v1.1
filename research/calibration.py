"""Detector calibration: does the pipeline recover a known alpha, and stay silent on a null?

    python research/calibration.py
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "calibration.json"
SYMBOLS, DAYS, LOOKBACK, HOLD = 20, 300, 30, 7
SIMS = 200


def one_market(alpha_weekly: float, seed: int) -> float:
    """Returns where next week's cross-section is proportional to the past month's return."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, 0.03, size=(DAYS, SYMBOLS))          # daily noise, 3% vol
    px = np.cumprod(1 + rets, axis=0) * 100
    spreads = []
    for d in range(LOOKBACK, DAYS - HOLD, HOLD):
        sig = px[d] / px[d - LOOKBACK] - 1
        fwd = px[d + HOLD] / px[d] - 1
        k = max(1, SYMBOLS // 5)
        order = np.argsort(sig)
        longs, shorts = order[-k:], order[:k]
        # the known alpha is added to the forward return of the high-signal names
        fwd = fwd + alpha_weekly * (sig - sig.mean()) / (sig.std() + 1e-9) * 0.5
        spreads.append(fwd[longs].mean() - fwd[shorts].mean())
    return float(np.mean(spreads)) * 52


def main() -> int:
    out = {"sims": SIMS, "power": {}, "false_positive": None}
    for alpha in (0.0, 0.001, 0.002, 0.004):
        est = np.array([one_market(alpha, seed=s) for s in range(SIMS)])
        ci_lo = np.percentile(est, 2.5)
        ci_hi = np.percentile(est, 97.5)
        out["power"][str(alpha)] = {
            "true_ann_pct": 100 * alpha, "mean_est_pct": 100 * float(est.mean()),
            "bias_pct": 100 * float(est.mean() - alpha),
            "ci95_pct": [100 * float(ci_lo), 100 * float(ci_hi)],
            "coverage": float(np.mean((est >= alpha * 0.5) & (est <= alpha * 2.0))) if alpha else None,
            "share_positive": float(np.mean(est > 0)),
        }
        if alpha == 0.0:
            out["false_positive"] = float(np.mean(est > 1.96 * est.std(ddof=1) / np.sqrt(SIMS) + 0))
    (ROOT / "research" / "calibration.json").write_text(json.dumps(out, indent=1))
    for a, r in out["power"].items():
        print(f"alpha {r['true_ann_pct']:+.1f}%/yr -> estimate {r['mean_est_pct']:+.1f}% "
              f"(CI {r['ci95_pct'][0]:+.1f}..{r['ci95_pct'][1]:+.1f}), positive share {r['share_positive']:.2f}")
    print(f"null: share of sims with a positive estimate {out['power']['0.0']['share_positive']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
