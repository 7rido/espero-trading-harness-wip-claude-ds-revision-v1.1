# Result — VPIN / flow toxicity on BTC

**Verdict: VPIN forecasts short-horizon variance and absolute moves; both pre-registered cells pass BH.
It is a risk instrument, not a direction signal.**

Registration: `research/PREREGISTRATION_vpin.md` · code: `research/vpin_study.py` · data: `vpin_study.json`.
29 days of cached Binance UM BTCUSDT aggTrades; 500 equal-volume buckets/day, 50-bucket VPIN window,
mapped causally to minutes.

| test | days | spread (top − bottom VPIN quintile) | t | p | BH |
|---|---|---|---|---|---|
| next 60-min realised variance | 29 | **+7.6e-5** (std units) | **2.98** | 0.003 | ✅ |
| next 30-min absolute return | 29 | **+3.95 bps** | **2.72** | 0.007 | ✅ |

Read: minutes in the highest-toxicity quintile are followed by ~**4 bps larger absolute moves** and a
measurably higher variance over the next hour than the lowest-toxicity quintile. The effect is a
volatility/state signal — it says nothing about direction, and no cost bar applies because it is not a
trade.

## Limits

- One month, one venue; no quotes, so the "toxicity → spread widening" claim is untested.
- VPIN definition (500 buckets, 50-window) fixed by registration; other settings were not tried.
- Buckets are day-relative, so cross-day comparisons of VPIN levels are not meaningful.

## Use

Sizing and execution timing: when VPIN spikes, expect larger moves (widen stops, avoid market orders,
prefer passive fills). The scorecard records it as a risk measurement, not a predictor.
