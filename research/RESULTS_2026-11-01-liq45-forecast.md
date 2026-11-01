# Result — retest #45: a three-layer score forecasts the bounce's rank, not its economic size

**Headline:** on the #26 sample, a fixed pre-entry score ranks forced-liquidation bounces out-of-time
(4 h rank IC 0.179, 95% day-block CI 0.093–0.266; top quintile +24.8 bps vs +1.9 bps for all events).
The rank skill is real, but it is mostly **volatility and break depth**, not liquidation intensity,
tape or funding; the top-quintile mean is not significantly positive (CI −69.5 to +129.1 bps), and the
composite does not beat the best single layer. This is a forecast result inside #26's discovery window,
not a new edge and not a #45 verdict.

Registration: [PREREGISTRATION_2026-11-01-liq45-forecast.md](PREREGISTRATION_2026-11-01-liq45-forecast.md)
· code: [`liq45_forecast.py`](liq45_forecast.py) · numbers: [`liq45_forecast.json`](liq45_forecast.json).

## What was tested

The trade behind #45/E1: buy a **forced down-break**, exit at 4 h / 12 h / 1 day, net of 9 bps and
funding. The question was not whether the average bounce exists — #26/#44/#45 already measured that —
but whether a small set of features known **before entry** can forecast which events do better.

- **Data.** The #26 replication's continuous sample: 26 COIN-M coins, 2023-06-26 → 2024-10-14,
  Binance USDⓈ-M 5-minute bars, COIN-M order fills as liquidations. 28,029 events over 427 days
  before tagging; 6,139 forced down-breaks over 410 days after the prior-observed-day tag.
- **Split.** Fit 2023-06-26 → 2024-03-31 (3,598 events / 243 days); score once 2024-04-01 →
  2024-10-14 (2,541 / 167 days). The validation window is inside #26's discovery window; the forecast
  model is out-of-time, the bounce itself is in-sample.
- **Models.** F1 is the pre-registered equal-weight percentile composite of `s` (forced share),
  `atr_pct` (14-bar ATR / entry) and `−ret_1h` (deeper break scores higher), with the CDFs fitted on
  design only. F1+T adds `taker_imb`; F2 is a ridge on eight features (λ = 10). Thresholds are the
  training 80th percentiles.
- **Target.** Net return after 9 bps and the sign-adjusted Binance funding over the hold.

## The unconditional trade in the two windows

| window | events | 4 h mean | 4 h day-mean (t) | 12 h mean | 1 d mean |
|---|---|---|---|---|---|
| design | 3,598 | **+37.1 bps** | +51.9 (7.16) | +58.2 | +89.1 |
| validation | 2,541 | **+1.9 bps** | +31.2 (4.05) | +9.1 | +22.1 |

The validation window's trade-weighted 4 h mean is much weaker than design (+1.9 vs +37.1 bps);
the day-mean remains positive at +31.2 bps (t 4.05), so the equal-day view is stronger than the
equal-event view. This is exactly the cross-section a forecast has to sort.

## Primary — F1

| horizon | rank IC | 95% day-block CI | top quintile | all events | top n | top hit | top-quintile 95% CI |
|---|---|---|---|---|---|---|---|
| **4 h** | **0.179** | **0.093 … 0.266** | **+24.8 bps** | +1.9 bps | 463 | 64.4% | −69.5 … +129.1 bps |
| 12 h | 0.140 | 0.028 … 0.246 | +63.7 bps | +9.1 bps | 463 | 61.6% | −81.9 … +194.9 bps |
| 1 d | 0.125 | −0.033 … 0.268 | +124.1 bps | +22.1 bps | 463 | 62.6% | −173.1 … +413.9 bps |

The registered primary criterion is met at 4 h: IC > 0 with a CI excluding 0, and the top-quintile mean
above the all-event mean. 12 h also clears the IC CI; 1 d does not. The top-quintile **level** is not
statistically distinguishable from zero under a day-block bootstrap; the forecast sorts the cross-
section, it does not establish a positive selected-trade mean.

Calibration increases across the score quintiles:

| score quintile | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| mean net, 4 h | −16.8 bps | −7.4 | −4.7 | +11.0 | **+27.2** |

## Where the forecast comes from — single layers

A positive IC means the feature as named ranks bounces higher. `−ret_1h` is the one sign-flipped
feature (a deeper break scores higher); the other names are raw.

| layer | feature | 4 h rank IC | top-quintile 4 h | top n |
|---|---|---|---|---|
| movement | `atr_pct` | **0.190** | +20.4 bps | 320 |
| movement | `−ret_1h` | 0.141 | **+31.9 bps** | 410 |
| liquidation | `s` | 0.088 | +6.7 bps | 652 |
| tape | `taker_imb` | 0.078 | −6.6 bps | 512 |
| signal | `funding_ann` | −0.056 | −39.5 bps | 18 |
| signal | `btc_ret_1h` | −0.143 | −2.2 bps | 410 |
| tape | `vol_z` | 0.009 | +24.9 bps | 303 |
| liquidation | `liq_count` | 0.064 | −11.4 bps | 558 |

The three-layer score does not beat the best single layer: its IC (0.179) is **below ATR alone**
(0.190), and its top-quintile mean (+24.8 bps) is below `−ret_1h` alone (+31.9 bps). The liquidation
and tape layers do not add rank skill beyond price movement; funding and BTC context point the other
way. The composite is a reasonable fixed forecast, but it is not evidence that the extra layers carry
independent information.

## Secondary models

| model | 4 h IC (CI) | 4 h top | 12 h IC (CI) | 12 h top | 1 d IC (CI) | 1 d top |
|---|---|---|---|---|---|---|
| F1T (+ tape) | 0.177 (0.093 … 0.267) | +28.6 bps | 0.144 (0.029 … 0.246) | +84.7 bps | 0.140 (−0.013 … 0.277) | +157.5 bps |
| F2 (ridge, 8) | 0.160 (0.069 … 0.248) | +21.1 bps | 0.132 (0.013 … 0.247) | +67.1 bps | 0.133 (−0.024 … 0.283) | +146.3 bps |

Adding tape changes the IC by −0.002 and the top mean by +3.8 bps at 4 h. The ridge with all eight
features is weaker than F1 at every horizon. F1 has the highest rank IC of the three; F1T's tape
addition lifts the top mean by 3.8 bps but not the IC. The extra parameters do not help.

## Cross-check — the month-start archive, 2020–2026

A different, broad archive: 39 coins, three days at the start of each month, multi-venue liquidations
(8,893 events; 2,310 forced down). Train 2020-01 → 2023-12, score 2024-01 → 2026-10. This is **not**
#26's day sample — #26 drops the first two days and the last day of each month — and it is not continuous after 2024.
It is exploratory.

| horizon | rank IC | 95% CI | top quintile | all events | top n | top-quintile CI |
|---|---|---|---|---|---|---|
| 4 h | 0.207 | 0.007 … 0.378 | +41.2 bps | −4.6 bps | 180 | −76.8 … +133.7 bps |
| 12 h | 0.176 | 0.028 … 0.285 | +6.8 bps | −31.3 bps | 180 | −282.0 … +172.5 bps |
| 1 d | 0.087 | −0.117 … 0.263 | +13.6 bps | −52.7 bps | 180 | −321.3 … +278.4 bps |

The direction is the same as the continuous sample, which is mildly reassuring. The top-quintile CIs
are wide and include zero; with 34 validation days this cannot confirm anything.

## Cross-check — the stock-market analog

Daily down-breaks in SPY, QQQ and IWM (close below the prior 20-day low, volume z ≥ 2), target the
next 5-day return. 107 events, 74 train / 33 validation (2016-10 → 2026-10). The target enters at the
next open and exits five days later — a stricter, causal version of the registered close-to-close
target. This is a **cross-market analog, not a #45 replication**; equities have no equivalent
forced-liquidation feed.

- The unconditional validation rebound is +176 bps (66.7% up) — but 2023–2026 is an equity bull
  market, and the sample is 33 events.
- The two forecast models disagree: ridge IC **−0.278**, composite IC **+0.388**. Neither is a
  forecast claim at n = 33.
- There is no evidence here that a generic stock down-break has the same structure as a crypto
  liquidation bounce. The honest reading is "not tested well enough to say", not "confirmed" or
  "absent".

## What this means

1. **The bounce is forecastable in rank, modestly, out-of-time.** A fixed pre-entry score gets a 4 h
   IC of 0.18 (CI 0.09–0.27) and puts the top quintile at +24.8 bps against +1.9 bps for all events.
   That is a genuine forecast improvement on this history.
2. **The forecast is mostly volatility and break depth.** ATR alone has a higher IC (0.190) than the
   three-layer score (0.179); the deepest-break quintile earns +31.9 bps. Liquidation intensity adds a
   small positive, but does not lift the rank skill beyond movement; tape, funding and BTC context do
   not add.
3. **The selected-trade mean is not established.** The top-quintile CI is −70 to +129 bps. A forecast
   can rank better without making the selected trades reliably profitable; do not read this as a
   tradeable edge or as a reason to size up #45.
4. **#45's forward test remains the only clean test of the trade.** The validation window is inside
   #26's discovery period; this document adds a forecast result, not a new verdict. The monthly and
   stock cross-checks are exploratory.

## Limits

- Continuous liquidation history ends 2024-10-14. Post-2024 is monthly samples, not a continuous
  series; there is no clean post-2024 continuous out-of-sample here.
- The validation window is inside #26's discovery window. Only the forecast model is out-of-time.
- Tape is proxied by 5-minute taker-buy quote and volume. True tick/tape data covers 29 days of
  BTCUSDT aggTrades in Oct 2026 plus single-day samples, not a multi-month panel; the existing
  seconds-level tape study is cited, not re-run.
- COIN-M liquidations are one venue family; #45's forward feed is multi-venue. The monthly archive is
  multi-venue but starts every month.
- Costs are a flat 9 bps and Binance funding, not venue-specific execution.
- The stock analog uses daily bars, three ETFs and no liquidation feed; it is a control, not a test of
  the mechanism.

## Reproduce

```bash
python research/liq45_forecast.py
```

Reads only the local `data_raw/` archives; no fetch. Writes
`research/liq45_forecast.json`. The script never writes a ledger row or an order.
