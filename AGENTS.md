# AGENTS.md — Espero Trading Harness

This repo is an evidence-first research and paper-trading harness. The product is
evidence, not a trading bot. Never describe an unvalidated result as an edge.

## Read first

- README.md
- NOTES.md
- PLUMBING.md
- research/MEASUREMENT_SCORECARD.md
- research/AUDIT_BY_NUMBER.md
- strategy_ledger.csv
- agent/README.md before touching agent/

## Hard boundaries

- Never read, print, copy, or commit `.env`, API keys, private keys, account files,
  or live journals (`*.db`, `*.db-wal`, `*.db-shm`).
- `reference/` is read-only prior art. Do not edit it.
- Do not edit `MANIFEST.sha256`, sealed data, `data_raw/`, `books/`, or
  `recordings/`.
- Do not inspect or use any holdout/sealed dataset for selection or validation.
- Never add or invoke live/mainnet order, signing, `run`, `order`, `trade`, or any
  privileged agent tool. Paper and testnet only; this repo has no mainnet path.
- `research/` is the evidence record. Do not edit a result, pre-registration, or
  audit to fit a change; only update it with explicit instruction and traceable
  evidence.
- Do not invent numbers, dates, citations, or strategy performance. Every claim
  must trace to a document, ledger row, or test.
- Do not change a ledger row or gate to make a change pass. If evidence is
  missing, stop and report it.
- Do not commit generated dashboards, logs, `.venv`, `__pycache__`, local DBs, or
  downloaded data.

## Canonical checks

- Install: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
- Tests: `python -m unittest discover -s tests -t .`
- Full gate: `bash scripts/check.sh`
  (tests + audit-citation check + ledger validation)
- CI uses Python 3.12. Do not rewrite code for 3.9 if the local Python is older;
  report the environment mismatch.
- A PR is not ready unless `bash scripts/check.sh` passes.

## Change shape

- Keep one PR to one small, reviewable change in one module or document set.
- Behavior changes need a test in `tests/`.
- Dashboard/UI changes need before/after evidence.
- Docs changes must cite their source; do not rewrite history or results.
- Do not add dependencies or do broad refactors unless the ticket explicitly asks.
- Do not start, stop, or restart the paper loop, E1 recorder, sync, or health jobs.
  Do not run `python -m espero2.cli run` or `--allow-plumbing`.
- Do not fetch or refresh market data; use existing fixtures and committed data.
  Use tests and fixtures, not live state.

## Stop and ask

- If the request is a strategy, product, or architecture decision, stop. Do not
  choose between A/B/C in NOTES.md.
- If the request conflicts with an evidence rule, say so; do not work around it.
- If a test fails for an unrelated reason, report it; never delete or skip it.
- If required data, credentials, or network access is unavailable, report the
  gap instead of fabricating data.

## PR

- Branch `agent/<name>`; describe the change, checks run, and limitations.
- Do not enable auto-merge or merge; a human reviews.
- Link the source request; do not expose private Feishu content.
