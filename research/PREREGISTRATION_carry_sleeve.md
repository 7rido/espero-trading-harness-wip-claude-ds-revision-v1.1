# Pre-registration — delta-neutral funding-carry sleeve (paper)

**Written before any sleeve code exists or any carry P&L is computed.** This registers a paper test of a
premium, not an alpha claim: the sleeve is paid to hold the other side of crowded longs.

## Question

On Hyperliquid, can a delta-neutral spot-long / perp-short sleeve earn the funding rate **net of costs,
basis drift and funding flips**, over a 30–60 day paper window?

## Venue and legs (fixed)

| leg | venue | instrument |
|---|---|---|
| long | **Coinbase Exchange** | spot (BTC-USD, ETH-USD, SOL-USD) — real prices, no wrapped asset |
| short | **Hyperliquid mainnet** | perp (BTC, ETH, SOL), 1× notional, 50 % margin buffer |

HL **spot is not used for the long leg**: it is wrapped UBTC, the asset-context endpoint reports wrong
prices, and the book is thin. Coinbase spot is the reference.

## Universe and sizing

- **BTC, ETH, SOL** only (top HL open interest, deepest spot books).
- Paper capital **$10,000** total; **$1,000 notional per coin** per side (30 % of measured capacity,
  which was ~$0.86M/symbol for this universe).
- Delta target: spot notional = perp notional within ±2 %; rebalance when outside.

## Entry (fixed thresholds)

Enter a coin when **all** hold at the 00:00 UTC check:

1. HL 7-day mean funding, annualised, **≥ 5 %**.
2. HL perp mark is **at or above** the spot mid (basis ≥ 0) — do not start into an inverted basis.
3. The coin's spot spread is ≤ **5 bps** at entry (execution sanity).

## Accrual and P&L

- Funding settles **hourly** on HL; the short receives when the rate is positive, pays when negative.
- Both legs marked at the daily close; **delta P&L** (spot move + perp move) should net near zero and is
  reported separately from funding.
- Fees: **Coinbase spot 5 bps taker**, **HL perp 4.5 bps taker**, **2 bps slippage per fill** — round trip
  ≈ **23 bps** per side-pair, charged on entry and exit.

## Exit (fixed)

Exit the sleeve when any hold:

1. HL 7-day mean funding, annualised, **< 0 %** for **two consecutive daily checks**.
2. Basis inverted by more than **−10 bps** for two consecutive days.
3. Short-leg margin buffer falls below **25 %**.
4. Paper window ends.

## Primary metric and decision rule

Over the window, report per coin and total:

- **funding capture ratio** = net funding received ÷ gross funding accrued (target **≥ 0.70**),
- **net P&L** in bps of capital, cumulative and daily mean,
- realised vol, max drawdown, funding-flip count, fee drag, delta drift,
- attribution: funding vs basis vs fees vs delta residual.

**Pass** = funding capture ≥ 0.70 **and** net P&L > 0 over at least 30 daily observations. A pass gives the
sleeve a ledger row `trial` — **never `holds`**. A fail is reported as a fail; no re-running with new
thresholds.

## Data needed

- HL funding history (have: `funding_multi`, hourly `fundingHistory`), HL mark/premium (have: optics),
- Coinbase spot quotes and fills (have: keyless ticker/book; paper fills),
- daily snapshots persisted for the window (`research/carry_sleeve.json`).

## Known risks (accepted, not solved by the rules)

- **Funding flips**: the 30-day mean has been as negative as −29.6 %; the exit rule is two daily checks,
  so one bad day is absorbed.
- **Short-leg liquidation**: 1× with a 50 % buffer; a 2× adverse move would breach it — the sleeve is
  delta-neutral, so this should be rare, but basis gaps can move the perp against the spot.
- **Venue split**: the hedge lives on two venues; a venue outage leaves one leg naked.
- **Costs dominate small rates**: 23 bps round trip needs roughly 30 days of 5 %/yr funding just to break
  even on entry/exit.
- **Stablecoin/withdrawal risk** on both venues.

## Window and governance

- **Paper window**: 2026-11-01 → 2026-12-31 (61 days), or until the exit rule fires per coin.
- One run, thresholds fixed here; every observation reported; no tuning after the first P&L is seen.
- Implementation only after this registration is committed: `research/carry_sleeve.py` (paper ledger +
  daily snapshot), a launchd daily job, and a dashboard row.

## Out of scope

- Real orders, leverage beyond 1×, other venues, options/basis-futures carry, portfolio optimisation,
  tax treatment.
