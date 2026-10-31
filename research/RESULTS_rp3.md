# Result — cost-aware residual pairs (RP3)

**Verdict: the FDR survivors lose money on their own design window after costs. Zero pairs selected;
validation never runs; the holdout remains unread.**

Seal: `9942469` (`research/PREREGISTRATION_RESIDUAL_PAIRS_COST.md`), written before any design backtest.

## The three candidates, and what they earn

RP2's discovery: 435 residual pairs, BH FDR 10% → **3 pass**. RP3 replaced the fixed half-life floor
with a direct measurement on the design window (2020–2022), same rule, same costs:

| pair | half-life | design net (bps/day) | t | round trips |
|---|---|---|---|---|
| FIL \| THETA | 3.2 d | **−8.2** | −0.76 | 229 |
| FIL \| EOS | 4.2 d | **−17.0** | −1.58 | 174 |
| FIL \| XTZ | 4.6 d | **−9.3** | −1.03 | 191 |

All three are statistically cointegrated and all three **lose** after 5 bps a side. The residual reverts,
but by less than the cost of being in the trade — and at 174–229 round trips, the cost is the strategy.

## What this establishes

1. **Residualisation works as a discovery tool** — 3/435 significant against 0/231 unconditional.
2. **Significance is not tradability**, and now we know it by the only measurement that matters: the
   design-window P&L of the exact rule.
3. **The gate held a third time.** No selection → no validation → no policy → no authorisation, and the
   holdout is still pristine for a future registration.

## Where the residual-pairs family stands

Two registrations, both negative, both informative:

- RP2: the pairs exist statistically but revert too fast for the fixed floor.
- RP3: the pairs revert too slowly to beat costs — the floor was not the binding constraint after all;
  the edge was never there.

The next move on this family would be **event-conditioned** trading: only enter a residual dislocation
after a mechanical flow shock (index rebalance, funding extreme), where the reversion can plausibly be
larger than the 8–17 bps/day the unconditional rule loses. That is a different hypothesis and requires
its own seal and its own slice of holdout.

## Changes to the record

- `pair_cost_frozen.csv` is empty by construction.
- `residual_pairs_select_rows.csv` holds the three design backtests.
- Ledger `R8` retired.
