# Pre-registration — retest #45: do price, flow and signal features forecast the forced-liquidation bounce?

Written **before the 2024-04-01 → 2024-10-14 validation window is scored**. It is a retest of the
trade behind #45/E1, not a new forward test: #45's own verdict date and rule stay unchanged. The
question here is narrower and different from #45's: given a forced down-break, can a small set of
pre-entry features forecast its return better than the unconditional trade?

## Why

#26/#44/#45 established that buying forced-liquidation down-breaks has a positive in-sample mean at
4 h–1 day. The forward plan prices that mean net of 9 bps and funding, but it does not ask whether the
**cross-section of events** is forecastable. The request that opened this ticket asked for exactly
that: retest the #45 findings not only on funding and fees, but on prices, movement, ticks, tape and
signals, for better forecasts of trades and future trades, using the history available on present
coins and the stock market.

The risk is the usual one: with 28k events and a dozen candidate features, a model can always find an
in-sample story. This document fixes the model, the split and the one primary endpoint before the
validation window is read. A null result is a valid outcome.

## Data — fixed

- **Events.** The #26 replication's continuous event set: 26 COIN-M coins, 2023-06-26 → 2024-10-14,
  Binance USDⓈ-M 5-minute bars (`data_raw/lows/`), COIN-M order fills as liquidations
  (`data_raw/liq2/`). The #26/#45 rule exactly:
  - 5-minute break of the prior 48-bar high/low, volume z ≥ 2 on log volume, burst in the break
    direction;
  - one event per coin per direction per hour;
  - entries only for break bars closing 01:00–24:00 UTC;
  - the #26 day filter (drop the first three days and the last day of each month), and days with
    fewer than 6 events.
  - 28,029 events over 427 days before tagging.
- **Tag.** Prior-observed-day forced tag, as E1: today's forced share `s` (liquidation USD on the
  break's side in the hour before / that hour's quote volume) is compared with the previous observed
  event day's terciles across all coins. Today's own distribution is not used. A day without a
  previous observed day is `middle` and is not traded. The trade is the **forced down-break**, bought
  long.
- **Prices.** Entry at the open of the bar after the break close; exits at the close of the bar
  ending at entry + 4 h / 12 h / 1 day. A missing bar drops that event/horizon.
- **Cost and funding.** 9 bps round trip (E1's cost) plus the sign-adjusted sum of Binance settled
  funding rates in (entry, exit]. Net is the primary target; gross is secondary.
- **Cut.** Nothing after 2024-10-14 in the continuous sample. The monthly cross-check stops at
  2026-10-03; the #45 forward window (from 2026-10-30) is not read.

## Split — fixed

- **Design/train:** events with close date **2023-06-26 → 2024-03-31**: 3,598 forced down events over
  243 days.
- **Validation:** events with close date **2024-04-01 → 2024-10-14**: 2,541 forced down events over
  167 days.
- No event is in both. Features are measured at the break bar only; targets start after the entry
  bar. The validation window overlaps #26's in-sample window; that is disclosed below. It is
  out-of-sample for the forecast model, not for the existence of the bounce.

## Features — fixed

All at the break bar, before entry:

| layer | feature | definition |
|---|---|---|
| liquidation | `s` | forced share, as above |
| liquidation | `liq_count` | number of liquidation prints in the hour before the close |
| tape | `taker_imb` | `2 · taker_buy_quote / quote_volume − 1` over the break bar |
| tape | `vol_z` | volume z-score over the prior 4 h (the event condition itself) |
| movement | `ret_1h` | log close / close 12 bars earlier |
| movement | `atr_pct` | 14-bar ATR / entry price |
| signal | `funding_ann` | last settled funding rate ≤ close, annualised (8 h interval) |
| signal | `btc_ret_1h` | BTC's 1 h log return over the same clock time |

No feature uses a bar after the break bar. `s` and `liq_count` use prints strictly before the break
close. `funding_ann` uses only rates already settled.

## Forecasts — fixed

**F1 (primary): equal-weight percentile composite.** For each feature, map the validation value
through the **training** empirical CDF. The score is the mean of:
- `s` percentile,
- `atr_pct` percentile,
- `−ret_1h` percentile (a deeper break scores higher).

The three layers were chosen on design data: they have the strongest design rank ICs (`s` 0.105,
`atr_pct` 0.209, `−ret_1h` 0.201). Equal weights leave no fitted coefficients.

**F1+T (secondary):** add the `taker_imb` percentile as a fourth equal component. It tests whether
tape flow adds anything to the three-layer score.

**F2 (secondary): ridge regression.** Standardise the eight features on train; ridge with λ = 10,
intercept unpenalised; target 4 h net. No hyperparameter search.

**Layer read-outs:** each feature's training-CDF percentile, scored alone on validation (rank IC and
top-quintile mean), to show which layers carry the forecast.

## Metrics and primary endpoint — fixed

- **Primary:** rank IC (Spearman) of F1 with 4 h net return on the validation window. A finding
  requires the IC to be > 0 with a **95% day-block bootstrap CI excluding 0** (1,000 resamples of
  UTC days, all events of a day kept together) and the top-quintile mean net to exceed the
  all-event mean. A positive IC without the top-quintile improvement is not a usable forecast.
- **Secondary, reported with the same CIs:** 12 h and 1 d IC; top-quintile mean net at each horizon;
  hit rate and AUC for net > 0; calibration by score quintile (predicted score vs realised net).
- **No promotion:** if F1 fails and F1+T or F2 passes, that is reported as a secondary model, not as
  a new primary. The primary endpoint is not moved.
- **Multiplicity:** three horizons are reported; only 4 h is the primary. No secondary horizon is
  called a finding unless its CI excludes 0 and it survives Holm across the three horizons at
  family α = 0.05. The layer read-outs are descriptive.
- Top-quintile threshold is the **training** 80th percentile of the score; the validation quantile is
  never used to choose the threshold.

## Cross-checks — fixed

1. **Monthly archive, 2020-01 → 2026-10** (`data_raw/liq/`): 39 coins, three days at the start of
   each month, multi-venue liquidations. This is not the #26 day sample: #26 deliberately drops the
   first three days of each month, and the archive has no continuous post-2024 history. It is a
   breadth check, not a confirmation. Train the same F1 CDFs on 2020-01 → 2023-12 and score
   2024-01 → 2026-10; report IC and top-quintile net, labelled exploratory. The month-start bias and
   the sparse days are stated beside the numbers.
2. **Stock-market analog, daily:** SPY, QQQ and IWM (`data_raw/trend/`, 2016-10 → 2026-10). Event =
   close below the prior 20-day low with volume z ≥ 2. Target = next 5-day close/close return.
   Features = 1 d / 5 d / 20 d returns, ATR, volume z, range, close location, TLT and GLD 1 d
   returns. Train 2016-10 → 2022-12, validate 2023-01 → 2026-10, ridge and a simple percentile
   composite. This is a **cross-market analog**, not a #45 replication: equities have no equivalent
   forced-liquidation feed. Its purpose is to say whether a generic down-break + volume reversal
   exists outside crypto.

## Outcomes — fixed

- **F1 primary passes:** the forced-liquidation bounce is forecastable out-of-time by a fixed
  three-layer score; report the gain per trade and the layer contributions. It is still an in-sample
  window for #45, so this is a forecast result, not an authorisation to trade.
- **F1 primary fails:** no better forecast than the unconditional trade on this history. Report the
  null; do not re-tune on validation. The #45 forward test remains the only clean test of the trade.
- Secondary models are reported regardless of the primary outcome.

## Transparency — what has been seen before this

- #26/#44/#45's published in-sample numbers, including the forced-tag D and the 4 h–1 d bounce.
- The continuous event set's **design** window: counts, unconditional means and per-feature design
  ICs. The design 4 h net mean is +37.1 bps (trade-weighted) / +51.9 bps (day mean, t 7.16); the
  three chosen features lead the design IC table. This is why F1 is fixed as above.
- The monthly archive's event counts by year and its unconditional means by year were inspected
  while assembling the data. Those numbers are therefore **not** a clean out-of-sample test; the
  monthly cross-check is reported as exploratory.
- The 2024-04-01 → 2024-10-14 validation outcomes, feature ICs and any model score have **not** been
  read. The validation is scored once, after this document is committed.
- #45's forward window has no events in the local data (it starts 2026-10-30); no forward outcome is
  used.

## What would void it

- Changing the event rule, split, feature list, F1 weights, cost or primary endpoint after the
  validation is scored.
- Using the validation quantile to set the top-quintile threshold.
- Reporting a secondary model as if it were the pre-registered primary.
- Filling a missing bar or funding rate from a later source.

## Limits, stated now

- Continuous liquidation history ends 2024-10-14. Post-2024 is monthly samples, not a continuous
  series; there is no clean post-2024 continuous OOS here.
- The validation window is inside #26's discovery window. The bounce itself is in-sample; only the
  forecast model is out-of-time.
- Tape is proxied by 5-minute taker-buy quote and volume. True tick/tape data in this repo is one
  day per month; it cannot support a multi-month forecast test. The existing seconds-level tape study
  is cited, not re-run.
- COIN-M liquidations are one venue family; #45's forward feed is multi-venue. The monthly archive is
  multi-venue but starts every month.
- Costs are a flat 9 bps and Binance funding, not the venue-specific execution model of #45.
