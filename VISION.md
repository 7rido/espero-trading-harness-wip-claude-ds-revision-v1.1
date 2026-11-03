# Vision and taste — the alignment document

This is **my read of your taste**, written down so you can correct it. It is not a spec you asked for; it
is a claim about what you want, which I should be able to defend and you should be able to strike out.
When we disagree, this document loses — but only after we've argued about it.

## The product in one sentence (my read)

A **public, honest trading desk**: one operator surface that shows every market, venue and data source,
sizes and labels risk, records forward tests, and never pretends a void book or an unproven signal is
real — with a path to small real trades only after the evidence clears.

## Your taste, as I read it

1. **Truth is the product.** A void book, a testnet price, or an in-sample number must be labelled as
   such at the point of display. You'd rather see "no edge" than a polished lie.
2. **Visible in action.** If it isn't running and visible on a surface, it doesn't count. "Merged" is
   not "working"; "written" is not "used".
3. **Craft is credibility.** A wrapped table or a missing LONG/SHORT column reads as sloppy thinking.
   The UI is the face of the work, not decoration.
4. **One screen, all markets.** You think in universes — every venue, every source, every coin — not in
   per-coin fragments. The optics panel was your idea before it was mine.
5. **Pragmatic path to trading.** Paper forever is failure; pretending paper is trading is worse. You
   want the smallest honest step toward real money, with the evidence bar enforced.
6. **Fewer, better things.** You push back on tables of failures. One decision, one recommendation, one
   reason beats ten cells.
7. **The agent drives.** You want me to decide what I can decide, surface the real choices with a
   recommendation, and never hand you a blank page to fill in.

## Where I failed to align (specific)

- I presented **$1,428 of fake BTC equity** without checking it — you had to ask "did you even run
  tests?" before I found the bug.
- I shipped dashboard cards while the **running loop kept overwriting them** with the old renderer.
- I answered "PR #6 is merged" when the question was "is it working and visible?" — and its live
  coverage was still 6 UNMAPPED.
- I quoted **"z ≈ 2.7" for a regime cell I had never computed**; the real value was 1.81.
- I asked "what do you mean?" instead of explaining the thing that confused you.
- I let the paper loop trade **testnet prices disconnected from spot** without flagging it loudly enough.

## The decisions I need from you

Each has a recommendation; override any of them and the document updates.

| # | decision | options | my recommendation |
|---|---|---|---|
| 1 | What is this? | research lab · operator product · both | **both, product first**: research feeds one surface |
| 2 | Path to real money | stay paper · small live after carry paper passes · abandon trading | **small live after the carry capture bar passes** (paper to Dec 31, then ≤$500) |
| 3 | Primary surface | dashboard · terminal TUI · agent chat | **dashboard** (TUI for ops, agent for actions) |
| 4 | What counts as "working" | the desk runs and shows honest state · a strategy makes money · a client can use it | **the desk runs and shows honest state**; P&L is a separate, later bar |
| 5 | Risk appetite | 0.5% · 2% · 5% of capital per month | **2% hard stop per month**, any strategy |

## How we stay aligned

- Every major change is checked against this document before it ships.
- When I see a mismatch between what you asked and what you meant, I write it here, not in a chat reply.
- You can strike any line; a struck line is a decision, not an edit.
- If I can't point to a line that justifies a choice, the choice is mine to defend or drop.

## Open taste questions I genuinely don't know

1. Do you want the project to look like a **fund's internal desk** (austere, numbers first) or a
   **product for others** (explained, guided)?
2. Is the **E1 forward test** worth the nine-month wait, or should the desk be built to make money in
   the next quarter (carry, execution) and treat E1 as background science?
3. When a result is marginal, do you want the **honest null** on the surface, or the **best cell** with
   its caveats? (I've been choosing the null; you've pushed for something usable.)
4. How much of your taste is **aesthetics** versus **decision quality**? I've assumed the two are the
   same; maybe they aren't.
