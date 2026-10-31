# Pre-registration — do regime states carry information? (RG1)

Written **before any regime-state test is computed**. Design thresholds are fixed below; the holdout
2025-07 → 2026-03 is not read until the seal commit exists.

## 1. Why

Nine regime definitions are candidates for gating strategies, and the user's prior is that none of
them works. That is exactly the kind of claim this project tests rather than assumes: the question is
not "does a regime exist" (all do, by construction) but **does the state separate forward returns**.

Gating a strategy on a regime that carries no market information only shrinks the sample and fits
noise. This registration tests the gate before it is used to gate anything. **Nothing trades.**

## 2. Data and windows

- `bars_daily` (42 symbols, 2020-01 → 2026-03), `rv`, `funding` (108k rows), `liq2` (COIN-M daily
  liquidations, 2023-06 → 2024-10, where it exists).
- **Design 2020-01-01 → 2022-12-31** (thresholds only: terciles/medians).
- **Validation 2023-01-01 → 2023-12-31** (evidence).
- **Holdout 2025-07-01 → 2026-03-31**, read once, after the seal.

## 3. The nine families — exact definitions

Market index `M` = equal-weight log price of all symbols with data that day.

| family | risk-on state | threshold |
|---|---|---|
| trend_sma | `SMA20(M) > SMA50(M)` | none |
| trend_200 | `M > SMA200(M)` | none |
| trend_20d | `M/M[-20] − 1 > 0` | none |
| vol_har | HAR-RV forecast **below** design median | median fitted on design |
| volofvol | std of last 20 daily RV **below** design median | median on design |
| breadth | share of symbols above their own 50d MA **above** design median | median on design |
| corr | average pairwise 30d correlation **above** design median | median on design |
| funding | universe median daily funding **≥ 0** | zero |
| drawdown | `M` drawdown from 90d high **< 10%** | none |
| liquidity | universe median quote volume **above** design median | median on design |
| liq_stress | 24h liquidation USD **below** design median | where liq2 exists |

A combined state, **har_trend**, is also fixed: `vol_har risk-on AND trend_200 risk-on`.

## 4. The test — fixed

For each family, on validation 2023:

- forward 5-day **market return** after the state is known (`M[t+5]/M[t] − 1`);
- mean forward return in the risk-on state minus the mean in the risk-off state;
- Newey–West t with 5 lags on that difference;
- **Benjamini–Hochberg FDR at 10%** across the ten tests (nine families + combined);
- sign must be the same in both halves of 2023.

A family "carries information" only if the difference survives FDR and the halves agree.

## 5. Outcomes — fixed

- **A family passes**: it may gate a strategy only through a *new* registration, with the gate's
  selection cost counted in the trial budget. No strategy is authorised by this test.
- **Nothing passes**: the honest conclusion is that these regime definitions do not separate forward
  market returns at this sample size, and gating on them would be decoration. Reported as a negative
  result; the holdout is still read once to confirm the null.
- The combined `har_trend` state is reported separately whether or not a single family passes.

## 6. Disproof suite

1. **Shuffled states** (random labels preserving counts) — the difference must vanish.
2. **Shifted states** (+5 days) — the effect must weaken.
3. **Both halves** — sign agreement is part of the criterion.
4. **Cost of gating**: report the share of days/trades removed by each gate.

## 7. What this refuses

- Choosing the threshold after seeing validation; testing a tenth definition discovered later
  without counting it; re-reading the holdout for a second family.
