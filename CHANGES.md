# Changes — espero2

Everything built in this project since forking from `espero` (the original). **Maintenance rule: every
change, major or minor, gets one dated line here in the same turn it is made.** The repository is
public and pushed; commits are the record. The log runs oldest → newest, with a current-state summary
at the top.

- **Source of the fork:** `/Users/fredp/Espero Trading QuantBot/espero` at `765a5b9` (read-only).
- **What was reused:** data, recorded market material and the research corpus. **No code was copied**;
  the point was a different implementation with the same discipline.
- **First version of this file:** 2026-10-30, written after the short/funding work.

## Current state (2026-11-01)

- **171 tests** green; working tree clean, pushed.
- **Paper loop running** under the plumbing window (`PLUMBING.md` to 2026-12-31): BTC/ETH/SOL, vol-target
  2 %, funding gate 25 %/yr, $500 cap. Books are **void** and never read as evidence.
- **E1 recording**: 11 seed events, 0 forced trades; window to 2027-04-30, 70 % power, OBF boundaries set.
- **Dashboard**: operator optics (10 markets, connections, data sources), gated forecasts, BTC tape.
- **Research**: the liquidation mechanism is the only directional result that survives selection;
  carry/XS/regimes/tape edges fail; volatility, VPIN and maker fills are risk/execution instruments.
- **Data**: 16 substrate tables — see `research/DATA_INVENTORY.md`.
- **Agent layer**: catalog + sandboxed executor; `run`, `order`, `trade` are refused to agents.

## Conventions

- **Major**: a new capability (shorts, funding, supervisor) or a schema change.
- **Minor**: a fix, a test, a doc line, a label.
- **Breaking**: changes the meaning of an existing journal row or CLI flag; always noted.
- Tests: `python -m unittest discover -s tests -t .` — currently **171 passing**.

---

## Changelog

### 2026-11-01 · PR #6 visible in the product

- **Dashboard** gains **"HL venue liquidity & forecast audit"**: OI $10.75B, 24 h volume $2.51B,
  24 h liquidations $27.65M (75 % long), 180 contracts, taker/maker 4.5/1.5 bps, the top-5 coins by OI,
  history counts from `forecast_liquidity.duckdb` (5 exchange / 150 coin snapshots), and the audit verdict
  **no model promoted** (CRPS 0.08051 vs 0.08030).
- **TUI** research view gains the same venue-liquidity block.
- Banner states the honest status: candidate feature, no history yet, **not used in the forecast**.
- Snapshot job `io.espero2.liquidity` runs every 15 minutes; card flags stale after 30.
- Tests: 2 liquidity row tests; suite **209**.

### 2026-11-01 · live forecast coverage completed (PR #6 follow-through)

- **PR #6 merged** the research layer (`forecast_audit.py`, `forecast_liquidity.py`, `auth_data_audit.py`)
  but left the live forecast with **6 UNMAPPED** markets, because `optics.py` reads only Binance
  `funding_multi` and those coins had no rows.
- **The archive had them**: `funding_fetch.py` pulled Binance monthly funding for HYPE, ZEC, NEAR, PUMP,
  ENA, XPL (and UNI, which appeared in the top-10 during the run) — 1,400–2,900 rows each, plus HL hourly
  and OKX where available.
- **Live result**: forecast now **10/10 CONTEXT ONLY, 0 UNMAPPED**; states resolve for every market
  (BTC `down/low/low`, −187 bps 20 d; HYPE/ZEC `up/low/high`, −319 bps; NEAR/ENA `up/high/high`, −426 bps).
- **`scripts/refresh_funding.sh`**: refreshes funding for the 17-coin universe once a day, appended to the
  07:45 sync chain before the E1 data commit, so coverage cannot silently decay.
- No change to `forecast.py` or `optics.py`: the fix was data and scheduling, as the PR intended.

### 2026-11-01 · E1 event log auto-committed daily

- **`scripts/e1_commit.sh`**: after the 07:45 recorder runs, commits `e1_events.csv`, `e1_status.json`,
  `e1_progress.json` and `e1_feed_status.json` with a dated message (`data: E1 events for YYYY-MM-DD`)
  and pushes. No changes → no commit.
- **Why**: those files are rewritten every morning and were tracked, so the tree went dirty daily; this
  keeps it clean and turns the E1 feed into a dated audit trail of exactly what the recorder saw.
- **Scheduled**: appended to the sync chain after the progress step.
- Verified by running it now: `e1 commit: no changes`, exit 0.
### 2026-11-01 · research: #20/#21 forecast retest (owner follow-up)

- **`research/RESULTS_2026-11-01-lows21-forecast.md`**: #21's spike cross-section is **not
  forecastable** from `share` (IC +0.05, 95% CI −0.06 … +0.17); #20's bounce **is** forecastable by
  prior volatility (IC +0.028, CI 0.017 … 0.039, t 5.03) but the top-vs-all spread is **+1.1 bps**,
  below the 9 bps round trip. The original #21 FAIL and #20 real-not-tradable stand.
- **`research/retest_20_21.py`**, `research/retest_20_21.json`, 8 tests.
- No data fetched; no forward window read.

### 2026-11-01 · pre-registration: #20 and #21 forecast retests

- **`research/PREREGISTRATION_2026-11-01-lows21-forecast.md`**: the project owner asked for #20 and
  #21 specifically. Tests whether the event cross-section is forecastable from information known at
  entry — #21 `share` → signed 24 h excess; #20 prior volatility → 1 h bounce — on the published
  event files, with fixed design/validation splits and BH across the two primaries.
- No data fetched; no forward window read.

### 2026-11-01 · research: retest the remaining audit findings

- **`research/RESULTS_2026-11-01-remaining-findings.md`**: six open audit rows retested out of time —
  #1 funding, #4 TSMOM, #8 multi-factor, #9b lead-lag, #15 trend, #43 horizon map. **No tradeable
  forecast.** #9b is the only significant IC (0.035, t 5.30) and its 4.0 bps spread is below the 9 bps
  cost; #4's nominal pass fails a significance test (alpha t 1.10); #43's 12-hour confirmation fails
  its own deflated bar (−9.6 bps, t −0.97); #1/#8/#15 do not forecast out of time.
- **`research/remaining_forecasts.py`**, `research/remaining_forecasts.json`, 18 helper tests.
- The other 39 ids are dispositioned in the result: 6 local retests, 8 re-estimates by #44, 3 clean
  fails, 9 running forward tests, 8 without data or needing a process fix, 5 not hypotheses.
- Data-quality amendment before the verdict: ARB/TIA/WLD/OP ticker collisions and |forward return|
  > 50% are dropped from the daily cross-section (reference/ERRATA.md).
- No data fetched; no forward window read; no ledger row or order written.

### 2026-11-01 · pre-registration: retest the remaining audit findings

- **`research/PREREGISTRATION_2026-11-01-remaining-findings.md`**: six fresh retests (#1, #4, #8, #9b,
  #15, #43) for the audit rows that are still open, estimator/forecast-flawed and have local data;
  every other row gets a disposition in the result.
- Forecasts first: out-of-time rank IC with day-block CIs, a spread hurdle, Newey-West t and BH
  across the six; #4 and #15 are judged against exposure-matched benchmarks.
- No data fetched; no forward or sealed window read.

### 2026-11-01 · TUI polish: responsive tables and a research strip

- **Status strip** under the header: `E1 0 forced · look 2026-11-30 · z 4.80 · carry net −1.90 · 2 open ·
  optics 04:09Z` — the research state is visible without opening a menu.
- **One-line rows**: ledger notes, order reasons and holds are clipped to the terminal width; at 80
  columns the screen went from **145 to 84 lines** with no wrapping inside a row.
- **Responsive widths**: sparkline 10/32, holds 15/24, order reason 13/18, ledger note 24/44, padding
  tight below 100 columns. Verified at 80, 100 and 140 columns with zero over-width lines.
- **Dead branch removed** (the unused "Refresh" check).
- Tests: clip + status strip; suite **193**.

### 2026-11-01 · bug: manual buy on a short corrupted the BTC book

- **Root cause**: `buy_manual` refused only when already *long*. Buying while short replaced the position
  with a long without covering it, so the short's proceeds stayed in cash and the new long was counted on
  top — BTC equity jumped from $985 to $1,428 in one cycle.
- **Fix**: manual buy refuses **any** open position; `close_manual` now covers shorts (buys back at the
  ask, signed cash accounting) as well as selling longs.
- **Repair**: BTC paper book reset to $1,000 (plumbing books are void); the loop will re-enter from here.
- **Tests**: 3 regression tests (refuse-while-short, cover-short cash sign, sell-long cash sign); suite **191**.
- **Snapshot**: `research/ui_snapshot.txt` (gitignored) renders the TUI screen for review.

### 2026-11-01 · TUI updated with the research state

- **`espero2/ui.py`**: new menu item **"Market optics & research state"** renders E1 progress (counts
  only), the carry sleeve, the top optics markets (state, funding B/HL, OI, CASCADE/BREAK) and the
  gated forecast labels, plus the BTC tape row — the same JSON the dashboard uses.
- **Research documents** now reads `research/` (our RESULTS and PREREGISTRATION files), not the
  original corpus in `reference/`.
- **Tests**: 5 row-builder tests; suite **188**.

### 2026-11-01 · E1 progress row (counts only, no statistic)

- **`research/e1_progress.py`**: calendar progress, event count, forced-trade count, next registered look
  and its OBF boundary. It **never computes a return, t or z** — enforced by a test that bans those keys.
- **Dashboard**: "E1 progress" card with the banner "progress only — no statistic is computed here".
- **Current**: 11 events, 0 forced, next look 2026-11-30 (boundary 4.80), window 0/181 days locally.
- **Scheduled**: appended to the 07:45 sync chain after the recorder.
- **Tests**: 4 progress cases; suite **183**.

### 2026-11-01 · carry sleeve running (paper)

- **`research/carry_sleeve.py`**: daily check — Coinbase spot long / HL perp short, $1,000 per side,
  5 + 4.5 bps fees and 2 bps slippage per fill; accrues hourly HL funding; exits on two-check funding or
  basis inversion, or margin buffer below 25 %. State in gitignored `carry_sleeve.json` + curve CSV.
- **First check (2026-11-01)**: **BTC opened** (funding +10.1 %/yr, basis +14.3 bps) and **SOL opened**
  (+9.3 %/yr, +10.9 bps); ETH stayed flat at +4.6 %/yr, below the 5 % entry. Fees $1.90; net −$1.90.
- **Scheduled**: added to the 07:45 sync chain (daily after the data copy).
- **Dashboard**: carry-sleeve card (open legs, funding, fees, net), banner says not authorised.
- **Tests**: 8 entry/exit gate tests; suite **179**.

### 2026-11-01 · carry sleeve registered (before any code)

- **`research/PREREGISTRATION_carry_sleeve.md`**: delta-neutral spot-long (Coinbase) / perp-short (HL)
  on BTC/ETH/SOL, $1k per side, 30 % of measured capacity.
- Entry: HL 7-day funding ≥ 5 %/yr, basis ≥ 0, spot spread ≤ 5 bps. Exit: funding < 0 for two days, basis
  < −10 bps for two days, margin buffer < 25 %, or window end.
- Costs: 5 bps Coinbase + 4.5 bps HL + 2 bps slippage per fill (~23 bps round trip).
- Primary metric: funding capture ≥ 0.70 and net > 0 over ≥ 30 observations → ledger `trial`, never `holds`.
- Window 2026-11-01 → 2026-12-31; thresholds fixed, no re-tuning.

### 2026-11-01 · sizing study: vol targeting lost to fixed on the SMA stream

- **`research/sizing_study.py`**: same SMA 20/50 signal, 10 coins, 2020-01 → 2026-03, $10k, 9 bps cost.
- **Matched exposure** (avg gross $931): fixed Sharpe **0.84**, max DD **−9.0 %**; vol-target (1.208 % risk)
  Sharpe **0.49**, max DD **−11.8 %**. Vol targeting sized up in calm chop and down in vol expansion.
- **Live setting** (2 %, $500 cap) runs **1,646** average gross — 1.8× fixed — with −18.9 % DD. The switch
  from $100 fixed changed the risk budget, not just the sizing rule.
- Correction recorded: the earlier claim that vol targeting "improves risk regardless" was too strong.
- Results: `research/RESULTS_sizing.md`; scorecard row added (risk 3).

### 2026-11-01 · docs refresh and repo hygiene

- **README rewritten**: current state, evidence table with the latest studies, unattended jobs, agent
  layer, and the claims the project explicitly does not make (void books, fictional testnet venue,
  no `holds`).
- **CHANGES**: current-state block added; stale claims fixed ("nothing is committed", "46 tests",
  "paper loop stopped"); code-standing table and open items refreshed.
- **Generated `research/forecast.json` untracked + gitignored** — the 15-minute job rewrote it and kept
  the tree dirty (`6b8ae61`).
- **Scorecard placeholder fixed** to the tape-edge row (`15bc621`).

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

### 2026-11-01 · tape-edge design: no forced-flow analogue survives

- **`PREREGISTRATION_tape_edges.md`** before any holdout fetch: four mechanisms (sweep exhaustion,
  absorption, block continuation, divergence), eight cells, BH 10%, 9 bps bar, sealed 61-day holdout.
- **`tape_edges.py --design`** on the 29 cached October days: 703 sweep events, 85 absorption,
  1,135 block, 1,328 divergence. **Every cell fails**: means +0.8 to −4.5 bps, t ≤ 1.1, all net far
  below −8 bps. Absorption has the *wrong* sign (−3.2/−4.5 bps).
- **Holdout never opened**: the registration only unseals if a design cell passes BH and the cost bar.
  The seal file was not written; 2026-08-01 → 2026-09-30 remains unread.
- **Result**: `research/RESULTS_tape_edges_design.md`.

### 2026-11-01 · E1 label semantics and cascade-fuel detector

- **E1 labels corrected**: a live down-break on the proxy is now **`E1-BREAK`** (unconfirmed — the forced
  tag needs the prior-day liquidation distribution). **`E1-FORWARD`** only when the recorder has a
  confirmed forced trade within the last two days. Previously the live break alone was labelled
  E1-FORWARD, which overstated the setup.
- **Cascade fuel implemented**: `cascade_risk = armed and HL funding > 10%/yr and OI percentile ≥ 0.9
  and price rolling over` (close below the prior 20-day low). `research/optics.py` appends an OI snapshot
  every 15 minutes to `research/oi_history.csv` (gitignored) and computes the percentile over the last
  30 days; **armed only after 7 days** of history.
- **Dashboard**: optics table gains **OI %ile** and a **risk** column that shows `CASCADE` (or `BREAK`).
- **Current state**: 1 snapshot per coin → `oi_pct` is `—`, `armed false`, `cascade false`; the detector is
  warming up by construction.
- Tests: E1-BREAK/E1-FORWARD cases and four cascade conditions; suite **171**.

### 2026-10-31 · VPIN and maker-execution pilots

- **`PREREGISTRATION_vpin.md` + `vpin_study.py`**: VPIN (500 equal-volume buckets/day, 50-bucket window)
  on 29 BTC days. Both cells pass BH: next-60m realised variance **+7.6e-5** (t 2.98) and next-30m
  absolute return **+3.95 bps** (t 2.72). A risk/volatility signal, not direction.
- **`PREREGISTRATION_maker.md` + `maker_study.py`** (one-day pilot, SOL 2026-10-01): **62.7% fill rate**,
  median capture **0.42 bps**, markout **+0.47 bps** at 1 min, net **+0.90 bps before fees**, adverse
  share 46.7%. At a 2 bps maker fee the gross becomes **−1.1 bps** — the fee tier decides it; one day is
  not evidence.
- Scorecard: VPIN risk **7**, maker execution **5**.
- Results: `research/RESULTS_vpin.md`, `research/RESULTS_maker.md`.

### 2026-10-31 · tape study 2: seconds OFI and block markout

- **`research/PREREGISTRATION_tape_2.md`** written before running: H5 seconds OFI (30/60/180 s), H6
  markout by print size (10/60 s, 4 buckets), H7 session structure (descriptive).
- **H5 passes BH at all three horizons**: +0.22 bps (t 6.16) at 30 s, +0.13 (2.40) at 60 s, **−0.49
  (−2.09) at 180 s** — continuation at seconds, reversal at minutes. The edge is 40–70× below the 9 bps
  cost bar, so it is a mechanism, not a trade.
- **H6**: raw markout is drift-contaminated; the drift-adjusted version shows **>$1M prints at +0.78 bps
  and $10–100k prints at −0.08/−0.13 bps** — block aggressors are informed, mid-size are not.
- **H7**: flow peaks 13:00–16:00 UTC (81–96k prints/hour vs ~30k at 06:00).
- Bugs caught: pandas 3 non-ns timestamps (OFI returned NaN) and drift contamination in markout.
- Scorecard updated; result in `research/RESULTS_tape_study_2.md`.

### 2026-10-31 · pre-registered tape study: direction fails, volatility survives

- **`research/PREREGISTRATION_tape.md`** written before the fetch: 4 features × 3 horizons (5/15/60 min),
  daily quintile spreads, BH 10%, 9 bps cost bar, one run, every cell reported.
- **`research/tape_study.py`**: Binance UM `BTCUSDT` aggTrades, 29 days (one archive 404), **39,993
  minutes**. **0 of 12 directional cells pass BH**; spreads −0.3 to +2.6 bps, all far below the 9 bps
  cost. Block cells are sparse (9 usable days).
- **H4 survives**: trade intensity predicts next-hour realised variance — **top quintile 1.74× the
  bottom**, 29 days. Tape is a volatility instrument, not a direction instrument.
- **Scorecard updated** (tape flow prediction 1, risk 5; intensity→vol risk 7); result in
  `research/RESULTS_tape_study.md`.

### 2026-10-31 · ops: dashboard changes need a loop restart

- **Observed**: the forecast and tape cards were committed and rendered manually, but the running
  paper loop kept overwriting `dashboard.html` with the **old** renderer — it had imported
  `espero2/dashboard.py` at 01:11, before the cards existed.
- **Fix**: `launchctl kickstart -k gui/$UID/io.espero2.paper`. Verified the loop-written page now
  contains both cards (grep counts 1 each, file written 21:41).
- **Rule**: after changing `dashboard.py` or anything imported by the loop, restart
  `io.espero2.paper`; a manual `dashboard --out` only holds until the next 60 s cycle.

### 2026-10-31 · BTC tape: research note, metrics, dashboard card

- **`research/TAPE_READING.md`**: what tape reading is (aggressor flow, CVD, blocks, sweeps, volume
  profile, absorption, divergence), what is *not* observable (icebergs, spoofs, intent), and canonical
  references (Cont–Kukanov–Stoikov order-flow imbalance; Easley–López de Prado–O'Hara VPIN).
- **`research/tape.py`**: Binance UM daily aggTrades (~21 MB/day, 1.8M prints) → minute flow, CVD,
  $100k blocks, same-ms sweeps, 0.1% volume profile (POC/VA70/HVN), absorption and delta divergence;
  writes `tape.json` + gitignored minute series. **2026-10-29**: 1,804,397 prints, taker buys 48%,
  CVD −9,891 BTC, 45,226 blocks ($12.2B), 2,881 sweeps, price −2.77% from POC, absorption 23%.
- **Live mode**: Coinbase last 1,000 prints, 30-minute window, **side-verified with a consecutive-print
  sign test** (62.5% agreement); venue labelled `coinbase-spot`, never mixed with Binance history.
- **Dashboard**: full-width **BTC tape** card (prints, taker buy share, CVD, blocks, sweeps, POC
  distance, absorption, divergence, one-line read), live slice preferred when <20 min old, stale flag.
- **Scheduled**: 15-min optics job now runs `optics → forecast → tape --live`; the 07:45 sync chain adds
  the previous day's historical tape.
- **Tests**: 15 new (CVD, blocks, sweeps, profile, absorption, divergence, live side validation, card);
  suite **169**.

### 2026-10-31 · forecasts & recommendations on the dashboard (gated)

- **`research/forecast.py`**: for every market in the optics snapshot, look up its regime state in
  `regime_signs` and report the 5/20-day distribution (median, 10-90, P(up) with Wilson CI) minus the
  cost hurdle (9 bps + spread).
- **Fixed rubric, hard-capped**: `UNMAPPED` < `CONTEXT ONLY` < `E1-FORWARD` < `WATCH`; while no strategy
  is in `holds`, the strongest label is **WATCH**. Unknown labels are treated as the strongest claim and
  capped — a test asserts no BUY/SELL/TRADE can ever be emitted.
- **Current output**: 10 markets — 4 `CONTEXT ONLY` (BTC −9 bps/20d, ETH −205, SOL −205, XRP −214, all
  39-50% up), 6 `UNMAPPED` (states with no historical cell, mostly `n/a` funding).
- **Dashboard**: full-width card with the banner ("no strategy in holds · capped at WATCH · not advice"),
  per-market distribution, cost and reason; **stale** flag if the snapshot or optics is older than the
  refresh window.
- **Optics hardened** (the 22:48Z 429 incident): retries with backoff, per-market isolation, and an empty
  run **no longer overwrites** a good snapshot — it writes `optics.failed.json` and exits 2.
- **Scheduled**: the 15-minute optics job now runs `optics.py && forecast.py`.
- **Tests**: 14 new (rubric, cap, Wilson, card, stale, 429 guard); suite **154**.

### 2026-10-31 · universal optics: every market and every source

- **Markets are discovered, not listed**: Hyperliquid perps ∩ Coinbase USD spot, ranked by open interest,
  top 10 — currently BTC, ETH, HYPE, ZEC, SOL, NEAR, XRP, PUMP, ENA, XPL.
- **Per market**: price/spread, state (trend/vol/funding), funding **per venue** (Binance 7-day vs HL
  24-hour history, which now differs by coin: HYPE +33%, XPL +55%, XRP +9.8%), OI, 6 h liquidations,
  and the live E1 break check.
- **Connections block**: every endpoint with status, latency and detail — Coinbase products, HL perps,
  HL spot book, OKX liquidations (4/4 up).
- **Sources block**: freshness of `funding_multi`, `metrics`, `tardis_derivative`,
  `tardis_liquidations`, `bars_daily`, the aggr feed and the paper marks.
- **Dashboard** renders three tables (markets, connections, data sources) full-width; formatting is
  adaptive for sub-dollar prices and OI in k/M/B.
- **Funding coverage**: fetched for XRP/DOGE/ADA/AVAX/LINK/DOT/LTC; markets without Binance history show
  `—` rather than a fake percentile (HYPE/ZEC/NEAR/PUMP/ENA/XPL).
- Suite 141; optics job every 15 minutes.

### 2026-10-31 · operator optics on the dashboard

- **`research/optics.py`**: one live snapshot — Coinbase price/spread, 60-day trend and vol percentile,
  Binance 7-day funding + percentile, HL funding/OI/premium, OKX 6-hour liquidations, and the live E1
  break check (48-bar low, volume z, burst). Writes `research/optics.json`; read-only.
- **Dashboard**: new **operator optics** card showing per coin: px, state, funding B/HL, OI, liquidation
  L/S, and **BREAK** when E1's condition is live. Data-quality flags render in the footer.
- **Scheduled**: `io.espero2.optics` launchd agent, every **15 minutes** (`scripts/install-optics.sh`).
- **Live values at install**: BTC `up/low/low` · funding B +2.7%/HL +10.9% · OI 41k · liq L $5.1M/S $39.9M;
  ETH `down/low/high` · OI 977k; SOL `down/low/high` · OI 5.41M · liq L $167k/S $67k.
- **Tests**: 3 for the card (render, missing snapshot, BREAK); suite 141.

### 2026-10-31 · measurement scorecard and positioning study

- **`research/positioning_study.py`**: SOL open interest, taker flow and top-trader long/short ratios
  against forward 1/5-day returns. Overlap is only **117 days** (prices end 2026-03); **12 cells, zero
  with |t| ≥ 2** (0.6 expected by chance). No support.
- **`research/MEASUREMENT_SCORECARD.md`**: every sign rated 1–10 for **prediction** and for **risk use**,
  with the evidence behind each number.
- **Result**: liquidation **9** (survives 121-cell correction), volatility **9 as risk / 1 as
  prediction**, funding **3/6**, basis **4/6**, trend **1/3**, positioning **1–2/5**, OBI **unrated**.

### 2026-10-31 · live signal check (proxy) between feeds

- **`research/live_signal.py`**: evaluates E1's conditions on live proxies — Coinbase 5m candles for the
  down-break/volume-z/burst test, OKX liquidations for the forced share — so "is there a signal now?"
  is answerable between the daily feeds. Labels every condition pass/fail.
- **Today (2026-10-31)**: BTC **+28.4 bp above** its 48-bar low, vol z **−0.28**, burst +1.3 bp → **no
  down-break**; flow is **$34.2M of short liquidations vs $0 long in 6 h** (the mirror of E1's rule).
  SOL +46.1 bp above the low, vol z −2.50 → no down-break either.
- **Why the real rule still waits**: E1 uses Binance 5m bars and the daily aggr feed, which land after
  the UTC close (07:45 sync); tags additionally need the prior day's terciles.

### 2026-10-31 · hardening: selection cost, E1 power, maker fills

- **`research/selection_cost.py`** (+ `trials.csv`): exact two-sided tails, Monte-Carlo null maximum,
  family-wise correction over the registered 9 and the full 121 cells. **The liquidation mechanism
  survives** (liq26_D p 2.9e-7, family-wise 3.5e-5) and so does the executable variant (p 6.1e-5),
  while carry (0.19), regimes (0.56), premium (0.68) and XS (0.96) do not.
- **`research/e1_monitor.py`**: O'Brien-Fleming boundaries for six monthly looks (4.80 → 1.96) and a
  power simulation: **70.4%** chance of detecting a true +32 bps effect by the final look, 30% false
  negative. Current E1: 11 events, 0 forced trades.
- **`research/maker_fill.py`**: Tardis SOL 2026-10-01 (11.3M book updates, 1.95M trades). Passive fills
  within 60 s: **61.5% buy / 63.5% sell**, ranging 50–77% by spread quartile — tighter spreads fill
  *less*. The 22–87% cost assumption is validated as a range but too wide to price a quiet regime.
- **Bugs caught**: a tanh normal approximation that turned p=3e-7 into 0.006, and a power simulation
  that under-diversified noise by `sqrt(n)`.

### 2026-10-31 · regime signs studied and applied to today's market

- **`research/regime_signs.py`**: 8 states (trend × vol × funding), market-relative 5/20-day outcomes,
  42 symbols, 2023-01 → 2025-06, BH FDR. **16 cells, 0 pass.**
- **Coherent descriptive pattern**: `up/low/high` and `up/high/high` (uptrend with expensive funding)
  → 20-day median **−319 / −426 bps**, positive only **37%** of the time — the crowded-long fade again.
- **`research/regime_now.py`**: classifies today from live data (Coinbase daily candles, Binance
  funding percentile, HL venue funding/OI/premium, OKX liquidations).
- **Today (2026-10-31)**: SOL `down/low/high` (hist median −205 bps at 20d), BTC `up/low/low`
  (≈flat), with **$39.9M of short liquidations vs $5.1M long** in BTC over 24 h — a short squeeze —
  and HL funding +10.9%/yr on both.
- **Verdict**: context, not a forecast; no cell survives multiplicity, no trade authorised.

### 2026-10-31 · data inventory, generated from the database

- **`research/inventory.py`** lists every substrate table with rows, real time span and key columns;
  writes `research/DATA_INVENTORY.md`.
- **16 tables**: bars_daily 82,774 (2020 → 2026-03), bars 128,959 (5m, 2021 → 2025-06), rv, funding
  108,374, funding_multi 3,818 (2025-07 → 2026-10), metrics 105,120, tardis_derivative 4,415,916,
  tardis_liquidations 44,353, book_ticker 45.5M (one day), trades 3.3M (one day), obi 4,320,
  tardis_book 1,440, premium 13,675, depth 1.73M, liquidation_multi 100.
- **Known data-quality issues surfaced**: `depth.day` is encoded as year-1 dates (parsing bug in the
  depth ingest), and `liquidation_multi` collapses fills sharing ts/price/qty (PK too coarse).

### 2026-10-31 · Tardis.dev data: funding, OI and liquidations for two years

- **What it is**: Tardis.dev publishes normalized historical exchange data. Its CSV datasets are free
  for the **first day of each month**, no API key:
  `https://datasets.tardis.dev/v1/binance-futures/{channel}/{Y}/{M}/01/{SYMBOL}.csv.gz`.
- **Channels that close our gaps**: `derivative_ticker` (funding, predicted funding, **open interest**,
  mark/index), `liquidations` (Binance forceOrder), `book_ticker` (with amounts), `trades`,
  `book_snapshot_25`. Also available: bybit (`allLiquidation`), okex (`liquidations`), deribit
  (options/IV), hyperliquid since 2024-10-29 (no liquidation channel).
- **`research/tardis_fetch.py`** ingests monthly samples into `tardis_derivative`, `tardis_liquidations`
  and `tardis_book`. Ran for SOLUSDT/BTCUSDT, 2025-01 → 2026-10: **4.42M derivative rows**, **44,353
  liquidation fills**, plus 1,440 book minutes for SOL.
- **Findings (SOL)**: funding flips sign month to month — sampled-day annualised values range from
  **−29.6%** (2026-02) to **+7.9%** (2025-10), and **−0.23%** on the 2026-10 sample, so "SOL funding is
  positive" is not a property of SOL. OI 6.8M–10.9M SOL (mean 8.72M). Sampled liquidation totals are
  similar in 2025 ($51.9M) and 2026 ($47.6M) but the **average fill grew from $4.4k to $7.4k**.
- **Book 2026-10-01**: median OBI **+0.009** (balanced), median spread **0.85 bps**.
- **Cost**: samples are one day per month; full daily history needs a paid key (tardis.dev/#order).

### 2026-10-31 · E1 records itself (local feed) and refreshes daily

- **Problem**: the maintainer's `liqbreak` step failed on the first window day, so
  `liqbreak_trades.csv` was empty while the raw 5m aggr feed (10,368 rows) had arrived — E1 would have
  recorded "0 events" for a reason unrelated to the market.
- **Fix**: `research/e1_feed.py` recomputes the #26/#27 rule locally from `data/aggr/forward5m` +
  `lows/forward` (48-bar down-break, volume z ≥ 2, forced share = prior-hour long liquidations /
  quote volume, one per coin/direction/hour, entries after 01:00 UTC) and writes `research/e1_events.csv`
  with prior-day tercile tags. `e1_recorder.py` prefers that file over the upstream ledger.
- **Day 1 (2026-10-30)**: **11 down-break events** across 9 coins, all tagged `middle` (no prior day
  yet, so no trades — correct); the tag distribution is seeded for 2026-10-31's events.
- **Daily refresh**: `io.espero2.sync` now runs sync → `e1_feed.py` → `e1_recorder.py` at 07:45, so E1
  keeps recording even when the upstream job is broken.
- **Repo hygiene**: `health.json` and the forward ledgers were tracked and dirtied by every sync —
  now gitignored and untracked.

### 2026-10-31 · risk sizing live in the paper loop

- **Enabled** in the supervisor: `--vol-target 2 --max-funding 25 --max-notional 500` for the running
  BTC/ETH/SOL loop (was fixed $100 notional, no gate).
- **`--max-notional` exposed** on `run`; the old hard-coded $100 cap was silently binding the vol-target
  size, so every coin got exactly $100. With the cap at $500 the sizing now operates.
- **Observed**: BTC 35%/yr vol → notional **500** (still capped), ETH 47% → **403.96**, SOL 63% →
  **302.30** — inverse to volatility, which is the point.
- **Funding gate**: active but not binding today (HL funding ~3.9%/yr vs the 25% cap).
- Loop restarted via `launchctl kickstart`; 138 tests green.

### 2026-10-31 · risk sizing, funding gate, OI and order-book imbalance data

- **`espero2/risk.py`**: Wilder ATR, realised vol, **volatility-target sizing** (`risk %` of equity per
  position at kσ), and a **funding gate** (skip entries paying more than a cap). Pure functions, 4 tests.
- **Wired into the paper engine**: `Rules(vol_target_pct=…, max_funding_annual_pct=…)`; `run` flags
  `--vol-target` / `--max-funding`; both **default off** so the running loop is unchanged. Demo:
  `--vol-target 2 --max-funding 25` → vol target 2% at 35%/yr → notional 100 (capped), long opened.
- **Bug caught by the demo**: the gate first fired on the *constant fallback* (1 bp/h ≈ 87.6%/yr) and
  blocked every long. It now gates only on **known venue funding** (fetches the last 3 h if flat).
- **Metrics ingested**: `research/metrics_fetch.py` → **105,120 five-minute rows** for SOLUSDT,
  2025-10-31 → 2026-10-30, mean OI **9.12M SOL** (OI, top-trader and taker ratios).
- **Order-book imbalance**: `research/book_fetch.py` → **4,320 minute rows** for GALA/DOGE/SUI on
  2024-01-02, median OBI ≈ 0, median spread 1.1–3.1 bps. bookTicker with sizes is ~20–130 MB/day and
  mostly stops in 2024, so the sample is deliberately small.
- **Catalog**: `metrics fetch` and `book fetch` added as write tools.

### 2026-10-31 · per-coin research tool (`coin report`)

- **`research/coin_report.py`**: substrate snapshot for one coin — coverage and last close, 30d/90d
  returns, annualised vol, median realised variance, funding profile, COIN-M liquidation totals, and
  the next-hour distribution after that coin's own top-1% long-liquidation hours. Descriptive only.
- **Catalog**: `coin report` added as a read tool, so "run research on SOL" is one audited call.
- **Observed for SOL**: 2,020 days from 2020-09; 90d −33.3%; annualised vol 118%; funding +0.544 bp/8h
  positive 75% of intervals; 25,658 COIN-M fills / $35.9M; after 26 top-1% long-liq hours the next hour
  averages +73.5 bp (median +68.3, 58% up, p10 −149 / p90 +360) — a small-n descriptive cell.
- **Dependencies**: `duckdb` and `statsmodels` added to `requirements.txt` and installed in the
  project venv (the agent tools run with it).

### 2026-10-31 · signals tool for the operator

- **`research/signals.py`**: read-only snapshot — mid, spread, SMA20/50 and the regime flag for a coin
  list on Hyperliquid. No orders, no writes; unavailable coins are reported, not fatal.
- **Catalog**: `signals` added as a `read` tool, so the operator can answer "signals on the top 5?"
  through the same audited executor as everything else.
- **Live answer**: BTC long; ETH, SOL, DOGE, AVAX short (1h SMA 20/50).
- **Label carried with it**: the `sma` ledger row is `plumbing` — these flags are mechanics data, not
  evidence, and no position is authorised.
- **Fix**: candle dicts use `close`, not `c`; script adds the repo root to `sys.path` when run as a file.

### 2026-10-31 · agent operator smoke test

- **`agent/smoke.py`**: a scripted five-step operator session through the real executor — see the
  surface, `health`, `ledger`, `e1 status`, `report`, deterministic briefing — then attempt `trade`
  and `run` and confirm both are refused. 8 audited calls, exit 0.
- **Observed** in the run: loop heartbeat 46 s, ledger `sma` in `plumbing`, E1 window open with
  0 days recorded, paper book BTC 999.41 / ETH 999.82, trading refused by privilege.
- **`duration_s`** exposed on tool results so a session can show timing.
- **Test**: `tests/test_smoke.py` runs the session (0.6 s, no network beyond local reads).
- Suite: 134.

### 2026-10-31 · agent layer: deterministic core, agent shell

- **`agent/catalog.py`**: every operation classified (`read`, `research`, `write`, `privileged`) with
  argv templates and argument guards; tests assert the catalog covers the CLI exactly
  (`espero2.cli.build_parser()` was extracted for this) and that privileged verbs are never offered.
- **`agent/tools.py`**: the only executor — subprocess, no shell, timeout, 256 KB output cap with
  spill, `fcntl` lock, secrets stripped from the environment, one JSONL audit line per call, and
  `--dry-run` that resolves argv without spawning. Refuses `run`, `order`, `trade`, `cb order`, `ui`.
- **`agent/brief.py`**: deterministic daily briefing (E1 window/state, paper book, ledger statuses,
  health); writes `research/agent/brief-YYYY-MM-DD.md`. No LLM, no key.
- **`agent/loop.py`**: optional DeepSeek-compatible loop, **off by default**, only catalog tools,
  12 calls / 3 turns cap; a model asking for `trade` raises instead of being obeyed.
- **Tests**: 20 new (`test_catalog`, `test_agent_tools`, `test_brief`, `test_loop_guard`).
- **Unchanged by design**: ledger gate, paper engine, order paths, launchd plists; the running loop
  was not touched.

### 2026-11-01 · inheritance map v2, the five-mode audit, and the rule in CI

- **`research/INHERITANCE.md`** rewritten to the requested shape: per original id — what it
  **concluded**, what we **built on it**, and what it **contradicts** (e.g. #21 → R1 finds the effect
  gone; #26 → R2 replicates but E1 tests the executable fix; #8 → R6 shows factor books flip sign).
- **The eight unledgered documents audited against the five failure modes** (estimator, cost bar,
  overlapping windows, executable tag, venue). **Two real gaps found**: `regime-signs` reports means
  over overlapping 5d/20d windows without a correction; `tape-edges-design` reports means with t
  without stating the estimator. Both ledgered with the caveat; the other six are clean.
- **Rule enforced, not just written**: `research/RESULT_TEMPLATE.md` (required sections) and
  `scripts/check_inheritance.py` fail the build if any ledger row or result document is missing from
  the map; wired into `scripts/check.sh`. The rule is also in README.
- **CI**: 46 originals, 20 ledger rows, 20 result documents referenced — all green; suite 193.

### 2026-11-01 · inheritance map; the eight unledgered documents ledgered

- **`research/INHERITANCE.md`**: every original id (46) mapped to our descendants, and every finding of
  ours mapped to its ancestor and the lessons it carries. Numbers: **21 descendants across 16
  originals**; **30 originals inherited as negative evidence only**; E1 is the forward test of #26.
- **Audited the 8 documents that had no ledger row** against the five failure modes: all apply a 9 bps
  cost bar where a return is claimed, use BH for multiplicity, and state one-month/one-venue limits.
  None overclaims. They are now **R11–R18** with status `audit`, so the trial count is complete.
- **Ledger now 20 rows**; suite 193 tests green.
- **Rule added**: a result cites its ancestor or says `no ancestor`; a negative ancestor justifies not
  re-running a family but never counts as evidence.

### 2026-10-31 · funding fix in the running loop

- **Bug**: `paper.tick` charged the 1 bp/h constant whenever no funding settlement fell inside the
  60-second tick window — i.e. almost every tick — instead of the venue's observed rate.
- **Fix**: cache the last venue rate per coin (`last_rate_bps`), expose it from `Store.get_state`, and
  charge the cached venue rate between settlements; the constant is used only when no venue rate has
  ever been seen. Verified in the log: `funding +0.0001 (venue-mainnet (cached))` with BTC at
  +0.125 bp/h (≈11%/yr) instead of the 1 bp/h constant.
- **Also observed**: vol targeting and the funding gate landed from the parallel session (6 commits:
  spot tool, multi-venue funding ingest, OKX liquidations, OI/OBI ingest, vol targeting wired,
  gitignore). The loop is sizing positions at 2% vol target.

### 2026-10-31 · continuous paper run while E1 records

- **Plumbing window extended** to **2026-12-31** (was 2026-11-02) with the purpose restated: continuous
  mechanics run, books void, never read as evidence.
- **Ledger**: `sma` returned to `plumbing` (not `retired`) for the duration of the window; the note
  says exactly that and why.
- **KILL lifted** (archived as `KILL.paused`); stop the loop again by `touch KILL`.
- **Supervisor hardened**: `scripts/supervise.sh` prefers the project `.venv/bin/python`
  (Python 3.12); a project `.venv` was created from `requirements.txt` because the system Python is
  3.9 and cannot run the code.
- **Running**: `io.espero2.paper` launchd agent, 60 s cadence, BTC/ETH/SOL, dashboard rewritten each
  cycle. Verified: 3 positions opened, equity rows growing, log ticking.
- **E1 is unaffected**: it is the daily recorder, not this loop.

### 2026-10-31 · liquidation anatomy (descriptive)

- **Built** `research/liquidation_anatomy.py`: hourly liquidation spikes (99th percentile per coin,
  2023-01 → 2024-11, ten coins) conditioned on the shape of the preceding 1h/2h/4h and on consecutive
  down hours, with day-clustered bootstrap intervals.
- **Long side (246 events)**: aligned-bear n=216 → next 1h +12.8 bps mean, +23.5 median, 56% up,
  CI −30…+57. Four consecutive down hours → **60% up, median +40 bps, mean −3.4** (fat left tail).
- **Short side (244 events)**: aligned-bull n=197 → next 1h −7.7 bps, 47% up — no continuation or
  reversal; the one negative small cell is multiplicity noise.
- **Conclusion**: liquidations produce a positively skewed bounce, not a reliable reversal; useful for
  risk sizing, not as a signal. Descriptive only — no trading claim.
- **Ledger `R10` (audit)**; result `research/RESULTS_liquidation_anatomy.md`.

### 2026-10-30 · RG1: nine regime families implemented and tested — none survives validation

- **Implemented** `research/regimes.py`: trend (SMA20/50, 200d, 20d), HAR vol state, vol-of-vol,
  breadth, average pairwise correlation, funding sign, drawdown, liquidity — plus a combined
  `har_trend` state; written to `regimes.csv`.
- **Validation 2023**: none passes BH FDR across eleven tests; best is trend_20d at t 1.27;
  `har_trend` is −23 bps, t −0.27 — gating E1 on it would have been decoration.
- **Holdout (sealed, read once for the test)**: `corr_high` +330 bps, t 3.26, both halves positive —
  but flat in validation (t 0.32), so holdout-only and not actionable under the registration;
  trend_20d passes FDR with the opposite sign to validation.
- **Not testable**: `funding_pos` (positive on 2,221/2,282 days) and `liq_stress` (no design-window
  liquidations).
- **Disclosed**: two evaluation bugs fixed before the final numbers (NW covariance, state/NaN), so the
  holdout was read three times, all within the registration and for code fixes only.
- **Ledger `R9` retired**; result `research/RESULTS_regimes.md`.

### 2026-10-30 · dashboard fix: direction, headers, no bare tables

- **Positions show direction explicitly** — a dedicated `direction` column renders **LONG** or
  **SHORT** (green/red), derived from Alpaca's `side` and falling back to the sign of quantity.
- **Every table has a header row**: account metrics, positions (symbol/direction/qty/value/P&L), open
  orders (symbol/side/qty/type/status), research state (research/value).
- **Empty states** say `flat` / `none` with the right colspan instead of an unstyled orphan row.
- **Verified on the live render**: BTCUSD and ETHUSD show LONG; AAPL/AMZN/META/TSLA orders show
  BUY/SELL with headers.

### 2026-10-30 · dashboard shows the Alpaca paper account

- **New card**: cash, buying power, portfolio value, status; positions with qty, market value and
  unrealised P&L; open orders with side, qty, type and status.
- **Live render**: BTCUSD $99.78 and ETHUSD $49.89 positions, plus AAPL/AMZN/META/TSLA queued orders.
- **Degrades safely**: a venue outage renders "unavailable" instead of crashing the page; fetch failure
  is unit-tested.
- **Tests**: 3 (`test_meta.py`: card renders positions/orders, unavailable message, fetch failure).

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
| data | 16 substrate tables (`research/DATA_INVENTORY.md`), Tardis/monthly samples, live optics cache |
| paper engine | long/short, taker fills + slippage, stops, funding, liquidation floor, vol-target sizing |
| journals | per-coin books, bars/signals/orders/equity, heartbeat |
| execution | testnet only, no mainnet path; maker-fill model measured (61–64 %) |
| supervision | launchd: paper 60 s, optics 15 min, sync 07:45, health 08:30 |
| UI | terminal home screen + HTML dashboard (optics, forecasts, tape) |
| research | audit, replications, E1, tape/VPIN/maker studies, scorecard, registrations |
| agent | catalog + sandboxed executor; privileged verbs refused |
| tests | 171 |

## Deviations from the original, on purpose

- No defensive "sell everything" rule; exits are the stop or the regime flip.
- No leverage, margin maintenance, or liquidation ladder — 1× only, with a zero-equity floor.
- Funding mixes venues: testnet prices, mainnet realised funding (documented assumption).
- Forward tests now exist (E1 recorder + daily job) and the dashboard/optics/tape jobs are scheduled; the original's three-coin book structure remains.
- The TUI is a port of the *look*; the original's menus for board/scan/fast/carry/forward/factors are
  absent because the modules behind them are.

## Open items

- **E1 is the only live test**: recording until 2027-04-30; forced tags arrive with the daily sync.
- **Nothing authorised**: no `holds` row; the paper loop remains plumbing and its books void.
- **Fills are fictional**: HL testnet prices run ~8 % off spot on ~21 bps spreads.
- **Cascade detector warming up**: needs 7 days of OI snapshots before it can arm.
- **Carry sleeve not built**: funding is venue-dependent (HL +10.9 %/yr, OKX +3.5 %, Binance −0.3 %);
  a delta-neutral sleeve needs its own registration and a 30–60 day paper test.
- **Vol-target sizing not yet measured against fixed sizing on history.**
- **Fee tier decides maker economics**: +0.9 bps net at zero fees, −1.1 bps at 2 bps.
