# Answer — did XS momentum fail because the signal decayed, or because the trades were unexecutable?

**One number:** the 2023 holdout book, repriced at **$1M per side** with measured impact, earns
**+26.4%/yr** against the registered **+27.8%/yr** — execution costs **1.4 percentage points**, and the
verdict is unchanged (registered CI −36.4 … +92.5, t 0.75). **Signal decay, not execution, is what
failed the test.** Execution does cap the strategy: at $5M per side net falls to **+7.0%**, at $10M to
**−16.0%**.

## The substrate this rests on

`data_substrate/substrate.duckdb` (DuckDB), built by `research/substrate.py`:

| table | rows | known_time |
|---|---|---|
| bars (2021–2024, UM perps) | 128,959 | file mtime per archive |
| funding | 108,374 | file mtime |
| premium index | 13,675 | file mtime |
| depth (bookDepth snapshots) | 1,728,000 | file mtime |
| prints (aggTrades samples) | 10 | file mtime |

`valid_time` is the venue date; `known_time` is when the file was fetched — so a query can ask what
was knowable on a date. **Duplicates: 0** in every table. Gaps are reported per symbol (largest: 4
days). Manifest: 6,664 files hashed (`data_substrate/manifest.sha256`).

**The universe is a query**, not a frozen file:
`research/substrate.py universe 2022-12-31 47` → top 47 by trailing 30-day volume, deduped by base
asset. It overlaps the frozen list **32/47**; the differences are the trailing window versus the
two-year sum used at seal time, and LUNAUSDT, which traded in the design window and no longer exists.

## Execution repriced

From 112 `bookDepth` days, the median notional inside 1% of mid is **$1.83M**; impact is modelled
linearly inside that band (the only defensible shape from snapshot data).

| book | gross | $100k/side | $1M | $5M | $10M |
|---|---|---|---|---|---|
| XS 2021–22 (design) | +112.6% | +108.1% | +103.7% | +84.5% | +61.3% |
| XS 2023 (holdout) | +35.3% | +30.8% | **+26.4%** | **+7.0%** | **−16.0%** |

Carry, repriced per position: impact adds 12 bps per round trip at $100k (1.0%/yr drag), 125 bps at
$1M (10.0%/yr), 200 bps at $5M (16.0%/yr).

## The decay side

The same book, same rule, gross weekly spread:

```
2021-22   278.7 bps/week
2023       71.0 bps/week      −69%
```

Against that collapse, a 5 bps fee plus ~4 bps of impact is a rounding error. The test failed because
the effect shrank by two thirds, not because the book could not be traded.

## Why the detector cannot call it either way

`research/calibration.py` — synthetic markets with known alpha, 200 sims each:

| true alpha | estimate | 95% band | share positive |
|---|---|---|---|
| 0 | +3.2% | −80.6 … +88.0 | 0.51 |
| 0.1%/wk | +10.4% | −73.4 … +95.1 | 0.58 |
| 0.2%/wk | +17.5% | −66.3 … +102.3 | 0.63 |
| 0.4%/wk | +31.9% | −52.1 … +116.6 | 0.77 |

The pipeline is unbiased at the null and recovers large effects, but the band is **±80%/yr wide**:
at the holdout's effect size, a t of 0.75 is what the detector gives even when an effect exists.
Any future claim at this scale needs more days, more names, or a narrower construction — not a
different threshold.

## Trial budget

| id | test | t | p | verdict |
|---|---|---|---|---|
| R1 | #21 liquidation spikes | 0.85 | 0.395 | FAIL |
| R2 | #26 forced bounce (replication) | 7.11 | 0.000 | replicated |
| R3 | carry deep | 3.13 | 0.0017 | FAIL (holdout flat) |
| R4 | XS momentum deep | 2.23 | 0.026 | FAIL (holdout) |
| E1 | executable liquidation bounce | — | — | pending 2027-04-30 |

Five registered, three new, two replications, two failed on their holdout, one pending. The deflated
Sharpe for the best completed test (R2) across four trials is 1.000 — but R2 is a **replication of an
in-sample claim**, not a new one, so it does not consume the budget the way a discovery would.

## Reconciliation

- **Funding vs premium index** (6,153 8-hour intervals): correlation **0.75**, sign agreement
  **83.5%** where |premium| > 5 bps, median gap **−4.6 bps** — Binance's −5 bps clamp, reproduced.
- **Prices vs tape**: 10/10 random 2023 symbol-days match the `aggTrades` last print.
- **Vendor overlap: not available.** No Tardis/Kaiko access in this environment; stated as a gap, not
  faked.

## Queue simulation — the registered gap, closed after the answer

`research/queue_sim.py` ingests one day (2023-07-10) of `bookTicker` and `aggTrades` for 11 symbols:
**45.5M quote updates, 3.3M trades**. Quoted and **effective half-spreads are identical** (0.21–3.82
bps), so takers pay the touch; maker orders fill in a minute 22–87% of the time with a 5 s markout of
−1.0 to −2.2 bps. That makes the earlier linear-impact reprice **conservative**: measured spread plus
fee is ~6 bps a side, so the holdout net at $1M/side is closer to **+29%/yr** than +26.4% — better, and
still t 0.75. See `research/RESULTS_queue_execution.md`.

## What the substrate cannot do, stated plainly

- `bookTicker` is now ingested for **one day and eleven symbols** (45.5M rows); impact beyond the
  touch still comes from depth snapshots, so large orders remain modelled.
- Depth covers **15 symbols** out of 47; missing symbols fall back to the peer median and the coverage
  is reported with every number.
- No live fills: the ultimate referee remains untested.

Even with those gaps, the decomposition is stable in sign: **the holdout book is not killed by
execution at the size a desk would actually run; it is killed by the signal shrinking, and it is
capped, not killed, by liquidity.**
