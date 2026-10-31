# Result — liquidation anatomy: what a liquidation actually does to price

Descriptive statistics, not a strategy. 2023-01 → 2024-11, ten coins, Binance COIN-M liquidations,
hourly bars from the 5m archive. An **event** is an hour whose liquidation notional is above that
coin's **99th percentile**. For each event we record the shape of the preceding hours and the return
over the next 1 / 4 / 24 hours. Intervals are day-clustered bootstrap 95%.

Code: `research/liquidation_anatomy.py` · data: `liquidation_anatomy.json` · events: **246 long-side,
244 short-side**.

## Long liquidations: what follows a forced sell-off

| pre-shape | n | next 1h | next 4h | next 24h |
|---|---|---|---|---|
| **1h, 2h, 4h all down** | **216** | **+12.8 bps** (med +23.5, 56% up) CI −30…+57 | +22.9 (53% up) CI −56…+113 | +159.5 (56% up) CI −143…+437 |
| aligned bull | 4 | +204.7 | +1231 | +213.8 |
| consecutive down hours: 1 | 44 | −3.4 | — | — |
| 2 | 68 | +52.6 | — | — |
| 3 | 38 | +24.6 | — | — |
| **4** | **75** | **−3.4 mean**, med **+40.1**, **60% up**, CI −74…+79 | — | — |

**The answer to "1–2–3–4 bearish hours → is the 5th bullish?"**: the **median and hit rate say yes**
(60% of the time, median +40 bps), but the **mean is zero** because the other 40% are large losses.
That is a positively skewed, fat-left-tailed distribution, not a reliable reversal. Any rule built on
it would be short a tail.

## Short liquidations: the squeeze side

| pre-shape | n | next 1h | next 4h | next 24h |
|---|---|---|---|---|
| **1h, 2h, 4h all up** | **197** | **−7.7 bps** (47% up) CI −45…+34 | +14.0 (50% up) | −2.6 |
| 1h down only | 14 | −47.4, CI −86…−16 | +31.9 | +282.7 |
| mixed | 31 | −30.9, CI −57…−4 | −1.9 | +191.1 |

Short squeezes show **no continuation and no reliable reversal**. The one negative cell
("1h down only", n=14) is too small to believe, and with this many cells it is what multiple testing
manufactures.

## What this establishes

1. **Liquidation events are not a clean multi-horizon reversal signal.** After long liquidations the
   bounce exists in the median and the hit rate, and is cancelled by the tail in the mean.
2. **Alignment matters less than it looks**: 216 of 246 long-side events happen with 1h/2h/4h all
   down — the "aligned bear" pattern is not rare, it is the normal state during a cascade.
3. **The short side is symmetric in the bad way**: squeezes do not predict.
4. This is consistent with the earlier finding that the *executable* bounce is worth ~+32 bps at 4h
   **in-sample** but needs a forward window to be believed — the descriptive statistics here cannot
   distinguish a 20 bps edge from noise.

## Caveats

- COIN-M liquidations only (Binance), so the notional is the coin-margined segment; the event
  threshold is per coin, not cross-venue.
- Events are hourly aggregates; the 5m archive's exact intra-hour timing is not used.
- Forward windows overlap across events; intervals are day-clustered, which handles the day-level
  dependence but not the intra-day overlap.
- No multiplicity correction is claimed — the table is descriptive, and the cells with n < 30 are
  reported anyway so they are not mistaken for findings.

## The honest use of this

A liquidation model for **risk** — expecting a bounce is wrong; expecting a fat left tail and a small
positive median is right. That is a statement about sizing and stops, not a signal to trade.
