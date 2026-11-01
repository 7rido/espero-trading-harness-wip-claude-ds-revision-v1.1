# Inheritance — what each finding stands on

Two tables, one rule. **Table A**: each original finding, what it concluded, what we built on it,
and what it now contradicts. **Table B**: the eight documents that had no ledger row, audited against
the five failure modes the original repository taught.

## A. The 46 originals

| id | concluded | our build | contradicts |
|---|---|---|---|
| 1 | next-day return after z<-2 → FAIL | — | — |
| 2 | holdout CAGR vs BTC → FAIL | R4 | R4: 2023 holdout +27.8%/yr, t 0.75 — not significant |
| 3 | LP P&L → FAIL | — | — |
| 4 | Sharpe 1.08 vs 1.02 → UNRESOLVED | R9 | R9: no trend regime separates forward returns on validation |
| 5 | holdout Sharpe/CAGR → FAIL | — | — |
| 6 | Spearman +0.024 → FAIL | — | — |
| 7 | forward paper test → EXPLORATORY | R4 | R4: same family, same failure |
| 8 | Sharpe 0.92 vs 0.45; IC t 8.11 → CONSTRUCTION | R6, R7, R8 | R6: factor books flip sign out of sample (PC1 +47% → −10.9%) |
| 9 | IC vs rev_1 → FAIL | — | — |
| 9b | IC t 13.44 → FAIL | — | — |
| 10 | PF / net / DD → FAIL | — | — |
| 11 | ann 5.2%, Sharpe 0.88 → FAIL | — | — |
| 12 | ann 10.9% at 0 bps maker → VENUE-DEPENDENT | R3 | R3: 2025 holdout never traded (regime), so no out-of-sample carry |
| 13 | PF / net → FAIL | — | — |
| 14 | ann return → FAIL | R3 | R3: same premium, still no evidence |
| 15 | trend vs vol-only → FAIL | R9 | R9: nine regime families, none survives FDR |
| 16 | IC t → FAIL | R4 | R4: survivor-free universe does not rescue it |
| 17 | IC t → FAIL | R4 | R4: same |
| 18 | D forced-organic → FAIL | R9, R10 | R10: liquidations give a skewed bounce, not a rule |
| 19 | g +15.5 bps, t 3.52 → REAL-NOT-TRADABLE | R5 | R5: 0 of 231 pairs survive FDR |
| 20 | +14.8 bps, t 9.78 → REAL-NOT-TRADABLE | R5 | R5: same family, no candidate |
| 21 | R +4.8 bps, t 0.27 → FAIL | R1, R10 | R1: day-mean t 0.85, trade-weighted −19.7 bps |
| 22 | spike decay → RUNNING | — | — |
| 23 | short leg → RUNNING | — | — |
| 24 | 4h bounce → RUNNING | — | — |
| 25 | D oi_drop → FAIL | — | — |
| 26 | D -23.6, t -4.06; leg +19.2 → HOLDS | R2, R10, E1 | R2 replicates it; but the tag was non-executable and net at 1h ≈ 0 — E1 tests the fix |
| 27 | D + long leg → RUNNING | — | — |
| 28 | after-close reversal → FAIL | — | — |
| 29 | reversal → RUNNING | — | — |
| 30 | net bps/fill → FAIL | — | — |
| 31 | net/fill → RUNNING | — | — |
| 32 | split D → RUNNING | — | — |
| 33 | m30 by bucket → FAIL | — | — |
| 34 | placebo +0.5 bps → RUNNING | — | — |
| 35 | reversal +15.3, t 7.0 → FAIL | — | — |
| 36 | funding forecast → FAIL | — | — |
| 37 | hit rate / Brier → FAIL | — | — |
| 38 | short basis → RUNNING | — | — |
| 39 | maker markout → NOT-A-TEST | — | — |
| 40 | fills/orders → PLUMBING | — | — |
| 41 | maker markout → NOT-A-TEST | — | — |
| 42 | 8 procedure rows → PLUMBING | — | — |
| 43 | S1 12h +21.8 bps → CONFIRMED-WEAK | R9 | R9: no regime sign survives |
| 44 | 16 headlines → NOT-A-TEST | R9, R10 | informs every estimator we use (R1, R4, R9) |
| 45 | net by hold → RUNNING | — | — |

**Counts**: 21 descendants across 16 originals; 30 originals are negative evidence with no
descendant — cited so their families are not re-run, never counted as evidence.

## B. The eight documents that had no ledger row

Failure modes: **F1** estimator stated (day-mean vs trade-weighted), **F2** cost bar where a
return is claimed, **F3** overlapping forward windows addressed, **F4** executable signal
timing, **F5** venue/fill assumption explicit. ✓ pass · ✗ gap · n/a not applicable.

| doc | F1 | F2 | F3 | F4 | F5 | verdict |
|---|---|---|---|---|---|---|
| hardening | n/a | ✓ 9 bps | ✓ power sim | ✓ | ✗ venue not discussed | ledgered R11 |
| maker | n/a | n/a (no claim) | n/a | n/a | ✓ one venue-day | annex→R12 |
| regime-signs | ✗ means, estimator unstated | n/a (descriptive) | **✗ 5d/20d daily overlap** | n/a | ✓ funding venue noted | **gap; ledgered R13 with caveat** |
| sizing | ✓ Sharpe at matched exposure | ✓ 9 bps | n/a | n/a | ✗ no funding (disclosed) | ledgered R14 |
| tape-edges-design | ✗ mean+t, estimator unstated | ✓ 9 bps | ✓ BH | n/a | ✓ one month/venue | ledgered R15 |
| tape-study | ✓ pre-registered | ✓ 9 bps | ✓ BH | ✓ pre-registered timing | ✓ one venue | ledgered R16 |
| tape-study-2 | ✓ cluster noted | ✓ 9 bps | ✓ BH | n/a | ✓ one venue | ledgered R17 |
| vpin | ✓ pre-registered | n/a (variance) | ✓ BH | n/a | ✓ one venue | ledgered R18 |

**What the audit found**: two real gaps — `regime-signs` reports means over **overlapping 5d/20d
windows** without a correction, and `tape-edges-design` reports means with t without stating the
estimator. Both are now ledgered with that caveat in the row; neither is ever evidence. The other
six are clean, and five of them are explicitly descriptive with no direction claim.

## C. Result documents and their ids (checked by CI)

| document | id | kind |
|---|---|---|
| `P1` plumbing books | P1 | plumbing — never evidence |
| `A1` audit-by-number | A1 | audit of the 46 originals |
| `RESULTS_2026-10-30-carry-deep.md` | R3 | registered |
| `RESULTS_2026-10-30-liq26-replication.md` | R2 | registered |
| `RESULTS_2026-10-30-liqspike.md` | R1 | registered |
| `RESULTS_2026-10-30-xs-momentum.md` | R4 | registered |
| `RESULTS_conditional.md` | annex (descriptive) | annex |
| `RESULTS_conditional_suite.md` | annex (descriptive) | annex |
| `RESULTS_hardening.md` | R11 | audit |
| `RESULTS_liquidation_anatomy.md` | R10 | audit |
| `RESULTS_maker.md` | R12 | audit |
| `RESULTS_program_phase1.md` | annex (A1) | annex |
| `RESULTS_queue_execution.md` | annex (execution) | annex |
| `RESULTS_regime_signs.md` | R13 | audit |
| `RESULTS_regimes.md` | R9 | registered |
| `RESULTS_rp2.md` | R7 | registered |
| `RESULTS_rp3.md` | R8 | registered |
| `RESULTS_sizing.md` | R14 | audit |
| `RESULTS_tape_edges_design.md` | R15 | audit |
| `RESULTS_tape_study.md` | R16 | audit |
| `RESULTS_tape_study_2.md` | R17 | audit |
| `RESULTS_vpin.md` | R18 | audit |
| `RESULTS_2026-11-01-liq45-forecast.md` | annex (forecast retest) | forecast retest of #45 |

## The rule (enforced)

1. A new result names its ancestor id, or states `no ancestor`.
2. A negative ancestor justifies not re-running a family; it never counts as evidence.
3. Any return claim names its estimator and its cost bar.
4. Nothing is evidence unless its ledger row is `holds` or its registration is sealed.

Enforcement: `scripts/check_inheritance.py` (CI) requires every ledger id to appear in this file,
every `RESULTS_*.md` to be referenced here, and all 46 original ids to be present. The template for
new results is `research/RESULT_TEMPLATE.md`.
