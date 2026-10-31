# Changes — espero2

Everything built in this project since forking from `espero` (the original), newest at the bottom of
the changelog. **Maintenance rule: every change, major or minor, gets one dated line here in the
same turn it is made.** Nothing in this repository is a git commit yet — the tree is the record.

- **Source of the fork:** `/Users/fredp/Espero Trading QuantBot/espero` at `765a5b9` (read-only).
- **What was reused:** data, recorded market material and the research corpus. **No code was copied**;
  the point was a different implementation with the same discipline.
- **First version of this file:** 2026-10-30, written after the short/funding work.

## Conventions

- **Major**: a new capability (shorts, funding, supervisor) or a schema change.
- **Minor**: a fix, a test, a doc line, a label.
- **Breaking**: changes the meaning of an existing journal row or CLI flag; always noted.
- Tests: `python -m unittest discover -s tests -t .` — currently **46 passing**.

---

## Changelog

### 2026-10-30 · fork and data

- **Forked**: created `espero2/` from the original at `765a5b9`. Copied `data/panel` (42-coin daily
  panel), `data/aggr` (explore + holdout hourly), `data/funding`, BTC/ETH daily, and the 86 research
  documents + measured cost table into `reference/`. Nothing executed from the old project.
- **Provenance**: `MANIFEST.sha256` over 705 files; `shasum -a 256 -c` re-checks them.
- **Second copy, with the owner's permission**: 12 SQLite paper books via the backup API (`books/`),
  `data/hlcollect` and `lows/forward` recordings (`recordings/`), 2.3 GB of raw archives
  (`data_raw/`, 109,350 files), and `.env` copied `0600` without reading it.
- **Fix (major)**: the first bulk copy flattened every directory into `data_raw/` because
  `cp -R dir/ dest/` merges contents on macOS. Removed it and recopied per directory; every
  directory then size-matched the source.

### 2026-10-30 · paper harness (first running version)

- **Major**: `espero2/hl.py` — testnet-only public client (`allMids`, `l2Book`, `candleSnapshot`,
  `fundingHistory`). Refuses non-Hyperliquid hosts.
- **Major**: `espero2/store.py` — one SQLite journal: bars, signals, orders, equity, state.
- **Major**: `espero2/paper.py` — one decision cycle: closed bars → signal → taker fill at the far
  touch + 2 bps slippage + 4.5 bps fee → mark.
- **Major**: `espero2/cli.py` — `run`, `report`, `book`; `--loop/--every`, `--coin` repeatable.
- **Minor**: forming candle dropped (`closed_only`), so a signal cannot see a live close.
- **Minor**: 9 tests — forming bar excluded, fill maths, stop trigger, journal round-trip, host guard.

### 2026-10-30 · the gate

- **Major**: `strategy_ledger.csv` + `espero2/ledger.py`. A strategy cannot run without a row;
  `plumbing`/`trial` need `--allow-plumbing`; `holds` is rejected at load unless
  `estimator_matches_claim=yes` **and** `economic_bar=yes`; `retired` never runs.
- **Minor**: CLI `ledger` subcommand prints what may run.

### 2026-10-30 · signed testnet orders

- **Major**: `espero2/hl_signed.py` and CLI `order` / `state`. Five guards: testnet host constant,
  `HL_NETWORK=testnet`, an explicit allow flag, a key present, and `--confirm-testnet`.
- **Minor (breaking)**: order size must be rounded by the asset's `szDecimals` from `meta`; the
  exchange minimum is **$10 notional** — learned by two rejections.
- **Minor**: exchange errors inside `statuses` are now surfaced instead of reported as success.
- **Fact**: first signed testnet fill — BUY 0.00015 BTC @ 78,656, oid 64117647169.

### 2026-10-30 · supervision and heartbeat

- **Major**: heartbeat after every cycle (`state.heartbeat`, `state.every`); CLI `health` exits 1
  when the beat is older than three cycles.
- **Major**: `scripts/supervise.sh` restarts a dead loop with backoff (5 s doubling to 60 s), exits on
  `KILL`. **Proven** by `kill -9`: restart in 5 s, ticks resumed.
- **Major**: `deploy/io.espero2.paper.plist` + `scripts/install-launchd.sh` (not installed — installing
  it beside a supervised loop would double-trade the same journal).
- **Minor**: `KILL` handling in the UI and supervisor.

### 2026-10-30 · dashboard

- **Major**: `espero2/dashboard.py` — self-contained HTML (no server, no framework), per-coin cards
  with sparkline, orders, ledger, 30 s self-refresh. CLI `dashboard --open`.
- **Minor**: `scripts/catchup_demo.sh` + live proof that a suspended 1 m loop fills the missing marks.

### 2026-10-30 · per-coin books (bug fix)

- **Breaking (major)**: the three coins shared one position — `tick()` read a global `cash/qty`, so a
  BTC fill would have appeared in ETH's account. State is now keyed per coin
  (`{coin}:cash`, `{coin}:qty`, …) and `equity` carries a `coin` column. Journals migrate in place;
  old rows become the BTC book.
- **Minor**: regression test — a BTC fill leaves the ETH book at $1,000.

### 2026-10-30 · terminal UI

- **Major**: `espero2/ui.py`, ported from the original `espero/ui.py` in grammar, not code: same
  mascot, `#d97757` accent, questionary style, header/accounts/orders/ledger panels.
- **Minor**: menu grown to status, dashboard, preview decision, paper actions (buy/close/reset),
  deposit/reset, pause/resume, log tail, research documents (rich markdown pager), tests, quit.
- **Minor**: the UI refuses to open if the strategy has no ledger row.

### 2026-10-30 · long and short

- **Major**: positions are signed (`qty > 0` long, `< 0` short). The SMA 20/50 pair is read as a
  **regime**; the book flips on the cross. Shorts credit proceeds (`cash -= qty × px`), longs debit.
- **Major**: mirrored stops (long below −3 %, short above +3 %). A stop **blocks re-entry** until the
  regime flips; without it a stop-out re-opened on the next tick.
- **Major**: funding accrues per settled hour; the default source is now **mainnet realised rates**
  (`venue-mainnet`), with a labelled constant fallback. Testnet rates are pathological (SOL pinned at
  50 bp/h vs mainnet 0.079), so the constant 1 bp/h assumption was 25–600× off.
- **Major**: liquidation is now priced, not a zero-equity floor: `liquidation_px()` from leverage and
  maintenance margin (1x -> ~1.99x against a short), checked **before** the strategy stop because the
  venue acts first. The fill is the mark or the liquidation price, whichever is worse - a gap through
  it can still leave a negative balance, which is what actually happens. Re-entry is blocked.
- **Minor**: `--long-only` for `run`; signed orders still require `--allow-short` to open a short.
- **Minor**: venue guards relaxed for **reading** (mainnet `fundingHistory` is public); `hl_signed.py`
  remains pinned to the testnet constant for anything that can sign.
- **Minor**: tests added across this phase (short open, mirrored stop, flip = close+open, stop blocks
  re-entry, funding signs, venue vs constant, liquidation at price, gap through it, long-only switch,
  mainnet read allowed / signing not). Suite: 29 -> 46 by the end of the funding work.

### 2026-10-30 · funding source, liquidation model, this file

- **Major**: paper funding now uses **mainnet realised hourly rates** by default, while price and
  fills stay on testnet. `hl.funding_history(..., venue="mainnet"|"testnet")`; each accrual label says
  which venue it used (`venue-mainnet`, `constant (no venue point)`, `constant (venue unavailable)`).
- **Minor**: reading mainnet is now permitted in `hl.py` (public `fundingHistory` only); `hl_signed.py`
  stays pinned to the testnet constant for anything that signs.
- **Minor**: fixed a label bug where the constant fallback printed `(venue)` - the first live tick
  after the change exposed it.
- **Minor (breaking)**: `liquidation_px` + `Rules.leverage` / `Rules.maintenance`; liquidation runs
  before the stop. Existing journals are unaffected (no liquidation rows yet).
- **Major**: this file.

### 2026-10-30 · venue review

- **Minor (no code)**: read the original's two venue plans (`VENUE_CONFIRMATION.md` for a US holder,
  uncommitted `VENUE_NONUS.md` for a non-US holder). Recorded the consequence in "Open items":
  residency decides the venue, the venue decides the cost model, and ours is Hyperliquid's.

### 2026-10-30 · Coinbase Advanced Trade sandbox

- **Major**: `espero2/coinbase.py` + CLI `cb`. Real public prices from `api.exchange.coinbase.com`
  (keyless), and order flow against `api-sandbox.coinbase.com`.
- **Finding (stated in the module)**: the sandbox is a **mock**. Every order returns the same canned
  payload (`client_order_id: "sandbox_success_order"`, side SELL even for a BUY) and `/orders/historical`
  serves a static 2024 fixture. It tests request/response shape, not fills. `place_market` marks the
  reply `mock` when the sandbox does not echo our client id.
- **Guards**: reads only from the two Coinbase hosts; orders only to the sandbox constant;
  `--confirm-sandbox` required. No key is read (the sandbox answered unauthenticated).
- **Minor (fix)**: the Exchange API returns 403 to the default Python urllib user agent; requests now
  send `User-Agent: espero2/0.1`.
- **Tests**: 4 (mainnet order refused, unknown host refused, confirm required, canned reply flagged).
  Suite: 58.

### 2026-10-30 · Coinbase sandbox docs -> error injection and perps

- **Minor**: read the official sandbox page. It confirms our probe: no authentication, static
  pre-defined responses, and **only accounts/orders endpoints** - plus two things we had missed:
  an `X-Sandbox:` header that triggers a documented error (`PostOrder_insufficient_fund`,
  `CancelOrders_failure`, `EditOrder_failure`, `PreviewOrder_insufficient_fund`), and **INTX
  perpetuals** endpoints (`/portfolios`, `/intx/portfolio/{uuid}`, `/intx/positions/{uuid}`,
  `/intx/balances/{uuid}`).
- **Minor**: `place_market(..., sandbox_case=...)` sends the header and parses `error_response`;
  CLI `cb order --sandbox-case ...` exits 1 on the forced error. New `cb portfolios`, `cb perps`,
  `cb fills`.
- **Minor**: 2 tests (header sent + error parsed; portfolios/perp positions parse). Suite: 60.

### 2026-10-30 · Alpaca crypto orders (the gap I left)

- **`alpaca.place_crypto`**: crypto pairs (`BTC/USD`), fractional qty, market, `gtc`; **long-only** —
  Alpaca crypto has no margin, so a crypto sell that would open a short is refused by the adapter.
- **Router**: a `/` in the symbol routes to the crypto path; stock symbols keep the equity path.
- **Placed and filled** (24/7 market): **BTC/USD 0.00129494 (~$100)** and **ETH/USD 0.02231441 (~$50)**,
  both `filled`; positions now BTCUSD $99.78 (+$0.03) and ETHUSD $49.89 (−$0.02).
- **Tests**: 3 (crypto needs qty, crypto shorts refused, crypto routing). Suite: 113.

### 2026-10-30 · Alpaca limit orders and a varied paper book

- **Limit orders**: `alpaca.place_order(..., order_type="limit", limit_price=...)` with GTC; the trade
  router and CLI expose `--type limit --limit-price`. Tests updated and passing.
- **Eight paper orders placed** (all `accepted`, market closed, fill at the next open): longs — AAPL
  market +1, MSFT 2, NVDA 3, SPY 1 market, AAPL limit 341.32; shorts — TSLA 1, META 2 market, AMZN
  limit 242.75. Reserved buying power 5,413 of 400,000; cash untouched until fills.
- **Paper only**: `paper-api.alpaca.markets`, live host absent from the module.

### 2026-10-30 · one trade command across the three paper venues

- **`espero2/trade.py` + `cli trade`**: `--venue alpaca|coinbase|hyperliquid`, `--symbol`, `--side`,
  `--qty` (Alpaca) or `--notional` (Coinbase/HL), `--confirm`.
- **Guards unchanged and verified**: every venue refuses without `--confirm`
  (`pass confirm=True (--confirm-paper)` / `--confirm-sandbox` / `--confirm-testnet`); Coinbase also
  passes `policy.require_sandbox()`; Alpaca's live host does not exist in its module; Hyperliquid
  builds a testnet exchange only.
- **Tests**: 5 (`tests/test_trade.py`: unknown venue, qty/notional validation, per-venue confirm
  refusals, routing arguments). Suite: 107.
- **Not opened**: live order paths. Alpaca has paper keys only, Coinbase's key is read-only
  (`can_trade: false`), and Hyperliquid mainnet remains unreachable by construction.

### 2026-10-30 · plumbing mechanics run (books void)

- Ran the paper loop for one cycle on BTC and ETH inside the dated `PLUMBING.md` window, with the
  ledger row temporarily `plumbing` and `KILL` lifted; **no venue order and no signing** — the paper
  engine fills locally at the touch with 4.5 bps taker cost and venue funding.
- **Result**: BTC short −0.001270 (equity 999.22), ETH short −0.044816 (equity 999.66), fees 0.04 each;
  journal, stops, funding and equity marks all wrote correctly. Dashboard rendered with the research card.
- **Restored immediately**: `KILL` back in place, ledger row back to `retired`. `paper.db` keeps the demo
  positions and is gitignored; the books are void for any performance claim.

### 2026-10-30 · signal provenance and a research-state card

- **Per-signal metadata** (from the article's audit-trail idea): the `signals` table now carries
  `prereg_id`, `model_version`, `inputs_hash`, `gate_state`; `Store.signal()` takes them as keyword
  arguments; old journals migrate in place (verified on a pre-existing schema).
- **Stamped at source**: `paper.tick` writes the ledger row id and status (`P1`, `retired`), the model
  version (`sma20/50`) and a 16-hex SHA-256 of the last 60 closes used, so every signal is
  reproducible from its inputs.
- **Dashboard research card**: E1 window, state, days recorded, events, ledger status counts and the
  number of `holds` (currently 0) — the thing the project is actually waiting on, visible on the page.
- **Tests**: 3 new (`tests/test_meta.py`: provenance round-trip, old-journal migration, research state),
  dashboard smoke-tested. Suite: 102.

### 2026-10-30 · RP3: cost-aware residual pairs — zero selected, the edge was never there

- **Sealed** `PREREGISTRATION_RESIDUAL_PAIRS_COST.md` (`9942469`): RP2's fixed half-life floor replaced
  by a direct design-window backtest of the rule (net > 0, t >= 2, >= 30 round trips).
- **Result**: the 3 FDR-passing pairs all **lose on their own design window** — FIL|THETA -8.2 bps/day
  (t -0.76), FIL|EOS -17.0 (t -1.58), FIL|XTZ -9.3 (t -1.03), each 174-229 round trips.
- **0 selected**; validation not run; **holdout still unread**. Ledger `R8` retired.
- **What it proves**: residualisation is the right discovery tool (3/435 vs 0/231), but the reversion is
  smaller than the cost of harvesting it. The half-life floor was not the binding constraint.

### 2026-10-30 · RP2: residual pairs — discovery works, the half-life floor kills it

- **Sealed** `PREREGISTRATION_RESIDUAL_PAIRS.md` (`c1ec15b`) before any residual statistic.
- **Discovery 2020-2022**: 435 pairs on market residuals, BH FDR 10% -> **3 pass** (raw prices: 0/231).
  FIL|THETA p 0.00021, FIL|ATOM 0.00113, FIL|AAVE 0.00119 — residualisation is the right diagnosis.
- **But** every survivor has a half-life of **2.8-4.4 days**, below the registered **5-30 day** floor:
  **0 frozen**, validation not executed, **holdout unread**.
- **Ledger `R7` retired**; result `research/RESULTS_rp2.md`. The gate held again.

### 2026-10-30 · research program phase 1: vol, pairs, factors — zero candidates pass

- **Data**: `extend_substrate.py` aggregated the local 5m archive into `bars_daily` and `rv` —
  **82,774 rows, 42 symbols, 2020-01 → 2026-03, zero duplicates**. Windows fixed: design 2020–2022,
  validation 2023, holdout 2025-07 → 2026-03 (not read; disclosed).
- **Volatility**: HAR-RV beats EWMA(0.94) and a trailing mean on **35/38** symbols
  (QLIKE 0.393 vs 0.450 vs 0.516). A usable risk instrument for sizing; no signal.
- **Pairs**: 231 tested, **0 survive BH FDR 10%**. Best FIL|XTZ, median ADF p 0.0043, half-life 5.2 d —
  would pass uncorrected, which is exactly what the multiplicity control exists to reject.
- **Factors**: PC1 explains 66% of variance; design +47.2%/yr (t 0.99) flips to **−10.9% (t −0.42)** on
  validation; PC2/PC3 negative throughout. Risk decomposition only, no alpha.
- **Gate**: zero candidates → **no policy fitted, no disproof run, no authorisation**. Fitting a policy
  on a failed signal is the overfitting this project exists to refuse.
- **Files**: `research/{extend_substrate,vol_model,pairs,factor_model}.py`,
  `RESULTS_program_phase1.md`; ledger rows `R5` (pairs) and `R6` (factors), both retired.

### 2026-10-30 · Alpaca crypto bars

- **`crypto_bars()`** on `/v1beta3/crypto/us/bars`; CLI `cb bars --crypto --symbols BTC/USD`.
  Verified live: 7 daily bars, last close **77,306.06** (2026-10-31).
- **Tests**: 5 for the Alpaca module (crypto endpoint URL added). Suite: 93.

### 2026-10-30 · Alpaca adapter verified against the live paper account

- **Keys present** (`APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`), loaded without printing values.
- **Authenticated**: paper account `PA35L5ACZ`, status ACTIVE, cash **$100,000**, buying power
  $400,000, options level 3, crypto ACTIVE; no positions, no orders.
- **Market data**: `cb bars --symbols AAPL MSFT --timeframe 1Day` returns IEX bars (AAPL 344.77,
  MSFT 521.97 at 2026-10-30).
- **Fix**: `--symbols` now takes a list (`nargs="+"`); previously only one symbol parsed.
- **Not wired**: crypto bars (Alpaca's `/v1beta3/crypto/us/bars`) — stocks only for now.

### 2026-10-30 · Alpaca paper API adapter

- **`espero2/alpaca.py`**: paper account, positions, clock, bars, orders and paper-only order
  placement. Hosts allowed are exactly `paper-api.alpaca.markets` and `data.alpaca.markets`; the live
  host `api.alpaca.markets` is recognised and **refused at the URL level**. Orders need
  `--confirm-paper`, and keys are required before any call leaves the process.
- **CLI**: `cb account | positions | clock | bars | orders | order` (the `cb` group is now the venue
  group; Hyperliquid's `order` is unchanged).
- **`.env`**: two empty placeholders added (`APCA_API_KEY_ID=`, `APCA_API_SECRET_KEY=`). Values are the
  account holder's to paste; the file is never printed by this project.
- **Verified**: both endpoints reachable; without keys every command refuses with exit 2 and a clear
  message; 4 tests (live host refused, missing keys refused, confirm required, bars query built).
- **Tests**: suite 92.

### 2026-10-30 · queue-aware execution: the last registered gap

- **Ingested** `bookTicker` + `aggTrades` for 2023-07-10, 11 depth-covered symbols (BTC/ETH excluded
  for file size): **45,547,988 quote updates, 3,296,200 trades** into the substrate.
- **Measured**: quoted and effective half-spreads coincide (0.21–3.82 bps); maker fill within 60 s
  22–87% (median 3.8–24.9 s); 5 s markout −1.0 to −2.2 bps.
- **Consequence**: the depth-band reprice was conservative at small size; measured spread+fee ≈ 6 bps
  a side → holdout net at $1M/side ≈ +29%/yr (vs +26.4% modelled), still t 0.75. The answer stands:
  decay, not execution. Capacity still binds at a few $M/side.
- **Files**: `research/queue_sim.py`, `queue_sim.json`, `RESULTS_queue_execution.md`; ANSWER updated.

### 2026-10-30 · research substrate and the XS failure answer

- **Substrate** (`research/substrate.py`): DuckDB with `valid_time` (venue date) and `known_time` (fetch
  date) — 128,959 bars, 108,374 funding, 13,675 premium, 1,728,000 depth rows; zero duplicate keys;
  gap reports per symbol; 6,664-file manifest. **The universe is a query**: top 47 by trailing 30-day
  volume, deduped by base asset — overlaps the frozen 47 by 32/47, the difference explained by window
  length and LUNAUSDT.
- **Execution simulator** (`research/execution_sim.py`): impact from 112 `bookDepth` days, median 1%
  notional $1.83M. XS holdout gross +35.3%/yr → net +30.8 at $100k/side, **+26.4 at $1M**, +7.0 at $5M,
  −16.0 at $10M. Carry impact drag 1.0%/yr at $100k per position, 10.0% at $1M.
- **Detector calibration** (`research/calibration.py`): 200 synthetic markets per effect size; null
  estimate +3.2% (CI −80.6…+88.0, 51% positive), 0.4%/wk → +31.9% with 77% positive. The band is
  ±80%/yr wide — the binding constraint is power, not execution.
- **Trial budget** (`research/trial_budget.py`): R1 0.395, R2 0.000 (replication), R3 0.0017,
  R4 0.026, E1 pending; deflated Sharpe of the best across four trials 1.000.
- **Answer** (`research/ANSWER_xs_failure.md`): at $1M/side execution changes +27.8% to +26.4% — the
  verdict is unchanged; decay of the gross spread (−69%) is what failed the test, while liquidity caps
  scale at a few million per side.
- **Gaps stated**: `bookTicker` not ingested, depth covers 15/47 symbols, no vendor overlap, no live
  fills.

### 2026-10-30 · XS verification gaps closed

- **Capacity computed**: 112 `bookDepth` days — median **$637,880/symbol** at 25 bps impact,
  **$38.96M** across 14 symbols (the registered P2 gap, now filled; the failure verdict is unchanged).
- **`aggTrades` print check**: 10/10 random 2023 symbol-days match the `klines` close exactly.
- **Independent recomputation**: the registered DuckDB query is **not equivalent** (row-based
  `LAG/LEAD`, 48 Fridays of 99) and is recorded as invalid; a third vectorized implementation
  reproduces the number — design **+144.9%/yr gross** (t 1.83), holdout **+36.9%/yr gross** (t 0.96),
  consistent with the net returns after costs.
- **Files**: `research/xs_verify.py`, `xs_verify.json`, results doc updated by a new section (the
  verdict and numbers are untouched).

### 2026-10-30 · deep cross-sectional momentum (#2/#7 rev 2) — sealed, FAIL on holdout

- **Sealed** `research/PREREGISTRATION_XS_MOMENTUM.md` (**95005ac**) before any 2021-2023 price; universe
  frozen from **1,051 symbols ever listed** (144 with 12+ months in 2021-2022, top 50 by design volume,
  deduped by base asset to 47 — **53ffbfc**). LUNAUSDT is in it and exits at its last print, so the
  survivorship test passes by construction.
- **Design 2021-2022**: +101.4%/yr net (CI +15.8…+194.8), NW t 2.23, Sharpe 1.24; variants +57.5 /
  +94.2; sign-flip placebo -108.9%/yr.
- **Holdout 2023**: **+27.8%/yr (CI -36.4…+92.5), t 0.75 — P1 fails**; variants -15.1 / +72.4;
  sign-flip placebo -34.8%/yr, random selection -14.8%/yr.
- **P3 placebo passes** in both windows: the pipeline discriminates; the effect is regime-sized.
- **P2 capacity not computed** — registered, not implemented, disclosed as a gap; no `aggTrades`
  check and no DuckDB re-implementation either.
- **Ledger row `R4`**; result `research/RESULTS_2026-10-30-xs-momentum.md`.

### 2026-10-30 · erratum: the carry P2 ratio used the wrong denominator

- **Found by testing the "fix"**: the intercept formulation does not identify alpha (t = -734: basis
  P&L in the error term), but it exposed a measurement error in the result.
- **The error**: `gross_funding_annual_pct` (11.3%) is the universe average including flat days; funding
  collected while the harvest was open is **21.2%/yr**. Against net **15.4%**, P2 as written is
  **0.73 < 1 — met**, and the basis-plus-cost contribution was **-5.8%/yr**, not positive.
- **The sealed FAIL stands** (the registration is the contract and is not rewritten); the result doc is
  corrected by `research/ERRATUM_2026-10-30-carry-p2.md`, not edited.
- **Process fix**: every future registration must name the denominator of each ratio explicitly.
- **Unchanged**: holdout 4 signals in 4,307 symbol-days — the threshold is a regime bet.

### 2026-10-30 · deep carry test (#12 rev 2) — sealed, run, inconclusive on holdout

- **Registered before the holdout existed** (`research/PREREGISTRATION_CARRY_DEEP.md`, seal commit
  **ac0bc24**): mechanism, universe (25 symbols frozen from 2024 volume), signal (trailing 20%
  annualised funding + positive basis, 30-day max, 30 bps round trip), estimator (stationary
  bootstrap, NW, deflated Sharpe, SPA family of 3), decay, capacity, placebo, reconciliation, outcomes.
- **Design (2024)**: **+15.4%/yr net** (95% CI +6.0…+26.2), NW t 3.13, 176 active days, 15.5 average
  positions; variants 15.4 / 10.6 / 9.1 (registered is best); deflated Sharpe p 1.000; placebo p 0.000;
  funding half-life **6.7 days**; capacity **$0.86M per symbol / $98.4M across 15**.
- **Holdout (2025 H1)**: **4 entry signals in 4,307 symbol-days — the rule stayed flat.** Not a pass,
  not a fail: an absolute 20% threshold is a **bet on a funding regime**, and 2025 H1 averaged 4.4%.
- **P2 failed as written** (net/funding 1.36 > 1): my criterion mis-specified carry, which earns
  funding *and* basis convergence. Disclosed, not repaired.
- **Reconciliation**: funding vs premium index over 6,153 intervals — corr **0.75**, sign agreement
  83.5% where |premium| > 5 bps, median gap **−4.6 bps** = Binance's −5 bps clamp.
- **Disclosure**: the holdout was partially read during a crash debug (signal counts, no P&L).
- **Files**: `research/carry_fetch.py`, `carry_deep.py`, `carry_deep.json`,
  `RESULTS_2026-10-30-carry-deep.md`; ledger row `R3`.
- **Tests**: 88 still green (the new scripts are research code, not imported by the suite).

### 2026-10-30 · public front page

- **README rewritten** for the project as it is now: the evidence table (audit, both replications,
  retired SMA), E1 and its window, the three enforced rules, quick start, the unattended jobs, the
  layout, and an explicit "what is not claimed" section. The old page still said "19 tests" and
  described only the paper harness.
- **LICENSE** added: MIT with both notices (original © 2026 7ucky7, this revision © 2026 7rido),
  because `reference/` reproduces the original's documents verbatim.
- **Repository made public** at the owner's request.

### 2026-10-30 · renamed

- The project title is **Espero Trading Harness WIP-CLAUDE/DS Revision v1.1**. GitHub does not allow
  spaces or a slash in a repository name, so the repo slug is
  `espero-trading-harness-wip-claude-ds-revision-v1.1` and the literal title becomes its description.
- The local folder stays `~/espero2`; the two launchd agents point at it.

### 2026-10-30 · silent-job health check, local CI, daily 08:30 agent

- **Health check** (`scripts/health_check.py`): `sync` (07:45 copy ran within 30 h, source exists),
  `feed` (aggr 5-minute feed arriving; day 0 is a WARN, day 2+ empty is a FAIL), `ledger` (no breaks
  for 7 days inside an open window is a FAIL), `window` (not opened / open with N days left / closed).
  Exit 1 on any FAIL; writes `logs/health.json`. Today: sync OK, feed WARN (first file due after the
  next 07:30 run), ledger OK, window open with 181 days left.
- **Scheduled** `io.espero2.health` daily at 08:30 (after the 07:45 copy), installed and kickstarted;
  exit 0. A failure lands in `logs/health-launchd.err`.
- **Local CI** `scripts/check.sh`: the suite, `audit_by_number.py --check`, and the ledger validation
  in one command - runs here, so the discipline is enforced without me remembering it.
- **GitHub workflow** `.github/workflows/ci.yml` mirrors `check.sh` for when the project is pushed;
  note there is **no git repository** in `~/espero2` yet, so it is inert until one exists.
- **Tests**: 6 (`tests/test_health.py`: healthy tree, stale copy, missing source, empty feed after the
  grace day, empty feed on day one, silent ledger). Suite: 94.

### 2026-10-30 · E1 recorder, measured cost, funding, P1 retired

- **E1 recorder** (`research/e1_recorder.py`): reads #27's ledger + `data/lows/forward` bars, tags with
  **prior-day terciles**, computes 4 h/12 h/1 d holds **net of 9 bps and realised funding**, and writes
  `research/e1_status.json`. `--score` refuses before **2027-04-30** (exit 2) - interim P&L is never
  read. Empty ledger today: window not opened, 0 events.
- **Cost measured** (`research/cost_check.py`): 17,266 snapshots from the fetched books (ETH-USD):
  median quoted spread **0.09 bps**, p90 0.77; fees 9.0 bps round trip -> all-in **9.09 bps** against
  E1's assumption of 9.0. The assumption holds; the spread is not the cost.
- **Funding** (`research/e1_recorder.py::funding_cost`): Binance `calc_time,last_funding_rate` parsed
  per interval; BTC 2026-06-10 over 24 h = **-0.17 bps** (a long was paid), over 4 h = no event.
  Column matcher fixed (`funding` + `rate`, not `fundingRate`).
- **P1 retired**: the SMA book tracked an equal-weight hold and its long/short variant liquidated 13
  times; it never had a pre-registered test.
- **Tests**: 4 new (`tests/test_e1.py`: prior-day tagging, hold net of cost+funding, score gate,
  status counts). Suite: 88.

### 2026-10-30 · #26 replicated; the executable variant measured and pre-registered

- **Copied** `data/liq2` (64 MB, 22,308 COIN-M liquidation files, 2023-06-25 → 2024-10-14) into
  `data_raw/liq2`.
- **Replicated** #26 in-sample on 26 coins, 28,039 events, 427 days: D **-20.3 bps (t -5.13)** vs the
  published -23.6 (t -4.06); 1 h long leg **+23.6 bps (t 7.11)** vs +19.2 (t 3.67); 4 h net +38.1
  (t 6.44) vs +21.9 (t 4.38). Same conclusion, stronger because 26 coins vs their 8 and a flat 9 bps
  cost instead of the markout curve.
- **Executable variant** (today tagged against **yesterday's** `s` terciles): D **-14.4 (t -5.36)**,
  long leg **+22.9 bps 1 h (t 6.72)**, **+32.0 bps 4 h gross / +27.5 net (t 4.01)**, 12 h +48.1,
  1 d +73.0. The hindsight tag was not what made #26 pass.
- **Pre-registered** `E1` for the forward test of the executable rule: window 2026-10-31 → 2027-04-30,
  four criteria, trade-weighted day-clustered, 9 bps + funding, power stated. It runs on data the
  07:45 copy brings in; nothing is scored before 2027-04-30.
- **Caveats stated in the result**: funding not charged (1 d is an upper bound), in-sample only,
  trade-weighted D not reproduced.
- **Files**: `research/liq26_replication.py`, `research/liq26_run.json`,
  `research/RESULTS_2026-10-30-liq26-replication.md`,
  `research/PREREGISTRATION_2026-10-30-liq-executable.md`; ledger row `R2`.

### 2026-10-30 · project moved to ~/espero2; the 07:45 copy now works

- **Moved** `espero2` from `~/Downloads/https-::github.com:7rido:espero/espero2` to **`~/espero2`**
  (2.4 GB) to escape the macOS TCC block on background agents reading `~/Downloads`.
- **Reinstalled** `io.espero2.sync` from the new location and kickstarted it: **exit 0**, copied
  1 file (6.9 KB — a ledger/health update), 612 already current, status written to
  `~/espero2/logs/sync-status.json`. The 07:45 run is scheduled and unblocked.
- **Verified**: 84 tests pass from the new path; no source file referenced the old path.
- **Untouched**: the maintainer's folder is still read-only to us, and the old workspace root keeps
  `repo/` and `audit/`.

### 2026-10-30 · daily 07:45 copy from the maintainer's folder (installed, blocked by macOS)

- **Built**: `scripts/sync_from_original.py` - one-way copy of the growing trees
  (`data/aggr/forward*`, `data/lows/forward`, `data/hlcollect`, `data/book`) plus the forward ledger
  CSVs and `health.json`. Copies a file only when it is missing or newer *and* a different size;
  never deletes; a newer local file is never overwritten; `--dry-run`; logs to `logs/sync.log`.
- **Ran manually**: 75 files, 1.4 MB copied (today's hlcollect contexts and the CSV ledgers),
  537 already current. Source folder is read-only throughout.
- **Scheduled**: `deploy/io.espero2.sync.plist`, 07:45 local (after the maintainer's 07:30 job),
  installed as `io.espero2.sync` via `scripts/install-sync-launchd.sh`.
- **Blocked by macOS TCC**: the launchd job exits 2 with
  `getcwd: Operation not permitted` / `can't open file 'scripts/sync_from_original.py'` - the
  destination lives under `~/Downloads`, which background agents cannot read without Full Disk
  Access. The manual run from a shell works. Fix is either moving the project out of Downloads or
  granting `/bin/bash` and `/usr/bin/python3` Full Disk Access.
- **Tests**: 6 (`tests/test_sync.py`: missing copied, unchanged skipped, newer+longer replaced,
  newer+same-size left alone, source deletion never propagates, dry-run writes nothing). Suite: 84.

### 2026-10-30 · live-data release fetched (book, hlcollect, one warm-up day)

- **Fetched** the public release `espero-live-data.tar.gz` (21 MB) directly into `espero2/data/`,
  SHA-256 verified (`90848ab2...`); the original folder was not written to.
- **Arrived**: `data/book` (22 MB of recorded books, the raw material for #39/#41), `data/hlcollect`
  (19 MB: positions, HLP, contexts, 1m candles) and `data/lows/forward` (41 zipped files, one day:
  2026-10-29, the pre-window warm-up).
- **Did not arrive**: no `data/aggr/forward*`, no `liqbreak`/`liqhold` ledger. #45's feed is not part
  of the release.
- **And there is nothing to read yet anyway**: the maintainer's own daily job (07:30) reports
  `liqbreak: 0 breaks on 0 days`, `liqhold: no forced down-break with a complete hold yet`,
  `liqfwd: 0 trades on 0 days`. The window opened 2026-10-30.
- **Consequence**: #45 cannot be evaluated or watched here until breaks occur, and its verdict date is
  2027-03-31. What the fetch did give us is the markout raw material (#39/#41) and one day of 5m bars.

### 2026-10-30 · audit by number

- **Major**: `research/AUDIT_BY_NUMBER.md` - all 46 ids (#1-#45, #9b), each with the original verdict,
  our evidence, the failure layer, why it failed and the remedy. Generated by
  `research/audit_by_number.py` from `research/audit_base.csv` (the ported 46-row rescoring) and
  `research/audit_findings.csv` (curated why/remedy/evidence); never hand-edited.
- **Verified**: 46/46 documents resolve; 31/31 parsed verdicts agree with the recorded decision;
  46/46 findings cite a file; two runs byte-identical; `--compare-original` shows our `reference/`
  copy is byte-identical to the read-only original folder.
- **Distribution**: FAIL 23 · RUNNING 10 · NOT-A-TEST 3 · REAL-NOT-TRADABLE 2 · PLUMBING 2 ·
  UNRESOLVED/CONSTRUCTION/VENUE-DEPENDENT/HOLDS/CONFIRMED-WEAK/EXPLORATORY 1 each.
- **Failure layers**: estimator 13 · process 11 · selection 4 · execution 2 · none 16.
- **Working mode**: `--check` (coverage, verdicts, citations), `--compare-original PATH` (name+hash
  drift against the read-only original), plain run writes the document.
- **Tests**: 6 new (`tests/test_audit.py`: coverage, findings cited, check passes, determinism,
  per-id rows, drift detection, identical copy). Suite: 78.
- **Ledger**: row `A1` (`audit-by-number`, status `audit`); `audit` added to the ledger's statuses.

### 2026-10-30 · first pre-registered test: #21 replication

- **Pre-registered** `research/PREREGISTRATION_2026-10-30-liqspike.md` before computing any return;
  holdout seal verified 4/4 against the original manifest.
- **Ran once** `research/liqspike_replication.py` (1,669 spikes, 14 coins, Jul-Oct 2026): **FAIL** -
  criterion 1 (revert, t >= 3) missed at **t 0.85**; criteria 2, 3, 4 met. Long-side excess +31.8 bps
  and the long leg +55.6 bps (t 2.86) land within ~10% of the original's published numbers; same
  verdict.
- **Information**: trade-weighted R **-19.7 bps (day-clustered t -0.67)** - opposite sign to the
  day-mean, the #44 lesson reproduced on new data.
- **Bug disclosed**: criterion 2 was first evaluated on R instead of raw excess (sign-flipped for the
  short side); the statistic was unchanged, the evaluation was fixed and the run repeated before the
  result was written.
- **Result**: `research/RESULTS_2026-10-30-liqspike.md`, run json beside it, ledger row `R1`
  (`replication`, `partly`, cost bar `no`).

### 2026-10-30 · Coinbase facts from the API, into the paper book

- **Read from the authenticated API**: `key_permissions` -> **view only** (`can_trade=false`,
  `can_transfer=false`); `transaction_summary` -> fee tier **"Intro": taker 90 bps, maker 50 bps**
  (our 120 bps assumption was too harsh); `products/{id}` -> `quote_min_size` **$1**, base increment
  1e-8, price increment 0.01; `portfolios` -> one DEFAULT portfolio.
- **Used**: `cbpaper.live_costs()` takes the **real taker rate** (90 bps) and falls back to 90 if the
  read fails; orders below the venue's `quote_min_size` are refused with a message instead of being
  simulated into existence.
- **Not available with this key**: `GET /best_bid_ask` returns 401, so bid/ask still comes from the
  public Exchange API (which is fine and keyless).
- **New commands**: `cb fees` (permissions + tier) and `cb product` (minimums/increments).
- **Tests**: 3 (tier parsed from the venue, fallback rate, sub-minimum order refused). Suite: 71.

### 2026-10-30 · Coinbase spot paper book (`cb paper`)

- **Major**: `espero2/cbpaper.py` + `cb paper`. Real prices from the public Exchange API
  (`/products/{id}/candles`, `/ticker`), simulated taker fills at the far touch + 2 bps slippage and
  **120 bps** Coinbase base-tier fee, one signed long position per product, 3% stop that blocks
  re-entry until the regime flips. Journal is ours (`cb-paper.db`), not the sandbox's.
- **Design**: the sandbox is used only for the **order's shape** - `--send-mock` sends the same
  request after a simulated fill and records nothing. Prices and fills never come from it.
- **Spot only**: no borrowing, so a short signal just closes/does nothing; the rule is long-only here
  even though the HL book is long/short.
- **Minor (bug caught by test)**: the first version re-entered immediately after a stop, making the
  stop decoration; it now sets a `blocked` flag cleared only on a regime flip.
- **Tests**: 3 (short signal opens nothing, long signal buys and charges the fee, stop closes and
  stays closed). Suite: 68.

### 2026-10-30 · execution policy, scoped to Coinbase

- **Correction**: the first version of this gate also blocked Hyperliquid testnet orders. That was
  wrong - testnet signing is the account holder's to use, and it has its own five guards. The policy
  now governs the **Coinbase side only**: `mock` (default, sandbox) or `live` (recognised and refused,
  because no authenticated order path exists). An unknown value is refused, never guessed.
- **Verified**: `EXECUTION=mock` -> sandbox order succeeds and is flagged MOCK; `EXECUTION=live` ->
  Coinbase order exits 3 with the refusal; Hyperliquid testnet order path is unaffected.
- **Incident, honestly**: while testing the correction I ran `order --confirm-testnet` expecting a
  refusal; with the gate removed it **filled** 0.00015 BTC @ 78,933 on testnet. I closed it
  immediately at 78,934 (net ~flat). The account's only position is the XPL short that was already
  there. Lesson: a changed guard must be re-tested with a non-sending probe first.
- **Tests**: 3 (default mock allows sandbox, live refused, unknown refused). Suite: 65.

### 2026-10-30 · Coinbase keys verified (read-only) - and the docs are wrong about the format

- **Verified**: the CDP key in `.env` (36-char key name + 64-byte base64 secret) authenticates against
  **production** Advanced Trade: `GET /api/v3/brokerage/accounts` returned **200 with 49 accounts**.
- **Surprise**: it signs as **EdDSA (Ed25519)**, which the Coinbase App auth page says is *not*
  supported ("you must use ES256"). Observed on 2026-10-30: the brokerage endpoint accepted EdDSA.
  The signer therefore tries ES256 for a PEM secret and falls back to EdDSA for this raw-64-byte key.
- **Scope kept**: only a GET path exists (`authed_get`, `live_accounts`, CLI `cb live`). There is no
  authenticated order function in the project; orders remain sandbox-only.
- **Minor**: 2 tests (JWT claims/headers and env loading that never overrides). Suite: 62.
- **Security note**: these keys work on the live account; the copy in `espero2/.env` is a second copy.

### 2026-10-30 · correction: INTX perps are retired; US derivatives are CFM futures

- **Correction (documentation)**: the Advanced Trade REST page says `/intx/*` endpoints are
  **retired** - INTX perpetuals trading ended **2026-10-01**, and international derivatives moved to
  the Global Derivatives gateway. What a US account can trade through this API is **CFM futures**
  (`/cfm/balance_summary`, `/cfm/positions`, `/cfm/positions/{id}`, `/cfm/sweeps`,
  `/cfm/intraday/*`), which needs a CDP JWT. Our earlier statement that INTX was "the only perps
  surface for a US account" was wrong; the sandbox just still serves the retired fixtures.
- **Verified**: the sandbox returns 404 for `/cfm/*` and `/market/*` - it only implements
  accounts/orders/portfolios/intx, as documented. So the futures path cannot be exercised without a
  production key, and this project does not hold one.
- **Verified**: public market data on the venue itself is keyless - `/market/products`,
  `/market/products/{id}`, `/market/product_book` - but `/market/products/{id}/ticker` returns a
  **trade tape, not a quote**; bid/ask still comes from the Exchange API we already use.
- **Minor**: `cb futures` prints the live path, its auth requirement and the sandbox gap, rather than
  pretending an unsigned call would work.

### 2026-10-30 · step two: the backtest the loop skipped

- **Major**: `espero2/backtest.py` + `cli backtest`. The paper rule on `data/panel` (42 coins, 1,826
  dates, next-open fills, 4.5+2 bps/side, 1x, liquidation at ~1.99x against a short, daily marks,
  no funding). Saves `research/sma-panel.json` and a long-only run.
- **Result (exploratory, not pre-registered)**: long/short **+6.3% total, 1.2% CAGR, Sharpe 0.39,
  -94.6% DD** - worse than holding BTC (+31% / 5.6%); 13 liquidations, all on the short side.
  Long-only: **+465% / 41.4% CAGR / 0.45 Sharpe / -84.6% DD**, which matches the equal-weight hold
  (+332% / 34.0% / 0.46) - beta, not alpha. Written up in `research/2026-10-30-sma-panel.md`.
- **Consequence**: the short configuration is retired from the paper books; long-only is the only
  version that could justify a pre-registration, and only with a criterion that separates it from
  holding the basket.
- **Ledger**: `sma` moved `plumbing` -> `trial`, economic bar `yes`, statistic `partly` (no
  significance test), note carries both results.
- **Bugs found in my own first run** (fixed before believing the numbers): equity was only recorded
  on bars with an active regime, and the equal-weight benchmark was truncated to the shortest listing.
- **Tests**: +2 backtest tests. Suite: 54.

### 2026-10-30 · process correction: the loop ran before any backtest

- **What happened (major, process)**: the supervised loop traded three paper books - long, then short
  after the regime flipped - for ~20 minutes with **no backtest, no pre-registration and no statistic**
  behind the rule. The ledger row said `plumbing` and the CLI required `--allow-plumbing`, so the
  *label* was honest; but the flag was baked into `scripts/supervise.sh`, which turned a one-off
  mechanics check into a permanent trading loop. That is the exact drift this project exists to stop:
  the old sequence is pre-register -> backtest -> forward test, and step two was skipped.
- **Fix**: loop stopped (`KILL` in place); `scripts/supervise.sh` no longer passes `--allow-plumbing`
  unless a `PLUMBING.md` window exists; `ledger.require` now demands a dated window naming the
  strategy with an expiry date, and refuses a missing, stale or wrong-strategy window.
- **Books written before the window are void** for any performance claim; they are demo data.
- **Tests**: +4 (missing window, expired window, wrong strategy, valid window). Suite: 52.

### 2026-10-30 · testnet account in the dashboard

- **Minor**: a fourth card shows the **real testnet account** - value and open positions with uPnL -
  read through the public `clearinghouseState` endpoint **by address, no key**. Address comes from
  `ESPERO2_ACCOUNT` / `HL_WALLET_ADDRESS` or a plain `account.txt`; the `order` command writes that
  file after a fill, so it maintains itself. Missing address renders a hint, not an error; an
  unreachable venue renders "unavailable" and the rest of the page still renders.
- **Minor**: 2 tests (short position card with PnL, no-address hint). Suite: 48.

### 2026-10-30 · dashboard actually refreshes

- **Minor (fix)**: the dashboard was a snapshot — `dashboard.html` was written once and the page's
  30 s reload just re-read the same stale file (it showed three flat books while the loop held three
  shorts). `run --dashboard` now rewrites the file after every cycle, and `scripts/supervise.sh`
  passes the flag. The page now follows the loop.
- **Note**: the dashboard reads `paper.db` only. Testnet account positions (e.g. the XPL short) are
  not in it, by design - they are not paper book state.

### 2026-10-30 · venue resolved

- **Minor (no code)**: recorded that Hyperliquid governs. The US venue plan is a guard rail written
  for a US holder (Hyperliquid's terms exclude US persons; the API itself is open), and it is not
  the governing document for this account. The holder still confirms eligibility against the venue's
  current terms - that check is theirs, not the code's.

### 2026-10-30 · docs and housekeeping

- **Minor**: `README.md` — quickstart, gate, supervision, dashboard, long/short, signing.
- **Minor**: `.gitignore` protects `.env`, `*.db`, `books/`, `data_raw/`, `recordings/`, logs.
- **Minor**: `NOTES.md` — provenance, exclusions, design intent, open question.
- **Major**: this file.

---

## Where the code stands

| area | state |
|---|---|
| data | 2.3 GB raw + 14 MB curated + 86 reference docs, hashed |
| paper engine | long/short, taker fills + slippage, mirrored stops, funding (venue), liquidation floor |
| journals | per-coin books, bars/signals/orders/equity, heartbeat |
| execution | testnet only, five guards, long-only unless `--allow-short` |
| supervision | shell supervisor + launchd unit, heartbeat + `health` |
| UI | terminal home screen + HTML dashboard |
| tests | 46 |

## Deviations from the original, on purpose

- No defensive "sell everything" rule; exits are the stop or the regime flip.
- No leverage, margin maintenance, or liquidation ladder — 1× only, with a zero-equity floor.
- Funding mixes venues: testnet prices, mainnet realised funding (documented assumption).
- No forward-test framework, no daily job, no accounts other than the three coin books.
- The TUI is a port of the *look*; the original's menus for board/scan/fast/carry/forward/factors are
  absent because the modules behind them are.

## Open items

- Live loop runs `sma` as `plumbing`; no strategy has a `holds` row yet.
- Testnet prices are unrealistic (SOL spread ~21 bps); fills inherit that.
- `--funding-venue` is not exposed on the CLI yet (mainnet is the code default).
- Leverage is fixed at 1x; `Rules` has the knobs but nothing passes them.
- **Venue: Hyperliquid governs** (holder is non-US, per the holder's statement). The original's
  `VENUE_CONFIRMATION.md` is a **guard rail for a US holder** - Hyperliquid's terms exclude US persons
  even though the public API answers from anywhere - and it does not apply here. The repo itself
  records the resolution in its uncommitted `VENUE_NONUS.md`. Our cost model (4.5 bps taker, hourly
  funding) and the testnet fill venue are therefore aligned. Still the holder's step zero: confirm
  the country of residence against Hyperliquid's current terms, and note that a US-based *operator*
  would still be a US person trading.
- No git commit; nothing pushed.
