# espero2

Paper trading and testnet execution on Hyperliquid. Three rules, enforced in code:

1. **A strategy cannot run without a ledger row** (`strategy_ledger.csv`), and `holds` needs a
   valid statistic *and* a cost bar.
2. **Fills are charged**: taker at the far touch plus slippage, fee from the venue table.
3. **Signing is testnet-only** and needs three independent opt-ins.

```bash
python -m espero2.cli book   --coin BTC                 # testnet touch
python -m espero2.cli ledger                            # what may run, and why
python -m espero2.cli run    --coin BTC --once --allow-plumbing
python -m espero2.cli run    --coin BTC --coin ETH --loop --every 60 --allow-plumbing
python -m espero2.cli report                            # journal summary
python -m espero2.cli state                             # testnet account (read-only)
python -m espero2.cli order  --coin BTC --side buy --notional 12 --confirm-testnet
python -m unittest discover -s tests -t .               # 19 tests
```

## Two front doors

```bash
python -m espero2.cli ui                     # terminal home screen (rich + questionary)
python -m espero2.cli dashboard --open       # self-contained HTML page
```

The TUI is the daily driver: a header with heartbeat and total, one row per coin (equity, change,
position, mini curve), the strategy ledger, and four actions — run a cycle, open the dashboard,
check health, quit. Every action is also a plain command; it is a front door, not a second
implementation.

```
╭──────────────────────────────────────────────────────────────────────────────────────╮
│ ▗▄▄▄▄▄▄▄▐▛██▜▌   espero2  paper accounts  $3,000.00                                  │
│ ▝▜██████▜████▛▘  heartbeat 6s ago  ·  ok  ·  every 60s  ·  journal paper.db          │
│   ▘▘ ▝▝  ▘▘ ▝▝   books  BTC 62 marks  ·  ETH 8 marks  ·  SOL 8 marks                 │
╰──────────────────────────────────────────────────────────────────────────────────────╯
  account       equity      day       P&L    curve                               holds
  BTC        $1,000.00    +0.00    +0.00%    ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁    flat
  ETH        $1,000.00    +0.00    +0.00%    ▁▁▁▁▁▁▁▁                            flat
  SOL        $1,000.00    +0.00    +0.00%    ▁▁▁▁▁▁▁▁                            flat

recent orders
  time    coin    side    qty    price    fee    why
  —                                              none yet

strategy ledger
  id    strategy    status      statistic    cost bar    note
  P1    sma         plumbing    na           na          reference strategy; no claim to an edge
```

## The dashboard

```bash
python -m espero2.cli dashboard --open        # writes dashboard.html and opens it
```

A self-contained page (no server, no JS framework) with one card per coin — equity, change,
position, sparkline — the order history, and the strategy ledger. It reloads itself every 30 s, and
the supervised loop rewrites the file after every cycle (`--dashboard`), so the tab follows the book
without being reopened. A fourth card shows the **real testnet account** (value, positions, uPnL)
read by public address — no key — from `account.txt` or `HL_WALLET_ADDRESS`; the paper books are still
`paper.db` only, and the account card is visibly separate from them.

Each coin is its **own** paper book ($1,000 each), not a shared portfolio: a BTC fill cannot appear
in ETH's account. That is asserted by a test.

## The gate

`strategy_ledger.csv` is the only door into `run`. Columns:

```
id,strategy,status,estimator,estimator_matches_claim,economic_bar,basis,note
P1,sma,plumbing,plain,na,na,,reference strategy; no claim to an edge
```

- `plumbing` / `trial` → refused unless `--allow-plumbing` is passed **and** a dated window in
  `PLUMBING.md` names that strategy with a future `expires:` date. No window, no run.
- `holds` → refused at load time unless `estimator_matches_claim=yes` **and** `economic_bar=yes`.
- `retired` → always refused.
- a strategy with no row → refused, with the message telling you to add one.

## Long and short

A position is a signed quantity: positive long, negative short. The strategy reads the 20/50 SMA
pair as a **regime** (above = long, below = short) and flips on the cross — so the book is almost
always in the market, in one direction.

- **Mirrored stops**: long stops below entry − 3 %, short stops above entry + 3 %.
- **A stop blocks re-entry** on the same regime; the block lifts only when the SMA regime flips.
  Without that, a stop-out would re-open on the next tick and the stop would be decoration.
- **Funding accrues** at a constant `funding_bps_hour` (default 1 bp/h ≈ 8.8 %/yr, positive = longs
  pay shorts, shorts receive). It is charged from the state's `last_funding`, capped at 24 h per gap.
- **Cash follows the signed position**: a long pays for the asset, a short receives the proceeds;
  equity is `cash + qty × mark` in both cases.
- `--long-only` on `run` ignores short signals; the signed testnet path has its own guard
  (`reduce_only` when closing a long, `--allow-short` when opening a short).

Paper only: no leverage, no margin call, no liquidation price. Notional per position is capped at
cash, and funding is an assumption, not the venue's realised rate.

## Signing (testnet only)

`espero2/hl_signed.py` is the only module that reads a key. It refuses unless: the base URL is the
testnet constant, `HL_NETWORK=testnet`, `ESPERO2_ALLOW_TESTNET=1`, `HL_PRIVATE_KEY` is set, and
`--confirm-testnet` is passed. The key is read into the process and never printed.

```bash
ESPERO2_ALLOW_TESTNET=1 python -m espero2.cli order --coin BTC --side buy --notional 12 --confirm-testnet
```

## Sleeping, and catching up

The loop is wall-clock scheduled, so a suspended laptop does not silently lose a cycle. On wake, if
it is more than 1.5 intervals late it first **marks the equity series over every bar that closed
while it slept** (no invented fills), then resumes. Proof, from `scripts/catchup_demo.sh` — a 1m loop
SIGSTOPped for 140 s:

```
paused 17:42:58 · resumed 17:45:18
17:45:18 catch-up BTC: 2 mark(s) for the 93s gap
17:45:18 BTC mid=78706.50 spread=1.1bps signal=- | hold | equity=1000.00
```

A fresh journal is not backfilled, and a cross that happened during the gap is not traded after the
fact: the next live tick sees the current touch, which is the price a person could get.

## Execution policy

`EXECUTION` holds one word:

- `mock` (default) — Coinbase sandbox orders only.
- `live` — recognised and refused: this project has no authenticated Coinbase order path.

Hyperliquid **testnet** orders are not governed by this file — they are testnet money and keep their
own five guards (`--confirm-testnet`, testnet host, explicit allow flag, key present, network check).

## Coinbase spot paper book

```bash
python -m espero2.cli cb paper --product BTC-USD --quote 20 --once
python -m espero2.cli cb paper --product BTC-USD --loop --every 60
```

Real prices from the public Exchange API; simulated taker fills at the far touch, 2 bps slippage,
and the **account's actual taker rate** read from `/transaction_summary` (90 bps on the current
"Intro" tier, 50 maker, falling back to 90); long-only (spot cannot short); 3% stop that blocks re-entry until the
regime flips. Everything lands in our own `cb-paper.db`. `--send-mock` additionally sends the order
to the sandbox to exercise the request shape — it records nothing, so the journal stays the truth.

## Coinbase account (read-only)

```bash
python -m espero2.cli cb live        # authenticated GET /accounts, non-zero balances
```

The CDP key in `.env` signs a JWT and reads the live account. Only GETs exist in this project:
there is no authenticated order path, and orders stay in the sandbox. The key is Ed25519; the docs
say EdDSA is unsupported for Coinbase App APIs, but the brokerage endpoint accepted it on 2026-10-30.

## Coinbase sandbox

```bash
python -m espero2.cli cb ticker --product BTC-USD     # real public price, no key
python -m espero2.cli cb accounts                     # sandbox fixture accounts
python -m espero2.cli cb order --quote 1 --confirm-sandbox
python -m espero2.cli cb order --quote 1 --confirm-sandbox --sandbox-case PostOrder_insufficient_fund
python -m espero2.cli cb portfolios                    # DEFAULT and INTX (perps)
python -m espero2.cli cb fills
```

The documented `X-Sandbox:` header forces an error deterministically, so failure handling can be
tested without inventing a mock: `PostOrder_insufficient_fund` makes the order come back
`INSUFFICIENT_FUND`. The sandbox still serves **INTX** portfolio/positions fixtures, but INTX perpetuals were **retired
on 2026-10-01**; US derivatives now go through **CFM futures** (`/cfm/*`, JWT required), which the
sandbox does not implement. `cb futures` prints the live path and that gap.

Prices are real (`api.exchange.coinbase.com`); orders go to the sandbox, which is a **mock** — it
returns one canned success payload and ignores the request's side. The CLI says so when the reply
does not echo our client id. Useful for validating the request shape, never for fills.

## Supervision and heartbeat

The loop writes a heartbeat after every cycle, so a silent death is visible:

```bash
python -m espero2.cli health        # exit 0 = alive, 1 = no heartbeat or older than 3 cycles
```

For multi-day running, start it under the supervisor, which restarts a dead loop with backoff
(5 s doubling to 60 s) and exits when a `KILL` file exists:

```bash
./scripts/supervise.sh                       # 60 s cadence, BTC/ETH/SOL, journal paper.db
STATE=demo.db EVERY=10 ./scripts/supervise.sh
./scripts/install-launchd.sh                 # optional: launchd agent, KeepAlive, logs in logs/
touch KILL                                   # stop everything, including the supervisor
```

Proof: a `kill -9` on the loop process —

```
17:47:29 loop exited 137 after 25s; restarting in 5s
17:47:35 BTC mid=78720.50 ... equity=1000.00
health: heartbeat 4s ago (every 10s) — ok
```

## What it is not

- Not evidence. The SMA cross is plumbing; it has no claim and needs `--allow-plumbing` to run.
- Not a venue simulator: testnet spreads (0.1 bps on BTC, 21 bps on SOL) are not mainnet's.
- Not mainnet-reachable: the host is a constant and the exchange is built on it.
