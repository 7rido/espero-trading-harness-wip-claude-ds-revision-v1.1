# Result — regime-conditioned residual pairs (RP2)

**Verdict: discovery succeeds, the trading filter kills it, validation is never reached.**
Residualising on the market factor produced **3 statistically significant pairs out of 435** (against
0 out of 231 for raw prices) — the diagnosis was right. But every survivor reverts with a half-life of
**2.8–4.4 days**, and the registration required **5–30 days**. Zero pairs froze; no validation trade
was taken; the holdout was not read.

Seal: `c1ec15b` (`research/PREREGISTRATION_RESIDUAL_PAIRS.md`).

## Discovery (design 2020–2022)

| pair | median ADF p | median half-life | significant windows |
|---|---|---|---|
| FIL \| THETA | 0.00021 | 3.2 d | 92% |
| FIL \| ATOM | 0.00113 | 4.2 d | 83% |
| FIL \| AAVE | 0.00119 | 4.4 d | 75% |
| OP \| XTZ | 0.00147 | 3.3 d | 100% |
| FIL \| TRX | 0.00157 | 4.3 d | 83% |

435 pairs tested, BH FDR at 10%; 3 pass. The raw-price scan found none. **Removing the 66% market
factor is what turns a statistical signal on** — which is exactly what phase 1 predicted.

## Why it still fails

The half-life filter was registered **before** the scan for a reason: a spread that closes in three days
must clear 10 bps of round-trip cost per trade, and the faster the reversion the more of the edge is
eaten by the entry. The three FDR survivors are all in the 2.8–4.4 day band — too fast for the
registered cost structure, by the rule's own arithmetic.

That leaves zero frozen pairs, so:

- `pair_regime_frozen.csv` is empty by construction;
- validation is not executed (there is nothing to validate);
- **the holdout 2025-07 → 2026-03 remains unread**, intact for a future registration.

## What this establishes

1. **The residualisation hypothesis is supported**: unconditional pairs are dominated by the market;
   residual pairs are not. Discovery went 0 → 3.
2. **Statistical significance is not tradability**: the surviving pairs are fast-reverting; the
   registered half-life floor is what separates the two.
3. The gate held: no candidate, no validation, no policy, no authorisation.

## What would change it (a new registration, not a re-tune)

- A **cost-aware half-life criterion** — require the expected reversion over the half-life to exceed
  the measured round trip by a pre-registered margin, rather than a fixed 5-day floor. That is a
  different hypothesis, and it needs its own seal.
- Or an **event-conditioned** variant: trade the residual only after a mechanical flow shock (index
  rebalancing, funding extreme), where the reversion is expected to be slower.

The holdout is still available for whichever is registered next.
