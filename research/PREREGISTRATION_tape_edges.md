# Pre-registration — tape edges: forced/urgent flow analogues of the liquidation mechanism

**Written before any holdout data is fetched or read.**

## Why

The liquidation edge works because the seller is *forced* (margin), so the concession is temporary. The
tape carries analogous "someone had to trade" signatures. Four mechanisms, fixed thresholds, one design
run, one sealed holdout. This is not a pattern search: no combinations are tried.

## Data

- **Design**: 2026-10-01 → 2026-10-30, the 29 cached Binance UM `BTCUSDT` aggTrades days. *Disclosed:
  these days were used by tape studies 1–2.*
- **Sealed holdout**: **2026-08-01 → 2026-09-30** (61 days), fetched only at holdout time, read once.
- Minute outcomes from aggTrades; entry at the **next minute's close**; horizons fixed below.

## Hypotheses (fixed)

| id | event | direction | horizons |
|---|---|---|---|
| H1 sweep exhaustion | minute with ≥ 2 sweep clusters (≥ 3 fills same ms+price), \|ret\| ≥ 2× the day's minute-return σ, and taker flow sign = return sign | **against** the move | 15, 60 min |
| H2 absorption | volume z ≥ 3 and \|ret\| ≤ 0.5× the day's median \|ret\| | **against** the prior 15-minute move | 30, 60 min |
| H3 block continuation | first print ≥ $1M after ≥ 10 minutes with no block; direction = taker side | **with** the print | 5, 15 min |
| H4 divergence | price at a 60-minute extreme and the 60-minute halves diverge (price lower low + flow higher low, or mirror) | bullish → long, bearish → short | 60 min |

## Statistics

- Signed forward return per event (bps), entry at next minute close.
- Per-day mean of signed returns; **t across days** (two-sided 5%); **BH at 10% across the 8 cells**.
- Economic bar: **9 bps** round trip; report gross, net and median beside each cell.
- Cells with < 10 event-days are reported as `insufficient`.

## Decision rule

- If no design cell passes BH **and** beats 9 bps → the holdout is never run; result is "design failed".
- If ≥ 1 passes → seal the design hash, then run the holdout **once**; a cell is a finding only if it also
  passes BH and the cost bar on the holdout.
- A finding does **not** authorise a trade: the ledger would get at most an `R11 trial` row, never `holds`.

## Governance

One design run; no threshold tuning; all cells reported; the holdout guard checks a committed SHA-256
of the design result and aborts otherwise. Results in `RESULTS_tape_edges_design.md` and
`RESULTS_tape_edges_holdout.md`.
