# Pre-registration — VPIN / flow toxicity on BTC

**Written before running.**

## Question

Does volume-synchronised order-flow toxicity (VPIN) forecast short-horizon volatility or absolute
returns on BTC?

## Data

29 cached Binance USD-M `BTCUSDT` daily aggTrades (2026-10-01 → 2026-10-30, one archive missing).
Trades only; no quotes in this study.

## Measure (fixed)

- Volume buckets: **500 equal-volume buckets per UTC day** (bucket size = daily volume / 500), sequential.
- Per bucket: `V = buy_qty + sell_qty`, `imbalance = |buy_qty − sell_qty| / V`.
- **VPIN** = 50-bucket rolling mean of imbalance; a bucket's value becomes known at its last trade time.
- Minute series: last completed VPIN mapped backward (causal only).

## Hypotheses and statistic

| id | outcome | prediction |
|---|---|---|
| H1 | next **60-minute realised variance** (std of next 60 one-minute log returns) | high VPIN → higher variance |
| H2 | next **30-minute absolute return** | high VPIN → larger absolute move |

Per day: mean outcome in the top VPIN quintile minus the bottom quintile of minutes. t across the 29
daily values (two-sided 5%); BH at 10% across the 2 cells.

## Costs

VPIN is a risk/context measure, not a trade signal; no cost bar applies. A positive result would be
used for sizing and execution timing, not direction.

## Governance

One run, fixed 500-bucket/50-window/30-60-minute choices; all cells reported; result in
`research/RESULTS_vpin.md`.
