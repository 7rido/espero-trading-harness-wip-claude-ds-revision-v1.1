# Result — tape-edge design: four forced-flow mechanisms, none survives

**Verdict: all eight design cells fail. No cell passes BH, none is within 8 bps of the cost bar, and per
the registration the sealed holdout was never opened.**

Registration: `research/PREREGISTRATION_tape_edges.md` · code: `research/tape_edges.py` · data:
`tape_edges_design.json`. Design window: 29 cached Binance UM `BTCUSDT` days (2026-10-01 → 2026-10-30,
one archive 404).

## The cells

| mechanism | h | days | events | mean (signed) | t | net of 9 bps | BH |
|---|---|---|---|---|---|---|---|
| sweep exhaustion | 15 | 29 | 703 | **+0.8 bps** | 0.98 | −8.2 | — |
| sweep exhaustion | 60 | 29 | 703 | +0.0 | 0.02 | −9.0 | — |
| absorption | 30 | 28 | 85 | **−3.2** | −0.95 | −12.2 | — |
| absorption | 60 | 28 | 85 | **−4.5** | −1.10 | −13.5 | — |
| block continuation | 5 | 29 | 1,135 | +0.2 | 0.67 | −8.8 | — |
| block continuation | 15 | 29 | 1,127 | +0.4 | 0.73 | −8.6 | — |
| divergence | 60 | 29 | 1,328 | −0.3 | −0.18 | −9.3 | — |

## What it means

1. **The liquidation mechanism does not have a tape analogue at minute resolution.** Sweeps, absorption,
   blocks and divergence are all real flow events, and none of them predicts the next move in the
   direction the mechanism implies.
2. **Absorption has the wrong sign** (−3.2/−4.5 bps when fading the prior move): if anything, the tape
   continued, but with t ≈ −1 it is inside noise. Either way it fails.
3. **The only tape predictability found in this project remains at seconds** (OFI 30–60 s, +0.13/+0.22
   bps, 40–70× below costs) and **volatility** (intensity→RV 1.74×, VPIN→variance, both risk measures).
4. **The cost bar matters as much as significance**: even a 2–3 bps effect could not pay 9 bps.

## Why the mechanisms may fail here

- Minute aggregation: sweep urgency decays in seconds, and the entry is the next minute's close —
  the effect may be gone before the fill.
- No order-book data: absorption needs book depth to distinguish "passive size" from "low volume".
- One month, one venue: 700 sweep events is a decent sample, but the October regime may simply not
  contain the cascade environment the mechanisms need.
- BTC only: the liquidation edge was a 10-coin phenomenon, strongest in smaller coins.

## Governance

The holdout (2026-08-01 → 2026-09-30) was **not** fetched or read; the seal was never written because the
design did not qualify. That is the registration working as intended.

## Would change the verdict

Trade-level (not minute) sweeps with paired book depth, multiple coins, and 6–12 months. That is a new
registration.
