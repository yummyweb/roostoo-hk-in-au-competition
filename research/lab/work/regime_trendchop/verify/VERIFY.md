# Verification of track regime_trendchop (design panel only)

Verdict: both candidates **replicate exactly and are causal, but are weak**. Neither is refuted; neither is strong
enough to call "survives". Candidate 1 is the sturdier of the two under stress costs (the opposite of the track's
preference for candidate 2).

Scripts: `v1.py` (evalkit report of candidate 2 with the 40-cut check), `v2.py` (costs, concentration, placebo,
neighbours, fresh windows), `v3.py` (label neighbours, grids, trade concentration, stop overshoot, evalkit report of
candidate 1 with the 40-cut check), `v4.py` (t-statistics, bar-by-bar look at the two largest trades).
Raw output: `v2.json`, `v3.json`, `c1_report.json`, `c2_report.json`, logs `v2.log`, `v3.log`.
To run the many variants quickly I used a subclass `FastEma` that only loops over coins whose entry test can pass; it
reproduces `strategies.EmaCross` to the last digit on both candidates (same totals, trades, windows, stress result).
All numbers use `start=744` unless stated.

## 1. Replication (`evalkit.report` on the candidate files, 40 cuts)

| | candidate_1 claimed | reproduced | candidate_2 claimed | reproduced |
|---|---|---|---|---|
| total return | +65.91% | +65.91% | +89.77% | +89.77% |
| max drawdown | 17.44% | 17.44% | 21.36% | 21.36% |
| 11-day windows mean / median | +2.53% / -0.44% | same | +3.27% / +0.48% | same |
| thirds | -5 / +53 / +14 | -4.7 / +53.3 / +13.6 | +2 / +81 / +3 | +2.0 / +81.0 / +2.8 |
| stress total, 11-day mean | +30.34%, +1.52% | same | +20.23%, +1.50% | same |
| stress thirds | -10 / +37 / +6 | -10.1 / +36.9 / +5.9 | -14 / +53 / -8 | -14.4 / +53.5 / -8.5 |
| trades, active days | 189, 43.5% | same | 352, 60.4% | same |
| look-ahead check | pass (8 cuts) | **pass (40 cuts)** | pass (8 cuts) | **pass (40 cuts)** |

The K-Means labels I recomputed from `candidate_1.make` are identical to the track's cached labels.

## 2. Code reading

- No look-ahead found. EMA, ATR, signal age, the gap and the label at row t use rows <= t; orders execute in bar t+1.
  `regime.walk_forward` standardises and fits on rows before each refit point only.
- No abuse of the fill model. The stop sits 3 ATR below the close, the limit 5 bp below it; there is no take-profit.
  After a spike bar the trailing stop is often above the close, and the harness then exits at the next open less costs
  (checked bar by bar on the STO and TUT trades), which is what a market sale would get.
- The result does not need the maker fee: market entries give the same result (section 3).
- Plain defect, no effect on the numbers claimed: `cooldown=6` is inert. `EmaCross` sets the re-entry block only on a
  cross-back exit, and 188 of 189 (candidate 1) and 352 of 352 (candidate 2) exits are trailing stops. Changing the
  cooldown to 4 or 8 gives identical results. 22 (candidate 1) and 43 (candidate 2) entries come within 6 bars of a
  stop-out on the same coin. The docstring's "exit on the cross back" describes 1 trade.
- Candidate 1 trades on 43% of days, below the competition's 8-of-14 requirement (57%). Candidate 2 is at 60%.

## 3. Costs

| total return (thirds) | candidate_1 | candidate_2 |
|---|---|---|
| default | +65.9% (-5 / +53 / +14) | +89.8% (+2 / +81 / +3) |
| stress | +30.3% (-10 / +37 / +6) | +20.2% (-14 / +54 / -8) |
| market entries, default costs | +65.2% (-4 / +52 / +13) | +85.1% (+4 / +80 / -1) |
| market entries, stress costs | +41.7% (-8 / +42 / +8) | +40.3% (-6 / +64 / -9) |
| six coarse-tick coins removed, default | +28.4% (-3 / +44 / -8) | +49.6% (+11 / +68 / -20) |
| six coarse-tick coins removed, stress | +5.9% (-8 / +32 / -12) | +5.2% (-6 / +45 / -23) |
| stop overshoot 30 / 50 / 100 bp (default 8) | +49.6% / +36.2% / +7.6% | +56.6% / +31.5% / -15.3% |
| market entries, stress costs, 50 bp stop overshoot | +20.0% (-12 / +32 / +3) | +2.8% (-16 / +47 / -17) |

Stress-positive sub-periods: candidate 1 two of three (the third is +6%), candidate 2 one of three.
From `start=1400` the split falls differently (candidate 1 stress +11 / +12 / +11, candidate 2 +11 / +13 / -1): the
profit is lumpy enough that where the cuts fall decides the picture.

## 4. Fragility

| | candidate_1 | candidate_2 |
|---|---|---|
| best coin dropped from the universe (rerun) | TUT: +30.5%, stress +3.9% | STO: +76.0%, stress +12.3% |
| best coin's trades zeroed | +41.4% | +67.5% |
| three best coins dropped (rerun) | **-3.6%** | +31.4% |
| best calendar month removed | Nov 2025 (+31%): +26.4% | Jan 2026 (+32%): +44.0% |
| months positive | 6 of 10 | 6 of 10 |
| P&L without the 5 best trades | **-$16.5k** (5 of 189 trades) | **-$10.9k** (5 of 352) |
| median trade / mean trade | -1.24% / +1.26% | -1.04% / +0.86% |
| t-statistic of daily returns, default / stress | 1.36 / 0.81 | 1.52 / 0.60 |
| non-overlapping 11-day windows positive | 10 of 25 | 12 of 25 |

The whole profit of both candidates is five pump events (STO +60% in 5 h, TUT +86% in 10 h, PEPE, FIL, 1000CHEEMS);
three of those coins are coarse-tick. STO traded about $9k an hour in the day before entry. The mock exchange fills
at mirrored prices so that is not a fill problem there, but it shows what kind of event carries the result.

Neighbours, one parameter at a time, about +-25% (fast 18/30, slow 75/125, freshness 11/19, stop 2.25/3.75 ATR,
ATR length 18/30, cooldown 4/8, limit offset 3.75/6.25 bp, ttl 1/3, slots 3/5; candidate 2 also min_gap 0.94/1.56;
candidate 1 also first fit 750/1250 bars and refit step 252/420 bars, from `start=1700`):

| | candidate_1 (22 neighbours) | candidate_2 (20 neighbours) |
|---|---|---|
| 11-day mean keeps its sign, default costs | 22 of 22 (100%) | 20 of 20 (100%) |
| 11-day mean keeps its sign, stress costs | 21 of 22 | 19 of 20 |
| total positive at stress | 21 of 22 | 18 of 20 |
| mean total of the strategy neighbours, default / stress | +61.9% / +27.0% | +78.5% / +15.1% |
| weakest neighbours (default, stress) | stop 2.25 ATR +22.6%, -7.1%; freshness 11 +25.0%, +7.3% | stop 2.25 ATR +21.7%, -32.5%; freshness 19 +69.7%, -2.9% |

Two of each set (cooldown) are inert copies of the base. Label neighbours agree with the base label on 99.5% of
coin-hours and return +59% to +74% (stress +28% to +38%); feature set agn8 +77% (stress +34%), K=3 top state +33% (+12%).

Freshness is the sensitive parameter and 15 is its peak (total, stress in brackets, `start=744`):

| freshness (h) | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 36 |
|---|---|---|---|---|---|---|---|---|---|
| candidate_1 | -1% (-4%) | +21% (+13%) | +17% (+4%) | +20% (-0%) | +66% (+30%) | +64% (+26%) | +46% (+11%) | +37% (+4%) | +8% (-28%) |
| candidate_2 | +2% (-1%) | +18% (-4%) | +49% (+10%) | +66% (+13%) | +90% (+20%) | +78% (+3%) | +58% (-13%) | +39% (-22%) | -10% (-56%) |

Mean over 6-24 h: candidate 1 +39% (stress +13%), candidate 2 +57% (stress +1%). The track's plateau claim for
candidate 1 ("all positive at stress") holds from `start=1400` but not from 744 (freshness 12 is -0.2%).
Candidate 2 by min_gap at freshness 15: 0.5 +25% (-41%), 0.75 +49% (-25%), 1.0 +115% (+22%), 1.25 +90% (+20%),
1.5 +67% (+20%), 1.75 +27% (+4%), 2.0 +22% (+2%).

Fresh-start 11-day windows (`h.fresh_windows`, step 3 days, start 744, 91 windows):

| | candidate_1 | candidate_2 | Breakout |
|---|---|---|---|
| mean / median | +2.64% / -0.44% | +3.35% / +0.41% | +2.31% / -0.17% |
| share positive, >= +10%, <= -10% | 38%, 15%, 1.1% | 52%, 21%, 3.3% | 49%, 23%, 13% |
| worst window | -10.5% | -12.4% | -16.0% |
| stress mean / median | +1.61% / -0.65% | +1.53% / -0.76% | - |
| market entries, mean | +2.64% | +3.32% | - |

## 5. Placebo labels

Same rule, label delayed (common `start=2900` so every label exists); total at default costs (stress):

| | candidate_1 gate | candidate_2 gate (gap >= 1.25 as a mask) |
|---|---|---|
| true label | +74.1% (+45.0%), 136 trades | +82.4% (+37.4%), 230 trades |
| 500 bars late | -18.9% (-47.6%), 438 trades | -24.9% (-40.6%), 228 trades |
| 1,000 bars late | +4.2% (-33.9%), 439 trades | -16.0% (-32.3%), 251 trades |
| 1,500 bars late | -29.2% (-53.2%), 445 trades | -42.2% (-57.6%), 325 trades |
| no gate (freshness 15 only) | -29.8% (-64.7%), 705 trades | same |
| Breakout benchmark | +19.9% (-1.3%) | same |

Each coin given another coin's label (5 draws, `start=1400`): candidate 1 -23% to -43% against +73.8%; candidate 2
-46% to +6% against +84.9%. The gate carries real, coin-specific information relative to a placebo: this part of the
claim holds. For candidate 1 the delayed label lets three times as many trades through, so the comparison is not
trade-count matched; candidate 2's is, and gives the same answer.

## Decision

- **candidate_1: weak.** Replicates, passes the 40-cut check, beats every placebo, 21 of 22 neighbours keep their sign
  at stress, stress-positive in two of three sub-periods. It stays "weak" because the profit is five trades (without
  them -$16.5k; without the three best coins -3.6%), the median 11-day window is negative with 38-40% of windows
  positive, the daily-return t-statistic is 1.4 (0.8 at stress) after about 640 variants, freshness 15 is the peak of
  its range, and it trades on too few days for the competition rule.
- **candidate_2: weak.** Replicates and is causal, beats its placebos, but is cost-dependent: stress-positive in one
  of three sub-periods, the freshness plateau averages about +1% at stress, and a 100 bp stop overshoot turns it negative.
