# Inheritance — what each finding stands on

**Rule**: every result names the original finding it extends or contradicts, or states that it has
no ancestor. Negative evidence is inherited as a *reason not to repeat*, not as a quantity to add.

## The 46 originals and their descendants

| id | original hypothesis | original verdict | our descendant(s) | relationship |
|---|---|---|---|---|
| 1 | funding extremes | FAIL | — | negative evidence, no descendant |
| 2 | XS momentum top-1 | FAIL | R4 | extended, survivorship-free universe |
| 3 | Polymarket LP | FAIL | — | negative evidence, no descendant |
| 4 | cross-asset TSMOM | UNRESOLVED | R9 | descendant (regime conditioning) |
| 5 | PEAD | FAIL | — | negative evidence, no descendant |
| 6 | crypto-policy odds | FAIL | — | negative evidence, no descendant |
| 7 | XS20 top-5 | EXPLORATORY | R4 | extended, survivorship-free universe |
| 8 | multi-factor XS | CONSTRUCTION | R6, R7, R8 | descendant of the multi-factor test; descendant (residual construction); descendant (cost-aware selection) |
| 9 | BTC lead-lag | FAIL | — | negative evidence, no descendant |
| 9b | lead-lag beta, hourly | FAIL | — | negative evidence, no descendant |
| 10 | degen 5m | FAIL | — | negative evidence, no descendant |
| 11 | carry, taker | FAIL | — | negative evidence, no descendant |
| 12 | carry, maker | VENUE-DEPENDENT | R3 | extended, repriced at real fees |
| 13 | degen 1h | FAIL | — | negative evidence, no descendant |
| 14 | carry on Kraken | FAIL | R3 | extended, repriced at real fees |
| 15 | multi-asset trend | FAIL | R9 | descendant (regime conditioning) |
| 16 | peer baskets | FAIL | R4 | extended, survivorship-free universe |
| 17 | ETH leads ecosystem | FAIL | R4 | extended, survivorship-free universe |
| 18 | liquidation sort | FAIL | R9, R10 | descendant (regime conditioning); descendant (descriptive mechanics) |
| 19 | settlement moves prices | REAL-NOT-TRADABLE | R5 | descendant of the reversion family |
| 20 | new 4h lows bounce | REAL-NOT-TRADABLE | R5 | descendant of the reversion family |
| 21 | liquidation spikes | FAIL | R1, R10 | contradicted (failed again); descendant (descriptive mechanics) |
| 22 | forward: spike decay | RUNNING | — | negative evidence, no descendant |
| 23 | forward: spike short | RUNNING | — | negative evidence, no descendant |
| 24 | forward: low bounce | RUNNING | — | negative evidence, no descendant |
| 25 | OI-drop breakdowns | FAIL | — | negative evidence, no descendant |
| 26 | forced liquidations (#26) | HOLDS | R2, R10, E1 | replicated + extended (executable variant); descendant (descriptive mechanics); forward test of the only hold |
| 27 | forward: #26 live | RUNNING | — | negative evidence, no descendant |
| 28 | leveraged ETFs | FAIL | — | negative evidence, no descendant |
| 29 | forward: post-close | RUNNING | — | negative evidence, no descendant |
| 30 | resting bids | FAIL | — | negative evidence, no descendant |
| 31 | forward: 2-ATR bids | RUNNING | — | negative evidence, no descendant |
| 32 | forward: funding split | RUNNING | — | negative evidence, no descendant |
| 33 | fill cost at 00:00 | FAIL | — | negative evidence, no descendant |
| 34 | 2x funds push alts | RUNNING | — | negative evidence, no descendant |
| 35 | stop runs reverse | FAIL | — | negative evidence, no descendant |
| 36 | Ethena flows | FAIL | — | negative evidence, no descendant |
| 37 | hourly crowd vs RW | FAIL | — | negative evidence, no descendant |
| 38 | forward: shorts pay | RUNNING | — | negative evidence, no descendant |
| 39 | markout measurement | NOT-A-TEST | — | negative evidence, no descendant |
| 40 | testnet reconciliation | PLUMBING | — | negative evidence, no descendant |
| 41 | markout, thin coins | NOT-A-TEST | — | negative evidence, no descendant |
| 42 | rehearsal | PLUMBING | — | negative evidence, no descendant |
| 43 | horizon map | CONFIRMED-WEAK | R9 | descendant (regime conditioning) |
| 44 | day-mean audit | NOT-A-TEST | R9, R10 | descendant (regime conditioning); descendant (descriptive mechanics) |
| 45 | forward: #26 holds 4h-1d | RUNNING | — | negative evidence, no descendant |

**23 descendants across 16 originals** — 40 of the 46 were inherited as
negative evidence rather than re-run. Our own findings, with their ancestors:

| id | finding | status | ancestor | lessons carried |
|---|---|---|---|---|
| P1 | sma plumbing | plumbing | none (mechanics only) | never evidence; books void |
| R1 | liqspike | replication | #21 | trade-weighted + day-mean both reported; holdout sealed |
| R2 | liq26-replication | replication | #26 | trade-weighted, 9 bps cost bar, executable variant |
| R3 | carry-deep | trial | #12, #14 | net of fees and funding; holdout read once |
| R4 | xs-momentum | trial | #2, #7, #16, #17 | survivor-free universe (LUNA), costs, holdout |
| R5 | pairs-coint | retired | #19, #20 | BH FDR over 231 pairs; no candidate |
| R6 | factor-pca | retired | #8 | out-of-sample validation; risk-only finding |
| R7 | residual-pairs | retired | #8, #19 | FDR; half-life floor registered before scan |
| R8 | residual-pairs-cost | retired | #8, #19 | design-window cost test, 5 bps/side |
| R9 | regime-scan | retired | #4, #15, #21, #26, #44 | BH over 11 families; validation/holdout split |
| R10 | liquidation-anatomy | audit | #18, #21, #26 | descriptive quantiles; no cost bar claimed |
| R11 | hardening | audit | #44 | selection cost + power; cross-checks E1's statistics |
| R12 | maker | audit | #12, #30 | one venue-day, descriptive, no BH by design |
| R13 | regime-signs | audit | #4, #15, #43 | 16 cells, BH, none survives; venue-specific funding noted |
| R14 | sizing | audit | #4 | matched-exposure comparison, 9 bps cost, no funding modelled |
| R15 | tape-edges-design | audit | #18, #21, #26 | 8 cells, BH, 9 bps bar, all fail |
| R16 | tape-study | audit | #21, #26 | pre-registered, 12 directional cells, cost bar, none pass |
| R17 | tape-study-2 | audit | #21, #26 | OFI at 30-60 s: BH-significant, 40-70x below cost |
| R18 | vpin | audit | #21, #44 | pre-registered; volatility forecast only, no direction claim |
| E1 | executable bounce (forward) | pending | #26 | sealed registration, single holdout read 2027-04-30 |

## The eight documents that had no ledger row

Audited against the five failure modes the original repository taught (day-mean, no cost bar,
overlapping labels, non-executable tag, venue-dependent fills). All eight apply a **cost bar**
(9 bps) where a return is claimed, use **BH** for multiplicity where cells are counted, and state
**one-month / one-venue** limits. None claims a direction edge it does not have. They are now
ledgered as `audit` rows R11–R18 so the count and the multiplicity accounting are complete.

## The count, honestly

| | n |
|---|---|
| original findings (audited) | 46 |
| originals with a descendant of ours | 16 (21 descendants, including E1) |
| originals inherited as negative evidence only | 30 |
| our own findings (ledgered) | 20 (12 before this pass + 8 now ledgered) |
| pending | 1 (E1) |

## The rule

1. A new result cites its ancestor id, or states `no ancestor`.
2. A negative ancestor is cited to justify *not* re-running its family; it never counts as evidence.
3. Any document that claims a return names its cost bar and its estimator.
4. Nothing cites a result as evidence unless its ledger row is `holds` or its registration is sealed.
