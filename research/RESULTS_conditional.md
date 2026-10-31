# Result — state-conditional distributions (the "is the 3rd candle green?" question)

**Verdict: there is no conditional rule here — there are skewed distributions.** After two or three
down hours the *median* next hour is slightly negative and the hit rate is below 50%; the *mean* is
positive only because the right tail is fatter than the left. 35 cells tested, **1 passes FDR**, and
that one is tail-driven. The one-day order-flow sample shows nothing.

Code: `research/conditional_study.py` · data: `conditional_study.json`.

## Sample A — 2023-01 → 2024-11, ten coins, hourly

`down_run` = consecutive hourly closes below the previous one at the moment of the state.

| state | n | mean | median | p10 | p90 | up | FDR |
|---|---|---|---|---|---|---|---|
| down_run=2 → 1h | 3,149 | **+17.7** | **−3.3** | −142.9 | +220.4 | 48% | **yes** |
| down_run=2 → 4h | 3,149 | +26.0 | +0.3 | −332.6 | +438.3 | 50% | no |
| down_run=3 → 1h | 1,626 | +3.9 | −6.4 | −149.3 | +194.8 | 47% | no |
| down_run=3 → 4h | 1,626 | −0.4 | −10.9 | −379.6 | +415.9 | 48% | no |

**The "green 3rd candle" is not there.** After two down hours the typical outcome is a small loss;
the average is positive because the up-moves are larger when they happen. That is skew, not a rule —
and the single FDR pass is exactly the cell you would expect to survive 35 tries by chance, with a
median that contradicts it.

Liquidation states are the same story with wider tails:

| state | n | mean | median | p10 | p90 | up |
|---|---|---|---|---|---|---|
| long_liq>99pct → 1h | 246 | +16.7 | +23.8 | −203.5 | +317.3 | 57% |
| long_liq>99pct → 8h | 246 | +94.4 | +34.9 | −662.5 | +907.7 | 54% |
| long_liq>95pct → 8h | 1,207 | +54.1 | +38.4 | −578.4 | +738.3 | 55% |

A positive median with a ±600 bp 10–90 band is not a signal; it is a coin-flip with a lottery ticket
attached. No liquidation cell survives FDR.

## Sample B — one day of order flow, 2023-07-10, 11 symbols

Taker-flow extremes (CVD bottom/top decile) against the next 5-minute mid return:

| state | n | mean | median | up |
|---|---|---|---|---|
| CVD bottom 10% | 1,584 | −1.0 bps | +0.0 | 49% |
| CVD top 10% | 1,595 | −0.3 bps | +0.0 | 47% |

Nothing. And this is a **single day**: it cannot support a conclusion either way, only show the
pipeline works on tick data.

## What this establishes

1. **Multi-timeframe "bearish alignment" does not predict a green candle** — the median and hit rate
   point the other way, and the mean is a skew artefact.
2. **The stable feature across every cell is the width of the distribution**, not its centre: a
   ±200–900 bp 10–90 band per hour means any rule without sizing and stops is a coin flip.
3. **Conditional tables are exactly how overfitting gets dressed up.** 35 cells, one FDR pass,
   contradicted by its own median — this is why the project counts tests.
4. The honest product is **risk**, not direction: liquidation and down-run states widen the
   distribution; they do not bend it.

## Limits

- Overlapping forward windows (hourly observations, 1/4/8 h horizons); day-clustered intervals only.
- COIN-M liquidations; hourly aggregates, no intra-hour timing.
- Order-book **quantities were not stored** in the tick ingest, so true OBI is not computed here —
  only taker flow. Fetching `bookTicker` with sizes for more days is the next data job.
- Sample B is one day by design (the only day ingested).
