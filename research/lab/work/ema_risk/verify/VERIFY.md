# Verification of track `ema_risk` (independent replication and attack)

Design panel only (`harness.load('design')`, 7,519 rows, start=744). Scripts and raw output are in this folder:
`v2_all.py/.log/.json` (replication, costs, fragility, neighbours, fresh windows), `v3_placebo.py/.log/.json`
(placebos, market attribution, mirrored market), `v4_stopmodel.py/.log/.json` (stop-fill assumption).
About 330 full-length backtests plus the fresh-window and look-ahead reruns. No shared file was modified.

## Verdicts

| candidate | verdict | one-line reason |
|---|---|---|
| candidate_1 (long+short, 6 x ATR trail, 1% risk sizing) | **survives, with a haircut** | Replicates exactly, causal, beats every placebo, works on the mirrored (bull) market, all neighbours positive after stress. But the centre is a local peak (expect about half), and the last third is negative after stress in 15 of 16 neighbours. |
| candidate_2 (same rule, full-size slots) | **weak** | Replicates and is causal, but one third carries everything (+122% of +169%), long leg loses, 28% drawdown, 10-13% of fresh 11-day windows lose 10% or more, signal-parameter neighbours fall to a median +12% after stress. |
| candidate_3 (short leg only, 1% risk sizing) | **weak** | Replicates and is causal and is steady on this data, but about two thirds of its profit is market direction: it loses on the mirrored market (-6%, -16% after stress). No regime filter was supplied to test it behind. |

The track's own verdict ("weak, market-dependent edge") is fair for candidates 2 and 3. For candidate 1 it is slightly
too pessimistic about market dependence (the rule is symmetric and made +82% on the inverted market) and too optimistic
about the level (the reported centre is the best point of its neighbourhood).

## 1. Replication

All three files import and run. `evalkit.report(..., check=True, cuts=40)`:

| | total | max DD | 11d mean | 11d median | >=+10% | <=-10% | thirds | stress total | stress 11d | trades | long P&L | short P&L | causal (40 cuts) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| candidate_1 | +100.9% | 14.9% | +3.11% | +2.49% | 9.9% | 0% | +23.3 / +57.5 / +3.5 | +71.2% | +2.48% | 384 | +32,251 | +66,458 | True |
| candidate_2 | +169.3% | 28.1% | +4.92% | +4.72% | 26.1% | 11.8% | +13.8 / +122.4 / +6.4 | +101.0% | +3.77% | 384 | -14,178 | +176,545 | True |
| candidate_3 | +32.2% | 12.9% | +1.27% | +1.31% | 1.1% | 0% | +4.7 / +15.4 / +9.3 | +18.1% | +0.83% | 258 | 0 | +31,817 | True |

Every claimed number matches to the reported precision (Sharpe / Sortino / Calmar of candidate_1: 2.65 / 5.60 / 9.80).
A rebuild from the stated parameters gives an identical equity curve to each file. Stress thirds also match:
c1 +16.4 / +50.1 / -2.0, c2 +2.5 / +102.2 / -3.0, c3 +0.9 / +11.1 / +5.3. Stress sixths positive: c1 4 of 6, c2 4 of 6, c3 5 of 6.

One thing does not replicate: the task brief says the folder contains `REPORT.md`. It does not (`gen_report.py` is
there, no output). The numbers were checked against the claim text and the `s*.json` logs instead.

## 2. Code review (look-ahead, fill model, bugs)

- Signals: `ind.ema`, `ind.atr` (causal), state at row t, orders fill at the open of t+1. Trailing stop uses
  `max(p.hi, C[t]) - 6*ATR[t]`, where `p.hi` is the high through bar t; it applies during t+1. No t+1 index, no centred
  window, nothing fitted, no threshold or label from the whole sample. `make(panel)` builds everything from its argument.
- Fill model: 0 limit orders out of 439 (c1, c2) and 302 (c3). Nothing depends on the maker fee or the limit-fill rule.
  No take-profits. No entry without a stop. Stops are 6 x ATR (about 8%) from price, so no zero-distance brackets.
- Risk sizing: `usd = min(slot, 1% * equity / stop distance)`. If 6 x ATR ever exceeded the price the long stop would be
  negative and the order would go out full size with no stop; it never happened here (0 cases) but the live bot should guard it.
- No cooldown after a stop-out (only after a cross exit). Harmless here because re-entry needs a cross at most 3 bars old.
- No bugs found that change a result.

## 3. Costs

- Stress (`evalkit.STRESS`): table above. All three stay positive in total.
- Taker-only: the candidates already use market orders and stops only, so taker-only equals the default result
  (c1 +100.9%, c2 +169.3%, c3 +32.2%).
- Stop-fill assumption (my addition): 333 of 384 trades exit on the stop and the stop exits carry all the profit
  (c1: stops +136.8k, cross exits -38.1k). If the bot only acted on hourly closes (close through the trail, market order
  at the next open, no intrabar stop) the results are: c1 +79.3% (stress +59.1%), c2 +116.1% (stress +74.0%),
  c3 +34.3% (stress +23.1%). So the result does not depend on the intrabar stop fill, but the last third of c1 and c2
  turns clearly negative under it (c1 -7.8%, stress -11.7%; c2 -11.7%, stress -18.0%).

## 4. Fragility

| | c1 | c2 | c3 |
|---|---|---|---|
| best coin | WLD (+22.0k) | ZEN (+50.2k) | FET (+6.6k) |
| total with that coin's trades zeroed | +76.7% | +112.2% | +25.2% |
| total with that coin dropped from the universe (rerun) | +72.0% (stress +46.2%) | +147.0% (stress +83.6%) | +28.1% (stress +14.4%) |
| without the three best coins (rerun) | +47.6% (stress +25.2%) | +77.0% (stress +31.0%) | +18.8% (stress +5.7%) |
| ...its stress thirds | +15.6 / +16.3 / -6.9 | +2.5 / +79.0 / -28.6 | -1.7 / +7.6 / -0.0 |
| best month | Sep 2025 (+29.1%) | Nov 2025 (+56.3%) | Jan 2026 (+7.3%) |
| total without the best month | +55.6% (stress +35.0%) | +72.2% (stress +31.2%) | +23.3% (stress +11.7%) |
| months positive (of 10; stress) | 7 (7) | 7 (6) | 7 (7) |
| coins profitable | 30 of 50 | 31 of 50 | 28 of 50 |
| share of net profit in the 10 best trades | 97% | 112% | 98% |
| fresh 11-day windows (step 3 d, n=91): mean / median / win / worst | +2.64% / +1.95% / 71% / -10.6% | +4.17% / +4.03% / 68% / -20.7% | +1.40% / +1.51% / 57% / -6.2% |
| same, stress | +2.00% / +1.79% / 65% / -12.0% | +2.99% / +3.55% / 67% / -22.7% | +0.94% / +1.07% / 56% / -7.1% |
| fresh windows at <=-10% (default / stress) | 1% / 2% | 10% / 13% | 0% / 0% |
| fresh 11-day windows with fewer than 8 active days | 26% | 26% | 44% (19% under 6) |

The last two calendar months of the design period (Feb, Mar 2026) are negative for c1 (-2.7%, -3.9%) and c2 (-4.0%, -9.9%).

Neighbours, one parameter at a time, about +-25% (fast 36/60, slow 150/250, stop 4.5/7.5 x ATR, ATR length 18/30,
fresh 2/4, cooldown 4/8, slots 3/5, risk 0.75%/1.25%):

| | c1 (16) | c2 (14) | c3 (16) |
|---|---|---|---|
| 11-day mean keeps its sign, default / stress | 100% / 100% | 100% / 100% | 100% / 100% |
| total > 0 after stress | 16 of 16 | 13 of 14 | 16 of 16 |
| at least 2 of 3 thirds positive after stress | 81% | 57% | 94% |
| last third positive after stress | 1 of 16 | 4 of 14 | 15 of 16 |
| all neighbours: total median (min to max) | +64% (+15% to +127%) | +116% (+17% to +176%) | +31% (+22% to +42%) |
| ...after stress | +40% (+3% to +87%) | +60% (-7% to +106%) | +18% (+4% to +24%) |
| signal-parameter neighbours only (fast, slow, stop, ATR length): total median | +46% | +61% | +28% |
| ...after stress | +17% | +12% | +15% |
| ...11-day mean, default / stress | +1.8% / +0.9% | +2.9% / +1.5% | +1.1% / +0.7% |

Correction to the track's plateau claim for c1 and c2: the sign is stable, the level is not. The centre is the best
point in every signal dimension. Moving the stop from 6 to 7.5 x ATR takes c1 from +101% to +15% (stress +3%) and c2
to +17% (stress -7%); 4.5 x ATR gives c1 +49% (stress +9%). Changing only the ATR length from 24 to 18 or 30 halves
c1 (+41%, +52%). A setting this sensitive to the ATR length is partly a lucky path through the slot queue. The honest
expectation for c1 is the neighbour median, roughly half the headline. c3 is flat across its neighbours (+22% to +42%):
it really is a plateau, just a low one.

Start-offset path dependence: starting the run at eight different bars between 744 and 1500 changes the return from
bar 1500 on by less than 2 points for all three. Not an issue.

## 5. Placebos and market dependence

None of the candidates contains a regime filter, so there is no label to shift. Candidate 3 is described as "for use
behind a market-is-bad filter" but no filter is supplied or tested; that combination is unverified. I ran signal
placebos instead (prices, ATR, stops, sizing and costs real; only the EMA signal arrays changed):

| | real | time-shift placebo, 16 shifts 400..6400 bars: mean (min to max) | shift = 1,000 bars exactly | coin-swap placebo, 16 permutations (keeps market-wide timing): mean (min to max) | placebos >= real |
|---|---|---|---|---|---|
| c1 | +100.9% | -18.7% (-50% to +6%) | -14.8% | +6.4% (-15% to +46%) | 0 of 32 |
| c2 | +169.3% | -34.7% (-80% to -2%) | -15.1% | -3.3% (-34% to +68%) | 0 of 32 |
| c3 | +32.2% | -1.0% (-19% to +26%) | +3.2% | +21.9% (+9% to +40%) | 2 of 32 |

Market attribution (equal-weight index fell 46.7% over the test span; thirds +15% / -28% / -35%):

| | average net / gross exposure | P&L of the same dollars, side and hours in the index | own P&L | on the mirrored market (prices inverted, +162% average coin): total (stress) and stress thirds |
|---|---|---|---|---|
| c1 | -0.03 / 0.33 | long +4.7k, short +42.1k | long +32.3k, short +66.5k | +82.1% (+54.5%); +6 / +40 / +4 |
| c2 | -0.12 / 0.58 | long -26.6k, short +82.6k | long -14.2k, short +176.5k | +111.4% (+57.9%); -3 / +53 / +7 |
| c3 | -0.29 / 0.29 | short +20.4k | short +31.8k | -5.6% (-15.7%); +4 / 0 / -19 |

Reading: c1 and c2 are not a disguised short. Their net exposure is near zero, random timing loses money, and they stay
profitable when the market is inverted. Their timing of the whole market explains about half the profit (index
attribution +47k of +99k for c1) and coin selection the rest. c3 is mostly market direction: using another coin's signal
gives two thirds of its return (+22% against +32%), a short of the index in the same hours gives +20k of its +32k, and
it loses on the inverted market. The long-only twin of c3 on the real data makes +28% with a 24% drawdown and -13% in
the last third, which is what c3 should be expected to do in the opposite market.

Caveat on the placebos: they test timing for the chosen parameters. They do not remove the selection bias from having
picked those parameters on this same data; the neighbour table does that.

## Corrected numbers to carry forward

| | c1 | c2 | c3 |
|---|---|---|---|
| design total (as filed) | +100.9% | +169.3% | +32.2% |
| stress total | +71.2% | +101.0% | +18.1% |
| taker-only total | +100.9% | +169.3% | +32.2% |
| fresh-start 11-day mean (default / stress) | +2.64% / +2.00% | +4.17% / +2.99% | +1.40% / +0.94% |
| realistic expectation (signal-neighbour median 11-day mean, default / stress) | +1.8% / +0.9% | +2.9% / +1.5% | +1.1% / +0.7% |
| without best coin (conservative of the two methods) | +72.0% | +112.2% | +25.2% |
| without best month | +55.6% | +72.2% | +23.3% |
| most recent third after stress | -2.0% | -3.0% | +5.3% |

## What the integrator should know

1. Candidate 1 is the only one worth carrying forward as a stand-alone rule, at about half its headline, and with the
   knowledge that in the most recent third of the design data it made nothing after costs in almost every nearby setting.
2. Candidate 2 is candidate 1 with more size, not a different edge. Its extra return comes with a 28% drawdown and a
   one-in-ten chance of losing 10% or more in an 11-day window; that is the wrong trade for a Sortino/Calmar ranking.
3. Candidate 3 must not run without a market-direction filter, and that filter has not been built or tested here.
4. Activity: about a quarter of fresh 11-day windows for c1/c2 (44% for c3) have fills on fewer than 8 calendar days.
   If the competition's active-day rule matters, this rule alone may not satisfy it.
5. Nothing here was tested outside the design period. The selection and holdout panels were not loaded.
