# The agent layer

Deterministic core, agent shell. An agent may **read and research**; it may not **trade**.

## What an agent can run

```bash
python -m agent.tools list                          # the catalog
python -m agent.tools run --name ledger             # a read
python -m agent.tools run --name book --arg coin=BTC
python -m agent.tools run --name e1 status           # research, writes research/e1_status.json
python -m agent.brief                               # deterministic daily briefing, no LLM
python -m agent.loop --dry-run                      # the tools the model would be offered
```

Every call is one JSONL line in `logs/agent.jsonl` (tool, argv, exit, duration, output hash) and is
replayable with `--dry-run`, which resolves the argv without spawning a process.

## What it can never run

`run`, `order`, `trade`, `cb order`, `ui` — the privileged set. The executor refuses them in agent
mode before a process exists, and they are absent from the list offered to any model.

## Boundaries

- **No shell.** argv lists only; `;`, `|`, `&`, `$(` and friends are refused, as are `..`, absolute
  paths and `~`.
- **No secrets in the environment.** `HL_PRIVATE_KEY`, `*_SECRET*` and API keys are stripped from the
  subprocess environment.
- **Writes limited to the repo.** Generated files land in `research/`, `logs/` or `dashboard.html`.
- **One call at a time** via `logs/agent.lock`.
- **The loop is off by default.** It needs `DEEPSEEK_API_KEY` and offers only catalog tools; a model
  asking for `trade` is stopped with an error, not obeyed.

## Why this and not an LLM trader

The evidence rules in this repo only work because decisions are reproducible. The agent layer exists
to operate that machinery — run the checks, read the results, draft the briefing — not to replace it.
