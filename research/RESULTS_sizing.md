# Result — volatility targeting vs fixed sizing on the same signal

**Verdict: on the SMA 20/50 stream, vol targeting made things worse at matched exposure — Sharpe 0.49
vs 0.84, drawdown −11.8 % vs −9.0 %. The setting now live (2 %, $500 cap) also raises gross exposure
5×, which raises both vol and drawdown. Vol targeting is not a free improvement; it depends on the
vol–return relationship of the signal.**

Code: `research/sizing_study.py` · data: `sizing_study.json`.

## Design

- 10 majors, daily bars 2020-01-01 → 2026-03-31, $10,000 capital, 9 bps round-trip cost.
- Same SMA 20/50 signal (retired as a strategy, used only as a return stream) and fills in both books.
- **Fixed**: $100 notional per open position.
- **Vol-target matched**: risk fraction calibrated so average gross exposure equals the fixed book
  ($931 gross).
- **Vol-target live**: 2 % risk, $500 cap — what the paper loop runs now.

## Results

| book | final | CAGR | vol | Sharpe | max DD | avg gross |
|---|---|---|---|---|---|---|
| fixed $100 | $12,998 | **4.3 %** | 5.2 % | **0.84** | **−9.0 %** | $931 |
| vol-target 1.208 % (matched) | $11,427 | 2.2 % | 4.5 % | 0.49 | −11.8 % | $931 |
| vol-target 2 % (live) | $12,362 | 3.5 % | 7.5 % | 0.49 | −18.9 % | $1,646 |

## What it means

1. **At equal average exposure, vol targeting lost Sharpe and had a bigger drawdown.** It sized up in
   calm, choppy periods and down during vol expansion — the opposite of what a trend signal needs.
2. **The live setting is not risk control; it is 1.8× the fixed exposure.** Switching from $100 fixed to
   2 %/$500 changed the risk budget, not just the sizing rule.
3. The result is signal-specific: a mean-reversion or carry stream, or a different vol–return relation,
   could give the opposite answer. This project's earlier claim that vol targeting "improves risk
   regardless" was too strong; this study is the correction.

## Limits

- One signal, ten coins, one cost assumption, no funding, no leverage/margin modeling.
- Average-exposure matching, not risk matching; Sharpe is the comparison that is scale-free.
- Daily close execution; no intraday path dependence.

## Practical consequence

For the void SMA plumbing loop the change is cosmetic. **For anything real, sizing must be tested with
the same discipline as the signal** — and this first test says fixed is better here, with the live
setting materially riskier than it looked.
