# Forecast audit — coverage and walk-forward skill

Status: **measurement**, not a strategy result. No order path, ledger row or paper book is touched.

## Why this exists

The live forecast currently has four `CONTEXT ONLY` rows and six `UNMAPPED` rows. Before adding
another model, this audit asks two questions:

1. Can the substrate even support a forecast for the current universe?
2. Does the existing 16-state conditional distribution beat the unconditional baseline out of sample?

## Coverage

`python research/forecast_audit.py --coverage` writes `research/forecast_audit.json`.

| table | rows | symbols | span |
|---|---:|---:|---|
| `bars_daily` | 82,774 | 42 | 2020-01-01 → 2026-03-31 |
| `rv` | 82,774 | 42 | 2020-01-01 → 2026-03-31 |
| `funding` | 108,374 | 56 | 2023-01-01 → 2025-06-30 |
| `funding_multi` | 38,198 | 30 | 2025-07-01 → 2026-10-31 |
| `metrics` | 105,120 | 1 | 2025-10-31 → 2026-10-30 |
| `tardis_derivative` | 4,415,916 | 2 | 2025-01-01 → 2026-10-01 |
| `tardis_liquidations` | 44,353 | 2 | 2025-01-01 → 2026-10-01 |

For the ten live forecast coins:

- **BTC, ETH, SOL, XRP** — covered; forecast label is blocked by the evidence gate.
- **ZEC, NEAR** — bars/RV exist, but no current funding → `n/a`.
- **HYPE, PUMP, ENA, UNI** — no bars/RV/funding history in the substrate.

So the six `UNMAPPED` rows are mostly a **data coverage** problem, not a model failure.

## Walk-forward evaluation

`python research/forecast_audit.py --eval` writes `research/forecast_eval.json`.

- Target: 20-day market-relative return (`x20`)
- Test start: 2023-01-01
- Expanding history, purged with a **20-day embargo** so a training outcome cannot overlap the test outcome
- Minimum 100 historical outcomes per state; otherwise fall back to the unconditional sample
- Scores: empirical CRPS, Brier for `P(return > 0)`, and PIT

Result (47,842 test rows):

| model | CRPS | Brier | PIT mean |
|---|---:|---:|---:|
| 16-state conditional | 0.08051 | 0.24024 | 0.518 |
| unconditional | **0.08030** | **0.23951** | 0.518 |

The conditional model does **not** beat the unconditional baseline. It is slightly worse on both
proper scores, and both PIT distributions are close to uniform but not perfectly calibrated.

Interpretation: the current 16 hard state cells add no measurable forecast skill on this sample. The
`CONTEXT ONLY` labels are therefore justified. Adding a more complex model before extending coverage
and features would only add overfitting risk.

## What to do next

1. **Extend coverage** — current bars/RV/funding for the active universe; unify symbol formats; add
   `funding_multi`, `metrics`, `premium`, and `tardis_derivative` where they have enough history.
2. **Re-run this audit** after coverage; the conditional sample and PIT bins will change.
3. **Then** try one model at a time (HAR-RV extension, shrinkage, quantile regression, HMM state
   probabilities) and keep only models that beat the unconditional baseline on CRPS/Brier without
   destroying calibration.
4. **Do not** use E1 holds or the sealed forward test as a forecast target.

The audit is deliberately read-only. It does not write to `paper.db`, `strategy_ledger.csv`, or
`research/forecast.json`.
