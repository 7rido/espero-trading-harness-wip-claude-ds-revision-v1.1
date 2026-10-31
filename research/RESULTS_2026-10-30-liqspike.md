# Result — replication of #21 (liquidation spikes reverse) on the sealed months

**Verdict: FAIL.** One of the four pre-registered criteria missed, and it is the decisive one: the
effect is not distinguishable from zero (day-mean **t 0.85** against a bar of 3). The replication
reaches the same verdict as the original, on the same sealed data.

Spec: [PREREGISTRATION_2026-10-30-liqspike.md](PREREGISTRATION_2026-10-30-liqspike.md) (written before
any return was computed). Code: [liqspike_replication.py](liqspike_replication.py). One run; the
criterion-2 sign bug below was fixed and the run repeated, verdict unchanged.

## Data

`data/aggr/holdout` 2026-07-01 → 2026-10-30, four files, **SHA-256 verified 4/4** against
`reference/aggr_holdout_manifest.json` (sealed 2026-10-29). `data/aggr/explore` (Apr–Jun) used for the
trailing 720-hour thresholds only. 14 coins; price from Binance USDⓈ-M (OKX for SHIB), liquidations
summed over Binance, Bybit and OKX.

**1,669 spikes** over 119 days. Baseline (mean 24 h return over every holdout coin-hour): **+23.9 bps**.

## Criteria

| # | criterion | required | actual | met |
|---|---|---|---|---|
| 1 | forced flow reverts | mean R > 0, t ≥ 3 | **+14.0 bps, t 0.85**, 119 days | **no** |
| 2 | each side | long > 0, short < 0 | long **+31.8 bps** (t 1.63); short **−64.1 bps** (t −2.34) | yes |
| 3 | not one stretch | R > 0 in both halves | +10.5 bps (46 days) / +16.2 bps (73 days) | yes |
| 4 | a long-only trade pays | > 18 bps raw, t > 2 | **+55.6 bps**, t 2.86, 102 days | yes |

**Information only** (fixed in the pre-registration): trade-weighted R **−19.7 bps**, day-clustered
**t −0.67**, 1,647 events. The day-mean is positive and the trade-weighted mean is negative — the
#44 lesson, reproduced on new data: the day-mean gives quiet days the same vote as busy ones.

## Against the original #21

| | original (sealed months) | this replication |
|---|---|---|
| criterion 1 | +4.8 bps, t 0.27 | +14.0 bps, t 0.85 |
| long side, 24 h excess | +28.0 bps (t 1.36) | +31.8 bps (t 1.63) |
| short side, 24 h excess | −53.9 bps (t −1.87) | −64.1 bps (t −2.34) |
| halves | −20.2 / +33.0 (fails) | +10.5 / +16.2 (passes) |
| long leg raw 24 h | +51.1 bps, t 2.45 | +55.6 bps, t 2.86 |
| verdict | FAIL | FAIL |

Same verdict, and criteria 2 and 4 land within ~10% of the published numbers — which is what a
replication should look like. The differences are in the event set and the halves:

- **Event count**: 1,669 here against 1,240 in the original. Our spike test is per side and per hour
  with the same 2%/720 h rule, but the original counted only spikes that also passed its `MIN_DAY`
  grouping; the net effect is a larger, slightly different sample.
- **Halves**: the original's first half was negative (−20.2 bps); ours is mildly positive. With t 0.42
  that half carries no signal in either direction — the criterion is met here, not "confirmed".
- **Criterion 1 is the one that matters**, and both runs miss it by a wide margin.

## Defects, disclosed

- **A sign bug in the first evaluation**: R = −excess for short spikes, and the first version tested
  criterion 2 on R instead of on raw excess, which inverted it. The statistic was unchanged; the
  evaluation was fixed and the run repeated before this result was written.
- **Day-mean vs trade-weighted**: the pre-registered estimator is the day-mean (to match the original).
  The trade-weighted number is reported beside it and disagrees in sign; under the repo's later
  standard (#44), the average event loses 19.7 bps.
- **No funding, no fees inside the criteria**: criterion 4's 18 bps is the round-trip cost bar, not a
  charged cost; the raw return is gross.

## What this changes

Nothing trades on this. It is a replication, and it replicates: **liquidation spikes do not reverse
reliably on these four months** — sign-positive on quiet days, sign-negative when weighted by events.
The dataset is exhausted for this idea; a new claim needs new days or a different definition.
