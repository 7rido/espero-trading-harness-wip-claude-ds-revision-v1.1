# Result — regime signs: trend × volatility × funding, and today's market

**16 cells, none survive FDR.** One coherent descriptive pattern: **uptrend + high funding
underperforms over 20 days** (median −320 to −430 bps, 37% up). Today SOL classifies as
`down/low/high` — the mirror cell, median −205 bps — and BTC as `up/low/low` with a visible short
squeeze. Neither is evidence.

Code: `research/regime_signs.py`, `research/regime_now.py` · data: `regime_signs.json`.

## Method

States from information at the close only: `trend` = 60-day return > 0; `vol` = realised-variance
percentile > 50% (252-day rank); `fund` = 7-day mean funding percentile > 50%. Outcomes are
**market-relative** (coin minus that day's cross-section) at 5 and 20 days. Sample 2023-01 → 2025-06,
42 symbols (funding limits the window). BH FDR across all 16 cells.

## The cells

| state | h | n | mean | median | p10 | p90 | up |
|---|---|---|---|---|---|---|---|
| up/low/high | 20 | 1,943 | −212 | **−319** | −1,999 | +1,333 | **37%** |
| up/high/high | 20 | 5,069 | −115 | **−426** | −2,141 | +2,099 | **37%** |
| down/high/low | 20 | 3,693 | −49 | −181 | −1,112 | +1,083 | 40% |
| up/low/low | 20 | 2,068 | +156 | −9 | −995 | +1,451 | 50% |
| up/high/low | 20 | 2,014 | +183 | −62 | −1,232 | +1,871 | 47% |

**The pattern is consistent across the two independent "high funding" cells**: when funding is
expensive in an uptrend, the next 20 days are negative in the median and positive only 37% of the
time. That is the same crowded-long mean reversion the conditional suite found with premium.

It still fails: z ≈ 2.7 on 16 cells needs ≈ 0.006 for BH; the cell sits near 0.01.

## Today's classification (2026-10-31, live)

| coin | price | 60d | vol %ile | funding %ile | state | hist n | med 5d | med 20d |
|---|---|---|---|---|---|---|---|---|
| **SOL** | 95.83 | −4.1% | 22% | 59% | **down/low/high** | 1,986 | −37 | **−205** |
| **BTC** | 77,459 | +0.1% | 24% | 32% | **up/low/low** | 2,068 | −3 | −9 |

Live microstructure:

- **BTC**: OKX 24 h liquidations **$39.9M short vs $5.1M long** — a short squeeze in progress; HL funding
  **+10.9%/yr** (longs paying), premium +0.6 bp, HL OI 41,062 BTC.
- **SOL**: OKX 24 h **$167k long vs $67k short** — mild long flush; HL funding +10.9%/yr, premium −1.6 bp,
  HL OI 5.40M SOL. Funding on Binance/OKX is ~+2–3.5%/yr, so the HL hourly number is venue-specific.

## What this means, honestly

1. **Today's state is a context label, not a forecast.** SOL is in the state whose 20-day median is
   −205 bps, but that cell covers 1,986 observations and still fails multiplicity.
2. **BTC's short squeeze is the more actionable fact** — not as a signal, but as a reason to expect
   continuation risk in the direction of the squeeze, and as evidence that liquidation data now
   actually describes the market in real time.
3. The regime study's value is **risk framing**: an uptrend with expensive funding is where longs get
   hurt; a downtrend with expensive funding (SOL) is where shorts get crowded next.

## Limits

- Funding window ends 2025-06 (Binance archive); vol and trend run to 2026-03 in `bars_daily`.
- Monthly Tardis samples are too sparse for state cells and were not used here.
- 16 cells, one specification, no out-of-sample read; the live classification is a single day.
