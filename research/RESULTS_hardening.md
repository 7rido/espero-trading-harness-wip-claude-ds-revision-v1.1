# Result — hardening: selection cost, E1 monitoring power, maker fills

Three tests of the project itself rather than the market. Two of them change how everything else
should be read.

## 1. Selection cost: the mechanism survives, the rest does not

`research/selection_cost.py` over 11 trials with reported t (registered family 9, full family 121
cells computed), two-sided exact tails, Monte-Carlo null for the maximum.

| trial | t | p | family-wise (N=121) |
|---|---|---|---|
| **liq26_D** (forced vs organic, same bar) | **−5.13** | **2.9e-7** | **3.5e-5** ✅ |
| **liq26_exec** (executable prior-day bounce, 4h) | **4.01** | **6.1e-5** | **0.0073** ✅ |
| carry design | 3.13 | 0.0017 | 0.19 ❌ |
| regimes best | 2.70 | 0.0069 | 0.56 ❌ |
| conditional suite best | 2.60 | 0.0093 | 0.68 ❌ |
| XS design | 2.23 | 0.026 | 0.96 ❌ |

**Reading**: the liquidation mechanism and its executable variant are the only results that beat the
family-wise bar even at 121 cells. Everything else — carry, regimes, premium, XS — is what a
121-test family produces by chance. This is the strongest justification the project has for E1 being
the right forward test.

Two bugs were caught doing it: a tanh normal approximation that broke at large t (turning
p = 3e-7 into 0.006), and a power simulation that treated one draw as the sum of many trades.

## 2. E1 sequential monitoring: 70% power, not 95%

`research/e1_monitor.py`: six monthly looks, two-sided 5%, Lan-DeMets O'Brien-Fleming.

| look | z boundary | P(stop by here) if effect is 32 bps |
|---|---|---|
| 1 (Nov 30) | 4.80 | 0.0% |
| 2 (Dec 31) | 3.39 | 2.5% |
| 3 (Jan 31) | 2.77 | 15.0% |
| 4 (Feb 28) | 2.40 | 34.8% |
| 5 (Mar 31) | 2.15 | 54.6% |
| 6 (Apr 30) | 1.96 | **70.4%** |

**Reading**: if the in-sample +32 bps is real, E1 has a **70% chance** of detecting it by the final
look and a **30% chance of a false negative**. That number should be written down before April, so a
null at the end is read as "not detected in this window", not "disproved".

## 3. Maker fills: 61% / 64%, not "22–87%"

`research/maker_fill.py`, Tardis SOL 2026-10-01: 11.3M book updates, 1.95M trades.

| spread quartile | n | buy fill | sell fill |
|---|---|---|---|
| tightest | 367 | 60.5% | 61.9% |
| Q2 | 357 | 51.3% | 49.9% |
| Q3 | 358 | 61.2% | 65.6% |
| widest | 358 | 73.2% | 76.8% |
| **all** | 1,440 | **61.5%** | **63.5%** |

**Reading**: the 22–87% assumption is not wrong, but it is so wide it hides the real structure — fills
cluster near **60%**, and tighter spreads fill *less* (50–60%) than wide ones (73–77%). A cost model
that assumes a constant fill rate misprices exactly the quiet, tight-spread regime where most trades
happen.

## What this changes

1. **E1 is the only test worth running forward** — the mechanism beats selection; the rest does not.
2. **E1's power is 70%**, so plan for a possible false negative and pre-commit how it will be reported.
3. **Maker fills should be modelled per spread regime**, not as one number.

## Limits

- The family count (121) includes correlated cells, so the family-wise p is conservative; the
  registered 9-trial view gives the same verdict for the mechanism (p 2.6e-6) and for carry (p 0.016 — still fails at 0.05/9).
- Maker fills use one day, one symbol, and a queue-at-the-back assumption; the true fill rate depends on
  queue position and on whether the exchange shows full size.
- Sequential boundaries assume the 4 h trade returns are close to normal; the empirical tails are fat,
  which makes the OBF boundaries slightly optimistic.
