# Result — queue-aware execution (the last registered gap)

One day of event data (2023-07-10) for 11 depth-covered symbols, the two largest excluded for size:

| | |
|---|---|
| `bookTicker` rows ingested | **45,547,988** |
| `aggTrades` rows ingested | **3,296,200** |
| symbols | ADA, ARB, AVAX, BNB, DOGE, FIL, LINK, NEAR, SOL, SUI, XRP |

## Spread — quoted and effective are the same

| symbol | quoted half-spread | effective half-spread | maker fill, 60 s | median fill |
|---|---|---|---|---|
| SOLUSDT | 0.24 bps | 0.24 | 87% | 3.8 s |
| BNBUSDT | 0.21 | 0.21 | 78% | 6.7 s |
| AVAXUSDT | 0.38 | 0.37 | 74% | 6.8 s |
| ARBUSDT | 0.45 | 0.45 | 70% | 13.5 s |
| SUIUSDT | 0.77 | 0.77 | 66% | 15.1 s |
| DOGEUSDT | 0.77 | 0.77 | 56% | 18.4 s |
| FILUSDT | 1.18 | 1.18 | 56% | 19.7 s |
| LINKUSDT | 0.82 | 0.82 | 52% | 19.3 s |
| ADAUSDT | 1.75 | 1.75 | 37% | 24.9 s |
| XRPUSDT | 1.06 | 1.06 | 26% | 21.6 s |
| NEARUSDT | 3.82 | 3.80 | 22% | 20.7 s |

Two facts matter. **Effective = quoted**: trades execute at the touch, so the taker cost is the half
spread plus the fee — 5.2 to 8.8 bps a side — not the 100 bps the depth-band model charged to small
orders. And **maker fills are quick**: 22–87% within a minute, median 3.8–24.9 s, with a 5-second
markout of **−1.0 to −2.2 bps** (adverse selection after the fill), small against the half spread.

## What this does to the answer

The earlier reprice charged linear impact inside the 1% depth band; at $100k–$1M per side that was
**conservative**. Measured spread + fee costs roughly **6 bps a side**, i.e. ~6%/yr of drag at weekly
turnover rather than the 9% the depth model charged at $1M. The holdout net at $1M/side is therefore
**~+29%/yr**, not +26.4% — better, and still indistinguishable from zero (t 0.75) and still far below
the design's +100%.

**The conclusion is unchanged and now measured rather than modelled: the test failed on signal decay,
not on execution. Liquidity constrains scale, not the verdict.**

## Limits, stated

- **One day, eleven symbols.** A single day cannot represent 2021–2023 regimes; this is a calibration
  of the cost model, not of the strategy.
- **Best level only.** `bookTicker` gives the touch; impact beyond it still comes from `bookDepth`
  snapshots, so large orders remain modelled rather than simulated.
- **Markout window 5 s**, chosen before inspection, not optimised.
