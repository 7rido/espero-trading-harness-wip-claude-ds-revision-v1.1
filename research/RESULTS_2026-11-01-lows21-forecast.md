# Result — #20 and #21, forecast retest

**Bottom line:** #21's spike cross-section is **not forecastable** from spike size on the last two
months (rank IC +0.05, 95% CI −0.06 … +0.17), and #20's bounce **is** forecastable by prior
volatility (IC +0.028, CI 0.017 … 0.039, t 5.03) but the top-vs-all spread is only **+1.1 bps**,
below the 9 bps round trip. The original verdicts stand: #21 FAIL; #20 real-not-tradable. Neither
gives a trade.

Registration: [PREREGISTRATION_2026-11-01-lows21-forecast.md](PREREGISTRATION_2026-11-01-lows21-forecast.md)
· code: [`retest_20_21.py`](retest_20_21.py) · numbers: [`retest_20_21.json`](retest_20_21.json) ·
tests: [`tests/test_retest_20_21.py`](../tests/test_retest_20_21.py).

## #21 — liquidation spikes reverse

- **Data.** 1,240 spikes (631 long, 609 short) on 119 days, 2026-07 → 2026-10, 14 coins. Design
  July–August (640 events), validation September–October (600 events; 563 with both fields on 47
  evaluable days).
- **Primary.** `share` (the liquidation share of the spike hour) vs signed 24-hour excess:
  validation rank IC **+0.052** (95% day-block −0.057 … +0.165), t 1.02, q 0.310; the pooled top
  quintile is **+35.2 bps** vs all **+2.2 bps**, a **+33.0 bps** spread (CI −53.9 … +111.8). The
  day-weighted average is +25.0 bps. The CI is too wide to call a forecast, and the design IC is
  +0.021 — the sign is not stable enough to trust.
- **Secondary.**
  - `abs_r0` (size of the forced move): IC +0.116 (−0.010 … +0.236), t 1.71; 4 h IC +0.187.
  - `log_usd`: IC +0.059 (−0.048 … +0.162).
  - `side`: IC −0.113 (−0.260 … +0.052) — shorts, not longs, are the ones with the larger signed
    excess, if anything.
  - None clears zero; all are information only.
- **Verdict.** NO FORECAST. The published FAIL and the local replication's trade-weighted −19.7 bps
  stand; the cross-section does not rescue the average.

## #20 — new 4-hour lows bounce

- **Data.** 106,840 down-breaks with panel features, 2021-10 → 2026-03; design 2021-10 → 2023-12
  (50,490 events), validation 2024-01 → 2026-03 (56,350 events over 740 days). Features are read
  from the previous day's close.
- **Primary.** `vol_30` (30-day realised volatility) vs the 1-hour bounce: validation rank IC
  **+0.0285** (95% day-block 0.0172 … 0.0394), t 5.03, q 9.7e-7; the pooled top quintile is
  **+5.5 bps** vs all **+3.7 bps** — a spread of **+1.9 bps** (CI −4.9 … +8.1), **−7.1 bps after the
  9 bps round trip**. The day-weighted average is +1.1 bps. The IC is stable (design +0.039), the
  money is not.
- **Secondary.**
  - `ret_1`: IC −0.015 (−0.026 … −0.004), t −2.73; `ret_5`: −0.016 (−0.027 … −0.004), t −2.74.
    Prior weakness predicts a slightly smaller bounce, not a larger one.
  - `ret_20`: −0.010 (−0.021 … +0.002); `vol_z`: −0.012 (−0.022 … −0.002). Both sub-cost.
  - Market and BTC context have no cross-sectional variation on a given day, so no rank IC is
    defined; they are not reported as signals.
- **Verdict.** WEAK FORECAST: a real rank forecast, not a trade. This mirrors #45's finding that
  volatility — not the event label — carries the forecast for the forced-liquidation bounce. It does
  not change #44's trade-weighted +5.9 bps on the average event.

## What this adds to the remaining-findings retest

The main result ([RESULTS_2026-11-01-remaining-findings.md](RESULTS_2026-11-01-remaining-findings.md))
dispositioned #20 as "#44 re-estimated" and #21 as "already retested locally". This follow-up adds
the forecast question those two rows did not answer:

- **#21:** the average reversal is not significant and the cross-section is not forecastable; the
  event is exhausted for both questions on these months.
- **#20:** the bounce is forecastable by prior volatility, but the improvement is 1.1 bps against a
  9 bps round trip. That is a forecast result, not an edge, and it does not promote #20 or its
  forward test #24.

No forward window was read, no ledger row or order was written, and no rule was changed.

## Limits

- **#21 is four months.** 563 evaluable validation events over 47 days; the confidence interval on
  the IC is wide and the design IC is half the validation IC. A null here is weak evidence against a
  small effect, but it cannot support a positive one.
- **#20's features are daily.** The 5-minute break depth and the event bar's own volume z are not in
  the published event file; `vol_30` is a coarse proxy for #45's ATR/break-depth layer. The result is
  a floor on what a 5-minute feature set might do, not a ceiling.
- **Panel start.** The daily panel starts 2021-10-27, so 2020-2021 events are dropped, not imputed.
- **One path.** The design/validation split is fixed, but both are historical; no claim about the
  future.
- **Data filter.** |target| > 50% observations are dropped as data errors, as in the main retest.

## Reproduce

```bash
python research/retest_20_21.py
python -m unittest tests.test_retest_20_21
```

Reads `data_raw/events/` and `data_raw/panel/` only. No fetch, no forward window, no ledger row, no
order.
