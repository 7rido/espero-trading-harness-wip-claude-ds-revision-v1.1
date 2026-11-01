# Result — pre-registered tape study: flow forecasts volatility, not direction

**Verdict: 12 directional cells, zero pass BH, zero beat the 9 bps cost bar. One non-directional
result is strong: trade intensity forecasts next-hour realised volatility — top quintile is 1.74× the
bottom quintile.**

Registration: `research/PREREGISTRATION_tape.md` (written before the fetch). Code:
`research/tape_study.py` · data: `tape_study.json`.

## Sample

Binance USD-M `BTCUSDT` aggTrades, **29 of 30 requested days** (2026-10-01 → 2026-10-30; one daily
archive returned 404) — **39,993 minute bars**, quintile spreads computed within each UTC day, then
averaged across days; t from the 29 daily values.

## Directional cells (all reported)

| feature | 5 min | 15 min | 60 min | BH |
|---|---|---|---|---|
| OFI `(buy−sell)/(buy+sell)` | −0.3 bp (t −1.52) | −0.3 (−0.95) | +0.7 (0.84) | none |
| absorption flag | +0.4 (0.50) | +0.8 (0.58) | −0.2 (−0.08) | none |
| sweep flag | −0.1 (−0.22) | +0.7 (1.18) | +1.1 (0.74) | none |
| block flag | +0.0 (0.19) | +0.4 (1.28) | +2.6 (1.51) | none |

Every spread is **below 2.6 bps** and none survives BH at 10%; the 9 bps round trip is ~4–30× the
measured edge. The block flag is also sparse (9 usable days) so its 60-minute +2.6 bps is the least
reliable cell in the table.

## The one real result: intensity → volatility

Sorting minutes by trade intensity (prints per minute), the **next 60 minutes of realised variance
in the top quintile are 1.74× the bottom quintile**, across 29 days. That is a robust, tradeable-in-risk
relationship: volume predicts variance, not direction — the same pattern the HAR work found with
bar-based measures.

## What this means

1. **Tape direction at 5–60 minutes is not supported** on this sample. The literature's OFI effect lives
   at seconds-to-a-few-minutes and decays; minute aggregation plus a 9 bps cost bar kills it.
2. **Tape intensity is a volatility instrument.** Use it to size, to widen stops when flow accelerates,
   and to expect regime change — not to pick a side.
3. **Blocks/sweeps are too sparse** at this sample size; they need months, not days.
4. The dashboard tape card stays descriptive; nothing here authorises a trade.

## Limits

- One month, one venue (Binance UM), minute aggregation.
- Daily 404s reduce cluster count; effective power is lower than the minute count suggests.
- No order-book data paired with the trades, so OFI is trade-flow only, not queue imbalance.
- Costs measured on Binance books; execution would be elsewhere.

## Would change the verdict

Shorter horizons (30–180 s), trade-level OFI, order-book imbalance paired with prints, and 6–12 months
of tape. That is a new registration, not a re-run.
