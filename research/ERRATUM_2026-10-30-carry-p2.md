# Erratum — the P2 measurement in the carry result

**Status: the sealed verdict (FAIL) stands. The reason it failed is a measurement error on my side,
not a failure of the strategy.** This note corrects the record and is committed as a separate
document; the sealed pre-registration and the result are not edited.

## What I wrote

In `RESULTS_2026-10-30-carry-deep.md`:

> P2 — net carry per unit of funding < 1: **fails**: 15.4/11.3 = **1.36**. […] the harvest earns
> funding *plus* the convergence of the basis it entered at a premium.

That sentence contains two mistakes.

## Mistake 1 — the denominator

The **11.3%/yr** was `gross_funding_annual_pct` from `carry_deep.json`, which is the **universe average
funding over every day**, including the days and symbols with no position. Worked examples: a flat
day contributes 0; an inactive symbol contributes 0; both dilute the numerator of "funding it
collects".

Funding **actually collected while holding**, measured over the same days the return is measured
(the 176 active days), is **+21.2%/yr**. The registered P2 says "the funding it collects", so the
correct ratio is:

```
net 15.4% / funding collected 21.2% = 0.73 < 1   →  P2 is met as written
```

The harvest kept **73%** of the funding, and the basis plus costs took the other 27%. That is the
opposite of what the result document claimed: basis convergence did not add to the return; it
subtracted from it.

## Mistake 2 — the "fix" does not identify alpha

The first attempt at a corrected criterion regressed net returns on the funding collected. It returns
an intercept of −10.8%/yr with t = **−734**, which is not a result: the basis P&L is in the error
term, so the intercept absorbs the average basis drift and the HAC standard error collapses. There is
no clean "alpha vs premium" statistic in that regression.

The honest decomposition is arithmetic, not a test:

```
funding collected        +21.2%/yr
basis P&L + costs         -5.8%/yr
-----------------------------------
net                     +15.4%/yr
```

## What follows

- **The sealed verdict remains FAIL** (P1 and P2 as written could not both be evaluated; the
  registration is the contract, and I do not rewrite it after the fact).
- **The strategy's design-window evidence is stronger than the result document says**: P1 passes
  (+15.4%, CI +6.0…+26.2, t 3.13) and P2, once its denominator is the funding actually collected,
  also passes (0.73).
- **The holdout is unchanged and decisive**: 4 entry signals in 4,307 symbol-days, no exposure. The
  absolute 20% threshold is a regime bet, and that finding is unaffected by this erratum.
- **Process fix**: every future registration must define the denominator of every ratio explicitly
  ("funding collected while holding", not "funding averaged over the universe"). This is now in the
  preregistration template.

## Files

- `research/carry_p2_alpha.py`, `research/carry_p2_alpha.json` — the intercept attempt and why it
  fails to identify the question.
- The sealed documents are untouched: `PREREGISTRATION_CARRY_DEEP.md`, `RESULTS_2026-10-30-carry-deep.md`.
