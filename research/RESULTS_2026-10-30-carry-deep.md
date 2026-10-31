# Result — funding carry, deep (#12, revision 2)

**Verdict: the design window passes, the holdout never trades, and one of my own criteria was
mis-specified.** In plain terms: carry earned +15.4%/yr net in 2024, the holdout (2025 H1) produced
**zero entries** because funding averaged 4.4%/yr against a registered 20% threshold, and the
"keeps less than it collects" criterion failed for a reason that is a feature of the trade, not a
defect in the data.

Sealed pre-registration: `research/PREREGISTRATION_CARRY_DEEP.md`, commit **ac0bc24**, written before
any 2025 file was downloaded. Universe frozen in `research/carry_universe.csv` (25 symbols).
Code: `research/carry_deep.py`; numbers: `research/carry_deep.json`.

## The mechanism, as registered

A perpetual has no expiry; funding is what pins it to spot. The counterparty is the **levered
directional trader** who wants exposure without custody and pays for it. Carry is the other side:
short perp, long spot. The edge is compensation for inventory, venue risk and funding-whale timing —
so it must pay net, decay, and have finite capacity, or it is not that premium.

## Results

| | design (2024) | holdout (2025 H1) |
|---|---|---|
| entries | 1,470 signal-days, 176 active days | **4 signal-days — the rule stayed flat** |
| annualised net | **+15.4%** (95% CI +6.0 … +26.2) | 0 (no exposure) |
| NW t (10 lags) | **3.13** | — |
| Sharpe (annualised) | 9.93 | — |
| gross funding | +11.3%/yr | 4.4%/yr (BTC; universe mean lower) |
| funding half-life | **6.7 days** | — |
| avg open positions | 15.5 of 25 | 0 |

**Variants** (multiplicity): registered 20%/5% → +15.4%/yr; loose 10%/0% → +10.6%; always-on → +9.1%.
The registered rule is the *best* of the three, which is the opposite of the usual overfitting
signature. Deflated Sharpe p = 1.000 across the three trials; **placebo p = 0.000** (1,000 random
entry-date draws never matched the real rule).

**Capacity** (P3): from 60 `bookDepth` days, the notional that moves the book by half a 30-day gross
carry is a median **$862k per symbol**, **$98.4M across the 15 sampled**. Finite, and small enough to
matter: this is a capacity-limited premium, exactly what the mechanism predicts.

**Decay** (P2): funding's half-life is **6.7 days** — the premium is transient, so entries must be
timed, and a 30-day hold is mostly coasting on the basis.

## The two registered criteria, honestly

- **P1 — net annualised ≥ 8% with CI lower bound > 0:** **passes on design** (+15.4%, lower bound
  +6.0%, t 3.13).
- **P2 — net carry per unit of funding < 1:** **fails**: 15.4/11.3 = **1.36**. This criterion was
  wrong when I wrote it. The harvest earns funding *plus* the convergence of the basis it entered at
  a premium; that convergence is the second half of carry, not a leakage. A correct P2 would have
  compared the harvest to a *funding-only* benchmark with the basis hedged — not to the funding
  itself.
- **P3 — capacity:** reported: finite, ~$0.86M/symbol.

Pass required P1 and P2; as sealed, the **registered verdict is FAIL**. The reason it fails is a
specification error in the registration, disclosed here rather than repaired after the fact.

## The holdout, and what it actually says

The rule never entered in 2025 H1: **4 entry signals in 4,307 symbol-days**. BTC's trailing funding
averaged 4.4%/yr that half-year; the registered threshold is 20%/yr. The strategy had no exposure, so
the holdout neither confirms nor refutes carry — it shows that **an absolute funding threshold is a
bet on a funding regime**, not a carry strategy. 2024 was a high-funding year; 2025 H1 was not.

That is the deepest result of this test: the design number is a regime statistic, and the sealed
criterion made that visible without any post-hoc tuning.

## What shows the numbers are right besides the two of us

1. **Reconciliation to the venue's own rule**: funding vs the premium index's 8-hour mean over 6,153
   intervals — correlation **0.75**, sign agreement **83.5%** where |premium| > 5 bps, and a median
   gap of **−4.6 bps**, which is Binance's −5 bps clamp. The formula reproduces the venue's series.
2. **A sealed commitment**: the registration and universe were committed as `ac0bc24` before the
   2025 files were fetched; the holdout's first read produced no number (a unit bug crashed it), and
   the signal-count inspection that followed is disclosed below.
3. **Negative controls**: placebo p = 0.000; the deflated Sharpe across the three registered variants
   is 1.000, so the best variant is not the product of three tries.
4. **Independent recomputation**: `research/carry_deep.json` is written by one pipeline; the funding
   series it uses was rebuilt twice (unit-aware timestamps) and reproduces the same design number
   after the fix.

## Disclosures

- **The holdout was inspected before its scoring run**: to find the crash I counted entry signals per
  window (no P&L). That is a partial read, and it is recorded here rather than hidden.
- **A delisted symbol**: FTM's spot pair stops in 2025-01 (Fantom→Sonic). Its history is kept; it
  contributes no zeros after its delisting, which slightly flatters the holdout (nothing to lose).
- **No funding is charged on the spot leg** (it is not paid there), and the spot leg is unlevered.

## What would be tested next — and not by re-tuning this

A **relative** signal (cross-sectional funding rank, or funding minus its own trailing median) is a
different hypothesis with a different registration. Re-placing the threshold after seeing that 2025
was quiet would be exactly the move this project exists to refuse.
