# Result — tape study 2: OFI works at seconds, block aggressors get better fills

**Headline: at 30–60 seconds, order-flow imbalance predicts direction (BH-significant), but the edge is
0.13–0.22 bps — 40–70× below the 9 bps cost. Large prints (>$1M) earn a drift-adjusted markout of
+0.78 bps; mid-size prints lose money for their aggressor.**

Registration: `research/PREREGISTRATION_tape_2.md` · code: `research/tape_study2.py` · data:
`tape_study2.json`. 29 cached days of Binance UM BTCUSDT aggTrades.

## H5 — seconds-scale OFI

| horizon | spread | t | BH |
|---|---|---|---|
| **30 s** | **+0.22 bps** | **6.16** | ✅ |
| **60 s** | **+0.13 bps** | **2.40** | ✅ |
| **180 s** | **−0.49 bps** | **−2.09** | ✅ |

The sign flips by 180 s: imbalance predicts continuation at seconds and reversal at minutes. This is
the Cont–Kukanov–Stoikov effect, and it is real — but 0.22 bps against a 9 bps round trip is not a trade.

## H6 — markout by print size (raw vs drift-adjusted)

| size | 10 s raw | 10 s adj | 60 s raw | 60 s adj |
|---|---|---|---|---|
| < $10k | +0.51 | +0.01 | +0.49 | +0.01 |
| $10k–100k | +0.42 | **−0.08** | +0.35 | **−0.13** |
| $100k–1M | +0.62 | +0.12 | +0.56 | +0.08 |
| **> $1M** | **+1.28** | **+0.78** | **+1.24** | **+0.77** |

Raw markout is dominated by intraday drift (every bucket positive, t ≈ 15–29), so the **drift-adjusted
column is the informative one**: million-dollar prints get ~+0.8 bps better fills than the small/mid
sizes, and the $10k–100k bucket is actually negative. Post-hoc adjustment is labelled as such; the
registered statistic was raw markout, which is reported too.

## H7 — session structure (descriptive)

Flow peaks in the **13:00–16:00 UTC** window (81–96k prints/hour vs ~30k at 06:00), and the largest
per-print moves cluster there. Asia hours are thinner and slower.

## What this means

1. **The tape has predictive content only at seconds.** At 5–60 minutes (study 1) nothing survived; at
   30–60 seconds OFI is significant. Both are economically untradeable at 9 bps costs.
2. **Blocks are different flow.** > $1M prints earn positive markout while $10–100k prints lose; if you
   ever execute, size tells you whether the counterparty was informed.
3. **Nothing here authorises a trade.** The result is a mechanism, not a strategy; a tradeable version
   would need maker execution, sub-second data, and costs near zero.

## Limits

- One month (2026-10), one venue, 29 days.
- Drift adjustment is crude; it removes common drift, not size-specific beta.
- Markout uses last trade price, not mid — bid-ask bounce is inside every number.
- No order-book data paired with prints; VPIN/toxicity remains untested.

## Would change the verdict

Maker-execution study with book data (can the 0.2 bps be captured as a maker?), and a 6–12 month sample.
That is a new registration, not a re-run.
