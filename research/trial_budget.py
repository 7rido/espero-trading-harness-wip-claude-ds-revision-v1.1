"""The project's trial inventory: every registered test, its p-value, and the multiple-testing bill."""
from __future__ import annotations
import json, math, pathlib
from statistics import NormalDist

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "trial_budget.json"

TESTS = [
    {"id": "R1", "name": "#21 liquidation spikes (replication)", "kind": "replication",
     "t": 0.85, "n": 119, "verdict": "FAIL"},
    {"id": "R2", "name": "#26 forced bounce (in-sample replication)", "kind": "replication",
     "t": 7.11, "n": 427, "verdict": "replicated"},
    {"id": "R3", "name": "carry deep (#12 rev2)", "kind": "new", "t": 3.13, "n": 176,
     "verdict": "FAIL (holdout flat)"},
    {"id": "R4", "name": "XS momentum deep (#2/#7 rev2)", "kind": "new", "t": 2.23, "n": 106,
     "verdict": "FAIL (holdout)"},
    {"id": "E1", "name": "executable liquidation bounce", "kind": "new", "t": None, "n": None,
     "verdict": "pending 2027-04-30"},
]


def p_two_sided(t: float) -> float:
    return float(2 * (1 - NormalDist().cdf(abs(t))))


def deflated_sharpe(sr_annual: float, n_trials: int, T: int) -> float:
    from math import sqrt
    e = 0.5772156649
    sr = sr_annual / sqrt(52)
    z1 = NormalDist().inv_cdf(1 - 1 / n_trials)
    z2 = NormalDist().inv_cdf(1 - 1 / (n_trials * e))
    sr0 = sqrt(1 / T) * ((1 - e) * z1 + e * z2)
    return float(NormalDist().cdf((sr - sr0) * sqrt(T - 1) / sqrt(max(1e-9, 1 - sr * sr / 4))))


def main() -> int:
    rows = []
    for t in TESTS:
        row = dict(t)
        row["p_value"] = p_two_sided(t["t"]) if t["t"] is not None else None
        row["sharpe_annual"] = (t["t"] / math.sqrt(t["n"])) * math.sqrt(52) if t["t"] and t["n"] else None
        rows.append(row)
    completed = [r for r in rows if r["t"] is not None]
    best = max(completed, key=lambda r: r["t"])
    dsr = deflated_sharpe(best["sharpe_annual"], len(completed), best["n"])
    out = {"tests": rows, "completed": len(completed), "pending": len(rows) - len(completed),
           "best": best["id"], "deflated_sharpe_p_of_best": dsr,
           "spend_rate": {"registered_tests": len(rows), "failed_on_holdout": 2,
                          "replications": 2, "pending": 1}}
    OUT.write_text(json.dumps(out, indent=1))
    for r in rows:
        p = "—" if r["p_value"] is None else f"{r['p_value']:.4f}"
        print(f"{r['id']:3s} {r['name'][:42]:42s} t {str(r['t']):>5s}  p {p:>7s}  {r['verdict']}")
    print(f"deflated Sharpe for the best ({best['id']}) across {len(completed)} completed trials: {dsr:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
