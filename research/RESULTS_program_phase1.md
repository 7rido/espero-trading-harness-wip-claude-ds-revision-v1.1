# Program report — volatility model, pairs, factors (phase 1)

**Gate outcome: zero candidates passed.** The program built three instruments, tested each on data the
analyst had not seen, and found no signal that survives out-of-sample, net of costs, after
multiplicity. No policy was fitted, no disproof suite was run (there is nothing to disprove), and
nothing was authorised to trade.

This is the designed outcome, not a failure of the build: the gate exists to stop a policy from being
fitted to a signal that has not earned one.

## Phase 0 — data

`research/extend_substrate.py` aggregated the local 5-minute archive into the substrate:

| table | rows | symbols | span | duplicates |
|---|---|---|---|---|
| `bars_daily` | 82,774 | 42 | 2020-01-01 → 2026-03-31 | **0** |
| `rv` (realised variance, Parkinson, Garman–Klass) | 82,774 | 42 | same | **0** |

Windows fixed before any model: **design 2020–2022**, **validation 2023**, holdout
**2025-07 → 2026-03** (not read in phase 1, disclosed as previously present in the repo via the
retired SMA backtest).

## Instrument 1 — volatility model (risk, not alpha)

HAR-RV against EWMA(0.94) and a trailing mean, scored by QLIKE on 2023, 38 symbols with enough data:

| model | mean QLIKE | median | beats EWMA on |
|---|---|---|---|
| **HAR-RV** | **0.393** | 0.344 | **35 / 38 symbols** |
| EWMA(0.94) | 0.450 | 0.412 | — |
| trailing mean (22d) | 0.516 | 0.478 | 1 / 38 |

HAR is a real, repeatable improvement and is the **usable output** of this phase: it becomes the
variance input for position sizing and limits. It generates no signal and claims no edge.

## Instrument 2 — co-integration pairs

Rolling 180-day Engle–Granger on 30 liquid names, monthly refits across 2022, Benjamini–Hochberg FDR
at 10% over every pair tested, half-life filter 5–30 days, design window only:

- **231 pairs tested, 0 survive FDR.**
- Best raw candidate: **FIL|XTZ**, median ADF p **0.0043**, half-life 5.2 days, significant in 83% of
  months. At an uncorrected 1% this is a "discovery"; after 231 tests the BH threshold is ~0.0004 and
  it does not pass.
- Next: LINK|ICP 0.0071, SUSHI|XTZ 0.0093, LTC|THETA 0.0098 — the same story.

**Interpretation:** at this standard, crypto perps do not offer a cointegrated pair universe; the
apparent short-half-life pairs are a multiple-testing artefact. The instrument works (it finds what a
naive screen would), and the discipline is what rejects it.

## Instrument 3 — factor model

PCA on design returns, 42 names; PC1 explains **66.1%** of variance (the market), PC2 4.2%, PC3 3.7%.
Fixed design loadings, long top / short bottom quintile, equal weight, raw returns (no look-ahead):

| book | design 2020–22 | validation 2023 |
|---|---|---|
| PC1 | +47.2%/yr (t 0.99) | **−10.9% (t −0.42)** |
| PC2 | −42.0% (t −1.04) | −7.9% (t −0.35) |
| PC3 | −44.6% (t −0.99) | −7.4% (t −0.20) |

The strongest design book flips sign out of sample and never reaches significance. **The factor model's
value is risk decomposition — covariance, exposures, hedging — not alpha.** As a signal it fails.

## What the gate blocked

Phase 3 (policy) requires a candidate with a CI excluding zero after costs. None exists, so:

- **no policy function was fitted** (fitting one on a failed signal is how overfitting starts);
- **no disproof suite was run** (nothing to try to break);
- **no ledger row reached `holds`**, no `PLUMBING.md` window, no paper execution.

## Honest reading

Three instruments, one usable risk model, two negative results. The pattern is the same one the
original repo took 46 tests to learn: at this level of noise, most apparent edges are multiplicity.
The difference here is that the filter ran *before* a policy or a trade, not after.

## What would change the answer

Each is a **new** pre-registration, not a re-tune of this one:

1. **Residual pairs**: cointegrate after removing the market and factor exposures (PC1 dominates 66% of
   variance; unconditional pairs are dominated by it).
2. **Regime-conditioned factors**: size the factor book by the volatility state (HAR gives the state),
   which is a different hypothesis from a static loading book.

## Files and reproduction

```
python research/extend_substrate.py build     # bars_daily + rv
python research/vol_model.py                  # HAR vs EWMA, QLIKE
python research/pairs.py scan                 # BH-FDR pair discovery (design only)
python research/factor_model.py               # PCA books, design + validation
```

Outputs: `vol_model.json`, `pairs_all.csv`, `pairs_frozen.csv` (empty by construction), `factor_model.json`,
`factor_loadings.csv`, `extend_report.json`.
