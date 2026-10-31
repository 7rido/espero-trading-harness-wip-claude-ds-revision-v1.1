# Result — cross-sectional momentum, deep (#2/#7, revision 2)

**Verdict: FAIL on the holdout.** The design window (2021–2022) earned **+101.4%/yr** net with a
bootstrap CI of +15.8 … +194.8 and NW t 2.23; the sealed holdout (2023) earned **+27.8%/yr** with a
CI of **−36.4 … +92.5** and t 0.75. The registered P1 required the CI's lower bound above zero. It is
not. The design number did not replicate.

Registration: `research/PREREGISTRATION_XS_MOMENTUM.md` (seal **95005ac**); universe frozen in
`research/xs_universe.csv` (seal **53ffbfc**, 47 base assets). Code: `research/xs_momentum.py`;
numbers: `research/xs_momentum.json`.

## Mechanism, as registered

The counterparty is the **mechanical buyer**: index and equal-weight allocators who must buy what has
risen to restore weights, risk-parity funds whose exposure rises as volatility falls, and the
attrition of delisting liquidity. The prediction was narrow: the 30-day cross-section predicts the
next week's cross-section, in a weekly-rebalanced, dollar-neutral quintile book that survives fees and
funding.

## Results

| | design 2021–2022 | holdout 2023 |
|---|---|---|
| weeks | 106 | 53 |
| **annualised net** | **+101.4%** | **+27.8%** |
| 95% block-bootstrap CI | +15.8 … +194.8 | **−36.4 … +92.5** |
| NW t (8 lags) | 2.23 | **0.75** |
| Sharpe (annualised) | 1.24 | 0.85 |
| variant: 7-day lookback | +57.5% | −15.1% |
| variant: 14-day hold | +94.2% | +72.4% |
| placebo: sign-flipped book | −108.9%/yr | −34.8%/yr |
| placebo: random selection | +19.8%/yr | −14.8%/yr |
| signal autocorrelation | −0.20 | −0.02 |

**P1:** fails on the holdout — the CI includes zero and the t is 0.75.
**P3 (placebo):** passes in both windows — the sign-flipped book loses about as much as the real book
gains, and random selection is indistinguishable from zero after costs. The pipeline discriminates.
**P2 (liquidity halves):** **not computed**. The registered capacity half (bookDepth) was not
implemented; this is a gap, not a pass.

## What the two windows together say

The design number was a 2021–2022 artefact: that window is the period when the mechanical flows the
mechanism names were largest — index products and vol-target funds were growing, and momentum was the
crowd's trade. In 2023 the same rule kept a positive sign but lost significance, and one of the three
variants (7-day lookback) turned negative.

The honest reading is not "momentum doesn't exist". It is that **the effect is regime-sized**: big when
mechanical flow is big, statistically indistinguishable from zero otherwise — and the registered
criterion forbids claiming the good regime while ignoring the bad one.

## Survivorship, handled explicitly

The universe was selected on 2021–2022 volume from **1,051 symbols ever listed**, including names that
stopped existing. **LUNAUSDT** is in the frozen universe: it traded through the design window, exited
at its last print, and contributes nothing to 2023 because it no longer exists. That is the
survivorship test passing by construction — not by exclusion.

## Reconciliation

- **Price identity**: the closes are the published `klines` closes — the same digits, read from the
  archive, not a re-aggregation.
- **Funding identity**: the daily funding charged in the P&L is the sum of the published
  `fundingRate` files for that symbol and day.
- **Not done**: the `aggTrades` print check and the independent DuckDB re-implementation. Both were
  registered and are listed here as gaps.

## Disclosures

- **Capacity (P2) not computed** — registered, not implemented; no number is claimed.
- The holdout has fewer liquid symbols than the design window (2023 is thinner than 2021), which the
  frozen universe rule did not anticipate.
- Random-selection placebo is one seed in each window; its sign differs between them, consistent with
  noise around zero.

## What would be tested next

Not this rule again. A regime-aware version — e.g., size the book by the mechanical-flow proxy the
mechanism names, pre-registering that proxy — is a *new* hypothesis with its own registration. Re-tuning
the 2023 threshold would repeat exactly the error the audit found in the original's carry test.
