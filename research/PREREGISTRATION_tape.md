# Pre-registration — tape features vs short-horizon BTC outcomes

**Written before any data is fetched for this test.** If it fails, it is reported as failed.

## Question

Do order-flow tape features forecast BTC returns or volatility at 5–60 minute horizons, after costs
and multiplicity?

## Data

- Binance USD-M `BTCUSDT` daily `aggTrades`, **2026-10-01 → 2026-10-30** (30 UTC days).
- Minute bars built from the aggTrades only (no external prices).
- Venue note: research on Binance UM; execution would be elsewhere — a finding is venue-specific.

## Hypotheses and statistics (fixed)

All return tests use the **daily quintile spread**: within each UTC day, sort minutes by the feature,
take the mean forward return of the top quintile minus the bottom quintile, then average across days and
compute a t-statistic from the 30 daily values (two-sided, 5%). Horizons: **5, 15, 60 minutes**.

| id | feature | prediction |
|---|---|---|
| H1 | order-flow imbalance `(buy_qty − sell_qty)/(buy_qty + sell_qty)` | positive spread (buying pressure precedes up moves) |
| H2 | absorption flag (volume z ≥ 2 and \|return\| below the **trailing 60-minute median**, shifted 1) | reversal: absorbed selling precedes up moves (and the mirror) — sign tested both ways |
| H3 | sweep flag (≥ 3 fills same ms and price in the minute) and block flag (≥ 1 print ≥ $100k) | continuation: positive spread |
| H4 | trade intensity (prints per minute) | volatility only: next 60-minute realised variance rises with intensity (Spearman + quintile means) |

## Multiplicity

12 return cells (H1–H3 × 3 horizons) corrected with **Benjamini–Hochberg at 10%**; H4 is reported
separately and not counted in that family.

## Costs and decision rule

Round-trip cost **9 bps** (measured Binance books). A cell is "tradeable" only if it passes BH **and**
its gross spread exceeds 9 bps. Otherwise it is reported as descriptive.

## Governance

- One run, no re-tuning of horizons, quintile count, thresholds or the blackout of the last 60 minutes
  of each day.
- Every cell is reported, including nulls.
- The result is written to `research/RESULTS_tape_study.md` with the JSON next to it.
