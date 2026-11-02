# Result — conditional suite over all the data we hold

**Verdict (corrected 2026-11-01): 17 of 51 cells pass BH at 10 %.** The first run reported zero because
the p-values used a broken normal-tail approximation that capped around 0.006 for large z. The direction
is the same and now has within-suite significance: **crowded positioning underperforms**.

**But none of the economically meaningful cells survives the full family.** The premium cell's p is
0.009; over the 121-cell program family that is **0.66**. The cells that do survive family-wise
correction are sub-cost effects (e.g. "3 % below the 20-day high", −3.6 bps at 1 d, z 4.02) — real, but
unable to pay a 9 bps round trip. So: statistical significance exists at suite level, none of it is both
family-wise significant and economic. Every cell here is
market-relative (coin return minus that day's cross-section), so the 2020–2026 bull drift is removed —
which is what makes the earlier raw means disappear.

Code: `research/conditional_suite.py` · data: `conditional_suite.json`.

## The cells with the strongest signal-to-noise

| state | h | n | mean | median | p10 | p90 | up |
|---|---|---|---|---|---|---|---|
| **premium top quintile** | 7d | 1,121 | **−222.5** | **−251.6** | −1,670 | +1,093 | **36%** |
| **funding top quintile** | 7d | 3,798 | −104.3 | −256.4 | −1,288 | +988 | **35%** |
| down run≥3 & funding high | 1d | 217 | −33.2 | −92.2 | −298 | +238 | 34% |
| vol bottom quintile | 7d | 20,293 | −27.7 | −106.6 | −804 | +733 | 41% |
| 10% below 20d high | 7d | 42,926 | −23.1 | −108.3 | −845 | +770 | 41% |

The two clean ones are **the same economic state measured twice**: when the perpetual's premium is
high *and* funding is high, the coin underperforms its peers over the next week, with the median hit
rate at 35–36%. That is the classic crowded-long mean reversion — and it is the only place in the
suite where direction, median and hit rate agree.

**And it still fails multiplicity**: z ≈ 2.6 on 51 cells needs ≈ 0.002 for BH, the cell sits at 0.009.
One lucky family would produce this; that is why the column exists.

## What changed from the first run

The first table used **raw** forward returns and reported +400 bps for "breadth top quintile" and
"+173 bps after a 3-day down run with high funding". That was the market's drift, not the state:
2020–2026 crypto rose a lot. Market-relative outcomes remove it, and most of those effects vanish or
flip. The remaining direction — crowded positioning underperforms — is the opposite of a bounce.

## What this means

1. **No conditional cell is tradable on this evidence**, but the premium/funding pair is the most
   coherent descriptive finding the project has produced: a mechanism (crowded longs pay to stay
   long, then underperform), a median, and a hit rate that agree.
2. The wide 10–90 bands (±1,000 bps over a week) are the real message: these states shift the
   distribution's centre by a fraction of its width.
3. The honest next step is not more cells — it is a **sealed out-of-sample test** of exactly one of
   them, with the selection cost counted.

## Limits

- Full-sample descriptive (2020–2026, 42 symbols); no train/test split here.
- Overlapping forward windows; SE uses an effective-n correction, not a block bootstrap.
- Premium exists for 25 symbols, 2024–2025 in our substrate; funding for 42 symbols.
- Market-relative outcomes mechanically remove market-wide states (breadth, correlation), which is
  why those were dropped rather than reported.
