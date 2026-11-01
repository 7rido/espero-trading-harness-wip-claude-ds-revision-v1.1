# Espero Trading Harness — WIP/CLAUDE/DS revision v1.1

A research and paper-trading harness whose product is **evidence, not a bot**. Every claim has a date,
a document and a number; every rule that could make money is gated by a ledger row that says what was
tested and on what bar. **Public repo:**
[`7rido/espero-trading-harness-wip-claude-ds-revision-v1.1`](https://github.com/7rido/espero-trading-harness-wip-claude-ds-revision-v1.1).

Built from a read-only audit of the earlier `espero` repository, not forked from it. The original's 87
research documents are in [`reference/`](reference), and its 46 numbered tests are audited in
[`research/AUDIT_BY_NUMBER.md`](research/AUDIT_BY_NUMBER.md).

## Current state (2026-11-01)

| | |
|---|---|
| tests | **171** green; `scripts/check.sh` also validates audit citations and the ledger |
| paper loop | **running** (`io.espero2.paper`, 60 s): BTC/ETH/SOL, vol-target 2 %, 25 %/yr funding gate, $500 cap |
| books | **void** — `sma` runs as `plumbing` under the window to 2026-12-31; never read as evidence |
| E1 | recording; **11 seed events, 0 forced trades**; window 2026-10-31 → 2027-04-30, 70 % power |
| dashboard | books, **operator optics** (10 markets, connections, data freshness), **forecasts** (capped at WATCH), **BTC tape** |
| agent layer | catalog + sandboxed executor + brief; privileged verbs (`run`, `order`, `trade`) refused |
| data | 16 substrate tables — see [`DATA_INVENTORY.md`](research/DATA_INVENTORY.md) |
| repo | clean, pushed |

## What the evidence says

| question | answer | document |
|---|---|---|
| Which of the original's 46 tests hold? | **one** (#26), with three asterisks | [`AUDIT_BY_NUMBER.md`](research/AUDIT_BY_NUMBER.md) |
| Does #26 (forced-liquidation bounce) replicate? | **yes** — D −20.3 bps (t −5.13), 26 coins, 427 days | [`RESULTS …liq26`](research/RESULTS_2026-10-30-liq26-replication.md) |
| Is the executable variant real? | **+32.0 bps at 4 h (t 4.01)**; survives 121-cell selection (p 6.1e-5) | same |
| Does anything else survive selection? | **no** — carry 0.19, regimes 0.56, XS 0.96 family-wise | [`RESULTS_hardening.md`](research/RESULTS_hardening.md) |
| Tape edges (sweeps, absorption, blocks, divergence)? | **no** — 8 cells, 0 BH, holdout never opened | [`RESULTS_tape_edges_design.md`](research/RESULTS_tape_edges_design.md) |
| Tape OFI at seconds? | **yes but sub-cost** — +0.22 bps at 30 s vs 9 bps cost | [`RESULTS_tape_study_2.md`](research/RESULTS_tape_study_2.md) |
| Tape as volatility instrument? | **yes** — intensity→RV 1.74×, VPIN→variance (BH) | [`RESULTS_vpin.md`](research/RESULTS_vpin.md) |
| Does vol-target sizing help? | **no on this signal** — Sharpe 0.49 vs 0.84 fixed at matched exposure | [`RESULTS_sizing.md`](research/RESULTS_sizing.md) |
| SMA strategy? | retired — tracked an equal-weight hold | `strategy_ledger.csv` (`P1`) |

**The only directional edge is the forced-liquidation bounce, and it is still a forward test.** E1's
rules were committed before the first window day existed:
[`PREREGISTRATION_2026-10-30-liq-executable.md`](research/PREREGISTRATION_2026-10-30-liq-executable.md).
It is recorded daily and not read until 2027-04-30.

## The rules, enforced in code

1. **A strategy cannot run without a ledger row** (`strategy_ledger.csv`). `holds` needs a statistic and
   a cost bar; `plumbing` needs a dated `PLUMBING.md` window.
2. **Fills are charged**: taker at the far touch + slippage, venue fee, funding over the hold. Measured
   all-in round trip: **9.09 bps**.
3. **No mainnet order path exists.** Signing is testnet-only and needs independent opt-ins.
4. **Forecasts cannot exceed `WATCH`** while no strategy is in `holds` — enforced by a test, not a convention.

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

python -m unittest discover -s tests -t .     # 171 tests
bash scripts/check.sh                         # tests + audit citations + ledger
python scripts/health_check.py                # unattended jobs alive?
python -m espero2.cli ledger                  # what may run, and why
python -m espero2.cli dashboard --open        # the page
python -m espero2.cli run --coin BTC --once --allow-plumbing   # one paper cycle
```

## What runs unattended

| job | when | what it does |
|---|---|---|
| `io.espero2.paper` | 60 s | paper loop, vol-target sizing, funding gate |
| `io.espero2.optics` | 15 min | `optics → forecast → tape --live` (dashboard data) |
| `io.espero2.sync` | 07:45 | sync → `e1_feed` → `e1_recorder` → daily tape |
| `io.espero2.health` | 08:30 | fails loudly if the copy or the E1 feed stalls |
| GitHub Actions | every push | tests, audit citations, ledger validation |

## Layout

```
espero2/     ledger gate, paper engine, risk, dashboard, venue clients (HL testnet, Coinbase, Alpaca)
agent/       tool catalog, sandboxed executor, briefing, smoke test — no trading tools
research/    audit, replications, E1, tape/VPIN/maker studies, registrations, scorecard, data inventory
tests/       171 tests, including those that assert a test is *refused*
scripts/     CI, health, sync, E1 refresh, launchd installers
reference/   the original repository's research documents, verbatim (87 files)
```

## Evidence map

- [`MEASUREMENT_SCORECARD.md`](research/MEASUREMENT_SCORECARD.md) — every measurement rated for prediction and risk use.
- [`DATA_INVENTORY.md`](research/DATA_INVENTORY.md) — every table, rows, span.
- [`RESULTS_hardening.md`](research/RESULTS_hardening.md) — selection cost, E1 power, maker fills.
- [`PLUMBING.md`](PLUMBING.md) — the window the paper loop runs under.

## What is not claimed

- **No strategy is authorised.** No ledger row is `holds`; the loop runs `sma` as plumbing and its books are void.
- **The testnet venue is not a market.** HL testnet SOL trades ~8 % above spot on a 21 bps spread; fills there are fictional.
- **In-sample numbers are not results.** The +32 bps at 4 h is a 2023–2024 reading; E1 exists because that is not evidence about the future.
- **Risk instruments are not edges.** Volatility, VPIN and maker fills improve sizing and execution; they do not predict direction.
- **Venue matters.** Funding differs up to 4× between HL, OKX and Binance; any carry read must name its venue.

## Licence

MIT. Original work © 2026 7ucky7; this revision © 2026 7rido. See [`LICENSE`](LICENSE).
