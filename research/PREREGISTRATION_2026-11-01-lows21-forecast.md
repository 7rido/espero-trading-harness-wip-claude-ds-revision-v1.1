# Pre-registration — #20 and #21, forecast retest

Written **before any forecast IC or spread in this document is computed**. It follows the
remaining-findings retest (PR #5): #20 and #21 were dispositioned there as "re-estimated by #44" and
"already retested locally". The project owner asked for those two specifically, so this document
tests the part those rows did **not** answer: can the event itself be forecast, out of time, from
information known at entry?

## Why these two

- **#21 liquidation spikes reverse.** The published test and the local replication both judge the
  average reversal. Neither asks whether the cross-section of spikes is forecastable: do bigger
  spikes, larger forced moves or one side reverse more? The audit says the sealed months are
  exhausted for the *average*; this is a different question on the same event file.
- **#20 new 4-hour lows bounce.** The published test and #44 re-estimate the average bounce. The
  forecast question is whether the events that bounce more can be identified before entry from the
  coin's own price/volatility state and the market context. #45 found that volatility and break
  depth carry the forecast for the forced-liquidation bounce; this asks the same of the price-only
  trigger.

Neither test re-tunes the original rule, and neither is a new sample. They are forecast tests on the
published event-level files.

## Data — fixed

- **#21 events**: `data_raw/events/liqspike_events.csv`, 1,240 spikes (631 long, 609 short) on 119
  days, 2026-07-01 → 2026-10-28, 14 coins. Columns: `side`, `usd`, `share`, `r0` (the spike hour's
  return), `r4`, `r24`.
- **#20 events**: `data_raw/events/lows_events.csv.gz`, the 136,523 down-breaks on 2,055 days,
  2020-01-03 → 2026-03-30. Columns: `ts`, `day`, `coin`, `r15`, `r60`, `r240`.
- **Panel features for #20**: `data_raw/panel/` daily close/volume, 42 coins. All features are read
  from the **previous day's close** (a one-day shift), so the event bar is not used.
- **Baselines for #21**: the local replication's published constants in `research/liqspike_run.json`
  — 24 h +23.886 bps, 4 h +4.112 bps. They are fixed, not recomputed.
- No data is fetched; no forward window is read.

## Splits — fixed

| test | design | validation |
|---|---|---|
| #21 | 2026-07-01 → 2026-08-31 | 2026-09-01 → 2026-10-28 |
| #20 | 2021-10-27 → 2023-12-31 | 2024-01-01 → 2026-03-30 |

#20's design starts at the panel's first date; its 2020-2021 events have no panel features and are
dropped, not imputed. The validation window is the verdict; design numbers are information only.

## Signals and targets — fixed

### #21

- **Primary signal**: `share` — the liquidation share of the spike hour. Hypothesis: a larger forced
  share reverses more.
- **Secondary signals**: `abs_r0` (the size of the forced move), `log_usd` (spike dollars), `side`
  (long = 1, short = 0).
- **Primary target**: signed 24-hour excess, `(r24 − 0.0023886) × (+1 long, −1 short)`. Positive is a
  reversal. 4 h is secondary with its own baseline `(r4 − 0.0004112)`.
- **Primary endpoint**: rank IC of `share` with the 24 h signed excess on validation; a forecast
  requires IC > 0, its 95% day-block CI excludes 0, and the top quintile's mean exceeds the
  all-event mean.

### #20

- **Primary signal**: `vol_30` — the coin's 30-day realised volatility at the previous close.
  Hypothesis: higher-volatility coins bounce more.
- **Secondary signals**: `ret_1`, `ret_5`, `ret_20` (the coin's prior returns), `vol_z` (log volume
  z over 30 days), `mkt_ret_1` (the cross-sectional mean prior-day return), `btc_ret_1`.
- **Target**: the 1-hour long return `r60` (primary); `r240` (4 h) secondary. Both are raw long
  returns from the event's next open, as the published file defines them.
- **Primary endpoint**: rank IC of `vol_30` with `r60` on validation; same three conditions.
- **Data filter**: observations with |target| > 50% are dropped as data errors (ticker/price
  artifacts), as in the remaining-findings retest.

## Statistics — fixed

- Rank IC is computed **per UTC day across events** (days with fewer than five events are dropped),
  then averaged; 95% CI from 1,000 day-block bootstrap resamples; Newey-West t with one lag.
- Top quintile is the top 20% of the signal across all validation events; the comparison is its mean
  target minus the all-event mean; 95% day-block CI. A 9 bps round trip is charged in the reported
  net, not in the IC.
- **Multiplicity**: BH at 5% across the two primary tests. Secondary signals and horizons are
  information only and cannot change a verdict.

## Outcomes — fixed now

- #21 gets FORECASTS / WEAK FORECAST / NO FORECAST for the spike-size signal. The original FAIL
  stands regardless; this only says whether the cross-section is forecastable.
- #20 gets the same for prior volatility. The #44 trade-weighted re-estimate stands regardless.
- A positive IC without a top-quintile improvement is WEAK; an IC whose CI includes 0 is NO FORECAST.
- No new trade, ledger row, forward test or order follows from either result.

## What would void this retest

- Changing the split, the primary signal, the target or the three conditions after seeing a
  validation number.
- Reading a forward window or substituting the design window for validation.
- Calling a secondary signal or the 4 h horizon a finding.
