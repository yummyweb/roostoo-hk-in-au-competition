# Track z_windows: z-score mean-reversion windows

Data: `harness.load('design')` only, rows 744+ (282 days, 50 pairs, average coin -45%). All numbers from `evalkit.report`
(default costs, and `evalkit.STRESS`). 1,247 variants were evaluated in total; treat every "best cell" below with that in mind.

## Verdict: no-edge

Plain z-score mean reversion does not beat cash on this data at any window, entry level, exit level or side.

- Base grid, 9 lookbacks x 5 entries x 5 exits x 3 sides = 675 variants (660 traded). **0 are positive after stress costs.**
  4 are positive at default costs (+1% to +4%, all long, n = 240/336 with z_in = 3.5, 91-125 trades), and in each of them one
  coin (1000CHEEMS) earned more than the whole net profit. Only 8 of 660 have two or more positive thirds.
- Long side: nearly every (n, z_in) cell loses 25 to 90 bp per trade after costs (the only exceptions are the two n = 240/336, z_in = 3.5 cells above). Short side (fading spikes) is worse, 40 to 155 bp
  per trade, in a market where the average coin fell 45%: all 225 short variants lose, best -38%. Spikes continue; they do not revert.
- Exit level, confirmation candle, RSI gate, RSI z-score, VWAP z-score, stop width, time limit, slot count, limit entry and the
  low-efficiency-ratio filter change how often it trades, not whether a trade makes money.
- One condition changes the sign: buying dips **only while BTC's 24h return is >= +1%**. It is positive after stress costs in
  most cells, but it trades 10 to 100 times in 9 months, its headline is carried by one flash-crash trade in one coin, and without
  that coin it is +2% on average (-3% under stress). It is filed as the least-bad region, not as an edge.

## Method

1. Raw event study (no slots, stops or costs): what a coin does after z reaches +-z_in, by lookback (section 0).
2. Full grid n {12,24,36,48,72,120,168,240,336} x z_in {1.5,2,2.5,3,3.5} x z_out {1,.5,0,-.5,-1} x side {long, short, both}
   with risk held at stop 5%, max hold 48 h, 4 slots, market entry, maker exit (sections A-D). 675 variants.
3. Confirmation candle, RSI gate {25,30,35}, RSI z-score and VWAP z-score subclasses, risk settings (stop 3% / 8% / none,
   hold 24 / 96, 8 slots, limit entry), ER filter and BTC floor (sections E-H). The machine became busy mid-run, so these were
   run on a sub-grid: long n {12,24,48,72,168,336} x z_in {2,3} (12 cells); short n {24,72,336} x z_in {2,3} (6 cells). 345 variants
   (316 on the sub-grids plus 29 confirm cells that had already run on the full grid before the cut).
4. Refinement of the only condition that changed sign, the BTC floor: floors {0.5,1,1.5,2,3}% x n {24..336} x z_in {2,2.5,3},
   then 11 robustness variations at floor 1% (section I). 227 new variants.
5. Look-ahead check (`check=True`, 40 cuts) on the two filed candidates: both pass.

Exit reasons: `target` = resting sale at the moving mean (harness reason `take`), `stop` = hard stop, `time` = closed by
max_hold (market exit with bars held > max_hold), `signal` = z back through the exit level at an hourly close (market exit).
Subclasses are in `zw.py`: `RsiZ` (z-score of RSI(14) over n bars; no price target exists so exits are signal/stop/time) and
`VwapZ` (rolling volume-weighted mean of typical price in place of the SMA, same std).

## Findings in plain words

**1. Short lookbacks: more trades and more whipsaw. Long lookbacks: fewer trades, not better trades.** Long side, z_in = 2, exit at the mean:

| n (hours) | trades | win rate | avg win | avg loss | break-even win rate | net per trade | total / stress |
|---|---|---|---|---|---|---|---|
| 12 | 2,200 | 56% | +1.2% | -2.3% | 66% | -35 bp | -87% / -98% |
| 24 | 1,402 | 59% | +1.8% | -3.5% | 66% | -38 bp | -76% / -93% |
| 48 | 961 | 58% | +2.7% | -4.4% | 62% | -30 bp | -55% / -84% |
| 72 | 740 | 50% | +3.4% | -4.6% | 58% | -66 bp | -73% / -85% |
| 168 | 506 | 38% | +5.0% | -4.4% | 47% | -81 bp | -67% / -77% |
| 336 | 430 | 39% | +5.4% | -4.6% | 46% | -70 bp | -58% / -70% |

Going from 12 h to 336 h cuts trades fivefold and triples the average win, but the win rate falls from 56-59% to 38-39% and the
loss per trade does not shrink (pooled over all z_in and z_out: -39 bp at n=12, -64 bp at n=120, -44 bp at n=336). Long windows
lose less in total only because they trade less. The number of raw signal-hours is about the same for every n >= 24
(80-94 per day across 50 coins at z_in = 2); short windows trade more because their mean catches up with price sooner and frees the slot.
Raising z_in helps the same way: z_in 1.5 -> 3.5 moves the average total from -79% to -21% by cutting trades from 1,331 to 203.

**2. Why it wins more than half its trades and still loses.** The win rate is 4 to 10 points below break-even everywhere
(table above). By exit reason, long side, pooled over z_in:

| lookbacks | target: share, avg | time: share, avg | stop: share, avg | net per trade | stop share needed to break even |
|---|---|---|---|---|---|
| 12-36 h | 70%, +0.97% | 0% | 21%, -5.37% | -40 bp | 14% |
| 48-120 h | 47%, +2.99% | 12%, +0.42% | 39%, -5.37% | -54 bp | 29% |
| 168-336 h | 15%, +7.17% | 37%, +2.29% | 48%, -5.37% | -65 bp | 36% |

With a short window the "mean" falls to meet the price: the target fills, but for under 1% on average (with no stop, target
exits at n = 12 and 24 average -0.2% to -0.6%: reaching the mean is not a profit). With a long window the target is worth 7%
but only 15% of trades reach it, and half are stopped first. Removing the stop does not fix it: losses move to the time exit
(-2% to -11% average) and the 12-cell average total goes from -52% to -37%. A 3% stop is worse (-60%), 8% is the same (-52%).
To be profitable, a quarter to a third of the stop-outs would have to disappear with everything else unchanged, or target exits at short
windows would have to earn about 1.5% instead of 1.0%. Nothing in the grid does either.

**3. The raw data says the same thing.** After z <= -2 on windows of 24-48 h the coin is down a further 35-45 bp over the next
24 h (all coins, all hours: -17 bp): the dip continues. On windows of 120 h and longer there is a bounce (+49 to +70 bp at 24 h,
+144 to +154 bp at 48 h) but the path to it goes through the stop. After z >= +2 (n >= 24) the coin is up a further 22-30 bp at 6 h and
27-72 bp at 24 h: fading spikes is the wrong side. A high z-score is a continuation signal, which is what the breakout benchmark trades.

**4. What did not matter.** z_out: average long total -55% (exit early at z = -1) to -51% (wait for z = +1), loss per trade
-46 to -50 bp throughout. Confirmation candle: halves trades and the loss (-52% -> -31%), per trade -34 bp, 0 of 11 cells
positive after stress. RSI <= 25 / 30 / 35: -30% / -44% / -49%, same per-trade loss. RSI z-score: -49% vs -52% for the plain
z-score (short side -61% vs -84%). VWAP z-score: -54% vs -52%. Hold 24 / 96: -53% / -54%. 8 slots: -47%. Limit entry: -48%
(-69% under stress). ER168 <= 0.03 / 0.07 / 0.12: -28% / -39% / -48%.

**5. The one condition that changed the sign: BTC 24h return above a floor.** 12-cell average total: no floor -52%, floor -1%
-32%, floor 0 -23%, floor +1% **+5%** (stress -6%, 8 of 12 cells positive after stress, +108 bp per trade). On the refined grid
at floor +1% every cell with z_in = 3 is positive (+10% to +20%, stress +5% to +16%) and floors of 1.5%, 2% and 3% agree. But:

- Trades are few: 12-75 at z_in = 3, 45-178 at z_in = 2.5, in 282 days. Fills on 7-25% of days.
- In almost every positive cell the best coin is 1000CHEEMS with +$7k to +$17k, which is one trade: the bar of 2025-10-27
  01:00 UTC closed 28% down and the next bar opened there and closed 39% higher (+$13.5k). A bot polling once a minute would
  probably not have been filled at that open. For n=168, z_in=2: net +$22.0k, without that trade +$8.5k, without the best three -$2.2k.
- Without the six coarse-tick coins the 12-cell average is +2% (stress -3%): z_in = 3 cells are +5% / +7% / +10% / +2% on
  10-36 trades, z_in = 2.5 cells are -2% / +5% / -6% / +3%, z_in = 2 cells are -13% / -14% / +21% / +10%.
- Requiring a confirmation candle removes the gain (-3%), so the profit comes from buying straight into one-bar dumps.
- By month (n=168, z_in=2): +$48.7k in Jun-Oct 2025, -$30.8k in Nov 2025-Feb 2026. The most recent third is negative
  in every z_in = 2 cell at floor +1% (-8% to -28%).

So the honest reading is: gating on a rising BTC turns a clear loser into roughly break-even, with a positive tail from rare
flash dumps that may not be fillable. It is a hypothesis for the selection period, not a result.

## Recommendation

- Do not run a z-score mean-reversion leg on its own, long or short, at any window. Never short a high z-score.
- If the team keeps a mean-reversion leg for the regime filter to switch on, use a long window and a deep entry (n 72-168 h,
  z_in >= 3, exit at the mean, z_out 0 to -0.5), long only, and allow entries only while BTC's 24h return is >= +1%
  (`candidate_1.py`). Expect it to be idle most days and to add about zero.
- `candidate_2.py` is the least-bad ungated window (n=240, z_in=3.5), filed only as a reference for an `allow_long` gate.

| candidate | total | max DD | 11d mean / median | >=+10% / <=-10% | thirds | trades | win | stress total | days with a fill | long P&L | without best trade | look-ahead |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1: n=72, z_in=3, BTC >= +1%, coarse coins out | +7.2% | 4.9% | +0.24% / 0.00% | 0% / 0% | +5.3% / -1.1% / +2.9% | 27 | 59% | +4.7% | 12% | +$7,174 | +$4,263 (best three out: +$134) | pass |
| 2: n=240, z_in=3.5, no gate | +2.2% | 25.0% | +0.22% / +0.42% | 2% / 4% | +23.2% / +1.6% / -18.3% | 125 | 39% | -7.1% | 28% | +$2,227 | -$9,236 | pass |
| Breakout benchmark | +40.3% | 43.4% | +2.11% / -0.61% | 23% / 12% | +12% / +61% / -23% | 449 | 36% | +4.2% | 80% | +$40,730 | | |

Plateau for candidate 1: n 48-168, z_in 2.5-3.0 (z_in 3 only once the coarse-tick coins are out), floor 1-2%, z_out -0.5 to +0.5,
stop 5% / 8% / none, hold 24-48 h. Hold 96 h weakens it and the confirmation candle breaks it. Neither candidate reaches the breakout benchmark, and
neither trades on enough days to satisfy the activity rule by itself.

## What is left to do

1. Selection-period test of `candidate_1.py` and `candidate_2.py` (integrators; this track did not load `select` or `full`).
2. Measure whether a market buy one minute after a flash-dump bar is fillable (minute data or live quotes); the BTC-gated result depends on it.
3. Sections E-H ran on 12-cell / 6-cell sub-grids, and the two subclasses were not run with side = both; the direction was uniform, so a full rerun is unlikely to change the verdict.
4. Hand to the trend track: z >= +2 to +3 on 120-336 h windows is followed by +50 to +150 bp over 24 h (a continuation entry).
5. Test the BTC floor as an `allow_long` gate inside the combined portfolio rather than stand-alone.

## 0. Raw event study

