# Pre-registration — regime-conditioned residual pairs (RP2)

Written **before any residual-pair statistic is computed**. The unconditional pair scan and the PCA
factor model are already known; the residual construction, the regime gate and the holdout have not
been examined.

## 1. Why this follows from phase 1

The unconditional scan found **0 of 231 pairs** surviving a 10% FDR, and the factor model showed that
**PC1 explains 66% of variance**. A naive log-price pair therefore largely measures whether two coins
share the market exposure — and the market is the one thing every pair shares. Two conclusions follow:

- pair selection should be done on **market-residual prices**, not raw prices;
- participation should be **conditioned on regime**, because relative-value spreads behave differently
  when the market is trending than when it is ranging (the XS and carry results were both regime
  statistics).

## 2. Mechanism — who is on the other side

After the market factor is removed, what remains is coin-specific flow: rotations between large caps
and mid caps, basket rebalancing, and supply/demand from venue-level events. The counterparty is the
**rotating allocator** — the participant who moves exposure between names because of a narrative, an
index change or a yield differential, and who does so without regard to a stable ratio. Their demand is
temporary, so the residual spread they create reverts. If it does not revert, the pair is not a pair and
the residual is a permanent repricing.

The narrow prediction: **a residual spread that is stationary in the design window and currently
dislocated tends to close, and the effect is not available when the market is trending strongly.**

## 3. Data and windows — fixed now

- **Source**: `bars_daily` in the substrate, 2020-01 → 2026-03, 42 symbols (5m archive aggregated).
- **Design**: 2020-01-01 → 2022-12-31 (discovery only).
- **Validation**: 2023-01-01 → 2023-12-31 (evidence; the gate runs here).
- **Holdout**: **2025-07-01 → 2026-03-31**, read **once**, only after the pre-registration and the
  frozen pair list are committed. Not previously used for any pairs or factor work (disclosed: the
  retired SMA backtest read daily closes through 2026, so the prices exist locally).

## 4. Construction — fixed

- **Universe**: top 30 by median daily quote volume in the design window.
- **Market proxy**: equal-weight log price index `M` over that universe.
- **Residualisation**: rolling 180-day OLS of `log p_i` on `log M`; residual `e_i = log p_i − α_i − β_i log M`,
  with `α, β` re-estimated monthly, using only data up to that date.
- **Pair test**: Engle–Granger on `e_a` vs `e_b` over the trailing 180 days, monthly refits; ADF p-value
  and OU half-life of the residual spread.
- **Discovery**: BH FDR at 10% across every pair tested on design; half-life **5–30 days**; the pair
  must be significant in ≥ 60% of the rolling windows.
- **Freeze**: surviving pairs and their last design `(α, β, α_a, β_a)` go to `pair_regime_frozen.csv`
  before validation.

## 5. Regime gate — fixed

- Regime at date `t`: **ranging** if `|M_t / M_{t−20} − 1|` is at or below the design-window median of
  that absolute 20-day return; otherwise **trending**.
- **Trades are opened only in ranging regimes.** An open trade is allowed to complete after the regime
  flips; no new entry.
- This gate is part of the registered rule, not a post-hoc filter: it is evaluated before any
  validation statistic.

## 6. Signal, costs and sizing — fixed

- Spread `s_t = e_a − (α + β e_b)` using the frozen design coefficients.
- z-score over 60 days; **enter |z| > 2**, **exit |z| < 0.5** or after **30 days**.
- Dollar-neutral, equal notional per leg, **$100k per side per pair** (capacity is measured and reported
  separately, not used for selection).
- **Costs: 5 bps per side on both legs at entry and exit, plus funding** over the hold.
- One open trade per pair at a time; pairs are independent; the book is equal-weighted across open pairs.

## 7. Statistics — fixed

- Stationary block bootstrap on **daily portfolio returns** (mean block 10 days, 10,000 resamples),
  95% percentile CI.
- Newey–West t with 10 lags.
- Multiplicity across the pair family: BH FDR on discovery already applied; at the gate, **deflated
  Sharpe** and **SPA p-value** over every pair tested.

## 8. The gate — fixed

The candidate passes only if, on **validation 2023**, all of:

1. mean net daily return > 0 with the bootstrap CI's lower bound > 0;
2. NW t ≥ 2;
3. positive in both halves of 2023;
4. SPA / deflated-Sharpe p < 0.10 across the family;
5. the disproof suite (placebo pairs, shifted signals, regime split, 2× cost stress) does not break it.

If it passes, the holdout is read once and judged by the same criteria. A pass on validation and a
failure on holdout is published as a failure.

## 9. Outcomes — fixed

- **Validation pass + holdout pass**: authorize a paper plumbing window; nothing live.
- **Validation pass + holdout fail**: regime or multiplicity artefact; retire the candidate.
- **Validation fail**: retire the family; report the diagnostic (residualisation may itself be the
  problem).

## 10. Disproof suite — pre-specified

1. **Random pairs** matched on correlation and volatility — must show no edge.
2. **Signal shift**: z-score delayed by 5 days — the edge must vanish.
3. **Regime placebo**: trades taken only when trending — must underperform ranging trades.
4. **Cost stress**: 2× spread and fee — report the survival fraction.
5. **Parameter neighbourhood**: z entry 1.5 and 2.5, exit 0.25 and 0.75 — sign must hold.

## 11. What this registration refuses

- Changing the residualisation, the regime definition, the z-thresholds, or the window after seeing
  validation or holdout.
- Re-using the holdout for a second hypothesis.
- Any LLM-generated confidence score as an input: the rule must be computable from the substrate alone.
