# Pre-registration — maker-execution pilot (one day)

**Written before running.** This is a **pilot**, one venue-day, descriptive only: it cannot support
inference and is not BH-tested.

## Question

If limit orders rest at the touch, what is the fill rate, the spread captured, and the post-fill markout?
Can the sub-basis-point tape effects ever be captured as a maker?

## Data

Tardis Binance USD-M `SOLUSDT`, **2026-10-01** (already cached): `book_ticker` with sizes and `trades`.

## Procedure (fixed)

- Each minute, place a passive buy at the best bid with the visible queue ahead (`bid_amount`) and a
  passive sell at the best ask with `ask_amount`.
- A fill requires cumulative aggressive volume at or through the price to exceed the queue within 60 s
  (sell prints for the buy, buy prints for the sell).
- For filled orders: capture = distance from the fill to the mid at the next minute (half-spread, bps);
  markout = mid at +1 min and +5 min relative to the fill, signed to the position; adverse selection is
  the negative of the average markout.
- Report fill rates by spread quartile, median capture, mean markout at 1 and 5 minutes, and net.

## What it settles

Whether maker execution is a viable path for the seconds-scale tape effects, or whether adverse
selection eats the spread. A one-day pilot can only show the mechanics and flag concentration risk.

## Governance

One run, no tuning of horizon/queue assumptions; result in `research/RESULTS_maker.md`.
