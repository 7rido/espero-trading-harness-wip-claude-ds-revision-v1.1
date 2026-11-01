# Result — retest the remaining audit findings

**Bottom line:** six open audit rows were retested out of time as forecasts first and trades second.
**None is a tradeable forecast.** #9b is the only one with a statistically significant validation
rank IC, and its 4.0 bps spread is below the 9 bps cost — the original FAIL stands. **#4's thin TSMOM
pass does not survive a significance test** (alpha t 1.10), and **#43's CONFIRMED 12-hour horizon does
not survive its own deflated bar** (trade-weighted −9.6 bps, t −0.97 against 4.09). #1, #8 and #15 do
not forecast out of time. The other 39 rows are already retested, running, clean fails, or untestable;
each is named below with its evidence.

Registration: [PREREGISTRATION_2026-11-01-remaining-findings.md](PREREGISTRATION_2026-11-01-remaining-findings.md)
· code: [`remaining_forecasts.py`](remaining_forecasts.py) · numbers:
[`remaining_forecasts.json`](remaining_forecasts.json) · tests:
[`tests/test_remaining_forecasts.py`](../tests/test_remaining_forecasts.py).

**Owner follow-up:** #20 and #21 were asked for by name after this retest. They are retested
separately in [RESULTS_2026-11-01-lows21-forecast.md](RESULTS_2026-11-01-lows21-forecast.md): #21's
spike cross-section is not forecastable; #20's bounce is forecastable by prior volatility (IC 0.028,
t 5.03) but the top-vs-all spread is 1.1 bps, below the 9 bps cost. The original verdicts stand.

## The six fresh retests

| id | finding | validation statistic | verdict |
|---|---|---|---|
| #1 | funding extremes | rank IC **+0.011** (−0.000 … +0.023), t 1.75, q 0.155; top +4.9 bps | **NO FORECAST** |
| #4 | cross-asset TSMOM | Sharpe **0.89** vs 0.85 exposure-matched; alpha t **1.10** | **FAIL** (nominal pass, not significant) |
| #8 | multi-factor XS | rank IC **+0.043** (−0.004 … +0.098), t 1.63; Q5−Q1 +11.2 bps | **NO FORECAST** (construction untouched) |
| #9b | BTC lead-lag | rank IC **+0.035** (0.022 … 0.048), t 5.30; spread **+4.0 bps** | **WEAK FORECAST** (sub-cost) |
| #15 | multi-asset trend | diff **−11.2 bps/wk**, t −1.79 vs vol-only | **NO RETURN BEYOND VOL** |
| #43 | horizon map | 12 h **−9.6 bps**, t −0.97 against the printed deflated bar 4.09 | **CONFIRMED DOES NOT SURVIVE** |

The six primary p-values were Benjamini-Hochberg corrected together; the smallest q is #9b's 6.9e-7,
then #1/#8/#15 at 0.155 and #4/#43 at 0.33. A q-value below 0.05 is not enough on its own: the
spread must also clear cost, which is why #9b is "forecast, not tradeable" rather than a finding.

## #1 — funding extremes

- **Data.** 41 funding series (38 after the collision filter), daily Binance settled funding, validation 2024-01-01 → 2026-10-27 (1,030 days).
  Signal: causal 30-day robust funding z; score is **−z**, so extreme negative funding ranks highest.
- **Validation.** rank IC +0.0111 (95% day-block −0.0002 … +0.0234), Newey-West t 1.75, p 0.079,
  q 0.155; IC was positive on 51.8% of days. Top quintile +4.9 bps vs all events +2.4 bps; spread
  +2.6 bps (−4.4 … +9.8), **−6.4 bps after 9 bps cost**.
- **Design.** The same signal had IC +0.0172 (0.0021 … 0.0316), t 2.37 in 2021-10 → 2023-12. It did
  not replicate out of time. That is the same "the first window looked better" pattern the original
  document warned about.
- **Verdict.** NO FORECAST; the audit's FAIL stands. A positive design-window IC is not a finding.

## #4 — cross-asset TSMOM

- **Data.** SPY, TLT, GLD, USO, BTC-USD, ETH-USD; monthly, 252-trading-day lookback, 10 bps a side;
  validation 2021-01 → 2026-10, 70 months.
- **Portfolio.** CAGR +14.8%, Sharpe **0.888**, max drawdown −20.2%; benchmark Sharpe 0.847,
  drawdown −32.9%. The three original criteria still pass on this implementation.
- **The missing test.** Monthly alpha over the benchmark is +0.34% with a Newey-West t of **1.10**.
  The deflated Sharpe for four trials is 0.961, so the **absolute** Sharpe survives deflation; what
  does not survive is the claimed improvement over the benchmark. The 0.04 Sharpe margin is not
  distinguishable from zero. Under the audit's standard — significance of the claimed improvement,
  not a point estimate — this is **FAIL**.
- **Forecast.** Pooled asset-month IC +0.071 (−0.060 … +0.196), t 1.26: no cross-sectional forecast.
- **Verdict.** FAIL. The nominal pass is real; the evidence that it is not luck is not.

## #8 — multi-factor cross-sectional

- **Data.** 42 coins, 38 eligible on the validation dates; weekly Sunday close, Monday open, 5-day
  target; composite of `mom_30`, `rev_3` and `lowvol_30`, equal-weight percentile ranks, no fitting.
- **Validation.** 120 weeks, 2024-07 → 2026-10: rank IC **+0.0434** (95% day-block −0.0040 …
  +0.0976), t 1.63, p 0.104, q 0.155; IC positive on 53.3% of weeks. Q5−Q1 **+11.2 bps** (−65.8 …
  +98.3), +2.2 bps after 9 bps cost. The spread is positive but its interval is enormous.
- **Design.** IC +0.0541 (0.0062 … 0.1078), t 2.09. The validation interval includes zero, so the
  out-of-time claim is not met.
- **Alphabetical control.** The same construction with alphabetical ranks: IC −0.021 (−0.048 …
  +0.007), spread −20.5 bps. Construction alone does not forecast; nor does the composite out of time.
- **Verdict.** NO FORECAST. The audit's point stands: the original's criterion-4 t was inflated by
  overlapping 5-day labels. The portfolio construction result (criteria 1–3) is **not** re-run here;
  it is not contradicted, only the selection claim is.

## #9b — BTC lead-lag

- **Data.** 39 coins, 8,756 hourly bars, 2025-10 → 2026-10; beta over trailing 168 hours; signal
  `beta × r_BTC − r_i`; target the next 3 hours from the next open.
- **Validation.** 1,433 non-overlapping 3-hour observations: rank IC **+0.0355** (95% day-block
  0.0224 … 0.0485), t 5.30; Newey-West t on the hourly series 8.32; p 1.2e-7, q 6.9e-7; hit 54.4%.
- **The money.** Q5−Q1 **+4.0 bps** (−1.3 … +9.3), **−5.0 bps after the 9 bps round trip**; top
  quintile +5.7 bps. The published +3.7 bps is reproduced almost exactly.
- **The control.** `leadlag_1h` and `rev_1` print identical statistics (IC 0.0368, spread 4.1 bps),
  and the beta term is slightly *below* plain reversal. The mechanism still subtracts information.
- **Verdict.** WEAK FORECAST: the IC is real and survives the overlap correction, but the spread does
  not pay the cost. The original FAIL stands, and for the same reason.

## #15 — multi-asset trend

- **Data.** 16 assets (5 equity, 2 bond, 6 commodity ETFs plus BTC/ETH/SOL), weekly, 1/3/12-month
  trend, vol-sized, 10 bps a side; validation 2021-01 → 2026-10, 305 weeks.
- **Portfolio.** Trend Sharpe **0.629**, CAGR +8.1%; vol-only benchmark Sharpe **1.050**, CAGR
  +11.4%. At matched risk the trend book returns **−11.2 bps a week** (t −1.79) less.
- **Forecast.** Pooled asset-week IC +0.019 (−0.018 … +0.057), t 1.05: no.
- **Verdict.** NO RETURN BEYOND VOL SIZING; the audit's FAIL stands. The original's drawdown
  protection is not disputed; it is not a return edge.

## #43 — horizon map

- **Data.** #20's published event file: 136,522 down-breaks over 2,055 days for 1 h/4 h; 6,310
  holdout trades over 599 days for 12 h; selection 12,516 trades over 1,636 days.
- **1 h / 4 h.** Trade-weighted **+5.9 bps (t 3.50)** and **+9.4 bps (t 2.98)**; the day-means are
  +14.8 and +37.8. The 1 h shrink is #44's.
- **12 h, holdout.** Trade-weighted **−9.6 bps (t −0.97)** against a day-mean of +21.8 (t 2.12).
  Selection trade-weighted +13.1 (t 2.01).
- **The bar.** The study printed a deflated bar of **4.09** for its best cell. The 12-hour
  confirmation is at t 2.12 as a day-mean and −0.97 trade-weighted. It does not survive its own bar.
- **Verdict.** CONFIRMED DOES NOT SURVIVE; FAIL. This is a re-estimate of the published file, not
  new data, and it reproduces #44's −9.6 bps exactly.

## Every remaining id

| id | finding | audit rescore | disposition | evidence |
|---|---|---|---|---|
| 1 | funding extremes | FAIL | fresh: no out-of-time forecast | this document |
| 2 | XS momentum top-1 | FAIL | already retested locally | `RESULTS_2026-10-30-xs-momentum.md`: holdout +27.8%/yr, CI −36.4…+92.5, t 0.75 |
| 3 | Polymarket LP | FAIL | not retestable | no venue reward/statement data; accounting cannot be re-derived |
| 4 | TSMOM | UNRESOLVED | fresh: FAIL | alpha t 1.10; nominal pass not significant |
| 5 | PEAD | FAIL | not retestable | no earnings/announcement data |
| 6 | crypto-policy odds | FAIL | not retestable | no event/odds dataset; design period empty |
| 7 | XS20 top-5 | EXPLORATORY | already retested locally | same XS run as #2; holdout fail |
| 8 | multi-factor XS | CONSTRUCTION | fresh: no selection forecast | IC t 1.63, CI includes 0; construction not re-run |
| 9 | BTC lead-lag | FAIL | not retestable as written | criterion impossible; #9b is the corrected version |
| 9b | lead-lag beta | FAIL | fresh: weak forecast, sub-cost | IC 0.035, spread 4.0 bps < 9 bps |
| 10 | degen 5m | FAIL | not re-run | clock/forward-half process fix; not a forecast test |
| 11 | carry taker | FAIL | already retested locally | `RESULTS_2026-10-30-carry-deep.md`: #11 ablation +5.2%/yr, Sharpe 0.88 |
| 12 | carry maker | VENUE-DEPENDENT | already retested locally | same document: #12 +10.9%/yr, provisional; venue/fill limits |
| 13 | degen 1h | FAIL | not re-run | forward half never run; process fix |
| 14 | carry Kraken | FAIL | not re-run | 6 trades; MDE unstated; original run fails |
| 15 | multi-asset trend | FAIL | fresh: no return beyond vol | diff −11.2 bps/wk, t −1.79 |
| 16 | peer baskets | FAIL | clean fail, no remedy | original pre-registered holdout fail; no estimator defect |
| 17 | ETH leads ecosystem | FAIL | clean fail, no remedy | same |
| 18 | liquidation sort | FAIL | re-estimated by #44 | leg +22.9 bps t 2.98; D −14.4 t −2.68 |
| 19 | settlement moves prices | REAL-NOT-TRADABLE | re-estimated by #44 | +15.0 bps t 3.15 |
| 20 | new 4h lows bounce | REAL-NOT-TRADABLE | #44 re-estimate + follow-up forecast | +5.9 bps t 3.50 (0.40× published); prior volatility IC 0.028, spread 1.1 bps < 9 bps |
| 21 | liquidation spikes | FAIL | local replication + follow-up forecast | `RESULTS_2026-10-30-liqspike.md`: trade-weighted −19.7 bps t −0.67; spike size IC 0.05, CI includes 0 |
| 22 | forward: spike decay | RUNNING | not judged | window to 2027-03-31; not read |
| 23 | forward: spike short | RUNNING | not judged | same |
| 24 | forward: low bounce | RUNNING | not judged | same |
| 25 | OI-drop breakdowns | FAIL | re-estimated by #44 | +6.1 bps t 2.40; D +3.3 t 1.93 |
| 26 | forced liquidations | HOLDS | already retested locally | `RESULTS_2026-10-30-liq26-replication.md`: D −20.3 t −5.13; prior-day 4h +32.0 t 4.01 |
| 27 | forward: #26 live | RUNNING | not judged | window to 2027-03-31; not read |
| 28 | leveraged ETFs | FAIL | clean fail / #44 | −1.5 bps t −1.44, unchanged |
| 29 | forward: post-close | RUNNING | not judged | window; not read |
| 30 | resting bids | FAIL | re-estimated by #44 | −3.6 bps t −1.65; sign flips |
| 31 | forward: 2-ATR bids | RUNNING | not judged | window; not read |
| 32 | forward: funding split | RUNNING | not judged | window; not read |
| 33 | fill cost at 00:00 | FAIL | re-estimated by #44 | −20.1 bps t −0.77; the t collapses |
| 34 | 2x funds push alts | RUNNING | not judged | window; not read |
| 35 | stop runs reverse | FAIL | re-estimated by #44 | +2.1 bps t 0.79; the "reversal" does not survive |
| 36 | Ethena flows | FAIL | not re-run | one week dropped; process fix; original fail |
| 37 | hourly crowd vs RW | FAIL | re-estimated by #44 | $0.012 a share t 1.34; the paired Brier interval is not run |
| 38 | forward: shorts pay | RUNNING | not judged | window; not read |
| 39 | markout measurement | NOT-A-TEST | measurement | cost reference (#39) |
| 40 | testnet reconciliation | PLUMBING | not a hypothesis | procedure test |
| 41 | markout, thin coins | NOT-A-TEST | measurement | cost reference (#41) |
| 42 | rehearsal | PLUMBING | not a hypothesis | procedure test |
| 43 | horizon map | CONFIRMED-WEAK | fresh: does not survive | 12 h −9.6 bps, t −0.97 against 4.09 |
| 44 | day-mean audit | NOT-A-TEST | audit | the standard the retests use |
| 45 | forward: #26 holds 4h–1d | RUNNING | retested separately | PR #4: forecast IC 0.179, top-quintile CI −70…+129 bps; forward window not read |

Counts: 6 fresh, 6 local retests, 8 re-estimated by #44, 3 clean fails (#16, #17, #28), 9 running,
8 without data or needing a process fix, 5 not hypotheses/plumbing. #20 and #21 also have the
follow-up forecast retest; #45 is the separate retest.

## What this means

1. **No new edge.** The six open rows do not produce a tradeable forecast. #9b is the closest: a
   real, out-of-time rank IC whose 4 bps spread is less than half the 9 bps round trip. That is a
   forecast result, not a trade.
2. **Two verdicts change, both downward.** #4's nominal pass is not statistically distinguishable
   from its benchmark (alpha t 1.10), and #43's 12-hour confirmation fails its own deflated bar
   (t −0.97, −9.6 bps trade-weighted). Both were already flagged by the audit; the retest confirms it.
3. **The audit's estimator criticism is confirmed where it can be tested.** #8's overlapping-label
   IC t falls from the published 8.11 to 1.63 on non-overlapping weeks; #43's day-mean 21.8 becomes
   −9.6 trade-weighted; #9b's t falls from 13.44 to 5.30 without changing the conclusion that the
   spread is sub-cost.
4. **The forward tests remain the only clean tests.** Nothing in this document reads a forward day.
   #22–#24, #27, #29, #31–#32, #34, #38 and #45 are judged on their dates.

## Limits

- **Forecast retests, not full replications.** #4 and #15 use simplified monthly/weekly engines and
  10 bps costs, not the original daily simulators. #8 re-tests the selection IC/spread, not the
  portfolio construction; criteria 1–3 are not re-run.
- **Data defects.** The daily panel's ARB/TIA/WLD/OP ticker collisions and |forward return| > 50%
  observations are dropped (amendment in the registration). Funding is Binance settled, not
  Hyperliquid or Deribit; the venue-specific-threshold criticism of #1 is not fully answered.
- **#43 uses the published event file.** It is a re-estimate on the original's event-level data, not
  new data; it cannot create new evidence, only re-read the old.
- **One path, one window.** The validation windows are single historical paths; no claim is made
  about the future. Survivorship is not corrected (the coin list is October 2026's).
- **Multiple testing.** Six primary tests, BH at 5%; secondary horizons and controls are information
  only. No secondary result is promoted.

## Reproduce

```bash
python research/remaining_forecasts.py
python -m unittest tests.test_remaining_forecasts
```

Reads `data_raw/` (gitignored): the local price/funding archives plus the original repository's
event-level outputs under `data_raw/events/` (`lows_events`, `horizons_s1_12h_trades`,
`horizons_cells`). To reproduce, copy those published event files there first. No fetch, no forward
window, no ledger row, no order.
