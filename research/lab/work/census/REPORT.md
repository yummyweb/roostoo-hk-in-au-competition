# Census: are the coins trending or choppy, and does a coin's character last?

Track `census`. Descriptive part on `harness.load('full')` (last bar 2026-10-06 19:00 UTC, 50 pairs); every test of whether the description is *usable* on `harness.load('design')` only. Code: `measures.py` (definitions), `census.py`, `persistence.py`, `labels.py`, `selection.py`, `selection2.py`, `finalist.py`; data: `census.csv` (50 coins x 4 windows x 27 measures) and the `*.json` files next to this report.

## Verdict

**no-edge for choosing coins by character; the census itself is descriptive.**

1. **Today (2026-10-06 19:00 UTC) the market is choppy, not trending.** Under the stated rule **0 of 50 coins are trending-up, 0 trending-down, 50 choppy** (loose thresholds: 2 up, 0 down, 48 choppy). A driftless random walk with fat tails would have about 5 of 50 labelled trending by the same rule, so the last two weeks were *choppier than chance*: the EMA 24/100 pair crossed 6.4 times per coin in 14 days (random walk: 4.4) and 4.2 times in the last 7 (random walk: 2.2).
2. **Over the last 14 days the always-in EMA 24/100 rule lost on 43 of 50 coins** after 26 bp per round trip (mean -20.2% per coin, sum of per-position returns), while **the z48 <= -2 dip-buy made money on 45 of 50** (mean +6.1%, 3.4 trades per coin). The market also rose +19% in 30 days and +62% in 90, which flatters dip-buying exactly as the bear market flattered shorts in the design period.
3. **None of this predicts the next 11 days.** On design data (23 non-overlapping 11-day forward windows x 50 coins) the only measure that persists is volatility (rank correlation +0.77 +/- 0.02). Efficiency ratio, crossover counts, variance ratio, autocorrelation, trend P&L and mean-reversion P&L all have rank correlations with their own next-11-day value between -0.07 and +0.09, none more than 2.6 standard errors from zero. A coin labelled trending is choppy 14 days later 88-92% of the time, the same as a coin labelled choppy (89%).
4. **Used the intuitive way, coin selection makes both strategies worse** (68 harness variants, all on design): EMA trend following restricted to the coins that have been trending: -43% to -50% against -10% to -39% unfiltered; z-score mean reversion restricted to the coins that have been choppy: -54% to -78% against -50% unfiltered. The opposite choice looked better at two lookbacks (+40% and +51%) but the midpoint I fixed in advance (21 days) returned +0.7% and every variant is negative under stress costs. No plateau, no candidate that clears the bar.

## 1. Method

Definitions (all in `measures.py`; a window `[a, b)` of hourly bars, signal at a close, traded at that close, which in a 24/7 market is the next open to within the spread):

| measure | definition | random-walk value |
|---|---|---|
| net return | `C[b-1] / C[a-1] - 1` | 0 |
| move | net log return / (hourly s.d. x sqrt(bars)): the move in units of what a driftless walk with this coin's volatility would do | N(0,1) |
| ER24 / ER72 / ER168 | mean over the window of Kaufman's efficiency ratio (net move / path length) at 24, 72, 168 h | 0.22 / 0.13 / 0.086 |
| x9/21, x24/100, x48/200 | number of hourly EMA crossovers in the window; run = window hours / (crossovers + 1) | 32 / 9.3 / 4.7 per 30 days |
| above100, above200 | share of bars with the close above the 100h / 200h EMA | 50% |
| trend P&L | always in the market: long while EMA24 > EMA100, short while below, reversing at each crossover; sum of per-position simple returns (equal stake, not compounded); net = minus 26 bp per position | gross 0 |
| MR P&L | start flat; buy at a close with 48h z-score <= -2, sell at the first close with z >= 0 (the 48h mean) or at the window end; sum of trade returns; net = minus 26 bp per trade. `mrs` is the mirror (short at z >= +2) | gross about 0 |
| VR24 | variance of 24h log returns / (24 x variance of 1h log returns); above 1 trending, below 1 mean-reverting | 1 (0.85-0.97 in short samples) |
| ac6 | lag-1 autocorrelation of non-overlapping 6h log returns | 0 |
| rvol_d | s.d. of hourly log returns x sqrt(24) | - |

26 bp per round trip = 2 x 10 bp taker fee + 2 x about 1 bp half-spread + 2 x 2 bp slippage (the harness defaults). The random-walk column is from 2,000 simulated paths with Student-t(4) hourly returns scaled to the coins' volatility (`null_ref.json`); it is the yardstick for "choppy": a coin is only unusually choppy if it crosses more, or is less efficient, than that.

**Classification rule (stated before looking at the result; 14-day lookback because 11 days are left).** With `move`, the EMA 24/100 crossover count `x` and `above100` measured over the trailing 336 bars:

- **trending-up**: move >= +1.0 and EMA24 > EMA100 at the last bar and x <= 2 and above100 >= 60%
- **trending-down**: move <= -1.0 and EMA24 < EMA100 at the last bar and x <= 2 and above100 <= 40%
- **choppy**: everything else

Loose variant: |move| >= 0.75, x <= 3, 55% / 45%. Strict: |move| >= 1.5, x <= 1, 70% / 30%. I did not adjust these after seeing that the base rule labels nothing as trending today; the loose and strict counts are shown instead.

**Persistence test (design only).** For 23 dates 11 days apart (bars 1320 to 7128, so the forward windows do not overlap), each coin's measure over the trailing 30 days is rank-correlated across the 50 coins with (a) the same measure over the next 11 days, (b) the next-11-day net trend P&L, (c) the next-11-day net MR P&L. Reported: mean of the 23 cross-sectional Spearman correlations, its standard error (s.d. / sqrt(23)), and the mean in each third of the dates. Repeated with the dates shifted by 88 and 176 bars and with 7-, 14- and 90-day lookbacks. Then the same question as money (top 10 against bottom 10 coins), as labels (transition matrix), at market level (does the cross-sectional average persist), and finally in the real harness with costs (`EmaCross` and `ZScoreMR` with a causal coin filter).

## 2. The census (full data, descriptive only)

### 2.1 All 50 coins by trailing window, against a random walk

| window | avg ret | median ret | ER24 | ER72 | ER168 | x9/21 | x24/100 | x48/200 | above 100h EMA | above 200h EMA | trend gross | trend net | coins trend net > 0 | trend long / short leg | MR gross | MR net | coins MR net > 0 | MR trades | MR-short net | median VR24 | coins VR24 < 1 | median ac6 | median daily vol |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 7d | +0.8% | +0.5% | 0.167 | 0.076 | 0.047 | 10.1 | 4.2 | 1.5 | 49% | 60% | -11.9% | -13.2% | 4 | -5.4% / -6.5% | +3.6% | +3.2% | 42 | 1.5 | +3.2% | 0.46 | 49 | -0.28 | 4.2% |
| 7d random walk | 0 | 0 | 0.223 | 0.130 | 0.086 | 7.6 | 2.2 | 1.1 | 50% | 50% | -0.3% | -1.1% | 23 | - | +0.3% | -0.1% | 26 | 1.7 | - | 0.78 | - | -0.03 | - |
| 14d | +2.0% | -0.8% | 0.187 | 0.093 | 0.075 | 18.2 | 6.4 | 2.0 | 57% | 72% | -18.3% | -20.2% | 7 | -8.0% / -10.4% | +6.9% | +6.1% | 45 | 3.4 | +5.4% | 0.73 | 42 | -0.08 | 5.0% |
| 14d random walk | 0 | 0 | 0.224 | 0.130 | 0.085 | 15.2 | 4.4 | 2.2 | 50% | 50% | -0.2% | -1.6% | 23 | - | +0.5% | -0.4% | 27 | 3.2 | - | 0.89 | - | -0.02 | - |
| 30d | +18.7% | +13.3% | 0.203 | 0.116 | 0.080 | 34.9 | 10.3 | 4.7 | 57% | 64% | -1.6% | -4.5% | 17 | +9.1% / -10.7% | +9.2% | +7.4% | 44 | 6.8 | -6.8% | 0.92 | 32 | +0.03 | 5.2% |
| 30d random walk | 0 | 0 | 0.224 | 0.131 | 0.086 | 32.3 | 9.3 | 4.7 | 50% | 50% | -0.8% | -3.5% | 22 | - | +0.9% | -0.9% | 26 | 6.7 | - | 0.96 | - | -0.01 | - |
| 90d | +62.1% | +53.9% | 0.204 | 0.118 | 0.080 | 101.0 | 29.4 | 15.1 | 51% | 55% | +16.6% | +8.7% | 22 | +38.1% / -21.6% | +15.1% | +9.9% | 39 | 20.0 | -40.9% | 0.99 | 28 | +0.00 | 4.2% |
| 90d random walk | 0 | 0 | 0.224 | 0.131 | 0.086 | 96.9 | 27.6 | 13.9 | 50% | 50% | +0.1% | -7.4% | 21 | - | +2.1% | -3.0% | 23 | 19.6 | - | 0.98 | - | -0.00 | - |

Reading: over 30 and 90 days the coins look like a random walk with drift (efficiency ratios 7-11% below the random-walk value, crossover counts 0-11% above it, variance ratio 0.92-0.99 against 0.96-0.98). Over the last 7-14 days they are clearly choppier than a random walk: ER72 0.076 against 0.130, 1.5 to 2 times the EMA 24/100 crossovers, variance ratio 0.46 against 0.78, 6h autocorrelation -0.28. The 90-day trend P&L is positive only through the long leg (+38.1%) in a market that rose +62%; the short leg lost -21.6%.

### 2.2 Classification today

| lookback | rule | trending-up | trending-down | choppy |
|---|---|---|---|---|
| 7d | base | 0 | 0 | 50 |
| 7d | loose | 2 | 2 | 46 |
| 7d | strict | 0 | 0 | 50 |
| 14d | base (the stated rule) | 0 | 0 | 50 |
| 14d | loose | 2 | 0 | 48 |
| 14d | strict | 0 | 0 | 50 |
| 30d | base | 0 | 0 | 50 |
| 30d | loose | 0 | 0 | 50 |
| 30d | strict | 0 | 0 | 50 |

Share of random-walk paths the same rules label trending (up + down): base 10.6% (about 5 of 50), loose 19.5% (about 10), strict 3.6% (about 2). Coins move together, so the real count swings between 0 and 20+ rather than sitting at 5; it is a reading of the whole market more than of 50 separate coins.

Direction without the quality tests, at the last bar: 19 coins are above their 200h EMA with EMA24 > EMA100, 19 are below both, 12 are mixed. So there is no lean either way, and with 6.4 crossovers per coin in 14 days that state has been flipping every 45 hours on average.

### 2.3 Ranked table: all 50 coins, most trend-friendly first (by 14-day net trend P&L)

State = close versus the 200h EMA, and whether EMA24 is above (+) or below (-) EMA100 at the last bar. x24/100 shows crossovers in 14 days and the average run between them in hours. All four windows and every measure are in `census.csv`.

| # | coin | class | state | ret 7d | ret 14d | ret 30d | ret 90d | ER72 14d | x9/21 14d | x24/100 14d (run) | x48/200 14d | above 100h 14d | above 200h 14d | trend net 14d | trend net 30d | MR net 14d (trades) | MR net 30d | VR24 14d | ac6 30d | daily vol 14d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SEI | choppy | +0.7% + | -1.6% | +18.9% | +50.0% | +54% | 0.133 | 15 | 2 (112h) | 0 | 73% | 96% | +18.3% | +66.1% | +2.3% (2) | -6.2% | 1.20 | +0.13 | 5.3% |
| 2 | CAKE | choppy | -5.1% - | -5.6% | -5.8% | +9.5% | +74% | 0.120 | 17 | 1 (168h) | 1 | 41% | 43% | +13.1% | +11.2% | -8.8% (3) | -3.2% | 0.77 | -0.06 | 3.5% |
| 3 | ZEC | choppy | -1.8% + | -3.1% | -11.1% | +11.2% | +190% | 0.108 | 16 | 2 (112h) | 1 | 36% | 42% | +7.9% | +3.4% | +1.1% (3) | +11.6% | 0.68 | +0.04 | 5.5% |
| 4 | SUI | choppy | +1.2% + | +3.4% | +18.0% | +49.0% | +66% | 0.102 | 14 | 2 (112h) | 0 | 81% | 99% | +6.0% | +50.3% | +10.4% (3) | +11.9% | 0.90 | +0.10 | 5.8% |
| 5 | HBAR | choppy | -1.8% - | -4.0% | +1.1% | +24.1% | +44% | 0.120 | 19 | 3 (84h) | 1 | 55% | 83% | +5.0% | +27.6% | +2.8% (1) | +2.5% | 2.03 | +0.08 | 5.8% |
| 6 | PAXG | choppy | -0.0% + | -0.2% | -4.3% | -5.6% | +2% | 0.133 | 18 | 1 (168h) | 0 | 10% | 2% | +4.0% | -1.2% | -2.2% (3) | -1.9% | 0.90 | -0.08 | 1.0% |
| 7 | LTC | choppy | -0.0% - | +2.8% | +10.1% | +27.9% | +59% | 0.125 | 17 | 3 (84h) | 0 | 72% | 90% | +2.7% | +10.8% | +2.2% (3) | -0.3% | 0.89 | +0.00 | 4.4% |
| 8 | ENA | choppy | -2.2% - | -4.8% | +14.5% | +35.6% | +221% | 0.124 | 12 | 5 (56h) | 3 | 57% | 71% | -2.9% | +49.8% | +8.7% (3) | +13.5% | 1.13 | -0.03 | 6.7% |
| 9 | ONDO | choppy | -0.2% - | -3.0% | +13.5% | +31.3% | +57% | 0.109 | 21 | 5 (56h) | 3 | 46% | 74% | -5.9% | +13.3% | +15.1% (5) | +14.3% | 1.25 | +0.04 | 6.5% |
| 10 | STO | choppy | -1.5% - | -5.3% | -4.4% | -1.2% | -6% | 0.095 | 16 | 3 (84h) | 3 | 45% | 54% | -6.2% | -2.2% | +4.2% (3) | +1.2% | 0.46 | -0.10 | 4.2% |
| 11 | POL | choppy | -2.7% - | -8.7% | -1.6% | +9.9% | +41% | 0.108 | 16 | 3 (84h) | 1 | 43% | 51% | -7.2% | -21.0% | +14.4% (5) | +20.2% | 0.80 | -0.15 | 4.8% |
| 12 | NEAR | choppy | +3.9% + | +3.2% | +17.9% | +111.6% | +172% | 0.099 | 13 | 4 (67h) | 2 | 71% | 88% | -8.4% | +59.8% | +7.0% (1) | +8.0% | 0.75 | +0.06 | 7.3% |
| 13 | BTC | choppy | +0.8% + | +2.4% | -0.7% | +7.2% | +37% | 0.097 | 25 | 10 (31h) | 0 | 69% | 89% | -9.8% | -1.9% | +0.0% (2) | +0.5% | 0.56 | +0.11 | 1.6% |
| 14 | TRX | choppy | -0.1% + | +0.2% | -1.7% | +0.2% | +2% | 0.109 | 22 | 12 (26h) | 1 | 31% | 26% | -10.4% | -9.7% | +0.9% (3) | +0.2% | 0.64 | -0.10 | 0.8% |
| 15 | 1000CHEEMS | choppy | -1.2% + | +1.1% | -5.4% | -0.7% | +16% | 0.096 | 13 | 4 (67h) | 2 | 54% | 59% | -12.2% | -3.3% | +4.3% (5) | +7.4% | 0.92 | -0.03 | 3.0% |
| 16 | BNB | choppy | +0.1% + | +3.2% | -0.9% | +4.1% | +37% | 0.086 | 20 | 10 (31h) | 2 | 53% | 77% | -12.6% | -12.4% | +0.8% (4) | +3.7% | 0.60 | -0.06 | 1.7% |
| 17 | AAVE | choppy | +5.1% + | +10.0% | +26.2% | +37.3% | +107% | 0.110 | 19 | 4 (67h) | 0 | 85% | 96% | -13.8% | -12.0% | +5.6% (3) | +7.0% | 1.09 | +0.18 | 4.9% |
| 18 | XRP | choppy | +0.1% + | +0.6% | -5.3% | +6.6% | +38% | 0.070 | 18 | 6 (48h) | 4 | 49% | 63% | -14.5% | -25.6% | +2.5% (2) | +8.1% | 0.62 | -0.04 | 3.1% |
| 19 | ARB | choppy | -0.3% - | -0.7% | -6.7% | +11.1% | +167% | 0.067 | 26 | 5 (56h) | 1 | 38% | 44% | -14.6% | +21.5% | +5.3% (3) | +23.5% | 0.54 | +0.02 | 5.7% |
| 20 | SOL | choppy | +0.9% + | +1.7% | +2.1% | +14.5% | +56% | 0.086 | 20 | 4 (67h) | 0 | 68% | 95% | -15.2% | -9.9% | +2.8% (3) | +5.5% | 0.60 | +0.04 | 2.7% |
| 21 | LINK | choppy | -0.4% - | -4.5% | +7.4% | +12.9% | +83% | 0.100 | 12 | 7 (42h) | 1 | 57% | 78% | -16.0% | +1.0% | +6.8% (4) | +6.3% | 0.96 | +0.05 | 4.4% |
| 22 | UNI | choppy | -4.1% - | -3.8% | -6.5% | +21.0% | +160% | 0.085 | 19 | 9 (34h) | 7 | 49% | 57% | -16.8% | +0.7% | +0.1% (4) | +3.3% | 0.67 | +0.09 | 5.2% |
| 23 | ICP | choppy | +2.2% + | -0.6% | +13.5% | +27.2% | +54% | 0.078 | 19 | 4 (67h) | 0 | 78% | 95% | -17.0% | -15.2% | +10.8% (4) | +18.6% | 0.61 | +0.09 | 5.8% |
| 24 | FIL | choppy | +7.5% + | +8.4% | +15.3% | +45.4% | +51% | 0.094 | 16 | 8 (37h) | 2 | 66% | 82% | -17.7% | -16.9% | +13.1% (4) | +11.8% | 0.88 | +0.08 | 5.8% |
| 25 | FET | choppy | +2.4% + | +7.0% | +17.7% | +40.3% | +52% | 0.122 | 21 | 4 (67h) | 0 | 66% | 90% | -19.4% | -9.7% | +11.1% (4) | +8.9% | 1.15 | +0.12 | 6.3% |
| 26 | WLD | choppy | +1.2% - | +12.1% | +19.6% | +33.9% | +43% | 0.116 | 9 | 5 (56h) | 0 | 74% | 92% | -20.1% | -6.5% | +11.2% (4) | +3.6% | 1.25 | -0.03 | 6.8% |
| 27 | WIF | choppy | -0.9% - | +3.0% | -5.1% | +14.3% | +56% | 0.066 | 21 | 5 (56h) | 0 | 75% | 91% | -22.1% | +16.0% | +12.2% (3) | +16.3% | 0.44 | +0.02 | 5.8% |
| 28 | TUT | choppy | -0.5% + | +3.5% | -1.3% | -4.0% | +154% | 0.104 | 15 | 8 (37h) | 2 | 62% | 73% | -22.1% | +17.1% | +1.7% (2) | -4.6% | 0.50 | +0.03 | 6.5% |
| 29 | ADA | choppy | +6.1% + | +11.3% | +7.2% | +23.6% | +62% | 0.086 | 18 | 6 (48h) | 2 | 61% | 78% | -22.2% | -17.9% | +7.4% (3) | +8.7% | 0.72 | -0.10 | 4.5% |
| 30 | ETH | choppy | -0.2% + | +0.1% | -2.2% | +8.1% | +55% | 0.066 | 29 | 10 (31h) | 0 | 57% | 85% | -22.2% | -29.9% | -0.4% (3) | +1.2% | 0.44 | -0.06 | 1.8% |
| 31 | APT | choppy | +4.0% + | +5.9% | +6.5% | +36.0% | +35% | 0.078 | 16 | 10 (31h) | 4 | 61% | 75% | -24.0% | -1.7% | +6.1% (2) | +7.4% | 0.56 | -0.02 | 5.5% |
| 32 | EIGEN | choppy | -1.5% - | -0.9% | +1.7% | +17.7% | +6% | 0.078 | 19 | 5 (56h) | 4 | 56% | 74% | -24.0% | -20.8% | +2.8% (3) | +20.7% | 0.71 | -0.13 | 6.0% |
| 33 | BONK | choppy | -1.4% - | +0.5% | +3.4% | +7.9% | -9% | 0.082 | 19 | 5 (56h) | 0 | 78% | 88% | -24.1% | +14.3% | +9.9% (4) | -2.5% | 0.59 | +0.03 | 6.3% |
| 34 | CFX | choppy | +0.6% + | +0.6% | -0.3% | +10.8% | +30% | 0.070 | 22 | 8 (37h) | 2 | 62% | 79% | -24.4% | -18.4% | +9.6% (4) | +4.7% | 0.69 | -0.06 | 3.7% |
| 35 | VIRTUAL | choppy | -0.2% + | -0.1% | +9.3% | +16.0% | +54% | 0.091 | 15 | 8 (37h) | 0 | 76% | 95% | -25.4% | +1.0% | +17.4% (4) | +22.6% | 0.54 | -0.07 | 6.0% |
| 36 | PENDLE | choppy | -2.4% + | +1.5% | -2.5% | +13.1% | +59% | 0.078 | 20 | 5 (56h) | 4 | 49% | 52% | -28.8% | -37.0% | +0.5% (4) | +12.2% | 0.58 | -0.02 | 5.1% |
| 37 | DOGE | choppy | -0.8% + | +0.1% | -6.2% | +4.7% | +29% | 0.080 | 25 | 8 (37h) | 4 | 51% | 67% | -31.6% | -17.5% | +3.3% (3) | +7.5% | 0.72 | +0.05 | 3.5% |
| 38 | TAO | choppy | +0.5% + | +0.2% | -2.8% | +13.4% | +49% | 0.081 | 22 | 8 (37h) | 2 | 56% | 84% | -32.2% | -4.4% | +8.3% (3) | +2.2% | 0.78 | +0.04 | 4.9% |
| 39 | PEPE | choppy | -1.6% - | +1.2% | -12.5% | +18.6% | +65% | 0.083 | 17 | 11 (28h) | 4 | 37% | 63% | -38.7% | -14.9% | -1.2% (4) | +0.4% | 0.80 | +0.13 | 4.5% |
| 40 | SHIB | choppy | -0.6% + | +0.5% | -4.8% | +6.3% | +35% | 0.073 | 21 | 10 (31h) | 4 | 56% | 69% | -38.8% | -31.2% | +4.3% (3) | +4.7% | 0.74 | +0.04 | 3.5% |
| 41 | XLM | choppy | -2.3% - | -3.8% | -1.6% | +15.8% | +17% | 0.079 | 17 | 9 (34h) | 3 | 59% | 75% | -39.7% | -40.9% | +16.0% (5) | +19.5% | 0.83 | +0.04 | 4.4% |
| 42 | AVAX | choppy | +4.3% + | +1.1% | +4.3% | +49.7% | +77% | 0.082 | 18 | 8 (37h) | 0 | 66% | 96% | -42.8% | -4.4% | +9.0% (5) | +10.4% | 0.79 | +0.04 | 4.6% |
| 43 | S | choppy | +6.9% + | +14.7% | -0.7% | +42.0% | +73% | 0.084 | 20 | 6 (48h) | 4 | 63% | 76% | -43.2% | +14.1% | +6.0% (3) | +5.9% | 0.64 | -0.03 | 5.4% |
| 44 | DOT | choppy | +0.9% + | +1.8% | +2.6% | +25.9% | +47% | 0.073 | 20 | 8 (37h) | 2 | 64% | 75% | -43.5% | -18.1% | +13.5% (4) | +15.6% | 0.65 | -0.08 | 4.8% |
| 45 | CRV | choppy | -2.3% - | -5.9% | +1.1% | -4.3% | +78% | 0.085 | 18 | 11 (28h) | 5 | 57% | 72% | -44.6% | -56.5% | +9.3% (4) | +5.1% | 1.04 | +0.08 | 5.3% |
| 46 | TRUMP | choppy | -2.3% - | -0.9% | -8.8% | -13.2% | +25% | 0.074 | 15 | 7 (42h) | 7 | 44% | 43% | -44.9% | -24.2% | +2.1% (3) | +5.8% | 0.62 | -0.04 | 5.2% |
| 47 | FLOKI | choppy | +3.6% + | +6.6% | -2.5% | +12.0% | +30% | 0.084 | 16 | 10 (31h) | 6 | 55% | 65% | -45.7% | -26.1% | +4.6% (3) | +0.8% | 0.78 | +0.09 | 4.4% |
| 48 | ZEN | choppy | -1.3% + | +1.1% | -12.7% | -4.7% | +72% | 0.095 | 24 | 10 (31h) | 3 | 41% | 33% | -47.5% | -30.8% | -2.5% (3) | +3.8% | 0.97 | -0.16 | 5.5% |
| 49 | PENGU | choppy | -3.0% - | -6.4% | -9.2% | +6.3% | +50% | 0.087 | 15 | 11 (28h) | 2 | 62% | 73% | -47.6% | -0.9% | +21.2% (4) | +16.3% | 0.52 | -0.09 | 6.4% |
| 50 | LISTA | choppy | -3.7% - | -6.1% | -5.5% | +4.4% | +74% | 0.077 | 13 | 9 (34h) | 3 | 55% | 66% | -48.4% | -59.9% | +9.0% (5) | +7.7% | 0.85 | +0.03 | 4.4% |

Counts from this table: net trend P&L positive on 4 / 7 / 17 / 22 of 50 coins over 7 / 14 / 30 / 90 days, on 6 in both the 14- and 30-day windows and on 1 in all four. Net MR P&L positive on 42 / 45 / 44 / 39, on 41 in both the 14- and 30-day windows and on 29 in all four. Section 3 shows why these counts are a description of the past and not a list of coins to trade.

### 2.4 The market month by month

Base rule read at every 00:00 UTC; the table gives the average number of coins in each class over the month (and the range of the daily count), next to what the two descriptive rules made per coin in that calendar month. Months to 2026-03-11 are the design period.

| month | avg coin | BTC | trending-up (range) | trending-down (range) | choppy | trend net / coin | coins trend > 0 | long leg | short leg | MR net / coin | coins MR > 0 | MR-short net | x24/100 per coin | median VR24 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-06 | -3.3% | +2.6% | 0.4 (0-2) | 2.8 (0-13) | 46.8 | -8.5% | 9 | -4.6% | -1.4% | -11.2% | 7 | -7.7% | 8.7 | 1.04 |
| 2025-07 | +25.0% | +7.8% | 5.8 (0-24) | 0.0 (0-1) | 44.1 | +8.8% | 29 | +19.0% | -7.5% | +1.7% | 27 | -12.6% | 9.5 | 0.93 |
| 2025-08 | -0.2% | -6.2% | 0.3 (0-2) | 0.4 (0-3) | 49.3 | -21.6% | 5 | -9.3% | -9.5% | +2.8% | 31 | +0.6% | 10.2 | 0.94 |
| 2025-09 | +1.2% | +5.4% | 1.5 (0-4) | 1.6 (0-11) | 46.9 | -0.6% | 21 | +1.8% | +0.0% | -0.4% | 28 | -5.3% | 8.4 | 0.91 |
| 2025-10 | -4.8% | -4.1% | 1.1 (0-4) | 2.7 (0-9) | 46.1 | -0.1% | 28 | -3.4% | +6.2% | -8.3% | 7 | -6.2% | 10.2 | 1.04 |
| 2025-11 | -20.9% | -17.7% | 0.3 (0-2) | 7.1 (0-24) | 42.5 | +9.6% | 36 | -4.3% | +16.0% | -9.5% | 7 | +0.5% | 7.1 | 0.84 |
| 2025-12 | -10.7% | +0.7% | 0.2 (0-1) | 4.5 (0-11) | 45.4 | -15.9% | 11 | -14.4% | +1.6% | +1.2% | 25 | +6.2% | 11.0 | 0.80 |
| 2026-01 | -14.7% | -10.3% | 2.1 (0-5) | 5.2 (0-32) | 42.6 | +17.6% | 46 | +4.2% | +15.4% | -15.1% | 2 | -10.3% | 6.9 | 0.98 |
| 2026-02 | -14.0% | -15.1% | 0.0 (0-1) | 19.4 (0-46) | 30.6 | +0.5% | 23 | -5.5% | +8.0% | +0.5% | 23 | -0.1% | 6.6 | 1.03 |
| 2026-03 | +2.4% | +2.2% | 1.0 (0-4) | 0.9 (0-6) | 48.2 | -10.9% | 8 | -3.6% | -4.5% | -7.3% | 12 | -2.4% | 9.7 | 0.92 |
| 2026-04 | +4.9% | +11.7% | 0.6 (0-3) | 1.5 (0-9) | 48.0 | -27.1% | 7 | -9.0% | -14.4% | +1.7% | 30 | +6.3% | 13.0 | 0.92 |
| 2026-05 | +3.5% | -3.6% | 1.5 (0-5) | 2.5 (0-17) | 46.0 | +6.1% | 30 | +6.5% | +2.0% | +0.1% | 27 | -6.2% | 8.6 | 0.87 |
| 2026-06 | -21.7% | -20.7% | 0.1 (0-1) | 6.6 (0-20) | 43.3 | +5.9% | 36 | -6.8% | +15.0% | -10.4% | 7 | +2.0% | 7.9 | 0.70 |
| 2026-07 | +2.7% | +7.4% | 0.7 (0-3) | 1.0 (0-3) | 48.3 | -12.4% | 8 | -3.3% | -6.0% | +0.0% | 25 | -3.3% | 10.8 | 0.82 |
| 2026-08 | +24.2% | +24.9% | 2.4 (0-9) | 1.1 (0-5) | 46.5 | +19.9% | 35 | +26.2% | -3.6% | +2.9% | 35 | -30.3% | 9.3 | 0.97 |
| 2026-09 | +31.4% | +6.3% | 2.5 (0-12) | 0.2 (0-1) | 47.3 | +8.9% | 26 | +20.7% | -9.4% | +5.3% | 40 | -12.3% | 8.5 | 0.94 |
| 2026-10 (6 days) | -0.1% | +2.5% | 2.0 (0-5) | 0.2 (0-1) | 47.8 | - | - | - | - | - | - | - | - | - |

- In 16 of 17 months at least 42 of 50 coins were choppy on the average day. The one clear exception is February 2026 (19 coins trending-down on average). "Choppy" is the normal state of this universe at the hourly scale, not a regime that comes and goes.
- The trend rule made money per coin in 8 of 16 full months and the dip-buy in 9 of 16; the correlation between the two monthly series is -0.24. Good trend months were the big directional ones (Nov 2025 and Jan 2026 down via the short leg, Jul 2025 and Aug-Sep 2026 up via the long leg). Dip-buying was positive mainly when the market was flat or rising and lost 7-15% per coin in six of the 16 months, five of them months in which the average coin fell (Jun, Oct, Nov 2025, Jan, Jun 2026; also Mar 2026).
- Last 30 days, daily count up / down / choppy: 09-07 3/0/47, 09-08 3/0/47, 09-09 1/0/49, 09-10 1/1/48, 09-11 0/1/49, 09-12 0/1/49, 09-13 1/1/48, 09-14 2/1/47, 09-15 2/1/47, 09-16 0/0/50, 09-17 0/0/50, 09-18 1/0/49, 09-19 1/0/49, 09-20 0/0/50, 09-21 0/0/50, 09-22 0/0/50, 09-23 0/0/50, 09-24 0/0/50, 09-25 6/0/44, 09-26 12/0/38, 09-27 12/0/38, 09-28 9/0/41, 09-29 4/0/46, 09-30 4/0/46, 10-01 5/0/45, 10-02 2/0/48, 10-03 1/0/49, 10-04 3/0/47, 10-05 1/1/48, 10-06 0/0/50. A burst to 12 coins trending-up on 26-27 September had faded to 0 by 6 October.

## 3. Is character persistent? (design data only)

### 3.1 Rank correlation of each trailing-30-day measure with the next 11 days (23 non-overlapping dates x 50 coins)

Mean cross-sectional Spearman correlation +/- standard error, then the mean in each third of the dates. With 63 cells in this table about three would exceed two standard errors by chance.

| trailing 30-day measure | with the same measure, next 11 days | with next-11-day net trend P&L | with next-11-day net MR P&L |
|---|---|---|---|
| net_ret | -0.018 +/- 0.055 (+0.02 / +0.06 / -0.16) | +0.015 +/- 0.046 (+0.05 / +0.00 / -0.01) | +0.047 +/- 0.044 (+0.09 / +0.06 / -0.02) |
| move | -0.002 +/- 0.044 (+0.09 / -0.06 / -0.04) | +0.038 +/- 0.046 (+0.05 / +0.02 / +0.05) | +0.040 +/- 0.038 (+0.09 / +0.03 / -0.00) |
| absmove | -0.054 +/- 0.034 (-0.08 / -0.07 / -0.01) | -0.040 +/- 0.046 (-0.05 / -0.02 / -0.05) | +0.026 +/- 0.030 (+0.07 / +0.04 / -0.04) |
| er24 | +0.054 +/- 0.035 (-0.02 / +0.05 / +0.14) | -0.039 +/- 0.034 (-0.06 / +0.08 / -0.15) | +0.035 +/- 0.038 (+0.12 / -0.03 / +0.01) |
| er72 | +0.002 +/- 0.026 (+0.03 / +0.04 / -0.07) | -0.092 +/- 0.029 (-0.11 / -0.02 / -0.16) | +0.016 +/- 0.030 (+0.07 / +0.01 / -0.04) |
| er168 | -0.025 +/- 0.036 (+0.01 / -0.01 / -0.08) | -0.079 +/- 0.029 (-0.10 / -0.01 / -0.13) | -0.019 +/- 0.031 (+0.05 / -0.03 / -0.09) |
| x9_21 | +0.083 +/- 0.042 (+0.14 / +0.08 / +0.03) | +0.021 +/- 0.031 (+0.07 / -0.08 / +0.08) | -0.012 +/- 0.036 (-0.03 / +0.00 / -0.00) |
| x24_100 | -0.070 +/- 0.027 (-0.05 / -0.03 / -0.14) | +0.090 +/- 0.032 (+0.06 / -0.00 / +0.23) | +0.006 +/- 0.031 (+0.02 / +0.07 / -0.08) |
| x48_200 | -0.060 +/- 0.033 (-0.09 / -0.07 / -0.01) | +0.085 +/- 0.031 (+0.09 / +0.08 / +0.08) | +0.017 +/- 0.036 (+0.02 / +0.04 / -0.01) |
| above100 | +0.092 +/- 0.053 (+0.24 / +0.06 / -0.04) | +0.043 +/- 0.040 (+0.03 / +0.05 / +0.05) | +0.021 +/- 0.040 (+0.05 / +0.04 / -0.04) |
| onesided | -0.070 +/- 0.049 (-0.06 / -0.07 / -0.09) | -0.046 +/- 0.045 (-0.02 / -0.04 / -0.08) | +0.012 +/- 0.033 (+0.01 / -0.06 / +0.10) |
| trend_gross | -0.058 +/- 0.038 (-0.03 / +0.02 / -0.18) | -0.058 +/- 0.038 (-0.03 / +0.01 / -0.18) | +0.002 +/- 0.032 (+0.07 / -0.04 / -0.02) |
| trend_net | -0.060 +/- 0.038 (-0.02 / +0.02 / -0.19) | -0.060 +/- 0.038 (-0.02 / +0.02 / -0.19) | +0.002 +/- 0.032 (+0.06 / -0.04 / -0.02) |
| trend_long | +0.024 +/- 0.052 (+0.08 / +0.10 / -0.13) | -0.004 +/- 0.043 (+0.03 / +0.06 / -0.11) | +0.002 +/- 0.039 (+0.06 / -0.00 / -0.07) |
| trend_short | -0.064 +/- 0.041 (-0.09 / +0.03 / -0.14) | -0.079 +/- 0.035 (-0.09 / -0.03 / -0.13) | -0.007 +/- 0.041 (+0.01 / -0.05 / +0.03) |
| mr_gross | -0.009 +/- 0.040 (-0.01 / -0.03 / +0.01) | +0.018 +/- 0.042 (+0.06 / -0.03 / +0.02) | -0.009 +/- 0.039 (-0.00 / -0.03 / +0.01) |
| mr_net | -0.008 +/- 0.040 (+0.00 / -0.03 / +0.01) | +0.020 +/- 0.042 (+0.06 / -0.02 / +0.02) | -0.008 +/- 0.040 (+0.00 / -0.03 / +0.01) |
| mrs_net | -0.019 +/- 0.039 (+0.11 / -0.08 / -0.09) | +0.022 +/- 0.036 (-0.01 / +0.00 / +0.08) | -0.036 +/- 0.039 (-0.11 / -0.06 / +0.07) |
| vr24 | -0.055 +/- 0.031 (-0.03 / -0.08 / -0.05) | -0.018 +/- 0.030 (-0.00 / +0.05 / -0.11) | +0.016 +/- 0.035 (+0.06 / -0.02 / +0.01) |
| ac6 | -0.046 +/- 0.034 (-0.08 / -0.13 / +0.09) | -0.025 +/- 0.034 (+0.01 / -0.01 / -0.09) | +0.014 +/- 0.038 (+0.05 / -0.04 / +0.03) |
| rvol_d | +0.772 +/- 0.016 (+0.81 / +0.75 / +0.75) | +0.023 +/- 0.039 (-0.07 / +0.04 / +0.11) | +0.053 +/- 0.049 (+0.13 / +0.00 / +0.02) |

- **Persists:** realised volatility only (+0.77, every third above +0.74). A volatile coin stays volatile; that is useful for sizing and stops, not for choosing a strategy.
- **Does not persist:** efficiency ratio at any horizon (+0.05, +0.00, -0.03), variance ratio (-0.05), 6h autocorrelation (-0.05), net return (-0.02), trend P&L (-0.06), MR P&L (-0.01). Last month's choppy coins are not next week's choppy coins.
- **Weakly reverses:** the EMA 24/100 crossover count (-0.070 +/- 0.027) and, as a predictor of trend P&L, ER72 (-0.092 +/- 0.029) and the crossover count (+0.090 +/- 0.032). Coins that trended cleanly last month did slightly *worse* on trend following in the next 11 days. These are about three standard errors, the best of 63 cells, and the size (0.09) is too small to trade: section 3.6 confirms that.
- **Nothing predicts MR P&L:** the largest entry in the last column is 0.053, about one standard error.

### 3.2 Same test with the dates shifted, and with other lookbacks (mean correlation only: same measure / trend net / MR net)

| measure | 30d, dates +88 bars | 30d, dates +176 bars | 7d lookback (+/- s.e. for *same*) | 14d lookback | 90d lookback (18 dates) |
|---|---|---|---|---|---|
| net_ret | -0.02 / -0.01 / +0.07 | -0.05 / -0.00 / +0.13 | +0.08 / -0.03 / -0.05 (+/- 0.04) | +0.01 / +0.02 / -0.04 | +0.01 / -0.03 / +0.09 |
| move | -0.01 / +0.01 / +0.07 | +0.03 / +0.02 / +0.13 | +0.12 / -0.03 / -0.02 (+/- 0.04) | +0.02 / +0.03 / -0.02 | -0.01 / +0.02 / +0.09 |
| absmove | -0.06 / -0.05 / -0.02 | +0.03 / +0.00 / -0.05 | -0.07 / -0.01 / +0.05 (+/- 0.04) | -0.01 / -0.02 / +0.00 | -0.01 / -0.08 / -0.04 |
| er24 | +0.06 / +0.00 / +0.05 | +0.09 / -0.02 / +0.05 | -0.02 / -0.07 / +0.07 (+/- 0.03) | +0.01 / -0.09 / +0.08 | +0.14 / -0.02 / +0.00 |
| er72 | -0.04 / -0.08 / +0.04 | -0.01 / -0.09 / +0.06 | -0.01 / -0.12 / +0.09 (+/- 0.04) | -0.02 / -0.14 / +0.02 | +0.07 / -0.06 / +0.03 |
| er168 | +0.01 / -0.06 / -0.03 | -0.06 / -0.10 / +0.00 | +0.08 / -0.10 / +0.02 (+/- 0.03) | -0.00 / -0.10 / -0.01 | +0.02 / -0.01 / -0.00 |
| x9_21 | +0.09 / +0.03 / -0.01 | +0.08 / +0.05 / -0.00 | -0.04 / +0.07 / -0.08 (+/- 0.03) | +0.01 / +0.02 / -0.04 | +0.08 / +0.00 / +0.04 |
| x24_100 | -0.07 / +0.11 / -0.02 | -0.06 / +0.08 / -0.00 | -0.01 / +0.01 / -0.01 (+/- 0.04) | -0.08 / +0.05 / +0.00 | -0.03 / +0.02 / -0.02 |
| x48_200 | -0.07 / +0.03 / +0.03 | -0.08 / +0.08 / +0.01 | -0.03 / +0.06 / -0.02 (+/- 0.04) | -0.08 / +0.04 / +0.04 | -0.04 / +0.02 / -0.02 |
| above100 | +0.07 / +0.01 / +0.05 | +0.12 / +0.05 / +0.07 | +0.23 / -0.01 / -0.00 (+/- 0.03) | +0.17 / +0.01 / -0.00 | +0.09 / -0.02 / +0.04 |
| onesided | -0.07 / -0.04 / -0.00 | -0.05 / -0.03 / -0.01 | +0.06 / -0.02 / +0.06 (+/- 0.04) | -0.07 / -0.03 / -0.02 | -0.01 / +0.03 / -0.01 |
| trend_gross | -0.06 / -0.06 / +0.03 | -0.09 / -0.09 / +0.05 | -0.06 / -0.06 / +0.04 (+/- 0.04) | -0.09 / -0.09 / -0.00 | +0.02 / +0.02 / +0.04 |
| trend_net | -0.06 / -0.06 / +0.03 | -0.09 / -0.09 / +0.04 | -0.06 / -0.06 / +0.04 (+/- 0.04) | -0.09 / -0.09 / -0.01 | +0.02 / +0.02 / +0.04 |
| trend_long | -0.05 / -0.04 / +0.04 | -0.08 / -0.05 / +0.08 | -0.01 / -0.08 / +0.01 (+/- 0.04) | -0.03 / -0.06 / -0.03 | +0.01 / +0.01 / +0.07 |
| trend_short | -0.08 / -0.05 / -0.02 | -0.06 / -0.08 / -0.05 | -0.02 / -0.04 / +0.05 (+/- 0.04) | -0.04 / -0.06 / +0.00 | +0.00 / +0.01 / -0.02 |
| mr_gross | -0.03 / +0.07 / -0.03 | -0.02 / +0.04 / -0.02 | -0.08 / +0.09 / -0.08 (+/- 0.04) | -0.06 / +0.08 / -0.06 | +0.01 / -0.01 / +0.01 |
| mr_net | -0.03 / +0.07 / -0.03 | -0.02 / +0.03 / -0.02 | -0.08 / +0.09 / -0.08 (+/- 0.04) | -0.06 / +0.09 / -0.06 | +0.01 / -0.02 / +0.01 |
| mrs_net | -0.03 / +0.02 / -0.05 | -0.08 / +0.01 / -0.12 | +0.02 / +0.07 / +0.00 (+/- 0.04) | +0.01 / +0.08 / -0.01 | -0.05 / -0.00 / -0.08 |
| vr24 | -0.04 / -0.02 / +0.06 | -0.07 / +0.00 / +0.04 | +0.01 / -0.04 / +0.03 (+/- 0.04) | +0.01 / -0.07 / +0.05 | +0.02 / -0.00 / +0.01 |
| ac6 | -0.01 / +0.02 / +0.05 | -0.03 / -0.02 / +0.04 | +0.03 / -0.04 / +0.04 (+/- 0.03) | -0.00 / -0.09 / +0.03 | -0.07 / -0.02 / +0.01 |
| rvol_d | +0.77 / +0.04 / +0.04 | +0.76 / +0.05 / +0.08 | +0.78 / +0.01 / +0.03 (+/- 0.01) | +0.77 / +0.02 / +0.06 | +0.73 / +0.08 / -0.04 |

The picture does not change with the date grid or the lookback. Two small exceptions, neither usable: the share of time above the 100h EMA carries over from a 7-day lookback (+0.23), which is mostly mechanical (a coin above its EMA today starts the next window above it) and does not predict either P&L (-0.01, -0.00); and ER24 measured over 90 days has a little persistence (+0.14 +/- 0.04), a mild coin trait that again predicts neither P&L. The negative link from trailing ER72 to next-11-day trend P&L appears at every lookback up to 30 days (-0.12, -0.14, -0.09) and fades at 90 (-0.06).

### 3.3 In money: top 10 against bottom 10 coins by the trailing-30-day measure, next-11-day net P&L per coin

| ranked by -> outcome | top 10 | bottom 10 | all 50 | spread +/- s.e. | dates spread > 0 | top 10 by thirds | bottom 10 by thirds |
|---|---|---|---|---|---|---|---|
| trend_net->trend_net | -1.66% | +0.00% | -0.62% | -1.66% +/- 1.26% | 35% | -2.0% / -0.9% / -2.1% | -2.8% / -0.6% / +3.9% |
| trend_gross->trend_net | -1.46% | +0.13% | -0.62% | -1.59% +/- 1.24% | 35% | -2.1% / -0.7% / -1.6% | -2.5% / -0.4% / +3.8% |
| er72->trend_net | -2.12% | -0.19% | -0.62% | -1.93% +/- 1.40% | 39% | -3.9% / -0.3% / -2.2% | -1.5% / -1.5% / +2.9% |
| er168->trend_net | -1.67% | +0.08% | -0.62% | -1.76% +/- 1.52% | 26% | -4.7% / +1.8% / -2.1% | -1.9% / -0.3% / +2.7% |
| x24_100->trend_net | -0.15% | -4.60% | -0.62% | +4.44% +/- 1.47% | 87% | -1.3% / -1.1% / +2.3% | -7.2% / -2.5% / -4.1% |
| absmove->trend_net | -1.39% | -0.22% | -0.62% | -1.17% +/- 1.92% | 30% | -2.7% / -1.0% / -0.4% | -1.9% / -0.9% / +2.5% |
| vr24->trend_net | +0.32% | -0.40% | -0.62% | +0.72% +/- 1.43% | 43% | -1.2% / +2.9% / -0.9% | -3.0% / -0.8% / +3.1% |
| rvol_d->trend_net | -0.01% | -1.05% | -0.62% | +1.04% +/- 1.41% | 57% | -4.2% / +2.1% / +2.3% | -0.7% / -1.9% / -0.5% |
| net_ret->trend_net | -0.74% | -1.43% | -0.62% | +0.68% +/- 1.91% | 48% | -2.5% / +0.9% / -0.6% | -2.6% / -2.0% / +0.5% |
| mr_net->mr_net | -0.68% | -0.97% | -1.12% | +0.30% +/- 0.95% | 52% | +0.5% / -0.7% / -1.9% | +0.9% / -1.9% / -2.1% |
| mr_gross->mr_net | -0.71% | -1.01% | -1.12% | +0.30% +/- 1.01% | 57% | +0.4% / -0.7% / -1.9% | +0.8% / -2.0% / -1.9% |
| x24_100->mr_net | -0.69% | -0.55% | -1.12% | -0.14% +/- 0.55% | 43% | +1.6% / -1.8% / -2.0% | +1.4% / -1.8% / -1.4% |
| er72->mr_net | -1.01% | -1.14% | -1.12% | +0.12% +/- 0.57% | 48% | +1.8% / -2.4% / -2.7% | +0.5% / -1.7% / -2.3% |
| vr24->mr_net | -0.81% | -1.05% | -1.12% | +0.24% +/- 0.75% | 74% | +0.8% / -2.0% / -1.3% | +0.3% / -1.7% / -1.8% |
| ac6->mr_net | -1.63% | -0.72% | -1.12% | -0.91% +/- 0.96% | 52% | +0.6% / -3.1% / -2.5% | +0.5% / -1.0% / -1.8% |
| rvol_d->mr_net | -0.25% | -1.06% | -1.12% | +0.82% +/- 0.76% | 65% | +1.4% / -0.2% / -2.1% | +0.3% / -1.3% / -2.3% |
| net_ret->mr_net | -0.09% | -1.44% | -1.12% | +1.35% +/- 1.06% | 65% | +1.9% / +0.1% / -2.6% | +0.0% / -2.1% / -2.4% |
| trend_net->mr_net | -0.99% | -1.36% | -1.12% | +0.37% +/- 0.62% | 57% | +1.9% / -2.1% / -3.0% | +0.1% / -2.4% / -1.8% |
| net_ret->net_ret | -1.26% | -1.64% | -1.68% | +0.37% +/- 2.34% | 43% | +3.8% / -1.0% / -7.4% | +4.9% / -7.5% / -2.5% |

Picking last month's best trend coins gives a *lower* trend P&L than picking the worst (-1.66%), and the same for the highest efficiency ratio. The only spread beyond two standard errors is the crossover count: the 10 coins with the *fewest* crossovers last month made -4.60% per 11 days on the trend rule (negative in all three thirds), the 10 with the most -0.15%. That is one result out of 19 rows, it says "avoid the coins that just had a long clean run" rather than "there is a group that works", and the top group is still not positive. For mean reversion no ranking separates winners from losers: every spread is within 1.3 standard errors of zero and both groups lose in the last third in every row.

### 3.4 Do the labels persist?

**base rule**, label now against label 14 days later (18 non-overlapping dates x 50 coins):

| now \ 14 days later | up | choppy | down | coin-dates |
|---|---|---|---|---|
| trending-up | 6% | 88% | 6% | 17 |
| choppy | 2% | 89% | 9% | 797 |
| trending-down | 0% | 92% | 8% | 86 |
| all | 1.8% | 89.4% | 8.8% | 900 |

| label today | dates with any | coin-dates | next-11d trend net (+/- s.e.) | by thirds | long leg | short leg | next-11d MR net | next-11d MR-short net | next-11d coin return |
|---|---|---|---|---|---|---|---|---|---|
| up | 11 | 32 | -2.32% +/- 4.67% | -12.0% / +2.2% / +5.9% | +0.90% | -2.30% | -2.33% +/- 1.76% | -4.68% | +3.51% |
| chop | 23 | 991 | -0.12% +/- 2.17% | -0.9% / -0.3% / +1.1% | -0.33% | +1.29% | -1.12% +/- 1.06% | -1.29% | -1.66% |
| down | 14 | 127 | -0.04% +/- 3.01% | -8.7% / +4.8% / -2.0% | -1.61% | +2.64% | -1.70% +/- 1.63% | +0.42% | -4.22% |
| all | 23 | 1150 | -0.62% +/- 2.15% | -1.8% / -0.2% / +0.3% | -0.58% | +1.05% | -1.12% +/- 1.04% | -1.20% | -1.68% |

Number of coins labelled trending at a date against the next-11-day average P&L across coins (23 dates): correlation +0.10 with trend P&L, -0.00 with MR P&L (s.e. about 0.21).

**loose rule**, label now against label 14 days later (18 non-overlapping dates x 50 coins):

| now \ 14 days later | up | choppy | down | coin-dates |
|---|---|---|---|---|
| trending-up | 6% | 91% | 3% | 34 |
| choppy | 4% | 81% | 15% | 729 |
| trending-down | 2% | 83% | 15% | 137 |
| all | 3.8% | 82.1% | 14.1% | 900 |

| label today | dates with any | coin-dates | next-11d trend net (+/- s.e.) | by thirds | long leg | short leg | next-11d MR net | next-11d MR-short net | next-11d coin return |
|---|---|---|---|---|---|---|---|---|---|
| up | 14 | 52 | -0.88% +/- 4.75% | -3.8% / +3.4% / -2.2% | +1.43% | -1.35% | -0.96% +/- 1.47% | -2.33% | +3.02% |
| chop | 23 | 902 | -0.24% +/- 2.20% | -1.1% / -0.6% / +1.2% | -0.43% | +1.27% | -1.25% +/- 1.10% | -1.23% | -1.77% |
| down | 16 | 196 | -0.74% +/- 2.57% | -7.6% / +2.2% / -0.7% | -1.31% | +1.64% | -0.54% +/- 1.33% | -0.49% | -3.01% |
| all | 23 | 1150 | -0.62% +/- 2.15% | -1.8% / -0.2% / +0.3% | -0.58% | +1.05% | -1.12% +/- 1.04% | -1.20% | -1.68% |

Number of coins labelled trending at a date against the next-11-day average P&L across coins (23 dates): correlation +0.21 with trend P&L, -0.08 with MR P&L (s.e. about 0.21).

A trending label is gone two weeks later about nine times in ten, whatever the label was. A coin labelled choppy does not make more on mean reversion in the next 11 days than a coin labelled trending, and a coin labelled trending does not make more on trend following; no difference between the rows exceeds its standard error. The direction of the label carries a little (labelled-up coins rose, labelled-down coins fell over the next 11 days) but on 32 and 127 coin-dates this is not established either. (Each row is the average over dates of that label's mean on the date, so the three label rows need not bracket the `all` row: dates with many trending coins weigh the same as dates with one.)

### 3.5 Market level: does the average character of the last 7 / 14 / 30 days carry into the next 11?

Time-series correlation across the 23 dates between the cross-sectional mean of the trailing measure and the cross-sectional mean of the next-11-day outcome (s.e. about 0.21, so nothing below 0.42 is distinguishable from zero).

| trailing measure -> next 11 days | 7d lookback r (Spearman) | 14d | 30d |
|---|---|---|---|
| absmove->trend_net | +0.12 (+0.09) | +0.21 (+0.11) | -0.37 (-0.37) |
| er72->trend_net | -0.03 (-0.10) | -0.13 (-0.18) | -0.09 (-0.19) |
| mr_net->mr_net | -0.15 (-0.30) | -0.03 (-0.05) | -0.20 (-0.19) |
| mr_net->trend_net | -0.08 (-0.04) | -0.05 (+0.09) | +0.20 (+0.17) |
| net_ret->mr_net | -0.20 (-0.24) | -0.02 (+0.00) | -0.22 (-0.22) |
| net_ret->trend_net | -0.13 (-0.12) | -0.03 (-0.02) | +0.15 (+0.20) |
| rvol_d->trend_net | -0.16 (-0.14) | -0.10 (-0.14) | -0.19 (-0.33) |
| trend_net->mr_net | -0.18 (-0.32) | -0.20 (-0.39) | -0.16 (-0.37) |
| trend_net->trend_net | -0.19 (-0.19) | -0.22 (-0.18) | -0.27 (-0.25) |
| vr24->mr_net | +0.34 (+0.38) | +0.10 (+0.22) | -0.04 (+0.28) |
| vr24->trend_net | +0.27 (+0.28) | -0.24 (-0.32) | +0.12 (+0.17) |
| x24_100->trend_net | +0.22 (+0.20) | +0.11 (+0.13) | +0.31 (+0.36) |

The market's own recent trend P&L is *negatively* related to its next-11-day trend P&L at every lookback (-0.19, -0.22, -0.27), and recent MR P&L has no positive relation to next MR P&L (-0.15, -0.03, -0.20). None is significant with 23 dates, but there is no sign at all of the positive persistence a "the market is choppy now, so run mean reversion" switch needs. This matters for today's reading: two good weeks for dip-buying say nothing reliable about the next 11 days.

What the two descriptive rules made per coin per 11-day window over the whole design period (23 windows x 50 coins):

| rule | mean +/- s.e. | coin-windows > 0 | dates with a positive average | by thirds |
|---|---|---|---|---|
| trend, before costs | +0.47% +/- 2.10% | 53% | 52% | -0.69% / +0.88% / +1.32% |
| trend, after 26 bp | -0.62% +/- 2.15% | 49% | 43% | -1.84% / -0.19% / +0.29% |
| trend long leg (gross) | -0.58% +/- 1.66% | 32% | 26% | +1.82% / -2.31% / -1.35% |
| trend short leg (gross) | +1.05% +/- 1.45% | 50% | 52% | -2.51% / +3.19% / +2.67% |
| MR long, before costs | -0.41% +/- 1.04% | 54% | 57% | +1.20% / -1.07% / -1.49% |
| MR long, after 26 bp | -1.12% +/- 1.04% | 50% | 52% | +0.55% / -1.84% / -2.21% |
| MR short, after 26 bp | -1.20% +/- 1.06% | 56% | 57% | -2.58% / -0.14% / -0.84% |
| holding the coin | -1.68% +/- 2.33% | 40% | 35% | +4.32% / -5.58% / -4.09% |

Average per coin per 11 days: 3.2 EMA 24/100 crossovers (4.2 positions), 2.7 dip-buy trades. Neither rule has a positive expectation after costs on the average coin; the trend rule's gross profit came from the short leg in a market that fell 45%.

### 3.6 In the real harness: does a coin filter built from character help? (design, default costs, start 744, 4 slots)

`EmaCross(24, 100)` and `ZScoreMR(48, 2.0)` from `strategies.py` with limit entries, unchanged except for `allow_long` / `allow_short`. Filters (all causal, recomputed every bar): `lowx` / `highx` = trailing-30-day EMA 24/100 crossover count at or below / above the cross-sectional median; `hiER` / `loER` = trailing-30-day mean ER72 above / below the median; `lab_trend` = long only coins labelled trending-up and short only coins labelled trending-down (base rule); `lab_chop` = only coins labelled choppy. `T_long/none` and `MR_long/none` reproduce the README benchmarks (-39%, -50%).

| variant | total | max DD | 11d mean | 11d median | 11d >= +10% | 11d <= -10% | thirds | trades | win | turnover | fill | active days | stress total | stress 11d mean | long P&L | short P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T_long/none | -39.4% | 58% | -1.47% | -2.81% | 15% | 18% | +4% / -32% / -14% | 743 | 28% | 327x | 88% | 93% | -74.0% | -4.59% | -39,664 | +0 |
| T_long/lowx | -50.3% | 62% | -2.55% | -3.08% | 6% | 15% | -10% / -30% / -22% | 491 | 28% | 193x | 89% | 77% | -70.9% | -4.51% | -51,087 | +0 |
| T_long/highx | +4.4% | 44% | +0.47% | -1.00% | 17% | 10% | +28% / -22% / +4% | 566 | 32% | 315x | 87% | 83% | -38.0% | -1.58% | +4,183 | +0 |
| T_long/hiER | -48.4% | 61% | -2.37% | -3.31% | 6% | 17% | -11% / -30% / -17% | 490 | 30% | 191x | 89% | 79% | -69.2% | -4.30% | -48,453 | +0 |
| T_long/loER | -0.1% | 38% | +0.25% | -0.91% | 11% | 7% | +35% / -19% / -8% | 563 | 31% | 327x | 87% | 83% | -47.0% | -2.15% | -500 | +0 |
| T_long/lab_trend | -1.3% | 7% | -0.05% | +0.00% | 0% | 0% | +2% / -3% / -1% | 19 | 26% | 9x | 95% | 7% | -2.6% | -0.11% | -1,334 | +0 |
| T_both/none | -9.6% | 55% | +0.27% | -0.53% | 19% | 17% | +24% / -15% / -14% | 1163 | 33% | 656x | 88% | 98% | -69.7% | -3.79% | -25,860 | +16,248 |
| T_both/lowx | -42.7% | 62% | -1.70% | -1.99% | 7% | 19% | -14% / -21% / -16% | 857 | 33% | 335x | 89% | 93% | -73.7% | -4.57% | -35,258 | -8,013 |
| T_both/highx | +8.7% | 51% | +1.04% | +0.13% | 20% | 12% | +39% / -24% / +3% | 963 | 34% | 541x | 88% | 93% | -57.2% | -2.59% | +7,394 | +507 |
| T_both/hiER | -46.8% | 67% | -2.01% | -2.01% | 9% | 23% | -12% / -27% / -17% | 885 | 33% | 351x | 89% | 93% | -76.8% | -5.08% | -44,590 | -1,966 |
| T_both/loER | +40.2% | 41% | +1.79% | +0.69% | 19% | 10% | +53% / -1% / -8% | 959 | 35% | 669x | 86% | 93% | -45.4% | -1.84% | +9,164 | +30,487 |
| T_both/lab_trend | -5.2% | 12% | -0.19% | -0.46% | 0% | 0% | +5% / -4% / -6% | 79 | 25% | 39x | 95% | 27% | -10.8% | -0.43% | -1,292 | -3,936 |
| MR_long/none | -50.4% | 56% | -2.27% | -1.49% | 6% | 16% | -7% / -7% / -42% | 920 | 57% | 387x | 89% | 97% | -85.8% | -6.91% | -50,929 | +0 |
| MR_long/lowx | -45.2% | 54% | -2.26% | -2.19% | 5% | 12% | -2% / -18% / -32% | 801 | 57% | 343x | 90% | 94% | -80.1% | -6.08% | -45,773 | +0 |
| MR_long/highx | -67.3% | 70% | -3.96% | -2.28% | 1% | 19% | -15% / -33% / -43% | 732 | 56% | 247x | 90% | 89% | -85.5% | -6.97% | -67,288 | +0 |
| MR_long/hiER | -19.1% | 41% | -0.37% | +0.61% | 4% | 6% | -1% / +17% / -30% | 775 | 59% | 396x | 91% | 92% | -75.6% | -4.96% | -19,930 | +0 |
| MR_long/loER | -77.8% | 80% | -5.47% | -4.68% | 0% | 24% | -29% / -41% / -47% | 780 | 53% | 219x | 90% | 89% | -90.9% | -8.65% | -77,805 | +0 |
| MR_long/lab_chop | -54.3% | 61% | -2.54% | -1.92% | 6% | 17% | -4% / -15% / -44% | 870 | 57% | 364x | 91% | 95% | -86.3% | -6.97% | -54,745 | +0 |
| MR_both/none | -90.6% | 93% | -7.87% | -5.09% | 5% | 38% | -64% / -63% / -30% | 1538 | 50% | 234x | 90% | 100% | -98.3% | -13.79% | -12,028 | -78,569 |
| MR_both/lowx | -85.9% | 89% | -6.81% | -6.92% | 4% | 35% | -55% / -57% / -26% | 1448 | 52% | 257x | 90% | 99% | -97.7% | -13.15% | -13,617 | -72,279 |
| MR_both/highx | -91.3% | 92% | -8.48% | -7.37% | 2% | 43% | -50% / -65% / -50% | 1388 | 52% | 242x | 91% | 98% | -97.6% | -12.98% | -21,800 | -69,448 |
| MR_both/hiER | -80.6% | 82% | -5.67% | -5.50% | 3% | 32% | -53% / -37% / -35% | 1416 | 53% | 290x | 91% | 98% | -93.8% | -9.82% | -11,274 | -69,620 |
| MR_both/loER | -92.1% | 93% | -8.75% | -8.55% | 4% | 47% | -46% / -76% / -40% | 1417 | 51% | 238x | 90% | 98% | -98.6% | -14.74% | -28,396 | -63,636 |
| MR_both/lab_chop | -95.1% | 96% | -10.02% | -8.31% | 4% | 45% | -67% / -76% / -39% | 1536 | 49% | 203x | 90% | 100% | -98.5% | -14.21% | -13,760 | -81,356 |

- Trend following on the coins that have been trending (`lowx`, `hiER`) is worse than no filter in all four comparisons. Trading only coins that carry a trending label almost never trades (19 and 79 trades in 282 days, 7% and 27% of days active) and still loses.
- Mean reversion on the coins that have been choppy (`highx`, `loER`, `lab_chop`) is worse than no filter in all six comparisons. Shorting z >= +2 is ruinous with or without a filter: it loses $64,000-$81,000 of the $100,000 on the short side.
- The reversed filters (trend-follow the recently choppy, mean-revert the recently trending) are less bad. That agrees in sign with section 3.1. The next table asks whether it is a plateau.

### 3.7 Plateau check of the reversed filter (lookback 7 / 14 / 30 / 60 days, share of coins kept)

Name = strategy / filter / lookback / share of coins kept (rank-based, so `keep0.5` is exactly the lower or upper half).

| variant | total | max DD | 11d mean | 11d median | 11d >= +10% | 11d <= -10% | thirds | trades | win | turnover | fill | active days | stress total | stress 11d mean | long P&L | short P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T_both/loER/7d/keep0.5 | -8.7% | 51% | +0.21% | -0.37% | 18% | 15% | +1% / -2% / -8% | 1018 | 35% | 509x | 89% | 95% | -68.1% | -3.78% | +3,358 | -12,747 |
| T_both/loER/14d/keep0.5 | +51.2% | 38% | +2.23% | +0.71% | 23% | 10% | +27% / +14% / +4% | 979 | 34% | 643x | 88% | 96% | -42.8% | -1.50% | +22,261 | +29,034 |
| T_both/loER/30d/keep0.5 | +40.2% | 41% | +1.79% | +0.69% | 19% | 10% | +53% / -1% / -8% | 959 | 35% | 669x | 86% | 93% | -45.4% | -1.84% | +9,164 | +30,487 |
| T_both/loER/60d/keep0.5 | -49.0% | 55% | -2.29% | -1.90% | 5% | 14% | -11% / -21% / -28% | 879 | 33% | 323x | 89% | 82% | -77.5% | -5.41% | -34,584 | -14,672 |
| T_both/highx/7d/keep0.5 | +8.8% | 49% | +1.05% | +0.77% | 21% | 14% | +30% / -7% / -10% | 1097 | 34% | 668x | 89% | 97% | -64.0% | -3.11% | -24,902 | +34,037 |
| T_both/highx/14d/keep0.5 | +52.7% | 42% | +2.40% | +0.77% | 25% | 10% | +38% / +6% / +4% | 1041 | 35% | 712x | 87% | 96% | -45.2% | -1.59% | +9,516 | +42,427 |
| T_both/highx/30d/keep0.5 | +10.1% | 50% | +1.16% | +1.23% | 21% | 16% | +27% / -14% / +2% | 1002 | 34% | 561x | 87% | 93% | -57.5% | -2.53% | -3,454 | +12,764 |
| T_both/highx/60d/keep0.5 | -25.0% | 53% | -0.60% | -0.05% | 12% | 15% | +6% / -33% / +6% | 884 | 34% | 370x | 89% | 82% | -69.4% | -4.02% | -8,947 | -16,500 |
| T_long/loER/7d/keep0.5 | -10.4% | 45% | -0.09% | -1.88% | 16% | 8% | +6% / -17% / +2% | 602 | 31% | 294x | 88% | 88% | -53.7% | -2.53% | -10,895 | +0 |
| T_long/loER/14d/keep0.5 | +21.3% | 31% | +1.16% | -0.29% | 14% | 4% | +17% / -5% / +9% | 567 | 31% | 319x | 88% | 83% | -33.3% | -1.08% | +20,839 | +0 |
| T_long/loER/30d/keep0.5 | -0.1% | 38% | +0.25% | -0.91% | 11% | 7% | +35% / -19% / -8% | 563 | 31% | 327x | 87% | 83% | -47.0% | -2.15% | -500 | +0 |
| T_long/loER/60d/keep0.5 | -39.4% | 49% | -1.81% | -1.44% | 4% | 8% | -4% / -28% / -13% | 515 | 30% | 211x | 89% | 75% | -63.4% | -3.75% | -39,697 | +0 |
| T_long/highx/7d/keep0.5 | -24.3% | 52% | -0.62% | -1.50% | 15% | 14% | +4% / -25% / -3% | 672 | 29% | 311x | 89% | 91% | -63.9% | -3.36% | -24,702 | +0 |
| T_long/highx/14d/keep0.5 | -16.9% | 48% | -0.23% | -1.54% | 17% | 12% | +11% / -23% / -3% | 634 | 30% | 313x | 89% | 88% | -57.3% | -2.74% | -17,494 | +0 |
| T_long/highx/30d/keep0.5 | -9.3% | 48% | -0.06% | -1.48% | 17% | 11% | +18% / -25% / +3% | 589 | 31% | 298x | 86% | 84% | -49.3% | -2.31% | -9,467 | +0 |
| T_long/highx/60d/keep0.5 | -15.4% | 52% | -0.31% | -0.88% | 12% | 9% | +11% / -35% / +17% | 526 | 31% | 238x | 89% | 75% | -51.1% | -2.42% | -15,843 | +0 |
| T_short/loER/7d/keep0.5 | -21.7% | 32% | -0.76% | -0.51% | 1% | 6% | -4% / +4% / -22% | 564 | 35% | 262x | n/a | 85% | -52.5% | -2.67% | +0 | -22,209 |
| T_short/loER/14d/keep0.5 | +17.3% | 21% | +0.78% | +1.13% | 7% | 4% | +7% / +16% / -6% | 534 | 38% | 289x | n/a | 83% | -24.4% | -0.93% | +0 | +16,601 |
| T_short/loER/30d/keep0.5 | +21.3% | 27% | +0.97% | +0.35% | 10% | 2% | +17% / +16% / -11% | 520 | 38% | 302x | n/a | 82% | -20.9% | -0.70% | +0 | +21,137 |
| T_short/loER/60d/keep0.5 | -23.1% | 28% | -0.89% | -0.96% | 2% | 3% | -6% / +3% / -21% | 482 | 35% | 210x | n/a | 72% | -49.7% | -2.54% | +0 | -23,224 |
| T_short/highx/7d/keep0.5 | +47.8% | 25% | +1.73% | +1.47% | 15% | 4% | +28% / +28% / -10% | 605 | 38% | 402x | n/a | 88% | -8.9% | -0.17% | +0 | +46,883 |
| T_short/highx/14d/keep0.5 | +32.5% | 23% | +1.25% | +0.31% | 12% | 2% | +15% / +26% / -9% | 585 | 37% | 353x | n/a | 86% | -15.8% | -0.53% | +0 | +31,638 |
| T_short/highx/30d/keep0.5 | +20.2% | 26% | +1.18% | -0.31% | 12% | 3% | +10% / +22% / -11% | 566 | 36% | 319x | n/a | 83% | -24.2% | -0.63% | +0 | +19,462 |
| T_short/highx/60d/keep0.5 | -14.0% | 26% | -0.43% | -0.13% | 1% | 1% | +0% / -3% / -12% | 498 | 37% | 228x | n/a | 73% | -44.3% | -2.14% | +0 | -14,485 |
| T_both/loER/30d/keep0.25 | +44.2% | 32% | +1.90% | +1.59% | 17% | 9% | +37% / -0% / +6% | 746 | 36% | 474x | 88% | 92% | -35.3% | -1.20% | +8,603 | +34,976 |
| T_both/loER/30d/keep0.33 | +15.3% | 35% | +1.07% | +0.61% | 14% | 9% | +20% / +5% / -8% | 843 | 36% | 469x | 87% | 92% | -50.6% | -2.16% | -7,687 | +22,776 |
| T_both/loER/30d/keep0.67 | +14.0% | 43% | +0.95% | -0.58% | 19% | 13% | +38% / -9% / -10% | 1027 | 35% | 645x | 87% | 94% | -58.5% | -2.95% | -19,491 | +33,071 |
| T_long/loER/30d/keep0.25 | +4.8% | 33% | +0.43% | +0.03% | 6% | 6% | +30% / -16% / -4% | 423 | 32% | 239x | 88% | 77% | -34.3% | -1.36% | +4,342 | +0 |
| T_long/loER/30d/keep0.33 | -12.6% | 40% | -0.23% | -0.26% | 6% | 6% | +18% / -19% / -9% | 485 | 32% | 245x | 88% | 80% | -47.6% | -2.17% | -12,982 | +0 |
| T_long/loER/30d/keep0.67 | -24.8% | 49% | -0.87% | -1.84% | 11% | 12% | +18% / -22% / -18% | 618 | 30% | 317x | 87% | 85% | -61.5% | -3.42% | -25,129 | +0 |
| MR_long/hiER/7d/keep0.5 | -49.9% | 52% | -2.26% | -1.22% | 1% | 14% | -16% / -5% / -37% | 777 | 57% | 297x | 91% | 92% | -80.4% | -5.76% | -50,406 | +0 |
| MR_long/hiER/14d/keep0.5 | -37.6% | 43% | -1.34% | +0.30% | 3% | 12% | -5% / -4% / -31% | 777 | 59% | 342x | 91% | 93% | -77.9% | -5.27% | -38,312 | +0 |
| MR_long/hiER/30d/keep0.5 | -19.1% | 41% | -0.37% | +0.61% | 4% | 6% | -1% / +17% / -30% | 775 | 59% | 396x | 91% | 92% | -75.6% | -4.96% | -19,930 | +0 |
| MR_long/hiER/60d/keep0.5 | -26.9% | 45% | -0.96% | +0.00% | 4% | 5% | +11% / -6% / -30% | 689 | 59% | 354x | 88% | 83% | -72.2% | -4.68% | -27,625 | +0 |
| MR_long/hiER/30d/keep0.25 | -42.6% | 45% | -1.84% | -0.46% | 1% | 12% | -10% / -18% / -22% | 695 | 57% | 275x | 91% | 88% | -80.5% | -5.85% | -43,210 | +0 |
| MR_long/hiER/30d/keep0.33 | -28.6% | 37% | -0.92% | +0.03% | 4% | 11% | -5% / +4% / -28% | 741 | 58% | 340x | 92% | 88% | -78.7% | -5.46% | -29,411 | +0 |
| MR_long/hiER/30d/keep0.67 | -33.9% | 46% | -1.12% | +0.20% | 4% | 11% | -8% / +17% / -38% | 812 | 59% | 381x | 89% | 94% | -72.8% | -4.49% | -34,628 | +0 |

- `T_both`: -9% / +51% / +40% / -49% for `loER` at 7 / 14 / 30 / 60 days and +9% / +53% / +10% / -25% for `highx`. The sign changes with the lookback. Kept share at 30 days: +44% / +15% / +40% / +14% for 25% / 33% / 50% / 67%.
- The short side alone (`T_short`) is positive in 5 of 8 rows and negative in the last third in all 8 (-6% to -22%): it is the bear market, visible in the thirds.
- `MR_long` with the reversed filter still loses 19-50% at every lookback and share.
- **Every one of the 37 rows is negative under stress costs** (-9% to -80%). Turnover is 200-700 times the account in 282 days; at the stress rates that is the whole result.

### 3.8 The pre-committed midpoint (candidate_1) and its robustness

To avoid choosing the top row, I fixed the lookback at 21 days (the midpoint of the two that looked good, not run before) and filed whatever came out.

| variant | total | max DD | 11d mean | 11d median | 11d >= +10% | 11d <= -10% | thirds | trades | win | turnover | fill | active days | stress total | stress 11d mean | long P&L | short P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| candidate_1 = T_both / loER / 21d / keep 0.5 | +0.7% | 47% | +0.34% | -0.24% | 17% | 14% | +31% / -19% / -6% | 965 | 34% | 539x | 88% | 94% | -63.0% | -3.48% | -18,310 | +18,917 |
| no coarse-tick pairs | +19.8% | 37% | +0.92% | -0.19% | 10% | 8% | +39% / +7% / -19% | 876 | 35% | 563x | 89% | 92% | -44.1% | -2.01% | +10,011 | +10,035 |
| market entries | +14.9% | 45% | +0.92% | +0.21% | 17% | 13% | +33% / -11% / -4% | 977 | 36% | 576x | n/a | 94% | -49.9% | -2.28% | -8,445 | +23,425 |
| T_long loER 21d | -13.7% | 44% | -0.28% | -0.86% | 10% | 10% | +21% / -23% / -8% | 570 | 30% | 294x | 88% | 85% | -53.7% | -2.65% | -13,809 | +0 |
| T_short loER 21d | +2.9% | 31% | +0.20% | +0.21% | 6% | 5% | +12% / -1% / -7% | 524 | 37% | 273x | n/a | 82% | -35.2% | -1.62% | +0 | +2,751 |
| T_both hiER 21d (intuitive direction) | -48.2% | 67% | -2.16% | -2.94% | 9% | 17% | -9% / -27% / -21% | 892 | 33% | 356x | 87% | 94% | -76.7% | -5.12% | -41,267 | -6,656 |
| T_both loER 21d 8 slots | +0.6% | 41% | +0.30% | +0.23% | 8% | 10% | +26% / -20% / +0% | 1465 | 34% | 394x | 89% | 96% | -53.5% | -2.65% | -6,518 | +7,033 |

- candidate_1: **+0.7% total, 47% max drawdown, thirds +31% / -19% / -6%, stress -63.0%**. The +40% and +51% of its two neighbours were not a plateau. Look-ahead check: passed (True).
- Sharpe 0.28, Sortino 0.44, Calmar 0.02; 965 trades, win rate 34%, fees $47,654 on $100,000, turnover 539x, limit fill rate 88%, 94% of days with a fill. 11-day windows: mean +0.34%, median -0.24%, 49% positive, 17% at or above +10%, 14% at or below -10%, worst -24.8%. Restarted flat every 4 days (68 fresh 11-day windows): mean +0.40%, median -1.16%, 47% positive.
- By exit: stop 874 trades +54,847, signal 91 trades -54,240. By side: long -18,310 (504), short +18,917 (461).
- By coin: 27 of 50 coins positive; best PEPE +18,147, TAO +17,310, NEAR +9,844, ZEN +8,922; worst CFX -10,270, PENDLE -12,062, LISTA -18,948, STO -22,289. The total (+607) is smaller than any one of these: the result is the difference of large offsetting numbers.
- The comparison that *is* stable: the intuitive direction (`hiER`, trade the coins that have been trending) at the same 21 days returns -48.2%, as it did at 30 days (-47%).

## 4. What failed, and how many things were tried

- Harness: **68 backtested variants** (24 in 3.6, 37 in 3.7, 7 in 3.8; 65 distinct, three appear twice). None beats cash after stress costs; the least negative are the label filter that barely trades (-2.6%, 19 trades) and `T_short/highx/7d` (-8.9%, last third -10% at default costs). None is positive in all three thirds at default costs except `T_both/loER/14d` and `T_both/highx/14d`, and their neighbours are not: `loER` returns -9% at 7 days, +0.7% at 21 and -49% at 60. Against the goal, `baselines.Breakout` (+40%, +4% under stress): nothing here is close under stress.
- Statistics: 21 measures x 3 targets x 4 lookbacks of rank correlations (252 cells, plus two shifted date grids), 19 top-minus-bottom spreads, 36 market-level correlations, two labelling rules. Outside volatility, the handful of cells beyond two standard errors is what that many tests produce by chance, with one family that is consistent in sign (recent trendiness slightly *hurts* next-period trend P&L).
- The intuitive plan "find the coins that are trending and trend-follow them; find the choppy ones and mean-revert them" failed in the statistics (3.1-3.4) and in the harness (3.6), on every measure tried.

## 5. Recommendation

1. **Do not choose coins, or switch between the two strategies, on trailing trend/chop character.** It does not persist over an 11-day horizon in this universe. If a universe filter is wanted, use things that do persist: volatility for position size and stop distance, and spread/tick size for limit orders (the six coarse-tick coins cost candidate_1 about 19 points: +0.7% with them, +19.8% without).
2. **If a character filter is used anyway, do not point it the intuitive way.** Restricting trend following to recently-trending coins or mean reversion to recently-choppy coins was worse than no filter in 10 of 10 comparisons.
3. **Read today's census as weather, not forecast.** Right now: 0 of 50 trending, about 45 of 50 would have paid a dip-buyer over the last two weeks, and the EMA rule was whipsawed on 43 of 50. In the design data the same reading had no positive relation to the following 11 days (market-level correlation -0.03 to -0.20 for MR, -0.19 to -0.27 for trend).
4. **Plateau:** there is none to recommend. The least-bad region is "EMA 24/100 both sides on the half of coins with the lowest trailing 14-30 day efficiency ratio" (+40% to +51% at default costs, -43% to -45% under stress, +0.7% at the 21-day midpoint). It is filed as `candidate_1.py`, labelled not recommended, so the integrators can confirm on later data.

**What would have to be true for coin selection by character to work:** (a) character would have to persist, i.e. a rank correlation of trailing with forward trend or MR P&L of roughly +0.1 or more that holds in each third; the data show -0.06 and -0.01; and (b) costs would have to be near the default model, since at 200-700x turnover every variant is negative at stress costs.

## 6. Caveats

- An 11-day realised P&L is a noisy measure of a coin's character, so a correlation near zero means "not predictable at the horizon the team has", not "coins have no traits at all" (ER24 over 90 days does show a small trait).
- 23 forward windows from one 10-month bear market. Standard errors treat dates as independent; trailing windows overlap, forward windows do not.
- The trend and MR P&L measures are simple descriptive rules (always-in EMA 24/100; z48 dip-buy with no stop), traded at the signal close with a flat 26 bp. They are not the harness strategies; sections 3.6-3.8 use the harness.
- The census on `full` looked at the selection and holdout periods only to describe them. No parameter, threshold or candidate was chosen on them: thresholds were fixed from random-walk reasoning, and every test in section 3 used `design`.
- Cross-sectional counts overstate the evidence: the 50 coins are highly correlated, so "45 of 50" is closer to one observation about the market than to 45.

