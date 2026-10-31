# Pre-registration — replication of #21 (liquidation spikes reverse) on the sealed months

Written 2026-10-30, **before any return was computed**. What had been seen: the schema (header plus
three rows), and the file list. No price change, no return, no statistic.

## Why

The original repo's #21 is a sealed-month test that returned FAIL. Replicating it here does two things
at once: it checks that our independent implementation and our copy of the data reach the same
conclusion, and it gives espero2 its first real test run under its own rules (pre-register, run once,
write the verdict as committed).

## Data

- `data/aggr/holdout/2026-07 … 2026-10.csv.gz` — four sealed months, SHA-256 verified against
  `reference/aggr_holdout_manifest.json` (sealed 2026-10-29, all four match).
- `data/aggr/explore/2026-04 … 2026-06.csv.gz` — **warm-up only**, for the trailing 720-hour
  thresholds of the first holdout hours. No return from the explore months is used.
- 14 coins with the original market mapping: price from Binance USDⓈ-M futures (OKX for SHIB),
  liquidations summed over Binance, Bybit and OKX.

## Rule (the original's, unchanged)

Hourly, per coin:

- liquidation share `s` = dollars liquidated on that side in the hour ÷ the hour's dollar volume;
- a **spike** is an hour whose `s` is at or above the 98th percentile of that coin's previous 720
  observed hours (strictly prior hours; no look-ahead);
- long-liquidation spike: `lsell` side (longs forced out). Short-liquidation spike: `lbuy` side;
- horizon returns: close of the spike hour → close h hours later, h ∈ {1, 4, 24};
- baseline: the mean of the same horizon return over **every** coin-hour in the window;
- excess = event return − baseline;
- **R = excess for long-liquidation spikes** (a bounce is the reversal), **R = −excess for
  short-liquidation spikes** (a fall is the reversal).

## Estimator

**Day-mean**, to match the run being replicated: one observation per UTC day (the mean of that day's
events), then the mean of days and a t-statistic across days. The trade-weighted mean with
day-clustered errors is reported beside it as information, because the original's own later audit
(#44) showed the day-mean overweights quiet days.

## Criteria (the original's four; PASS needs all four)

1. the forced flow reverts: mean R > 0 with **t ≥ 3** (24 h horizon);
2. each side: long-spike excess 24 h > 0 **and** short-spike excess 24 h < 0;
3. not one stretch: R > 0 in both halves (2026-07-01 → 2026-08-15; 2026-08-16 → 2026-10-27);
4. a long-only trade pays: raw 24 h return after long-liquidation spikes **> 18 bps** with **t > 2**.

Anything else is FAIL. No re-tuning, no early stop.

## Power, stated in advance

The original reported a day-mean t of 0.27 for criterion 1 on 117 days — so this replication is
expected to FAIL, and a FAIL does not by itself mean the effect is absent; it means this window
cannot show it. A PASS here would be evidence *against* the original's FAIL, and would be reported as
a contradiction worth investigating, not as a discovery.

## Outcomes, fixed now

- **PASS (all four)**: the original's FAIL is contradicted; write it up as a discrepancy and check the
  market mapping and spike definition before anything else.
- **FAIL (any criterion)**: consistent with the original; record which criterion and by how much.
- Either way, the numbers go into `research/RESULTS_2026-10-30-liqspike.md` and one row in
  `strategy_ledger.csv`; nothing is tuned afterwards.

## Transparency

- The holdout seal was verified (4/4 hashes) before the run.
- The market mapping and spike definition are copied from the original's `aggr_explore.py`/`liqspike`
  code, not re-invented.
- There is no warm-up leak: explore months inform thresholds only, and every return uses holdout
  closes only.
