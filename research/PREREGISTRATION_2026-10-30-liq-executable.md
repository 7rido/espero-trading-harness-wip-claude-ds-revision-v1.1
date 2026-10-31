# Pre-registration — the executable forced-liquidation bounce (E1)

Written **before the forward window exists** (the first event can only be recorded from 2026-10-31).
What had been seen: #26's in-sample numbers, and the in-sample reading of this same rule in
[RESULTS_2026-10-30-liq26-replication.md](RESULTS_2026-10-30-liq26-replication.md). That is disclosed
and is the basis of the power estimate below; it is not a look at forward data.

## Why

#26 passed with a **within-day** tag: whether a break was "forced" depends on the day's whole
liquidation distribution, known only after the close. #45 forward-tests that rule, but its verdict
will not say whether the rule is tradeable. The tag can be made causal: classify today's break against
**yesterday's** forced-share terciles. In sample that keeps 2/3 of the effect.

## Data — fixed

- **Events.** The feed behind #27's ledger: aggr's 5-minute liquidations (Binance USDⓈ-M, Bybit, OKX)
  on aggr's 14 coins, recorded by the maintainer's 07:30 job and copied here by `scripts/sync_from_original.py`.
- **Prices.** Binance USDⓈ-M 5-minute bars as #24 records them (`data/lows/forward`), entry at the next
  bar's open after the break's close.
- **Window.** UTC days **2026-10-31 → 2027-04-30** (183 days). Days with fewer than 6 events are
  dropped, as in #26.
- **No re-derivation of the feed.** If the ledger does not record it, it does not exist; a gap is
  reported, never filled.

## The rule — executable, no hindsight

1. Break = #26's: close making a new 4-hour extreme, volume z ≥ 2, hour's burst in the break direction.
2. Forced share `s` = liquidations on the break's side in the hour before ÷ that hour's quote volume.
3. **Tag today's event against the previous UTC day's terciles of `s`** (that day's 33rd and 67th
   percentile across all coins): above the 67th → forced, at or below the 33rd → organic, else middle.
   A day without events has no terciles and its events are middle (not traded).
4. Trade: **buy** forced down-breaks. Hold 4 h, 12 h and 1 d. Exit at the close of the bar ending at
   entry + h; a missing bar drops that trade.
5. Costs: **9 bps** round trip (two Hyperliquid taker fills) + Hyperliquid funding over the hold,
   realised hourly. Net is the verdict number; gross is reported beside it.

## Statistics

- **Trade-weighted** mean across events, with **day-clustered** standard errors (the #44 standard).
- One observation per event; days are clusters, not weights.

## Criteria — PASS needs all four

1. **4 h net > 0** with **t ≥ 3** (trade-weighted, day-clustered);
2. **12 h net > 0** and **1 d net > 0**, each with t > 2;
3. **Not one stretch**: 4 h net > 0 in both halves (2026-10-31 → 2027-01-30; 2027-01-31 → 2027-04-30);
4. **The effect is the bounce, not a trend**: D (forced − organic, 1 h, prior-day tags) < 0 with t ≤ −2.

## Power, stated in advance

In-sample prior-day 4 h is +32.0 bps gross with t 4.01 on 427 days. A six-month window will have
roughly 120–150 days with breaks and fewer events per day than the 26-coin sample (14 coins, one venue
family). Expect t near 2.5–3.5 at 4 h if the in-sample effect holds at half strength, which is why the
4 h bar is the primary criterion and 12 h / 1 d are confirmations.

## Outcomes — fixed now

- **PASS (all four)**: the executable rule is confirmed on unseen days; a paper account may be considered.
- **1–2 pass, 3–4 fail**: real but fragile; retire or re-register with a different horizon, never re-tune this one.
- **Anything else: FAIL.** Not re-tuned.

## What would void it

- Changing the tag definition, the horizons, the cost model or the coin set after seeing any forward day.
- Reading interim P&L and stopping early.
- Filling a data gap with a re-derived feed.
