# shorts_direction: independent verification

Design panel only (`harness.load('design')`, rows 744+), default costs unless stated. Scripts and logs are in this folder
(`v1_replicate`, `v2_fragility`, `v3_neighbours`, `v4_placebo`, `v5_extra`; each has a `.py`, `.log` and `.json`).

## Verdict

| candidate | status | one-line reason |
|---|---|---|
| 1: gated breakout longs, no shorts | **survives** | Every reported number replicates, no look-ahead, positive after stress costs in 2 of 3 thirds, 14 of 14 neighbours positive, beats 27 of 29 placebo gates on return and 29 of 29 on drawdown. Uneven: two coins are 71% of profit and the median 11-day window is about zero. |
| 2: candidate 1 at 67% size plus a standing BTC short | **weak** | Replicates and is causal. The hedge's whole gain is BTC's 32% fall: with that average removed the hedged book is no better than the same long book without the hedge (Sortino 4.10 against 4.27). |
| 3: gated breakout longs plus EMA-cross shorts in bad markets | **weak** | Replicates and is causal. The short leg is not an edge: $24k at default costs, $4k at stress costs, negative with one short slot, and timing the shorts with the "bad market" label did worse than 10 of 14 placebo labels. After stress costs the whole book is no better than candidate 1 and has a larger drawdown. |

The track's overall reading holds: do not switch to shorts on this signal; the signal is useful only for deciding whether to
open new breakout longs.

## 1. Replication

`evalkit.report(make, P, check=True)` with 40 cuts for each file. All three import, run and match the claims to the last digit.

| | total | max drawdown | 11-day mean / median | thirds | stress total | stress thirds | trades | active days | look-ahead check |
|---|---|---|---|---|---|---|---|---|---|
| benchmark breakout | +40.3% | 43.4% | +2.11% / -0.61% | +12% / +61% / -23% | +4.2% | +1% / +44% / -28% | 449 | 80% | not run |
| candidate 1 | +106.9% | 18.8% | +3.57% / +0.31% | +23% / +66% / +1% | +73.3% | +12% / +57% / -2% | 256 | 45% | pass (40 cuts) |
| candidate 2 | +84.0% | 12.8% | +2.85% / +1.76% | +14% / +47% / +9% | +62.9% | +8% / +43% / +6% | 259 | 46% | pass (40 cuts) |
| candidate 3 | +130.1% | 21.7% | +4.00% / +2.38% | +20% / +80% / +6% | +75.1% | +8% / +63% / -1% | 381 | 75% | pass (40 cuts) |

No corrections to the reported figures. My own re-implementation of the ungated rule through the candidate's class gives the
benchmark exactly (+40.3%), so the gate is the only difference between candidate 1 and the benchmark.

## 2. Code review

- **Look-ahead: none found.** The gate is `BTC close > EMA480` at row t; entries use `ret(C, 24)[t]`, `rmax(C, 72)[t]` and
  `p.hi` (updated by the harness before `on_bar`); orders fill at the open of t+1. The EMA-cross part uses row-t EMAs and ATR.
  Nothing is fitted and nothing is computed outside `make`.
- **Fill model: no abuse possible.** All three use market orders only (limit fill rate is undefined, zero limits placed), so
  there is no maker fee, no limit fill rule and no bracket to exploit. Taker-only execution is therefore identical to the
  reported numbers. Candidate 3's short stops are bot-side market stops filled at `max(stop, open)` plus spread and overshoot.
- **Bugs: none that change results.** Slot counting in candidate 3 is correct; candidate 2 never buys BTC and the hedge is
  rebalanced 3 times. No rejected orders, at most 4 orders in an hour.
- One thing to know about candidate 3: stop exits on shorts made +$72k (97 trades) and cover-on-cross exits lost about $48k
  (33 trades). The short leg's profit depends on the trailing stop fill, which is the least certain part of the cost model.

## 3. Costs

| | default | stress (`evalkit.STRESS`) | harsher (taker 20 bp, slip 20 bp, stop overshoot 30 bp, 3x spread) |
|---|---|---|---|
| benchmark | +40.3% | +4.2% | -33.0% |
| candidate 1 | +106.9% | +73.3% | +34.5% |
| candidate 2 | +84.0% | +62.9% | +39.9% |
| candidate 3 | +130.1% | +75.1% | +15.9% |
| candidate 3 short leg only | +$23.9k | +$4.0k | -$16.7k |

Taker-only: same as default for all three (they already use only market orders).

## 4. Fragility

| | candidate 1 | candidate 2 | candidate 3 |
|---|---|---|---|
| best coin | STO +$38.9k | TUT +$22.8k (BTC hedge +$21.3k) | TUT +$39.1k |
| total without best coin (dropped from universe) | +75.4% (stress +49.7%) | +51.4% (stress +36.2%) | +69.2% (stress +29.8%) |
| total without STO and TUT | +29.8% (stress +11.8%; stress thirds +9% / +22% / -16%) | +37.0% (stress +22.5%; +6% / +20% / -4%) | +41.6% (stress +11.7%; +6% / +24% / -15%) |
| best month | Oct 2025 +40.0% | Oct 2025 +26.9% | Oct 2025 +46.5% |
| total without best month | +47.8% (stress +27.9%) | +45.0% (stress +32.3%) | +57.1% (stress +25.0%) |
| months positive | 6 of 10 | 8 of 10 | 7 of 10 |
| top 5 trades as share of net profit | 90% | 75% | 72% |
| neighbours (each parameter about +-25%) with same sign of 11-day mean | 14 of 14 (stress 14 of 14) | 18 of 18 (18 of 18) | 28 of 28 (28 of 28) |
| neighbour range, total | +54% to +163% | +51% to +113% | +68% to +208% |
| neighbour range, stress total | +28% to +128% | +34% to +97% | +32% to +145% |
| fresh-start 11-day windows (91, every 3 days): mean / median / win | +3.40% / +0.27% / 52% | +2.75% / +1.75% / 73% | +3.95% / +3.11% / 60% |
| fresh windows at stress costs: mean / median | +2.66% / 0.00% | +2.22% / +1.33% | +2.79% / +2.11% |
| fresh windows at or below -10% / worst | 3% / -16.8% | 1% / -11.2% | 4% / -19.4% |
| 14-day windows with 8 or more active days | 41% (minimum 0 days) | 41% (minimum 0) | 86% (minimum 5) |

Neighbours tested: gate EMA 360/600, slots 3/5, move 6%/10%, trail 4.5%/7.5%, lock 9/15, return look-back 18/30 h, high window
54/90 h; plus hedge 25%/41% and band 22.5%/37.5% for candidate 2; plus short slots 1/3, fast 18/30, slow 150/250, stop
4.5/7.5 ATR, ATR 18/30, freshness 2/4, cool-down 4/8 for candidate 3. Benchmark fresh windows for reference: +2.31% / -0.17%, 13% at or below -10%.

Gate against no gate on 13 breakout settings (the filed one and 12 neighbours): the gated version had the higher total, the
lower drawdown and the higher stress total in 13 of 13. The ungated rule was positive after stress costs in 9 of 13.

## 5. Placebo for the direction label

Placebo = the same label circularly shifted, so it has the same share of "good" hours (about 40%) and the same persistence.

**Candidate 1 (gate on longs).** 29 shifts (every 250 bars):

| | real gate | placebo mean | placebo median | placebo best | real beats |
|---|---|---|---|---|---|
| total return | +106.9% | +24.8% | +18.1% | +172.3% | 27 of 29 |
| max drawdown | 18.8% | 32.4% | | 20.0% (lowest) | 29 of 29 |
| 11-day mean | +3.57% | | | | 28 of 29 |

Without STO and TUT (14 shifts): real +29.8% against a placebo mean of +8.1%; real beats 12 of 14 on total and 13 of 14 on
drawdown. So the gate carries information beyond "be in cash 60% of the time", but the test has few independent market
episodes (one long decline) and two placebo labels matched or beat it on return.

**Candidate 2.** Shifting the gate (7 shifts): real beats 7 of 7 on total, drawdown and Sortino (same gate as candidate 1).
The hedge is a separate question:

| daily-return ratios | total | Sortino | Sharpe | max drawdown |
|---|---|---|---|---|
| hedged (as filed) | +83.1% | 4.84 | 2.42 | 11.1% |
| same 67% long book, no hedge | +67.1% | 4.27 | 2.05 | 11.5% |
| hedged, hedge's average daily gain removed | +67.3% | 4.10 | 2.08 | 11.2% |

The hedge's contribution has a -0.99 correlation with BTC's daily return and added -$2.1k / +$5.2k / +$13.2k in the three
thirds, while BTC returned +5.5% / -16.9% / -23.0%. It paid because BTC fell. It moves the book's BTC beta from +0.19 to -0.13,
so in a BTC rally it costs about a third of BTC's rise.

**Candidate 3 (label used to time shorts).** Shifting only the short gate and leaving the long gate real (14 shifts):

| | real "bad market" label | placebo mean | real beats |
|---|---|---|---|
| short-leg profit, default costs | +$23.9k | +$35.9k | 4 of 14 |
| short-leg profit, stress costs | +$4.0k | +$18.2k | 3 of 14 |
| book total, stress costs | +75.1% | +82.9% | 5 of 14 |

Shorting only in good markets made +$33.7k (stress +$22.3k) and shorting always made +$64.5k (stress +$35.3k). The direction
label does not help time shorts; it does slightly worse than a random label of the same shape. Short profit by third:
-$2.2k / +$27.0k / -$0.8k at default costs and -$4.3k / +$15.3k / -$6.9k at stress costs: one third out of three. With one
short slot instead of two the short leg lost $5.0k (stress -$13.4k).

## What this means for the candidates

1. **Candidate 1 survives as a risk switch on the breakout rule**, not as a better stock-picker. Expect a mean of about +3%
   per 11 days with a median near zero: about half of 11-day windows make nothing, and the profit comes from a few large
   trades (top 5 are 90% of it). It leaves the account idle for long stretches: in 59% of 14-day windows it traded on fewer
   than 8 days, and at least one 14-day window had no trades at all. That conflicts with the competition's activity rule
   and has to be solved outside this candidate.
2. **Candidate 2 is candidate 1 at two-thirds size plus a bet that BTC falls.** Its better ratios on the design data are
   that bet paying off. Use it only if the team wants lower BTC exposure on purpose.
3. **Candidate 3's short leg is an activity device with no demonstrated edge.** It raises active days from 45% to 75%, at
   the price of a larger drawdown under stress costs (27.1% against 20.6%) and no extra return after costs (+75.1% against
   +73.3%). The rule "short when the market looks bad" is refuted by the placebo test.

All of this is the design period only, a falling market (basket +15% / -28% / -35% by third). None of it has been checked on
the selection or holdout rows.
