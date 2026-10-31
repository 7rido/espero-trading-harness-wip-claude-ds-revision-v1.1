# Espero Trading Harness WIP-CLAUDE/DS Revision v1.1

A research and paper-trading harness whose product is **evidence, not a bot**. Every claim here has a
date, a document and a number; every rule that could make money is gated by a ledger row that says what
was tested and on what bar.

This is a **new project built from a read-only audit of the earlier `espero` repository**, not a fork.
That repository's own research documents are in [`reference/`](reference) (87 files, verbatim) and its
46 numbered tests are audited in [`research/AUDIT_BY_NUMBER.md`](research/AUDIT_BY_NUMBER.md) — what
each claimed, what it decided, why it failed, and what would fix it.

## What the evidence currently says

| question | answer | document |
|---|---|---|
| Which of the original's 46 tests hold? | **one** (#26), with three asterisks | [`AUDIT_BY_NUMBER.md`](research/AUDIT_BY_NUMBER.md) |
| Does #21 (liquidation spikes) replicate? | **no** — day-mean t 0.85; trade-weighted −19.7 bps | [`RESULTS …liqspike`](research/RESULTS_2026-10-30-liqspike.md) |
| Does #26 (forced-liquidation bounce) replicate? | **yes** — D −20.3 bps (t −5.13) on 26 coins, 427 days | [`RESULTS …liq26`](research/RESULTS_2026-10-30-liq26-replication.md) |
| Is #26's tag executable? | the within-day tag is not; the **prior-day** version keeps +32.0 bps at 4 h (t 4.01) | same |
| Is the SMA strategy worth running? | **no** — it tracked an equal-weight hold; retired | `strategy_ledger.csv` (`P1`) |

The only forward test this project owns is **E1** — the executable forced-liquidation bounce, window
**2026-10-31 → 2027-04-30**, four pre-registered criteria, net of measured cost and realised funding.
Its rules were committed before the first day of the window existed:
[`PREREGISTRATION_2026-10-30-liq-executable.md`](research/PREREGISTRATION_2026-10-30-liq-executable.md).
It is recorded daily and **not read** until the window closes: `research/e1_recorder.py --score`
refuses before 2027-04-30.

## The rules, enforced in code

1. **A strategy cannot run without a ledger row** (`strategy_ledger.csv`); `holds` requires a valid
   statistic *and* a cost bar. Plumbing work needs a dated `PLUMBING.md` window.
2. **Fills are charged**: taker at the far touch plus slippage, the venue's measured fee, and funding
   over the hold. Measured all-in round trip on the recorded books: **9.09 bps**.
3. **Signing is testnet-only** and needs independent opt-ins. `EXECUTION` gates the Coinbase side, and
   there is no authenticated order path at all.

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

python -m unittest discover -s tests -t .    # 94 tests
bash scripts/check.sh                        # tests + audit citations + ledger validation
python scripts/health_check.py               # are the unattended jobs alive?
python -m espero2.cli ledger                 # what may run, and why
```

## Two front doors

```bash
python -m espero2.cli ui                     # terminal home screen (rich + questionary)
python -m espero2.cli dashboard --open       # self-contained HTML page
```

```
╭──────────────────────────────────────────────────────────────────────────────────────╮
│ ▗▄▄▄▄▄▄▄▐▛██▜▌   espero2  paper accounts  $3,000.00                                  │
│ ▝▜██████▜████▛▘  heartbeat 6s ago  ·  ok  ·  every 60s  ·  journal paper.db          │
│   ▘▘ ▝▝  ▘▘ ▝▝   books  BTC 62 marks  ·  ETH 8 marks  ·  SOL 8 marks                 │
╰──────────────────────────────────────────────────────────────────────────────────────╯
  account       equity      day       P&L    curve                               holds
  BTC        $1,000.00    +0.00    +0.00%    ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁    flat
```

## What runs unattended

| job | when | what it does |
|---|---|---|
| `io.espero2.sync` | 07:45 daily | one-way copy of the new data from the maintainer's folder |
| `io.espero2.health` | 08:30 daily | fails loudly if the copy stalled or the E1 feed stopped |
| GitHub Actions | every push | tests, audit citation check, ledger validation |

## Layout

```
espero2/        the harness: ledger gate, paper engine, HL testnet client, Coinbase adapter
research/       the audit, both replications, E1's registration, the recorder and its run JSONs
reference/      the original repository's research documents, verbatim (87 files)
tests/          94 tests, including the ones that assert a test is *refused*
scripts/        health check, local CI, the 07:45 copy, launchd installers
```

## What is not claimed

- **No mainnet order path exists.** The Hyperliquid client has a testnet host constant; the Coinbase
  client is read-only by design.
- **No strategy is running.** The paper loop is stopped; restarting it needs a new dated plumbing window
  and a ledger row that earns it.
- **In-sample numbers are not results.** The +32 bps at 4 h is a 2023–2024 reading; E1 exists precisely
  because that is not the same thing as evidence about the future.
- **Funding in the replication is approximate**; E1 charges it exactly.

## Licence

MIT. Original work © 2026 7ucky7; this revision © 2026 7rido. See [`LICENSE`](LICENSE).
