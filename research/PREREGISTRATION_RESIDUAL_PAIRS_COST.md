# Pre-registration — cost-aware residual pairs (RP3)

Written **before any design backtest of a residual pair is computed**. RP2 is known: residualisation
lifted discovery from 0/231 to 3/435 FDR-passing pairs, and every survivor reverted in 2.8–4.4 days,
below the fixed 5-day floor. The holdout 2025-07 → 2026-03 has not been read.

## 1. Why this registration exists

RP2's half-life floor was a crude proxy for the real question: **does the reversion, at the cost the
pair actually pays, leave money on the design data?** A fixed 5-day floor rejects a 3-day pair that may
earn 20 bps per round trip and accepts a 20-day pair that earns 4. The replacement is not a lower
floor; it is a direct measurement of the registered rule's design-window edge, with a multiplicity bill.

## 2. What changes from RP2

| | RP2 | RP3 |
|---|---|---|
| half-life filter | fixed 5–30 days | **2–30 days** (a plausibility bound, not the decision) |
| selection | statistics only | **design-window backtest of the exact rule: net > 0, t ≥ 2, ≥ 30 round trips** |
| multiplicity | BH FDR on discovery | BH FDR on discovery **and** SPA at the gate |
| everything else | residual construction, regime gate, costs, validation, holdout | unchanged |

## 3. Construction — fixed (unchanged from RP2)

- Universe: top 30 by design median quote volume; design 2020-01 → 2022-12.
- Market proxy: equal-weight log price index; residualisation `e_i = log p_i − α_i − β_i log M`,
  rolling 180 days, monthly refit.
- Pair test: Engle–Granger on `e_a` vs `e_b`, monthly; BH FDR 10% across all 435 pairs.
- Half-life 2–30 days; significant in ≥ 60% of windows.

## 4. Selection on design — fixed

For every FDR-passing pair, simulate the registered rule on the **design window** with the regime gate
active (ranging = |20-day market return| at or below the design median):

- enter |z| > 2 (z over 60 days), exit |z| < 0.5 or 30 days;
- 5 bps per side on both legs at entry and exit, plus funding;
- dollar-neutral, $100k per side.

A pair is **selected** only if its design backtest has net mean daily return > 0, **t ≥ 2**, and at
least **30 round trips**. Selected pairs and their design coefficients are frozen in
`pair_cost_frozen.csv` before validation.

## 5. Validation and gate — fixed

- Validation: **2023-01-01 → 2023-12-31**, same rule, same costs, same regime gate.
- The candidate passes only if: portfolio net mean daily > 0, stationary-bootstrap 95% CI lower bound >
  0, NW t ≥ 2, positive in both halves, SPA / deflated-Sharpe p < 0.10 across the selected family, and
  the disproof suite does not break it.

## 6. Holdout — sealed

**2025-07-01 → 2026-03-31**, read once, after the freeze. Same criteria. A validation pass followed by a
holdout fail is published as a failure.

## 7. Disproof suite — pre-specified

1. Random pairs matched on correlation and volatility — no edge.
2. z-score delayed by 5 days — edge vanishes.
3. Regime placebo: entries only when trending — underperforms.
4. Cost stress: 2× fees and spread — report survival fraction.
5. Parameter neighbourhood: entry 1.5/2.5, exit 0.25/0.75 — sign holds.

## 8. Outcomes — fixed

- **Validation pass, holdout pass**: paper plumbing window may be opened; no live path.
- **Either fails**: retire the family with the diagnostic; no re-tuning.
- Discovery that yields no FDR pair, or no pair surviving design selection, is reported as a negative
  result and the holdout stays unread.
