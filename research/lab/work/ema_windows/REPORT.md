# Track "ema_windows": which EMA crossover windows, on hourly candles

Design panel only (2025-05-02 to 2026-03-11, 50 pairs, start bar 744). All portfolio numbers come from `evalkit.report`.

## Verdict: weak edge, short-biased, not robust

- **The textbook windows lose badly.** EMA 9/21 (with or without the 55 line) on hourly candles: long -86% to -89%, both sides -77% to -83%, short -44% to -47%; -82% to -97% at stress costs. No risk setting rescues the fast corner of the map (fast <= 12 h, slow <= 72 h): 0-6% of its long cells have a positive 11-day mean at any stop width.
- **At the risk settings the brief started from (4 slots, 3-ATR trailing stop), 0 of 216 window/side combinations beat cash at stress costs.** Best: long 24/300 at -14%.
- **The stop width matters more than the windows.** A 2-ATR stop loses in all 216 cells. With a trailing stop of 4-8 ATR, a region of slow windows (fast 18-72 h, slow 100-300 h) has a positive 11-day mean in 80-100% of its cells for long, short and both, at default costs. At stress costs that region averages about zero for long-only (-11% to +5% with a stop), +13% to +18% for short-only with a 6-8 ATR stop, +32% to +37% for both sides with a 5-6 ATR stop.
- **Where the money came from.** Short side: 94% of coins fell in this period and a passive equal-weight short made +49% (thirds -13% / +31% / +36%). Long side: one to three coins. Both-sides candidate: +59%, but -$10.8k without its three best coins and one 30-day month of +51%.
- **The signal itself is weak.** Without slots, stops or costs, coins with fast EMA above slow beat coins below by a median 0.8 bp per hour (t about 1); only slow = 300 h (and 72/200) reaches t = 1.9-2.4, before any correction for trying 72 pairs, and all of it comes from the middle third (thirds average -0.1 / +2.9 / -0.5 bp per hour).
- Against the benchmark: `baselines.Breakout` is +40%, stress +4%, thirds +12% / +61% / -23%, 11-day mean +2.1%, median -0.6%. The short-only and both-sides candidates beat it on design; the long-only one does not once its best coin is removed. Whether the short result is skill or the bear market cannot be settled on this data: that is what the held-back periods are for.

**Variants tried: 2,429 portfolio backtests** (each at default and stress costs; 432 of them rerun at zero cost), plus about 220 signal-level measurements. Any single cell quoted below is one draw from that many.

## Method

1. `strategies.EmaCross` inside `Portfolio`, market entries, cooldown 6, ATR(24). Sweeps used `FastEma` (`common.py`): the same class with cached indicators and a pre-filtered candidate loop; `verify_fast.py` confirms identical orders, stops and equity on 10 configurations.
2. Stage A (216): fast {4,6,9,12,18,24,36,48,72} x slow {21,36,55,72,100,150,200,300,480}, fast < slow, sides long / short / both, no trend line, fresh 3, 4 slots, 3-ATR trail.
3. Stage C (225): fresh {1,3,6,12,always} on 15 window pairs. Stage B (246): trend line {none, 2x slow, 4x slow, 200, 480, 720} on the same 15 pairs, all started at bar 2,160 so a filter is not judged on a shorter period.
4. Stages D and E (1,512): the full map again at 8 slots, and at stop widths 2, 4, 5, 6, 8 ATR and no stop.
5. Signal-level event study (`events.py`): every cross on every coin, harness fill timing, no slot limit. Used for whipsaw, entry lag, and exits on identical entries. `state_test.py`: next-hour return by EMA state.
6. Finalists (20), team-document windows (18), portfolio exit variants (192). Look-ahead check on the three filed candidates only: all pass.
7. Plateau rule: a cell counts when its 11-day mean is positive, at least 70% of its neighbours are positive and at least two thirds are positive (P2), or all three (P3).

Warm-up note: `EmaCross` does not trade before 3 x the longest window. Cells with slow = 480 start at bar 1,440 (29 of 282 days idle), which dilutes them slightly.

## The map in one table

Average over regions of the fast x slow map. Cell: 11-day mean / total / total at stress costs / thirds.

Middle region (fast 18-72, slow 100-300; 20 cells):

| stop | long | short | both |
|---|---|---|---|
| 2 ATR | -1.9% / -44% / -73% / -6 -18 -28 | -1.8% / -39% / -68% / -15 -4 -25 | -3.3% / -63% / -89% / -18 -17 -45 |
| 3 ATR (base) | +0.5% / +1% / -37% / +13 +10 -17 | +0.0% / -6% / -39% / -1 +7 -11 | +1.1% / +13% / -49% / +18 +26 -23 |
| 4 ATR | +2.3% / +50% / +5% / +26 +36 -10 | +0.6% / +6% / -25% / -4 +10 +1 | +2.9% / +74% / -1% / +16 +64 -8 |
| 5 ATR | +1.6% / +28% / -4% / +10 +34 -12 | +1.3% / +26% / -4% / -5 +25 +6 | +3.6% / +101% / +32% / -6 +96 +11 |
| 6 ATR | +1.2% / +13% / -11% / +5 +24 -11 | +2.0% / +49% / +18% / +2 +35 +7 | +3.3% / +89% / +37% / +2 +82 +3 |
| 8 ATR | +1.6% / +25% / +3% / +28 +15 -12 | +1.6% / +36% / +13% / -4 +27 +10 | +1.9% / +36% / +7% / -3 +56 -9 |
| none (opposite cross only) | +3.0% / +55% / +39% / +20 +69 -22 | +1.8% / +38% / +25% / -6 +23 +19 | -0.4% / -23% / -31% / -18 +2 -10 |

Fast corner (fast <= 12, slow <= 72; 16 cells), which contains 9/21:

| stop | long | short | both |
|---|---|---|---|
| 3 ATR (base) | -5.8% / -79% / -92% | -1.4% / -38% / -76% | -3.7% / -62% / -88% |
| 6 ATR | -2.1% / -54% / -75% | -0.6% / -27% / -59% | -0.4% / -16% / -50% |
| none | -2.1% / -57% / -75% | -0.6% / -25% / -54% | -0.8% / -23% / -50% |

Cells (of 72 per side) with a positive total at stress costs, long / short / both: stop 2: 0 / 0 / 0. Stop 3: 0 / 0 / 0. Stop 3 with 8 slots: 0 / 0 / 0. Stop 4: 14 / 3 / 13. Stop 5: 8 / 17 / 31. Stop 6: 5 / 27 / 39. Stop 8: 13 / 27 / 25. None: 23 / 30 / 9.

What to read from it:

- **Windows.** The ordering of the map is stable: rank correlation of the 11-day mean with the base map is +0.72 to +0.95 for long and +0.60 to +0.85 for short across all risk settings. Fast pairs are worst everywhere; fast 18-48 h with slow 150-300 h is the least-bad region everywhere. Slow = 480 is erratic (few trades, one period).
- **Long-only has no plateau in stop width.** Around 24/200 (3 x 3 cells: fast 18-36, slow 150-300) the median stress total is +13% at 4 ATR, -4% at 5, -20% at 6, +8% at 8, +67% with no stop (range -39% to +228%). The last third is negative for every long variant.
- **Short-only has one.** Same 3 x 3 block: stress positive in 0/9 cells at 4 ATR, 8/9 at 5, 9/9 at 6 (all nine with three positive thirds, median +36%), 9/9 at 8 (median +25%), 8/9 with no stop.
- **Both sides.** Same block: stress median +6% at 4 ATR (5/9 positive), +56% at 5 (8/9), +40% at 6 (9/9), +8% at 8 (6/9), -29% with no stop (1/9). Only 1-4 of 9 cells have three positive thirds: the middle third carries it.
- **Costs decide.** Before any costs the middle region made +72% long, +55% short, +177% both at the base stop; default costs take that to +1% / -6% / +13% and stress costs to -37% / -39% / -49%. Turnover is 350-1,050x equity at the base stop and 80-260x with a 6-ATR stop or none.
- **Noise.** A 4-slot book follows one path. Changing something that should not matter moves the both-sides candidate from +59% to: +73% / +130% / +170% (fresh 1 / 6 / 12), +96% / +68% / +25% (3 / 6 / 8 slots), +49% (5-ATR stop), +28% (limit entries). Stress total across those neighbours: -15% to +93%. Treat differences smaller than about 50 points of total return between single cells as noise.

Other dimensions:

- **Trend line: no.** Requiring price above (below) a slower EMA made long variants worse in 9-13 of the 11-15 pairs tested (2x slow: -1.9 points of 11-day mean; 200: -1.7; 480: -0.8; 720: -0.1) and did nothing for shorts (-0.4 to +0.1 points). It adds trades: the state switches on again each time price re-crosses the trend line.
- **Fresh: 1-3 bars at the base stop.** Average 11-day mean over 15 pairs, long: -1.6% (1), -1.8% (3), -1.9% (6), -2.5% (12), -2.0% (always, with 55% more trades). With a wide stop the ranking reverses on the one candidate tested, so this is not a strong result either way.
- **Slots: 4, not 8.** At the base stop, 8 slots lowers the 11-day mean of the middle region for all three sides (long +0.5% to 0.0%, short 0.0% to -0.3%, both +1.1% to -0.1%) and raises trades by 54-73%. On the finalists 8 slots cut return and drawdown together (short: +65% with 18% drawdown against +87% with 21%; both: +25% against +59%).

## Whipsaw

Signal level (every cross, every coin, exit at the opposite cross):

| fast/slow | long signals per coin per week | long win rate | avg win / avg loss | mean net per long signal | short win rate | mean net per short signal |
|---|---|---|---|---|---|---|
| 4/21 | 5.61 | 22% | +4.7% / -1.7% | -0.29% | 27% | -0.10% |
| 9/21 | 3.78 | 25% | +5.3% / -2.2% | -0.32% | 31% | -0.02% |
| 12/36 | 2.48 | 24% | +6.6% / -2.6% | -0.38% | 33% | +0.09% |
| 18/72 | 1.41 | 22% | +8.9% / -3.3% | -0.65% | 31% | +0.21% |
| 24/100 | 1.03 | 20% | +11.4% / -3.9% | -0.78% | 31% | +0.34% |
| 48/200 | 0.54 | 20% | +16.2% / -5.6% | -1.14% | 36% | +1.01% |
| 72/300 | 0.33 | 22% | +24.7% / -6.8% | +0.09% | 41% | +2.86% |
| 72/480 | 0.24 | 19% | +29.6% / -6.8% | +0.24% | 37% | +4.38% |

The long win rate is 19-25% at every window length: slower windows do not win more often, they trade less and win bigger. Long signals lose on average at every length except the two slowest, and those two are positive only in the first third (+7.0% and +10.8% per trade, then -3.5% to -4.7%). In the portfolio (4 slots, base stop) trades per coin per week fall from 0.81 (slow 21) to 0.26 (slow 480) for longs and the win rate rises only from 23% to 29%.

## Where the team's document windows sit

| document setting | as hourly EMAs | position on the map | long / short / both total (stress) |
|---|---|---|---|
| 9/21 + 55 on hourly candles | 9 / 21 / 55 | fast corner, worst region | -89% / -44% / -83% (-97% / -82% / -94%) |
| 9/21 + 55 on 4-hour candles | 36 / 84 / 220 | between cells 36/72 and 36/100, plus a trend line | -67% / -44% / -59% (-86% / -75% / -87%); without the trend line those cells are -20% and +17% long |
| 9/21 + 55 on daily candles | 216 / 504 / 1,320 | beyond the slow edge; cannot trade before bar 3,960 | -35% / -12% / -38% on the remaining 3,559 of 6,775 hours, 139-286 trades |
| 50/200 golden cross on hourly candles | 50 / 200 | cell 48/200, inside the least-bad region | +2% / +3% / +55% at the base stop (-33% / -29% / -24%) |
| 50/200 on 4-hour candles | 200 / 800 | beyond the slow edge; first trade at bar 2,400 | -8% / -14% / -19% (-16% / -23% / -34%), 117-257 trades |
| 50/200 on daily candles | 1,200 / 4,800 | not testable: needs 600 days of history, the panel has 313 | would give at most one signal per coin in 11 days |

The hourly golden cross is the only document setting inside the usable region. With a 6-ATR stop its both-sides cell is the best of the whole map (+169%, stress +101%), which is exactly the kind of single top cell not to trust: its four neighbours are +44% (48/150, stress +1%), +31% (72/200, stress -3%), +114% (36/200, stress +57%) and +146% (48/300, stress +86%).

## Team question 1: how late is the entry, and what does a faster entry cost?

Measured two ways (appendix E).

Within each window pair's own swing, winners only: at entry the median winning long had already used **25-30% of the move from the pre-signal low to the eventual high, at every window length** (9/21: 30%, 24/100: 26%, 48/200: 26%, 72/480: 29%). It then kept 16-28% and gave back 39-49% before the opposite cross. In clock and price terms the entry comes 9 h after the low and 3.7% above it for 9/21, 28 h and 6.7% for 24/100, 53 h and 9.5% for 48/200, 81 h and 11.3% for 72/300.

Against a common yardstick, hindsight up-swings of at least 15% (877 legs, median +27% over 95 h):

| fast/slow | legs with a buy signal inside | share of the leg gone at the first buy | buys per coin per week | of which false (inside a down-leg) |
|---|---|---|---|---|
| 9/21 | 88% | 29% | 3.42 | 50% = 1.72 per coin per week |
| 12/36 | 83% | 34% | 2.24 | 46% = 1.03 |
| 24/100 | 69% | 47% | 0.91 | 31% = 0.29 |
| 48/200 | 51% | 55% | 0.47 | 29% = 0.14 |
| 72/480 | 24% | 61% | 0.21 | 24% = 0.05 |

For swings of 25% or more (median +47% over 200 h) the first buy lands at 19% (9/21), 33% (24/100), 40% (48/200), 54% (72/480) of the leg.

So going from 24/100 to 9/21 gets in about 18 points of the leg earlier (about 5% of price on a 27% leg), and costs 2.5 more trades per coin per week, 1.4 of them false, and the average losing 9/21 trade costs 2.2%. Per coin per week the long signals net -1.2% (9/21), -0.8% (24/100), -0.6% (48/200), +0.03% (72/300). The statement in the document is true as arithmetic but it is not what limits profit here: the number of false signals times cost is.

## Team question 2: how to tell when the trend will reverse

With these tools, not in advance. The opposite cross confirms a reversal after the median winner has given back 39-49% of its move. The state test (appendix G) shows how little the EMA state says about the next hour. And on identical long entries no exit rule made the signal profitable (next table). What can be chosen is how much to give back before leaving.

## Team question 3: when to sell, between greedy and safe

Identical entries: every 24/100 cross-up on every coin, 2,085 trades, default costs (appendix F1 has 9/21 and 48/200, and the short side).

| exit | median hold | mean peak open profit | kept of that peak, trades that were up 2%+ (median) | kept, all trades (sum / sum) | win rate | mean net per trade | by third |
|---|---|---|---|---|---|---|---|
| trail 1.5 ATR | 3 h | 2.0% | 45% | +3% | 31% | -0.31% | -0.39 / -0.47 / -0.05 |
| trail 2 ATR | 6 h | 2.7% | 37% | +4% | 33% | -0.27% | -0.32 / -0.54 / +0.04 |
| trail 3 ATR | 13 h | 4.1% | 22% | +4% | 32% | -0.20% | +0.07 / -0.79 / +0.09 |
| trail 4 ATR | 23 h | 5.6% | 12% | +6% | 32% | **-0.04%** | +0.24 / -0.52 / +0.12 |
| trail 6 ATR | 40 h | 7.9% | -2% | +1% | 31% | -0.25% | +0.08 / -0.31 / -0.55 |
| opposite cross | 44 h | 8.1% | -25% | -6% | 20% | -0.78% | -0.12 / -0.91 / -1.40 |
| opposite cross + trail 3 | 12 h | 3.9% | 22% | +5% | 31% | -0.18% | +0.05 / -0.70 / +0.09 |
| time 12 h | 13 h | 2.9% | 48% | -3% | 43% | -0.37% | -0.13 / -0.80 / -0.21 |
| time 24 h | 25 h | 4.2% | 41% | +3% | 43% | -0.18% | -0.02 / -0.46 / -0.07 |
| time 48 h | 49 h | 5.9% | 20% | -8% | 40% | -0.73% | -0.35 / -0.96 / -0.93 |
| time 168 h | 169 h | 10.8% | 3% | -10% | 41% | -1.36% | +0.65 / -2.54 / -2.44 |

- Too safe (1.5-2 ATR, about 2-2.6% for a typical coin): keeps the largest share of each small peak, but the peak is cut to 2-2.7% and costs eat it. In the portfolio a 2-ATR stop loses in all 216 cells.
- Too greedy (opposite cross alone, or a week): lets the peak reach 8-11% and then hands it back; under the opposite cross the median trade that was up 2% ends below its entry.
- Least bad for longs: a 4-ATR trail (about 5% for a typical coin, ATR(24h) is 1.3% of price at the median). Still -0.04% per trade: no exit turns these long entries into a positive expectation.
- Shorts: wider is better. On 24/100 short entries the mean net per trade is -0.33% (trail 2), -0.20% (3), 0.00% (4), +0.35% (6), +0.34% (opposite cross), +0.50% (168 h). That is what a falling market does to any short that is held longer.
- Portfolio level agrees: 2 ATR loses everywhere, 3 ATR is about zero, 4-6 ATR is the best band (long 4, short and both 5-6), no stop works for one-sided books but not for both sides sharing slots. A fixed (non-trailing) 3-ATR stop gave mixed results and adding a 48-96 h time limit to the trailing stop changed almost nothing.

## Recommendation

For the trend-following part of the team's design:

- **Windows: fast EMA 24 h, slow EMA 200 h** (on 4-hour candles: EMA 6 over EMA 50; the document's hourly 50/200 is the neighbouring cell). Plateau: fast 18-48, slow 150-300. Do not use 9/21/55 on hourly or 4-hour candles.
- **No trend line. Entry within 3 bars of the cross. 4 slots. Market entries** (limit entries were worse on the one finalist tested, +28% against +59%, stress -15%).
- **Exit: opposite cross, plus an ATR(24h) trailing stop of 6 ATR for shorts and both-sides books (plateau 5-8), 4 ATR for longs (no plateau).** Never 2-3 ATR.

| | candidate_1: both | candidate_2: short only | candidate_3: long only (least bad, not an edge) |
|---|---|---|---|
| settings | 24/200, trail 6 ATR | 24/200, trail 6 ATR | 24/200, trail 4 ATR |
| total / max drawdown | +59.1% / 25.4% | +86.8% / 21.4% | +66.3% / 44.6% |
| Sharpe / Sortino / Calmar | 1.24 / 2.13 / 3.25 | 1.85 / 3.50 / 5.80 | 1.26 / 2.62 / 2.09 |
| 11-day windows: mean / median / win | +2.25% / +1.44% / 57% | +3.05% / +2.58% / 61% | +2.69% / -0.21% / 49% |
| 11-day windows: >= +10% / <= -10% | 12% / 4% | 20% / 5% | 24% / 10% |
| thirds | +12% / +45% / -2% | +12% / +47% / +13% | +48% / +43% / -21% |
| stress: total / 11-day mean | +16.8% / +1.03% | +47.6% / +2.12% | +13.0% / +1.15% |
| stress thirds | +1% / +30% / -10% | +4% / +35% / +5% | +32% / +24% / -31% |
| restart-flat 11-day windows (68): mean / median / win | +1.7% / +0.2% / 51% | +2.6% / +2.4% / 56% | +2.4% / -0.5% / 50% |
| same at stress costs: mean / median | +0.3% / -1.3% | +1.6% / +1.1% | +0.9% / -1.7% |
| trades / win rate / avg hold | 430 / 36% / 55 h | 311 / 41% / 55 h | 500 / 31% / 24 h |
| turnover / fees | 264x / $26k | 208x / $21k | 447x / $45k |
| days with a fill | 73% | 73% | 83% |
| P&L long / short | +$13.6k / +$39.2k | - / +$87.5k | +$62.9k / - |
| P&L without its 3 best coins | -$10.8k | +$40.5k | -$52.2k (TUT alone is +$62.3k) |
| 30-day months | -4 +13 +4 -1 -2 +51 -9 -6 +15 | +13 -5 +2 -2 +14 +27 +8 +8 +19 | +11 +24 +9 +25 +9 +11 -19 +8 -11 |
| stress total across the 3 x 3 window block | median +40%, 9/9 positive | median +36%, 9/9 positive, 9/9 with three positive thirds | median +13%, 6/9 positive |
| look-ahead check | pass | pass | pass |

How to read them:

- **candidate_2 (short)** is the only one that clears "beats cash after stress costs in most sub-periods" with a plateau in both windows and stop width. It did not lose in the first third, when the average coin rose 16% and a passive short lost 13%. But it has only been seen in a period where 94% of coins fell; a passive short made +49%. It belongs behind the regime gate the team already plans ("shorts when the market is bad").
- **candidate_1 (both)** is the team's stated design. It clears the bar on paper, but three coins (ZEC, ICP, ZEN) and one month are the whole profit, and three quarters of it is the short leg.
- **candidate_3 (long)** is filed only so the integrator has a long leg to gate. It is one coin.

## What failed

- Everything in the fast corner, including 9/21 and 9/21/55 on hourly and on 4-hour candles.
- Every window at a 2-ATR stop (0/216), and every window at stress costs with a 3-ATR stop (0/216) or with 8 slots (0/216).
- The trend line (2x slow, 4x slow, 200, 480, 720).
- Entering whenever the state is on instead of near the cross (55% more trades, worse).
- Daily-candle versions of the document windows: too slow for the data and for an 11-day contest.
- Long-only at stress costs: no stop width gives a stable sign, and the last third loses for every variant.
- Time exits of 48 h and longer on long entries; adding a time limit to the trailing stop (no effect).
- Both sides with no stop: the long and short legs each work alone, but sharing 4 slots with no stop the book is -23% in the middle region (rank correlation with the base map +0.02).

## What would have to be true for this to work live

1. Costs close to the default model (10 bp taker, about 3 bp of spread and slippage). At stress costs the long leg is about zero.
2. Multi-day trends in the next 11 days. The profit came in bursts: the middle third and one month. In 11-day windows restarted flat, the both-sides candidate has a median of +0.2% (-1.3% at stress costs).
3. For the short leg, a market that keeps falling or at least does not rally broadly. Nothing here tests it in a bull market.

## Caveats

- 2,429 variants; best cells are inflated. Region averages and the 3 x 3 blocks are the numbers to use, and they are still drawn from one 10-month bear market.
- Four slots means one path. Single-cell totals move by 50 points and more when an irrelevant setting changes.
- The three thirds are not independent tests of the short side: coins fell in two of them.
- `evalkit` thirds are at default costs; stress thirds are given for candidates only.
- Stops are filled at the stop price less spread, slippage and 8 bp (15 bp stress). A coin that gaps through a 6-ATR stop within the minute poll would do worse.
- Slow candidates trade on 73% of days on average; a quiet 11-day stretch could fall short of the competition's active-day requirement.
- Limit entries, the regime filter and combination with the mean-reversion part are other tracks' work; one limit-entry run here was worse than market entry.
- Not tested: other ATR lengths, cooldown, position sizing, ranking rules for which signals get the slots.

## Files (all under `work/ema_windows/`)

`candidate_1.py`, `candidate_2.py`, `candidate_3.py` (each exposes `make(panel, allow_long=None, allow_short=None)`), `candidate_<n>_report.json` (full evalkit output), `common.py`, `sweep.py`, `refine.py`, `extra.py`, `events.py`, `state_test.py`, `finalists.py`, `final_check.py`, `verify_fast.py`, `tables.py`, `summ.py`, `build_report.py`, and the raw results `res_A.json` (base map), `res_B.json` (trend line), `res_C.json` (fresh), `res_D.json` / `res_E.json` (slots and stop widths), `res_T.json` (document windows), `res_X.json` (portfolio exits), `res_Z.json` (zero cost), `res_S.json` (state test), `res_F.json` (finalists), `res_P.json` (passive yardsticks and Breakout), `res_final.json`, `events.json`.

---

# Appendix: full tables

All numbers: design panel, start bar 744, $100k, evalkit.report. "Stress" = evalkit.STRESS costs. Thirds = total return in each third of the run.
Trades per coin per week = trades / 50 / 40.3.

## A. Base map: fast x slow, no trend line, fresh 3, 4 slots, 3-ATR trailing stop, market entries (216 variants)

### LONG 

**11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -7.5% | -6.8% | -6.8% | -6.8% | -4.4% | -3.5% | -2.6% | -1.6% | -2.9% |
| **6** | -8.8% | -6.4% | -6.2% | -4.9% | -4.3% | -2.5% | -2.2% | -0.6% | -1.3% |
| **9** | -6.7% | -6.0% | -4.4% | -3.8% | -2.8% | -2.3% | -1.2% | -0.4% | -1.2% |
| **12** | -5.9% | -5.1% | -4.1% | -1.8% | -2.4% | -1.6% | -1.1% | -1.0% | -1.3% |
| **18** | -5.7% | -5.3% | -2.3% | -0.7% | -0.8% | +0.7% | -0.7% | +0.6% | -0.8% |
| **24** |  | -5.3% | -0.3% | -0.6% | -0.3% | -0.1% | +0.8% | +1.8% | -0.6% |
| **36** |  |  | +0.5% | -0.2% | +1.2% | +0.6% | +1.0% | +1.7% | -1.3% |
| **48** |  |  | -0.0% | +0.4% | +0.4% | +0.5% | -0.1% | +0.8% | -1.0% |
| **72** |  |  |  |  | +0.7% | -0.1% | +1.3% | +0.8% | -0.8% |

**11-day window median**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -10.5% | -8.9% | -7.1% | -8.0% | -6.5% | -3.5% | -4.7% | -1.8% | -2.1% |
| **6** | -12.7% | -7.8% | -6.9% | -6.3% | -6.3% | -3.2% | -4.1% | -0.9% | -1.4% |
| **9** | -8.8% | -6.2% | -5.8% | -5.7% | -3.9% | -3.0% | -2.7% | -1.4% | -1.7% |
| **12** | -7.7% | -4.8% | -6.2% | -3.4% | -3.2% | -2.6% | -2.2% | -1.7% | -1.5% |
| **18** | -5.8% | -6.9% | -3.9% | -3.7% | -2.0% | -1.6% | -2.3% | -0.7% | -0.4% |
| **24** |  | -5.6% | -2.4% | -1.6% | -2.5% | -1.5% | -2.8% | +0.5% | -0.2% |
| **36** |  |  | -1.1% | -2.2% | -1.3% | -2.5% | -1.2% | +0.0% | -1.9% |
| **48** |  |  | -2.6% | -1.9% | -2.2% | -1.8% | -1.1% | -0.5% | -0.4% |
| **72** |  |  |  |  | -1.9% | -1.8% | +0.8% | -0.6% | -0.8% |

**Total return (default costs)**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -90% | -86% | -85% | -85% | -72% | -64% | -54% | -39% | -58% |
| **6** | -92% | -84% | -82% | -75% | -73% | -53% | -50% | -21% | -37% |
| **9** | -86% | -81% | -72% | -68% | -58% | -52% | -33% | -16% | -36% |
| **12** | -82% | -76% | -70% | -46% | -54% | -42% | -34% | -29% | -38% |
| **18** | -80% | -78% | -50% | -30% | -26% | -1% | -25% | -1% | -28% |
| **24** |  | -76% | -21% | -23% | -20% | -16% | +6% | +34% | -21% |
| **36** |  |  | -3% | -20% | +17% | +0% | +11% | +27% | -35% |
| **48** |  |  | -17% | -6% | -3% | -1% | -15% | +6% | -29% |
| **72** |  |  |  |  | +6% | -16% | +20% | +12% | -25% |

**Total return (stress costs)**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -98% | -96% | -95% | -95% | -90% | -86% | -82% | -72% | -77% |
| **6** | -98% | -95% | -94% | -91% | -89% | -79% | -78% | -61% | -63% |
| **9** | -96% | -94% | -89% | -87% | -82% | -77% | -67% | -54% | -60% |
| **12** | -94% | -91% | -87% | -76% | -78% | -71% | -65% | -60% | -59% |
| **18** | -93% | -91% | -78% | -67% | -62% | -46% | -57% | -40% | -52% |
| **24** |  | -90% | -62% | -60% | -57% | -52% | -36% | -14% | -44% |
| **36** |  |  | -49% | -56% | -32% | -39% | -28% | -16% | -52% |
| **48** |  |  | -55% | -45% | -41% | -41% | -45% | -27% | -46% |
| **72** |  |  |  |  | -33% | -43% | -17% | -16% | -41% |

**Trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 2030 | 1799 | 1582 | 1552 | 1412 | 1290 | 1201 | 1040 | 825 |
| **6** | 1826 | 1573 | 1419 | 1333 | 1247 | 1104 | 1053 | 909 | 700 |
| **9** | 1610 | 1383 | 1266 | 1179 | 1088 | 969 | 893 | 768 | 619 |
| **12** | 1451 | 1269 | 1143 | 1067 | 990 | 877 | 813 | 716 | 565 |
| **18** | 1291 | 1149 | 1008 | 934 | 845 | 763 | 722 | 610 | 494 |
| **24** |  | 1058 | 938 | 818 | 768 | 706 | 651 | 548 | 426 |
| **36** |  |  | 790 | 755 | 694 | 613 | 577 | 516 | 378 |
| **48** |  |  | 755 | 700 | 617 | 576 | 535 | 470 | 331 |
| **72** |  |  |  |  | 569 | 499 | 472 | 367 | 288 |

**Win rate**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 21% | 21% | 23% | 23% | 24% | 23% | 24% | 24% | 26% |
| **6** | 22% | 23% | 23% | 25% | 25% | 26% | 25% | 27% | 27% |
| **9** | 23% | 25% | 24% | 27% | 27% | 28% | 27% | 27% | 29% |
| **12** | 24% | 25% | 26% | 28% | 27% | 28% | 28% | 27% | 28% |
| **18** | 26% | 26% | 27% | 28% | 29% | 29% | 29% | 30% | 31% |
| **24** |  | 27% | 28% | 29% | 30% | 29% | 32% | 33% | 31% |
| **36** |  |  | 30% | 29% | 32% | 31% | 31% | 31% | 28% |
| **48** |  |  | 29% | 32% | 32% | 30% | 30% | 30% | 28% |
| **72** |  |  |  |  | 31% | 31% | 33% | 33% | 30% |

**Max drawdown**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 90% | 88% | 87% | 87% | 79% | 73% | 61% | 58% | 61% |
| **6** | 93% | 87% | 84% | 81% | 80% | 63% | 62% | 54% | 48% |
| **9** | 89% | 84% | 76% | 73% | 69% | 60% | 52% | 52% | 54% |
| **12** | 84% | 80% | 76% | 68% | 69% | 54% | 56% | 55% | 55% |
| **18** | 82% | 82% | 64% | 58% | 49% | 44% | 54% | 54% | 53% |
| **24** |  | 81% | 54% | 47% | 50% | 47% | 39% | 40% | 51% |
| **36** |  |  | 45% | 44% | 37% | 31% | 41% | 39% | 52% |
| **48** |  |  | 45% | 39% | 36% | 34% | 52% | 43% | 40% |
| **72** |  |  |  |  | 35% | 47% | 39% | 42% | 41% |

**Thirds (total return in each third of the period)**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -48% -44% -65% | -41% -41% -61% | -49% -45% -47% | -29% -50% -59% | -12% -34% -52% | -18% -30% -37% | -26% -27% -15% | -10% -34% +4% | -32% -11% -31% |
| **6** | -53% -47% -69% | -47% -44% -47% | -45% -42% -45% | -11% -44% -50% | -11% -38% -50% | -8% -29% -28% | -17% -29% -16% | +17% -33% +1% | -21% -5% -16% |
| **9** | -37% -47% -59% | -43% -42% -43% | -25% -37% -40% | -17% -33% -42% | -6% -40% -26% | -6% -39% -16% | +0% -28% -8% | +15% -27% -1% | -6% -4% -29% |
| **12** | -40% -29% -59% | -30% -40% -43% | -12% -39% -43% | +25% -38% -30% | +2% -44% -19% | -9% -28% -12% | +15% -35% -12% | +15% -15% -27% | -7% -2% -31% |
| **18** | -37% -36% -50% | -34% -34% -48% | -7% -20% -33% | +20% -24% -24% | +17% -25% -15% | +17% -10% -6% | +8% -24% -9% | +23% +16% -30% | +4% +3% -33% |
| **24** |  | -18% -44% -48% | +20% -15% -23% | +6% -14% -15% | +12% -18% -14% | +12% -17% -10% | +17% +11% -19% | +25% +39% -23% | +14% +3% -33% |
| **36** |  |  | +17% -1% -16% | +9% -10% -19% | +8% +9% -1% | +7% -3% -3% | +12% +32% -25% | +18% +29% -17% | +12% -10% -35% |
| **48** |  |  | +6% -11% -12% | +9% -1% -12% | -5% +7% -4% | +2% +11% -12% | +3% +42% -42% | +29% +14% -28% | -2% -2% -26% |
| **72** |  |  |  |  | -0% +12% -5% | +6% +21% -35% | +19% +39% -27% | +22% +19% -23% | +0% +6% -29% |

**Plateau map: P3 = positive mean, >=70% of neighbours positive, 3/3 thirds positive; P2 = same with 2/3 thirds; + / - = sign only; s = stress total > 0; n/3 = thirds positive**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 1/3 | - 0/3 |
| **6** | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 2/3 | - 0/3 |
| **9** | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 1/3 | - 1/3 | - 0/3 |
| **12** | - 0/3 | - 0/3 | - 0/3 | - 1/3 | - 1/3 | - 0/3 | - 1/3 | - 1/3 | - 0/3 |
| **18** | - 0/3 | - 0/3 | - 0/3 | - 1/3 | - 1/3 | + 1/3 | - 1/3 | + 2/3 | - 2/3 |
| **24** |  | - 0/3 | - 1/3 | - 1/3 | - 1/3 | - 1/3 | P2 2/3 | + 2/3 | - 2/3 |
| **36** |  |  | + 1/3 | - 1/3 | + 2/3 | + 1/3 | P2 2/3 | + 2/3 | - 1/3 |
| **48** |  |  | - 1/3 | + 1/3 | + 1/3 | P2 2/3 | - 2/3 | + 2/3 | - 0/3 |
| **72** |  |  |  |  | + 1/3 | - 2/3 | + 2/3 | + 2/3 | - 2/3 |

### SHORT 

**11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -2.9% | -1.9% | -1.9% | -0.6% | -1.9% | -0.9% | -0.2% | +1.1% | +1.1% |
| **6** | -2.7% | -0.5% | -1.2% | -1.3% | -1.8% | +0.4% | +1.1% | +0.6% | +0.9% |
| **9** | -1.9% | -0.5% | -1.4% | -0.7% | -1.4% | +0.6% | +0.3% | +1.4% | +0.7% |
| **12** | -0.9% | -1.2% | -1.9% | -0.6% | -1.5% | +0.5% | +1.4% | +1.3% | +1.1% |
| **18** | -0.6% | -0.2% | -0.8% | -0.3% | -0.2% | +0.0% | +0.5% | -0.1% | +0.2% |
| **24** |  | -1.4% | -0.4% | -0.7% | +1.1% | +1.1% | +0.4% | +0.1% | +0.3% |
| **36** |  |  | +0.4% | -0.7% | -0.3% | +0.5% | -1.1% | -0.1% | -0.6% |
| **48** |  |  | -0.9% | -1.1% | -0.1% | -0.4% | +0.4% | -0.0% | -1.4% |
| **72** |  |  |  |  | -0.1% | -0.8% | -0.0% | -0.3% | -1.3% |

**11-day window median**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -3.6% | -3.3% | -2.2% | -2.1% | -3.0% | -2.1% | -1.5% | +0.0% | +0.0% |
| **6** | -4.0% | -1.7% | -1.3% | -2.8% | -2.9% | -1.6% | -0.6% | -0.5% | -0.4% |
| **9** | -3.2% | -1.0% | -1.9% | -1.5% | -1.6% | -0.8% | -0.7% | -0.1% | -0.1% |
| **12** | -1.8% | -1.4% | -1.8% | -0.9% | -2.2% | -0.1% | +0.3% | +0.4% | -0.1% |
| **18** | -2.5% | -2.2% | -1.2% | -1.4% | -1.1% | -0.8% | -0.4% | -1.3% | -0.9% |
| **24** |  | -0.9% | -1.5% | -1.8% | +0.3% | -0.4% | -0.6% | -1.0% | -0.3% |
| **36** |  |  | -0.6% | -0.9% | -0.5% | -1.1% | -2.3% | -1.3% | -1.4% |
| **48** |  |  | -1.5% | -1.4% | -1.5% | -2.1% | -0.4% | -0.9% | -1.3% |
| **72** |  |  |  |  | -0.9% | -1.5% | -1.3% | -0.9% | -1.7% |

**Total return (default costs)**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -62% | -49% | -49% | -30% | -47% | -28% | -16% | +20% | +20% |
| **6** | -59% | -27% | -35% | -38% | -43% | +2% | +18% | +8% | +12% |
| **9** | -47% | -22% | -34% | -27% | -35% | +5% | -2% | +32% | +9% |
| **12** | -35% | -32% | -42% | -22% | -36% | +10% | +29% | +30% | +20% |
| **18** | -23% | -17% | -27% | -19% | -10% | -6% | +4% | -9% | -3% |
| **24** |  | -34% | -21% | -23% | +24% | +21% | +5% | -8% | -0% |
| **36** |  |  | +1% | -22% | -14% | +4% | -30% | -11% | -16% |
| **48** |  |  | -27% | -29% | -10% | -17% | +2% | -6% | -30% |
| **72** |  |  |  |  | -8% | -24% | -8% | -10% | -29% |

**Total return (stress costs)**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -89% | -84% | -83% | -74% | -80% | -68% | -62% | -38% | -28% |
| **6** | -88% | -74% | -75% | -75% | -75% | -51% | -41% | -40% | -29% |
| **9** | -82% | -69% | -72% | -67% | -69% | -45% | -46% | -21% | -27% |
| **12** | -76% | -72% | -73% | -63% | -68% | -40% | -26% | -20% | -17% |
| **18** | -69% | -62% | -65% | -58% | -51% | -46% | -36% | -42% | -31% |
| **24** |  | -69% | -60% | -59% | -27% | -27% | -33% | -40% | -27% |
| **36** |  |  | -45% | -55% | -48% | -33% | -54% | -38% | -37% |
| **48** |  |  | -59% | -58% | -43% | -46% | -31% | -33% | -46% |
| **72** |  |  |  |  | -39% | -50% | -36% | -34% | -44% |

**Trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 1770 | 1545 | 1433 | 1345 | 1260 | 1092 | 1020 | 879 | 688 |
| **6** | 1609 | 1350 | 1253 | 1191 | 1094 | 948 | 882 | 766 | 602 |
| **9** | 1394 | 1195 | 1077 | 1010 | 962 | 836 | 757 | 667 | 535 |
| **12** | 1254 | 1105 | 985 | 941 | 888 | 750 | 686 | 613 | 484 |
| **18** | 1151 | 1009 | 912 | 843 | 759 | 676 | 615 | 539 | 445 |
| **24** |  | 936 | 851 | 797 | 669 | 626 | 569 | 502 | 406 |
| **36** |  |  | 757 | 678 | 621 | 559 | 533 | 468 | 375 |
| **48** |  |  | 700 | 648 | 565 | 511 | 478 | 435 | 339 |
| **72** |  |  |  |  | 516 | 479 | 458 | 384 | 300 |

**Win rate**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 25% | 27% | 27% | 27% | 27% | 28% | 29% | 31% | 32% |
| **6** | 26% | 29% | 30% | 29% | 29% | 31% | 32% | 33% | 32% |
| **9** | 28% | 31% | 32% | 31% | 31% | 32% | 33% | 35% | 33% |
| **12** | 30% | 32% | 34% | 31% | 30% | 33% | 35% | 37% | 35% |
| **18** | 32% | 34% | 32% | 33% | 33% | 33% | 34% | 35% | 35% |
| **24** |  | 34% | 33% | 33% | 37% | 35% | 36% | 35% | 36% |
| **36** |  |  | 35% | 34% | 35% | 35% | 33% | 36% | 34% |
| **48** |  |  | 33% | 34% | 34% | 35% | 36% | 35% | 33% |
| **72** |  |  |  |  | 36% | 34% | 36% | 34% | 31% |

**Max drawdown**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 71% | 65% | 62% | 50% | 57% | 46% | 47% | 33% | 29% |
| **6** | 70% | 55% | 55% | 55% | 55% | 37% | 36% | 25% | 33% |
| **9** | 63% | 54% | 52% | 51% | 50% | 35% | 30% | 20% | 33% |
| **12** | 53% | 55% | 54% | 46% | 52% | 26% | 28% | 29% | 23% |
| **18** | 47% | 44% | 46% | 41% | 35% | 28% | 32% | 32% | 25% |
| **24** |  | 46% | 39% | 43% | 24% | 25% | 26% | 32% | 18% |
| **36** |  |  | 33% | 41% | 29% | 24% | 41% | 30% | 23% |
| **48** |  |  | 38% | 38% | 29% | 29% | 25% | 21% | 32% |
| **72** |  |  |  |  | 25% | 40% | 24% | 28% | 32% |

**Thirds (total return in each third of the period)**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -50% -19% -5% | -42% -3% -9% | -37% -9% -12% | -33% +5% -1% | -26% -11% -19% | -21% +2% -10% | -26% +12% +1% | -8% +19% +9% | -17% +25% +16% |
| **6** | -51% -10% -8% | -35% +3% +10% | -30% -10% +3% | -33% -2% -6% | -27% -8% -15% | -3% +8% -3% | -12% +34% -1% | -4% +7% +5% | -21% +24% +15% |
| **9** | -39% -11% -3% | -22% -6% +6% | -16% -20% -2% | -18% -15% +5% | -18% -13% -9% | -2% +10% -3% | -8% +18% -10% | +0% +8% +21% | -19% +15% +17% |
| **12** | -27% -15% +4% | -19% -18% +3% | -12% -24% -14% | -17% -10% +5% | -20% -16% -4% | +4% +12% -6% | +18% +24% -12% | +6% -1% +24% | -12% +26% +9% |
| **18** | -17% -2% -5% | -15% -4% +2% | -1% -13% -15% | -17% +9% -10% | -1% +6% -15% | -0% +6% -11% | +17% +10% -19% | -7% -8% +6% | -10% +16% -7% |
| **24** |  | -9% -13% -18% | -16% +12% -16% | -17% +10% -16% | +11% +22% -8% | +4% +16% +1% | +13% +16% -19% | -8% +2% -2% | -9% +28% -14% |
| **36** |  |  | -9% +20% -8% | -14% -4% -6% | -4% +3% -13% | +10% +14% -16% | -8% -10% -16% | -7% +3% -6% | -17% +15% -12% |
| **48** |  |  | -10% -5% -15% | -14% +3% -20% | -5% +8% -13% | -0% +2% -19% | +2% +13% -12% | -2% +7% -10% | -16% -2% -15% |
| **72** |  |  |  |  | -6% +11% -12% | -15% +5% -16% | -8% +10% -9% | -12% +8% -6% | -12% -5% -15% |

**Plateau map: P3 = positive mean, >=70% of neighbours positive, 3/3 thirds positive; P2 = same with 2/3 thirds; + / - = sign only; s = stress total > 0; n/3 = thirds positive**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | - 0/3 | - 0/3 | - 0/3 | - 1/3 | - 0/3 | - 1/3 | - 2/3 | P2 2/3 | P2 2/3 |
| **6** | - 0/3 | - 2/3 | - 1/3 | - 0/3 | - 0/3 | + 1/3 | + 1/3 | P2 2/3 | P2 2/3 |
| **9** | - 0/3 | - 1/3 | - 0/3 | - 1/3 | - 0/3 | + 1/3 | + 1/3 | P3 3/3 | P2 2/3 |
| **12** | - 1/3 | - 1/3 | - 0/3 | - 1/3 | - 0/3 | + 2/3 | P2 2/3 | P2 2/3 | P2 2/3 |
| **18** | - 0/3 | - 1/3 | - 0/3 | - 1/3 | - 1/3 | + 1/3 | P2 2/3 | - 1/3 | + 1/3 |
| **24** |  | - 0/3 | - 1/3 | - 1/3 | + 2/3 | + 3/3 | + 2/3 | + 1/3 | + 1/3 |
| **36** |  |  | + 1/3 | - 0/3 | - 1/3 | + 2/3 | - 0/3 | - 1/3 | - 1/3 |
| **48** |  |  | - 0/3 | - 1/3 | - 1/3 | - 1/3 | + 2/3 | - 1/3 | - 0/3 |
| **72** |  |  |  |  | - 1/3 | - 1/3 | - 1/3 | - 1/3 | - 0/3 |

### BOTH 

**11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -5.1% | -3.3% | -3.7% | -3.2% | -2.6% | -0.8% | +0.9% | +1.9% | -1.2% |
| **6** | -3.7% | -3.9% | -6.0% | -4.0% | -1.1% | +1.2% | +1.4% | +0.7% | +0.7% |
| **9** | -5.0% | -5.5% | -2.9% | -0.5% | +0.8% | +0.3% | +0.7% | +2.1% | +0.5% |
| **12** | -4.8% | -4.7% | -3.9% | +1.0% | -3.1% | +1.5% | +1.2% | +2.0% | +0.2% |
| **18** | -4.0% | -5.1% | -1.5% | +2.4% | -1.3% | +1.6% | +1.9% | +0.8% | -0.0% |
| **24** |  | -3.9% | -0.0% | -1.6% | +1.4% | +2.1% | +2.5% | +2.0% | -0.0% |
| **36** |  |  | +1.2% | -0.6% | +1.9% | +2.1% | -0.1% | +1.4% | -1.7% |
| **48** |  |  | -0.8% | +0.2% | +0.8% | +0.2% | +1.5% | +0.2% | -1.7% |
| **72** |  |  |  |  | +1.6% | +0.7% | +1.0% | +0.4% | -2.2% |

**11-day window median**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -6.3% | -4.0% | -3.8% | -3.1% | -2.0% | -1.3% | -0.6% | +0.9% | -1.5% |
| **6** | -4.1% | -4.2% | -6.7% | -4.6% | -1.2% | +0.5% | -0.1% | -0.5% | -0.1% |
| **9** | -5.2% | -6.2% | -4.7% | -2.0% | +0.1% | -0.6% | -0.3% | +0.6% | +0.0% |
| **12** | -7.3% | -4.8% | -5.3% | +1.6% | -3.0% | -0.6% | +1.9% | +2.0% | +0.0% |
| **18** | -4.5% | -7.5% | -3.0% | +0.5% | -1.3% | +0.9% | +0.7% | +1.7% | +0.0% |
| **24** |  | -4.1% | -1.5% | -4.1% | +0.4% | +1.9% | +1.7% | +2.2% | +0.0% |
| **36** |  |  | +0.5% | -1.2% | +1.3% | +1.6% | -0.7% | +0.7% | -2.3% |
| **48** |  |  | -1.7% | -0.2% | -0.1% | +0.4% | -0.2% | -0.5% | -1.7% |
| **72** |  |  |  |  | +1.2% | +0.6% | +1.3% | -0.1% | -2.5% |

**Total return (default costs)**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -77% | -62% | -65% | -61% | -56% | -31% | +8% | +46% | -36% |
| **6** | -67% | -67% | -81% | -66% | -33% | +19% | +16% | +4% | -7% |
| **9** | -77% | -77% | -56% | -28% | +4% | -13% | -3% | +48% | -6% |
| **12** | -76% | -72% | -68% | +12% | -60% | +25% | +5% | +45% | -11% |
| **18** | -67% | -76% | -38% | +46% | -41% | +21% | +34% | -2% | -21% |
| **24** |  | -67% | -14% | -44% | +17% | +37% | +58% | +34% | -18% |
| **36** |  |  | +16% | -28% | +27% | +43% | -18% | +13% | -42% |
| **48** |  |  | -35% | -15% | +1% | -10% | +20% | -10% | -41% |
| **72** |  |  |  |  | +28% | -0% | +5% | -2% | -47% |

**Total return (stress costs)**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -94% | -90% | -90% | -89% | -87% | -78% | -62% | -42% | -71% |
| **6** | -91% | -90% | -95% | -90% | -80% | -58% | -60% | -59% | -55% |
| **9** | -94% | -93% | -86% | -77% | -67% | -70% | -65% | -38% | -53% |
| **12** | -93% | -91% | -90% | -64% | -86% | -53% | -58% | -37% | -54% |
| **18** | -90% | -93% | -79% | -48% | -78% | -52% | -43% | -56% | -59% |
| **24** |  | -90% | -70% | -80% | -54% | -44% | -31% | -36% | -55% |
| **36** |  |  | -58% | -75% | -48% | -37% | -62% | -44% | -67% |
| **48** |  |  | -77% | -66% | -57% | -58% | -42% | -54% | -65% |
| **72** |  |  |  |  | -41% | -54% | -47% | -44% | -66% |

**Trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 1782 | 1645 | 1632 | 1632 | 1570 | 1472 | 1382 | 1221 | 1087 |
| **6** | 1672 | 1573 | 1600 | 1571 | 1457 | 1336 | 1296 | 1181 | 989 |
| **9** | 1617 | 1556 | 1472 | 1458 | 1379 | 1315 | 1230 | 1107 | 922 |
| **12** | 1611 | 1517 | 1469 | 1396 | 1382 | 1229 | 1169 | 1056 | 886 |
| **18** | 1545 | 1466 | 1354 | 1304 | 1284 | 1161 | 1101 | 994 | 821 |
| **24** |  | 1418 | 1342 | 1267 | 1180 | 1112 | 1037 | 917 | 763 |
| **36** |  |  | 1234 | 1189 | 1115 | 1021 | 984 | 878 | 695 |
| **48** |  |  | 1205 | 1130 | 1041 | 967 | 904 | 822 | 622 |
| **72** |  |  |  |  | 964 | 890 | 862 | 706 | 556 |

**Win rate**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 30% | 30% | 30% | 30% | 29% | 30% | 31% | 32% | 32% |
| **6** | 30% | 30% | 30% | 30% | 32% | 33% | 32% | 33% | 32% |
| **9** | 31% | 30% | 33% | 33% | 32% | 32% | 32% | 34% | 33% |
| **12** | 30% | 31% | 32% | 33% | 29% | 33% | 34% | 35% | 33% |
| **18** | 31% | 32% | 33% | 34% | 31% | 33% | 34% | 34% | 34% |
| **24** |  | 33% | 33% | 33% | 34% | 34% | 36% | 35% | 34% |
| **36** |  |  | 34% | 34% | 34% | 34% | 32% | 34% | 30% |
| **48** |  |  | 32% | 33% | 34% | 33% | 34% | 33% | 32% |
| **72** |  |  |  |  | 36% | 34% | 35% | 34% | 31% |

**Max drawdown**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 84% | 75% | 75% | 75% | 71% | 60% | 45% | 49% | 51% |
| **6** | 78% | 80% | 87% | 80% | 65% | 47% | 47% | 59% | 47% |
| **9** | 88% | 85% | 72% | 62% | 57% | 59% | 52% | 49% | 48% |
| **12** | 84% | 81% | 81% | 57% | 74% | 55% | 55% | 50% | 49% |
| **18** | 79% | 87% | 65% | 48% | 64% | 50% | 50% | 52% | 56% |
| **24** |  | 81% | 56% | 68% | 54% | 43% | 42% | 42% | 53% |
| **36** |  |  | 50% | 54% | 44% | 33% | 54% | 45% | 56% |
| **48** |  |  | 50% | 44% | 36% | 36% | 51% | 55% | 49% |
| **72** |  |  |  |  | 31% | 44% | 42% | 50% | 55% |

**Thirds (total return in each third of the period)**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -45% -30% -42% | -17% -19% -44% | +1% -45% -38% | -15% -15% -46% | -2% -35% -31% | -7% -7% -21% | +17% -3% -5% | +38% -17% +28% | -19% -2% -18% |
| **6** | -28% -38% -25% | -31% -42% -17% | -34% -41% -52% | -14% -45% -29% | +10% -33% -8% | +30% +6% -14% | +17% +10% -9% | +36% -28% +6% | -21% +22% -3% |
| **9** | -28% -51% -34% | -17% -50% -44% | -3% -12% -48% | +28% -14% -34% | +28% -21% +3% | +20% -24% -4% | +12% -3% -10% | +43% -3% +6% | -8% +25% -18% |
| **12** | -41% -31% -42% | -20% -37% -45% | +17% -31% -60% | +42% -20% -1% | -17% -35% -25% | +38% -8% -2% | +33% -11% -11% | +41% +5% -2% | -8% +21% -20% |
| **18** | -12% -48% -29% | -16% -40% -53% | +10% -10% -38% | +44% +23% -18% | +10% -4% -44% | +27% +8% -11% | +58% -0% -15% | +27% +12% -31% | -9% +29% -33% |
| **24** |  | +6% -28% -57% | +9% +11% -29% | +22% -8% -50% | +42% -6% -12% | +33% +18% -13% | +30% +37% -12% | +15% +58% -26% | +10% +22% -39% |
| **36** |  |  | +30% +31% -32% | +8% -8% -28% | +13% +32% -15% | +32% +24% -13% | +2% +18% -32% | +13% +33% -24% | -10% +9% -41% |
| **48** |  |  | -10% -2% -27% | -15% +15% -14% | -10% +21% -8% | +9% +6% -23% | +22% +71% -42% | +23% +22% -40% | -10% +4% -37% |
| **72** |  |  |  |  | -3% +40% -6% | +5% +41% -33% | +3% +47% -30% | +10% +35% -34% | -11% -1% -39% |

**P&L by side, $k (long / short)**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -51 / -26 | -57 / -5 | -58 / -7 | -52 / -10 | -30 / -26 | -26 / -5 | -7 / +13 | -4 / +47 | -38 / +2 |
| **6** | -53 / -14 | -59 / -8 | -64 / -18 | -33 / -34 | -15 / -19 | -22 / +40 | -9 / +26 | -13 / +15 | -14 / +7 |
| **9** | -56 / -21 | -47 / -31 | -53 / -4 | -15 / -13 | -0 / +3 | -37 / +23 | -8 / +5 | -6 / +52 | -23 / +18 |
| **12** | -57 / -19 | -49 / -24 | -37 / -31 | +21 / -10 | -36 / -24 | -12 / +36 | -29 / +35 | -11 / +54 | -28 / +18 |
| **18** | -49 / -19 | -49 / -28 | -31 / -8 | +30 / +14 | -37 / -3 | +27 / -6 | +5 / +27 | +14 / -16 | -13 / -9 |
| **24** |  | -35 / -32 | -8 / -7 | -20 / -23 | -2 / +19 | +7 / +28 | +42 / +14 | +42 / -9 | -18 / -0 |
| **36** |  |  | +1 / +15 | -16 / -12 | +28 / -1 | +44 / -3 | +16 / -35 | +26 / -13 | -31 / -12 |
| **48** |  |  | -15 / -21 | -1 / -14 | +6 / -6 | +5 / -17 | +16 / +3 | -4 / -7 | -14 / -27 |
| **72** |  |  |  |  | +22 / +3 | +10 / -10 | +9 / -3 | -3 / -1 | -19 / -29 |

**Plateau map: P3 = positive mean, >=70% of neighbours positive, 3/3 thirds positive; P2 = same with 2/3 thirds; + / - = sign only; s = stress total > 0; n/3 = thirds positive**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | - 0/3 | - 0/3 | - 1/3 | - 0/3 | - 0/3 | - 0/3 | + 1/3 | P2 2/3 | - 0/3 |
| **6** | - 0/3 | - 0/3 | - 0/3 | - 0/3 | - 1/3 | + 2/3 | P2 2/3 | P2 2/3 | + 1/3 |
| **9** | - 0/3 | - 0/3 | - 0/3 | - 1/3 | + 2/3 | + 1/3 | + 1/3 | P2 2/3 | + 1/3 |
| **12** | - 0/3 | - 0/3 | - 1/3 | + 1/3 | - 0/3 | + 1/3 | + 1/3 | P2 2/3 | + 1/3 |
| **18** | - 0/3 | - 0/3 | - 1/3 | + 2/3 | - 1/3 | P2 2/3 | + 1/3 | P2 2/3 | - 1/3 |
| **24** |  | - 1/3 | - 2/3 | - 1/3 | + 1/3 | P2 2/3 | P2 2/3 | + 2/3 | - 2/3 |
| **36** |  |  | + 2/3 | - 1/3 | P2 2/3 | P2 2/3 | - 2/3 | + 2/3 | - 1/3 |
| **48** |  |  | - 0/3 | + 1/3 | + 1/3 | P2 2/3 | P2 2/3 | + 2/3 | - 1/3 |
| **72** |  |  |  |  | + 1/3 | P2 2/3 | P2 2/3 | + 2/3 | - 0/3 |

## B. Does the map survive other risk settings? (1,512 variants)

**Base: 4 slots, trail 3 ATR**

| side | cells | mean>0 | median>0 | total>0 | stress>0 | best stress | thirds 3/3 | thirds >=2/3 | P2 plateau cells | avg trades | avg win | rank corr. with base map |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long | 72 | 16 | 3 | 10 | 0 | -14% | 0 | 16 | 3 | 928 | 28% | - |
| short | 72 | 25 | 4 | 20 | 0 | -17% | 2 | 18 | 10 | 819 | 32% | - |
| both | 72 | 37 | 23 | 26 | 0 | -31% | 0 | 26 | 15 | 1218 | 32% | - |

| side | region | 11d mean | total | stress total | share of cells with mean>0 | thirds (avg) |
|---|---|---|---|---|---|---|
| long | fast corner (fast<=12, slow<=72) | -5.8% | -79% | -92% | 0% | -31% -41% -50% |
| long | middle (fast 18-72, slow 100-300) | +0.5% | +1% | -37% | 70% | +13% +10% -17% |
| long | fast lead, slow base (fast<=12, slow 150-480) | -1.7% | -41% | -69% | 0% | -6% -24% -17% |
| long | slow = 480 | -1.2% | -34% | -55% | 0% | -4% -2% -29% |
| short | fast corner (fast<=12, slow<=72) | -1.4% | -38% | -76% | 0% | -30% -10% -1% |
| short | middle (fast 18-72, slow 100-300) | +0.0% | -6% | -39% | 40% | -1% +7% -11% |
| short | fast lead, slow base (fast<=12, slow 150-480) | +0.7% | +11% | -37% | 88% | -8% +15% +4% |
| short | slow = 480 | +0.1% | -2% | -32% | 67% | -15% +16% -1% |
| both | fast corner (fast<=12, slow<=72) | -3.7% | -62% | -88% | 6% | -13% -33% -38% |
| both | middle (fast 18-72, slow 100-300) | +1.1% | +13% | -49% | 90% | +18% +26% -23% |
| both | fast lead, slow base (fast<=12, slow 150-480) | +0.8% | +7% | -57% | 88% | +16% -1% -6% |
| both | slow = 480 | -0.6% | -25% | -61% | 33% | -10% +14% -28% |

**8 slots, trail 3 ATR**

| side | cells | mean>0 | median>0 | total>0 | stress>0 | best stress | thirds 3/3 | thirds >=2/3 | P2 plateau cells | avg trades | avg win | rank corr. with base map |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long | 72 | 12 | 1 | 5 | 0 | -22% | 0 | 10 | 1 | 1432 | 28% | +0.95 |
| short | 72 | 18 | 2 | 9 | 0 | -21% | 2 | 16 | 7 | 1313 | 33% | +0.80 |
| both | 72 | 18 | 16 | 4 | 0 | -41% | 0 | 15 | 1 | 2105 | 32% | +0.85 |

| side | region | 11d mean | total | stress total | share of cells with mean>0 | thirds (avg) |
|---|---|---|---|---|---|---|
| long | fast corner (fast<=12, slow<=72) | -4.8% | -72% | -88% | 0% | -20% -38% -45% |
| long | middle (fast 18-72, slow 100-300) | +0.0% | -7% | -33% | 60% | +12% -3% -14% |
| long | fast lead, slow base (fast<=12, slow 150-480) | -1.3% | -32% | -58% | 0% | +2% -21% -15% |
| long | slow = 480 | -0.6% | -20% | -38% | 0% | +4% -4% -20% |
| short | fast corner (fast<=12, slow<=72) | -1.1% | -30% | -69% | 0% | -19% -11% -3% |
| short | middle (fast 18-72, slow 100-300) | -0.3% | -11% | -36% | 15% | -2% -0% -9% |
| short | fast lead, slow base (fast<=12, slow 150-480) | +0.3% | +3% | -34% | 88% | -2% +10% -4% |
| short | slow = 480 | -0.0% | -4% | -26% | 44% | -9% +11% -5% |
| both | fast corner (fast<=12, slow<=72) | -3.4% | -58% | -87% | 0% | -6% -31% -36% |
| both | middle (fast 18-72, slow 100-300) | -0.1% | -11% | -52% | 45% | +11% +0% -19% |
| both | fast lead, slow base (fast<=12, slow 150-480) | -0.1% | -10% | -57% | 50% | +15% -10% -11% |
| both | slow = 480 | -0.4% | -17% | -48% | 22% | +1% +5% -22% |

**4 slots, trail 2 ATR**

| side | cells | mean>0 | median>0 | total>0 | stress>0 | best stress | thirds 3/3 | thirds >=2/3 | P2 plateau cells | avg trades | avg win | rank corr. with base map |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long | 72 | 0 | 0 | 0 | 0 | -55% | 0 | 0 | 0 | 1386 | 29% | +0.88 |
| short | 72 | 0 | 0 | 0 | 0 | -44% | 0 | 0 | 0 | 1189 | 31% | +0.79 |
| both | 72 | 0 | 0 | 0 | 0 | -77% | 0 | 0 | 0 | 2043 | 31% | +0.65 |

| side | region | 11d mean | total | stress total | share of cells with mean>0 | thirds (avg) |
|---|---|---|---|---|---|---|
| long | fast corner (fast<=12, slow<=72) | -8.9% | -90% | -98% | 0% | -49% -56% -60% |
| long | middle (fast 18-72, slow 100-300) | -1.9% | -44% | -73% | 0% | -6% -18% -28% |
| long | fast lead, slow base (fast<=12, slow 150-480) | -3.7% | -63% | -86% | 0% | -20% -37% -27% |
| long | slow = 480 | -2.1% | -46% | -69% | 0% | -7% -15% -30% |
| short | fast corner (fast<=12, slow<=72) | -4.4% | -71% | -93% | 0% | -46% -26% -29% |
| short | middle (fast 18-72, slow 100-300) | -1.8% | -39% | -68% | 0% | -15% -4% -25% |
| short | fast lead, slow base (fast<=12, slow 150-480) | -1.7% | -39% | -73% | 0% | -25% -2% -17% |
| short | slow = 480 | -1.3% | -31% | -58% | 0% | -22% +2% -13% |
| both | fast corner (fast<=12, slow<=72) | -9.1% | -91% | -99% | 0% | -56% -50% -61% |
| both | middle (fast 18-72, slow 100-300) | -3.3% | -63% | -89% | 0% | -18% -17% -45% |
| both | fast lead, slow base (fast<=12, slow 150-480) | -3.8% | -66% | -92% | 0% | -27% -26% -35% |
| both | slow = 480 | -3.1% | -59% | -85% | 0% | -24% -12% -38% |

**4 slots, trail 4 ATR**

| side | cells | mean>0 | median>0 | total>0 | stress>0 | best stress | thirds 3/3 | thirds >=2/3 | P2 plateau cells | avg trades | avg win | rank corr. with base map |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long | 72 | 45 | 15 | 34 | 14 | +41% | 7 | 39 | 33 | 711 | 27% | +0.90 |
| short | 72 | 40 | 9 | 32 | 3 | +21% | 9 | 41 | 22 | 653 | 32% | +0.85 |
| both | 72 | 55 | 38 | 50 | 13 | +33% | 10 | 39 | 38 | 855 | 34% | +0.81 |

| side | region | 11d mean | total | stress total | share of cells with mean>0 | thirds (avg) |
|---|---|---|---|---|---|---|
| long | fast corner (fast<=12, slow<=72) | -2.6% | -57% | -80% | 6% | -11% +1% -52% |
| long | middle (fast 18-72, slow 100-300) | +2.3% | +50% | +5% | 100% | +26% +36% -10% |
| long | fast lead, slow base (fast<=12, slow 150-480) | +0.8% | +6% | -35% | 75% | -3% +28% -14% |
| long | slow = 480 | +0.1% | -9% | -32% | 67% | -6% +36% -29% |
| short | fast corner (fast<=12, slow<=72) | -1.2% | -35% | -69% | 6% | -37% -4% +6% |
| short | middle (fast 18-72, slow 100-300) | +0.6% | +6% | -25% | 80% | -4% +10% +1% |
| short | fast lead, slow base (fast<=12, slow 150-480) | +1.3% | +26% | -20% | 88% | -8% +22% +13% |
| short | slow = 480 | +0.6% | +10% | -18% | 67% | -17% +21% +9% |
| both | fast corner (fast<=12, slow<=72) | -1.2% | -33% | -70% | 25% | -15% +19% -35% |
| both | middle (fast 18-72, slow 100-300) | +2.9% | +74% | -1% | 100% | +16% +64% -8% |
| both | fast lead, slow base (fast<=12, slow 150-480) | +2.3% | +52% | -18% | 100% | +4% +53% -3% |
| both | slow = 480 | +1.0% | +16% | -27% | 78% | -14% +62% -18% |

**4 slots, trail 5 ATR**

| side | cells | mean>0 | median>0 | total>0 | stress>0 | best stress | thirds 3/3 | thirds >=2/3 | P2 plateau cells | avg trades | avg win | rank corr. with base map |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long | 72 | 43 | 7 | 33 | 8 | +67% | 2 | 29 | 23 | 603 | 26% | +0.81 |
| short | 72 | 47 | 24 | 40 | 17 | +29% | 7 | 40 | 34 | 563 | 32% | +0.80 |
| both | 72 | 60 | 43 | 53 | 31 | +105% | 10 | 37 | 31 | 661 | 33% | +0.73 |

| side | region | 11d mean | total | stress total | share of cells with mean>0 | thirds (avg) |
|---|---|---|---|---|---|---|
| long | fast corner (fast<=12, slow<=72) | -1.7% | -50% | -74% | 0% | -18% +22% -49% |
| long | middle (fast 18-72, slow 100-300) | +1.6% | +28% | -4% | 100% | +10% +34% -12% |
| long | fast lead, slow base (fast<=12, slow 150-480) | +0.8% | +3% | -31% | 81% | -10% +38% -16% |
| long | slow = 480 | +1.0% | +8% | -16% | 89% | -10% +73% -30% |
| short | fast corner (fast<=12, slow<=72) | -1.2% | -36% | -66% | 6% | -37% -5% +7% |
| short | middle (fast 18-72, slow 100-300) | +1.3% | +26% | -4% | 100% | -5% +25% +6% |
| short | fast lead, slow base (fast<=12, slow 150-480) | +1.5% | +31% | -10% | 94% | -11% +27% +16% |
| short | slow = 480 | +0.9% | +17% | -9% | 78% | -16% +30% +7% |
| both | fast corner (fast<=12, slow<=72) | -0.7% | -23% | -58% | 44% | -4% +18% -34% |
| both | middle (fast 18-72, slow 100-300) | +3.6% | +101% | +32% | 100% | -6% +96% +11% |
| both | fast lead, slow base (fast<=12, slow 150-480) | +3.7% | +107% | +32% | 100% | +2% +100% +4% |
| both | slow = 480 | +1.8% | +46% | +2% | 89% | -13% +121% -28% |

**4 slots, trail 6 ATR**

| side | cells | mean>0 | median>0 | total>0 | stress>0 | best stress | thirds 3/3 | thirds >=2/3 | P2 plateau cells | avg trades | avg win | rank corr. with base map |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long | 72 | 36 | 5 | 20 | 5 | +49% | 1 | 18 | 12 | 546 | 25% | +0.78 |
| short | 72 | 54 | 42 | 41 | 27 | +68% | 16 | 43 | 38 | 507 | 32% | +0.77 |
| both | 72 | 58 | 44 | 53 | 39 | +101% | 7 | 36 | 31 | 555 | 33% | +0.63 |

| side | region | 11d mean | total | stress total | share of cells with mean>0 | thirds (avg) |
|---|---|---|---|---|---|---|
| long | fast corner (fast<=12, slow<=72) | -2.1% | -54% | -75% | 6% | -14% +4% -47% |
| long | middle (fast 18-72, slow 100-300) | +1.2% | +13% | -11% | 95% | +5% +24% -11% |
| long | fast lead, slow base (fast<=12, slow 150-480) | -0.3% | -19% | -43% | 50% | -17% +15% -15% |
| long | slow = 480 | +1.0% | +4% | -16% | 100% | -13% +67% -29% |
| short | fast corner (fast<=12, slow<=72) | -0.6% | -27% | -59% | 31% | -37% -2% +18% |
| short | middle (fast 18-72, slow 100-300) | +2.0% | +49% | +18% | 100% | +2% +35% +7% |
| short | fast lead, slow base (fast<=12, slow 150-480) | +2.3% | +60% | +16% | 100% | -8% +43% +21% |
| short | slow = 480 | +1.8% | +43% | +16% | 100% | -14% +44% +15% |
| both | fast corner (fast<=12, slow<=72) | -0.4% | -16% | -50% | 31% | +1% +12% -26% |
| both | middle (fast 18-72, slow 100-300) | +3.3% | +89% | +37% | 100% | +2% +82% +3% |
| both | fast lead, slow base (fast<=12, slow 150-480) | +2.9% | +70% | +18% | 100% | +0% +87% -8% |
| both | slow = 480 | +3.0% | +76% | +33% | 100% | -14% +156% -20% |

**4 slots, trail 8 ATR**

| side | cells | mean>0 | median>0 | total>0 | stress>0 | best stress | thirds 3/3 | thirds >=2/3 | P2 plateau cells | avg trades | avg win | rank corr. with base map |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long | 72 | 36 | 4 | 24 | 13 | +64% | 0 | 24 | 20 | 486 | 23% | +0.76 |
| short | 72 | 47 | 40 | 39 | 27 | +68% | 10 | 43 | 35 | 449 | 30% | +0.71 |
| both | 72 | 46 | 34 | 39 | 25 | +67% | 3 | 29 | 17 | 463 | 30% | +0.56 |

| side | region | 11d mean | total | stress total | share of cells with mean>0 | thirds (avg) |
|---|---|---|---|---|---|---|
| long | fast corner (fast<=12, slow<=72) | -2.1% | -56% | -75% | 0% | -11% -0% -49% |
| long | middle (fast 18-72, slow 100-300) | +1.6% | +25% | +3% | 90% | +28% +15% -12% |
| long | fast lead, slow base (fast<=12, slow 150-480) | +0.3% | -9% | -31% | 69% | +2% +12% -19% |
| long | slow = 480 | +1.0% | +2% | -14% | 100% | +2% +55% -34% |
| short | fast corner (fast<=12, slow<=72) | -0.7% | -26% | -55% | 31% | -39% -7% +28% |
| short | middle (fast 18-72, slow 100-300) | +1.6% | +36% | +13% | 90% | -4% +27% +10% |
| short | fast lead, slow base (fast<=12, slow 150-480) | +1.9% | +47% | +13% | 94% | -12% +33% +24% |
| short | slow = 480 | +1.7% | +42% | +20% | 89% | -15% +40% +19% |
| both | fast corner (fast<=12, slow<=72) | -1.1% | -31% | -57% | 12% | -5% -2% -25% |
| both | middle (fast 18-72, slow 100-300) | +1.9% | +36% | +7% | 100% | -3% +56% -9% |
| both | fast lead, slow base (fast<=12, slow 150-480) | +1.6% | +36% | +5% | 81% | +3% +49% -12% |
| both | slow = 480 | +2.5% | +55% | +26% | 100% | +0% +97% -22% |

**4 slots, no stop (exit on opposite cross only)**

| side | cells | mean>0 | median>0 | total>0 | stress>0 | best stress | thirds 3/3 | thirds >=2/3 | P2 plateau cells | avg trades | avg win | rank corr. with base map |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long | 72 | 34 | 1 | 24 | 23 | +228% | 0 | 23 | 17 | 426 | 20% | +0.72 |
| short | 72 | 54 | 40 | 45 | 30 | +83% | 6 | 52 | 43 | 376 | 27% | +0.60 |
| both | 72 | 34 | 10 | 18 | 9 | +273% | 4 | 18 | 3 | 368 | 27% | +0.02 |

| side | region | 11d mean | total | stress total | share of cells with mean>0 | thirds (avg) |
|---|---|---|---|---|---|---|
| long | fast corner (fast<=12, slow<=72) | -2.1% | -57% | -75% | 0% | -9% +0% -51% |
| long | middle (fast 18-72, slow 100-300) | +3.0% | +55% | +39% | 95% | +20% +69% -22% |
| long | fast lead, slow base (fast<=12, slow 150-480) | +0.9% | +11% | -6% | 44% | +10% +47% -29% |
| long | slow = 480 | +3.9% | +97% | +82% | 78% | +5% +193% -36% |
| short | fast corner (fast<=12, slow<=72) | -0.6% | -25% | -54% | 31% | -36% -9% +27% |
| short | middle (fast 18-72, slow 100-300) | +1.8% | +38% | +25% | 100% | -6% +23% +19% |
| short | fast lead, slow base (fast<=12, slow 150-480) | +1.5% | +31% | +11% | 100% | -15% +22% +24% |
| short | slow = 480 | +1.8% | +39% | +30% | 100% | -13% +32% +21% |
| both | fast corner (fast<=12, slow<=72) | -0.8% | -23% | -50% | 38% | -1% -6% -17% |
| both | middle (fast 18-72, slow 100-300) | -0.4% | -23% | -31% | 40% | -18% +2% -10% |
| both | fast lead, slow base (fast<=12, slow 150-480) | +0.2% | -10% | -22% | 62% | -0% +4% -12% |
| both | slow = 480 | +2.1% | +52% | +43% | 100% | +4% +47% +1% |

**long, trail 4 ATR: 11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -2.4% | -3.4% | -3.9% | -3.4% | +0.4% | +0.1% | +0.3% | -0.1% | -0.3% |
| **6** | -3.7% | -2.9% | -2.3% | -1.8% | -0.5% | -0.2% | +0.7% | +1.6% | +1.2% |
| **9** | -3.7% | -3.3% | -2.3% | -1.4% | -0.5% | -0.2% | +0.9% | +3.0% | +1.2% |
| **12** | -1.7% | -3.3% | -2.4% | +0.9% | -0.5% | +2.3% | +0.6% | +2.2% | +0.4% |
| **18** | -3.1% | -2.4% | +0.0% | +1.4% | +2.0% | +2.2% | +2.2% | +2.1% | +0.4% |
| **24** |  | -2.3% | +1.1% | +1.2% | +2.0% | +3.2% | +2.7% | +2.4% | +0.2% |
| **36** |  |  | +3.1% | +2.2% | +2.9% | +2.9% | +3.7% | +2.4% | -0.5% |
| **48** |  |  | +3.1% | +2.5% | +2.6% | +2.0% | +1.6% | +1.5% | -1.4% |
| **72** |  |  |  |  | +2.4% | +1.6% | +1.8% | +1.2% | +0.0% |

**long, trail 4 ATR: total return at stress costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -88% | -88% | -88% | -86% | -62% | -59% | -55% | -54% | -51% |
| **6** | -90% | -84% | -80% | -76% | -65% | -59% | -46% | -26% | -26% |
| **9** | -88% | -83% | -77% | -71% | -62% | -55% | -35% | +16% | -22% |
| **12** | -77% | -82% | -76% | -46% | -57% | -13% | -41% | +6% | -32% |
| **18** | -81% | -76% | -53% | -36% | -18% | -11% | -3% | -2% | -26% |
| **24** |  | -74% | -39% | -34% | -13% | +20% | +13% | +13% | -25% |
| **36** |  |  | +8% | -8% | +16% | +17% | +41% | +13% | -37% |
| **48** |  |  | +15% | -0% | +12% | -0% | -8% | -2% | -47% |
| **72** |  |  |  |  | +13% | -5% | +4% | -0% | -24% |

**long, trail 4 ATR: thirds**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -20% +33% -65% | -35% +24% -61% | -37% -11% -48% | -15% -5% -60% | +43% -6% -38% | +7% +15% -34% | -27% +41% -12% | -10% -6% -0% | -18% +34% -30% |
| **6** | -41% +15% -57% | -21% -4% -52% | -19% +20% -54% | +2% -6% -47% | +6% +1% -34% | -14% +19% -24% | -18% +17% +3% | +15% +12% -3% | -14% +76% -27% |
| **9** | -14% -6% -63% | -14% -15% -51% | -2% -9% -48% | -0% -8% -39% | +3% -3% -29% | -2% +1% -20% | -5% +17% -2% | +27% +46% -2% | -12% +64% -24% |
| **12** | +10% +17% -61% | -18% -7% -52% | -1% -11% -48% | +50% -8% -29% | +6% -11% -21% | +9% +22% +8% | +2% +1% -8% | +31% +47% -26% | -13% +45% -26% |
| **18** | -21% +6% -53% | -12% -1% -47% | +34% -10% -31% | +27% +21% -28% | +34% +8% -8% | +1% +37% -2% | +36% +13% -5% | +47% +30% -25% | +4% +30% -27% |
| **24** |  | +2% -24% -39% | +42% +3% -28% | +10% +18% -17% | +7% +13% +11% | +33% +33% +2% | +48% +43% -21% | +39% +36% -16% | +7% +26% -28% |
| **36** |  |  | +32% +41% -7% | +19% +22% -2% | +28% +23% +9% | +22% +31% +10% | +57% +64% -20% | +36% +33% -16% | +9% +13% -36% |
| **48** |  |  | +21% +24% +19% | +11% +37% -2% | +18% +30% +5% | +29% +23% -10% | +7% +72% -32% | +34% +13% -14% | -9% +9% -34% |
| **72** |  |  |  |  | +13% +42% -1% | +9% +70% -32% | +9% +60% -21% | +13% +40% -21% | -7% +29% -24% |

**long, trail 4 ATR: trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 1715 | 1423 | 1253 | 1189 | 1090 | 984 | 950 | 819 | 638 |
| **6** | 1493 | 1214 | 1088 | 1016 | 951 | 870 | 803 | 705 | 529 |
| **9** | 1270 | 1056 | 966 | 898 | 833 | 747 | 687 | 596 | 477 |
| **12** | 1108 | 965 | 843 | 797 | 741 | 660 | 616 | 545 | 429 |
| **18** | 981 | 845 | 751 | 716 | 633 | 575 | 541 | 474 | 379 |
| **24** |  | 783 | 694 | 615 | 555 | 531 | 500 | 419 | 326 |
| **36** |  |  | 585 | 547 | 519 | 471 | 447 | 390 | 294 |
| **48** |  |  | 547 | 518 | 459 | 449 | 399 | 356 | 263 |
| **72** |  |  |  |  | 418 | 378 | 355 | 286 | 225 |

**short, trail 4 ATR: 11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -2.8% | -1.8% | -2.1% | -1.2% | -0.3% | -0.3% | +0.8% | +2.0% | +1.4% |
| **6** | -2.7% | -0.9% | -0.8% | -1.1% | -0.4% | +1.3% | +0.9% | +1.6% | +1.3% |
| **9** | -0.9% | -0.9% | -0.3% | -0.2% | -0.1% | +1.6% | -0.0% | +2.8% | +1.7% |
| **12** | -1.8% | -1.2% | -0.2% | +0.4% | +0.0% | +1.1% | +1.2% | +1.7% | +1.2% |
| **18** | -1.3% | -0.6% | +0.4% | +0.4% | +0.8% | -0.2% | +1.1% | +0.7% | +0.7% |
| **24** |  | -1.7% | -0.5% | +0.7% | +2.0% | +0.9% | +0.7% | +0.5% | +1.0% |
| **36** |  |  | +0.5% | +0.9% | +0.4% | +0.7% | +0.2% | +0.1% | -0.1% |
| **48** |  |  | +0.4% | -0.2% | +0.5% | -0.2% | +1.2% | +1.1% | -1.0% |
| **72** |  |  |  |  | +0.0% | -0.0% | +0.9% | -0.0% | -1.0% |

**short, trail 4 ATR: total return at stress costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -87% | -80% | -79% | -73% | -64% | -58% | -46% | -16% | -14% |
| **6** | -84% | -70% | -68% | -70% | -59% | -32% | -37% | -17% | -12% |
| **9** | -72% | -66% | -56% | -55% | -50% | -15% | -46% | +21% | +5% |
| **12** | -75% | -65% | -52% | -47% | -46% | -22% | -20% | -2% | -5% |
| **18** | -68% | -58% | -44% | -43% | -28% | -42% | -17% | -22% | -17% |
| **24** |  | -66% | -53% | -35% | +1% | -23% | -23% | -27% | -10% |
| **36** |  |  | -36% | -26% | -31% | -24% | -32% | -31% | -28% |
| **48** |  |  | -34% | -42% | -29% | -37% | -8% | -8% | -41% |
| **72** |  |  |  |  | -32% | -34% | -17% | -27% | -40% |

**short, trail 4 ATR: thirds**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -52% -17% -1% | -45% -7% +1% | -39% -17% -4% | -44% +5% +1% | -27% +9% -2% | -26% +15% -6% | -26% +37% +1% | -10% +31% +21% | -17% +15% +34% |
| **6** | -52% -5% -9% | -40% -11% +23% | -43% +4% +16% | -40% +0% +1% | -32% +7% +8% | -13% +40% -3% | -14% +31% -3% | +2% +11% +19% | -21% +24% +29% |
| **9** | -38% +10% -6% | -33% -10% +16% | -30% +5% +12% | -28% +4% +10% | -25% +11% +6% | +5% +30% +1% | -8% -1% -3% | +5% +35% +27% | -18% +28% +36% |
| **12** | -39% -14% +2% | -25% -15% +8% | -25% +4% +10% | -19% -1% +17% | -16% +1% +8% | +6% +15% +3% | +9% +12% +0% | +7% +3% +29% | -17% +31% +19% |
| **18** | -31% -12% +2% | -27% -13% +22% | -13% +2% +10% | -27% +16% +13% | -2% +14% +2% | -2% -8% -1% | +8% +10% +3% | -8% -0% +19% | -15% +24% +4% |
| **24** |  | -25% -18% -2% | -25% +2% +4% | -23% +33% +2% | +7% +36% +5% | -0% +1% +11% | +8% +8% -6% | -8% +1% +8% | -10% +31% -1% |
| **36** |  |  | -26% +26% +8% | -12% +19% +6% | -6% +6% +0% | -4% +10% +2% | -5% +5% -4% | -12% -0% +5% | -14% +15% -8% |
| **48** |  |  | -13% +14% +1% | -11% +8% -9% | -12% +12% +2% | -7% +5% -12% | +2% +12% +7% | -2% +18% +4% | -20% +7% -14% |
| **72** |  |  |  |  | -7% +12% -9% | -16% +20% -12% | -11% +19% +4% | -12% +18% -11% | -18% +11% -19% |

**short, trail 4 ATR: trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 1577 | 1285 | 1180 | 1096 | 1018 | 870 | 839 | 731 | 563 |
| **6** | 1367 | 1084 | 1027 | 972 | 879 | 753 | 714 | 635 | 490 |
| **9** | 1129 | 940 | 852 | 796 | 752 | 643 | 613 | 534 | 433 |
| **12** | 1005 | 879 | 767 | 738 | 692 | 595 | 535 | 490 | 397 |
| **18** | 883 | 783 | 704 | 658 | 571 | 525 | 484 | 421 | 365 |
| **24** |  | 725 | 657 | 613 | 514 | 478 | 452 | 398 | 325 |
| **36** |  |  | 578 | 517 | 464 | 432 | 419 | 369 | 305 |
| **48** |  |  | 529 | 503 | 426 | 400 | 365 | 333 | 279 |
| **72** |  |  |  |  | 395 | 371 | 349 | 303 | 251 |

**both, trail 4 ATR: 11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -1.0% | -2.4% | -1.8% | -0.3% | +1.2% | +0.3% | +2.2% | +3.4% | +0.7% |
| **6** | +0.7% | -4.1% | -1.5% | -2.1% | +0.8% | +2.2% | +2.7% | +3.1% | +2.6% |
| **9** | -2.8% | -1.7% | -0.4% | +0.7% | +1.7% | +1.0% | +2.5% | +4.4% | +3.4% |
| **12** | +1.2% | -2.7% | -1.6% | +1.2% | +0.5% | +2.1% | +2.8% | +2.9% | +1.0% |
| **18** | -1.2% | -0.9% | +2.7% | +3.8% | +2.5% | +3.1% | +3.8% | +3.3% | +1.6% |
| **24** |  | -2.2% | +0.8% | +2.5% | +4.4% | +2.8% | +3.7% | +2.9% | +1.2% |
| **36** |  |  | +2.3% | +4.1% | +4.3% | +4.2% | +2.5% | +0.9% | +0.4% |
| **48** |  |  | +3.7% | +2.3% | +3.7% | +1.6% | +4.3% | +2.3% | -1.4% |
| **72** |  |  |  |  | +2.7% | +2.6% | +2.3% | +0.8% | -0.1% |

**both, trail 4 ATR: total return at stress costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -74% | -80% | -76% | -67% | -52% | -59% | -28% | -8% | -40% |
| **6** | -59% | -87% | -73% | -78% | -51% | -28% | -18% | -9% | -6% |
| **9** | -83% | -73% | -68% | -51% | -37% | -47% | -17% | +32% | +20% |
| **12** | -45% | -79% | -75% | -46% | -53% | -32% | -14% | -8% | -31% |
| **18** | -71% | -66% | -20% | -3% | -23% | -8% | +11% | +6% | -23% |
| **24** |  | -75% | -50% | -24% | +33% | -14% | +13% | +7% | -24% |
| **36** |  |  | -31% | +13% | +27% | +26% | -12% | -36% | -37% |
| **48** |  |  | +5% | -20% | +14% | -31% | +33% | -7% | -58% |
| **72** |  |  |  |  | -7% | -10% | -15% | -28% | -42% |

**both, trail 4 ATR: thirds**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | +10% -1% -40% | -12% +7% -51% | -25% +6% -29% | -33% +54% -25% | -19% +98% -34% | -18% +9% -2% | +1% +53% -3% | +39% +28% +2% | -15% +34% -9% |
| **6** | -9% +51% -28% | -39% -23% -36% | -32% +8% -19% | -16% -6% -40% | -11% +43% -20% | +21% +51% -20% | +7% +71% -10% | +34% +33% -1% | -21% +95% +3% |
| **9** | -31% +24% -53% | -8% +1% -36% | -21% +45% -34% | -11% +67% -34% | +39% +32% -30% | +4% +21% -17% | +4% +38% +12% | +5% +89% +20% | -16% +118% +7% |
| **12** | +11% +49% -32% | -6% -8% -52% | -5% +23% -54% | -10% +16% +6% | +28% +16% -36% | -1% +16% +16% | +11% +71% -15% | +31% +61% -22% | -20% +59% -12% |
| **18** | +17% -3% -43% | -6% +0% -25% | -4% +77% -8% | -6% +147% -16% | +23% +61% -25% | +22% +39% +5% | +35% +48% +1% | +32% +58% -12% | -9% +81% -26% |
| **24** |  | -19% -5% -34% | +2% +47% -33% | +12% +43% -5% | +18% +84% +9% | +1% +51% +4% | +40% +60% -8% | +17% +44% +7% | -8% +65% -23% |
| **36** |  |  | -4% +62% -10% | -6% +108% +9% | +20% +62% +18% | +38% +73% -3% | +44% +61% -34% | +4% +21% -16% | -0% +36% -30% |
| **48** |  |  | -2% +78% +13% | +2% +38% +3% | -3% +67% +25% | +8% +41% -20% | +3% +137% -9% | +26% +33% -12% | -24% +23% -34% |
| **72** |  |  |  |  | +8% +65% -9% | -5% +125% -28% | -7% +88% -19% | -3% +73% -34% | -9% +46% -38% |

**both, trail 4 ATR: trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 1434 | 1184 | 1185 | 1152 | 1090 | 1037 | 976 | 900 | 747 |
| **6** | 1284 | 1139 | 1067 | 1077 | 991 | 937 | 926 | 835 | 698 |
| **9** | 1215 | 1027 | 1021 | 976 | 944 | 893 | 850 | 767 | 639 |
| **12** | 1071 | 1030 | 1000 | 943 | 905 | 869 | 810 | 754 | 644 |
| **18** | 1018 | 981 | 907 | 892 | 859 | 815 | 781 | 697 | 610 |
| **24** |  | 956 | 923 | 858 | 786 | 793 | 769 | 667 | 562 |
| **36** |  |  | 857 | 802 | 753 | 733 | 712 | 647 | 519 |
| **48** |  |  | 802 | 783 | 719 | 699 | 652 | 590 | 480 |
| **72** |  |  |  |  | 675 | 652 | 626 | 527 | 438 |

**long, trail 6 ATR: 11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -0.2% | -2.9% | -3.1% | -2.0% | -2.4% | -3.3% | -1.6% | +0.5% | +0.8% |
| **6** | -3.2% | -2.2% | -1.8% | -1.0% | -4.7% | -2.3% | -2.0% | +1.2% | +0.7% |
| **9** | -2.4% | -3.3% | -1.7% | -2.6% | -2.8% | -0.9% | -0.4% | +1.1% | +1.1% |
| **12** | -0.8% | -3.4% | -3.0% | +0.1% | -1.5% | -0.5% | -2.3% | +1.5% | +1.3% |
| **18** | -3.9% | -2.5% | -1.4% | +0.2% | -0.2% | +0.2% | +0.4% | +0.8% | +1.3% |
| **24** |  | -1.5% | -0.5% | -0.5% | +0.7% | +0.4% | +0.8% | +2.6% | +1.2% |
| **36** |  |  | +0.4% | +0.1% | +1.0% | +0.4% | +1.7% | +3.2% | +0.6% |
| **48** |  |  | -0.1% | -0.0% | +0.2% | +1.1% | +1.5% | +2.3% | +0.4% |
| **72** |  |  |  |  | +0.7% | +1.3% | +1.3% | +2.8% | +1.2% |

**long, trail 6 ATR: total return at stress costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -80% | -83% | -83% | -76% | -76% | -79% | -67% | -39% | -32% |
| **6** | -87% | -78% | -73% | -64% | -84% | -72% | -66% | -20% | -28% |
| **9** | -80% | -81% | -69% | -73% | -73% | -58% | -47% | -16% | -22% |
| **12** | -69% | -79% | -75% | -47% | -64% | -50% | -66% | -9% | -14% |
| **18** | -81% | -73% | -60% | -43% | -45% | -42% | -32% | -19% | -10% |
| **24** |  | -64% | -50% | -52% | -33% | -33% | -20% | +21% | -5% |
| **36** |  |  | -39% | -39% | -21% | -29% | +4% | +45% | -18% |
| **48** |  |  | -42% | -36% | -33% | -15% | -5% | +29% | -17% |
| **72** |  |  |  |  | -21% | -10% | -4% | +49% | -1% |

**long, trail 6 ATR: thirds**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -14% +64% -59% | -31% +22% -56% | -32% +3% -53% | -20% -6% -40% | -7% -26% -39% | -20% -20% -46% | -33% -5% -14% | -19% +6% +10% | -21% +68% -29% |
| **6** | -36% +41% -66% | -17% -2% -48% | -25% +11% -43% | +8% -4% -41% | -3% -48% -49% | -26% -19% -26% | -32% -22% -4% | +3% +12% +1% | -21% +66% -27% |
| **9** | -6% +15% -63% | -26% -5% -52% | -19% -8% -31% | -19% -23% -33% | +8% -33% -43% | -22% -11% -12% | -20% +5% -9% | +11% +13% -8% | -21% +61% -21% |
| **12** | +10% +26% -58% | -14% -24% -46% | -24% -17% -39% | +38% -27% -21% | +3% -24% -33% | -23% -8% +0% | -26% -28% -11% | +14% +48% -27% | -21% +74% -21% |
| **18** | -25% -21% -45% | -12% -27% -33% | -8% -6% -31% | +11% -3% -23% | +33% -36% -10% | -26% +3% +4% | +12% -17% -3% | +19% +17% -25% | -9% +83% -33% |
| **24** |  | +11% -28% -32% | +44% -24% -35% | -4% -12% -20% | +8% -13% -2% | -5% +3% -8% | +7% +11% -12% | +11% +64% -17% | -2% +69% -31% |
| **36** |  |  | +10% +1% -24% | -1% -7% -12% | -12% +16% +2% | -4% -7% +3% | +31% +20% -17% | +21% +71% -14% | -8% +68% -37% |
| **48** |  |  | +8% -13% -18% | -7% -12% -0% | -18% +7% -3% | +13% +13% -15% | +2% +57% -26% | +14% +53% -10% | -10% +55% -30% |
| **72** |  |  |  |  | -8% +14% -6% | -5% +55% -25% | -9% +57% -18% | +20% +91% -23% | +1% +59% -29% |

**long, trail 6 ATR: trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 1593 | 1243 | 1025 | 924 | 843 | 744 | 718 | 627 | 490 |
| **6** | 1362 | 1035 | 852 | 765 | 713 | 665 | 590 | 524 | 413 |
| **9** | 1114 | 874 | 727 | 636 | 615 | 542 | 497 | 445 | 367 |
| **12** | 955 | 781 | 635 | 566 | 544 | 485 | 452 | 409 | 327 |
| **18** | 816 | 648 | 539 | 507 | 459 | 415 | 393 | 335 | 294 |
| **24** |  | 577 | 491 | 439 | 405 | 384 | 349 | 300 | 244 |
| **36** |  |  | 430 | 379 | 371 | 332 | 312 | 277 | 223 |
| **48** |  |  | 386 | 363 | 328 | 310 | 281 | 251 | 203 |
| **72** |  |  |  |  | 298 | 264 | 261 | 210 | 173 |

**short, trail 6 ATR: 11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -2.6% | -1.5% | -0.6% | +0.2% | -0.3% | +0.4% | +1.8% | +3.9% | +2.5% |
| **6** | -2.1% | -1.1% | -0.4% | +0.9% | +0.2% | +1.8% | +2.6% | +3.6% | +2.2% |
| **9** | -1.0% | -0.2% | +0.3% | +0.1% | +1.4% | +1.1% | +1.2% | +3.7% | +2.3% |
| **12** | -2.0% | -0.2% | -0.4% | +0.4% | +0.4% | +1.8% | +2.8% | +3.3% | +1.7% |
| **18** | -1.7% | +0.4% | -0.8% | -0.4% | +0.5% | +2.4% | +3.2% | +2.6% | +2.0% |
| **24** |  | -0.5% | -1.1% | -0.5% | +1.3% | +2.9% | +3.1% | +3.1% | +2.5% |
| **36** |  |  | +1.2% | +0.4% | +1.2% | +1.9% | +2.6% | +2.3% | +1.9% |
| **48** |  |  | +0.3% | +0.5% | +0.4% | +2.5% | +2.9% | +1.7% | +0.6% |
| **72** |  |  |  |  | +1.0% | +1.3% | +2.2% | +1.0% | +0.1% |

**short, trail 6 ATR: total return at stress costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -84% | -75% | -62% | -52% | -56% | -40% | -19% | +48% | +24% |
| **6** | -80% | -68% | -56% | -38% | -45% | -9% | +11% | +50% | +19% |
| **9** | -68% | -54% | -42% | -46% | -21% | -13% | -18% | +68% | +26% |
| **12** | -74% | -48% | -51% | -42% | -34% | +4% | +33% | +60% | +12% |
| **18** | -68% | -36% | -53% | -48% | -29% | +22% | +50% | +36% | +23% |
| **24** |  | -47% | -57% | -47% | -7% | +37% | +48% | +49% | +38% |
| **36** |  |  | -20% | -31% | -10% | +10% | +35% | +28% | +23% |
| **48** |  |  | -33% | -24% | -25% | +32% | +52% | +14% | -9% |
| **72** |  |  |  |  | -7% | -0% | +27% | -2% | -17% |

**short, trail 6 ATR: thirds**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -53% -20% +15% | -46% -7% +10% | -34% -4% +13% | -32% +16% +8% | -25% -5% +8% | -26% +27% -1% | -20% +46% +11% | -3% +70% +32% | -19% +56% +32% |
| **6** | -47% -18% +12% | -41% -5% +11% | -37% -1% +24% | -30% +30% +14% | -28% +17% +6% | -1% +34% +2% | -7% +57% +11% | -7% +66% +36% | -20% +53% +27% |
| **9** | -37% -9% +13% | -34% -12% +36% | -32% -1% +37% | -35% +16% +12% | -28% +46% +12% | +3% +19% +1% | -11% +19% +10% | +5% +55% +37% | -19% +46% +35% |
| **12** | -45% -14% +4% | -25% -9% +26% | -37% +2% +18% | -34% +5% +28% | -25% +17% +10% | -1% +22% +19% | +8% +44% +15% | +8% +37% +40% | -18% +32% +30% |
| **18** | -34% -23% +8% | -29% -4% +43% | -33% -14% +22% | -29% +9% -2% | -18% +17% +3% | +9% +36% +10% | +15% +47% +14% | +4% +42% +17% | -9% +32% +25% |
| **24** |  | -21% -10% +9% | -37% -1% +2% | -28% +13% -7% | -3% +26% +3% | +8% +43% +16% | +12% +47% +13% | +8% +51% +14% | -8% +60% +11% |
| **36** |  |  | -27% +45% +5% | -20% +27% -9% | -3% +17% +3% | +4% +29% +5% | +4% +40% +15% | +6% +42% +4% | -2% +50% -1% |
| **48** |  |  | -22% +21% -3% | -4% +8% -3% | -14% +17% -5% | +10% +45% +3% | +14% +41% +15% | +7% +17% +11% | -14% +38% -10% |
| **72** |  |  |  |  | -4% +27% -5% | -4% +34% -5% | -0% +42% +8% | -11% +31% +0% | -15% +30% -13% |

**short, trail 6 ATR: trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 1518 | 1163 | 946 | 840 | 800 | 641 | 639 | 533 | 433 |
| **6** | 1280 | 961 | 812 | 742 | 668 | 547 | 522 | 460 | 383 |
| **9** | 1040 | 781 | 661 | 618 | 560 | 475 | 463 | 391 | 337 |
| **12** | 912 | 684 | 595 | 570 | 517 | 435 | 401 | 353 | 303 |
| **18** | 749 | 584 | 533 | 490 | 433 | 375 | 338 | 304 | 268 |
| **24** |  | 520 | 494 | 463 | 383 | 336 | 311 | 280 | 234 |
| **36** |  |  | 420 | 380 | 336 | 314 | 288 | 256 | 221 |
| **48** |  |  | 382 | 349 | 313 | 278 | 258 | 244 | 210 |
| **72** |  |  |  |  | 278 | 256 | 239 | 221 | 183 |

**both, trail 6 ATR: 11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -2.2% | +0.2% | -2.3% | -2.0% | +3.3% | +1.7% | +2.4% | +2.8% | +3.5% |
| **6** | -1.0% | -1.2% | +0.2% | -0.4% | -1.5% | +3.8% | +2.6% | +1.7% | +2.8% |
| **9** | +1.3% | -2.1% | -1.2% | -0.1% | -0.5% | +1.9% | +3.6% | +2.4% | +3.6% |
| **12** | -0.3% | -0.5% | +2.3% | +2.8% | +0.3% | +3.4% | +3.4% | +2.8% | +3.4% |
| **18** | -0.5% | +1.5% | +1.6% | +0.6% | +1.7% | +3.7% | +4.0% | +4.0% | +4.4% |
| **24** |  | +0.9% | +0.6% | +0.6% | +3.9% | +3.8% | +2.2% | +3.4% | +3.6% |
| **36** |  |  | +0.5% | +2.6% | +4.0% | +2.8% | +3.9% | +3.3% | +2.8% |
| **48** |  |  | +1.4% | +2.1% | +2.5% | +2.2% | +4.9% | +4.3% | +0.9% |
| **72** |  |  |  |  | +2.5% | +4.3% | +2.0% | +3.0% | +1.9% |

**both, trail 6 ATR: total return at stress costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -79% | -49% | -73% | -68% | +15% | -18% | +2% | +9% | +36% |
| **6** | -72% | -65% | -46% | -50% | -64% | +34% | +2% | -10% | +14% |
| **9** | -32% | -68% | -59% | -49% | -53% | -10% | +35% | +9% | +53% |
| **12** | -51% | -51% | +2% | +9% | -39% | +27% | +34% | +24% | +47% |
| **18** | -50% | -25% | -21% | -40% | -10% | +31% | +54% | +63% | +74% |
| **24** |  | -26% | -35% | -37% | +39% | +40% | +17% | +43% | +59% |
| **36** |  |  | -38% | +5% | +47% | +17% | +57% | +39% | +27% |
| **48** |  |  | -23% | -5% | +7% | +1% | +101% | +86% | -19% |
| **72** |  |  |  |  | +7% | +70% | -3% | +40% | +1% |

**both, trail 6 ATR: thirds**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | +27% -12% -56% | +31% -0% -28% | -13% +1% -47% | -27% -4% -24% | +28% +79% -19% | -6% +57% -16% | +4% +83% -18% | +19% +69% -19% | -12% +138% -7% |
| **6** | -7% +14% -44% | -7% +30% -49% | -12% +26% -22% | +24% -14% -25% | -26% +12% -31% | +16% +68% +5% | +10% +59% -13% | +8% +53% -20% | -7% +104% -17% |
| **9** | +18% +64% -36% | -13% -24% -17% | -19% +0% -20% | -16% +32% -28% | -11% +13% -28% | +2% +45% -12% | +8% +40% +30% | +1% +69% -9% | -3% +157% -18% |
| **12** | +12% +13% -32% | +3% -16% -7% | +6% +26% +16% | +3% +64% -2% | -18% +17% -6% | -4% +85% +5% | -12% +90% +13% | -7% +102% -9% | -14% +175% -18% |
| **18** | +4% -12% -10% | -14% +67% -14% | -7% +74% -27% | -34% +60% -12% | -17% +38% +15% | -13% +66% +29% | -1% +97% +12% | +2% +124% -1% | -19% +273% -25% |
| **24** |  | -18% +60% -17% | -27% +67% -21% | -25% +21% +12% | -10% +58% +43% | -4% +106% -1% | +12% +45% -2% | +4% +101% -7% | -12% +176% -16% |
| **36** |  |  | -31% +26% +16% | -27% +78% +17% | -2% +93% +10% | +2% +55% +2% | +24% +99% -13% | +13% +71% -3% | -18% +148% -20% |
| **48** |  |  | -29% +72% -9% | -8% +68% -12% | -8% +57% +5% | +11% +30% +0% | +14% +122% +6% | +13% +116% +1% | -24% +91% -29% |
| **72** |  |  |  |  | -21% +73% +9% | +9% +113% -3% | -9% +69% -15% | +12% +101% -19% | -21% +136% -31% |

**both, trail 6 ATR: trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 1328 | 957 | 858 | 773 | 697 | 620 | 595 | 571 | 517 |
| **6** | 1198 | 874 | 720 | 702 | 655 | 579 | 557 | 536 | 459 |
| **9** | 954 | 799 | 664 | 629 | 608 | 521 | 504 | 480 | 413 |
| **12** | 859 | 723 | 590 | 569 | 551 | 506 | 490 | 447 | 387 |
| **18** | 729 | 620 | 555 | 566 | 507 | 469 | 465 | 422 | 369 |
| **24** |  | 564 | 549 | 514 | 490 | 445 | 430 | 401 | 339 |
| **36** |  |  | 502 | 474 | 448 | 421 | 419 | 377 | 335 |
| **48** |  |  | 481 | 464 | 436 | 429 | 384 | 365 | 331 |
| **72** |  |  |  |  | 406 | 373 | 378 | 347 | 294 |

**long, no stop: 11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -0.6% | -2.6% | -1.9% | -1.5% | -3.5% | -2.8% | -0.6% | -0.1% | +5.9% |
| **6** | -3.5% | -2.5% | -1.3% | -1.5% | -4.2% | -3.6% | +1.5% | +3.4% | +4.8% |
| **9** | -3.1% | -2.1% | -1.6% | -2.5% | -3.8% | -1.0% | -1.1% | +3.9% | +4.8% |
| **12** | -1.8% | -2.3% | -3.2% | -2.1% | -0.3% | -1.4% | -1.3% | +2.1% | -0.5% |
| **18** | -2.7% | -3.0% | -0.2% | -0.1% | +1.3% | +0.8% | +2.2% | +4.3% | +6.1% |
| **24** |  | -0.8% | -2.2% | +0.1% | +0.9% | -0.0% | +0.5% | +7.1% | +5.1% |
| **36** |  |  | +0.0% | +0.7% | +0.5% | +4.8% | +4.5% | +4.4% | +5.4% |
| **48** |  |  | +0.8% | -0.1% | +1.3% | +3.1% | +3.6% | +5.7% | +5.1% |
| **72** |  |  |  |  | +2.2% | +2.4% | +3.6% | +5.8% | -1.5% |

**long, no stop: total return at stress costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -82% | -82% | -76% | -70% | -80% | -73% | -50% | -39% | +134% |
| **6** | -88% | -80% | -69% | -68% | -81% | -77% | -19% | +26% | +103% |
| **9** | -84% | -74% | -67% | -71% | -77% | -53% | -51% | +51% | +82% |
| **12** | -75% | -72% | -77% | -68% | -47% | -56% | -54% | +11% | -34% |
| **18** | -74% | -75% | -45% | -46% | -20% | -29% | +3% | +67% | +159% |
| **24** |  | -55% | -67% | -36% | -25% | -39% | -24% | +228% | +113% |
| **36** |  |  | -36% | -29% | -27% | +76% | +70% | +75% | +117% |
| **48** |  |  | -26% | -37% | -14% | +27% | +42% | +151% | +107% |
| **72** |  |  |  |  | +2% | +3% | +48% | +161% | -45% |

**long, no stop: thirds**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -9% +46% -62% | -26% +18% -56% | -19% +13% -52% | -8% +8% -49% | -9% -37% -45% | +9% -35% -47% | +17% -23% -26% | +7% +5% -28% | -2% +285% -30% |
| **6** | -31% +24% -67% | -15% -7% -52% | -18% +15% -45% | +8% -3% -52% | +4% -53% -43% | +1% -49% -39% | +2% +25% -19% | +45% +78% -38% | +10% +197% -31% |
| **9** | +5% -12% -64% | -26% +19% -51% | -17% -1% -39% | -1% -35% -36% | -12% -38% -43% | +8% -25% -25% | -6% -23% -15% | +57% +72% -34% | -12% +249% -35% |
| **12** | +12% -0% -59% | -9% -15% -44% | -22% -24% -43% | +25% -42% -39% | +17% -22% -26% | -10% -26% -16% | +7% -38% -16% | +30% +50% -35% | +6% +3% -33% |
| **18** | -26% -3% -41% | -12% -36% -35% | +7% -9% -25% | +23% -17% -32% | +33% -9% -18% | -11% +8% -13% | -6% +34% -4% | +36% +102% -31% | +17% +263% -35% |
| **24** |  | +19% -21% -35% | +7% -38% -35% | +10% -3% -26% | +32% -19% -16% | +22% -28% -17% | +12% -6% -17% | +77% +185% -29% | +2% +252% -37% |
| **36** |  |  | +11% -9% -22% | +20% -3% -27% | +9% -9% -16% | +65% +40% -12% | +32% +73% -17% | +10% +154% -32% | +12% +248% -41% |
| **48** |  |  | +24% -10% -22% | +1% -19% -10% | +14% +5% -18% | +23% +60% -27% | +16% +92% -30% | +19% +222% -30% | +5% +257% -42% |
| **72** |  |  |  |  | +12% +35% -24% | -9% +75% -29% | +7% +102% -26% | +7% +260% -28% | +12% -16% -38% |

**long, no stop: trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 1572 | 1212 | 957 | 842 | 696 | 559 | 467 | 392 | 228 |
| **6** | 1341 | 1005 | 803 | 709 | 587 | 496 | 403 | 311 | 191 |
| **9** | 1095 | 829 | 673 | 547 | 495 | 382 | 331 | 259 | 178 |
| **12** | 932 | 715 | 582 | 491 | 406 | 341 | 296 | 230 | 161 |
| **18** | 766 | 588 | 444 | 390 | 326 | 282 | 243 | 185 | 129 |
| **24** |  | 502 | 403 | 324 | 288 | 259 | 209 | 152 | 117 |
| **36** |  |  | 316 | 274 | 233 | 203 | 180 | 133 | 98 |
| **48** |  |  | 272 | 237 | 204 | 179 | 157 | 119 | 88 |
| **72** |  |  |  |  | 179 | 151 | 125 | 89 | 80 |

**short, no stop: 11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -2.8% | -1.9% | -0.7% | +0.8% | +0.0% | +0.1% | +1.3% | +1.5% | +2.3% |
| **6** | -2.1% | -1.5% | -0.8% | +1.2% | +0.9% | +1.0% | +1.4% | +2.5% | +1.5% |
| **9** | -0.7% | -0.2% | -0.2% | +0.7% | +1.4% | +0.6% | +0.9% | +2.7% | +1.8% |
| **12** | -2.1% | +0.3% | -0.0% | +0.6% | +0.7% | +0.4% | +2.5% | +2.0% | +1.9% |
| **18** | -1.3% | +0.8% | -0.0% | -0.6% | +0.7% | +2.6% | +2.4% | +1.7% | +2.0% |
| **24** |  | +0.6% | -0.5% | +0.9% | +0.9% | +1.9% | +1.9% | +1.4% | +1.5% |
| **36** |  |  | -0.6% | -0.9% | +0.1% | +1.0% | +1.9% | +2.3% | +1.8% |
| **48** |  |  | -0.9% | +0.2% | +2.2% | +3.5% | +2.1% | +2.7% | +2.0% |
| **72** |  |  |  |  | +2.2% | +1.9% | +2.3% | +0.8% | +1.3% |

**short, no stop: total return at stress costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -85% | -77% | -61% | -40% | -46% | -37% | -17% | +1% | +42% |
| **6** | -79% | -69% | -57% | -24% | -24% | -16% | -7% | +39% | +15% |
| **9** | -66% | -51% | -42% | -29% | -5% | -13% | -10% | +55% | +28% |
| **12** | -73% | -39% | -39% | -29% | -17% | -17% | +40% | +33% | +32% |
| **18** | -61% | -24% | -39% | -40% | -13% | +43% | +42% | +21% | +38% |
| **24** |  | -27% | -40% | -17% | -6% | +21% | +28% | +14% | +24% |
| **36** |  |  | -42% | -43% | -24% | -2% | +23% | +41% | +32% |
| **48** |  |  | -42% | -22% | +29% | +83% | +31% | +56% | +43% |
| **72** |  |  |  |  | +33% | +29% | +42% | +3% | +18% |

**short, no stop: thirds**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -54% -23% +15% | -46% -10% +4% | -33% -14% +23% | -34% +22% +20% | -33% -3% +26% | -30% +6% +16% | -31% +29% +25% | -14% +8% +35% | -10% +33% +33% |
| **6** | -45% -25% +18% | -38% -20% +16% | -35% -16% +27% | -24% +23% +22% | -30% +10% +38% | -20% +29% +4% | -23% +25% +22% | -4% +26% +34% | -15% +15% +32% |
| **9** | -35% -11% +18% | -30% -25% +53% | -29% -11% +35% | -34% +6% +43% | -28% +26% +36% | -11% +0% +21% | -22% +15% +21% | -1% +32% +36% | -12% +34% +18% |
| **12** | -41% -22% +5% | -20% -21% +49% | -39% +2% +39% | -35% -1% +47% | -29% +20% +24% | -13% +4% +11% | -7% +42% +24% | -5% +21% +30% | -16% +35% +25% |
| **18** | -28% -29% +25% | -26% -7% +56% | -39% -8% +46% | -31% +2% +9% | -24% +12% +25% | +1% +30% +26% | +4% +27% +21% | +2% +7% +24% | -5% +29% +19% |
| **24** |  | -28% -5% +44% | -39% +1% +23% | -32% +36% +11% | -20% +31% +7% | -2% +15% +23% | -9% +17% +33% | +1% -1% +26% | -13% +34% +12% |
| **36** |  |  | -37% +14% -1% | -31% +16% -14% | -16% +4% +1% | -6% +16% +1% | -12% +26% +21% | +7% +15% +23% | -9% +34% +13% |
| **48** |  |  | -36% +7% +0% | -25% +19% +1% | -20% +44% +26% | +3% +48% +31% | -2% +18% +22% | +11% +26% +18% | -15% +38% +25% |
| **72** |  |  |  |  | -10% +51% +8% | -13% +24% +29% | -0% +41% +7% | -8% +18% -0% | -20% +33% +14% |

**short, no stop: trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 1508 | 1152 | 880 | 723 | 616 | 463 | 423 | 322 | 175 |
| **6** | 1263 | 940 | 739 | 605 | 510 | 387 | 337 | 247 | 170 |
| **9** | 1027 | 734 | 587 | 490 | 405 | 311 | 274 | 205 | 137 |
| **12** | 894 | 637 | 498 | 442 | 380 | 286 | 228 | 187 | 125 |
| **18** | 722 | 523 | 434 | 361 | 292 | 212 | 183 | 156 | 93 |
| **24** |  | 446 | 366 | 315 | 254 | 200 | 162 | 142 | 84 |
| **36** |  |  | 304 | 270 | 214 | 168 | 134 | 108 | 72 |
| **48** |  |  | 269 | 225 | 171 | 131 | 115 | 91 | 61 |
| **72** |  |  |  |  | 141 | 111 | 96 | 76 | 51 |

**both, no stop: 11-day window mean**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -1.5% | +0.8% | -1.7% | -0.7% | +0.9% | +0.7% | +0.4% | -0.0% | +0.7% |
| **6** | -0.3% | -4.4% | -2.9% | +0.9% | -0.3% | +0.5% | +0.1% | +1.3% | +0.5% |
| **9** | +0.7% | -3.5% | -1.5% | +1.6% | -3.0% | +0.2% | -0.8% | -0.2% | +2.0% |
| **12** | -0.9% | -1.1% | +1.4% | +0.2% | -2.8% | -0.9% | -1.0% | -2.0% | +1.9% |
| **18** | -0.8% | +0.5% | -0.4% | -0.4% | -0.3% | -1.7% | +0.2% | +0.7% | +2.8% |
| **24** |  | +1.0% | -0.6% | -0.9% | -2.7% | -0.3% | +1.6% | +0.5% | +1.4% |
| **36** |  |  | +0.1% | +0.1% | -0.5% | -0.1% | +0.2% | -0.2% | +1.0% |
| **48** |  |  | -1.3% | -1.8% | -2.7% | -1.9% | +0.2% | -0.7% | +7.4% |
| **72** |  |  |  |  | -2.1% | -0.5% | +0.5% | +1.8% | +1.5% |

**both, no stop: total return at stress costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -75% | -37% | -63% | -49% | -20% | -24% | -20% | -25% | -12% |
| **6** | -64% | -84% | -72% | -25% | -46% | -22% | -30% | -2% | -24% |
| **9** | -36% | -75% | -56% | -6% | -69% | -25% | -39% | -36% | +22% |
| **12** | -58% | -57% | -10% | -33% | -68% | -45% | -46% | -54% | +29% |
| **18** | -50% | -32% | -36% | -35% | -36% | -55% | -27% | -8% | +65% |
| **24** |  | -12% | -37% | -41% | -63% | -40% | +17% | -13% | +13% |
| **36** |  |  | -29% | -32% | -38% | -35% | -29% | -30% | +1% |
| **48** |  |  | -49% | -57% | -65% | -59% | -22% | -36% | +273% |
| **72** |  |  |  |  | -58% | -39% | -23% | +34% | +22% |

**both, no stop: thirds**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | +21% -6% -51% | +37% +7% -25% | +6% -31% -22% | -8% -33% +21% | +18% -16% +8% | -22% +27% -2% | -8% +11% -6% | +1% -14% +1% | -3% +20% -14% |
| **6** | +7% -5% -28% | -21% -40% -41% | -5% -41% -26% | +20% -36% +37% | -16% -18% +5% | +18% -4% -16% | +38% -33% -9% | +7% +27% -16% | +42% -12% -32% |
| **9** | +20% +22% -23% | -17% -26% -36% | -32% +7% -15% | -25% +50% +11% | -43% -25% -6% | +2% -4% -10% | +17% -23% -19% | -10% +4% -22% | +1% +35% -4% |
| **12** | +18% -4% -37% | -5% -12% -24% | -12% +62% -16% | -14% -3% +5% | -44% -18% -13% | -31% +14% -17% | -26% -15% -0% | -26% -3% -27% | -1% +35% +3% |
| **18** | +25% -20% -22% | +21% -17% -5% | -6% +3% -15% | -31% -7% +27% | -16% -10% +2% | -39% +12% -22% | -20% +28% -19% | -11% +38% -18% | +15% +24% +22% |
| **24** |  | -6% -2% +26% | -17% -13% +9% | -27% -8% +7% | -50% +0% -12% | -26% +6% -11% | +2% +9% +18% | -8% -4% +8% | -10% +31% +3% |
| **36** |  |  | -13% +9% -8% | -36% +23% +2% | -24% +4% -10% | -4% -2% -21% | +0% -23% +1% | -8% -9% -10% | -16% +12% +12% |
| **48** |  |  | -42% +6% -1% | -44% +12% -19% | -36% -18% -24% | -20% -24% -24% | -32% +29% -3% | -22% +2% -12% | +2% +275% +1% |
| **72** |  |  |  |  | -27% -9% -29% | -12% -16% -11% | +9% -6% -18% | -11% +34% +18% | +4% +5% +16% |

**both, no stop: trades**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 1302 | 907 | 728 | 626 | 481 | 405 | 319 | 296 | 203 |
| **6** | 1151 | 858 | 676 | 546 | 478 | 348 | 321 | 260 | 183 |
| **9** | 939 | 749 | 542 | 472 | 432 | 289 | 292 | 237 | 136 |
| **12** | 858 | 663 | 484 | 433 | 385 | 286 | 255 | 220 | 120 |
| **18** | 710 | 559 | 411 | 381 | 318 | 263 | 218 | 169 | 87 |
| **24** |  | 454 | 367 | 335 | 303 | 248 | 172 | 149 | 109 |
| **36** |  |  | 336 | 288 | 237 | 202 | 172 | 135 | 82 |
| **48** |  |  | 293 | 251 | 218 | 190 | 155 | 132 | 74 |
| **72** |  |  |  |  | 187 | 146 | 141 | 92 | 59 |

## C. Fresh (bars after the cross in which an entry is still allowed), base risk settings (225 variants)

Cell: 11-day mean / total / stress total / trades.

**long**

| fast/slow | fresh 1 | fresh 3 | fresh 6 | fresh 12 | always (10^6) |
|---|---|---|---|---|---|
| 6/36 | -5.3% / -78% / -93% / 1474 | -6.4% / -84% / -95% / 1573 | -7.0% / -86% / -96% / 1650 | -6.9% / -87% / -97% / 1743 | -1.3% / -54% / -88% / 1724 |
| 12/36 | -5.4% / -77% / -91% / 1188 | -5.1% / -76% / -91% / 1269 | -5.4% / -80% / -93% / 1375 | -5.7% / -82% / -94% / 1478 | +0.1% / -38% / -81% / 1579 |
| 24/36 | -4.5% / -70% / -86% / 985 | -5.3% / -76% / -90% / 1058 | -5.4% / -78% / -91% / 1164 | -4.1% / -71% / -89% / 1278 | -0.7% / -46% / -83% / 1478 |
| 6/72 | -4.1% / -69% / -88% / 1263 | -4.9% / -75% / -91% / 1333 | -4.7% / -75% / -92% / 1416 | -6.2% / -84% / -95% / 1517 | -0.5% / -41% / -82% / 1544 |
| 12/72 | -2.2% / -48% / -76% / 990 | -1.8% / -46% / -76% / 1067 | -2.7% / -56% / -82% / 1168 | -2.6% / -59% / -85% / 1303 | -1.8% / -58% / -86% / 1469 |
| 24/72 | -0.4% / -20% / -57% / 771 | -0.6% / -23% / -60% / 818 | -0.3% / -25% / -63% / 896 | -2.6% / -58% / -81% / 1042 | -1.7% / -57% / -85% / 1406 |
| 48/72 | -0.2% / -15% / -50% / 646 | +0.4% / -6% / -45% / 700 | -0.8% / -33% / -63% / 786 | -1.3% / -40% / -70% / 906 | -2.7% / -65% / -88% / 1370 |
| 6/150 | -2.5% / -52% / -79% / 1053 | -2.5% / -53% / -79% / 1104 | -2.3% / -53% / -81% / 1175 | -2.8% / -60% / -85% / 1255 | -2.3% / -62% / -87% / 1432 |
| 12/150 | -0.2% / -17% / -56% / 822 | -1.6% / -42% / -71% / 877 | -1.0% / -36% / -70% / 960 | -1.7% / -49% / -78% / 1069 | -2.5% / -64% / -88% / 1380 |
| 24/150 | +0.8% / +4% / -39% / 647 | -0.1% / -16% / -52% / 706 | +0.7% / -2% / -47% / 776 | -0.7% / -34% / -67% / 897 | -3.5% / -69% / -89% / 1348 |
| 48/150 | +0.1% / -9% / -43% / 531 | +0.5% / -1% / -41% / 576 | +0.5% / -3% / -43% / 648 | -1.0% / -33% / -64% / 751 | -4.2% / -74% / -90% / 1326 |
| 6/300 | -0.9% / -26% / -62% / 855 | -0.6% / -21% / -61% / 909 | -0.7% / -29% / -66% / 980 | -1.3% / -38% / -73% / 1053 | -1.2% / -45% / -80% / 1345 |
| 12/300 | +0.2% / -3% / -43% / 673 | -1.0% / -29% / -60% / 716 | -0.0% / -13% / -53% / 780 | -1.2% / -37% / -69% / 901 | -1.3% / -46% / -79% / 1324 |
| 24/300 | -0.0% / -8% / -38% / 502 | +1.8% / +34% / -14% / 548 | +0.4% / -7% / -43% / 609 | -0.5% / -24% / -57% / 715 | -2.7% / -60% / -85% / 1290 |
| 48/300 | +0.6% / +4% / -27% / 437 | +0.8% / +6% / -27% / 470 | +0.4% / +0% / -33% / 517 | +0.4% / -3% / -38% / 580 | -4.4% / -74% / -90% / 1308 |
| **average** | -1.6% / -32% / -62% / 856 | -1.8% / -34% / -63% / 915 | -1.9% / -38% / -68% / 993 | -2.5% / -51% / -76% / 1099 | -2.0% / -57% / -85% / 1422 |

**short**

| fast/slow | fresh 1 | fresh 3 | fresh 6 | fresh 12 | always (10^6) |
|---|---|---|---|---|---|
| 6/36 | -1.9% / -48% / -81% / 1323 | -0.5% / -27% / -74% / 1350 | -1.4% / -43% / -81% / 1425 | -1.7% / -47% / -83% / 1457 | -3.4% / -64% / -90% / 1531 |
| 12/36 | -1.6% / -38% / -74% / 1059 | -1.2% / -32% / -72% / 1105 | -1.6% / -39% / -76% / 1179 | -2.6% / -53% / -83% / 1271 | -2.9% / -59% / -88% / 1474 |
| 24/36 | -0.4% / -18% / -60% / 879 | -1.4% / -34% / -69% / 936 | -1.4% / -36% / -71% / 1004 | -1.3% / -33% / -72% / 1107 | -2.7% / -58% / -87% / 1437 |
| 6/72 | -0.8% / -31% / -72% / 1162 | -1.3% / -38% / -75% / 1191 | -2.2% / -49% / -80% / 1250 | -2.7% / -57% / -85% / 1329 | -2.7% / -58% / -87% / 1422 |
| 12/72 | +0.3% / -7% / -54% / 878 | -0.6% / -22% / -63% / 941 | -1.6% / -41% / -73% / 1019 | -1.0% / -34% / -72% / 1116 | -1.7% / -46% / -83% / 1429 |
| 24/72 | -0.5% / -20% / -56% / 750 | -0.7% / -23% / -59% / 797 | -0.6% / -19% / -59% / 857 | -0.6% / -22% / -64% / 966 | -3.4% / -64% / -89% / 1430 |
| 48/72 | -0.3% / -15% / -48% / 603 | -1.1% / -29% / -58% / 648 | -0.7% / -21% / -55% / 702 | -0.1% / -12% / -52% / 784 | -3.7% / -68% / -90% / 1390 |
| 6/150 | -0.0% / -6% / -53% / 903 | +0.4% / +2% / -51% / 948 | +0.7% / +8% / -50% / 998 | +0.7% / +9% / -52% / 1059 | -2.1% / -51% / -85% / 1377 |
| 12/150 | +0.9% / +19% / -33% / 711 | +0.5% / +10% / -40% / 750 | +0.1% / -2% / -49% / 821 | +0.1% / -4% / -53% / 909 | -2.3% / -53% / -85% / 1348 |
| 24/150 | +0.9% / +15% / -28% / 579 | +1.1% / +21% / -27% / 626 | +0.4% / -2% / -43% / 682 | +0.4% / -2% / -48% / 775 | -2.2% / -53% / -85% / 1350 |
| 48/150 | -1.0% / -27% / -52% / 493 | -0.4% / -17% / -46% / 511 | -0.2% / -13% / -46% / 570 | +0.3% / -2% / -42% / 654 | -2.8% / -61% / -88% / 1368 |
| 6/300 | -0.0% / -7% / -47% / 738 | +0.6% / +8% / -40% / 766 | +0.6% / +9% / -41% / 803 | +0.5% / +5% / -47% / 873 | -3.5% / -65% / -90% / 1358 |
| 12/300 | +1.2% / +28% / -19% / 579 | +1.3% / +30% / -20% / 613 | +1.3% / +31% / -22% / 645 | +1.4% / +33% / -25% / 735 | -3.4% / -65% / -90% / 1353 |
| 24/300 | +0.3% / -4% / -35% / 471 | +0.1% / -8% / -40% / 502 | +0.2% / -5% / -39% / 549 | -0.0% / -9% / -46% / 637 | -2.5% / -55% / -86% / 1330 |
| 48/300 | -0.3% / -13% / -37% / 408 | -0.0% / -6% / -33% / 435 | +0.4% / +4% / -27% / 461 | -0.4% / -15% / -45% / 545 | -3.3% / -64% / -89% / 1322 |
| **average** | -0.2% / -11% / -50% / 769 | -0.2% / -11% / -51% / 808 | -0.4% / -14% / -54% / 864 | -0.5% / -16% / -58% / 948 | -2.8% / -59% / -88% / 1395 |

**both**

| fast/slow | fresh 1 | fresh 3 | fresh 6 | fresh 12 | always (10^6) |
|---|---|---|---|---|---|
| 6/36 | -5.2% / -76% / -94% / 1651 | -3.9% / -67% / -90% / 1573 | -3.4% / -65% / -90% / 1573 | -3.4% / -66% / -91% / 1590 | +1.2% / -2% / -70% / 1488 |
| 12/36 | -6.2% / -80% / -94% / 1529 | -4.7% / -72% / -91% / 1517 | -5.4% / -79% / -94% / 1546 | -0.9% / -35% / -82% / 1524 | +1.3% / -2% / -70% / 1458 |
| 24/36 | -3.9% / -66% / -88% / 1374 | -3.9% / -67% / -90% / 1418 | -2.8% / -55% / -86% / 1448 | -1.7% / -40% / -81% / 1468 | +0.6% / -16% / -74% / 1432 |
| 6/72 | -2.3% / -49% / -85% / 1573 | -4.0% / -66% / -90% / 1571 | -2.5% / -54% / -87% / 1569 | -1.5% / -47% / -84% / 1530 | +1.7% / -1% / -67% / 1451 |
| 12/72 | +1.8% / +31% / -55% / 1368 | +1.0% / +12% / -64% / 1396 | -2.2% / -53% / -86% / 1489 | -0.1% / -27% / -78% / 1492 | +0.7% / -17% / -74% / 1438 |
| 24/72 | +0.6% / +0% / -61% / 1226 | -1.6% / -44% / -80% / 1267 | +0.2% / -14% / -72% / 1348 | -1.6% / -44% / -82% / 1396 | -2.9% / -65% / -89% / 1435 |
| 48/72 | -0.2% / -19% / -69% / 1070 | +0.2% / -15% / -66% / 1130 | +0.6% / -3% / -63% / 1200 | -0.2% / -19% / -71% / 1285 | -5.9% / -84% / -95% / 1466 |
| 6/150 | +0.6% / +0% / -64% / 1354 | +1.2% / +19% / -58% / 1336 | +1.2% / +14% / -63% / 1424 | +2.2% / +32% / -56% / 1428 | -1.1% / -44% / -82% / 1425 |
| 12/150 | +2.0% / +40% / -48% / 1211 | +1.5% / +25% / -53% / 1229 | +1.5% / +11% / -62% / 1343 | +1.7% / +19% / -60% / 1377 | -3.4% / -70% / -91% / 1443 |
| 24/150 | +1.8% / +26% / -46% / 1070 | +2.1% / +37% / -44% / 1112 | +1.4% / +14% / -57% / 1201 | -0.4% / -30% / -74% / 1289 | -5.9% / -84% / -95% / 1474 |
| 48/150 | -0.8% / -30% / -68% / 916 | +0.2% / -10% / -58% / 967 | +0.4% / -10% / -62% / 1082 | -1.1% / -39% / -77% / 1172 | -6.9% / -87% / -96% / 1491 |
| 6/300 | +0.9% / +12% / -54% / 1160 | +0.7% / +4% / -59% / 1181 | +1.5% / +22% / -53% / 1228 | +1.3% / +14% / -58% / 1280 | -5.6% / -82% / -95% / 1447 |
| 12/300 | +2.5% / +59% / -30% / 1009 | +2.0% / +45% / -37% / 1056 | +1.7% / +27% / -49% / 1126 | +1.0% / +12% / -58% / 1211 | -5.2% / -80% / -94% / 1460 |
| 24/300 | +0.8% / +2% / -50% / 874 | +2.0% / +34% / -36% / 917 | +1.0% / +6% / -53% / 1001 | -0.0% / -16% / -65% / 1111 | -6.1% / -83% / -95% / 1449 |
| 48/300 | +0.3% / -8% / -51% / 773 | +0.2% / -10% / -54% / 822 | +0.7% / +4% / -48% / 880 | -0.1% / -14% / -60% / 958 | -5.1% / -78% / -93% / 1431 |
| **average** | -0.5% / -11% / -64% / 1211 | -0.5% / -12% / -65% / 1233 | -0.4% / -16% / -68% / 1297 | -0.3% / -20% / -72% / 1341 | -2.8% / -53% / -85% / 1453 |

## D. Trend line (price must be above/below a slower EMA), base risk settings, every variant started at bar 2,160 (246 variants)

Cell: 11-day mean / total / stress total / trades. Blank = trend line not slower than the slow EMA, or longer than 720 h.

**long**

| fast/slow | none | 2 x slow | 4 x slow | 200 | 480 | 720 |
|---|---|---|---|---|---|---|
| 6/36 | -7.7% / -82% / -93% / 1255 | -7.2% / -82% / -93% / 1311 | -5.6% / -72% / -88% / 1133 | -6.8% / -79% / -91% / 1091 | -6.0% / -75% / -88% / 965 | -3.8% / -61% / -80% / 879 |
| 12/36 | -6.4% / -75% / -89% / 1027 | -7.6% / -82% / -93% / 1216 | -7.5% / -81% / -91% / 1039 | -7.4% / -81% / -91% / 1013 | -6.9% / -78% / -89% / 851 | -4.5% / -64% / -80% / 783 |
| 24/36 | -6.8% / -75% / -87% / 872 | -7.6% / -81% / -92% / 1130 | -7.4% / -80% / -91% / 1015 | -6.7% / -77% / -89% / 940 | -6.0% / -72% / -84% / 759 | -4.5% / -63% / -78% / 695 |
| 6/72 | -7.1% / -78% / -91% / 1091 | -7.1% / -80% / -92% / 1106 | -6.3% / -76% / -88% / 954 | -7.7% / -82% / -92% / 1030 | -4.1% / -61% / -79% / 839 | -4.2% / -61% / -79% / 770 |
| 12/72 | -4.4% / -62% / -81% / 884 | -5.7% / -73% / -88% / 1015 | -4.7% / -66% / -83% / 860 | -6.7% / -77% / -89% / 943 | -4.8% / -66% / -81% / 753 | -4.2% / -60% / -77% / 685 |
| 24/72 | -1.1% / -26% / -56% / 672 | -5.0% / -69% / -85% / 945 | -3.2% / -51% / -73% / 783 | -4.0% / -61% / -80% / 871 | -3.7% / -56% / -74% / 683 | -2.5% / -42% / -65% / 613 |
| 48/72 | -0.4% / -19% / -47% / 561 | -4.8% / -68% / -84% / 860 | -2.9% / -48% / -72% / 775 | -2.8% / -50% / -74% / 823 | -2.1% / -41% / -65% / 678 | -1.9% / -37% / -61% / 596 |
| 6/150 | -3.6% / -57% / -78% / 908 | -5.9% / -73% / -86% / 906 | -4.1% / -61% / -79% / 766 | -6.7% / -78% / -90% / 1067 | -4.2% / -63% / -80% / 812 | -4.0% / -61% / -78% / 740 |
| 12/150 | -2.2% / -42% / -67% / 724 | -3.8% / -59% / -78% / 837 | -3.4% / -53% / -73% / 691 | -3.7% / -59% / -80% / 938 | -3.3% / -54% / -73% / 729 | -2.3% / -42% / -66% / 654 |
| 24/150 | -1.1% / -27% / -54% / 584 | -2.6% / -47% / -71% / 778 | -2.9% / -47% / -69% / 642 | -3.4% / -56% / -77% / 853 | -2.5% / -46% / -68% / 685 | -2.1% / -39% / -63% / 602 |
| 48/150 | +0.3% / +1% / -35% / 470 | -2.8% / -49% / -71% / 737 | -3.0% / -50% / -69% / 622 | -3.4% / -55% / -76% / 780 | -3.0% / -51% / -70% / 657 | -1.7% / -35% / -58% / 559 |
| 6/300 | -1.6% / -30% / -61% / 757 | -3.5% / -52% / -73% / 715 |  |  | -2.5% / -43% / -69% / 759 | -3.0% / -48% / -70% / 667 |
| 12/300 | -1.9% / -37% / -60% / 587 | -3.5% / -54% / -73% / 665 |  |  | -2.4% / -44% / -68% / 712 | -2.8% / -46% / -67% / 609 |
| 24/300 | +1.2% / +13% / -22% / 448 | -1.5% / -34% / -60% / 639 |  |  | -1.3% / -32% / -60% / 679 | -0.7% / -21% / -50% / 579 |
| 48/300 | -0.0% / -11% / -34% / 382 | -2.5% / -44% / -66% / 605 |  |  | -1.8% / -38% / -62% / 638 | -1.9% / -36% / -59% / 552 |
| **average** | -2.9%; vs none +0.00 pt, better in 0/15 | -4.7%; vs none -1.89 pt, better in 2/15 | -4.6%; vs none -0.94 pt, better in 2/11 | -5.4%; vs none -1.70 pt, better in 2/11 | -3.6%; vs none -0.78 pt, better in 3/15 | -2.9%; vs none -0.09 pt, better in 5/15 |

**short**

| fast/slow | none | 2 x slow | 4 x slow | 200 | 480 | 720 |
|---|---|---|---|---|---|---|
| 6/36 | +0.9% / +2% / -55% / 1057 | +0.2% / -10% / -61% / 1119 | -0.5% / -21% / -65% / 1011 | +0.1% / -8% / -57% / 998 | +0.9% / +8% / -48% / 969 | +0.2% / -7% / -56% / 977 |
| 12/36 | -0.8% / -19% / -60% / 881 | -0.3% / -13% / -63% / 1090 | -1.4% / -30% / -65% / 926 | -1.0% / -21% / -60% / 893 | -0.7% / -19% / -58% / 845 | -0.8% / -18% / -59% / 846 |
| 24/36 | -1.1% / -18% / -55% / 747 | -0.8% / -22% / -65% / 1066 | -1.9% / -36% / -69% / 912 | -1.8% / -33% / -66% / 854 | -0.4% / -10% / -53% / 774 | -1.7% / -30% / -62% / 768 |
| 6/72 | -0.6% / -20% / -61% / 942 | -1.2% / -27% / -65% / 976 | +0.6% / -0% / -51% / 896 | -0.9% / -24% / -63% / 933 | +1.0% / +11% / -43% / 870 | +0.4% / +3% / -47% / 868 |
| 12/72 | +0.0% / -3% / -46% / 747 | -1.2% / -28% / -65% / 920 | -0.5% / -17% / -56% / 816 | -1.6% / -33% / -66% / 866 | -0.1% / -11% / -51% / 772 | -0.5% / -14% / -52% / 758 |
| 24/72 | +0.2% / -0% / -39% / 630 | -0.5% / -23% / -61% / 912 | +0.3% / -7% / -49% / 763 | +0.7% / +2% / -46% / 819 | -0.6% / -20% / -56% / 729 | -0.9% / -22% / -55% / 692 |
| 48/72 | -0.6% / -16% / -45% / 522 | +0.6% / -1% / -50% / 853 | -0.4% / -17% / -53% / 734 | -0.6% / -16% / -57% / 813 | -1.7% / -36% / -63% / 669 | -1.6% / -33% / -59% / 632 |
| 6/150 | +0.5% / +7% / -40% / 749 | +0.5% / -2% / -45% / 791 | +1.0% / +14% / -35% / 729 | -0.1% / -9% / -53% / 870 | +0.8% / +8% / -40% / 747 | +0.6% / +5% / -40% / 723 |
| 12/150 | +0.7% / +14% / -29% / 604 | +0.4% / -1% / -46% / 751 | +0.4% / +3% / -39% / 646 | +0.0% / -7% / -53% / 872 | -0.0% / -7% / -45% / 667 | +0.2% / +1% / -39% / 630 |
| 24/150 | +1.2% / +21% / -19% / 505 | -0.0% / -13% / -51% / 742 | +0.9% / +7% / -34% / 610 | -0.1% / -12% / -56% / 852 | +0.1% / -10% / -46% / 636 | +0.0% / -7% / -42% / 604 |
| 48/150 | -1.0% / -22% / -44% / 421 | +0.7% / +1% / -43% / 731 | +1.6% / +19% / -25% / 582 | -0.2% / -16% / -58% / 824 | +0.9% / +2% / -38% / 631 | +1.0% / +12% / -29% / 563 |
| 6/300 | +0.8% / +13% / -30% / 620 | +0.5% / +1% / -40% / 678 |  |  | +0.2% / -6% / -46% / 710 | +0.3% / -0% / -40% / 659 |
| 12/300 | +1.4% / +30% / -11% / 495 | +0.3% / -1% / -40% / 627 |  |  | -0.4% / -17% / -51% / 670 | +0.0% / -3% / -39% / 603 |
| 24/300 | +0.1% / -7% / -33% / 411 | +0.2% / -9% / -43% / 597 |  |  | -0.4% / -20% / -53% / 668 | -0.3% / -13% / -45% / 558 |
| 48/300 | -0.4% / -9% / -32% / 362 | -0.6% / -20% / -51% / 614 |  |  | +0.3% / -8% / -46% / 666 | -1.0% / -24% / -52% / 581 |
| **average** | +0.1%; vs none +0.00 pt, better in 0/15 | -0.1%; vs none -0.16 pt, better in 5/15 | +0.0%; vs none +0.06 pt, better in 5/11 | -0.5%; vs none -0.44 pt, better in 3/11 | -0.0%; vs none -0.10 pt, better in 7/15 | -0.3%; vs none -0.35 pt, better in 3/15 |

**both**

| fast/slow | none | 2 x slow | 4 x slow | 200 | 480 | 720 |
|---|---|---|---|---|---|---|
| 6/36 | -3.7% / -57% / -84% / 1270 | -5.2% / -65% / -88% / 1315 | -4.3% / -62% / -86% / 1253 | -2.8% / -52% / -83% / 1275 | -2.9% / -51% / -82% / 1266 | -1.1% / -33% / -74% / 1238 |
| 12/36 | -6.5% / -75% / -90% / 1246 | -4.2% / -58% / -83% / 1218 | -5.3% / -68% / -88% / 1219 | -4.0% / -59% / -85% / 1221 | -5.6% / -73% / -89% / 1197 | -2.1% / -39% / -76% / 1136 |
| 24/36 | -6.0% / -69% / -88% / 1147 | -5.4% / -69% / -88% / 1240 | -6.3% / -76% / -91% / 1229 | -4.3% / -62% / -86% / 1159 | -3.3% / -52% / -80% / 1115 | -3.6% / -55% / -81% / 1099 |
| 6/72 | -5.4% / -67% / -88% / 1277 | -4.9% / -66% / -87% / 1226 | -4.2% / -61% / -85% / 1195 | -3.7% / -57% / -84% / 1210 | -2.1% / -40% / -76% / 1184 | -1.4% / -33% / -73% / 1141 |
| 12/72 | -0.8% / -18% / -67% / 1141 | -4.3% / -61% / -85% / 1194 | -1.5% / -33% / -72% / 1120 | -1.7% / -35% / -75% / 1154 | -2.0% / -41% / -75% / 1109 | -2.9% / -50% / -78% / 1071 |
| 24/72 | -3.1% / -51% / -79% / 1038 | -1.3% / -32% / -73% / 1137 | -1.0% / -24% / -68% / 1047 | -0.5% / -14% / -65% / 1083 | -1.1% / -27% / -68% / 1047 | -0.7% / -21% / -65% / 1015 |
| 48/72 | +0.6% / -3% / -53% / 909 | -1.9% / -46% / -77% / 1087 | -2.4% / -44% / -77% / 1039 | -1.7% / -38% / -75% / 1077 | -3.7% / -59% / -81% / 1029 | -1.0% / -30% / -68% / 971 |
| 6/150 | +0.1% / -6% / -60% / 1089 | -1.5% / -34% / -73% / 1105 | -2.1% / -39% / -75% / 1079 | -2.7% / -44% / -77% / 1122 | -1.0% / -26% / -68% / 1089 | -1.3% / -31% / -71% / 1052 |
| 12/150 | +0.1% / -6% / -58% / 1017 | -0.3% / -14% / -62% / 1030 | -1.8% / -37% / -70% / 1010 | -2.5% / -45% / -76% / 1101 | -0.9% / -24% / -66% / 1013 | -0.9% / -25% / -66% / 991 |
| 24/150 | +0.7% / +4% / -50% / 916 | -2.3% / -43% / -75% / 1010 | -1.0% / -27% / -69% / 949 | -1.6% / -32% / -70% / 1051 | -0.9% / -23% / -64% / 967 | -0.4% / -17% / -59% / 921 |
| 48/150 | -0.9% / -21% / -57% / 786 | -3.8% / -58% / -82% / 1019 | -0.8% / -27% / -65% / 916 | -3.1% / -51% / -78% / 1008 | -0.5% / -18% / -60% / 933 | -0.6% / -23% / -62% / 880 |
| 6/300 | -0.4% / -10% / -57% / 984 | -3.1% / -48% / -77% / 1009 |  |  | +0.1% / +0% / -54% / 992 | -2.4% / -42% / -73% / 985 |
| 12/300 | +0.9% / +11% / -44% / 874 | -2.6% / -47% / -76% / 962 |  |  | -0.7% / -22% / -63% / 972 | -1.5% / -33% / -69% / 942 |
| 24/300 | +1.5% / +12% / -39% / 754 | -0.8% / -26% / -65% / 911 |  |  | -0.3% / -10% / -55% / 933 | +0.2% / -5% / -53% / 860 |
| 48/300 | -1.0% / -25% / -57% / 676 | -3.1% / -51% / -76% / 893 |  |  | +0.7% / +2% / -49% / 892 | -2.7% / -46% / -73% / 834 |
| **average** | -1.6%; vs none +0.00 pt, better in 0/15 | -3.0%; vs none -1.38 pt, better in 4/15 | -2.8%; vs none -0.55 pt, better in 4/11 | -2.6%; vs none -0.34 pt, better in 5/11 | -1.6%; vs none -0.02 pt, better in 8/15 | -1.5%; vs none +0.10 pt, better in 6/15 |

## E. Whipsaw and entry lag, signal level (every cross on every coin, exit on the opposite cross, default costs)

| side | fast/slow | signals | per coin per week | win rate | avg win | avg loss | mean net per trade | same, stress | sum of net returns | median hold (h) | winners: share of own swing gone at entry (median) | kept | given back before exit | hours from the low to entry | price already off the low | mean net by third | coins with positive sum |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long | 4/21 | 11305 | 5.61 | 22% | +4.7% | -1.7% | -0.29% | -0.55% | -33.2 | 8 | 28% | 28% | 39% | 6 | +3.1% | +0.08% / -0.30% / -0.63% | 6% |
| long | 9/21 | 7622 | 3.78 | 25% | +5.3% | -2.2% | -0.32% | -0.58% | -24.7 | 13 | 30% | 27% | 39% | 9 | +3.7% | +0.27% / -0.45% / -0.73% | 10% |
| long | 6/36 | 7031 | 3.49 | 23% | +5.6% | -2.1% | -0.38% | -0.63% | -26.4 | 12 | 28% | 25% | 42% | 9 | +3.9% | +0.16% / -0.50% / -0.75% | 10% |
| long | 12/36 | 5001 | 2.48 | 24% | +6.6% | -2.6% | -0.38% | -0.63% | -18.9 | 20 | 29% | 25% | 42% | 14 | +4.5% | +0.30% / -0.63% / -0.77% | 18% |
| long | 12/55 | 4003 | 1.99 | 23% | +7.3% | -2.8% | -0.46% | -0.71% | -18.4 | 24 | 28% | 24% | 43% | 16 | +4.9% | +0.16% / -0.68% / -0.83% | 16% |
| long | 18/72 | 2843 | 1.41 | 22% | +8.9% | -3.3% | -0.65% | -0.90% | -18.4 | 36 | 25% | 25% | 42% | 20 | +5.6% | -0.13% / -0.89% / -0.98% | 12% |
| long | 24/100 | 2086 | 1.03 | 20% | +11.4% | -3.9% | -0.78% | -1.04% | -16.4 | 44 | 26% | 26% | 43% | 28 | +6.7% | -0.12% / -0.91% / -1.40% | 16% |
| long | 36/150 | 1400 | 0.69 | 19% | +14.9% | -4.7% | -0.92% | -1.17% | -12.8 | 59 | 25% | 23% | 45% | 41 | +8.1% | +0.49% / -1.04% / -2.25% | 22% |
| long | 48/200 | 1082 | 0.54 | 20% | +16.2% | -5.6% | -1.14% | -1.39% | -12.4 | 67 | 26% | 22% | 47% | 53 | +9.5% | +1.09% / -1.54% / -2.98% | 22% |
| long | 72/300 | 647 | 0.33 | 22% | +24.7% | -6.8% | +0.09% | -0.16% | +0.6 | 100 | 27% | 20% | 49% | 81 | +11.3% | +6.99% / -4.21% / -3.47% | 24% |
| long | 72/480 | 426 | 0.24 | 19% | +29.6% | -6.8% | +0.24% | -0.02% | +1.0 | 148 | 29% | 16% | 49% | 136 | +16.9% | +10.80% / -4.59% / -4.73% | 22% |
| short | 4/21 | 11287 | 5.60 | 27% | +4.3% | -1.7% | -0.10% | -0.36% | -11.3 | 10 | 29% | 30% | 37% | 5 | +2.9% | -0.21% / +0.11% / -0.20% | 36% |
| short | 9/21 | 7600 | 3.77 | 31% | +4.8% | -2.2% | -0.02% | -0.28% | -1.8 | 17 | 32% | 30% | 35% | 8 | +3.7% | -0.15% / +0.14% / -0.07% | 50% |
| short | 6/36 | 7008 | 3.48 | 28% | +5.1% | -2.1% | -0.04% | -0.29% | -2.7 | 16 | 29% | 29% | 38% | 8 | +3.8% | -0.28% / +0.17% / -0.01% | 52% |
| short | 12/36 | 4977 | 2.47 | 33% | +5.5% | -2.6% | +0.09% | -0.17% | +4.4 | 26 | 33% | 27% | 37% | 11 | +4.7% | -0.32% / +0.26% / +0.31% | 62% |
| short | 12/55 | 3972 | 1.97 | 32% | +6.4% | -2.8% | +0.13% | -0.12% | +5.3 | 30 | 33% | 25% | 38% | 13 | +5.2% | -0.57% / +0.49% / +0.48% | 62% |
| short | 18/72 | 2806 | 1.39 | 31% | +8.0% | -3.3% | +0.21% | -0.05% | +5.9 | 44 | 32% | 25% | 38% | 19 | +6.3% | -1.04% / +0.77% / +1.06% | 60% |
| short | 24/100 | 2049 | 1.02 | 31% | +9.8% | -3.9% | +0.34% | +0.09% | +7.0 | 65 | 31% | 27% | 37% | 25 | +7.3% | -1.46% / +1.31% / +1.41% | 58% |
| short | 36/150 | 1366 | 0.68 | 33% | +12.5% | -5.0% | +0.68% | +0.42% | +9.3 | 90 | 30% | 29% | 35% | 34 | +8.3% | -1.83% / +2.34% / +1.74% | 66% |
| short | 48/200 | 1054 | 0.52 | 36% | +13.1% | -5.7% | +1.01% | +0.76% | +10.6 | 110 | 32% | 27% | 36% | 44 | +9.4% | -2.13% / +3.54% / +1.84% | 70% |
| short | 72/300 | 630 | 0.32 | 41% | +15.9% | -6.1% | +2.86% | +2.61% | +18.0 | 235 | 34% | 25% | 35% | 65 | +10.9% | -2.59% / +6.66% / +5.48% | 88% |
| short | 72/480 | 427 | 0.24 | 37% | +23.3% | -6.6% | +4.38% | +4.13% | +18.7 | 255 | 32% | 37% | 30% | 80 | +12.7% | -4.92% / +9.56% / +8.82% | 86% |

"Own swing" = from the lowest low since the fast EMA last crossed below (highest high for shorts) to the best price before the exit signal.

**Common yardstick: hindsight up-swings of at least 10% (zigzag on highs/lows). 1902 up-legs, median size +18% over 48 h.**

| fast/slow | up-legs with a buy signal inside | no signal at all (missed) | already long at the low | share of the leg gone at the first buy (median) | first buy after the midpoint | hours from the low | buy signals per coin per week | of which inside down-legs (false) | false per coin per week |
|---|---|---|---|---|---|---|---|---|---|
| 4/21 | 84% | 9% | 7% | 32% | 23% | 10 | 5.39 | 46% | 2.47 |
| 9/21 | 80% | 11% | 9% | 36% | 29% | 13 | 3.63 | 43% | 1.55 |
| 6/36 | 77% | 13% | 10% | 39% | 32% | 16 | 3.35 | 41% | 1.38 |
| 12/36 | 72% | 16% | 12% | 42% | 36% | 20 | 2.38 | 38% | 0.91 |
| 12/55 | 67% | 19% | 14% | 45% | 42% | 24 | 1.90 | 33% | 0.63 |
| 18/72 | 60% | 23% | 17% | 50% | 50% | 31 | 1.34 | 27% | 0.36 |
| 24/100 | 51% | 28% | 21% | 54% | 57% | 41 | 0.98 | 23% | 0.23 |
| 36/150 | 39% | 35% | 26% | 57% | 62% | 56 | 0.66 | 23% | 0.15 |
| 48/200 | 30% | 40% | 30% | 62% | 66% | 76 | 0.51 | 26% | 0.13 |
| 72/300 | 18% | 48% | 34% | 58% | 61% | 113 | 0.31 | 25% | 0.08 |
| 72/480 | 13% | 51% | 36% | 62% | 68% | 125 | 0.22 | 25% | 0.06 |

**Common yardstick: hindsight up-swings of at least 15% (zigzag on highs/lows). 877 up-legs, median size +27% over 95 h.**

| fast/slow | up-legs with a buy signal inside | no signal at all (missed) | already long at the low | share of the leg gone at the first buy (median) | first buy after the midpoint | hours from the low | buy signals per coin per week | of which inside down-legs (false) | false per coin per week |
|---|---|---|---|---|---|---|---|---|---|
| 4/21 | 90% | 5% | 5% | 25% | 18% | 11 | 5.08 | 52% | 2.63 |
| 9/21 | 88% | 6% | 6% | 29% | 21% | 14 | 3.42 | 50% | 1.72 |
| 6/36 | 86% | 6% | 7% | 32% | 23% | 18 | 3.16 | 48% | 1.52 |
| 12/36 | 83% | 9% | 8% | 34% | 26% | 22 | 2.24 | 46% | 1.03 |
| 12/55 | 80% | 11% | 9% | 38% | 31% | 27 | 1.78 | 42% | 0.75 |
| 18/72 | 76% | 13% | 12% | 41% | 39% | 37 | 1.25 | 36% | 0.44 |
| 24/100 | 69% | 17% | 14% | 47% | 45% | 50 | 0.91 | 31% | 0.29 |
| 36/150 | 59% | 23% | 18% | 51% | 51% | 74 | 0.61 | 29% | 0.18 |
| 48/200 | 51% | 30% | 20% | 55% | 55% | 103 | 0.47 | 29% | 0.14 |
| 72/300 | 34% | 42% | 24% | 54% | 54% | 150 | 0.28 | 25% | 0.07 |
| 72/480 | 24% | 49% | 27% | 61% | 64% | 157 | 0.21 | 24% | 0.05 |

**Common yardstick: hindsight up-swings of at least 25% (zigzag on highs/lows). 315 up-legs, median size +47% over 200 h.**

| fast/slow | up-legs with a buy signal inside | no signal at all (missed) | already long at the low | share of the leg gone at the first buy (median) | first buy after the midpoint | hours from the low | buy signals per coin per week | of which inside down-legs (false) | false per coin per week |
|---|---|---|---|---|---|---|---|---|---|
| 4/21 | 95% | 3% | 2% | 17% | 18% | 11 | 4.35 | 64% | 2.76 |
| 9/21 | 95% | 3% | 2% | 19% | 19% | 14 | 2.92 | 63% | 1.83 |
| 6/36 | 93% | 4% | 3% | 20% | 19% | 18 | 2.69 | 62% | 1.66 |
| 12/36 | 92% | 4% | 4% | 24% | 21% | 21 | 1.92 | 59% | 1.14 |
| 12/55 | 90% | 5% | 5% | 28% | 22% | 27 | 1.51 | 57% | 0.86 |
| 18/72 | 86% | 8% | 7% | 29% | 23% | 37 | 1.07 | 53% | 0.56 |
| 24/100 | 78% | 13% | 9% | 33% | 24% | 46 | 0.78 | 51% | 0.40 |
| 36/150 | 74% | 15% | 11% | 36% | 28% | 74 | 0.52 | 47% | 0.24 |
| 48/200 | 70% | 18% | 12% | 40% | 37% | 104 | 0.40 | 46% | 0.18 |
| 72/300 | 60% | 25% | 15% | 43% | 39% | 155 | 0.24 | 38% | 0.09 |
| 72/480 | 42% | 37% | 21% | 54% | 55% | 166 | 0.19 | 40% | 0.08 |

## F. Exits on identical entries

### F1. Signal level (every cross, every coin, same entries for every exit rule)

"Kept of peak" = sum of realised gross profit / sum of peak open profit over all trades. "Kept, trades that were up 2%+" = median of realised / peak for trades whose open profit reached 2%.


**Long entries, 9/21 cross, 7621 trades**

| exit | win rate | mean net per trade | same, stress | sum of net returns | median hold (h) | mean peak open profit | kept of peak | kept, trades that were up 2%+ | exits by stop | mean net by third |
|---|---|---|---|---|---|---|---|---|---|---|
| cross | 25% | -0.32% | -0.58% | -24.7 | 13 | 4.1% | -1% | +12% | 0% | +0.27% / -0.45% / -0.73% |
| cross+trail2 | 28% | -0.42% | -0.73% | -32.2 | 6 | 2.3% | -3% | +34% | 83% | -0.29% / -0.48% / -0.48% |
| cross+trail3 | 26% | -0.40% | -0.70% | -30.8 | 9 | 3.2% | -2% | +22% | 63% | -0.01% / -0.65% / -0.52% |
| cross+trail4 | 25% | -0.32% | -0.60% | -24.6 | 12 | 3.8% | -0% | +15% | 37% | +0.24% / -0.56% / -0.60% |
| trail1.5 | 28% | -0.42% | -0.74% | -31.7 | 4 | 1.9% | -3% | +41% | 100% | -0.38% / -0.39% / -0.48% |
| trail2 | 30% | -0.44% | -0.76% | -33.3 | 7 | 2.5% | -3% | +34% | 100% | -0.28% / -0.52% / -0.49% |
| trail3 | 31% | -0.43% | -0.76% | -33.1 | 13 | 3.7% | -2% | +22% | 99% | +0.11% / -0.75% / -0.62% |
| trail4 | 32% | -0.42% | -0.75% | -32.2 | 23 | 5.0% | -1% | +14% | 99% | +0.48% / -0.79% / -0.87% |
| trail6 | 31% | -0.75% | -1.07% | -57.1 | 42 | 7.1% | -5% | -1% | 99% | +0.41% / -0.89% / -1.65% |
| time12 | 41% | -0.51% | -0.76% | -38.9 | 13 | 2.6% | -9% | +50% | 0% | -0.03% / -0.76% / -0.70% |
| time24 | 43% | -0.54% | -0.79% | -41.1 | 25 | 3.8% | -7% | +44% | 0% | +0.31% / -0.89% / -0.96% |
| time48 | 43% | -0.81% | -1.06% | -61.7 | 49 | 5.4% | -10% | +31% | 0% | +0.26% / -1.17% / -1.41% |
| time96 | 38% | -1.35% | -1.60% | -103.1 | 97 | 7.6% | -14% | +6% | 0% | +0.39% / -1.73% / -2.55% |
| time168 | 38% | -2.00% | -2.25% | -152.7 | 169 | 10.1% | -17% | -3% | 0% | +0.83% / -3.35% / -3.24% |
| cross+time48 | 25% | -0.37% | -0.62% | -27.8 | 13 | 3.8% | -2% | +13% | 0% | +0.21% / -0.50% / -0.75% |

**Long entries, 24/100 cross, 2085 trades**

| exit | win rate | mean net per trade | same, stress | sum of net returns | median hold (h) | mean peak open profit | kept of peak | kept, trades that were up 2%+ | exits by stop | mean net by third |
|---|---|---|---|---|---|---|---|---|---|---|
| cross | 20% | -0.78% | -1.04% | -16.3 | 44 | 8.1% | -6% | -25% | 0% | -0.12% / -0.91% / -1.40% |
| cross+trail2 | 32% | -0.26% | -0.58% | -5.5 | 6 | 2.6% | +4% | +37% | 96% | -0.33% / -0.50% / +0.05% |
| cross+trail3 | 31% | -0.18% | -0.50% | -3.7 | 12 | 3.9% | +5% | +22% | 91% | +0.05% / -0.70% / +0.09% |
| cross+trail4 | 30% | -0.08% | -0.40% | -1.7 | 21 | 5.2% | +5% | +11% | 85% | +0.19% / -0.50% / +0.04% |
| trail1.5 | 31% | -0.31% | -0.63% | -6.4 | 3 | 2.0% | +3% | +45% | 100% | -0.39% / -0.47% / -0.05% |
| trail2 | 33% | -0.27% | -0.60% | -5.7 | 6 | 2.7% | +4% | +37% | 100% | -0.32% / -0.54% / +0.04% |
| trail3 | 32% | -0.20% | -0.52% | -4.2 | 13 | 4.1% | +4% | +22% | 100% | +0.07% / -0.79% / +0.09% |
| trail4 | 32% | -0.04% | -0.36% | -0.8 | 23 | 5.6% | +6% | +12% | 99% | +0.24% / -0.52% / +0.12% |
| trail6 | 31% | -0.25% | -0.57% | -5.2 | 40 | 7.9% | +1% | -2% | 98% | +0.08% / -0.31% / -0.55% |
| time12 | 43% | -0.37% | -0.62% | -7.7 | 13 | 2.9% | -3% | +48% | 0% | -0.13% / -0.80% / -0.21% |
| time24 | 43% | -0.18% | -0.43% | -3.7 | 25 | 4.2% | +3% | +41% | 0% | -0.02% / -0.46% / -0.07% |
| time48 | 40% | -0.73% | -0.98% | -15.2 | 49 | 5.9% | -8% | +20% | 0% | -0.35% / -0.96% / -0.93% |
| time96 | 39% | -0.87% | -1.12% | -18.2 | 97 | 8.3% | -7% | +5% | 0% | -0.02% / -1.16% / -1.53% |
| time168 | 41% | -1.36% | -1.62% | -28.5 | 169 | 10.8% | -10% | +3% | 0% | +0.65% / -2.54% / -2.44% |
| cross+time48 | 31% | -0.61% | -0.86% | -12.7 | 44 | 5.1% | -6% | +9% | 0% | -0.28% / -0.82% / -0.77% |

**Long entries, 48/200 cross, 1082 trades**

| exit | win rate | mean net per trade | same, stress | sum of net returns | median hold (h) | mean peak open profit | kept of peak | kept, trades that were up 2%+ | exits by stop | mean net by third |
|---|---|---|---|---|---|---|---|---|---|---|
| cross | 20% | -1.14% | -1.39% | -12.4 | 67 | 11.4% | -8% | -50% | 0% | +1.09% / -1.54% / -2.98% |
| cross+trail2 | 28% | -0.49% | -0.81% | -5.3 | 6 | 2.5% | -5% | +31% | 98% | -0.33% / -0.51% / -0.62% |
| cross+trail3 | 30% | -0.17% | -0.49% | -1.9 | 13 | 4.2% | +5% | +16% | 95% | +0.55% / -0.27% / -0.79% |
| cross+trail4 | 30% | -0.12% | -0.44% | -1.3 | 22 | 5.5% | +4% | +7% | 92% | +0.17% / +0.23% / -0.71% |
| trail1.5 | 26% | -0.45% | -0.77% | -4.9 | 3 | 1.9% | -5% | +40% | 100% | -0.45% / -0.32% / -0.57% |
| trail2 | 28% | -0.50% | -0.82% | -5.4 | 6 | 2.5% | -5% | +31% | 100% | -0.34% / -0.52% / -0.63% |
| trail3 | 31% | -0.17% | -0.49% | -1.8 | 14 | 4.2% | +5% | +17% | 99% | +0.56% / -0.27% / -0.79% |
| trail4 | 31% | -0.15% | -0.47% | -1.6 | 23 | 5.6% | +4% | +7% | 99% | +0.14% / +0.20% / -0.75% |
| trail6 | 28% | -0.52% | -0.84% | -5.6 | 40 | 7.7% | -2% | -14% | 97% | -0.42% / +0.24% / -1.29% |
| time12 | 42% | -0.28% | -0.53% | -3.0 | 13 | 3.0% | +0% | +52% | 0% | +0.01% / -0.07% / -0.74% |
| time24 | 40% | -0.39% | -0.64% | -4.2 | 25 | 4.2% | -2% | +36% | 0% | +0.01% / +0.18% / -1.28% |
| time48 | 36% | -1.31% | -1.56% | -14.1 | 49 | 5.8% | -18% | +8% | 0% | -1.33% / -0.68% / -1.84% |
| time96 | 36% | -1.82% | -2.07% | -19.7 | 97 | 7.7% | -20% | -2% | 0% | -1.55% / -2.18% / -1.76% |
| time168 | 38% | -1.86% | -2.10% | -20.1 | 169 | 10.4% | -15% | -10% | 0% | -0.33% / -2.59% / -2.70% |
| cross+time48 | 33% | -0.96% | -1.21% | -10.4 | 49 | 5.5% | -12% | +5% | 0% | -0.74% / -0.30% / -1.76% |

**Short entries, 9/21 cross, 7600 trades**

| exit | win rate | mean net per trade | same, stress | sum of net returns | median hold (h) | mean peak open profit | kept of peak | kept, trades that were up 2%+ | exits by stop | mean net by third |
|---|---|---|---|---|---|---|---|---|---|---|
| cross | 31% | -0.02% | -0.28% | -1.8 | 17 | 4.4% | +6% | +20% | 0% | -0.15% / +0.14% / -0.07% |
| cross+trail2 | 31% | -0.30% | -0.61% | -22.4 | 6 | 2.6% | +2% | +35% | 85% | -0.37% / -0.08% / -0.44% |
| cross+trail3 | 31% | -0.11% | -0.42% | -8.5 | 11 | 3.6% | +6% | +26% | 68% | -0.16% / +0.04% / -0.22% |
| cross+trail4 | 30% | -0.02% | -0.31% | -1.8 | 14 | 4.2% | +7% | +19% | 40% | -0.15% / +0.22% / -0.14% |
| trail1.5 | 32% | -0.32% | -0.64% | -24.2 | 4 | 2.1% | +2% | +42% | 100% | -0.34% / -0.22% / -0.39% |
| trail2 | 33% | -0.29% | -0.62% | -22.0 | 7 | 2.7% | +3% | +35% | 100% | -0.40% / -0.07% / -0.40% |
| trail3 | 36% | -0.09% | -0.41% | -6.5 | 15 | 4.1% | +7% | +26% | 100% | -0.27% / +0.08% / -0.07% |
| trail4 | 39% | +0.17% | -0.15% | +13.1 | 25 | 5.5% | +10% | +22% | 100% | -0.36% / +0.62% / +0.22% |
| trail6 | 42% | +0.47% | +0.14% | +35.5 | 49 | 7.8% | +11% | +20% | 99% | -0.65% / +1.51% / +0.47% |
| time12 | 49% | -0.06% | -0.32% | -4.6 | 13 | 2.9% | +8% | +59% | 0% | -0.07% / +0.17% / -0.28% |
| time24 | 51% | +0.16% | -0.10% | +12.0 | 25 | 4.1% | +11% | +53% | 0% | +0.07% / +0.26% / +0.13% |
| time48 | 57% | +0.57% | +0.32% | +43.6 | 49 | 6.1% | +14% | +52% | 0% | +0.08% / +0.80% / +0.80% |
| time96 | 58% | +0.86% | +0.61% | +65.5 | 97 | 8.7% | +13% | +39% | 0% | -0.88% / +1.73% / +1.61% |
| time168 | 58% | +1.48% | +1.23% | +112.4 | 169 | 11.6% | +15% | +37% | 0% | -1.43% / +3.30% / +2.36% |
| cross+time48 | 31% | +0.04% | -0.22% | +2.7 | 17 | 4.1% | +8% | +20% | 0% | +0.10% / +0.14% / -0.12% |

**Short entries, 24/100 cross, 2049 trades**

| exit | win rate | mean net per trade | same, stress | sum of net returns | median hold (h) | mean peak open profit | kept of peak | kept, trades that were up 2%+ | exits by stop | mean net by third |
|---|---|---|---|---|---|---|---|---|---|---|
| cross | 31% | +0.34% | +0.09% | +7.0 | 65 | 9.0% | +7% | -8% | 0% | -1.46% / +1.31% / +1.41% |
| cross+trail2 | 30% | -0.32% | -0.65% | -6.6 | 8 | 2.7% | +2% | +31% | 96% | -0.25% / -0.37% / -0.37% |
| cross+trail3 | 35% | -0.19% | -0.51% | -3.8 | 16 | 3.9% | +5% | +27% | 93% | -0.10% / -0.27% / -0.19% |
| cross+trail4 | 37% | -0.04% | -0.36% | -0.9 | 25 | 5.0% | +6% | +21% | 89% | -0.45% / +0.27% / +0.10% |
| trail1.5 | 30% | -0.33% | -0.65% | -6.7 | 5 | 2.1% | +2% | +36% | 100% | -0.20% / -0.42% / -0.37% |
| trail2 | 31% | -0.33% | -0.65% | -6.7 | 8 | 2.7% | +2% | +31% | 100% | -0.25% / -0.37% / -0.38% |
| trail3 | 36% | -0.20% | -0.52% | -4.1 | 17 | 4.0% | +4% | +27% | 100% | -0.11% / -0.27% / -0.23% |
| trail4 | 40% | -0.00% | -0.33% | -0.1 | 27 | 5.3% | +7% | +22% | 100% | -0.49% / +0.40% / +0.15% |
| trail6 | 41% | +0.35% | +0.03% | +7.3 | 51 | 7.5% | +10% | +15% | 99% | -1.01% / +2.17% / +0.05% |
| time12 | 48% | +0.01% | -0.25% | +0.1 | 13 | 2.8% | +10% | +59% | 0% | +0.28% / -0.13% / -0.17% |
| time24 | 50% | +0.06% | -0.19% | +1.3 | 25 | 3.9% | +9% | +48% | 0% | -0.01% / +0.30% / -0.09% |
| time48 | 54% | +0.01% | -0.25% | +0.1 | 49 | 5.5% | +5% | +44% | 0% | -1.26% / +0.86% / +0.58% |
| time96 | 52% | -0.09% | -0.35% | -1.9 | 97 | 8.5% | +2% | +30% | 0% | -1.66% / +1.23% / +0.35% |
| time168 | 55% | +0.50% | +0.24% | +10.1 | 169 | 11.6% | +7% | +35% | 0% | -3.03% / +4.04% / +0.89% |
| cross+time48 | 46% | +0.10% | -0.16% | +2.0 | 49 | 5.0% | +8% | +43% | 0% | -0.42% / +0.52% / +0.26% |

**Short entries, 48/200 cross, 1054 trades**

| exit | win rate | mean net per trade | same, stress | sum of net returns | median hold (h) | mean peak open profit | kept of peak | kept, trades that were up 2%+ | exits by stop | mean net by third |
|---|---|---|---|---|---|---|---|---|---|---|
| cross | 36% | +1.01% | +0.76% | +10.6 | 110 | 12.8% | +10% | +3% | 0% | -2.13% / +3.54% / +1.84% |
| cross+trail2 | 31% | -0.39% | -0.72% | -4.1 | 7 | 2.7% | -1% | +34% | 98% | -0.47% / -0.12% / -0.58% |
| cross+trail3 | 32% | -0.39% | -0.71% | -4.1 | 15 | 3.8% | -1% | +25% | 96% | -0.71% / -0.05% / -0.38% |
| cross+trail4 | 34% | -0.25% | -0.57% | -2.6 | 24 | 5.0% | +2% | +18% | 94% | -1.01% / +0.80% / -0.45% |
| trail1.5 | 28% | -0.35% | -0.68% | -3.7 | 4 | 2.1% | +1% | +42% | 100% | -0.28% / -0.23% / -0.54% |
| trail2 | 31% | -0.39% | -0.72% | -4.1 | 8 | 2.7% | -1% | +34% | 100% | -0.47% / -0.13% / -0.56% |
| trail3 | 33% | -0.38% | -0.71% | -4.0 | 16 | 3.8% | -0% | +25% | 100% | -0.67% / -0.07% / -0.38% |
| trail4 | 35% | -0.21% | -0.53% | -2.2 | 25 | 5.1% | +3% | +18% | 100% | -0.98% / +0.89% / -0.46% |
| trail6 | 38% | +0.23% | -0.09% | +2.4 | 49 | 7.6% | +8% | +13% | 99% | -1.44% / +3.06% / -0.73% |
| time12 | 44% | -0.17% | -0.43% | -1.8 | 13 | 2.7% | +4% | +57% | 0% | -0.22% / +0.19% / -0.47% |
| time24 | 47% | -0.08% | -0.34% | -0.9 | 25 | 4.0% | +5% | +48% | 0% | -0.37% / +0.59% / -0.43% |
| time48 | 50% | +0.14% | -0.11% | +1.5 | 49 | 6.1% | +7% | +38% | 0% | -0.92% / +1.85% / -0.39% |
| time96 | 54% | +0.51% | +0.25% | +5.3 | 97 | 9.1% | +9% | +36% | 0% | -0.58% / +2.61% / -0.37% |
| time168 | 62% | +1.96% | +1.71% | +20.6 | 169 | 12.0% | +19% | +47% | 0% | -1.38% / +6.85% / +0.75% |
| cross+time48 | 45% | -0.05% | -0.31% | -0.6 | 49 | 5.6% | +4% | +37% | 0% | -1.01% / +1.53% / -0.58% |

### F2. Portfolio level (4 slots, fresh 3; the slot limit means entries are no longer identical) (192 variants)


**9/21 long**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | -67% | 81% | -3.1% | -7.1% | +5% / -12% / -64% | 1095 | 22% | 20 | -84% |
| cross + trail 2 ATR | -95% | 96% | -10.7% | -11.7% | -59% / -66% / -65% | 2411 | 25% | 6 | -99% |
| cross + trail 3 ATR | -86% | 89% | -6.7% | -8.8% | -37% / -47% / -59% | 1610 | 23% | 11 | -96% |
| cross + trail 4 ATR | -70% | 80% | -3.7% | -5.5% | -14% / -6% / -63% | 1270 | 23% | 16 | -88% |
| cross + trail 6 ATR | -59% | 80% | -2.4% | -6.1% | -6% / +15% / -63% | 1114 | 22% | 19 | -80% |
| cross + fixed stop 3 ATR | -72% | 82% | -3.8% | -7.3% | -6% / -17% / -64% | 1127 | 22% | 19 | -87% |
| trail 2 ATR only | -95% | 96% | -10.8% | -11.9% | -58% / -67% / -66% | 2228 | 27% | 7 | -99% |
| trail 3 ATR only | -82% | 86% | -5.6% | -7.2% | -31% / -43% / -53% | 1281 | 28% | 15 | -94% |
| trail 4 ATR only | -55% | 74% | -2.2% | -3.0% | -11% / +3% / -51% | 819 | 29% | 27 | -77% |
| trail 6 ATR only | -73% | 77% | -4.3% | -4.6% | -28% / -18% / -55% | 468 | 31% | 51 | -82% |
| time 24h only | -71% | 76% | -3.8% | -5.3% | -36% / +31% / -65% | 948 | 42% | 25 | -84% |
| time 48h only | -50% | 69% | -2.0% | -2.3% | -3% / +19% / -57% | 524 | 42% | 49 | -64% |
| time 96h only | -13% | 60% | +0.1% | -1.9% | +12% / +8% / -29% | 270 | 42% | 97 | -27% |
| time 168h only | -28% | 65% | -0.9% | -1.3% | +27% / -19% / -31% | 156 | 48% | 169 | -36% |
| cross + trail 3 + time 48h | -87% | 89% | -6.9% | -8.9% | -37% / -49% / -59% | 1626 | 23% | 11 | -96% |
| cross + trail 3 + time 96h | -86% | 89% | -6.7% | -8.8% | -37% / -47% / -59% | 1610 | 23% | 11 | -96% |

**9/21 short**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | -32% | 60% | -0.7% | -1.8% | -35% / -11% / +18% | 1027 | 28% | 22 | -66% |
| cross + trail 2 ATR | -80% | 80% | -5.4% | -5.5% | -59% / -32% / -26% | 2070 | 29% | 8 | -96% |
| cross + trail 3 ATR | -47% | 63% | -1.9% | -3.2% | -39% / -11% / -3% | 1394 | 28% | 14 | -82% |
| cross + trail 4 ATR | -36% | 56% | -0.9% | -2.5% | -38% / +10% / -6% | 1129 | 28% | 19 | -72% |
| cross + trail 6 ATR | -36% | 60% | -1.0% | -2.5% | -37% / -9% / +13% | 1040 | 28% | 22 | -68% |
| cross + fixed stop 3 ATR | -32% | 57% | -0.7% | -2.4% | -36% / -0% / +6% | 1049 | 27% | 22 | -67% |
| trail 2 ATR only | -75% | 76% | -4.5% | -4.7% | -60% / -26% / -13% | 1856 | 34% | 10 | -95% |
| trail 3 ATR only | -33% | 54% | -0.8% | -2.1% | -35% / -3% / +7% | 1099 | 35% | 19 | -74% |
| trail 4 ATR only | -42% | 55% | -1.4% | -2.4% | -32% / -10% / -5% | 767 | 36% | 30 | -70% |
| trail 6 ATR only | +1% | 48% | +0.5% | -0.3% | -30% / +15% / +26% | 422 | 39% | 59 | -29% |
| time 24h only | -50% | 66% | -2.2% | -2.5% | -37% / -24% / +3% | 966 | 50% | 25 | -74% |
| time 48h only | -46% | 67% | -1.3% | -2.8% | -40% / -12% / +1% | 525 | 53% | 49 | -63% |
| time 96h only | -10% | 64% | +0.6% | -0.1% | -43% / +34% / +18% | 270 | 54% | 97 | -25% |
| time 168h only | +4% | 38% | +0.7% | -0.3% | +3% / -15% / +19% | 156 | 56% | 169 | -6% |
| cross + trail 3 + time 48h | -53% | 66% | -2.4% | -3.6% | -43% / -15% / -4% | 1441 | 28% | 14 | -84% |
| cross + trail 3 + time 96h | -48% | 63% | -1.9% | -3.2% | -39% / -11% / -3% | 1394 | 28% | 14 | -82% |

**9/21 both**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | +14% | 54% | +0.7% | +0.5% | +20% / +22% / -23% | 939 | 36% | 29 | -36% |
| cross + trail 2 ATR | -94% | 94% | -9.7% | -10.7% | -70% / -48% / -58% | 2900 | 29% | 8 | -99% |
| cross + trail 3 ATR | -77% | 88% | -5.0% | -5.2% | -28% / -51% / -34% | 1617 | 31% | 15 | -94% |
| cross + trail 4 ATR | -60% | 71% | -2.8% | -5.3% | -31% / +24% / -53% | 1215 | 30% | 21 | -83% |
| cross + trail 6 ATR | +25% | 59% | +1.3% | +0.3% | +18% / +64% / -36% | 954 | 36% | 28 | -32% |
| cross + fixed stop 3 ATR | -13% | 60% | -0.3% | +0.4% | +25% / -12% / -21% | 986 | 33% | 27 | -54% |
| trail 2 ATR only | -93% | 94% | -9.6% | -10.3% | -71% / -45% / -58% | 2773 | 30% | 8 | -99% |
| trail 3 ATR only | -59% | 79% | -2.7% | -2.7% | -22% / -33% / -22% | 1437 | 33% | 17 | -87% |
| trail 4 ATR only | +22% | 46% | +1.7% | -1.4% | +0% / +57% / -22% | 886 | 37% | 29 | -38% |
| trail 6 ATR only | -20% | 64% | -0.5% | -0.5% | -28% / +4% / +7% | 468 | 38% | 56 | -45% |
| time 24h only | -52% | 65% | -2.5% | -1.6% | +17% / -40% / -31% | 1049 | 47% | 25 | -76% |
| time 48h only | -58% | 69% | -2.9% | -3.1% | -26% / -48% / +8% | 544 | 47% | 49 | -71% |
| time 96h only | +87% | 38% | +2.8% | +3.1% | +28% / -10% / +62% | 276 | 50% | 97 | +56% |
| time 168h only | +13% | 42% | +0.9% | +0.4% | -27% / +21% / +27% | 157 | 56% | 169 | +2% |
| cross + trail 3 + time 48h | -76% | 86% | -4.8% | -6.1% | -37% / -38% / -38% | 1671 | 30% | 15 | -94% |
| cross + trail 3 + time 96h | -77% | 88% | -5.0% | -5.2% | -28% / -51% / -34% | 1615 | 31% | 16 | -94% |

**24/100 long**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | -11% | 62% | +0.9% | -2.1% | +32% / -19% / -16% | 288 | 23% | 71 | -25% |
| cross + trail 2 ATR | -58% | 66% | -3.0% | -3.2% | -7% / -35% / -29% | 1199 | 31% | 7 | -84% |
| cross + trail 3 ATR | -20% | 50% | -0.3% | -2.5% | +12% / -18% / -14% | 768 | 30% | 14 | -57% |
| cross + trail 4 ATR | +34% | 43% | +2.0% | -0.8% | +7% / +13% / +11% | 555 | 31% | 24 | -13% |
| cross + trail 6 ATR | -8% | 52% | +0.7% | -1.5% | +8% / -13% / -2% | 405 | 28% | 43 | -33% |
| cross + fixed stop 3 ATR | -27% | 70% | +0.1% | -2.4% | +34% / -33% / -19% | 315 | 21% | 62 | -42% |
| trail 2 ATR only | -59% | 66% | -3.1% | -3.0% | -10% / -36% / -28% | 1177 | 32% | 7 | -85% |
| trail 3 ATR only | -20% | 50% | -0.3% | -1.9% | +9% / -21% / -8% | 731 | 32% | 15 | -56% |
| trail 4 ATR only | +25% | 49% | +1.8% | -0.7% | +3% / +6% / +15% | 514 | 34% | 28 | -18% |
| trail 6 ATR only | -27% | 54% | -0.4% | -1.9% | -10% / -10% / -10% | 342 | 33% | 54 | -46% |
| time 24h only | +27% | 50% | +1.8% | -1.9% | +14% / +30% / -15% | 617 | 44% | 25 | -14% |
| time 48h only | -51% | 70% | -2.5% | -3.2% | -6% / -34% / -22% | 407 | 40% | 49 | -63% |
| time 96h only | -55% | 75% | -2.5% | -3.5% | +5% / -41% / -27% | 241 | 41% | 97 | -62% |
| time 168h only | -70% | 82% | -3.7% | -3.5% | +23% / -56% / -45% | 148 | 39% | 169 | -73% |
| cross + trail 3 + time 48h | -24% | 49% | -0.5% | -2.5% | +8% / -18% / -15% | 773 | 30% | 14 | -59% |
| cross + trail 3 + time 96h | -20% | 50% | -0.3% | -2.5% | +12% / -18% / -14% | 768 | 30% | 14 | -57% |

**24/100 short**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | +12% | 37% | +0.9% | +0.3% | -20% / +31% / +7% | 254 | 29% | 88 | -6% |
| cross + trail 2 ATR | -27% | 35% | -1.0% | -1.4% | -6% / +10% / -29% | 990 | 33% | 9 | -68% |
| cross + trail 3 ATR | +24% | 24% | +1.1% | +0.3% | +11% / +22% / -8% | 669 | 37% | 18 | -27% |
| cross + trail 4 ATR | +53% | 23% | +2.0% | +1.7% | +7% / +36% / +5% | 514 | 37% | 29 | +1% |
| cross + trail 6 ATR | +27% | 30% | +1.3% | +1.3% | -3% / +26% / +3% | 383 | 37% | 48 | -7% |
| cross + fixed stop 3 ATR | +7% | 40% | +0.7% | -0.2% | -22% / +35% / +2% | 282 | 27% | 77 | -13% |
| trail 2 ATR only | -26% | 35% | -1.0% | -1.2% | -5% / +7% / -28% | 973 | 34% | 10 | -68% |
| trail 3 ATR only | +21% | 24% | +1.0% | +0.4% | +7% / +24% / -9% | 644 | 39% | 19 | -28% |
| trail 4 ATR only | +56% | 27% | +2.1% | +1.6% | +8% / +46% / -1% | 473 | 41% | 33 | +5% |
| trail 6 ATR only | +24% | 31% | +1.3% | +0.8% | -6% / +27% / +5% | 319 | 43% | 60 | -5% |
| time 24h only | +3% | 41% | +0.4% | +0.1% | +4% / +3% / -3% | 597 | 50% | 25 | -31% |
| time 48h only | +25% | 28% | +1.2% | +1.5% | +18% / +0% / +6% | 376 | 52% | 49 | -3% |
| time 96h only | +28% | 55% | +1.7% | +0.5% | -22% / +44% / +13% | 234 | 53% | 97 | +9% |
| time 168h only | -3% | 58% | +0.6% | +0.7% | -37% / +28% / +20% | 144 | 50% | 169 | -12% |
| cross + trail 3 + time 48h | +29% | 23% | +1.2% | +0.7% | +14% / +23% / -9% | 678 | 37% | 18 | -25% |
| cross + trail 3 + time 96h | +24% | 24% | +1.1% | +0.3% | +11% / +22% / -8% | 669 | 37% | 18 | -27% |

**24/100 both**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | -56% | 60% | -2.7% | -4.0% | -50% / +0% / -12% | 303 | 23% | 88 | -63% |
| cross + trail 2 ATR | -65% | 72% | -3.5% | -3.3% | -12% / -26% / -47% | 1961 | 32% | 8 | -93% |
| cross + trail 3 ATR | +17% | 54% | +1.4% | +0.4% | +42% / -6% / -12% | 1180 | 34% | 17 | -54% |
| cross + trail 4 ATR | +135% | 37% | +4.4% | +1.5% | +18% / +84% / +9% | 786 | 37% | 29 | +33% |
| cross + trail 6 ATR | +103% | 52% | +3.9% | +3.3% | -10% / +58% / +43% | 490 | 36% | 50 | +39% |
| cross + fixed stop 3 ATR | -42% | 57% | -1.2% | -4.1% | -33% / -13% / -1% | 360 | 24% | 74 | -55% |
| trail 2 ATR only | -66% | 72% | -3.7% | -3.1% | -11% / -31% / -45% | 1943 | 32% | 8 | -93% |
| trail 3 ATR only | +25% | 50% | +1.7% | +0.7% | +46% / -7% / -8% | 1135 | 35% | 18 | -51% |
| trail 4 ATR only | +163% | 36% | +4.7% | +1.6% | +27% / +80% / +15% | 736 | 39% | 31 | +39% |
| trail 6 ATR only | -36% | 57% | -1.2% | -2.0% | -21% / -11% / -10% | 450 | 36% | 55 | -56% |
| time 24h only | +48% | 47% | +2.1% | -0.1% | +16% / +29% / -1% | 865 | 46% | 25 | -15% |
| time 48h only | -31% | 57% | -1.2% | -0.7% | -33% / -17% / +24% | 487 | 45% | 49 | -50% |
| time 96h only | -76% | 79% | -5.3% | -5.4% | -38% / -35% / -41% | 259 | 44% | 97 | -80% |
| time 168h only | -51% | 59% | -2.3% | -1.4% | -48% / -1% / -5% | 155 | 50% | 169 | -55% |
| cross + trail 3 + time 48h | +15% | 50% | +1.4% | +0.3% | +25% / +7% / -14% | 1193 | 34% | 16 | -55% |
| cross + trail 3 + time 96h | +17% | 54% | +1.4% | +0.4% | +42% / -6% / -12% | 1180 | 34% | 17 | -54% |

**24/200 long**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | -13% | 59% | +0.5% | -2.9% | +12% / -6% / -17% | 209 | 20% | 96 | -24% |
| cross + trail 2 ATR | -53% | 62% | -2.6% | -2.8% | -1% / -31% / -30% | 972 | 30% | 7 | -78% |
| cross + trail 3 ATR | +6% | 39% | +0.8% | -2.8% | +17% / +11% / -19% | 651 | 32% | 15 | -36% |
| cross + trail 4 ATR | +66% | 45% | +2.7% | -0.2% | +48% / +43% / -21% | 500 | 31% | 24 | +13% |
| cross + trail 6 ATR | +4% | 45% | +0.8% | -2.3% | +7% / +11% / -12% | 349 | 28% | 44 | -20% |
| cross + fixed stop 3 ATR | -25% | 59% | -0.1% | -3.0% | +20% / -27% / -14% | 242 | 17% | 78 | -37% |
| trail 2 ATR only | -52% | 61% | -2.5% | -3.0% | -4% / -31% / -28% | 959 | 31% | 8 | -78% |
| trail 3 ATR only | +10% | 38% | +0.9% | -2.4% | +15% / +14% / -16% | 627 | 34% | 16 | -34% |
| trail 4 ATR only | +78% | 43% | +3.0% | +0.4% | +44% / +45% / -15% | 463 | 33% | 28 | +23% |
| trail 6 ATR only | +16% | 47% | +1.2% | -1.1% | +12% / +9% / -5% | 295 | 33% | 55 | -9% |
| time 24h only | +43% | 43% | +2.2% | -0.9% | +21% / +25% / -6% | 533 | 45% | 25 | +1% |
| time 48h only | -27% | 63% | -0.6% | -1.0% | +17% / -18% / -24% | 358 | 46% | 49 | -42% |
| time 96h only | +16% | 56% | +1.4% | +1.6% | +49% / -10% / -14% | 223 | 46% | 97 | +0% |
| time 168h only | -65% | 75% | -3.4% | -3.4% | -5% / -47% / -31% | 143 | 35% | 169 | -68% |
| cross + trail 3 + time 48h | -0% | 41% | +0.5% | -2.6% | +13% / +12% / -21% | 658 | 32% | 14 | -40% |
| cross + trail 3 + time 96h | +6% | 39% | +0.8% | -2.8% | +17% / +11% / -19% | 651 | 32% | 15 | -36% |

**24/200 short**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | +42% | 35% | +1.9% | +1.0% | -9% / +17% / +33% | 162 | 28% | 137 | +28% |
| cross + trail 2 ATR | -33% | 42% | -1.4% | -2.2% | +2% / -3% / -32% | 840 | 32% | 9 | -66% |
| cross + trail 3 ATR | +5% | 26% | +0.4% | -0.6% | +13% / +16% / -19% | 569 | 36% | 19 | -33% |
| cross + trail 4 ATR | +9% | 23% | +0.7% | -1.1% | +8% / +8% / -6% | 452 | 36% | 29 | -23% |
| cross + trail 6 ATR | +87% | 21% | +3.1% | +2.6% | +12% / +47% / +13% | 311 | 41% | 55 | +48% |
| cross + fixed stop 3 ATR | +29% | 41% | +1.6% | -0.0% | -18% / +26% / +25% | 181 | 25% | 120 | +13% |
| trail 2 ATR only | -34% | 42% | -1.5% | -2.2% | +1% / -5% / -31% | 834 | 33% | 10 | -67% |
| trail 3 ATR only | +3% | 28% | +0.4% | -0.7% | +17% / +10% / -19% | 549 | 38% | 20 | -34% |
| trail 4 ATR only | +2% | 26% | +0.4% | -1.0% | +9% / +3% / -9% | 424 | 38% | 32 | -28% |
| trail 6 ATR only | +69% | 25% | +2.6% | +2.6% | +9% / +32% / +18% | 267 | 48% | 66 | +39% |
| time 24h only | -17% | 49% | -0.3% | -0.2% | -6% / +2% / -13% | 527 | 50% | 25 | -41% |
| time 48h only | +4% | 55% | +0.7% | +0.3% | -13% / +22% / -3% | 348 | 53% | 49 | -17% |
| time 96h only | +32% | 56% | +1.8% | +1.6% | -22% / +28% / +33% | 217 | 57% | 97 | +15% |
| time 168h only | +36% | 60% | +2.1% | +2.0% | -25% / +38% / +31% | 138 | 61% | 169 | +24% |
| cross + trail 3 + time 48h | +7% | 26% | +0.5% | -0.6% | +12% / +18% / -19% | 578 | 35% | 18 | -32% |
| cross + trail 3 + time 96h | +5% | 26% | +0.4% | -0.6% | +13% / +16% / -19% | 569 | 36% | 19 | -33% |

**24/200 both**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | +31% | 25% | +1.6% | +1.3% | +2% / +9% / +18% | 172 | 30% | 152 | +17% |
| cross + trail 2 ATR | -62% | 71% | -3.4% | -3.5% | +7% / -29% / -50% | 1671 | 31% | 8 | -90% |
| cross + trail 3 ATR | +58% | 42% | +2.5% | +1.7% | +30% / +37% / -12% | 1037 | 36% | 17 | -31% |
| cross + trail 4 ATR | +107% | 45% | +3.7% | +2.6% | +40% / +60% / -8% | 769 | 36% | 27 | +13% |
| cross + trail 6 ATR | +59% | 25% | +2.2% | +1.4% | +12% / +45% / -2% | 430 | 36% | 55 | +17% |
| cross + fixed stop 3 ATR | +15% | 32% | +1.3% | +0.6% | +4% / +15% / -4% | 229 | 24% | 115 | -2% |
| trail 2 ATR only | -64% | 72% | -3.6% | -3.9% | +1% / -33% / -47% | 1661 | 32% | 9 | -91% |
| trail 3 ATR only | +28% | 46% | +1.6% | +0.6% | +39% / +27% / -27% | 1023 | 36% | 18 | -44% |
| trail 4 ATR only | +40% | 46% | +2.1% | +0.8% | +24% / +43% / -21% | 741 | 36% | 28 | -22% |
| trail 6 ATR only | +90% | 27% | +3.1% | +1.7% | +8% / +70% / +3% | 400 | 40% | 60 | +39% |
| time 24h only | +28% | 36% | +1.6% | -0.4% | -3% / +37% / -4% | 794 | 47% | 25 | -23% |
| time 48h only | -59% | 69% | -2.5% | -2.2% | -33% / -23% / -21% | 458 | 45% | 49 | -69% |
| time 96h only | -20% | 48% | -0.3% | +0.0% | +9% / +0% / -27% | 249 | 46% | 97 | -31% |
| time 168h only | -35% | 45% | -1.3% | -1.3% | -12% / -24% / -3% | 151 | 46% | 169 | -41% |
| cross + trail 3 + time 48h | +48% | 41% | +2.2% | +1.4% | +25% / +41% / -15% | 1049 | 36% | 17 | -35% |
| cross + trail 3 + time 96h | +58% | 42% | +2.5% | +1.7% | +30% / +37% / -12% | 1037 | 36% | 17 | -31% |

**48/200 long**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | +56% | 63% | +3.6% | -2.5% | +16% / +92% / -30% | 157 | 21% | 129 | +42% |
| cross + trail 2 ATR | -45% | 56% | -1.7% | -2.1% | +0% / -7% / -41% | 809 | 30% | 7 | -71% |
| cross + trail 3 ATR | -15% | 52% | -0.1% | -1.1% | +3% / +42% / -42% | 535 | 30% | 15 | -45% |
| cross + trail 4 ATR | +26% | 48% | +1.6% | -0.8% | +7% / +72% / -32% | 399 | 30% | 25 | -8% |
| cross + trail 6 ATR | +19% | 51% | +1.5% | -0.6% | +2% / +57% / -26% | 281 | 29% | 48 | -5% |
| cross + fixed stop 3 ATR | +29% | 68% | +2.9% | -2.5% | +13% / +78% / -36% | 200 | 17% | 94 | +12% |
| trail 2 ATR only | -46% | 56% | -1.8% | -2.3% | -1% / -7% / -41% | 805 | 31% | 7 | -72% |
| trail 3 ATR only | -17% | 50% | -0.1% | -0.8% | +1% / +36% / -40% | 523 | 32% | 16 | -46% |
| trail 4 ATR only | +25% | 44% | +1.6% | -1.0% | +6% / +62% / -27% | 382 | 31% | 27 | -8% |
| trail 6 ATR only | +8% | 49% | +1.1% | -1.0% | -6% / +44% / -21% | 256 | 31% | 56 | -14% |
| time 24h only | -37% | 55% | -1.0% | -2.0% | -1% / +7% / -41% | 453 | 39% | 25 | -53% |
| time 48h only | -60% | 65% | -3.0% | -2.3% | -23% / -30% / -26% | 311 | 40% | 49 | -67% |
| time 96h only | -10% | 60% | +0.4% | -0.7% | +16% / +21% / -36% | 203 | 43% | 97 | -20% |
| time 168h only | -29% | 58% | -0.5% | -1.9% | +17% / -10% / -33% | 130 | 45% | 169 | -34% |
| cross + trail 3 + time 48h | -13% | 52% | +0.0% | -1.2% | +5% / +45% / -43% | 542 | 30% | 15 | -44% |
| cross + trail 3 + time 96h | -15% | 52% | -0.1% | -1.1% | +3% / +42% / -42% | 535 | 30% | 15 | -45% |

**48/200 short**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | +42% | 28% | +2.1% | +1.0% | -2% / +18% / +22% | 115 | 34% | 193 | +31% |
| cross + trail 2 ATR | -30% | 35% | -1.2% | -1.4% | -6% / +5% / -29% | 703 | 33% | 9 | -60% |
| cross + trail 3 ATR | +2% | 25% | +0.4% | -0.4% | +2% / +13% / -12% | 478 | 36% | 19 | -31% |
| cross + trail 4 ATR | +23% | 19% | +1.2% | +0.1% | +2% / +12% / +7% | 365 | 39% | 30 | -8% |
| cross + trail 6 ATR | +86% | 19% | +2.9% | +2.7% | +14% / +41% / +15% | 258 | 45% | 58 | +52% |
| cross + fixed stop 3 ATR | +30% | 32% | +1.5% | +1.1% | -6% / +24% / +12% | 152 | 26% | 138 | +16% |
| trail 2 ATR only | -27% | 32% | -1.1% | -1.4% | -4% / +4% / -27% | 696 | 34% | 10 | -58% |
| trail 3 ATR only | +5% | 24% | +0.5% | -0.2% | +3% / +13% / -10% | 468 | 37% | 19 | -29% |
| trail 4 ATR only | +29% | 20% | +1.4% | +0.1% | +3% / +18% / +6% | 351 | 41% | 32 | -3% |
| trail 6 ATR only | +93% | 19% | +3.1% | +2.7% | +15% / +50% / +12% | 240 | 47% | 64 | +56% |
| time 24h only | -5% | 40% | +0.1% | +0.2% | -0% / -7% / +2% | 440 | 50% | 25 | -28% |
| time 48h only | +38% | 39% | +1.6% | +1.6% | +4% / +13% / +17% | 301 | 57% | 49 | +14% |
| time 96h only | +22% | 43% | +1.5% | +0.0% | +8% / -10% / +26% | 192 | 63% | 97 | +8% |
| time 168h only | +132% | 29% | +4.0% | +5.7% | +20% / +56% / +25% | 129 | 66% | 169 | +114% |
| cross + trail 3 + time 48h | +1% | 24% | +0.4% | -0.7% | +1% / +15% / -13% | 484 | 36% | 18 | -32% |
| cross + trail 3 + time 96h | +2% | 25% | +0.4% | -0.4% | +2% / +13% / -12% | 478 | 36% | 19 | -31% |

**48/200 both**

| exit | total | max DD | 11d mean | 11d median | thirds | trades | win | avg hold (h) | stress total |
|---|---|---|---|---|---|---|---|---|---|
| cross only | -15% | 35% | +0.2% | +0.4% | -32% / +29% / -3% | 155 | 28% | 168 | -22% |
| cross + trail 2 ATR | -56% | 67% | -2.4% | -2.7% | -3% / +3% / -56% | 1428 | 32% | 8 | -86% |
| cross + trail 3 ATR | +20% | 51% | +1.5% | -0.2% | +22% / +71% / -42% | 904 | 34% | 18 | -42% |
| cross + trail 4 ATR | +121% | 30% | +4.3% | +2.7% | +3% / +137% / -9% | 652 | 37% | 29 | +33% |
| cross + trail 6 ATR | +169% | 28% | +4.9% | +4.7% | +14% / +122% / +6% | 384 | 39% | 58 | +101% |
| cross + fixed stop 3 ATR | +11% | 34% | +1.5% | +0.9% | +10% / +8% / -6% | 209 | 25% | 125 | -4% |
| trail 2 ATR only | -54% | 65% | -2.3% | -2.6% | -3% / +1% / -53% | 1423 | 33% | 8 | -86% |
| trail 3 ATR only | +7% | 49% | +1.0% | -0.4% | +19% / +54% / -41% | 888 | 35% | 18 | -47% |
| trail 4 ATR only | +97% | 33% | +3.7% | +1.8% | +4% / +126% / -16% | 624 | 38% | 30 | +19% |
| trail 6 ATR only | +108% | 28% | +3.7% | +2.2% | +9% / +112% / -10% | 364 | 40% | 62 | +56% |
| time 24h only | +16% | 51% | +1.4% | +0.6% | +1% / +103% / -43% | 724 | 44% | 25 | -26% |
| time 48h only | -10% | 40% | +0.0% | -0.8% | -8% / +6% / -9% | 434 | 49% | 49 | -32% |
| time 96h only | -23% | 46% | -0.3% | -0.4% | +4% / -17% / -11% | 241 | 49% | 97 | -34% |
| time 168h only | +52% | 24% | +2.1% | +1.5% | +14% / +20% / +10% | 147 | 57% | 169 | +38% |
| cross + trail 3 + time 48h | +22% | 52% | +1.6% | +0.4% | +25% / +75% / -44% | 918 | 34% | 17 | -41% |
| cross + trail 3 + time 96h | +20% | 51% | +1.5% | -0.2% | +22% / +71% / -42% | 904 | 34% | 18 | -42% |

## G. The signal without slots, stops or costs: next-hour return of coins whose fast EMA is above the slow one minus those below (bp per hour, equal weight)

**Spread, bp per hour**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -0.2 | +0.7 | +0.6 | +0.8 | +0.8 | +0.5 | +0.8 | +1.7 | +0.9 |
| **6** | -0.1 | +1.1 | +1.2 | +0.7 | +0.4 | +0.7 | +1.0 | +1.6 | +1.0 |
| **9** | +0.4 | +1.2 | +0.9 | +0.3 | +0.2 | +0.5 | +0.7 | +1.6 | +0.8 |
| **12** | +1.1 | +1.3 | +0.2 | +0.5 | +0.2 | +0.9 | +0.8 | +1.6 | +0.8 |
| **18** | +1.5 | +0.8 | +0.5 | +0.1 | +0.7 | +0.7 | +1.0 | +1.5 | +0.9 |
| **24** |  | +0.6 | +0.2 | -0.1 | +0.9 | +0.7 | +0.9 | +1.8 | +0.8 |
| **36** |  |  | +0.3 | +0.6 | +0.7 | +0.8 | +1.0 | +1.5 | +0.9 |
| **48** |  |  | +0.5 | +0.5 | +0.7 | +0.7 | +1.3 | +1.7 | +0.9 |
| **72** |  |  |  |  | +0.7 | +0.9 | +1.7 | +1.7 | +0.7 |

**t-statistic (daily blocks)**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -0.2 | +0.8 | +0.7 | +0.8 | +1.0 | +0.6 | +0.9 | +2.3 | +1.0 |
| **6** | -0.1 | +1.1 | +1.2 | +0.9 | +0.6 | +1.0 | +1.3 | +2.2 | +1.1 |
| **9** | +0.4 | +1.2 | +1.0 | +0.4 | +0.2 | +0.7 | +0.9 | +1.9 | +1.0 |
| **12** | +1.1 | +1.4 | +0.2 | +0.6 | +0.2 | +1.2 | +1.0 | +1.9 | +0.9 |
| **18** | +1.5 | +0.8 | +0.7 | +0.1 | +0.8 | +1.0 | +1.3 | +2.1 | +1.1 |
| **24** |  | +0.6 | +0.3 | -0.1 | +1.1 | +0.9 | +1.2 | +2.4 | +0.9 |
| **36** |  |  | +0.3 | +0.8 | +1.0 | +1.0 | +1.2 | +1.9 | +1.2 |
| **48** |  |  | +0.5 | +0.6 | +1.0 | +0.9 | +1.7 | +2.4 | +1.2 |
| **72** |  |  |  |  | +0.8 | +1.1 | +2.3 | +2.3 | +0.8 |

**Spread by third, bp per hour**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -2.0 +5.1 -3.8 | -1.1 +4.7 -1.6 | -0.4 +3.9 -1.8 | -0.2 +3.6 -1.2 | +0.1 +2.7 -0.5 | -0.2 +2.7 -1.0 | -0.5 +2.9 -0.2 | +0.6 +3.8 +0.6 | -1.5 +3.6 -0.3 |
| **6** | -1.8 +4.3 -2.8 | -0.5 +5.2 -1.5 | -0.3 +4.7 -1.1 | -0.1 +3.2 -1.0 | -0.6 +2.1 -0.2 | +0.1 +2.8 -0.8 | +0.2 +3.0 -0.2 | +0.9 +3.5 +0.2 | -0.8 +3.3 -0.3 |
| **9** | -1.2 +4.2 -2.0 | +0.2 +4.3 -1.2 | -0.0 +3.5 -0.8 | -1.2 +2.9 -0.8 | -1.1 +1.8 -0.1 | +0.1 +1.6 -0.3 | +0.0 +2.0 +0.1 | +1.3 +3.3 +0.1 | -0.8 +3.1 -0.4 |
| **12** | +0.1 +4.8 -1.6 | +0.7 +4.0 -1.0 | -0.9 +2.5 -1.1 | -0.6 +2.4 -0.5 | -0.7 +1.5 -0.3 | +0.4 +1.7 +0.5 | +0.7 +2.0 -0.4 | +1.4 +3.3 -0.1 | -0.8 +2.8 -0.2 |
| **18** | +0.9 +4.7 -1.4 | -0.5 +3.9 -1.1 | -0.5 +2.7 -0.7 | -0.8 +1.6 -0.6 | -0.4 +1.8 +0.5 | +0.3 +1.3 +0.5 | +1.2 +2.0 -0.2 | +1.4 +3.4 -0.5 | -0.2 +3.0 -0.6 |
| **24** |  | -0.9 +3.4 -0.9 | -1.0 +2.5 -0.9 | -1.8 +1.8 -0.3 | -0.3 +2.3 +0.7 | +0.7 +1.4 -0.1 | +1.0 +2.1 -0.4 | +1.3 +3.7 +0.2 | +0.0 +2.7 -0.7 |
| **36** |  |  | -1.4 +2.2 -0.1 | -1.1 +2.2 +0.6 | +0.1 +1.4 +0.7 | +1.1 +1.3 +0.1 | +0.9 +2.4 -0.2 | +1.5 +3.4 -0.3 | +0.1 +2.7 -0.5 |
| **48** |  |  | -1.3 +2.0 +0.8 | -0.9 +1.4 +0.8 | +0.2 +1.9 +0.1 | +1.0 +1.7 -0.5 | +1.1 +2.9 -0.1 | +1.3 +4.1 -0.4 | -0.2 +3.3 -0.7 |
| **72** |  |  |  |  | +0.6 +1.8 -0.3 | +1.0 +1.7 +0.0 | +1.6 +3.5 -0.0 | +1.6 +4.1 -0.6 | -0.7 +3.0 -0.7 |

**State flips per coin per week**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | 11.2 | 8.5 | 6.7 | 5.7 | 4.7 | 3.8 | 3.2 | 2.6 | 1.8 |
| **6** | 9.2 | 7.0 | 5.5 | 4.7 | 3.9 | 3.1 | 2.7 | 2.1 | 1.5 |
| **9** | 7.5 | 5.7 | 4.5 | 3.9 | 3.3 | 2.6 | 2.2 | 1.8 | 1.3 |
| **12** | 6.5 | 4.9 | 4.0 | 3.4 | 2.8 | 2.3 | 1.9 | 1.5 | 1.1 |
| **18** | 5.3 | 4.1 | 3.2 | 2.8 | 2.3 | 1.9 | 1.6 | 1.3 | 0.9 |
| **24** |  | 3.6 | 2.8 | 2.5 | 2.1 | 1.7 | 1.4 | 1.1 | 0.8 |
| **36** |  |  | 2.3 | 2.0 | 1.7 | 1.4 | 1.2 | 1.0 | 0.7 |
| **48** |  |  | 2.0 | 1.8 | 1.5 | 1.2 | 1.1 | 0.8 | 0.6 |
| **72** |  |  |  |  | 1.2 | 1.0 | 0.9 | 0.6 | 0.5 |

## H. Before costs (zero fees, spread, slippage), 4 slots: total return

**long, trail 3 ATR, zero costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -46% | -41% | -45% | -47% | -10% | +5% | +25% | +46% | -17% |
| **6** | -65% | -41% | -43% | -24% | -22% | +20% | +23% | +72% | +15% |
| **9** | -46% | -39% | -17% | -12% | +6% | +10% | +45% | +63% | +10% |
| **12** | -39% | -28% | -18% | +37% | +9% | +24% | +34% | +32% | +2% |
| **18** | -38% | -39% | +21% | +61% | +56% | +95% | +42% | +71% | +11% |
| **24** |  | -40% | +81% | +59% | +58% | +57% | +88% | +118% | +15% |
| **36** |  |  | +97% | +58% | +118% | +74% | +86% | +103% | -8% |
| **48** |  |  | +62% | +76% | +69% | +67% | +38% | +61% | -4% |
| **72** |  |  |  |  | +78% | +31% | +84% | +56% | -3% |

**short, trail 3 ATR, zero costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | +57% | +83% | +66% | +115% | +52% | +79% | +97% | +149% | +113% |
| **6** | +54% | +128% | +87% | +68% | +44% | +128% | +152% | +107% | +85% |
| **9** | +71% | +117% | +65% | +75% | +49% | +115% | +90% | +134% | +72% |
| **12** | +90% | +77% | +36% | +76% | +38% | +113% | +135% | +121% | +83% |
| **18** | +110% | +100% | +62% | +71% | +76% | +72% | +80% | +47% | +44% |
| **24** |  | +50% | +68% | +56% | +126% | +111% | +75% | +44% | +42% |
| **36** |  |  | +100% | +43% | +50% | +72% | +11% | +36% | +18% |
| **48** |  |  | +37% | +27% | +49% | +31% | +56% | +39% | -5% |
| **72** |  |  |  |  | +46% | +16% | +39% | +26% | -7% |

**both, trail 3 ATR, zero costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | -1% | +53% | +41% | +60% | +70% | +143% | +256% | +317% | +62% |
| **6** | +39% | +30% | -26% | +31% | +139% | +280% | +263% | +187% | +118% |
| **9** | -5% | -9% | +57% | +159% | +244% | +176% | +190% | +289% | +107% |
| **12** | -2% | +5% | +16% | +287% | +38% | +271% | +195% | +266% | +94% |
| **18** | +27% | -13% | +105% | +365% | +86% | +241% | +255% | +140% | +62% |
| **24** |  | +18% | +185% | +75% | +236% | +268% | +299% | +205% | +63% |
| **36** |  |  | +253% | +109% | +245% | +257% | +96% | +150% | +7% |
| **48** |  |  | +90% | +133% | +158% | +114% | +171% | +87% | +4% |
| **72** |  |  |  |  | +203% | +121% | +129% | +85% | -12% |

**long, no stop, zero costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | +53% | -9% | -15% | -9% | -49% | -44% | -9% | +6% | +206% |
| **6** | -26% | -22% | -9% | -17% | -58% | -56% | +34% | +97% | +158% |
| **9** | -28% | -22% | -20% | -40% | -56% | -22% | -22% | +112% | +123% |
| **12** | -12% | -28% | -49% | -38% | -10% | -29% | -31% | +51% | -19% |
| **18** | -27% | -45% | +0% | -8% | +25% | +3% | +42% | +116% | +199% |
| **24** |  | -13% | -42% | +0% | +10% | -12% | +1% | +294% | +142% |
| **36** |  |  | -2% | +3% | -1% | +135% | +117% | +108% | +143% |
| **48** |  |  | +6% | -13% | +14% | +63% | +74% | +191% | +130% |
| **72** |  |  |  |  | +31% | +26% | +75% | +192% | -39% |

**short, no stop, zero costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | +22% | +15% | +32% | +63% | +27% | +19% | +51% | +58% | +80% |
| **6** | +23% | +14% | +18% | +76% | +53% | +42% | +50% | +96% | +45% |
| **9** | +44% | +37% | +31% | +41% | +65% | +35% | +33% | +104% | +53% |
| **12** | -7% | +51% | +22% | +30% | +38% | +24% | +93% | +73% | +56% |
| **18** | +7% | +56% | +12% | -1% | +31% | +93% | +83% | +51% | +56% |
| **24** |  | +35% | -1% | +28% | +35% | +60% | +59% | +40% | +37% |
| **36** |  |  | -11% | -16% | +3% | +24% | +48% | +64% | +45% |
| **48** |  |  | -16% | +7% | +64% | +119% | +54% | +76% | +55% |
| **72** |  |  |  |  | +62% | +51% | +61% | +14% | +27% |

**both, no stop, zero costs**

| fast \ slow | 21 | 36 | 55 | 72 | 100 | 150 | 200 | 300 | 480 |
|---|---|---|---|---|---|---|---|---|---|
| **4** | +39% | +108% | -6% | +14% | +48% | +27% | +19% | +7% | +13% |
| **6** | +65% | -50% | -34% | +53% | +1% | +21% | +5% | +35% | -4% |
| **9** | +119% | -33% | -11% | +73% | -46% | +7% | -12% | -14% | +43% |
| **12** | +29% | +1% | +66% | +18% | -48% | -20% | -25% | -39% | +51% |
| **18** | +28% | +41% | +9% | +6% | -3% | -36% | -3% | +13% | +84% |
| **24** |  | +59% | +1% | -9% | -46% | -17% | +47% | +6% | +30% |
| **36** |  |  | +11% | -2% | -16% | -14% | -12% | -16% | +12% |
| **48** |  |  | -26% | -40% | -54% | -47% | -5% | -24% | +303% |
| **72** |  |  |  |  | -46% | -27% | -8% | +51% | +31% |

## I. The windows in the team document (base risk settings: 4 slots, trail 3 ATR, fresh 3)

| windows | side | first tradable bar | total | max DD | 11d mean / median | >=+10% / <=-10% | thirds | trades | win | stress total |
|---|---|---|---|---|---|---|---|---|---|---|
| 9/21 + 55 trend, hourly candles | long | 165 | -89% | 91% | -7.7% / -9.6% | 9% / 49% | -38% / -49% / -66% | 1670 | 23% | -97% |
| 9/21 + 55 trend, hourly candles | short | 165 | -44% | 61% | -1.6% / -2.3% | 10% / 17% | -30% / -18% / -3% | 1479 | 28% | -82% |
| 9/21 + 55 trend, hourly candles | both | 165 | -83% | 85% | -6.3% / -6.5% | 5% / 39% | -34% / -38% / -57% | 1619 | 31% | -94% |
| 9/21 hourly, no trend line | long | 72 | -86% | 89% | -6.7% / -8.8% | 11% / 46% | -37% / -47% / -59% | 1610 | 23% | -96% |
| 9/21 hourly, no trend line | short | 72 | -47% | 63% | -1.9% / -3.2% | 11% / 18% | -39% / -11% / -3% | 1394 | 28% | -82% |
| 9/21 hourly, no trend line | both | 72 | -77% | 88% | -5.0% / -5.2% | 12% / 37% | -28% / -51% / -34% | 1617 | 31% | -94% |
| 9/21/55 on 4h candles = 36/84/220 h | long | 660 | -67% | 70% | -3.7% / -5.5% | 8% / 27% | -38% / -29% / -25% | 1050 | 29% | -86% |
| 9/21/55 on 4h candles = 36/84/220 h | short | 660 | -44% | 57% | -1.7% / -3.1% | 9% / 14% | -32% / -3% / -16% | 1016 | 33% | -75% |
| 9/21/55 on 4h candles = 36/84/220 h | both | 660 | -59% | 66% | -2.8% / -3.3% | 10% / 21% | -44% / -14% / -16% | 1336 | 33% | -87% |
| 9/21/55 on daily candles = 216/504/1320 h | long | 3960 | -35% | 45% | -1.5% / +0.0% | 1% / 10% | +0% / -16% / -23% | 172 | 21% | -43% |
| 9/21/55 on daily candles = 216/504/1320 h | short | 3960 | -12% | 19% | -0.5% / +0.0% | 0% / 0% | +0% / -4% / -8% | 139 | 43% | -21% |
| 9/21/55 on daily candles = 216/504/1320 h | both | 3960 | -38% | 47% | -1.7% / +0.0% | 1% / 9% | +0% / -17% / -26% | 286 | 31% | -50% |
| 50/200 golden cross, hourly candles | long | 600 | +2% | 38% | +0.7% / -0.4% | 13% / 9% | +2% / +42% / -29% | 527 | 32% | -33% |
| 50/200 golden cross, hourly candles | short | 600 | +3% | 24% | +0.4% / -0.9% | 8% / 1% | -2% / +18% / -10% | 471 | 37% | -29% |
| 50/200 golden cross, hourly candles | both | 600 | +55% | 35% | +2.7% / +1.3% | 27% / 13% | +9% / +92% / -26% | 883 | 36% | -24% |
| 50/200 on 4h candles = 200/800 h | long | 2400 | -8% | 17% | -0.2% / +0.0% | 3% / 0% | -11% / +6% / -2% | 117 | 29% | -16% |
| 50/200 on 4h candles = 200/800 h | short | 2400 | -14% | 19% | -0.5% / +0.0% | 0% / 0% | -10% / -2% / -2% | 145 | 35% | -23% |
| 50/200 on 4h candles = 200/800 h | both | 2400 | -19% | 24% | -0.6% / +0.0% | 3% / 3% | -19% / +4% / -4% | 257 | 33% | -34% |

## J. Finalists and their neighbours

| variant | total | max DD | Sharpe | Sortino | 11d mean / median | win | >=+10% / <=-10% | thirds | stress total | stress thirds | trades | win rate | active days | long P&L | short P&L | P&L without its 3 best coins | 3 best coins | coins with profit | 30-day months |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| both 24/200 trail6 | +59% | 25% | +1.24 | +2.13 | +2.2% / +1.4% | 57% | 12% / 4% | +12% / +45% / -2% | +17% | +1% / +30% / -10% | 430 | 36% | 73% | +13,573 | +39,175 | -10,772 | ZEC +23k, ICP +21k, ZEN +19k | 47% | -4% +13% +4% -1% -2% +51% -9% -6% +15% |
| both 36/200 trail6 | +114% | 29% | +1.84 | +3.31 | +3.9% / +2.1% | 58% | 23% / 8% | +24% / +99% / -13% | +57% | +11% / +80% / -22% | 419 | 38% | 74% | +8,214 | +106,121 | +13,358 | ICP +38k, ZEN +36k, 1000CHEEMS +27k | 58% | +7% +29% -6% +10% +2% +68% -8% +1% +7% |
| both 36/150 trail6 | +62% | 29% | +1.29 | +2.25 | +2.8% / +0.2% | 52% | 20% / 6% | +2% / +55% / +2% | +17% | -9% / +40% / -9% | 421 | 37% | 78% | -105 | +61,172 | +1,019 | ICP +26k, ZEN +18k, 1000CHEEMS +16k | 54% | -3% +14% -6% -6% +3% +61% -0% +13% -4% |
| both 24/200 trail5 | +49% | 29% | +1.06 | +1.98 | +2.2% / +0.6% | 53% | 16% / 10% | +5% / +51% / -7% | -3% | -9% / +29% / -18% | 559 | 36% | 82% | +4,728 | +39,161 | -14,706 | ZEN +20k, ZEC +19k, UNI +19k | 52% | +9% +7% -9% +4% -10% +56% -14% +16% +9% |
| both 24/200 trail6 3 slots | +96% | 27% | +1.59 | +2.83 | +3.3% / +2.5% | 60% | 19% / 6% | +29% / +62% / -6% | +42% | +16% / +46% / -16% | 319 | 37% | 69% | +15,359 | +71,172 | -19,129 | ZEC +39k, ZEN +34k, ICP +33k | 47% | -0% +21% +8% +1% +2% +55% -7% -8% +13% |
| both 24/200 trail6 6 slots | +68% | 25% | +1.40 | +2.57 | +2.7% / +1.8% | 56% | 13% / 4% | +13% / +45% / +2% | +22% | +1% / +30% / -8% | 647 | 37% | 84% | +13,542 | +50,307 | +5,849 | ICP +22k, ZEN +21k, UNI +15k | 54% | -1% +23% -7% +4% -9% +53% -14% +13% +13% |
| both 24/200 trail6 8 slots | +25% | 32% | +0.80 | +1.35 | +1.4% / +1.1% | 55% | 11% / 6% | +5% / +20% / -1% | -7% | -5% / +8% / -10% | 822 | 35% | 88% | -7,386 | +29,886 | -9,793 | ICP +15k, ZEN +12k, STO +6k | 46% | -1% +22% -12% +4% -12% +34% -13% +13% +8% |
| both 24/200 trail6 fresh1 | +73% | 32% | +1.39 | +2.44 | +2.9% / +1.8% | 56% | 14% / 6% | +3% / +56% / +7% | +24% | -8% / +39% / -3% | 446 | 36% | 76% | +12,166 | +57,589 | +8,640 | ICP +24k, ZEN +21k, ZEC +16k | 56% | -6% +13% -1% +5% -9% +61% -4% -3% +18% |
| both 24/200 trail6 fresh6 | +130% | 23% | +1.94 | +3.42 | +4.0% / +2.2% | 61% | 17% / 3% | +28% / +64% / +10% | +63% | +14% / +46% / -2% | 437 | 39% | 76% | +13,078 | +107,397 | +21,172 | ZEN +39k, ICP +38k, PEPE +23k | 54% | +18% +9% -0% +0% +4% +54% -5% +18% +5% |
| both 24/200 trail6 fresh12 | +170% | 29% | +2.12 | +3.96 | +4.9% / +3.1% | 67% | 25% / 6% | +39% / +86% / +5% | +93% | +24% / +66% / -6% | 454 | 38% | 77% | +54,643 | +110,906 | +22,522 | ICP +63k, ZEN +50k, PEPE +30k | 44% | +11% +28% -3% +29% +13% +32% -3% +22% -4% |
| both 24/200 trail6 limit entry | +28% | 29% | +0.79 | +1.34 | +1.4% / +0.1% | 50% | 10% / 5% | -2% / +34% / -3% | -15% | -14% / +17% / -15% | 439 | 35% | 76% | +483 | +22,345 | -29,371 | ZEC +19k, ICP +19k, ZEN +14k | 43% | -6% +13% -7% -1% -2% +39% -9% -6% +13% |
| long 36/200 trail4 | +106% | 39% | +1.67 | +3.64 | +3.7% / +0.7% | 52% | 25% / 6% | +57% / +64% / -20% | +41% | +41% / +43% / -30% | 447 | 32% | 84% | +100,218 | +0 | -35,425 | TUT +69k, PEPE +35k, VIRTUAL +31k | 44% | +14% +32% +6% +38% +7% +18% -14% +4% -10% |
| long 24/200 trail4 | +66% | 45% | +1.26 | +2.62 | +2.7% / -0.2% | 49% | 24% / 10% | +48% / +43% / -21% | +13% | +32% / +24% / -31% | 500 | 31% | 83% | +62,854 | +0 | -52,223 | TUT +62k, ZEC +27k, ZEN +26k | 44% | +11% +24% +9% +25% +9% +11% -19% +8% -11% |
| long 36/200 trail6 | +31% | 45% | +0.82 | +1.52 | +1.7% / -0.8% | 48% | 16% / 6% | +31% / +20% / -17% | +4% | +22% / +10% / -23% | 312 | 29% | 77% | +29,979 | +0 | -40,451 | ICP +33k, PEPE +19k, ZEN +18k | 38% | +10% +13% +9% +0% -4% +26% -11% +5% -10% |
| long 36/200 no stop | +91% | 57% | +1.36 | +2.44 | +4.5% / -2.5% | 42% | 25% / 15% | +32% / +73% / -17% | +70% | +27% / +67% / -20% | 180 | 21% | 59% | +86,426 | +0 | -127,777 | ZEC +150k, PENGU +43k, PEPE +22k | 24% | +28% +22% -10% -3% +74% +5% -16% +6% -10% |
| long 36/200 trail4 8 slots | +40% | 25% | +1.20 | +2.27 | +1.7% / +0.9% | 54% | 13% / 0% | +25% / +27% / -11% | +7% | +15% / +16% / -20% | 659 | 32% | 87% | +38,146 | +0 | -8,153 | TUT +26k, VIRTUAL +10k, PEPE +10k | 48% | +7% +19% +0% +19% +2% +7% -12% +12% -6% |
| short 24/200 trail6 | +87% | 21% | +1.85 | +3.50 | +3.1% / +2.6% | 61% | 20% / 5% | +12% / +47% / +13% | +48% | +4% / +35% / +5% | 311 | 41% | 73% | +0 | +87,474 | +40,503 | APT +18k, ZEN +15k, PENGU +14k | 52% | +13% -5% +2% -2% +14% +27% +8% +8% +19% |
| short 36/200 trail6 | +67% | 22% | +1.62 | +2.85 | +2.6% / +1.9% | 60% | 16% / 4% | +4% / +40% / +15% | +35% | -4% / +30% / +7% | 288 | 42% | 73% | +0 | +66,976 | +25,361 | ZEN +18k, FET +14k, SUI +10k | 62% | +9% -2% -3% +1% +12% +19% +7% +7% +23% |
| short 12/300 trail6 | +108% | 20% | +2.18 | +4.01 | +3.3% / +2.6% | 66% | 20% / 3% | +8% / +37% / +40% | +60% | -1% / +24% / +30% | 353 | 39% | 72% | +0 | +108,861 | +61,768 | ZEC +20k, PENGU +16k, PENDLE +11k | 72% | +8% -1% -2% +12% +9% +11% +10% +12% +19% |
| short 24/200 trail6 8 slots | +65% | 18% | +1.66 | +3.08 | +2.4% / +1.7% | 59% | 14% / 1% | +9% / +31% / +17% | +36% | +2% / +22% / +10% | 519 | 42% | 83% | +0 | +65,577 | +37,138 | VIRTUAL +10k, APT +10k, ZEN +9k | 60% | +9% +3% -6% +4% +3% +19% +8% +8% +21% |

