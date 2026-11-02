# Order flow and liquidity map

A description of three things the market is showing now: where resting liquidity sits, which side is
paying in the tape, and where Hyperliquid's public positions would be forced out. It is **not a
signal**, has no ledger row and no order path.

Code: [`liquidity_map.py`](liquidity_map.py) · snapshot: `research/liquidity_map.json` (generated) ·
card: `espero2/dashboard.py::_liquidity_card`.

## The three layers

| layer | source | unit | window |
|---|---|---|---|
| **Resting pools** | Coinbase spot L2 book (`/products/{pair}/book?level=2`) | price bucket, USD notional | +/-2 % of the mid |
| **Order flow** | Coinbase spot trades (`/products/{pair}/trades`) | taker buy share, net USD | last 30 min or 1,000 prints |
| **Liquidation clusters** | Hyperliquid public positions (`clearinghouseState`, recorded hourly) | the venue's own `liquidationPx`, USD notional | positions within +/-30 % of the mark |

The book and trades are one venue; the liquidation ladder is another. They are labelled separately,
and every level is mapped from its own venue's reference price (Coinbase mid for pools, Hyperliquid
mark for liquidations). The snapshot records the cross-venue basis so the two scales are not confused.

## Resting pools

1. Keep book levels inside +/-2 % of the mid. The full Coinbase book contains orders far outside any
   useful range; those are excluded rather than allowed to dominate a bucket.
2. Drop levels within 5 bps of the mid: the touch is spread, not a pool.
3. Aggregate notional into 10 bps price buckets.
4. Rank the buckets, merge adjacent selected buckets into one zone, and keep the three largest zones
   per side. A pool's price is the notional-weighted average of its levels; its `share` is the pool's
   notional over all notional in the window on that side.

A pool is **resting size**, not committed size. Orders can be cancelled before they trade, and hidden
or iceberg orders do not appear at all. The book shows where a limit order was at the snapshot time.

## Order flow

Coinbase's trade `side` is treated as the taker side. The snapshot checks that assumption: a taker buy
should print at or above the previous print more often than not. `side_agreement` is recorded and
`side_verified` is false below 55 %. The card reports taker buy share, net taker USD
(buys minus sells) and the largest single print. When 1,000 prints cover less than 30 minutes, the
actual `span_min` is shown instead of the requested window.

This is venue flow, not consolidated tape: Coinbase spot, not the perp book and not Binance.

## Liquidation clusters

Hyperliquid publishes every account's positions and the liquidation price the venue computes for each
one. `hlcollect` records the top 2,000 accounts by account value every hour, and the sync job copies
the recordings into `data/hlcollect/`. The map reads the newest local snapshot.

1. Keep positions whose `liquidationPx` is finite and on the correct side of the mark: longs below,
   shorts above. A long whose liquidation price is already above the mark is not a forward level.
2. Keep the +/-30 % window. Further walls are recorded by the collector but not mapped.
3. Aggregate position value into 25 bps buckets, rank by notional, suppress a cluster within 50 bps of
   a larger one, and keep the three largest per side.
4. Report the sample's notional against venue open interest (`open_interest * mark`). The top-2,000
   sample is not the whole market; the coverage percentage is the honest denominator.

This is the **exact ladder**, not a Coinglass-style estimate from leverage tiers or open interest: the
liquidation price is Hyperliquid's own value for that account and position. It is still a sample and a
snapshot. Cross-margin liquidation prices reflect the account's whole collateral, so one position can
carry a liquidation price much farther away than its own leverage suggests. Positions outside the top
2,000, and accounts that failed during collection, are missing.

## What the map is not

- **Not a forecast.** It does not say price will reach a cluster or that a pool will hold. #26's
  forced-liquidation bounce is the only directional result in this repo, and the map does not compute
  it.
- **Not a full liquidation heatmap.** A forward heatmap needs every position's entry, size and
  leverage. Hyperliquid gives that for its own accounts only; other venues do not. No synthetic
  leverage distribution is invented here.
- **Not a consolidated book.** Coinbase spot depth is not Hyperliquid perp depth. The basis is in the
  snapshot.
- **Not a trade trigger.** Nothing in `liquidity_map.py` writes a signal, touches the ledger or reaches
  an order path.

## Running it

```bash
python research/liquidity_map.py                  # BTC, ETH, SOL
python research/liquidity_map.py --coins SOL      # one market
python research/liquidity_map.py --hl-dir data/hlcollect --out /tmp/map.json
```

The optics launchd job runs it after `forecast` and before `tape --live`, every 15 minutes. The liquidation ladder is only
as fresh as the newest `hlcollect` recording; the card labels its age and flags a snapshot older than
two hours. A missing local snapshot leaves the pools and flow in place and says so.

## Snapshot fields

| field | meaning |
|---|---|
| `mid`, `mark`, `spread_bps`, `basis_bps` | Coinbase mid and spread; Hyperliquid mark; mark/mid basis |
| `flow` | prints, actual span, taker buy share, net USD, largest print, side check |
| `pools[]` | side, price, distance %, USD, share of side, levels, bucket bounds |
| `clusters[]` | side, price, distance %, USD, long/short split, position count, share |
| `ladder` | sampled positions, coverage against OI, nearest long/short, snapshot time and age |
| `windows` | the +/-2 % pool window, +/-30 % liquidation window, and flow minutes |

## References

- Coinbase Exchange API, [products book](https://docs.cdp.coinbase.com/exchange/docs/welcome)
  and [trades](https://docs.cdp.coinbase.com/exchange/docs/welcome).
- Hyperliquid API, [info endpoint](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)
  (`clearinghouseState` carries `liquidationPx`).
- Cont, Kukanov & Stoikov, [*The price impact of order book events*](https://export.arxiv.org/abs/1011.6402)
  — why book depth and order flow are separate measurements.
- The original corpus's idea 3, [`reference/IDEAS_NOVEL.md`](../reference/IDEAS_NOVEL.md), for the
  exact-ladder mechanism and its limits.

## Dashboard evidence

`research/screenshots/liquidity-map-before.png` and `-after.png` are 1500 × 1600 crops of the same
frozen dashboard at a 1500 × 7600 viewport: baseline `16eee49` (tape then carry sleeve) and this
branch (tape, then the map, then carry). The surrounding cards, data snapshot and theme are identical.
