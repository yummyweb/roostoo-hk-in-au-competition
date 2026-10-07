# Verification of track "ema_windows"

Independent rerun on `harness.load('design')` only (start bar 744, 6,775 hours, 50 pairs). Scripts and raw output are in this folder:
`v1_report.py` / `v1.json` (standard report with the 40-cut look-ahead check, coins, months), `v2_fragility.py` / `v2.json`
(neighbours, fresh windows, coin removal, stop-fill attacks), `v3_placebo.py` / `v3.json` (placebo signals, market dependence),
`v4_trades.py` / `v4.json` (trade-level statistics). About 330 backtests in total.

## Verdicts

| candidate | verdict | one-line reason |
|---|---|---|
| candidate_2, short only, 24/200, 6-ATR trail | **survives (conditionally)** | Replicates exactly, causal, positive at stress costs in 3 of 3 thirds, 14 of 14 neighbours keep the sign, beats all 12 placebo shorts. But it loses in 81% of 11-day windows when the market rises, and two of the three stress thirds are only +4% and +5%. |
| candidate_1, both sides, 24/200, 6-ATR trail | **weak** | Replicates and is causal, but one calendar month (Nov 2025, +50%) is the result: without it +6% (stress -20%). Only 43% of neighbours have two positive thirds at stress costs. |
| candidate_3, long only, 24/200, 4-ATR trail | **weak (not usable alone)** | Replicates and is causal, and beats placebo longs by 100+ points, but one coin (TUT) is 99% of the profit, the last third is -21% (stress -31%) in every neighbour, and the fresh-window median is negative. |

The track's own verdict ("weak edge, short-biased, market-direction dependent") is accurate. Its numbers are correct. I found no look-ahead and no bug.

## 1. Replication

All headline numbers reproduce to the last digit (`evalkit.report`, `check=True`, 40 cuts).

| | candidate_1 | candidate_2 | candidate_3 |
|---|---|---|---|
| total / max drawdown | +59.1% / 25.4% | +86.8% / 21.4% | +66.3% / 44.6% |
| 11-day windows mean / median | +2.25% / +1.44% | +3.05% / +2.58% | +2.69% / -0.21% |
| thirds | +12% / +45% / -2% | +12% / +47% / +13% | +48% / +43% / -21% |
| stress total / 11-day mean | +16.8% / +1.03% | +47.6% / +2.12% | +13.0% / +1.15% |
| stress thirds | +1% / +30% / -10% | +4% / +35% / +5% | +32% / +24% / -31% |
| trades, long / short P&L | 430, +$13.6k / +$39.2k | 311, - / +$87.5k | 500, +$62.9k / - |
| look-ahead check (40 cuts) | pass | pass | pass |

## 2. Code reading

The three files are 1-line configurations of the shared `strategies.EmaCross` inside `Portfolio`; nothing is fitted.
- EMAs and ATR come from `ind.py` (recursive EMA seeded with an SMA, trailing SMA of true range), built inside `make(panel)`.
- Entry uses `up/dn/age/gap/atr` at row `t` only; the initial stop is `C[t] +- k * ATR[t]`; the trail uses `p.lo` / `p.hi` (extremes through bar `t`) and `ATR[t]`, and applies from bar `t+1`. No `t+1` index, no centred window, no full-sample statistic.
- No limit orders exist in any candidate (limit fill rate is NaN, 0 limits placed), so there is no maker fee, no limit-fill assumption and no bracket to abuse. **Taker-only execution is identical to the reported run.**
- No rejects, at most 3-4 orders in any hour.
- Not a bug, but worth knowing: stop exits carry all the profit (candidate_2: 225 stop exits +$175k, 86 opposite-cross exits -$88k). The opposite cross is the loss exit; the trailing stop is the profit exit. See the stop-fill attack below.

## 3. Costs and fill model

| total return | candidate_1 | candidate_2 | candidate_3 |
|---|---|---|---|
| default | +59.1% | +86.8% | +66.3% |
| stress (`evalkit.STRESS`) | +16.8% | +47.6% | +13.0% |
| stress, stops overshoot 50 bp instead of 15 | -13.0% | +22.5% (thirds -2% / +26% / -1%) | -20.1% |
| stress, stops overshoot 100 bp | -42.9% | -6.3% | -51.5% |
| stop acts only on hourly closes, exit at next open (no intrabar stop fill), default / stress | +43.4% / +11.5% | +92.6% / +60.0% | +31.0% / -1.0% |

Candidate_2 does not need the intrabar stop fill: with a stop that is only checked on completed candles it is as good or better
(stress thirds -0.5% / +45% / +11%). Candidates 1 and 3 lose about a third to a half of their return without it, and all of it at stress costs for candidate_3.

## 4. Fragility

| | candidate_1 | candidate_2 | candidate_3 |
|---|---|---|---|
| best coin | ZEC +$23.5k | APT +$18.2k | TUT +$62.3k |
| total with that coin's trades zeroed | +29.3% | +69.3% | +0.6% |
| total with that coin dropped from the universe (stress) | +43.1% (+6.9%) | +79.6% (+41.9%) | +10.9% (-23.8%) |
| three best coins dropped from the universe (stress) | +41.7% (+3.4%) | +54.0% (+21.4%) | -17.6% (-42.8%) |
| best calendar month | Nov 2025 +49.6% | Nov 2025 +28.9% | Sep 2025 +27.2% |
| total without that month (stress) | +6.4% (-20.0%) | +44.9% (+17.0%) | +30.7% (-8.1%) |
| calendar months positive | 6 of 10 | 7 of 10 | 7 of 10 |
| 14 neighbours (+-25% one at a time): 11-day mean keeps its sign, default / stress | 100% / 86% | 100% / 100% | 100% / 86% |
| neighbours with a positive stress total | 64% | 100% | 71% |
| neighbours with at least 2 of 3 thirds positive at stress | 43% | 86% | 79% |
| neighbour stress total: median, min to max | +14%, -21% to +137% | +39%, +9% to +71% | +8%, -36% to +24% |
| fresh 11-day windows, step 3 days (91): mean / median / win | +2.68% / +1.70% / 57% | +2.75% / +0.49% / 55% | +2.52% / -1.12% / 47% |
| same at stress costs: mean / median / win | +1.31% / +0.61% / 54% | +1.78% / -0.66% / 49% | +0.99% / -2.40% / 44% |
| trade-level mean return, t (naive / clustered by entry week), default | +0.57%, 1.3 / 1.2 | +0.95%, 2.5 / 1.6 | +0.52%, 1.3 / 1.2 |
| same at stress costs | +0.28%, 0.7 / 0.6 | +0.64%, 1.7 / 1.1 | +0.20%, 0.5 / 0.5 |

Neighbours tested: fast 18 / 30, slow 150 / 250, stop 0.75x / 1.25x, ATR length 18 / 30, fresh 2 / 4, cooldown 4 / 8, slots 3 / 5.

Corrections to the claim:
- Candidate_2's restart-flat median of +2.4% (68 windows, step 4 days) is phase-dependent. At step 3 days (91 windows) the median is +0.5% and -0.7% at stress costs. The mean (+2.6% to +2.8%, stress +1.6% to +1.8%) is stable. A typical 11-day run is about flat; the average comes from a minority of large windows (22% of windows are +10% or better).
- Candidate_2's stop plateau is narrower than "5 to 8 ATR" suggests on this cell: at 4.5 ATR the stress total is +9% with thirds -3% / +22% / -7%; at 7.5 ATR +26% with thirds -3% / +20% / +8%.
- Candidate_1 behaves like a lottery over its neighbours: fast 30 gives stress -21%, slow 250 gives stress +137%. The filed cell says little.
- Candidate_3's new-coverage result: with TUT removed from the universe it is +10.9% and -23.8% at stress costs.
- Statistical weight is modest everywhere. Clustered by entry week, candidate_2's trade mean has t = 1.6 (1.1 at stress costs).

## 5. Placebo and market direction

None of the candidates uses a regime filter, so the shifted-label test was applied to the EMA signal itself: (a) the fast and slow EMA arrays rolled in time by 1,000 to 6,000 bars (same frequency and persistence, wrong timing), (b) each coin trading another coin's signal (same market timing, wrong coin). Six of each, same stops, slots and costs.

| total return (stress) | real | time-shifted: mean, best | other coin's signal: mean, best | placebos at or above real |
|---|---|---|---|---|
| candidate_1 | +59% (+17%) | -30%, +4% (-54%, -28%) | +5%, +75% (-27%, +24%) | 1 of 12 |
| candidate_2 | +87% (+48%) | -5%, +33% (-29%, 0%) | +28%, +44% (-1%, +10%) | 0 of 12 |
| candidate_3 | +66% (+13%) | -48%, -37% (-65%, -58%) | -42%, -23% (-60%, -46%) | 0 of 12 |

This settles more than the track claimed. A placebo short with the same exposure (about 58% of slot-hours) earns what the bear market gives: +28% with the right market timing and the wrong coin, about zero with the wrong timing, and nothing after stress costs. The real short signal is 59 points above the first and 92 above the second, and it is positive in the first third (+12%) where time-shifted placebo shorts lost 21%. So candidate_2 is not just bear-market drift: both the timing and the coin choice add return. The passive short figures are right (+45% uncapped, +49% with the collateral cap; 94% of coins fell).

It is still a directional bet. Rolling 11-day windows of the continuous run, split by what the equal-weight market did in the same window:

| mean 11-day return (win rate) | market worst third (-14%) | middle third (-3%) | best third (+11%) | market above +5% (72 windows) |
|---|---|---|---|---|
| candidate_1 | +1.9% (55%) | +2.7% (56%) | +2.1% (59%) | +2.4% (63%) |
| candidate_2 | +10.5% (92%) | +3.0% (71%) | -4.3% (19%) | -5.0% (10%) |
| candidate_3 | -4.0% (18%) | +0.9% (43%) | +11.2% (85%) | +12.8% (89%) |

On 25 non-overlapping 11-day blocks candidate_2 has a slope of -0.49 against the market (correlation -0.70) and an intercept of +2.0% per block (standard error about 1.1%). Candidate_3 is the mirror image (slope +0.68). Candidate_1 is close to market-neutral (slope +0.13), which is its one real merit. These splits use the market's move during the window, which is not known in advance: they describe the risk, they do not show that a gate can pick the side.

## What this means for use

- Candidate_2 may go forward to the selection period as the short trend leg. Expect about -5% in an 11-day window in which the average coin rises more than 5%, and about +10% in one where it falls 14%. With 11 days left that is a bet on direction with a small positive offset, not a standalone edge.
- Candidate_1 and candidate_3 should not go forward on their own numbers. Candidate_1's only argument is that it did not depend on market direction on design.
- Nothing here was tested outside the design period, and the design period was a bear market.
