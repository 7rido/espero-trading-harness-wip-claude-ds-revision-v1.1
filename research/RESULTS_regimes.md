# Result — do regime states carry information? (RG1)

**Verdict: on the validation year, no. Not one of the nine families separates forward 5-day market
returns after multiplicity.** On the sealed holdout one family (average correlation) appears at
t 3.26 — but it was flat on validation (t 0.32), so it is a holdout-only observation, not a regime
law, and it cannot gate anything under this registration.

Seal: `71fc5ea` (`research/PREREGISTRATION_REGIMES.md`). Code: `research/regimes.py`, data
`research/regimes.csv`, numbers `research/regimes.json`.

## Validation 2023 — the gate

| family | diff (5d) | NW t | perm p | FDR |
|---|---|---|---|---|
| trend_20d | +102.6 bps | 1.27 | 0.036 | fail |
| dd_ok | −91.5 | −1.05 | 0.032 | fail |
| liq_high (liquidity) | +56.0 | 0.89 | 0.232 | fail |
| volofvol_low | −93.2 | −0.82 | 0.176 | fail |
| trend_sma | +56.1 | 0.66 | 0.206 | fail |
| vol_har | −44.0 | −0.63 | 0.588 | fail |
| breadth_high | +48.8 | 0.61 | 0.290 | fail |
| corr_high | +28.4 | 0.32 | 0.516 | fail |
| har_trend | −23.0 | −0.27 | 0.608 | fail |
| trend_200 | −10.4 | −0.12 | 0.832 | fail |
| funding_pos | n/a | — | — | one state has 15 days |

Nothing clears BH at 10% across eleven tests. The combined **har_trend** gate — the one proposed for
E1 — is −23 bps with t −0.27: indistinguishable from nothing.

## Holdout — read once (after two code fixes, disclosed below)

| family | diff (5d) | NW t | perm p | FDR | halves |
|---|---|---|---|---|---|
| **corr_high** | **+330.4 bps** | **3.26** | **0.000** | **PASS** | +100.8 / +429.3 |
| trend_20d | −148.5 | −1.38 | 0.014 | PASS | −256.1 / −138.5 |
| liq_high | +116.5 | 1.36 | 0.070 | fail | −7.6 / +53.7 |
| trend_sma | −140.3 | −1.31 | 0.036 | fail | −165.2 / −558.7 |

`corr_high` says: when the cross-section is more correlated than its design median, the next five
days of the market index are **+330 bps** better than when it is not. It is the only family that
passes FDR on the holdout with both halves positive. `trend_20d` passes FDR too but with the
**opposite sign** to validation — an unstable state, not a finding.

## What this establishes

1. **The user's prior was right**: these regime definitions, as specified, do not separate forward
   market returns on 2023 at any standard that survives multiplicity.
2. **A holdout-only signal is not a result.** `corr_high` failed validation (t 0.32) and succeeded on
   holdout; one of those two windows is noise, and the registration says validation decides.
3. **`funding_pos` is not a usable state**: funding is positive on 2,221 of 2,282 days, so the
   "negative funding" regime barely exists.
4. **Gating E1 on har_trend would have been decoration** — −23 bps, t −0.27 in validation.

## Disclosures

- The evaluation had **two bugs**, both fixed before the numbers above: an OLS/NW covariance error that
  produced t-statistics in the hundreds, and a state/NaN handling bug that made some halves NaN. The
  holdout was therefore read three times in total, all within this registration and all for code
  fixes, never for tuning. The first two readings are void.
- `liq_stress` (liquidation-stress regime) is **not testable**: COIN-M liquidations start in 2023-06,
  so there is no design-window median to threshold against. It was not included in the FDR.
- Thresholds are design medians/terciles, fixed in the prereg.

## What would be a legitimate next step

`corr_high` gets its own registration with a **validation window it has not seen** (e.g., 2024 as
validation, holdout 2025-07…2026-03), and the selection cost counted in the trial budget. Testing it
again on the same holdout would be the mistake this project exists to avoid.
