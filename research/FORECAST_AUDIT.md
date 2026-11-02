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

### Research overlay

`python research/forecast_coverage.py` fetches public Coinbase daily candles into
`research/forecast_overlay.duckdb` (gitignored) and computes a two-dimensional trend/vol state for
the live universe. It does not change the substrate. After the fetch:

| coin | bars | first | last | 2D state |
|---|---:|---|---|---|
| BTC | 2,497 | 2020-01-01 | 2026-11-01 | up/low |
| ETH | 2,497 | 2020-01-01 | 2026-11-01 | down/low |
| SOL | 1,964 | 2021-06-17 | 2026-11-01 | down/low |
| XRP | 1,593 | 2020-01-01 | 2026-11-01 | down/low |
| ZEC | 2,155 | 2020-12-08 | 2026-11-01 | up/low |
| NEAR | 1,523 | 2022-09-01 | 2026-11-01 | up/high |
| HYPE | 270 | 2026-02-05 | 2026-11-01 | up/low |
| PUMP | 475 | 2025-07-15 | 2026-11-01 | up/low |
| ENA | 515 | 2025-06-05 | 2026-11-01 | up/high |
| UNI | 2,237 | 2020-09-17 | 2026-11-01 | up/high |

All ten now have price history in the overlay. The limiting field is still **current funding**:
ZEC, NEAR, HYPE, PUMP, ENA and UNI have no `funding_multi` history, so the 16-state model still
labels them `UNMAPPED`. The overlay supports a future 2D fallback; it is not wired into the live
forecast.

### Funding coverage (Hyperliquid proxy)

Binance and Bybit public endpoints are geo-blocked from this machine. Hyperliquid's public
`fundingHistory` endpoint answers, so `python research/forecast_funding.py` paginates it into a
research-only overlay.

| coin | rows | first | 7d funding | percentile | state |
|---|---:|---|---:|---:|---|
| ZEC | 9,493 | 2025-10-02 | +11.3%/yr | 0.76 | high |
| NEAR | 16,083 | 2025-01-01 | +9.6%/yr | 0.42 | low |
| ENA | 16,083 | 2025-01-01 | +11.6%/yr | 0.87 | high |
| UNI | 16,083 | 2025-01-01 | +16.9%/yr | 0.93 | high |
| HYPE | 16,083 | 2025-01-01 | +22.5%/yr | 0.99 | high |
| PUMP | 11,519 | 2025-07-10 | +9.4%/yr | 0.48 | low |

Combined with the 2D states, all six now map to an existing 16-state cell:

| coin | 3D state | label |
|---|---|---|
| ZEC | up/low/high | CONTEXT ONLY |
| NEAR | up/high/low | CONTEXT ONLY |
| ENA | up/high/high | CONTEXT ONLY |
| UNI | up/high/high | CONTEXT ONLY |
| HYPE | up/low/high | CONTEXT ONLY |
| PUMP | up/low/low | CONTEXT ONLY |

This removes the `UNMAPPED` reason, but not the evidence gate. The live forecast is unchanged: it
still reads the old funding field, and the historical `regime_signs` cells were built with the
Binance funding table. Using Hyperliquid percentiles inside those cells is a venue proxy, not a
like-for-like replacement. The overlay is coverage and a candidate for a separate HL-specific model,
not a promotion of the current forecast.

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
| 2D trend/vol conditional | 0.08011 | 0.23968 | 0.519 |
| unconditional | **0.08030** | **0.23951** | 0.518 |

The 16-state model does **not** beat the unconditional baseline. The 2D trend/vol fallback is a
mixed result: CRPS improves by 0.00019, but Brier worsens by 0.00017. That is not a robust win, and
PIT is still close to uniform but not perfect.

Interpretation: neither hard-cell model has demonstrated forecast skill on this sample. The
`CONTEXT ONLY` labels are therefore justified. Adding a more complex model before extending coverage
and features would only add overfitting risk.

## What to do next

1. **Extend coverage** — current bars/RV/funding for the active universe; unify symbol formats; add
   `funding_multi`, `metrics`, `premium`, and `tardis_derivative` where they have enough history.
2. **Re-run this audit** after coverage; the conditional sample and PIT bins will change.
3. **Test a 2D fallback** against the 16-state model and the unconditional baseline. It reduces
   `UNMAPPED` rows, but the first result is a tie; do not promote it without a clearer CRPS/Brier
   improvement.
4. **Then** try one model at a time (HAR-RV extension, shrinkage, quantile regression, HMM state
   probabilities) and keep only models that beat the unconditional baseline on CRPS/Brier without
   destroying calibration.
5. **Do not** use E1 holds or the sealed forward test as a forecast target.

The audit is deliberately read-only. It does not write to `paper.db`, `strategy_ledger.csv`, or
`research/forecast.json`.
