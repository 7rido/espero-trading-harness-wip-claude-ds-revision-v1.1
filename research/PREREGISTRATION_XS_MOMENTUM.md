# Pre-registration — cross-sectional momentum, deep (#2/#7, revision 2)

Written **before any 2021–2023 price is fetched**. The design window is 2021–2022; the holdout is
2023 and is read once, after this document and the frozen universe are committed.

## 1. Mechanism — who is on the other side

Cross-sectional momentum is not a story about information; it is a story about **who must trade in the
same direction twice**. Three counterparties:

- **Rebalancing allocators**: index and equal-weight products must buy what has risen (to restore
  weights) and sell what has fallen, at fixed calendar points. Their demand is price-insensitive and
  predictable.
- **Risk-parity and volatility-target funds**: a coin whose realised volatility falls gets bought; a
  coin in a drawdown gets sold, again mechanically.
- **Attrition and delisting**: coins that lose sponsorship lose liquidity, so the remaining holders
  are forced sellers into a thinning book; the mirror is true for winners as they get added to
  baskets.

The prediction that follows is not "winners keep winning" in general; it is narrower:

**P1 — the cross-section of 30-day returns predicts the next 7 days' cross-section, but only with
turnover-aware construction: a weekly-rebalanced, dollar-neutral top-minus-bottom quintile book earns a
positive net return after fees and funding, because the rebalancing counterparties provide the flow.**

**P2 — the effect decays with size and liquidity**: the spread is larger in the less liquid half of the
universe and shrinks after a coin's liquidity doubles.

If the sign is there but costs eat it, momentum is real and untradeable at this level of turnover — a
result worth as much as a pass.

## 2. Universe — fixed by rule now, frozen in a file later

- **Source**: Binance USDⓈ-M perpetuals, monthly `klines` and `fundingRate` archives. Symbols that
  delisted are included while they existed; the archive's own file existence is the listing record.
- **Candidate set**: every symbol with **at least 12 monthly files between 2021-01 and 2022-12**.
- **Selection**: the **top 50 by summed daily quote volume over 2021–2022**. Volume is measured in the
  design window only.
- **Frozen** in `research/xs_universe.csv` and committed before the 2023 files are fetched.
- **Delisting in the holdout**: a coin that stops trading exits the book at its last available close;
  it is not back-filled and not silently dropped — the exit is a sale at the last print.

## 3. Signal and portfolio

- Daily closes, UTC. Signal at Friday 00:00 UTC: **30-day return** (close/close 30 days earlier − 1).
- Rank the universe cross-sectionally; **long the top quintile, short the bottom quintile**, equal
  notional, dollar-neutral.
- Hold **7 days**, rebalance weekly on the same weekday.
- A coin with fewer than 30 days of history in the window is excluded that week (no partial windows).
- Funding: a **long pays** positive funding, a short receives it, charged daily from `fundingRate`.
- Costs: **5 bps per side** on every position opened, closed, or resized; a turnover-neutral
  rebalance changes weights only by the turnover actually traded.

## 4. The falsifiable prediction, with numbers

**P1**: mean weekly net return of the top-minus-bottom book **> 0** with a block-bootstrap 95% CI whose
lower bound is **> 0**, and an annualised net Sharpe **> 0.8** after costs.

**P2**: the net spread is positive in **both** liquidity halves (ranked by 2021–2022 median quote
volume) and larger in the low-liquidity half.

**P3**: a **placebo** book built from 30-day returns with the sign removed (long the worst, short the
best) must lose money after costs; and a book on **date-shuffled** returns must be indistinguishable
from zero.

**Pass requires P1 and P3; P2 is reported either way.** If P1 fails, momentum at weekly turnover is
dead at 5 bps and that is the result.

## 5. Estimator — fixed before the run

- **Block bootstrap** on weekly portfolio returns (stationary, mean block 8 weeks, 10,000 resamples),
  95% percentile CI.
- **HAC**: Newey–West with 8 lags on the weekly mean.
- **Multiplicity**: three registered variants — 30-day lookback weekly (candidate), 7-day lookback
  weekly, and 30-day lookback with 14-day holds — with the **deflated Sharpe ratio** and Hansen's SPA
  computed across them.
- No fitting: the candidate is the first; the others are reported as information.

## 6. Capacity and decay

- **Capacity**: from `bookDepth` samples, the $ notional at which impact consumes half the spread, per
  symbol; report the median and the total.
- **Decay**: the spread's autocorrelation across weeks; report the half-life of the momentum signal.
- **Placebo suite**: sign-flipped book and date-shuffled book, as in P3.

## 7. Holdout — sealed

- Design: **2021-01-01 → 2022-12-31**.
- Holdout: **2023-01-01 → 2023-12-31**, read once, after the universe file is committed.
- Same rules, costs and estimator; no re-tuning.

## 8. Reconciliation — the venue's own records

1. **Price identity**: our daily closes equal the published `klines` closes to the last digit.
2. **Funding identity**: summed `fundingRate` per day equals the funding charged in the P&L.
3. **External print check**: on 10 random symbol-days, the close is the last `aggTrades` print of that
   day.
4. **Independent implementation**: the final number is reproduced by a second query (DuckDB SQL) over
   the same Parquet files.

## 9. Outcomes — fixed

- **P1 and P3 hold**: weekly cross-sectional momentum is a tradeable premium at this cost level; a
  forward test may be registered.
- **P1 fails, P3 holds**: real but dominated by costs; retire the family with the mechanism written down.
- **Placebo fails**: the pipeline is broken; nothing else in the result is trusted.
