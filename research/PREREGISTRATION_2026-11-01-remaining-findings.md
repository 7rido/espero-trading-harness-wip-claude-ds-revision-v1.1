# Pre-registration — retest the remaining audit findings

Written **before any validation-window statistic in this document is computed**. It retests the
audit rows other than #45, on the local record, as forecasts first and trades second. #45 was
retested separately (PR #4); this document does not read its forward window or any other forward
window.

## Why

The audit ([AUDIT_BY_NUMBER.md](AUDIT_BY_NUMBER.md)) gives 46 ids: #1-#45 plus #9b. The first retest
covered #45's forced-liquidation trade. The request that opened this ticket asked for **the other
findings as well**, on prices, movement, ticks, tape and signals, not only on funding and fees, and
for **better forecasts on trades and future trades**, not only for a tradeable edge.

Most rows are not open questions: some were retested locally, some were re-estimated by the
day-mean audit (#44), ten are running forward tests, and a few have no data. The rows that are still
open, have a stated estimator/forecast defect, and have local data are retested here. Every one of
the 45 rows gets a disposition in the result, so "not retested" is a finding with a reason, not a
silence.

## Rows fresh-tested here — six

| id | finding | the audit's defect | what this retest changes |
|---|---|---|---|
| #1 | funding extremes | selection examined before holdout; venue-specific z | robust, causal z; out-of-time forecast |
| #4 | cross-asset TSMOM | passed on a 0.06 Sharpe margin with no significance test | deflated Sharpe vs an exposure-matched benchmark; alpha t |
| #8 | multi-factor XS | criterion 4 met by an overlapping-label IC while the Q5-Q1 spread is negative | non-overlapping IC **and** a spread hurdle; alphabetical control |
| #9b | BTC lead-lag | IC t inflated ~2× by overlapping hourly labels | non-overlapping + Newey-West; economic spread |
| #15 | multi-asset trend | criteria 2-3 met by lower exposure | exposure-matched benchmark; NW t of the difference |
| #43 | horizon map | CONFIRMED at t 2.12 against its own deflated bar of 4.09, trade-weighted −9.6 bps | trade-weighted, day-clustered, against the printed deflated bar |

They are the open estimator/forecast rows. The other 39 are dispositioned in the result with their
evidence.

## Data — fixed

No data is fetched. No forward or sealed window is read.

- **Daily panel**: `data_raw/panel/` — 42 coins, 2021-10-27 → 2026-10-27, open/high/low/close/volume.
- **Hourly panel**: `data_raw/panel_hourly/` — 39 coins, 2025-10-27 → 2026-10-27; and
  `data_raw/panel_peers/` — 39 coins, 2024-10-27 → 2025-10-26, used only if #16/#17 are revisited.
- **Trend series**: `data_raw/trend/` — 56 daily Yahoo series, 2016-10 → 2026-10. Equity ETFs use
  `adj_close`; crypto uses `close`.
- **Funding**: `data_raw/settle/funding/*.json` — settled Binance rates, 2019-12 → 2026-10.
- **Event artifacts**: `data_raw/events/` — the original repository's event-level outputs
  (`lows_events.csv.gz`, `horizons_s1_12h_trades.csv.gz`, `horizons_cells.csv`). They are read-only
  data, not code.

## Splits — fixed

| test | design | validation |
|---|---|---|
| #1, daily panel | 2021-10-27 → 2023-12-31 | 2024-01-01 → 2026-10-27 |
| #4 TSMOM | 2016-10-31 → 2020-12-31 | 2021-01-01 → 2026-10-28 |
| #8 multi-factor | 2021-10-27 → 2024-06-30 | 2024-07-01 → 2026-10-27 |
| #9b lead-lag | 2025-10-27 → 2026-04-30 | 2026-05-01 → 2026-10-27 |
| #15 trend | 2016-10-31 → 2020-12-31 | 2021-01-01 → 2026-10-28 |
| #43 horizon | no split; event files as published | — |

The validation window is the verdict window. Design-window numbers are reported only to show the
signal existed before; they cannot rescue a validation failure.

## Eligibility — fixed

- **Daily cross-section**: at least 30 daily closes and trailing 30-day mean dollar volume
  (`close × volume`) ≥ $1,000,000. #8 uses the original's stricter 365 closes.
- **Hourly cross-section**: at least 720 hourly closes and trailing 168-hour mean dollar volume
  ≥ $50,000 per hour. BTC is the leader and is excluded from the #9b cross-section.
- **#4**: SPY, TLT, GLD, USO, BTC-USD, ETH-USD; an asset enters on a rebalance only with 252 daily
  closes.
- **#15**: SPY, QQQ, IWM, EFA, EEM, TLT, IEF, GLD, SLV, USO, UNG, DBA, CPER, BTC-USD, ETH-USD,
  SOL-USD; an asset enters with 252 daily closes.
- No survivorship correction; the coin list is October 2026's. Disclosed.

## Signals and targets — fixed

### #1 funding extremes

- Funding per coin-day: the sum of settled rates in the UTC day, annualised on the 8-hour interval.
- Signal: causal robust z over the trailing 30 settled days,
  `z = (r − median_30) / (1.4826 × MAD_30)`; the score is `−z`, so extremely negative funding
  scores highest.
- Target: next day's open → close 1 day later; 3 days secondary.
- Primary: cross-sectional rank IC across coins on each validation day, top quintile of `−z` vs all
  events. Time-series pooled IC (all coin-days) is information only.
- **Forecast** if validation IC > 0, its 95% day-block CI excludes 0, and the top-quintile mean
  exceeds the all-event mean. **Tradeable** only if the top-quintile mean net of 9 bps is > 0.

### #4 cross-asset TSMOM

- Monthly at the last trading day's close; signal = 252-trading-day total return; long if > 0,
  equal weight across longs capped at 1/6 each, remainder cash; execute the next month's first
  trading day open; 10 bps per side.
- Benchmark: equal-weight buy-and-hold of the same eligible universe, monthly, same costs.
- Exposure-matched benchmark: the benchmark's daily returns scaled to the TSMOM book's realised
  volatility over validation.
- Metrics: CAGR, Sharpe, max drawdown, turnover; deflated Sharpe with N = 4 trials (the fourth
  hypothesis in the original corpus); alpha and its Newey-West t from a regression of TSMOM monthly
  returns on the benchmark's.
- Forecast: pooled rank IC of the 252-day return with the next month's return across asset-months.
- **Pass** only if validation Sharpe > exposure-matched benchmark Sharpe **and** alpha NW t ≥ 2.
  The original's three criteria are reported beside it, not substituted for it.

### #8 multi-factor cross-sectional

- Signals: `mom_30` (30-day return ending 1 day ago), `rev_3` (−3-day return), `lowvol_30`
  (−30-day realised volatility). Each is MAD-winsorised at k = 3, cross-sectionally percentile-ranked,
  and the three ranks are averaged with equal weights. No fitting.
- Weekly: decide at the Sunday close, enter at Monday's open, target the next 5 trading days' return.
- Primary: rank IC on **non-overlapping** weekly observations, Newey-West t (4 lags), Q5-Q1 spread
  net of 9 bps, 95% day-block CI.
- Alphabetical control: the same ranks assigned alphabetically (no signal), measured with the same
  IC and spread, to show what construction alone produces.
- **Forecast** if validation IC > 0, CI excludes 0, **and** the Q5-Q1 net spread is > 0. A positive
  IC with a non-positive spread is not a pass — the audit's defect.

### #9b BTC lead-lag

- Hourly, 2025-10-27 → 2026-10-27; 38 coins, BTC excluded from the cross-section.
- `beta_i` = trailing 168-hour covariance of coin and BTC returns / BTC variance, causal.
- Primary signal: `leadlag_beta_1h = beta_i × BTC 1-hour return`. Controls: raw BTC 1-hour return,
  `rev_1` (− coin's 1-hour return).
- Target: next 3 hours (enter at the next hour's open, exit at the close 3 hours later).
- Primary: rank IC on a **non-overlapping** 3-hour sample and Newey-West t (4 lags) on the hourly IC
  series; Q5-Q1 spread net of 9 bps.
- **Forecast** if validation IC > 0 and the non-overlapping CI excludes 0. **Tradeable** only if the
  net spread exceeds 9 bps.

### #15 multi-asset trend

- Weekly at the close; trend score = mean of the signs of the 1-, 3- and 12-month returns; long if
  the score > 0, flat otherwise.
- Position size = 20% / annualised 30-day volatility, capped at 2×, gross capped at 100%; equal
  risk budget across assets; 10 bps per side.
- Benchmark: the same sizing and costs, always in (vol-only). Exposure-matched: vol-only scaled to
  the trend book's realised volatility.
- Primary: weekly return difference (trend − vol-only), Newey-West t (4 lags). **Adds return** only
  if the mean difference > 0 and NW t ≥ 2.
- Forecast: pooled rank IC of the trend score with the next week's return.

### #43 horizon map

- S1 = #20's new-low bounce. 1-hour and 4-hour event returns from `lows_events.csv.gz` (`r60`,
  `r240`); 12-hour net returns from `horizons_s1_12h_trades.csv.gz` (`net`).
- Trade-weighted mean across events and day-clustered t; day-mean reported beside it.
- The original printed a deflated bar of **4.09** for its best cell. The 12-hour confirmation stands
  only if the trade-weighted mean is > 0 **and** its day-clustered t ≥ 4.09 on the same trades.
- This re-evaluates the published event file; it is not a new sample and cannot create new evidence.

## Statistics — fixed

- **Rank IC**: Spearman per date; mean across dates; 95% CI from 1,000 day-block bootstrap
  resamples (all cross-sections of a date kept together); Newey-West t with lags = max(1, h − 1)
  on the date series.
- **Spread**: top quintile mean minus bottom quintile mean in bps, net of 9 bps; day-block CI.
  Where a quantile has fewer than two coins it is dropped.
- **Hit rate**: share of dates with positive IC; top-quintile positive share.
- **Multiplicity**: Benjamini-Hochberg FDR 5% across the six primary tests; q-values reported. A
  finding is a forecast only if its CI excludes 0 and it survives BH.
- **No promotion**: secondary horizons, controls and layer read-outs are information only.

## Outcomes — fixed now

- Each of the six gets one of: **FORECASTS** (IC and spread), **WEAK FORECAST** (IC only),
  **NO FORECAST**, or **FAIL / NO VERDICT** for the two portfolio tests (#4, #15).
- A positive IC with no economic spread is written as "forecast, not tradeable". It is not an edge.
- The result lists all 45 remaining ids with a disposition and its evidence. A row that was already
  retested, is running, or has no data is not re-run; it is named.

## What would void this retest

- Changing a signal, a split, a horizon or a criterion after seeing a validation number.
- Reading any forward-window day, or any sealed holdout.
- Substituting the design window for the validation window.
- Calling a secondary horizon or a control a finding.

## Amendment 2026-11-01 — before the verdict is written

The first execution of the daily cross-section showed the ticker collisions already documented in
`reference/ERRATA.md`: the Yahoo `ARB-USD`, `TIA-USD`, `WLD-USD` and `OP-USD` histories switch
tokens mid-series, and 21 forward returns in the panel exceed ±100% (up to +680,000%). These are
data errors, not market moves.

For **#1 and #8 only**, and before any verdict is read or written, this amendment:

- drops the four collision tickers from the daily cross-section;
- drops any observation whose forward return is outside ±50%.

No split, signal, horizon, criterion or estimator changes. The filter is data quality, disclosed
here rather than applied silently. #4, #9b, #15 and #43 are unaffected (their series do not contain
those tickers in the tested windows).
