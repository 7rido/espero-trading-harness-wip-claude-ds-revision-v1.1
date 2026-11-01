# Result — maker-execution pilot (one day)

**Pilot, descriptive only.** One venue-day cannot support inference; no BH test was run.

Registration: `research/PREREGISTRATION_maker.md` · code: `research/maker_study.py` · data:
`maker_study.json`. Tardis Binance UM `SOLUSDT`, 2026-10-01.

```
minutes          1,434
fills            1,798
fill rate        62.7%
median capture   0.42 bps   (half-spread at the fill)
markout +1 min  +0.47 bps   (positive = no adverse selection on average)
markout +5 min  +0.30 bps
net before fees +0.90 bps (1m) / +0.72 bps (5m)
adverse share    46.7%      (fills that were underwater one minute later)
```

By spread quartile: capture is flat (~0.42 bps), markout at 5 min swings from **+1.16** (tightest
spreads) to **−0.32** (Q3).

## What it says

1. **The mechanics work**: resting at the touch fills 62.7% of the time within a minute and captures
   about the half-spread.
2. **No adverse selection on this day** — markout is positive, which is unusual and likely a benign,
   trending session. A trending day flatters any passive fill.
3. **Fees decide it**: at a 2 bps maker fee (regular tier), the +0.9 bps gross becomes **−1.1 bps net**.
   At zero or negative fees (VIP/rebates) it is positive on this sample. The fee tier is the whole
   question.
4. **Queue position is assumed at the back**; real fills would be worse when the book is stacked.

## Verdict

Not a path yet. The pilot says the plumbing is worth testing properly — **10+ days, the actual fee tier,
queue-aware fills, and a registered net-P&L statistic** — before any claim. One day of positive markout
is exactly the kind of result this project has learned not to trust.
