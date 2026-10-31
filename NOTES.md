# espero2 — a different solution, built from espero's data and evidence

Started 2026-10-30. Source of the copied material:
`/Users/fredp/Espero Trading QuantBot/espero` (git `765a5b9`), read-only.

This directory is **not a fork**. It takes the data and the published findings — the parts that are
expensive to reproduce — and starts from a different architecture. The old code is deliberately not
copied: the point is a different solution, not a rename.

## What was copied, and why

| path | size | why it is here |
|---|---|---|
| `data/panel/` | 6.4 MB | 42-coin wide daily OHLCV, 2018→2026. The only market data that supports cross-sectional work. |
| `data/aggr/` | 6.9 MB | aggr hourly bars, **explore** (Apr–Jun 2026) and **holdout** (Jul–Oct 2026), already sealed with hashes upstream. The raw material for the one effect the old repo could not kill (#26). |
| `data/funding/` | 96 KB | funding rates, for carry and for conditioning. |
| `data/BTCUSD_86400s.csv`, `data/ETHUSD_86400s.csv` | 220 KB | the two series every sanity check needs. |
| `reference/*.md` | 600 KB | all 86 research documents: pre-registrations, results, forward plans, errata, audits. Read as prior art, never edited. |
| `reference/costs_table.py` | 6 KB | the measured per-venue cost cells (#39/#41). Data, not code to depend on — copy the numbers into the new system. |
| `reference/venues.py` | 5 KB | venue fees, symbol conventions, minimums. |

Integrity: `MANIFEST.sha256` covers all 128 copied files. `shasum -a 256 -c MANIFEST.sha256` re-checks
them. The upstream repo's own copy of this data is at `research/data/` and `data/`; nothing here was
modified on the way in.

## Second copy — everything else, with the owner's permission (2026-10-30)

| path | size | contents | why |
|---|---|---|---|
| `books/` | 17 MB | 12 SQLite snapshots of the paper journals (`degen*`, `features`, `mf*`, `xs`, `carry*`, `fast`, `tsmom`) | consistent copies via SQLite's backup API, so a WAL is not half-copied |
| `recordings/hlcollect/` | 20 MB | Hyperliquid position/HLP/context/1m recordings | irreplaceable, same reason the old repo forbids deleting them |
| `recordings/lows_forward/` | 552 KB | the #20 forward recording | the only copy of those days |
| `data_raw/` | 2.3 GB | `bids book cache degen levetf liq liq2 lows markout markout_small oi panel_hourly panel_peers panel_peers_hl polymarket settle trend` | the raw archives behind the published numbers |
| `.env` | 3 KB | the account holder's environment file | copied on explicit instruction; mode 0600, never opened or printed |

Bulk integrity: every directory in `data_raw/` was compared against the source with `du -sk`
(all equal, one rounded by 4 KB). `books/tsmom.db` passed `PRAGMA quick_check`; the other eleven are
SQLite backup snapshots. `.env` was copied by `cp -p` and `chmod 600`, and its contents were never
read.

**Security note.** A second copy of live API credentials now exists at
`espero2/.env`. It is in `.gitignore`, but a copy is a copy: delete it
(`rm espero2/.env`) or rotate the keys when this project no longer needs them. Nothing in
`espero2/` reads it today — the harness has no signing code.

**What is still not here:** `.git`, `.venv`, build artefacts. Everything else from the source
directory has been copied.

## What is different by design

1. **The trial is a first-class object.** A hypothesis is declared before it runs — estimand,
   estimator, hurdle, economic bar, number of trials — and the runner refuses to compute a statistic
   the declaration does not name. In the old repo this existed only as prose in a pre-registration.
2. **The gate is the product, not an appendix.** The ledger and its two hurdles decide what may be
   called a pass, what may be replicated, and what may reach a sizing document. Everything else is a
   plugin.
3. **Storage is SQL.** Panels live in DuckDB (parquet/CSV import), not in pandas objects rebuilt on
   every run. That is what makes "recompute the whole ledger" cheap enough to run in CI.
4. **No live execution path.** Capital is out of scope for this project; the ceiling is a paper
   ledger and an execution simulation against measured costs. The old repo shipped a live path that
   trades a strategy its own numbers reject — this one does not ship one at all.

## Open question (needs one decision)

Which of these is the build:

- **A — trial engine.** DuckDB + polars; declare → compute → ledger → gate; one dataset (panel or
  aggr) proving the loop end to end.
- **B — paper exchange.** Queue-position matching engine with measured costs, venue-agnostic, fed by
  the aggr or panel data; the ledger decides which strategies get a simulation.
- **C — portfolio lab.** Capital allocation across a small set of already-evidenced effects, with
  deflated Sharpe and exposure accounting; the gate decides what enters the book.
