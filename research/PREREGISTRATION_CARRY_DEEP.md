# Pre-registration — funding carry, deep (#12, revision 2)

Written **before any 2025 data is downloaded**, and committed to the repository before the evaluation
window is read. The design window (2024) may be inspected; the holdout (2025 H1) may not, except
through this document's fixed rules.

## 1. Mechanism — who pays, and why they cannot stop

A perpetual future has no expiry, so its price is pinned to spot only by a **funding payment**: every
8 hours, when the perp trades at a premium, longs pay shorts the premium. The counterparty is therefore
**the levered directional trader** — the participant who wants long exposure with borrowed size and no
custody, and who accepts paying for it. They cannot substitute spot because their constraint is capital
and margin: spot requires the full notional and a separate balance sheet, while a perp gives the same
exposure against collateral, and their venue treats it as one margin account.

Carry takes the other side: **short perp, long spot**, delta-neutral. Its return is the funding
received plus the change in basis, minus costs.

Why the edge persists:

- the arbitrageur must hold inventory, bear **venue and custody risk**, and post margin on both legs;
- spot borrow and transfer frictions, and the need to pre-fund the spot leg, bound the capital;
- funding spikes coincide with liquidation cascades, exactly when levered shorts are most expensive;
- funding is capped per interval by the venue, so the arbitrage is not unlimited at any moment.

If this is the whole story, the harvest is a **risk premium paid for inventory and venue risk — not
alpha**. That is a testable difference: it must pay net of realistic costs, it must decay with the
funding premium, and it must have finite capacity.

## 2. Universe — fixed now

- **Symbols**: Binance USDⓈ-M perpetuals with a funding-rate file in **every month of 2024 and of
  2025-01…2025-06** and a matching Binance spot pair with daily klines over the same span.
- **Selection**: the **top 25 by median daily quote volume in 2024**, computed only from 2024 data.
  The list is frozen in `research/carry_universe.csv` and committed before the holdout is read.
- **No post-hoc removal**: a symbol that delists or stops paying during the holdout keeps its slot and
  contributes zeros from that point; removing it would be survivorship by the back door.

## 3. Signal and position — fixed now

Daily at 00:00 UTC, for each symbol:

- `f3` = mean of the last 9 funding rates (3 days, 8 h each), annualised: `f3 × 3 × 365`.
- **Entry**: if `f3_annualised > 20%` and the perp trades at a premium (`perp_close/spot_close − 1 > 0`),
  open the harvest: short perp, long spot, equal notional.
- **Exit**: when `f3_annualised < 5%`, or after **30 calendar days**, or on a margin call (none is
  modelled — positions are unlevered, so this cannot happen).
- **Capital**: 100% of notional in spot plus 100% in perp margin (unlevered, deliberately: the edge
  must exist before leverage amplifies it).
- **P&L**, per day held: `funding_received + (spot_return − perp_return) − costs`, where
  `funding_received` is the sum of realised rates while short, and costs are charged at entry and exit.

**Costs — pre-registered, no table games**: Binance USDⓈ-M taker **5 bps**, spot taker **10 bps**,
charged on both legs at entry and at exit → **30 bps per round trip**, plus the measured half-spread
from `bookDepth` if it exceeds 1 bp (it is added, never substituted).

## 4. The falsifiable prediction, with numbers

**P1 (the edge exists):** the portfolio of all open harvests, daily equal-weighted across symbols,
earns a **net annualised return ≥ 8%** over the design window, with a block-bootstrap 95% CI whose lower
bound is **> 0**, after the 30 bps round trips are amortised over actual holding periods.

**P2 (it is a premium, not alpha):** net carry per unit of funding is **< 1** — i.e., the harvest keeps
less than the funding it collects, the difference being basis drift and costs — and its **decay
half-life** is finite (< 30 days), measured as the autocorrelation decay of daily funding.

**P3 (capacity is finite):** using `bookDepth`, the **$ notional at which market impact consumes half
the gross carry** is computed and reported; a symbol with impact-adjusted edge ≤ 0 is not tradeable at
any size and is reported as such.

**Pass requires P1 and P2; P3 is reported regardless.** Failure of P1 is a FAIL and is published as
such.

## 5. Estimator — fixed before running

- **Block bootstrap**: stationary bootstrap on daily portfolio returns, 10,000 resamples, mean block
  length 10 days; 95% percentile CI.
- **HAC**: Newey–West with 10 lags for the daily mean, reported beside the bootstrap.
- **Multiplicity**: the family is three variants (the registered 20%/5% rule, a 10%/0% variant, and a
  no-threshold always-on variant); the **deflated Sharpe ratio** and **Hansen's SPA** are computed over
  the three, with the registered variant as the candidate.
- **No fitting**: the signal has no free parameters beyond the frozen thresholds; if a variant is
  fitted on design data it is reported as such and excluded from the holdout.

## 6. Capacity and decay

- **Decay**: fit an AR(1) to daily funding; half-life = `ln(2)/−ln(φ)`, reported with bootstrap CI.
- **Capacity**: from daily `bookDepth` snapshots, estimate the price impact of a market order as
  `k × sqrt(notional)` (square-root law) by regression across snapshots; report the notional where
  impact = half the gross annualised carry.
- **Placebo suite**: (a) vol-matched random entry dates, 1,000 draws — the strategy's return must
  exceed 95% of them; (b) date-shifted signal (signal lagged 7 days, then applied) — decay must
  weaken it, not strengthen it; (c) a synthetic DGP with known funding and zero basis drift — the
  pipeline must recover the known carry within its CI.

## 7. Holdout — sealed

- Design: **2024-01-01 → 2024-12-31**. Selection and thresholds come from here only.
- Holdout: **2025-01-01 → 2025-06-30**, read **once**, after `research/carry_universe.csv` and this
  document are committed. The commit hash is the seal.
- The same rules, costs, and estimator apply. No re-tuning, no re-running with adjusted thresholds.

## 8. Reconciliation — what shows it is right besides us

1. **Funding totals**: our summed funding per symbol per month is reconciled against
   `premiumIndexKlines`-implied funding; the implied and published series must agree in sign on
   ≥ 95% of intervals and within 20% on average.
2. **Prices**: our perp close equals the published `klines` close, and the spot close equals the
   spot `klines` close, to the last digit.
3. **Third-party check**: on 10 randomly chosen symbol-days, the closing price is cross-checked
   against `aggTrades`' last print of the day.
4. **Independent implementation**: the final number is reproduced by a second query written in
   DuckDB SQL over the same Parquet files, and both are committed.

## 9. Outcomes — fixed

- **P1 and P2 hold on the holdout too**: carry is a real, decaying premium; the result is a capacity-
  limited, risk-compensated harvest.
- **P1 holds on design, fails on holdout**: a 2024 artefact; published as a failure with the same rigour.
- **P1 fails on design**: no deep test of #12 is warranted; the family is retired with the mechanism
  written down.

Nothing here trades. No order path is touched.
