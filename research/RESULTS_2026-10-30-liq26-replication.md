# Result — #26 replicated, and the executable variant measured

**Bottom line:** the in-sample result replicates (D −20.3 bps, t −5.13 against the published −23.6,
t −4.06), and the **prior-day tag** — the one a human could actually compute before trading — keeps
about two thirds of it: D −14.4 bps (t −5.36), and buying forced down-breaks earns **+32.0 bps** at 4 h
(t 4.01) before funding.

Code: [liq26_replication.py](liq26_replication.py) · numbers: [liq26_run.json](liq26_run.json).

## What was replicated

#26's rule, unchanged, on **26 COIN-M coins**, 2023-06-26 → 2024-10-14, events 28,039 over 427 days:

- 5-minute breaks closing 01:00–24:00 UTC, one per coin per direction per hour, on Binance USDⓈ-M bars;
- forced share `s` = COIN-M liquidations on the break's side in the hour before ÷ that hour's quote volume;
- within-day terciles of `s` → forced / organic;
- `D(day)` = forced mean − organic mean of the break-direction return.

| statistic | published (#26/#44) | this replication |
|---|---|---|
| D, day-mean | −23.6 bps, t −4.06 | **−20.3 bps, t −5.13** |
| D, trade-weighted | −22.2 bps, t −3.54 | not computed (day-mean only) |
| long leg, 1 h | +19.2 bps, t 3.67 | **+23.6 bps, t 7.11** |
| long leg, 4 h net | +21.9 bps, t 4.38 | **+38.1 bps (net of 9 bps), t 6.44** |
| long leg, 12 h net | +36.5 bps, t 3.57 | +60.8 bps, t 5.55 |
| long leg, 1 d net | +60.4 bps, t 3.63 | +90.4 bps, t 4.77 |

Same conclusion, stronger magnitude — expected, because this runs all 26 COIN-M coins while the
published basis was the eight coins `espero.costs` measures, and my cost model is a flat 9 bps rather
than their markout curve.

## The variant that matters: prior-day tags

Today's events are tagged against **yesterday's** `s` terciles — a threshold that exists before the
trading day starts. No peeking at the day's own distribution.

| | within-day (registered) | **prior-day (executable)** |
|---|---|---|
| D | −20.3 bps (t −5.13) | **−14.4 bps (t −5.36)** |
| long leg, 1 h | +23.6 bps (t 7.11) | **+22.9 bps (t 6.72)** |
| long leg, 4 h | +42.6 gross / +38.1 net (t 6.44) | **+32.0 gross / +27.5 net (t 4.01)** |
| long leg, 12 h | +65.3 / +60.8 (t 5.55) | +48.1 / +43.6 (t 3.45) |
| long leg, 1 d | +94.9 / +90.4 (t 4.77) | +73.0 / +68.5 (t 2.90) |

So the classifier being hindsight **was not what made #26 pass**. The executable version is weaker but
still positive at every horizon, with t between 2.9 and 6.7 on 426–427 days. That is the first
in-sample reading in this project that survives the audit's two complaints at once — executable tag,
trade-weighted, net of cost.

## What it does not do

- **Cost checked from the books** (`cost_check.py`): median quoted spread 0.09 bps on 17,266 ETH-USD
  snapshots, all-in round trip 9.09 bps against the 9 bps used here - the fee is the cost, not the spread.
- **Funding is not charged.** Their model uses Binance settled rates over the hold; mine stops at the
  9 bps round trip. On a 4 h hold funding is small, on 1 day it is not. The 1 d numbers are upper bounds.
- **It is still in-sample**, on the same 2023–2024 window #26 was found in. Nothing here is evidence
  about the future; it is evidence that the *rule can be run*, which is what #45 lacks.
- **Our D is day-mean only.** The published trade-weighted D (−22.2) is not reproduced; the long-leg
  numbers are trade-weighted.

## Consequence for #45

#45 keeps testing the within-day tag. It remains the registered test of the phenomenon, and it should
run to its date unchanged. But its result — either way — will not answer "could this have been
traded?". That question now has an in-sample basis and a written pre-registration:
[PREREGISTRATION_2026-10-30-liq-executable.md](PREREGISTRATION_2026-10-30-liq-executable.md).
