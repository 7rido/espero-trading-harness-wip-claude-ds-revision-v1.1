# Reading the BTC tape

"Reading the tape" is reading **aggressor flow**: who is lifting offers, who is hitting bids, how large
those prints are, whether that aggression is moving price, and where volume has accumulated. It is a
description of who is paying, not a forecast.

## The measurable primitives

| concept | definition | our implementation |
|---|---|---|
| **Aggressor side** | the taker side of each print | Binance `is_buyer_maker == False` → taker bought |
| **CVD** | cumulative sum of taker buy minus taker sell volume | `research/tape.py::minute_table` |
| **Buy share** | taker buys ÷ total volume | same |
| **Blocks** | single prints above a notional threshold | `block_stats`, default **$100k** |
| **Sweeps** | several prints at the same millisecond and price | `sweep_stats`, ≥3 fills |
| **Volume profile** | volume by price bucket; POC = heaviest bucket; value area = 70% around it | `profile`, 0.1% buckets |
| **Absorption** | high aggressive volume that fails to move price | `absorption`: volume z ≥ 2 and \|return\| below the day median |
| **Delta divergence** | price makes a lower low while CVD makes a higher low (or the mirror) | `divergence`, 60-minute halves |

## What is *not* observable

- **Icebergs and spoofs**: trade prints cannot show hidden or cancelled size. The order book hints, but
  cancellations leave no trace in the tape. Any claim to "see" them from trades is inference, not data.
- **Intent**: a block print is a large trade, not necessarily an institution acting on information.
- **Consolidated tape**: Binance UM, Coinbase spot and Hyperliquid are separate books; aggregating them
  without a common clock misstates the flow.

## Canonical references

- Cont, Kukanov & Stoikov, [*The price impact of order book events*](https://export.arxiv.org/abs/1011.6402)
  — order-flow imbalance and short-horizon price impact, the quantitative basis of tape reading.
- Easley, López de Prado & O'Hara, *Flow Toxicity and Liquidity* (VPIN) — volume-synchronised measure of
  informed trading.
- Practitioner definitions of CVD and absorption (e.g. the CVD/absorbance write-ups circulating on
  TradingView and CoinMarketCap) describe the same quantities without the formalism.

## Our data

- **History**: Binance USD-M daily `aggTrades` archive, `BTCUSDT-aggTrades-YYYY-MM-DD.zip` (~21 MB/day,
  ~1.8M prints on 2026-10-29). Public, keyless, not geo-blocked.
- **Live**: Coinbase `/products/BTC-USD/trades?limit=1000` — last few minutes, **venue differs** from the
  history and is labelled `coinbase-spot`. The `side` field is assumed to be the aggressor side and is
  checked against the direction of the preceding print (a taker buy should print at or above the
  previous price more often than not); below 55% agreement the output says `side_verified: false`.
- **Not available**: Binance REST is geo-blocked here (HTTP 451), so live Binance flow is not used.

## What this panel is for

Situational awareness on the dashboard: is the move being sold or bought, are there large prints,
where is the volume shelf, is aggression being absorbed, is price/CVD diverging. It produces **no
label** and no trade; the forecast card remains the only place with labels, and it is capped at WATCH.
