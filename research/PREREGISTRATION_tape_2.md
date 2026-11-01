# Pre-registration — tape study 2: seconds-scale OFI, markout by print size, session structure

**Written before running.** Follows the first tape study, which found no direction at 5–60 minutes and a
strong intensity→volatility relationship.

## Data

The 29 cached Binance USD-M `BTCUSDT` daily aggTrades files from the first study (2026-10-01 → 2026-10-30).
No new fetch. Venue: Binance UM.

## H5 — seconds-scale order-flow imbalance

Literature places OFI at seconds. Buckets of **30, 60 and 180 seconds**. In each bucket compute
`ofi = (buy_qty − sell_qty)/(buy_qty + sell_qty)`; outcome is the **next bucket's return** (same horizon).
Statistic: within each UTC day, mean forward return of the top OFI quintile minus the bottom quintile;
t across days (two-sided 5%), BH at 10% across the 3 cells.

## H6 — markout by print size

For every agg print, take the taker side and the signed future return at **+10 s and +60 s**
(`buy: p_future/p − 1`, `sell: 1 − p_future/p`, in bps). Bucket prints by notional:
**< $10k, $10k–100k, $100k–1M, > $1M**. Per day, average markout per bucket; t across days. BH at 10%
across the 8 cells. This is an execution question (did the aggressor get a good fill), not a trade
signal; no cost bar applies.

## H7 — session structure (descriptive, not tested)

Hour-of-day means of OFI, absolute 1-minute return, volume and prints; reported as a table with no
inference claim.

## Governance

One run; fixed buckets, horizons and bins; all cells reported. Result in `research/RESULTS_tape_study_2.md`.
