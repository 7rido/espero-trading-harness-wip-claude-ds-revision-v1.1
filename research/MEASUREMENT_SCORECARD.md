# Measurement scorecard — what each sign has actually earned

Two ratings per measurement, because they answer different questions:

- **Prediction (1–10)** — has it forecast direction with evidence that survives the family-wise bar?
  1 = tested and failed with adequate sample, 5 = coherent but not significant, 9–10 = survives selection.
- **Risk use (1–10)** — is it useful for sizing, gating or context even without a directional edge?

Every number below is from this repo. No new tests were run for the ratings except positioning (117 days).

| measurement | sample | best evidence | prediction | risk use |
|---|---|---|---|---|
| **Liquidation mechanism** | 28k breaks, 10 coins, 2023–24 | forced−organic t −5.13, p 2.9e-7; **survives 121-cell correction** | **9** | 8 |
| **Realised volatility (HAR)** | 38 symbols | QLIKE 0.393 vs EWMA 0.450, beats on 35/38 | 1 | **9** |
| **Funding level** | 2023–2025, 42 symbols | carry design t 3.13; family-wise 0.19 → fails | 3 | 6 |
| **Basis / premium** | 1,121 obs | 7d median −252 bps, 36% up; FDR 0.68 → fails | 4 | 6 |
| **Trend (SMA, 60d)** | 42 symbols, 6 yr | SMA retired (tracked hold); regime cells fail | 1 | 3 |
| **Volume** | 17.5k obs | 51-cell suite: no FDR pass | 2 | 4 |
| **Open-interest change** | SOL, 117 days | 12 cells, 0 with \|t\|≥2 | 1 | 5 |
| **Taker flow / CVD** | SOL 117d + 1 day ticks | 0 with \|t\|≥2; one-day CVD ≈ 0 | 2 | 5 |
| **Long/short ratios** | SOL, 117 days | best cell +140 bps at 5d, t 0.56 | 2 | 5 |
| **Order-book imbalance** | 2 days, 4,320 min | median OBI +0.009; no relationship tested at scale | 1 | 4 |
| **Breadth / correlation** | regimes.csv | regime families all fail validation | 2 | 6 |
| **Drawdown from high** | 42.9k obs | 7d median −108 bps, 41% up; fails FDR | 2 | 5 |
| **Implied vol / VRP** | — | no data | n/a | n/a |

## What the ratings say

1. **Only the liquidation mechanism earns a prediction rating above 5.** It is the one result that
   survives the 121-cell correction (p 2.9e-7); the executable variant survives too (p 6.1e-5).
2. **Volatility is the best *risk* measurement and the worst *prediction*.** It forecasts variance, not
   direction — rating 9 for sizing, 1 for signals. That split is the whole lesson of the audit.
3. **Funding and basis are the best of the failures.** Both show a coherent crowded-long fade (median
   −250 to −320 bps over 7–20 days, 36–37% up) and both fail multiplicity. Rating 4, not 0 — the
   mechanism is plausible and the sample is large; it simply hasn't cleared the bar.
4. **Positioning measures (OI, taker, long/short) have no support at all.** SOL only, 117 days, 12
   cells, zero |t| ≥ 2 (0.6 expected by chance). Rating 1–2 as prediction, 5 as context.
5. **Order-book imbalance cannot be rated yet** — two days of data, balanced book, no forward test at
   scale.

## What would raise a rating

| measurement | needed to reach 6+ |
|---|---|
| funding / basis | one sealed OOS window on the top-quintile fade |
| OI / positioning | 2+ years across ≥20 symbols, non-overlapping windows |
| order-book imbalance | 90+ days with sizes, tested against 5-min returns |
| implied vol | Deribit options history (samples or paid) |
| trend / volume / drawdown | would need a new mechanism, not more cells |

## The honest summary

**One measurement predicts (liquidation), one manages risk (volatility), two are plausible and
unproven (funding, basis), and the rest are noise or context.** Anything rated 1–2 should not be
allowed near a live decision, regardless of how good it looks in a single cell.
