# Track `shorts_direction`: should the market's direction decide whether we go long or short?

All numbers: `harness.load('design')` only, rows 744 to 7,519 (282 days, 50 pairs), default costs unless "stress" is written
(`evalkit.STRESS`). In this period the equal-weight basket fell 45% and BTC 32%. By third: basket +15% / -28% / -35%, BTC +5% / -17% / -23%.
Only the first third was a rising market, so "thirds" is the main guard against results that are just "short in a bear market".

## 1. Verdict

**Weak edge for the direction signal as a risk switch on longs. No edge for the short side: shorts do not earn their fees.**

1. **No direction signal predicts the market.** For 9 signals and 3 horizons (24 h, 72 h, 7 d) the t-statistic of
   "basket return after a good label minus after a bad label" lies between -1.4 and +0.1; 24 of 27 are negative. The labels
   describe what already happened. The 2-state HMM was no better (after its "good" state the basket did worse in all three
   thirds at all three horizons), and it disagrees with the trend signals on about 60% of hours.
2. **The team's rule "long in good markets, short in bad ones" is not supported.** Where shorts made money (EMA-cross shorts),
   shorting only in *good* markets (the signal reversed) earned more than shorting only in bad markets in 7 of 12 like-for-like
   comparisons, and shorting always earned more in 12 of 12 (mean short P&L: bad-only $22k, good-only $29k, always $57k).
   The signal is not what made them pay. The falling market was.
3. **Does adding shorts beat "long in good markets, cash in bad ones"?** At default costs, with EMA-cross shorts: yes on this
   sample. Candidate 3 against candidate 1: 11-day mean +4.00% against +3.57%, median +2.38% against +0.31%, Sortino 4.36 / 4.23,
   Sharpe 2.19 / 2.04, Calmar 8.95 / 8.29. At stress costs: no. 11-day mean +2.90% against +2.85%, Sortino 2.93 / 3.16, Sharpe
   1.55 / 1.60, Calmar 3.92 / 5.02, drawdown 27% against 21%; the short leg's profit shrinks from $24k to $4k. All of the short
   profit came from the middle third (-$2k / +$27k / -$1k), and with one short slot instead of two the same leg lost $5k.
   With mirrored breakdown shorts the ratios fall (Sortino lower for 7 of 9 signals, stress return lower for 9 of 9). With
   z-score shorts everything gets much worse (0 of 9).
4. **Shorts when the basket was rising:** every one of the 40 EMA-cross short settings lost money in the 11-day blocks in which
   the basket rose (-1% to -7% per block), and all 16 breakdown-short settings did too. The short side is a bet on the market
   falling (beta -0.4 to -0.5), with an estimated extra return of +0.2% per 11 days at the median setting (-1.5% at stress costs).
5. **What does hold up:** a slow trend filter on BTC (close above its 300 to 960 hour EMA) as an entry gate for the breakout
   longs. All 16 EMA gates of 150 h or slower beat the ungated benchmark at default and stress costs and cut the drawdown
   (43% to 18-32%). But about 70% of the gated profit is two coins (STO, TUT). Without them the gate still helps
   (+30% against +19%, stress +12% against -8%), yet the per-trade advantage of good-market entries disappears (t = 0.0).
   What is left is "trade less when the market is falling", which is a risk rule, not a forecast.
6. **The standing BTC hedge** improved every ratio here only because BTC fell 32%. With BTC's drift removed, the hedged book
   is the same as the unhedged book at the same reduced size (Sortino 4.10 against 4.27, Sharpe 2.08 against 2.05).

Recommendation: use the direction signal to decide **whether to take new longs**, not to switch to shorts (candidate 1). If the
team must trade on at least 8 of every 14 days, candidate 1 alone will not do that (41% of 14-day windows qualified); candidate 3
adds the least-bad short leg for activity (86% of windows) at roughly zero expected profit after stress costs.

## 2. Method

- **Signals** (all causal, row t uses rows <= t; +1 good, -1 bad): BTC close above its EMA(100 / 200 / 480 h); the equal-weight
  basket (hourly rebalanced) above its EMA(100 / 200 / 480 h); breadth = share of coins above their own 200 h EMA with hysteresis
  (good above 55%, bad below 45%); sign of BTC's 7-day return; a 2-state K-Means-initialised HMM (`regime.walk_forward`, X of
  shape (T,1,2): basket 24 h log return and log 72 h realised volatility, first fit after 672 h, refit every 168 h, "good" = the
  state with the higher mean return in the training data).
- **Prediction test:** basket return over the next 24 / 72 / 168 h sampled without overlap, Welch t of good minus bad, repeated
  for 8 start offsets (median reported), overall and by thirds.
- **Strategies:** (A) `strategies.EmaCross`, three parameter sets (24/100 stop 3 ATR, 24/200 stop 6, 48/200 stop 5); (B)
  `strategies.ZScoreMR`, three sets (48 h z 2.0, 72 h z 3.0, 24 h z 2.5); (C) `baselines.Breakout` plus its mirror, written for
  this track (`common.BreakoutLS`: short when the 24 h return <= -8% and the close is at the 72 h low, cover when an hourly close
  is 6% above the low since entry; verified to reproduce `baselines.Breakout` exactly when long-only, 449 trades). 4 equal slots,
  market entries, shorts at 10 bp each way and never above 1x.
- **Modes:** L / S / B = always long / short / both. Lg = long only in good markets (cash in bad). Sb = short only in bad
  markets. LgSb = the team's rule. Lb / Sg / LbSg = the same with the signal **reversed** (placebo), on one set per family.
- **Honesty checks:** thirds; long and short P&L apart; stress costs; short legs in non-overlapping 11-day and 30-day blocks
  split by whether the basket rose; daily regression of each leg on the basket (alpha per 11 days and beta); parameter grids
  around anything that looked good; removing the best coins; the look-ahead check on the three finalists (all pass).
- **Count:** 517 backtested variants (each at default and stress costs), plus 32 trade-level gate tests and 27 signal
  prediction tests. Nothing here was fitted on the selection or holdout data.
- Code: `common.py` (signals, mirror, hedge), `lib.py`, `s1_signals.py` ... `s7_verify.py`; raw rows in `s*_results.jsonl`.

## 3. Direction signals: how often they flip and whether they predict

| signal | good share | good share by third | flips per 14 d | median run | next 24h: after good / bad | next 72h | next 168h | t 24h (thirds) | t 72h (thirds) | t 168h (thirds) |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC > EMA100 | 45% | 51% / 44% / 41% | 18.6 | 4 h | -0.23% / -0.10% | -0.79% / -0.32% | -1.16% / -1.33% | -0.29 (-0.5 +0.1 -0.6) | -0.35 (-0.1 +0.2 -0.7) | +0.07 (+0.1 -0.3 +0.3) |
| BTC > EMA200 | 45% | 54% / 45% / 35% | 14.3 | 4 h | -0.33% / -0.03% | -0.54% / -0.49% | -1.92% / -0.60% | -0.68 (-0.3 -0.8 -0.6) | -0.01 (-0.1 -0.3 -0.2) | -0.41 (-0.1 -0.6 -0.1) |
| BTC > EMA480 | 40% | 59% / 31% / 29% | 6.9 | 5 h | -0.22% / -0.13% | -0.65% / -0.48% | -1.72% / -0.86% | -0.21 (-0.3 -0.7 -0.4) | -0.15 (-0.5 -0.5 -0.1) | -0.28 (-0.1 -1.3 +0.2) |
| basket > EMA100 | 43% | 51% / 44% / 35% | 19.3 | 3 h | -0.33% / -0.04% | -1.07% / -0.10% | -1.94% / -0.57% | -0.64 (-0.8 -0.4 -0.4) | -0.70 (-0.4 -1.1 -0.6) | -0.50 (-0.3 -0.4 +0.1) |
| basket > EMA200 | 40% | 47% / 39% / 33% | 13.0 | 4 h | -0.44% / +0.02% | -1.18% / -0.09% | -3.78% / +0.50% | -0.96 (-0.6 -0.9 -0.4) | -0.82 (-0.3 -1.6 +0.1) | -1.36 (-0.2 -1.1 +0.2) |
| basket > EMA480 | 33% | 47% / 31% / 22% | 5.7 | 5 h | -0.30% / -0.08% | -0.97% / -0.26% | -2.89% / -0.27% | -0.41 (-0.6 -0.8 +0.2) | -0.49 (-0.4 -0.8 -0.1) | -0.76 (-0.1 -1.5 -0.1) |
| breadth 55/45 | 33% | 40% / 29% / 28% | 6.6 | 18 h | -0.31% / -0.08% | -0.92% / -0.28% | -2.64% / -0.54% | -0.48 (-0.4 -0.1 -0.9) | -0.48 (-0.3 -0.3 -0.3) | -0.67 (-0.1 -1.0 +1.0) |
| BTC 7d return > 0 | 46% | 52% / 44% / 43% | 13.4 | 3 h | -0.15% / -0.17% | -0.57% / -0.44% | -1.11% / -1.18% | +0.06 (+0.1 -0.3 -0.1) | -0.10 (+0.4 -0.1 +0.4) | +0.02 (+0.1 -0.5 -0.1) |
| 2-state HMM | 49% | 41% / 49% / 56% | 3.6 | 65 h | -0.48% / +0.13% | -0.84% / -0.20% | -2.01% / -0.35% | -1.34 (-0.9 -0.7 -0.5) | -0.49 (-0.2 -0.5 -0.1) | -0.61 (-0.6 -0.4 -0.3) |

Basket drift for scale: -0.15% per 24 h, -0.48% per 72 h, -1.14% per 168 h
(n = 282 / 94 / 40 non-overlapping samples).

Reading: a positive t would mean "good" is followed by better returns than "bad". None is. The fast signals (EMA100, EMA200,
7-day return) flip 13 to 19 times per 14 days with a median run of 3 to 4 hours, so a rule that switches book on each flip would
churn. EMA480 and breadth flip about 6 to 7 times, the HMM 3.6 times. The eight trend signals agree with each other on 70 to 92%
of hours; the HMM agrees with them on only 36 to 43% (it is close to their opposite).

## 4. Strategies under each direction rule

Each cell: total return / stress total / 11-day mean. "none" = the rule without any signal.

**(A) EMA cross, E24_100_s3**

| signal | long only (in good) | short only (in bad) | both (team rule) | thirds of "both" | long / short P&L of "both" |
|---|---|---|---|---|---|
| none (always) | -20% / -57% / -0.3% | +24% / -27% / +1.1% | +17% / -54% / +1.4% | +42% / -6% / -12% | -2k / +19k |
| BTC > EMA100 | -6% / -38% / +0.2% | +26% / -16% / +1.0% | +8% / -50% / +0.8% | +21% / -7% / -4% | -14k / +22k |
| BTC > EMA200 | -4% / -35% / +0.3% | +33% / -8% / +1.1% | +41% / -32% / +1.9% | +42% / +12% / -11% | +11k / +30k |
| BTC > EMA480 | +18% / -13% / +1.0% | +29% / -9% / +1.1% | +40% / -26% / +2.0% | +26% / +24% / -11% | +6k / +34k |
| basket > EMA100 | -22% / -49% / -0.5% | +41% / -7% / +1.6% | +33% / -39% / +2.0% | +22% / +33% / -18% | -5k / +38k |
| basket > EMA200 | +18% / -18% / +1.1% | +31% / -12% / +1.3% | +74% / -16% / +2.9% | +44% / +19% / +1% | +34k / +40k |
| basket > EMA480 | +14% / -13% / +1.0% | +32% / -11% / +1.2% | +45% / -25% / +2.0% | +20% / +39% / -14% | +11k / +33k |
| breadth 55/45 | +10% / -17% / +0.7% | +33% / -14% / +1.2% | +69% / -16% / +2.6% | +49% / +43% / -20% | +27k / +42k |
| BTC 7d return > 0 | +2% / -30% / +0.4% | +24% / -10% / +0.9% | +27% / -34% / +1.4% | +39% / +8% / -15% | -6k / +32k |
| 2-state HMM | -34% / -53% / -1.2% | -1% / -29% / +0.2% | -31% / -64% / -0.8% | -14% / -12% / -9% | -31k / -1k |

**(A) EMA cross, E24_200_s6**

| signal | long only (in good) | short only (in bad) | both (team rule) | thirds of "both" | long / short P&L of "both" |
|---|---|---|---|---|---|
| none (always) | +4% / -20% / +0.8% | +87% / +48% / +3.1% | +59% / +17% / +2.2% | +12% / +45% / -2% | +14k / +39k |
| BTC > EMA100 | -22% / -35% / -0.6% | +57% / +30% / +2.0% | +6% / -22% / +0.6% | +7% / -3% / +2% | -33k / +35k |
| BTC > EMA200 | -22% / -35% / -0.7% | +100% / +70% / +3.1% | +25% / -7% / +1.5% | +12% / +30% / -14% | -40k / +60k |
| BTC > EMA480 | -11% / -23% / -0.3% | +50% / +26% / +1.9% | +40% / +6% / +1.6% | -3% / +38% / +4% | -14k / +48k |
| basket > EMA100 | +32% / +9% / +1.8% | +112% / +77% / +3.3% | +117% / +61% / +3.7% | +2% / +78% / +20% | +32k / +77k |
| basket > EMA200 | -11% / -26% / +0.1% | +51% / +25% / +2.1% | +29% / -5% / +1.9% | -7% / +58% / -12% | -16k / +41k |
| basket > EMA480 | -15% / -26% / -0.3% | +27% / +7% / +1.4% | -1% / -26% / +0.3% | +10% / -2% / -9% | -25k / +22k |
| breadth 55/45 | -19% / -30% / -0.7% | +49% / +23% / +1.8% | +46% / +8% / +1.8% | +7% / +21% / +12% | -1k / +42k |
| BTC 7d return > 0 | -11% / -25% / -0.2% | +71% / +48% / +2.5% | +2% / -23% / +0.3% | +13% / +11% / -18% | -32k / +32k |
| 2-state HMM | -34% / -44% / -1.2% | -8% / -21% / +0.0% | -31% / -47% / -0.5% | -15% / +11% / -26% | -23k / -8k |

**(A) EMA cross, E48_200_s5**

| signal | long only (in good) | short only (in bad) | both (team rule) | thirds of "both" | long / short P&L of "both" |
|---|---|---|---|---|---|
| none (always) | +10% / -15% / +1.2% | +41% / +10% / +1.6% | +121% / +48% / +4.2% | -17% / +167% / -0% | +46k / +72k |
| BTC > EMA100 | -12% / -27% / -0.2% | +46% / +20% / +1.9% | +56% / +9% / +2.6% | -6% / +98% / -16% | +10k / +41k |
| BTC > EMA200 | -17% / -30% / -0.4% | +40% / +17% / +1.7% | +21% / -12% / +1.4% | +6% / +68% / -32% | -25k / +43k |
| BTC > EMA480 | +3% / -11% / +0.4% | +57% / +33% / +2.1% | +62% / +21% / +2.6% | -0% / +60% / +1% | +4k / +54k |
| basket > EMA100 | +18% / -5% / +1.3% | +51% / +23% / +2.1% | +94% / +33% / +3.6% | -16% / +149% / -8% | +42k / +51k |
| basket > EMA200 | +12% / -6% / +1.0% | +6% / -14% / +0.6% | +41% / -1% / +2.2% | -22% / +117% / -16% | +20k / +18k |
| basket > EMA480 | -24% / -34% / -0.5% | +27% / +6% / +1.2% | +22% / -11% / +1.4% | -20% / +41% / +7% | +1k / +18k |
| breadth 55/45 | -13% / -26% / -0.3% | +27% / +2% / +1.3% | +30% / -7% / +1.7% | -13% / +63% / -8% | -10k / +38k |
| BTC 7d return > 0 | +17% / -1% / +1.0% | +48% / +28% / +1.9% | +92% / +44% / +3.2% | +19% / +83% / -12% | +8k / +82k |
| 2-state HMM | -22% / -33% / -0.6% | -15% / -27% / -0.4% | -30% / -48% / -0.8% | -23% / +12% / -19% | -19k / -13k |

**(B) z-score mean reversion, Z48_2**

| signal | long only (in good) | short only (in bad) | both (team rule) | thirds of "both" | long / short P&L of "both" |
|---|---|---|---|---|---|
| none (always) | -55% / -84% / -2.7% | -90% / -97% / -7.1% | -92% / -98% / -8.5% | -70% / -62% / -34% | -16k / -76k |
| BTC > EMA100 | -39% / -60% / -1.8% | -70% / -83% / -3.9% | -84% / -93% / -6.1% | -53% / -51% / -29% | -17k / -66k |
| BTC > EMA200 | -46% / -63% / -2.2% | -41% / -65% / -1.4% | -67% / -85% / -3.4% | -42% / -34% / -15% | -26k / -41k |
| BTC > EMA480 | -30% / -52% / -1.2% | -47% / -70% / -1.6% | -66% / -86% / -3.1% | -32% / -43% / -12% | -18k / -49k |
| basket > EMA100 | -29% / -51% / -1.1% | -61% / -77% / -2.9% | -73% / -88% / -4.3% | -35% / -46% / -24% | -12k / -61k |
| basket > EMA200 | -28% / -50% / -1.2% | -62% / -78% / -3.0% | -72% / -88% / -4.0% | -32% / -49% / -18% | -13k / -59k |
| basket > EMA480 | -26% / -46% / -0.9% | -56% / -76% / -2.3% | -71% / -88% / -3.5% | -33% / -59% / +6% | -19k / -53k |
| breadth 55/45 | -26% / -45% / -1.0% | -75% / -87% / -4.5% | -82% / -93% / -5.6% | -40% / -62% / -22% | -7k / -75k |
| BTC 7d return > 0 | -31% / -55% / -1.3% | -36% / -63% / -1.0% | -53% / -82% / -2.1% | -35% / -18% / -12% | -12k / -41k |
| 2-state HMM | -62% / -79% / -3.5% | -84% / -91% / -6.1% | -93% / -98% / -8.9% | -59% / -70% / -43% | -19k / -74k |

**(B) z-score mean reversion, Z72_3**

| signal | long only (in good) | short only (in bad) | both (team rule) | thirds of "both" | long / short P&L of "both" |
|---|---|---|---|---|---|
| none (always) | -44% / -60% / -2.0% | -76% / -86% / -4.6% | -86% / -93% / -6.5% | -51% / -63% / -21% | -18k / -68k |
| BTC > EMA100 | +17% / +9% / +0.7% | -38% / -49% / -1.4% | -25% / -43% / -0.7% | +3% / -26% / -2% | +16k / -41k |
| BTC > EMA200 | +7% / -2% / +0.3% | -14% / -29% / -0.1% | -6% / -29% / +0.3% | +1% / -11% / +5% | +8k / -13k |
| BTC > EMA480 | -0% / -10% / +0.0% | -26% / -40% / -0.6% | -27% / -46% / -0.7% | +1% / -29% / +2% | -1k / -26k |
| basket > EMA100 | +12% / +6% / +0.5% | -19% / -30% / -0.5% | -9% / -26% / -0.0% | +8% / -12% / -5% | +11k / -20k |
| basket > EMA200 | +2% / -5% / +0.1% | -28% / -40% / -0.7% | -23% / -39% / -0.4% | -4% / -12% / -8% | +3k / -25k |
| basket > EMA480 | +2% / -6% / +0.2% | -41% / -53% / -1.4% | -40% / -56% / -1.3% | -15% / -31% / +3% | +2k / -42k |
| breadth 55/45 | +9% / +3% / +0.4% | -34% / -49% / -1.1% | -28% / -48% / -0.7% | +5% / -27% / -6% | +10k / -38k |
| BTC 7d return > 0 | +5% / -6% / +0.3% | -35% / -49% / -1.3% | -34% / -53% / -1.2% | -23% / +2% / -16% | +4k / -38k |
| 2-state HMM | -54% / -64% / -3.0% | -67% / -77% / -3.9% | -84% / -91% / -6.5% | -41% / -63% / -25% | -26k / -58k |

**(B) z-score mean reversion, Z24_2p5**

| signal | long only (in good) | short only (in bad) | both (team rule) | thirds of "both" | long / short P&L of "both" |
|---|---|---|---|---|---|
| none (always) | -58% / -84% / -3.3% | -85% / -95% / -6.3% | -94% / -99% / -9.7% | -76% / -51% / -45% | -33k / -61k |
| BTC > EMA100 | -24% / -48% / -1.1% | -63% / -79% / -3.5% | -73% / -89% / -4.7% | -35% / -43% / -26% | -13k / -59k |
| BTC > EMA200 | -36% / -59% / -1.8% | -55% / -74% / -2.6% | -71% / -90% / -4.4% | -36% / -36% / -30% | -23k / -48k |
| BTC > EMA480 | -38% / -57% / -1.9% | -55% / -76% / -2.4% | -72% / -90% / -4.3% | -35% / -42% / -26% | -27k / -45k |
| basket > EMA100 | -23% / -42% / -1.0% | -45% / -67% / -1.9% | -59% / -82% / -3.1% | -32% / -35% / -7% | -14k / -45k |
| basket > EMA200 | -31% / -51% / -1.5% | -59% / -77% / -2.8% | -72% / -88% / -4.2% | -42% / -33% / -28% | -19k / -53k |
| basket > EMA480 | -29% / -46% / -1.3% | -61% / -80% / -2.9% | -72% / -89% / -4.2% | -42% / -44% / -14% | -18k / -54k |
| breadth 55/45 | -28% / -44% / -1.3% | -70% / -85% / -4.0% | -80% / -92% / -5.4% | -43% / -49% / -31% | -14k / -66k |
| BTC 7d return > 0 | -20% / -48% / -1.0% | -47% / -70% / -2.1% | -55% / -83% / -2.8% | -20% / -30% / -19% | -10k / -44k |
| 2-state HMM | -53% / -73% / -2.9% | -74% / -87% / -4.9% | -88% / -96% / -7.7% | -62% / -54% / -29% | -21k / -67k |

**(C) breakout long + mirrored breakdown short, BK8_6**

| signal | long only (in good) | short only (in bad) | both (team rule) | thirds of "both" | long / short P&L of "both" |
|---|---|---|---|---|---|
| none (always) | +40% / +4% / +2.1% | -20% / -36% / -0.8% | +49% / -6% / +2.3% | -11% / +81% / -7% | +54k / -6k |
| BTC > EMA100 | -0% / -20% / +0.6% | -8% / -25% / -0.3% | -11% / -41% / +0.1% | -14% / +11% / -6% | -5k / -5k |
| BTC > EMA200 | +53% / +23% / +2.5% | +5% / -14% / +0.3% | +55% / +4% / +2.7% | -10% / +78% / -3% | +39k / +16k |
| BTC > EMA480 | +107% / +73% / +3.6% | +3% / -14% / +0.2% | +131% / +62% / +4.2% | +4% / +108% / +7% | +97k / +33k |
| basket > EMA100 | +60% / +24% / +2.7% | +1% / -18% / +0.2% | +79% / +15% / +3.3% | -11% / +114% / -7% | +62k / +17k |
| basket > EMA200 | +78% / +43% / +3.2% | +4% / -16% / +0.3% | +76% / +16% / +3.5% | -21% / +134% / -4% | +61k / +16k |
| basket > EMA480 | +52% / +27% / +2.4% | +19% / -1% / +0.7% | +66% / +15% / +2.9% | -21% / +99% / +5% | +32k / +36k |
| breadth 55/45 | +20% / +1% / +1.2% | -2% / -20% / +0.0% | +21% / -17% / +1.2% | -16% / +48% / -3% | +19k / +2k |
| BTC 7d return > 0 | +95% / +61% / +3.3% | -6% / -21% / -0.1% | +92% / +34% / +3.4% | +17% / +74% / -6% | +83k / +8k |
| 2-state HMM | -36% / -45% / -1.5% | -15% / -24% / -0.4% | -43% / -56% / -1.8% | -29% / -8% / -13% | -29k / -14k |

Reading:
- **EMA cross:** long-only loses or is flat with or without a gate (Lg totals -34% to +32%). Short-only made money in every
  trend-signal variant with a 6-ATR or 5-ATR stop, gated or not. "Both" beats "long only in good" because of that short P&L.
- **Z-score:** all 78 variants that include shorts lose (0 positive); of the 39 long-only rows 7 are positive, all of them the 72 h / z 3.0 set bought only in good markets (best +17%, stress +9%). Shorting spikes is the worst rule
  tested in this track (short-only-in-bad: -14% to -84%; always: -76% to -90%); a spike in a small coin tends to keep going.
  Gating by direction makes the shorts lose less, never win.
- **Breakout:** long-only is the only long rule with a positive total. The mirrored short loses alone (-20%) and adds almost
  nothing when gated (+2% on average over 8 trend signals, -16% at stress costs).

### 4.1 The paired comparison the team asked for: "both" minus "long in good, cash in bad"

Mean difference over the 9 signals (LgSb minus Lg, same family and parameters); in brackets, for how many of the 9 signals it rose.

| family_parameters | 11d mean | 11d median | Sortino | Sharpe | Calmar | max DD (up = worse) | total | stress total | stress 11d mean | first (rising) third |
|---|---|---|---|---|---|---|---|---|---|---|
| brk_BK8_6 | +0.15% (7/9) | +0.88% (7/9) | -0.28 (2/9) | -0.04 (3/9) | -0.89 (1/9) | +11.9% (9/9) | +4.0% (5/9) | -16.9% (0/9) | -0.55% (0/9) | -20.0% (0/9) |
| ema_E24_100_s3 | +1.31% (9/9) | +1.23% (8/9) | +1.26 (9/9) | +0.72 (9/9) | +1.37 (9/9) | +2.7% (6/9) | +34.6% (9/9) | -4.0% (4/9) | -0.06% (4/9) | +17.1% (9/9) |
| ema_E24_200_s6 | +1.47% (9/9) | +1.18% (8/9) | +1.44 (9/9) | +0.84 (9/9) | +1.93 (9/9) | -6.7% (2/9) | +38.5% (9/9) | +19.9% (7/9) | +0.98% (8/9) | +0.8% (6/9) |
| ema_E48_200_s5 | +1.80% (8/9) | +1.82% (8/9) | +1.70 (8/9) | +0.90 (8/9) | +2.12 (8/9) | -4.5% (2/9) | +47.3% (8/9) | +22.4% (8/9) | +1.19% (8/9) | -4.7% (2/9) |
| z_Z48_2 | -2.98% (0/9) | -2.53% (1/9) | -0.91 (2/9) | -1.04 (2/9) | -0.04 (4/9) | +35.9% (9/9) | -38.2% (0/9) | -33.3% (0/9) | -4.70% (0/9) | -29.3% (0/9) |
| z_Z72_3 | -1.17% (0/9) | -0.42% (2/9) | -1.75 (0/9) | -1.18 (0/9) | -1.38 (1/9) | +24.7% (9/9) | -30.6% (0/9) | -39.6% (0/9) | -1.97% (0/9) | -6.6% (4/9) |
| z_Z24_2p5 | -3.00% (0/9) | -3.72% (0/9) | -1.48 (0/9) | -1.43 (0/9) | -0.05 (3/9) | +36.4% (9/9) | -39.9% (0/9) | -36.9% (0/9) | -5.10% (0/9) | -23.4% (0/9) |

So the answer depends on the family: EMA-cross shorts raised the 11-day mean and all three ratios for 8 or 9 of 9 signals
(two of three parameter sets also at stress costs); breakdown shorts raised the 11-day mean a little but lowered Sortino and
Calmar, deepened the drawdown for 9 of 9 and lost under stress for 9 of 9; z-score shorts lowered everything.

### 4.2 Placebo: is it the signal, or just the side?

Total return with the real signal against the same rule with the signal reversed (mean over the 8 trend signals).

| family_mode | real signal | reversed signal | real better | real, stress | reversed, stress | HMM: real vs reversed |
|---|---|---|---|---|---|---|
| brk_Lg | +58.0% | +12.0% | 6/8 | +28.8% | -2.4% | -36% vs +66% |
| brk_Sb | +2.0% | -11.9% | 7/8 | -16.0% | -17.0% | -15% vs -2% |
| brk_LgSb | +63.4% | -2.3% | 7/8 | +11.2% | -19.2% | -43% vs +76% |
| ema_Lg | -9.9% | +17.9% | 1/8 | -23.9% | -1.6% | -34% vs +12% |
| ema_Sb | +64.7% | +48.7% | 6/8 | +38.4% | +29.8% | -8% vs +90% |
| ema_LgSb | +33.0% | +67.7% | 2/8 | -1.1% | +30.2% | -31% vs +35% |
| z_Lg | -31.8% | -52.7% | 8/8 | -52.7% | -76.8% | -62% vs -15% |
| z_Sb | -56.0% | -80.8% | 8/8 | -74.8% | -89.4% | -84% vs -44% |
| z_LgSb | -71.0% | -88.9% | 8/8 | -87.9% | -96.5% | -93% vs -54% |

- Breakout **longs** are better in good markets (6 of 8 signals; +58% against +12%). This is the one place a direction signal helps.
- EMA-cross **shorts** earn +65% when allowed only in bad markets and +49% when allowed only in good markets, although good
  markets are only 33 to 46% of the hours. Per hour of permission the reversed rule earned more. The team's full rule (LgSb)
  beat its own mirror image for only 2 of 8 signals.
- The HMM is upside down for every family: its reversed version wins everywhere.
- Gating both sides against simply running both sides all the time (LgSb against B, 9 signals): the gated rule had the higher
  total and Sortino for 7 of 9 signals with EMA 24/100, 1 of 9 with EMA 24/200, 0 of 9 with EMA 48/200, 6 of 9 for breakout.

### 4.3 Fixed-size test: gated breakout longs, with and without an EMA-cross short leg

Every position is 24.75% of equity; shorts may use 1 or 2 of the 4 slots; the short leg is allowed in bad markets (the team's
rule), always, or only in good markets (placebo). "d" columns are against the no-shorts row of the same gate.

| gate | short leg | total | max DD | Sortino | Sharpe | Calmar | 11d mean / median | thirds | trades | active days | long P&L | short P&L | stress total | d 11d mean | d Sortino | d Sharpe | d Calmar | d stress total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| btc_ema300 | no shorts | +79% | 22% | +3.36 | +1.63 | +5.04 | +3.1% / +0.3% | +19% / +54% / -3% | 303 | 53% | +80k | +0k | +46% | +0.00% | +0.00 | +0.00 | +0.00 | +0.0% |
| btc_ema300 | E24_200_s6 x1 when bad | +68% | 26% | +2.86 | +1.45 | +3.72 | +2.9% / +1.0% | +18% / +58% / -10% | 378 | 71% | +74k | -6k | +28% | -0.22% | -0.50 | -0.18 | -1.32 | -17.5% |
| btc_ema300 | E24_200_s6 x1 when always | +106% | 25% | +4.03 | +1.98 | +6.23 | +3.8% / +1.0% | +12% / +77% / +4% | 377 | 69% | +72k | +36k | +57% | +0.64% | +0.68 | +0.35 | +1.19 | +11.5% |
| btc_ema300 | E24_200_s6 x1 when good | +114% | 23% | +4.30 | +2.08 | +7.35 | +3.9% / +1.7% | +13% / +76% / +8% | 342 | 57% | +71k | +44k | +69% | +0.82% | +0.95 | +0.45 | +2.32 | +23.1% |
| btc_ema300 | E24_200_s6 x2 when bad | +116% | 23% | +3.96 | +1.99 | +7.58 | +3.9% / +2.2% | +19% / +82% / +0% | 420 | 76% | +86k | +25k | +60% | +0.75% | +0.60 | +0.35 | +2.55 | +14.4% |
| btc_ema300 | E24_200_s6 x2 when always | +133% | 24% | +4.57 | +2.30 | +8.29 | +4.4% / +2.2% | -2% / +93% / +24% | 430 | 76% | +56k | +78k | +72% | +1.25% | +1.21 | +0.67 | +3.26 | +25.9% |
| btc_ema300 | E24_200_s6 x2 when good | +92% | 24% | +3.65 | +1.87 | +5.43 | +3.5% / +1.4% | -3% / +70% / +16% | 369 | 59% | +49k | +44k | +49% | +0.40% | +0.29 | +0.24 | +0.39 | +3.0% |
| btc_ema300 | E48_200_s5 x1 when bad | +105% | 25% | +3.83 | +1.92 | +5.99 | +3.8% / +2.4% | +18% / +78% / -3% | 368 | 69% | +75k | +30k | +58% | +0.71% | +0.47 | +0.28 | +0.95 | +12.1% |
| btc_ema300 | E48_200_s5 x1 when always | +141% | 26% | +4.83 | +2.31 | +8.19 | +4.5% / +2.5% | +23% / +68% / +17% | 388 | 68% | +100k | +41k | +82% | +1.36% | +1.47 | +0.68 | +3.15 | +36.3% |
| btc_ema300 | E48_200_s5 x1 when good | +104% | 23% | +4.13 | +1.96 | +6.54 | +3.7% / +0.4% | +21% / +56% / +8% | 347 | 55% | +101k | +4k | +60% | +0.56% | +0.77 | +0.32 | +1.50 | +13.8% |
| btc_ema300 | E48_200_s5 x2 when bad | +108% | 27% | +3.80 | +1.91 | +5.82 | +3.9% / +2.7% | +13% / +78% / +4% | 419 | 76% | +72k | +36k | +54% | +0.82% | +0.44 | +0.28 | +0.78 | +7.7% |
| btc_ema300 | E48_200_s5 x2 when always | +194% | 23% | +5.98 | +2.72 | +13.29 | +5.2% / +3.0% | +23% / +81% / +32% | 447 | 77% | +104k | +82k | +114% | +2.12% | +2.63 | +1.08 | +8.25 | +67.9% |
| btc_ema300 | E48_200_s5 x2 when good | +132% | 22% | +5.02 | +2.24 | +8.87 | +4.3% / +0.6% | +21% / +70% / +14% | 370 | 57% | +112k | +21k | +80% | +1.14% | +1.66 | +0.60 | +3.83 | +34.2% |
| btc_ema480 | no shorts | +107% | 19% | +4.23 | +2.04 | +8.29 | +3.6% / +0.3% | +23% / +66% / +1% | 256 | 45% | +108k | +0k | +73% | +0.00% | +0.00 | +0.00 | +0.00 | +0.0% |
| btc_ema480 | E24_200_s6 x1 when bad | +93% | 21% | +3.68 | +1.82 | +6.47 | +3.3% / +0.9% | +17% / +63% / +1% | 331 | 69% | +98k | -5k | +52% | -0.28% | -0.56 | -0.22 | -1.83 | -21.7% |
| btc_ema480 | E24_200_s6 x1 when always | +144% | 17% | +5.17 | +2.45 | +12.54 | +4.3% / +1.3% | +16% / +88% / +12% | 335 | 66% | +111k | +34k | +91% | +0.74% | +0.94 | +0.41 | +4.25 | +17.6% |
| btc_ema480 | E24_200_s6 x1 when good | +149% | 17% | +5.57 | +2.54 | +13.60 | +4.4% / +0.7% | +16% / +86% / +15% | 286 | 49% | +113k | +38k | +104% | +0.84% | +1.33 | +0.50 | +5.30 | +30.4% |
| btc_ema480 | E24_200_s6 x2 when bad | +130% | 22% | +4.36 | +2.19 | +8.95 | +4.0% / +2.4% | +20% / +80% / +6% | 381 | 75% | +107k | +24k | +75% | +0.43% | +0.13 | +0.15 | +0.65 | +1.7% |
| btc_ema480 | E24_200_s6 x2 when always | +153% | 22% | +5.05 | +2.52 | +10.36 | +4.6% / +2.5% | +1% / +96% / +28% | 397 | 75% | +90k | +64k | +91% | +1.00% | +0.82 | +0.49 | +2.07 | +17.2% |
| btc_ema480 | E24_200_s6 x2 when good | +127% | 22% | +4.89 | +2.36 | +8.40 | +4.1% / +0.9% | +0% / +81% / +25% | 307 | 51% | +94k | +34k | +84% | +0.49% | +0.66 | +0.33 | +0.10 | +10.2% |
| btc_ema480 | E48_200_s5 x1 when bad | +130% | 21% | +4.57 | +2.25 | +9.20 | +4.2% / +2.3% | +20% / +86% / +3% | 321 | 65% | +109k | +22k | +82% | +0.63% | +0.34 | +0.22 | +0.91 | +8.9% |
| btc_ema480 | E48_200_s5 x1 when always | +186% | 17% | +6.00 | +2.79 | +16.58 | +5.1% / +2.4% | +26% / +82% / +24% | 343 | 64% | +145k | +41k | +123% | +1.49% | +1.77 | +0.75 | +8.28 | +49.3% |
| btc_ema480 | E48_200_s5 x1 when good | +164% | 17% | +5.87 | +2.64 | +14.37 | +4.6% / +1.1% | +24% / +75% / +21% | 295 | 49% | +149k | +15k | +114% | +1.04% | +1.64 | +0.61 | +6.08 | +40.4% |
| btc_ema480 | E48_200_s5 x2 when bad | +175% | 23% | +5.47 | +2.63 | +11.72 | +4.7% / +3.3% | +20% / +87% / +22% | 365 | 73% | +119k | +48k | +110% | +1.16% | +1.24 | +0.59 | +3.42 | +36.8% |
| btc_ema480 | E48_200_s5 x2 when always | +266% | 18% | +7.63 | +3.29 | +24.59 | +6.0% / +3.5% | +27% / +99% / +46% | 401 | 74% | +165k | +92k | +174% | +2.45% | +3.39 | +1.25 | +16.29 | +101.0% |
| btc_ema480 | E48_200_s5 x2 when good | +188% | 15% | +6.67 | +2.83 | +19.41 | +5.0% / +1.2% | +23% / +84% / +27% | 317 | 51% | +162k | +27k | +131% | +1.45% | +2.43 | +0.79 | +11.11 | +57.7% |
| btc_ema720 | no shorts | +129% | 26% | +5.01 | +2.28 | +7.49 | +3.9% / +0.0% | +26% / +53% / +18% | 246 | 41% | +131k | +0k | +93% | +0.00% | +0.00 | +0.00 | +0.00 | +0.0% |
| btc_ema720 | E24_200_s6 x1 when bad | +132% | 25% | +4.70 | +2.23 | +7.76 | +4.1% / +0.8% | +26% / +62% / +13% | 310 | 66% | +136k | -3k | +85% | +0.19% | -0.31 | -0.05 | +0.27 | -8.1% |
| btc_ema720 | E24_200_s6 x1 when always | +168% | 25% | +5.83 | +2.65 | +10.41 | +4.6% / +1.5% | +24% / +76% / +23% | 320 | 65% | +140k | +30k | +112% | +0.76% | +0.82 | +0.37 | +2.92 | +18.6% |
| btc_ema720 | E24_200_s6 x1 when good | +167% | 24% | +6.21 | +2.70 | +10.52 | +4.6% / +0.0% | +22% / +71% / +27% | 268 | 45% | +138k | +32k | +120% | +0.68% | +1.21 | +0.41 | +3.03 | +26.8% |
| btc_ema720 | E24_200_s6 x2 when bad | +165% | 25% | +5.12 | +2.49 | +10.04 | +4.7% / +2.1% | +23% / +80% / +19% | 364 | 73% | +133k | +35k | +104% | +0.80% | +0.11 | +0.21 | +2.55 | +10.4% |
| btc_ema720 | E24_200_s6 x2 when always | +170% | 26% | +5.51 | +2.65 | +9.90 | +4.8% / +2.5% | +8% / +86% / +35% | 387 | 74% | +115k | +57k | +104% | +0.89% | +0.51 | +0.36 | +2.41 | +11.2% |
| btc_ema720 | E24_200_s6 x2 when good | +146% | 25% | +5.64 | +2.54 | +8.77 | +4.4% / +0.0% | +6% / +74% / +34% | 293 | 47% | +111k | +38k | +101% | +0.50% | +0.64 | +0.26 | +1.28 | +7.8% |
| btc_ema720 | E48_200_s5 x1 when bad | +149% | 26% | +5.18 | +2.43 | +8.68 | +4.2% / +1.9% | +30% / +52% / +26% | 306 | 64% | +133k | +17k | +99% | +0.34% | +0.17 | +0.15 | +1.19 | +6.3% |
| btc_ema720 | E48_200_s5 x1 when always | +191% | 23% | +6.27 | +2.83 | +13.06 | +5.1% / +2.1% | +30% / +65% / +36% | 330 | 63% | +154k | +39k | +129% | +1.19% | +1.26 | +0.55 | +5.57 | +35.6% |
| btc_ema720 | E48_200_s5 x1 when good | +171% | 21% | +6.18 | +2.71 | +12.52 | +4.6% / +0.0% | +28% / +59% / +33% | 282 | 45% | +152k | +20k | +121% | +0.74% | +1.17 | +0.42 | +5.03 | +28.2% |
| btc_ema720 | E48_200_s5 x2 when bad | +188% | 28% | +5.84 | +2.73 | +10.34 | +4.7% / +2.6% | +26% / +62% / +41% | 352 | 73% | +138k | +43k | +123% | +0.84% | +0.83 | +0.44 | +2.85 | +29.7% |
| btc_ema720 | E48_200_s5 x2 when always | +269% | 26% | +7.76 | +3.27 | +17.01 | +6.0% / +3.2% | +30% / +82% / +57% | 393 | 74% | +171k | +90k | +178% | +2.12% | +2.76 | +0.99 | +9.52 | +85.4% |
| btc_ema720 | E48_200_s5 x2 when good | +192% | 23% | +6.89 | +2.85 | +13.33 | +4.9% / +0.0% | +32% / +62% / +37% | 311 | 47% | +157k | +36k | +136% | +1.06% | +1.88 | +0.57 | +5.84 | +42.6% |

Of the 36 variants with shorts: 11-day mean higher in 34, Sortino higher in 33,
Sharpe higher in 33, Calmar higher in 34, stress total higher in 33, max drawdown lower in 15,
short P&L negative in 3. Short gate, 12 like-for-like groups: "always" earned more short P&L than "bad" in 12;
"bad" beat "good" (the placebo) in 5; mean short P&L was +22k for "bad", +29k for "good" and +57k for "always".
The team's version (short when bad) is the weakest of the three on average and is the only one that ever lost money
(24/200 with one short slot: -$3k to -$6k at all three gates).

(An earlier version of this test, `combo` rows in `s4_results.jsonl`, sized the long book on the slots the shorts did not hold and so
concentrated the longs; its totals of +190% to +271% are inflated by that and are not used. The table above replaces it.)

## 5. The short side on its own: real edge or bear market?

### 5.1 Short legs in 11-day and 30-day blocks, split by whether the basket rose

| short leg | 11d blocks, basket rose (10 blocks, +7.5%) | 11d, basket fell (15, -8.0%) | 30d, basket rose (3, +7.3%) | 30d, basket fell (6, -12.8%) |
|---|---|---|---|---|
| ema_E24_100_s3_S_always | -4.21% (20% positive) | +4.91% (80%) | -1.08% (67%) | +6.13% (67%) |
| ema_E24_200_s6_S_always | -2.91% (30% positive) | +6.73% (93%) | +1.70% (67%) | +13.30% (83%) |
| ema_E48_200_s5_S_always | -2.85% (30% positive) | +4.14% (87%) | +0.45% (33%) | +6.82% (100%) |
| brk_BK8_6_S_always | -3.89% (20% positive) | +1.16% (53%) | -15.97% (0%) | +5.18% (83%) |
| z_Z48_2_S_always | -10.04% (10% positive) | -5.22% (47%) | -23.77% (0%) | -15.29% (33%) |
| z_Z72_3_S_always | -5.56% (20% positive) | -4.25% (47%) | -19.00% (0%) | -9.50% (33%) |
| ema_E24_200_s6_Sb_btc_ema200 | -0.98% (50% positive) | +5.64% (73%) | +0.65% (67%) | +13.86% (83%) |
| ema_E24_200_s6_Sb_btc_ema480 | -2.28% (20% positive) | +4.33% (60%) | -2.78% (0%) | +10.62% (83%) |
| ema_E24_200_s6_Sb_bkt_ema100 | -1.11% (40% positive) | +5.96% (80%) | +2.56% (67%) | +13.47% (100%) |
| ema_E24_200_s6_Sb_breadth | -3.29% (20% positive) | +4.87% (80%) | -1.57% (67%) | +9.33% (100%) |
| brk_BK8_6_Sb_btc_ema480 | -1.82% (20% positive) | +1.33% (67%) | -9.45% (0%) | +5.75% (83%) |
| brk_BK8_6_Sb_bkt_ema480 | -1.21% (30% positive) | +1.90% (67%) | -7.63% (0%) | +7.08% (100%) |

### 5.2 Return beyond being short the basket (daily regression on the basket; alpha per 11 days)

| leg | alpha / 11d | t | beta | mean on up days | mean on down days | stress alpha / 11d | stress t |
|---|---|---|---|---|---|---|---|
| brk_L | +2.71% | +1.34 | +0.46 | +1.31% | -0.93% | +1.54% | +0.76 |
| brk_Lg_btc480 | +3.67% | +2.20 | +0.27 | +1.08% | -0.47% | +2.97% | +1.79 |
| brk_Lg_bkt200 | +3.35% | +1.79 | +0.35 | +1.10% | -0.58% | +2.47% | +1.33 |
| brk_S | -1.14% | -0.91 | -0.35 | -1.16% | +1.03% | -2.01% | -1.59 |
| brk_Sb_btc480 | -0.16% | -0.15 | -0.30 | -0.82% | +0.86% | -0.85% | -0.79 |
| ema24_100_S | +0.50% | +0.40 | -0.41 | -0.99% | +1.18% | -1.57% | -1.22 |
| ema24_200_S | +1.96% | +1.71 | -0.52 | -1.28% | +1.75% | +1.04% | +0.90 |
| ema48_200_S | +0.93% | +0.85 | -0.40 | -1.10% | +1.36% | -0.01% | -0.01 |
| ema24_200_Sb_btc480 | +1.20% | +1.04 | -0.41 | -0.97% | +1.27% | +0.53% | +0.45 |
| ema24_200_L | +1.80% | +0.91 | +0.57 | +1.78% | -1.58% | +0.79% | +0.39 |
| ema24_200_B | +2.46% | +1.13 | +0.05 | +0.29% | +0.14% | +1.27% | +0.58 |
| z48_S | -9.07% | -4.31 | -0.62 | -2.60% | +1.09% | -13.07% | -6.01 |
| btc_short_always | +0.61% | +0.87 | -0.40 | -1.09% | +1.29% | +0.61% | +0.86 |
| combo_btc480_Sbad | +3.89% | +2.02 | +0.08 | +0.56% | +0.13% | +2.81% | +1.46 |
| combo_btc480_Salw | +4.58% | +2.25 | -0.03 | +0.27% | +0.56% | +3.38% | +1.67 |

(`combo_*` rows are the concentrated-sizing version, shown for completeness only.)

### 5.3 Is the EMA-cross short a plateau? 40 settings, short-only, always on, 4 slots

| fast | slow | stop (ATR) | total | max DD | thirds | 11d mean | trades | basket-rose blocks | basket-fell blocks | alpha / 11d (t) | beta | stress total | stress thirds | stress alpha (t) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12 | 100 | 3 | -36.1% | 52% | -20% / -16% / -4% | -1.49% | 888 | -7.30% | +2.24% | -2.14% (-1.69) | -0.49 | -67.9% | -36% / -35% / -23% | -4.80% (-3.66) |
| 12 | 150 | 3 | +10.0% | 26% | +4% / +12% / -6% | +0.53% | 750 | -5.83% | +4.76% | +0.02% (+0.01) | -0.45 | -39.6% | -13% / -10% / -23% | -2.29% (-1.69) |
| 12 | 200 | 3 | +28.7% | 28% | +18% / +24% / -12% | +1.37% | 686 | -4.46% | +5.34% | +0.63% (+0.50) | -0.41 | -25.6% | -1% / +2% / -26% | -1.49% (-1.15) |
| 12 | 300 | 3 | +30.1% | 29% | +6% / -1% / +24% | +1.30% | 613 | -3.49% | +4.15% | +0.72% (+0.64) | -0.35 | -20.1% | -10% / -18% / +7% | -1.16% (-0.99) |
| 12 | 400 | 3 | +8.9% | 24% | -7% / +15% / +2% | +0.68% | 524 | -3.37% | +3.20% | +0.06% (+0.05) | -0.32 | -27.5% | -17% / -1% / -11% | -1.52% (-1.31) |
| 24 | 100 | 3 | +24.3% | 24% | +11% / +22% / -8% | +1.07% | 669 | -4.21% | +4.91% | +0.50% (+0.40) | -0.41 | -27.4% | -6% / -0% / -23% | -1.57% (-1.22) |
| 24 | 150 | 3 | +20.8% | 25% | +4% / +16% / +1% | +1.14% | 626 | -5.06% | +5.14% | +0.41% (+0.32) | -0.41 | -26.8% | -12% / -3% / -14% | -1.52% (-1.13) |
| 24 | 200 | 3 | +5.4% | 26% | +13% / +16% / -19% | +0.44% | 569 | -4.36% | +3.61% | -0.09% (-0.08) | -0.36 | -33.1% | -2% / -1% / -31% | -1.84% (-1.51) |
| 24 | 300 | 3 | -8.5% | 32% | -8% / +2% / -2% | +0.10% | 502 | -4.63% | +3.03% | -0.62% (-0.52) | -0.31 | -39.5% | -20% / -12% / -14% | -2.22% (-1.84) |
| 24 | 400 | 3 | -7.8% | 29% | -5% / -0% / -3% | -0.04% | 421 | -3.28% | +1.94% | -0.51% (-0.47) | -0.24 | -33.5% | -13% / -12% / -13% | -1.78% (-1.60) |
| 48 | 100 | 3 | -10.3% | 29% | -5% / +8% / -13% | -0.06% | 565 | -5.33% | +3.34% | -0.77% (-0.71) | -0.36 | -43.4% | -18% / -9% / -25% | -2.54% (-2.28) |
| 48 | 150 | 3 | -17.3% | 29% | -0% / +2% / -19% | -0.44% | 511 | -4.52% | +2.30% | -0.97% (-0.87) | -0.26 | -46.0% | -14% / -12% / -29% | -2.61% (-2.28) |
| 48 | 200 | 3 | +1.6% | 25% | +2% / +13% / -12% | +0.40% | 478 | -3.18% | +2.66% | -0.19% (-0.17) | -0.28 | -31.5% | -9% / -2% / -23% | -1.70% (-1.47) |
| 48 | 300 | 3 | -6.0% | 21% | -2% / +7% / -10% | -0.05% | 435 | -3.32% | +1.92% | -0.46% (-0.48) | -0.23 | -33.3% | -12% / -5% / -20% | -1.79% (-1.81) |
| 48 | 400 | 3 | -13.8% | 25% | -13% / +5% / -6% | -0.51% | 346 | -2.90% | +0.96% | -0.68% (-0.73) | -0.14 | -34.7% | -20% / -5% / -15% | -1.75% (-1.85) |
| 72 | 100 | 3 | -8.1% | 25% | -6% / +11% / -12% | -0.14% | 516 | -5.08% | +3.21% | -0.64% (-0.61) | -0.32 | -39.2% | -18% / -4% / -23% | -2.23% (-2.07) |
| 72 | 150 | 3 | -24.3% | 40% | -15% / +5% / -16% | -0.81% | 479 | -3.78% | +1.05% | -1.36% (-1.35) | -0.28 | -49.7% | -25% / -10% / -26% | -2.94% (-2.83) |
| 72 | 200 | 3 | -8.0% | 24% | -8% / +10% / -9% | -0.03% | 458 | -3.48% | +1.96% | -0.56% (-0.53) | -0.26 | -36.2% | -18% / -4% / -19% | -1.98% (-1.80) |
| 72 | 300 | 3 | -10.5% | 28% | -12% / +8% / -6% | -0.27% | 384 | -3.54% | +1.79% | -0.62% (-0.63) | -0.21 | -33.9% | -20% / -2% / -15% | -1.80% (-1.79) |
| 72 | 400 | 3 | -24.5% | 32% | -20% / +6% / -11% | -0.91% | 328 | -3.85% | +1.00% | -1.26% (-1.38) | -0.18 | -42.1% | -26% / -4% / -18% | -2.29% (-2.45) |
| 12 | 100 | 6 | -4.0% | 47% | -25% / +17% / +10% | +0.40% | 517 | -5.49% | +4.01% | -0.69% (-0.58) | -0.59 | -34.1% | -35% / +3% / -2% | -2.14% (-1.75) |
| 12 | 150 | 6 | +43.9% | 29% | -1% / +22% / +19% | +1.78% | 435 | -4.70% | +5.83% | +0.88% (+0.80) | -0.56 | +3.8% | -10% / +8% / +7% | -0.39% (-0.34) |
| 12 | 200 | 6 | +77.9% | 23% | +8% / +44% / +15% | +2.83% | 401 | -3.76% | +7.03% | +1.73% (+1.57) | -0.56 | +32.6% | -3% / +30% / +5% | +0.59% (+0.52) |
| 12 | 300 | 6 | +108.4% | 20% | +8% / +37% / +40% | +3.35% | 353 | -2.03% | +6.32% | +2.40% (+2.14) | -0.50 | +60.4% | -1% / +24% / +30% | +1.39% (+1.21) |
| 12 | 400 | 6 | +94.6% | 23% | -5% / +49% / +38% | +3.08% | 307 | -2.05% | +6.02% | +2.16% (+1.85) | -0.46 | +54.7% | -12% / +37% / +28% | +1.27% (+1.07) |
| 24 | 100 | 6 | +26.9% | 30% | -3% / +26% / +3% | +1.31% | 383 | -3.88% | +4.70% | +0.45% (+0.39) | -0.54 | -6.6% | -11% / +13% / -7% | -0.74% (-0.63) |
| 24 | 150 | 6 | +78.1% | 25% | +8% / +43% / +16% | +2.92% | 336 | -3.82% | +7.12% | +1.74% (+1.51) | -0.55 | +37.0% | -1% / +30% / +6% | +0.72% (+0.61) |
| 24 | 200 | 6 | +86.8% | 21% | +12% / +47% / +13% | +3.05% | 311 | -2.91% | +6.73% | +1.96% (+1.71) | -0.52 | +47.6% | +4% / +35% / +5% | +1.04% (+0.90) |
| 24 | 300 | 6 | +86.1% | 19% | +8% / +51% / +14% | +3.09% | 280 | -2.35% | +6.25% | +1.99% (+1.65) | -0.48 | +49.1% | +1% / +40% / +6% | +1.13% (+0.92) |
| 24 | 400 | 6 | +49.6% | 22% | -8% / +40% / +17% | +2.04% | 241 | -3.16% | +5.22% | +1.21% (+1.01) | -0.40 | +24.9% | -13% / +31% / +10% | +0.51% (+0.42) |
| 48 | 100 | 6 | -4.2% | 34% | -14% / +17% / -5% | +0.42% | 313 | -5.95% | +4.40% | -0.68% (-0.61) | -0.53 | -25.4% | -20% / +8% / -13% | -1.65% (-1.44) |
| 48 | 150 | 6 | +63.9% | 21% | +10% / +45% / +3% | +2.51% | 278 | -3.52% | +6.29% | +1.44% (+1.32) | -0.49 | +31.6% | +2% / +35% / -5% | +0.59% (+0.53) |
| 48 | 200 | 6 | +85.6% | 19% | +14% / +41% / +15% | +2.91% | 258 | -1.06% | +5.31% | +1.97% (+1.76) | -0.45 | +51.7% | +7% / +31% / +8% | +1.19% (+1.05) |
| 48 | 300 | 6 | +38.7% | 20% | +7% / +17% / +11% | +1.73% | 244 | -2.75% | +4.46% | +0.88% (+0.80) | -0.39 | +14.5% | +0% / +9% / +4% | +0.14% (+0.13) |
| 48 | 400 | 6 | +17.0% | 25% | -18% / +38% / +3% | +1.03% | 211 | -3.05% | +3.71% | +0.35% (+0.33) | -0.29 | -0.9% | -22% / +30% / -3% | -0.29% (-0.27) |
| 72 | 100 | 6 | +16.4% | 24% | -4% / +27% / -5% | +0.96% | 278 | -4.55% | +4.49% | +0.12% (+0.10) | -0.50 | -6.8% | -11% / +18% / -11% | -0.74% (-0.60) |
| 72 | 150 | 6 | +22.4% | 25% | -4% / +34% / -5% | +1.30% | 256 | -2.71% | +3.75% | +0.35% (+0.33) | -0.45 | -0.0% | -11% / +26% / -11% | -0.43% (-0.40) |
| 72 | 200 | 6 | +53.3% | 18% | -0% / +42% / +8% | +2.19% | 239 | -2.06% | +4.60% | +1.29% (+1.10) | -0.41 | +26.9% | -6% / +33% / +1% | +0.56% (+0.47) |
| 72 | 300 | 6 | +17.0% | 28% | -11% / +31% / +0% | +0.97% | 221 | -3.42% | +3.65% | +0.25% (+0.25) | -0.36 | -1.7% | -16% / +23% / -5% | -0.42% (-0.40) |
| 72 | 400 | 6 | +6.8% | 21% | -9% / +27% / -8% | +0.59% | 192 | -3.46% | +3.19% | -0.09% (-0.09) | -0.34 | -8.3% | -12% / +20% / -13% | -0.68% (-0.68) |

Of 40 settings: total > 0 in 26; stress total > 0 in 12; alpha > 0 in 23
(stress: 11); t(alpha) > 2 in 1; all three thirds positive in 9 (stress: 4);
**positive in the blocks where the basket rose: 0 of 40**. The 3-ATR stop: stress total > 0 in 0 of 20. The 6-ATR stop:
default total > 0 in 18 of 20, stress total > 0 in 12 of 20. So there is a region (wide stop, fast 12-48 h, slow 150-300 h: +39% to +108%,
stress +4% to +60%), but it exists only with the wide stop, its best t(alpha) is 2.1 out of 40 tries, and no setting made
money while the basket was rising. One expects about 1 in 40 to reach t = 2 by chance.

### 5.4 The mirrored breakdown short: 16 settings, short-only, always on

| 24h move | trail | total | max DD | thirds | trades | basket-rose blocks | basket-fell blocks | alpha / 11d (t) | beta | stress total |
|---|---|---|---|---|---|---|---|---|---|---|
| 6% | 4% | -35.9% | 59% | -27% / -29% / +23% | 562 | -4.81% | +0.31% | -2.02% (-1.59) | -0.36 | -56.3% |
| 6% | 6% | -12.3% | 44% | -28% / -4% / +26% | 369 | -4.41% | +2.04% | -0.92% (-0.75) | -0.46 | -32.2% |
| 6% | 8% | -25.2% | 52% | -40% / +13% / +10% | 285 | -5.89% | +2.30% | -1.64% (-1.28) | -0.57 | -39.7% |
| 6% | 10% | -5.3% | 48% | -29% / +8% / +24% | 208 | -5.11% | +3.25% | -0.79% (-0.65) | -0.66 | -18.8% |
| 8% | 4% | -42.9% | 55% | -27% / -22% / +1% | 462 | -5.21% | -0.23% | -2.36% (-2.06) | -0.23 | -58.3% |
| 8% | 6% | -19.7% | 44% | -27% / +7% / +3% | 329 | -3.89% | +1.16% | -1.14% (-0.91) | -0.35 | -36.1% |
| 8% | 8% | -22.9% | 53% | -35% / +10% / +7% | 247 | -4.92% | +1.72% | -1.41% (-1.08) | -0.47 | -36.6% |
| 8% | 10% | -10.1% | 54% | -31% / +13% / +15% | 191 | -5.10% | +3.01% | -0.92% (-0.74) | -0.57 | -21.9% |
| 10% | 4% | -34.7% | 48% | -19% / -20% / -0% | 317 | -2.60% | -1.03% | -1.75% (-1.78) | -0.14 | -47.1% |
| 10% | 6% | -20.3% | 38% | -17% / -8% / +4% | 256 | -1.65% | -0.35% | -1.08% (-1.02) | -0.24 | -33.2% |
| 10% | 8% | -28.6% | 39% | -24% / -1% / -5% | 203 | -2.66% | -0.36% | -1.63% (-1.32) | -0.37 | -38.2% |
| 10% | 10% | -31.3% | 39% | -24% / +6% / -15% | 176 | -3.33% | -0.03% | -1.88% (-1.53) | -0.46 | -39.6% |
| 12% | 4% | -26.4% | 37% | -8% / -23% / +4% | 211 | -1.91% | -0.65% | -1.23% (-1.59) | -0.07 | -36.2% |
| 12% | 6% | -31.3% | 37% | -19% / -14% / -1% | 188 | -1.77% | -1.32% | -1.53% (-1.81) | -0.11 | -39.5% |
| 12% | 8% | -29.5% | 37% | -24% / -8% / +1% | 154 | -1.69% | -1.18% | -1.58% (-1.44) | -0.24 | -36.7% |
| 12% | 10% | -33.7% | 40% | -21% / -8% / -9% | 136 | -2.00% | -1.33% | -1.86% (-1.56) | -0.30 | -39.9% |

0 of 16 made money, in a market that fell 45%. All 16 have negative alpha. A coin that has just dropped 8% to a 3-day low
bounces often enough to stop the short out. This confirms the earlier finding ("shorting breakdowns lost on average").

## 6. The hedge: a standing BTC short against a long book of small coins

Long book = breakout longs (ungated `brkL`, or gated by BTC > EMA480 `brkLg`), never buying BTC. `scaled` = the long book at
reduced size with no hedge (the fair comparison). `stand` = BTC short of hf x equity always on. `cond` = hedge on only in bad
markets. `match` = BTC short equal to k x the current long value, only while longs are held.

| book | hedge | setting | total | max DD | Sortino | Sharpe | Calmar | 11d mean / median | thirds | trades | active days | long P&L | short P&L | stress total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brkL | scaled | expo 0.80 no hedge | +36% | 36% | +1.94 | +0.98 | +1.33 | +1.7% / -0.4% | +12% / +48% / -18% | 449 | 80% | +36k | +0k | +7% |
| brkL | stand | hf 0.2 | +44% | 32% | +2.25 | +1.14 | +1.91 | +2.0% / +0.0% | +11% / +53% / -15% | 453 | 80% | +31k | +13k | +15% |
| brkL | cond | hf 0.2 | +36% | 35% | +1.95 | +0.99 | +1.42 | +1.8% / -0.2% | +9% / +51% / -17% | 521 | 84% | +32k | +4k | +4% |
| brkLg | stand | hf 0.2 | +96% | 15% | +4.82 | +2.31 | +9.18 | +3.2% / +1.4% | +18% / +56% / +7% | 259 | 46% | +82k | +12k | +67% |
| brkLg | cond | hf 0.2 | +85% | 16% | +4.22 | +2.07 | +7.67 | +3.0% / +1.4% | +17% / +53% / +3% | 328 | 51% | +81k | +5k | +56% |
| brkL | scaled | expo 0.67 no hedge | +31% | 31% | +1.93 | +0.97 | +1.33 | +1.4% / -0.3% | +10% / +40% / -15% | 449 | 80% | +31k | +0k | +7% |
| brkL | stand | hf 0.33 | +44% | 23% | +2.45 | +1.28 | +2.58 | +1.8% / +0.6% | +8% / +46% / -9% | 453 | 80% | +25k | +19k | +20% |
| brkL | cond | hf 0.33 | +32% | 28% | +1.95 | +1.01 | +1.55 | +1.6% / -0.0% | +6% / +44% / -13% | 521 | 83% | +26k | +7k | +3% |
| brkLg | stand | hf 0.33 | +84% | 13% | +4.84 | +2.42 | +9.40 | +2.9% / +1.8% | +14% / +47% / +9% | 259 | 46% | +65k | +21k | +63% |
| brkLg | cond | hf 0.33 | +69% | 16% | +3.99 | +2.03 | +6.25 | +2.6% / +1.7% | +12% / +45% / +4% | 328 | 51% | +64k | +6k | +44% |
| brkL | scaled | expo 0.50 no hedge | +24% | 24% | +1.91 | +0.97 | +1.31 | +1.1% / -0.2% | +8% / +29% / -11% | 449 | 80% | +24k | +0k | +6% |
| brkL | stand | hf 0.5 | +43% | 17% | +2.74 | +1.51 | +3.46 | +1.7% / +0.9% | +5% / +36% / +0% | 453 | 80% | +21k | +18k | +28% |
| brkL | cond | hf 0.5 | +26% | 22% | +1.86 | +1.02 | +1.59 | +1.3% / +0.4% | +1% / +35% / -8% | 521 | 83% | +19k | +8k | +2% |
| brkLg | stand | hf 0.5 | +71% | 11% | +4.41 | +2.48 | +9.31 | +2.5% / +1.7% | +9% / +38% / +13% | 259 | 46% | +45k | +32k | +58% |
| brkLg | cond | hf 0.5 | +51% | 17% | +3.47 | +1.90 | +4.11 | +2.1% / +1.3% | +6% / +36% / +5% | 328 | 51% | +44k | +7k | +29% |
| brkL | match | k 0.5 | +12% | 33% | +1.02 | +0.53 | +0.47 | +0.8% / -1.0% | +2% / +34% / -18% | 824 | 80% | +31k | -18k | -18% |
| brkLg | match | k 0.5 | +53% | 12% | +3.65 | +1.78 | +5.91 | +2.0% / +0.0% | +10% / +39% / +0% | 467 | 46% | +64k | -10k | +27% |
| brkL | match | k 1.0 | -2% | 28% | +0.08 | +0.04 | -0.11 | +0.1% / -1.1% | -4% / +21% / -16% | 824 | 80% | +23k | -25k | -30% |
| brkLg | match | k 1.0 | +29% | 10% | +2.86 | +1.45 | +4.12 | +1.3% / +0.0% | +4% / +26% / -1% | 469 | 46% | +45k | -14k | +7% |

With BTC's own drift removed from the hedge (daily hedge contribution minus its mean):

| book | hedge share | long book alone: Sortino / Sharpe / Calmar / DD | hedged | hedged, BTC drift removed | hedge earned per 11 d |
|---|---|---|---|---|---|
| gated | 0.2 | +4.29 / +2.06 / +8.68 / 13.6% | +4.82 / +2.31 / +10.37 / 13.3% | +4.35 / +2.11 / +8.88 / 13.4% | +0.25% |
| gated | 0.33 | +4.27 / +2.05 / +8.17 / 11.5% | +4.84 / +2.42 / +10.74 / 11.1% | +4.10 / +2.08 / +8.46 / 11.2% | +0.35% |
| gated | 0.5 | +4.25 / +2.05 / +7.55 / 8.7% | +4.41 / +2.48 / +10.33 / 9.6% | +3.16 / +1.83 / +5.71 / 11.3% | +0.58% |
| ungated | 0.2 | +1.94 / +0.98 / +1.45 / 32.8% | +2.25 / +1.14 / +2.02 / 29.4% | +1.98 / +1.01 / +1.58 / 30.9% | +0.20% |
| ungated | 0.33 | +1.93 / +0.97 / +1.46 / 28.0% | +2.45 / +1.28 / +2.66 / 22.2% | +1.92 / +1.02 / +1.68 / 24.9% | +0.34% |
| ungated | 0.5 | +1.91 / +0.97 / +1.45 / 21.5% | +2.74 / +1.51 / +3.53 / 16.4% | +1.70 / +0.96 / +1.71 / 18.3% | +0.56% |

The direction signal traded on BTC alone (short BTC with all capital while the market is "bad", cash otherwise):

| signal | total | max DD | Sortino | Sharpe | Calmar | 11d mean / median | thirds | trades | active days | long P&L | short P&L | stress total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC > EMA100 | -32% | 35% | -2.05 | -1.45 | -1.10 | -1.2% / -2.1% | -25% / +11% / -18% | 188 | 48% | +0k | -32k | -51% |
| BTC > EMA200 | -28% | 34% | -1.82 | -1.29 | -1.02 | -0.8% / -2.0% | -21% / +7% / -14% | 145 | 36% | +0k | -28k | -44% |
| BTC > EMA480 | +3% | 21% | +0.42 | +0.27 | +0.18 | +0.6% / -0.3% | -10% / +9% / +5% | 70 | 21% | +0k | +3k | -9% |
| basket > EMA100 | -23% | 29% | -1.44 | -0.98 | -1.00 | -0.6% / -1.7% | -14% / -0% / -11% | 195 | 48% | +0k | -23k | -46% |
| basket > EMA200 | -12% | 27% | -0.56 | -0.37 | -0.54 | -0.1% / -1.6% | -13% / -2% / +3% | 132 | 37% | +0k | -12k | -30% |
| basket > EMA480 | +12% | 18% | +0.99 | +0.65 | +0.89 | +1.0% / +0.0% | -11% / +16% / +9% | 58 | 19% | +0k | +12k | +1% |
| breadth 55/45 | +6% | 20% | +0.62 | +0.40 | +0.39 | +0.6% / -0.7% | -8% / +14% / +1% | 67 | 29% | +0k | +6k | -6% |
| BTC 7d return > 0 | -17% | 30% | -1.02 | -0.71 | -0.72 | -0.5% / -2.0% | -19% / +7% / -4% | 135 | 31% | +0k | -16k | -35% |
| 2-state HMM | -32% | 36% | -2.05 | -1.57 | -1.07 | -1.3% / -1.0% | -17% / -13% / -5% | 36 | 22% | +0k | -32k | -36% |
| always short | +32% | 25% | +1.84 | +1.18 | +1.76 | +1.4% / +1.0% | -6% / +19% / +18% | 0 | 0% | +0k | +0k | +32% |

Reading: against the same long book at the same reduced size, the standing hedge raised Sortino, Sharpe and Calmar in 6 of 6
rows and cut the drawdown in 5 of 6, and it costs almost nothing in fees (3 to 4 round trips in 9 months). But it earned +0.2% to +0.6% per 11 days purely because BTC fell. Without that
drift the hedged book is no better than a smaller unhedged book. Timing the hedge with the signal (`cond`) was worse than
leaving it on, and timing a BTC short with any of the 9 signals lost money for 6 of 9 while a plain always-on BTC short made
+32%: again the signal adds nothing to the short side. A hedge sized to the long book (`match`) lost money on the short
(-$10k to -$25k) because it is short exactly when the longs are winning.

## 7. The direction gate on breakout longs

### 7.1 Plateau: 32 gates. Trade-level test = the 449 ungated trades split by the state at entry

| gate | good-market entries (n) | bad-market entries (n) | t | thirds agreeing | total | max DD | Sortino | Sharpe | Calmar | 11d mean / median | thirds | trades | active days | long P&L | short P&L | stress total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| btc_ema100 | -0.14% (290) | +1.55% (159) | -1.61 | 2/3 | -0% | 36% | +0.46 | +0.25 | -0.00 | +0.6% / -0.6% | +14% / +7% / -18% | 342 | 63% | +0k | +0k | -20% |
| btc_ema150 | +0.66% (275) | +0.13% (174) | +0.59 | 2/3 | +75% | 30% | +3.19 | +1.53 | +3.50 | +3.0% / +1.4% | +32% / +55% / -14% | 325 | 59% | +76k | +0k | +41% |
| btc_ema200 | +0.60% (261) | +0.26% (188) | +0.38 | 2/3 | +53% | 28% | +2.42 | +1.22 | +2.63 | +2.5% / +0.0% | +15% / +52% / -12% | 331 | 57% | +53k | +0k | +23% |
| btc_ema300 | +0.87% (252) | -0.07% (197) | +1.06 | 3/3 | +79% | 22% | +3.36 | +1.63 | +5.04 | +3.1% / +0.3% | +19% / +54% / -3% | 303 | 53% | +80k | +0k | +46% |
| btc_ema400 | +1.12% (228) | -0.23% (221) | +1.51 | 3/3 | +110% | 18% | +4.38 | +2.06 | +9.09 | +3.7% / +0.3% | +22% / +64% / +5% | 267 | 48% | +110k | +0k | +74% |
| btc_ema480 | +1.03% (219) | -0.09% (230) | +1.24 | 3/3 | +107% | 19% | +4.23 | +2.04 | +8.29 | +3.6% / +0.3% | +23% / +66% / +1% | 256 | 45% | +108k | +0k | +73% |
| btc_ema600 | +1.35% (215) | -0.36% (234) | +1.87 | 3/3 | +96% | 19% | +4.08 | +1.94 | +7.41 | +3.2% / +0.0% | +31% / +55% / -3% | 247 | 42% | +97k | +0k | +65% |
| btc_ema720 | +1.56% (208) | -0.49% (241) | +2.21 | 3/3 | +129% | 26% | +5.01 | +2.28 | +7.49 | +3.9% / +0.0% | +26% / +53% / +18% | 246 | 41% | +131k | +0k | +93% |
| btc_ema960 | +1.61% (205) | -0.60% (233) | +2.34 | 3/3 | +112% | 32% | +4.74 | +2.16 | +5.19 | +3.5% / +0.0% | +17% / +50% / +21% | 229 | 36% | +112k | +0k | +81% |
| bkt_ema100 | +0.45% (338) | +0.48% (111) | -0.04 | 2/3 | +60% | 34% | +2.51 | +1.21 | +2.44 | +2.7% / -0.4% | +3% / +91% / -19% | 387 | 65% | +60k | +0k | +24% |
| bkt_ema150 | +0.84% (301) | -0.33% (148) | +1.38 | 3/3 | +62% | 31% | +2.55 | +1.29 | +2.77 | +2.7% / +1.0% | +2% / +76% / -10% | 366 | 60% | +62k | +0k | +27% |
| bkt_ema200 | +1.14% (268) | -0.56% (181) | +2.03 | 3/3 | +78% | 27% | +3.27 | +1.53 | +4.07 | +3.2% / +0.0% | +2% / +88% / -7% | 343 | 57% | +80k | +0k | +43% |
| bkt_ema300 | +1.16% (235) | -0.32% (214) | +1.67 | 2/3 | +76% | 25% | +3.23 | +1.58 | +4.29 | +3.1% / +0.0% | -2% / +86% / -4% | 306 | 47% | +77k | +0k | +43% |
| bkt_ema400 | +1.22% (216) | -0.26% (233) | +1.61 | 3/3 | +50% | 24% | +2.42 | +1.25 | +2.89 | +2.5% / +0.0% | -6% / +68% / -5% | 285 | 42% | +51k | +0k | +24% |
| bkt_ema480 | +1.09% (210) | -0.10% (239) | +1.28 | 2/3 | +52% | 21% | +2.62 | +1.30 | +3.39 | +2.4% / +0.0% | -1% / +66% / -8% | 267 | 39% | +54k | +0k | +27% |
| bkt_ema600 | +1.40% (198) | -0.29% (251) | +1.76 | 2/3 | +65% | 23% | +3.05 | +1.50 | +3.94 | +2.9% / +0.0% | -6% / +61% / +10% | 257 | 37% | +67k | +0k | +38% |
| bkt_ema720 | +1.40% (193) | -0.25% (256) | +1.70 | 2/3 | +55% | 28% | +2.70 | +1.36 | +2.75 | +2.4% / +0.0% | -15% / +51% / +20% | 243 | 35% | +55k | +0k | +31% |
| bkt_ema960 | +1.16% (191) | -0.12% (247) | +1.32 | 2/3 | +66% | 30% | +3.28 | +1.57 | +3.07 | +2.4% / +0.0% | -12% / +57% / +20% | 218 | 33% | +66k | +0k | +42% |
| btc_ret48 | -0.18% (267) | +1.39% (182) | -1.64 | 0/3 | -19% | 42% | -0.42 | -0.23 | -0.57 | -0.4% / -1.9% | -2% / +21% / -32% | 343 | 63% | -19k | +0k | -35% |
| btc_ret72 | -0.00% (269) | +1.14% (180) | -1.22 | 1/3 | -2% | 39% | +0.37 | +0.21 | -0.07 | +0.4% / -1.3% | +14% / +12% / -23% | 338 | 60% | -2k | +0k | -21% |
| btc_ret120 | +0.95% (224) | -0.04% (225) | +1.09 | 3/3 | +49% | 30% | +2.42 | +1.24 | +2.30 | +2.2% / +0.7% | +20% / +45% / -14% | 285 | 53% | +48k | +0k | +24% |
| btc_ret168 | +1.13% (238) | -0.30% (211) | +1.61 | 3/3 | +95% | 22% | +3.97 | +1.83 | +6.27 | +3.3% / +0.7% | +27% / +61% / -5% | 280 | 53% | +94k | +0k | +61% |
| btc_ret240 | +1.04% (226) | -0.13% (223) | +1.30 | 3/3 | +43% | 28% | +2.11 | +1.11 | +2.12 | +2.1% / +0.0% | +4% / +63% / -16% | 274 | 46% | +43k | +0k | +18% |
| btc_ret336 | +0.90% (232) | -0.02% (217) | +1.03 | 3/3 | +67% | 20% | +3.04 | +1.50 | +4.72 | +2.7% / +0.1% | +23% / +36% / -0% | 276 | 47% | +67k | +0k | +38% |
| btc_ret504 | +1.04% (214) | -0.08% (235) | +1.22 | 3/3 | +26% | 34% | +1.53 | +0.81 | +1.01 | +1.3% / +0.0% | -4% / +37% / -4% | 249 | 42% | +26k | +0k | +6% |
| bkt_ret48 | +0.37% (310) | +0.66% (139) | -0.29 | 1/3 | +23% | 32% | +1.40 | +0.72 | +0.97 | +1.4% / -0.6% | -6% / +53% / -14% | 374 | 65% | +24k | +0k | -2% |
| bkt_ret72 | +0.99% (272) | -0.36% (177) | +1.52 | 2/3 | +70% | 32% | +3.07 | +1.43 | +3.11 | +2.9% / -0.0% | +4% / +94% / -16% | 335 | 57% | +71k | +0k | +37% |
| bkt_ret120 | +1.46% (231) | -0.61% (218) | +2.33 | 3/3 | +80% | 26% | +3.35 | +1.64 | +4.28 | +3.1% / +0.6% | +3% / +75% / -0% | 299 | 53% | +79k | +0k | +47% |
| bkt_ret168 | +0.80% (258) | -0.01% (191) | +0.93 | 2/3 | +44% | 30% | +2.30 | +1.15 | +2.04 | +2.1% / +0.8% | +10% / +49% / -12% | 321 | 54% | +46k | +0k | +16% |
| bkt_ret240 | +0.67% (233) | +0.22% (216) | +0.50 | 2/3 | +17% | 33% | +1.19 | +0.63 | +0.66 | +1.3% / +0.0% | -2% / +55% / -23% | 290 | 48% | +18k | +0k | -4% |
| bkt_ret336 | +1.35% (215) | -0.37% (234) | +1.87 | 3/3 | +50% | 27% | +2.56 | +1.26 | +2.54 | +2.4% / -0.1% | -7% / +54% / +5% | 263 | 42% | +51k | +0k | +26% |
| bkt_ret504 | +0.81% (193) | +0.19% (256) | +0.65 | 2/3 | +93% | 27% | +4.08 | +1.94 | +5.07 | +3.1% / +0.0% | +14% / +71% / -1% | 237 | 35% | +93k | +0k | +65% |

Ungated benchmark: total +40.3%, stress +4.2%, max drawdown 43%. EMA gates of 150 h or slower: 16 of 16 beat it on total
return, 16 of 16 at stress costs, 16 of 16 with a smaller drawdown. Fast gates fail: BTC > EMA100 gives 0%, BTC 48 h and 72 h return give -19% and -2%
(the trade-level t is negative: breakouts taken right after a short BTC bounce did worse). Return-sign gates are erratic
(BTC 168 h: +95%, 240 h: +43%, 504 h: +26%), so the EMA form is the one to use. On BTC the plateau is EMA 300 to 960 h:
+79% to +129%, drawdown 18% to 32%, last (worst) third -3% to +21%.

The same gate on other breakout settings (gate = BTC > EMA480):

| setting | ungated: total / stress / thirds | gated: total / stress / thirds | gated Sortino | gated max DD |
|---|---|---|---|---|
| m0.06_t0.04 | +8.0% / -31.3% / +19% / +4% / -12% | +46.1% / +9.9% / +19% / +25% / -2% | +2.45 | 20% |
| m0.06_t0.06 | +39.3% / +2.2% / +8% / +82% / -29% | +118.7% / +82.8% / +26% / +73% / -0% | +4.52 | 20% |
| m0.06_t0.08 | +26.0% / -1.8% / -4% / +124% / -42% | +119.9% / +90.6% / +17% / +97% / -5% | +4.06 | 25% |
| m0.08_t0.04 | +25.6% / -17.5% / +27% / +4% / -5% | +59.5% / +22.1% / +20% / +23% / +8% | +3.47 | 15% |
| m0.08_t0.06 | +40.3% / +4.2% / +12% / +61% / -23% | +106.9% / +73.3% / +23% / +66% / +1% | +4.23 | 19% |
| m0.08_t0.08 | +63.0% / +30.1% / +6% / +132% / -34% | +134.9% / +105.9% / +22% / +92% / +1% | +4.58 | 23% |
| m0.1_t0.04 | +24.5% / -12.0% / +13% / +8% / +2% | +45.2% / +15.8% / +5% / +27% / +9% | +3.20 | 19% |
| m0.1_t0.06 | +54.8% / +19.6% / -5% / +59% / +2% | +61.0% / +37.4% / +1% / +46% / +10% | +3.03 | 19% |
| m0.1_t0.08 | +100.5% / +63.1% / +3% / +99% / -2% | +122.4% / +95.7% / +9% / +82% / +12% | +4.61 | 23% |
| slots3 | +63.8% / +15.7% / -1% / +115% / -23% | +123.8% / +81.7% / +11% / +81% / +11% | +4.27 | 20% |
| slots6 | +22.7% / -3.8% / -6% / +37% / -5% | +41.1% / +21.7% / +4% / +34% / +1% | +2.25 | 16% |
| slots8 | +10.7% / -10.0% / -8% / +27% / -5% | +23.0% / +7.9% / -5% / +20% / +8% | +1.55 | 16% |

The gate improved all 12 settings at default and stress costs. Note the slots row: 3 slots +124%, 4 slots +107%, 6 slots
+41%, 8 slots +23%. The profit sits in the top-ranked breakouts, and in a few coins, as the next table shows.

### 7.2 Concentration: how much of this is two coins?

| book | trade P&L | pairs with a profit | top 5 pairs |
|---|---|---|---|
| ungated | +40,730 | 22/45 | ZEC +28,960, POL +20,471, UNI +20,431, ICP +18,969, TUT +18,806 |
| gated | +107,567 | 23/45 | STO +38,949, TUT +37,611, POL +16,075, ZEN +14,262, 1000CHEEMS +13,513 |

| never trade | ungated: total / stress / thirds | gated: total / stress / thirds |
|---|---|---|
| nothing | +40.3% / +4.2% / +12% / +61% / -23% | +106.9% / +73.3% / +23% / +66% / +1% |
| STO,TUT | +18.5% / -7.8% / +13% / +44% / -27% | +29.8% / +11.8% / +18% / +27% / -14% |
| POL,STO,TUT,UNI,ZEC | -5.2% / -25.3% / +15% / +20% / -31% | +16.9% / +1.3% / +20% / +20% / -19% |

| trade-level test (ungated trade list, state = BTC > EMA480 at entry) | good-market entries: mean (median, n) | bad-market entries | t |
|---|---|---|---|
| all trades | +1.03% (-2.74%, 219) | -0.09% (-2.13%, 230) | +1.24 |
| without STO, TUT | +0.32% (-2.92%, 202) | +0.28% (-1.76%, 203) | +0.04 |
| without top-3 of either book | +0.12% (-2.92%, 184) | -0.35% (-2.05%, 173) | +0.56 |

Reading: the breakout rule is a lottery on a few very large winners (the median trade loses 2 to 3% in both states; only
about half of the 45 pairs traded are profitable). STO and TUT happened to break out while BTC was above its EMA480, and they are 71% of the
gated profit. Remove them and the gate's selection effect is gone (t = 0.0), though the gated book still ends ahead of the
ungated one because it sits out most of the falling third (-14% against -27%). So the honest description of the gate is
"smaller losses in a falling market", worth roughly 10 to 20 points of return over 9 months here, not "+107% against +40%".

### 7.3 Closing positions when the state flips

| family | parameters | mode | signal | total | max DD | Sortino | Sharpe | Calmar | 11d mean / median | thirds | trades | active days | long P&L | short P&L | stress total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brk | BK8_6 | Lg | btc_ema480 | +92% | 20% | +4.00 | +1.87 | +6.64 | +3.3% / +0.0% | +21% / +64% / -3% | 290 | 44% | +92k | +0k | +57% |
| brk | BK8_6 | LgSb | btc_ema480 | +110% | 32% | +3.48 | +1.81 | +4.97 | +3.9% / +1.3% | +9% / +109% / -7% | 573 | 86% | +83k | +28k | +42% |
| brk | BK8_6 | Lg | bkt_ema200 | +48% | 26% | +2.44 | +1.20 | +2.56 | +2.4% / +0.0% | -1% / +67% / -10% | 389 | 53% | +48k | +0k | +15% |
| brk | BK8_6 | Lg | btc_ret7d | +72% | 22% | +3.43 | +1.71 | +4.70 | +2.7% / +0.0% | +20% / +40% / +2% | 335 | 50% | +72k | +0k | +36% |
| ema | E24_200_s6 | LgSb | bkt_ema100 | -29% | 51% | -0.64 | -0.42 | -0.70 | -0.8% / -1.4% | +20% / -20% / -26% | 809 | 75% | -25k | -3k | -59% |
| ema | E24_200_s6 | LgSb | btc_ema480 | +30% | 29% | +1.48 | +0.88 | +1.39 | +1.5% / +0.5% | +11% / +37% / -14% | 522 | 75% | -20k | +48k | -9% |
| ema | E48_200_s5 | LgSb | btc_ret7d | +59% | 37% | +2.47 | +1.27 | +2.22 | +2.4% / -0.2% | +7% / +66% / -10% | 564 | 80% | +47k | +12k | +7% |
| ema | E24_200_s6 | Sb | btc_ema200 | +21% | 20% | +1.43 | +0.78 | +1.36 | +1.1% / -0.9% | -6% / +40% / -8% | 380 | 53% | +0k | +21k | -6% |

Force-closing on a flip was worse than letting positions leave by their own exits in 8 of 8 cases (for example breakout Lg
with BTC > EMA480: +92% against +107%; EMA 24/200 team rule with basket > EMA100: -29% against +117%). The signals flip too often.

## 8. What failed

- Predicting the basket's direction with any of the 9 signals (section 3).
- The 2-state HMM as a direction signal: anti-predictive, and every strategy did better with it reversed.
- Z-score shorts under every direction rule (0 of 78 variants with shorts made money).
- The mirrored breakdown short: 0 of 16 settings profitable alone; as the bad-market leg it lowered Sortino and Calmar.
- EMA-cross longs with a direction gate: the gate made them worse (real signal better than reversed for 1 of 8).
- Timing shorts with the direction signal: no better than the reversed signal, worse than always-on.
- Timing the BTC hedge with the signal; sizing the hedge to the long book; flattening on a flip.
- Fast gates (EMA100, 48 h and 72 h returns) on breakout longs.
- The first combo test (concentrated sizing): discarded as an artefact, replaced by section 4.3.

## 9. Recommendation, plateau and the three filed candidates

| metric | benchmark_breakout | candidate_1 | candidate_2 | candidate_3 |
|---|---|---|---|---|
| total | +40.3% | +106.9% | +84.0% | +130.1% |
| max DD | 43.4% | 18.8% | 12.8% | 21.7% |
| Sortino / Sharpe / Calmar | +1.91 / +0.96 / +1.27 | +4.23 / +2.04 / +8.29 | +4.84 / +2.42 / +9.40 | +4.36 / +2.19 / +8.95 |
| 11d mean / median | +2.11% / -0.61% | +3.57% / +0.31% | +2.85% / +1.76% | +4.00% / +2.38% |
| 11d >= +10% / <= -10% | 23% / 12% | 19% / 3% | 11% / 0% | 17% / 4% |
| worst 11d | -19.6% | -13.9% | -9.3% | -16.1% |
| thirds | +12% / +61% / -23% | +23% / +66% / +1% | +14% / +47% / +9% | +20% / +80% / +6% |
| trades | 449 | 256 | 259 | 381 |
| win rate | 36% | 38% | 39% | 38% |
| turnover | 351x | 190x | 115x | 296x |
| fees $ | 35,112 | 18,999 | 11,470 | 29,634 |
| days with a fill | 80% | 45% | 46% | 75% |
| 14d windows with >= 8 active days | 95% (min 6) | 41% (min 0) | 41% (min 0) | 86% (min 5) |
| long / short P&L | +41k / +0k | +108k / +0k | +65k / +21k | +107k / +24k |
| P&L by third (long, short) | +12k, +0k ; +69k, +0k ; -41k, +0k | +23k, +0k ; +81k, +0k ; +3k, +0k | +16k, +0k ; +47k, +9k ; +2k, +13k | +21k, -2k ; +71k, +27k ; +14k, -1k |
| stress total | +4.2% | +73.3% | +62.9% | +75.1% |
| stress thirds | +1% / +44% / -28% | +12% / +57% / -2% | +8% / +43% / +6% | +8% / +63% / -1% |
| stress Sortino / Sharpe / Calmar | +0.74 / +0.39 / +0.11 | +3.16 / +1.60 / +5.02 | +3.75 / +1.97 / +6.31 | +2.93 / +1.55 / +3.92 |
| stress max DD | 48.7% | 20.6% | 13.9% | 27.1% |
| stress 11d mean / median | +0.92% / -1.60% | +2.85% / +0.00% | +2.38% / +1.42% | +2.90% / +1.49% |
| stress long / short P&L | +5k / +0k | +74k / +0k | +47k / +23k | +72k / +4k |
| fresh-start 11d windows: mean / median / win | +2.57% / +0.46% / 54% | +3.53% / +0.00% / 49% | +2.81% / +1.57% / 69% | +3.92% / +1.64% / 60% |
| alpha per 11d vs basket | +2.71% (t +1.34), beta +0.46 | +3.67% (t +2.20), beta +0.27 | +2.61% (t +2.19), beta +0.04 | +3.81% (t +1.99), beta +0.07 |
| 11d blocks: basket rose / fell | +6.41% / -0.40% | +5.08% / +2.56% | +2.84% / +2.64% | +3.67% / +4.00% |
| 30d blocks positive | 6/9 | 6/9 | 7/9 | 7/9 |
| without STO, TUT: total / stress / thirds | +18.5% / -7.8% / +13% / +44% / -27% | +29.8% / +11.8% / +18% / +27% / -14% | +37.0% / +22.5% / +11% / +24% / -1% | +41.6% / +11.7% / +17% / +34% / -10% |
| look-ahead check | not run | True | True | True |

All P&L by tag: benchmark and candidate 1 are 100% `breakout` exits by signal. Candidate 2: breakout +65k (256 trades),
hedge +21k (3 closed round trips). Candidate 3: breakout +107k (251), ema shorts +24k (130);
by exit reason: signal +59k (284), stop +72k (97).

**Direction rule recommended:** the market is "good" while BTC's hourly close is above its 480-hour EMA. Use it to allow or block
new long entries. Do not force-close on a flip. Do not use it to switch to shorts.
**Plateau:** BTC EMA 300 to 960 h (+79% to +129%, drawdown 18 to 32%, all thirds >= -3%); basket EMA 150 to 960 h also works
(+50% to +78%, weaker in the first third). 480 is the middle of the BTC plateau, not the best value (720 was).

1. `candidate_1.py`: breakout longs in good markets, cash in bad ones. The answer to "what direction rule". Weak edge;
   two-coin concentration; fills on only 45% of days.
2. `candidate_2.py`: candidate 1 at 67% size plus a standing 33% BTC short. Best ratios on this sample (Sortino 4.8, Sharpe 2.4,
   Calmar 9.4, no 11-day window below -10%) and the only one positive in all three thirds at stress costs, but the hedge's
   contribution is BTC's 32% fall. Choose it only as a deliberate view that BTC will not rally.
3. `candidate_3.py`: the team's rule in its least-bad form (breakout longs in good markets, EMA 24/200 shorts with a 6-ATR
   stop in bad markets, at most 2 of 4 slots). Filed because the team asked for it and because it keeps the account active
   (fills on 75% of days). Its short leg is **not** a proven edge: +$24k at default costs, +$4k at stress costs, all from one
   third, and negative with one short slot.

## 10. What would have to be true for shorts to work

- The next 11 days would have to look like the middle third of the design period (a steady fall with weak bounces). In the
  rising third and in the choppy last third the gated short leg lost money even though the basket fell 35% in the last one.
- Real short costs would have to be at the default level (10 bp each way and a 1.2 bp half-spread), not the stress level;
  at stress costs the short leg's profit is $4k on $100k over 9 months.
- A direction signal that actually forecasts would be needed to time shorts. None of the nine does.

## 11. Caveats

- One 9-month sample that is 2/3 bear market. Every short result is flattered by it and every long result is hurt by it.
- 517 variants were tried in this track; the three candidates are the survivors, so their design numbers are optimistic.
  The gate was chosen among 41 (9 + 32), the short leg among 3 families.
- The long book's profit is a handful of coins; expect any 11-day window to be near zero or negative unless one of those
  moves happens (median 11-day return of candidate 1: +0.3%, of fresh-start windows: 0.0%).
- Stops and covers are modelled as market orders after a one-minute poll; short fills at the bid with the measured spread.
  Borrow limits, funding or a short ban on small coins on the real exchange are not modelled.
- The HMM here uses basket return and volatility only (as briefed); the paper's per-coin model is another track's subject.

## Appendix A. Every stage-2 row (291 runs)

Modes: L / S / B always long / short / both; Lg long only in good; Sb short only in bad; LgSb both (team rule); Lb / Sg / LbSg the same with the signal reversed.

| family | parameters | mode | signal | total | max DD | Sortino | Sharpe | Calmar | 11d mean / median | thirds | trades | active days | long P&L | short P&L | stress total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brk | BK8_6 | L | - | +40% | 43% | +1.91 | +0.96 | +1.27 | +2.1% / -0.6% | +12% / +61% / -23% | 449 | 80% | +41k | +0k | +4% |
| brk | BK8_6 | S | - | -20% | 44% | -0.63 | -0.41 | -0.57 | -0.8% / -1.6% | -27% / +7% / +3% | 329 | 71% | +0k | -20k | -36% |
| brk | BK8_6 | B | - | +49% | 43% | +1.91 | +1.05 | +1.55 | +2.3% / +0.1% | -11% / +81% / -7% | 697 | 92% | +54k | -6k | -6% |
| brk | BK8_6 | Lg | btc_ema100 | -0% | 36% | +0.46 | +0.25 | -0.00 | +0.6% / -0.6% | +14% / +7% / -18% | 342 | 63% | +0k | +0k | -20% |
| brk | BK8_6 | Sb | btc_ema100 | -8% | 41% | -0.08 | -0.05 | -0.24 | -0.3% / -1.8% | -23% / +15% / +4% | 298 | 61% | +0k | -8k | -25% |
| brk | BK8_6 | LgSb | btc_ema100 | -11% | 46% | +0.08 | +0.05 | -0.30 | +0.1% / -0.8% | -14% / +11% / -6% | 606 | 91% | -5k | -5k | -41% |
| brk | BK8_6 | Lb | btc_ema100 | +56% | 28% | +3.25 | +1.38 | +2.76 | +2.2% / -0.9% | -6% / +97% / -16% | 190 | 48% | +56k | +0k | +37% |
| brk | BK8_6 | Sg | btc_ema100 | -20% | 24% | -1.54 | -1.24 | -1.02 | -0.8% / -0.1% | -2% / -9% / -10% | 69 | 25% | +0k | -20k | -24% |
| brk | BK8_6 | LbSg | btc_ema100 | +25% | 32% | +1.56 | +0.79 | +1.05 | +1.5% / -0.7% | -10% / +79% / -23% | 258 | 67% | +54k | -29k | +4% |
| brk | BK8_6 | Lg | btc_ema200 | +53% | 28% | +2.42 | +1.22 | +2.63 | +2.5% / +0.0% | +15% / +52% / -12% | 331 | 57% | +53k | +0k | +23% |
| brk | BK8_6 | Sb | btc_ema200 | +5% | 29% | +0.59 | +0.36 | +0.22 | +0.3% / -1.1% | -16% / +22% / +3% | 283 | 57% | +0k | +5k | -14% |
| brk | BK8_6 | LgSb | btc_ema200 | +55% | 39% | +2.13 | +1.17 | +1.92 | +2.7% / +1.0% | -10% / +78% / -3% | 594 | 90% | +39k | +16k | +4% |
| brk | BK8_6 | Lb | btc_ema200 | +9% | 31% | +0.95 | +0.46 | +0.39 | +0.6% / -1.7% | -4% / +38% / -17% | 205 | 53% | +9k | +0k | -4% |
| brk | BK8_6 | Sg | btc_ema200 | +1% | 28% | +0.45 | +0.23 | +0.06 | +0.2% / +0.0% | -12% / +19% / -3% | 102 | 32% | +0k | +1k | -6% |
| brk | BK8_6 | LbSg | btc_ema200 | -2% | 34% | +0.48 | +0.25 | -0.06 | +0.3% / -1.4% | -16% / +45% / -19% | 302 | 74% | -3k | +2k | -20% |
| brk | BK8_6 | Lg | btc_ema480 | +107% | 19% | +4.23 | +2.04 | +8.29 | +3.6% / +0.3% | +23% / +66% / +1% | 256 | 45% | +108k | +0k | +73% |
| brk | BK8_6 | Sb | btc_ema480 | +3% | 27% | +0.46 | +0.28 | +0.13 | +0.2% / -0.4% | -17% / +23% / +0% | 265 | 53% | +0k | +3k | -14% |
| brk | BK8_6 | LgSb | btc_ema480 | +131% | 34% | +3.81 | +2.00 | +5.75 | +4.2% / +1.8% | +4% / +108% / +7% | 509 | 84% | +97k | +33k | +62% |
| brk | BK8_6 | Lb | btc_ema480 | -14% | 42% | -0.37 | -0.20 | -0.43 | -0.4% / -0.8% | +5% / +6% / -23% | 239 | 53% | -14k | +0k | -26% |
| brk | BK8_6 | Sg | btc_ema480 | -10% | 33% | -0.33 | -0.17 | -0.38 | -0.3% / +0.0% | -17% / +8% / +1% | 103 | 29% | +0k | -10k | -16% |
| brk | BK8_6 | LbSg | btc_ema480 | -27% | 45% | -0.66 | -0.36 | -0.73 | -1.0% / -3.5% | -14% / +11% / -23% | 340 | 75% | -13k | -13k | -41% |
| brk | BK8_6 | Lg | bkt_ema100 | +60% | 34% | +2.51 | +1.21 | +2.44 | +2.7% / -0.4% | +3% / +91% / -19% | 387 | 65% | +60k | +0k | +24% |
| brk | BK8_6 | Sb | bkt_ema100 | +1% | 34% | +0.41 | +0.26 | +0.05 | +0.2% / -1.2% | -18% / +22% / +1% | 305 | 61% | +0k | +1k | -18% |
| brk | BK8_6 | LgSb | bkt_ema100 | +79% | 41% | +2.69 | +1.35 | +2.72 | +3.3% / +0.8% | -11% / +114% / -7% | 653 | 90% | +62k | +17k | +15% |
| brk | BK8_6 | Lb | bkt_ema100 | +36% | 25% | +2.90 | +1.23 | +2.00 | +1.4% / -0.4% | +2% / +47% / -9% | 130 | 44% | +36k | +0k | +24% |
| brk | BK8_6 | Sg | bkt_ema100 | +7% | 17% | +0.81 | +0.44 | +0.53 | +0.4% / +0.0% | -10% / +15% / +3% | 51 | 20% | +0k | +7k | +3% |
| brk | BK8_6 | LbSg | bkt_ema100 | +44% | 26% | +2.63 | +1.22 | +2.31 | +1.8% / -0.3% | -7% / +66% / -7% | 181 | 57% | +29k | +15k | +26% |
| brk | BK8_6 | Lg | bkt_ema200 | +78% | 27% | +3.27 | +1.53 | +4.07 | +3.2% / +0.0% | +2% / +88% / -7% | 343 | 57% | +80k | +0k | +43% |
| brk | BK8_6 | Sb | bkt_ema200 | +4% | 38% | +0.54 | +0.32 | +0.12 | +0.3% / -1.2% | -21% / +30% / +1% | 300 | 61% | +0k | +4k | -16% |
| brk | BK8_6 | LgSb | bkt_ema200 | +76% | 44% | +2.63 | +1.40 | +2.46 | +3.5% / +1.6% | -21% / +134% / -4% | 625 | 89% | +61k | +16k | +16% |
| brk | BK8_6 | Lb | bkt_ema200 | -18% | 38% | -0.76 | -0.44 | -0.59 | -0.7% / -1.6% | +9% / -4% / -21% | 194 | 52% | -18k | +0k | -28% |
| brk | BK8_6 | Sg | bkt_ema200 | -14% | 24% | -0.89 | -0.45 | -0.76 | -0.4% / +0.0% | -13% / +7% / -8% | 65 | 23% | +0k | -14k | -18% |
| brk | BK8_6 | LbSg | bkt_ema200 | -28% | 47% | -1.05 | -0.58 | -0.74 | -1.2% / -2.8% | -6% / +3% / -26% | 256 | 66% | -16k | -12k | -40% |
| brk | BK8_6 | Lg | bkt_ema480 | +52% | 21% | +2.62 | +1.30 | +3.39 | +2.4% / +0.0% | -1% / +66% / -8% | 267 | 39% | +54k | +0k | +27% |
| brk | BK8_6 | Sb | bkt_ema480 | +19% | 29% | +1.33 | +0.77 | +0.89 | +0.7% / +0.0% | -13% / +22% / +13% | 269 | 57% | +0k | +19k | -1% |
| brk | BK8_6 | LgSb | bkt_ema480 | +66% | 37% | +2.37 | +1.33 | +2.48 | +2.9% / +1.8% | -21% / +99% / +5% | 533 | 85% | +32k | +36k | +15% |
| brk | BK8_6 | Lb | bkt_ema480 | -11% | 41% | -0.14 | -0.08 | -0.33 | -0.2% / -0.4% | +13% / +4% / -24% | 242 | 56% | -11k | +0k | -24% |
| brk | BK8_6 | Sg | bkt_ema480 | -22% | 33% | -1.39 | -0.75 | -0.81 | -0.8% / +0.0% | -20% / +9% / -10% | 80 | 20% | +0k | -22k | -26% |
| brk | BK8_6 | LbSg | bkt_ema480 | -30% | 47% | -0.87 | -0.48 | -0.78 | -1.1% / -3.5% | -10% / +14% / -31% | 322 | 74% | -7k | -23k | -43% |
| brk | BK8_6 | Lg | breadth | +20% | 25% | +1.38 | +0.71 | +1.11 | +1.2% / +0.0% | +10% / +16% / -6% | 279 | 45% | +21k | +0k | +1% |
| brk | BK8_6 | Sb | breadth | -2% | 37% | +0.24 | +0.15 | -0.07 | +0.0% / -1.3% | -21% / +25% / -1% | 302 | 63% | +0k | -2k | -20% |
| brk | BK8_6 | LgSb | breadth | +21% | 38% | +1.19 | +0.69 | +0.72 | +1.2% / +0.9% | -16% / +48% / -3% | 567 | 86% | +19k | +2k | -17% |
| brk | BK8_6 | Lb | breadth | +46% | 35% | +2.46 | +1.15 | +1.81 | +1.9% / -0.3% | +4% / +78% / -21% | 249 | 62% | +46k | +0k | +24% |
| brk | BK8_6 | Sg | breadth | -24% | 29% | -2.17 | -1.80 | -1.05 | -1.0% / +0.0% | -9% / -11% / -7% | 54 | 20% | +0k | -24k | -27% |
| brk | BK8_6 | LbSg | breadth | +13% | 35% | +1.03 | +0.55 | +0.48 | +0.9% / -1.0% | -5% / +58% / -24% | 300 | 72% | +45k | -32k | -8% |
| brk | BK8_6 | Lg | btc_ret7d | +95% | 22% | +3.97 | +1.83 | +6.27 | +3.3% / +0.7% | +27% / +61% / -5% | 280 | 53% | +94k | +0k | +61% |
| brk | BK8_6 | Sb | btc_ret7d | -6% | 24% | -0.06 | -0.04 | -0.31 | -0.1% / -0.5% | -10% / +10% / -5% | 252 | 50% | +0k | -6k | -21% |
| brk | BK8_6 | LgSb | btc_ret7d | +92% | 30% | +3.17 | +1.62 | +4.42 | +3.4% / +1.6% | +17% / +74% / -6% | 518 | 85% | +83k | +8k | +34% |
| brk | BK8_6 | Lb | btc_ret7d | -9% | 36% | +0.02 | +0.01 | -0.32 | +0.1% / -2.0% | -11% / +29% / -21% | 245 | 53% | -9k | +0k | -22% |
| brk | BK8_6 | Sg | btc_ret7d | -13% | 33% | -0.53 | -0.28 | -0.51 | -0.4% / -0.4% | -20% / +13% / -5% | 130 | 37% | +0k | -13k | -21% |
| brk | BK8_6 | LbSg | btc_ret7d | -14% | 36% | -0.05 | -0.03 | -0.51 | -0.2% / -3.1% | -22% / +40% / -21% | 367 | 76% | -1k | -13k | -33% |
| brk | BK8_6 | Lg | hmm2 | -36% | 47% | -1.70 | -0.98 | -0.92 | -1.5% / -2.5% | -13% / -10% / -17% | 252 | 48% | -35k | +0k | -45% |
| brk | BK8_6 | Sb | hmm2 | -15% | 34% | -0.47 | -0.25 | -0.54 | -0.4% / -1.2% | -20% / +2% / +4% | 152 | 37% | +0k | -15k | -24% |
| brk | BK8_6 | LgSb | hmm2 | -43% | 56% | -1.48 | -0.85 | -0.92 | -1.8% / -3.4% | -29% / -8% / -13% | 392 | 73% | -29k | -14k | -56% |
| brk | BK8_6 | Lb | hmm2 | +66% | 24% | +3.29 | +1.55 | +3.87 | +2.6% / -0.0% | +13% / +67% / -12% | 266 | 52% | +66k | +0k | +40% |
| brk | BK8_6 | Sg | hmm2 | -2% | 30% | +0.15 | +0.09 | -0.10 | -0.1% / -0.1% | -24% / +24% / +3% | 234 | 48% | +0k | -2k | -16% |
| brk | BK8_6 | LbSg | hmm2 | +76% | 29% | +2.98 | +1.52 | +3.67 | +2.9% / +0.9% | -11% / +108% / -5% | 489 | 84% | +60k | +17k | +29% |
| ema | E24_100_s3 | L | - | -20% | 50% | -0.34 | -0.19 | -0.51 | -0.3% / -2.5% | +12% / -18% / -14% | 768 | 93% | -21k | +0k | -57% |
| ema | E24_100_s3 | S | - | +24% | 24% | +1.55 | +0.83 | +1.35 | +1.1% / +0.3% | +11% / +22% / -8% | 669 | 91% | +0k | +23k | -27% |
| ema | E24_100_s3 | B | - | +17% | 54% | +1.05 | +0.63 | +0.41 | +1.4% / +0.4% | +42% / -6% / -12% | 1180 | 97% | -2k | +19k | -54% |
| ema | E24_100_s3 | Lg | btc_ema100 | -6% | 46% | +0.03 | +0.02 | -0.17 | +0.2% / -1.0% | +14% / -21% / +4% | 529 | 68% | -7k | +0k | -38% |
| ema | E24_100_s3 | Sb | btc_ema100 | +26% | 22% | +1.72 | +0.92 | +1.59 | +1.0% / -0.2% | +5% / +22% / -2% | 492 | 71% | +0k | +26k | -16% |
| ema | E24_100_s3 | LgSb | btc_ema100 | +8% | 50% | +0.73 | +0.44 | +0.21 | +0.8% / -0.2% | +21% / -7% / -4% | 966 | 96% | -14k | +22k | -50% |
| ema | E24_100_s3 | Lg | btc_ema200 | -4% | 41% | +0.16 | +0.09 | -0.12 | +0.3% / -1.2% | +10% / -6% / -7% | 501 | 62% | -4k | +0k | -35% |
| ema | E24_100_s3 | Sb | btc_ema200 | +33% | 25% | +2.15 | +1.16 | +1.79 | +1.1% / +0.0% | +18% / +20% / -6% | 455 | 67% | +0k | +33k | -8% |
| ema | E24_100_s3 | LgSb | btc_ema200 | +41% | 48% | +1.87 | +1.05 | +1.19 | +1.9% / +1.5% | +42% / +12% / -11% | 906 | 94% | +11k | +30k | -32% |
| ema | E24_100_s3 | Lg | btc_ema480 | +18% | 31% | +1.24 | +0.69 | +0.76 | +1.0% / +0.0% | +18% / +6% / -6% | 377 | 49% | +17k | +0k | -13% |
| ema | E24_100_s3 | Sb | btc_ema480 | +29% | 22% | +1.98 | +1.05 | +1.81 | +1.1% / +0.0% | +13% / +23% / -7% | 451 | 64% | +0k | +29k | -9% |
| ema | E24_100_s3 | LgSb | btc_ema480 | +40% | 36% | +1.86 | +1.06 | +1.51 | +2.0% / +1.1% | +26% / +24% / -11% | 798 | 94% | +6k | +34k | -26% |
| ema | E24_100_s3 | Lg | bkt_ema100 | -22% | 39% | -0.88 | -0.51 | -0.71 | -0.5% / -1.1% | -0% / -8% / -16% | 542 | 67% | -23k | +0k | -49% |
| ema | E24_100_s3 | Sb | bkt_ema100 | +41% | 27% | +2.52 | +1.26 | +2.07 | +1.6% / +0.1% | +14% / +37% / -10% | 511 | 72% | +0k | +41k | -7% |
| ema | E24_100_s3 | LgSb | bkt_ema100 | +33% | 36% | +1.60 | +0.91 | +1.25 | +2.0% / +0.6% | +22% / +33% / -18% | 972 | 96% | -5k | +38k | -39% |
| ema | E24_100_s3 | Lg | bkt_ema200 | +18% | 32% | +1.22 | +0.68 | +0.72 | +1.1% / +0.0% | +17% / -10% / +11% | 444 | 58% | +18k | +0k | -18% |
| ema | E24_100_s3 | Sb | bkt_ema200 | +31% | 24% | +2.07 | +1.09 | +1.78 | +1.3% / +0.0% | +15% / +25% / -8% | 495 | 72% | +0k | +31k | -12% |
| ema | E24_100_s3 | LgSb | bkt_ema200 | +74% | 30% | +2.75 | +1.57 | +3.50 | +2.9% / +1.9% | +44% / +19% / +1% | 897 | 95% | +34k | +40k | -16% |
| ema | E24_100_s3 | Lg | bkt_ema480 | +14% | 24% | +1.07 | +0.62 | +0.78 | +1.0% / +0.0% | +10% / +13% / -8% | 318 | 43% | +14k | +0k | -13% |
| ema | E24_100_s3 | Sb | bkt_ema480 | +32% | 20% | +2.10 | +1.10 | +2.14 | +1.2% / +0.0% | +15% / +21% / -6% | 494 | 68% | +0k | +31k | -11% |
| ema | E24_100_s3 | LgSb | bkt_ema480 | +45% | 29% | +2.04 | +1.15 | +2.16 | +2.0% / +0.6% | +20% / +39% / -14% | 803 | 94% | +11k | +33k | -25% |
| ema | E24_100_s3 | Lg | breadth | +10% | 32% | +0.92 | +0.52 | +0.42 | +0.7% / +0.0% | +26% / +2% / -14% | 356 | 47% | +10k | +0k | -17% |
| ema | E24_100_s3 | Sb | breadth | +33% | 24% | +2.13 | +1.07 | +1.84 | +1.2% / -0.5% | +10% / +28% / -6% | 540 | 75% | +0k | +33k | -14% |
| ema | E24_100_s3 | LgSb | breadth | +69% | 29% | +2.75 | +1.48 | +3.38 | +2.6% / +2.0% | +49% / +43% / -20% | 867 | 93% | +27k | +42k | -16% |
| ema | E24_100_s3 | Lg | btc_ret7d | +2% | 45% | +0.48 | +0.27 | +0.05 | +0.4% / -1.5% | +13% / -8% / -2% | 462 | 59% | +1k | +0k | -30% |
| ema | E24_100_s3 | Sb | btc_ret7d | +24% | 23% | +1.76 | +0.94 | +1.40 | +0.9% / -0.1% | +21% / +17% / -13% | 407 | 63% | +0k | +24k | -10% |
| ema | E24_100_s3 | LgSb | btc_ret7d | +27% | 51% | +1.45 | +0.83 | +0.70 | +1.4% / +0.1% | +39% / +8% / -15% | 822 | 92% | -6k | +32k | -34% |
| ema | E24_100_s3 | Lg | hmm2 | -34% | 45% | -1.61 | -0.91 | -0.93 | -1.2% / -1.8% | -15% / -15% / -9% | 434 | 54% | -34k | +0k | -53% |
| ema | E24_100_s3 | Sb | hmm2 | -1% | 22% | +0.17 | +0.09 | -0.09 | +0.2% / -0.4% | -7% / +6% / +1% | 374 | 60% | +0k | -1k | -29% |
| ema | E24_100_s3 | LgSb | hmm2 | -31% | 52% | -1.07 | -0.61 | -0.74 | -0.8% / -2.9% | -14% / -12% / -9% | 785 | 94% | -31k | -1k | -64% |
| ema | E24_200_s6 | L | - | +4% | 45% | +0.71 | +0.40 | +0.13 | +0.8% / -2.3% | +7% / +11% / -12% | 349 | 80% | +3k | +0k | -20% |
| ema | E24_200_s6 | S | - | +87% | 21% | +3.50 | +1.85 | +5.80 | +3.1% / +2.6% | +12% / +47% / +13% | 311 | 73% | +0k | +87k | +48% |
| ema | E24_200_s6 | B | - | +59% | 25% | +2.13 | +1.24 | +3.25 | +2.2% / +1.4% | +12% / +45% / -2% | 430 | 73% | +14k | +39k | +17% |
| ema | E24_200_s6 | Lg | btc_ema100 | -22% | 46% | -0.59 | -0.37 | -0.59 | -0.6% / -2.7% | +6% / -22% / -5% | 251 | 61% | -23k | +0k | -35% |
| ema | E24_200_s6 | Sb | btc_ema100 | +57% | 17% | +2.72 | +1.51 | +4.54 | +2.0% / +1.2% | +11% / +27% / +11% | 243 | 61% | +0k | +53k | +30% |
| ema | E24_200_s6 | LgSb | btc_ema100 | +6% | 28% | +0.64 | +0.39 | +0.28 | +0.6% / -0.4% | +7% / -3% / +2% | 400 | 75% | -33k | +35k | -22% |
| ema | E24_200_s6 | Lb | btc_ema100 | +20% | 36% | +1.26 | +0.67 | +0.74 | +1.4% / -1.3% | +14% / +14% / -8% | 224 | 63% | +18k | +0k | +1% |
| ema | E24_200_s6 | Sg | btc_ema100 | +43% | 22% | +2.50 | +1.38 | +2.74 | +1.8% / +1.4% | +13% / +25% / +2% | 215 | 58% | +0k | +44k | +22% |
| ema | E24_200_s6 | LbSg | btc_ema100 | +59% | 22% | +2.51 | +1.33 | +3.75 | +2.4% / +2.0% | +11% / +25% / +15% | 338 | 81% | +3k | +55k | +23% |
| ema | E24_200_s6 | Lg | btc_ema200 | -22% | 42% | -0.63 | -0.40 | -0.66 | -0.7% / -2.6% | +0% / -14% / -10% | 240 | 54% | -24k | +0k | -35% |
| ema | E24_200_s6 | Sb | btc_ema200 | +100% | 15% | +4.43 | +2.10 | +9.62 | +3.1% / +1.2% | +16% / +64% / +5% | 219 | 55% | +0k | +95k | +70% |
| ema | E24_200_s6 | LgSb | btc_ema200 | +25% | 32% | +1.36 | +0.76 | +1.05 | +1.5% / -0.5% | +12% / +30% / -14% | 402 | 73% | -40k | +60k | -7% |
| ema | E24_200_s6 | Lb | btc_ema200 | -8% | 40% | +0.14 | +0.07 | -0.26 | +0.3% / -1.7% | -2% / +7% / -13% | 230 | 61% | -10k | +0k | -23% |
| ema | E24_200_s6 | Sg | btc_ema200 | +54% | 19% | +3.03 | +1.60 | +3.88 | +2.1% / +2.2% | +12% / +34% / +3% | 199 | 54% | +0k | +55k | +33% |
| ema | E24_200_s6 | LbSg | btc_ema200 | +52% | 19% | +2.28 | +1.20 | +3.71 | +2.3% / +1.5% | +8% / +29% / +10% | 346 | 78% | -15k | +66k | +18% |
| ema | E24_200_s6 | Lg | btc_ema480 | -11% | 27% | -0.23 | -0.15 | -0.52 | -0.3% / +0.0% | -3% / +6% / -13% | 186 | 43% | -12k | +0k | -23% |
| ema | E24_200_s6 | Sb | btc_ema480 | +50% | 21% | +2.64 | +1.38 | +3.37 | +1.9% / +0.0% | +1% / +41% / +6% | 231 | 55% | +0k | +46k | +26% |
| ema | E24_200_s6 | LgSb | btc_ema480 | +40% | 22% | +1.71 | +1.04 | +2.47 | +1.6% / +0.5% | -3% / +38% / +4% | 369 | 73% | -14k | +48k | +6% |
| ema | E24_200_s6 | Lb | btc_ema480 | +14% | 43% | +1.04 | +0.56 | +0.44 | +1.2% / -0.5% | +2% / +19% / -5% | 238 | 59% | +12k | +0k | -4% |
| ema | E24_200_s6 | Sg | btc_ema480 | +49% | 19% | +3.29 | +1.67 | +3.57 | +1.9% / +0.0% | +12% / +28% / +5% | 148 | 40% | +0k | +50k | +33% |
| ema | E24_200_s6 | LbSg | btc_ema480 | +99% | 38% | +3.20 | +1.66 | +3.80 | +3.8% / +1.4% | +8% / +67% / +10% | 344 | 76% | +28k | +68k | +54% |
| ema | E24_200_s6 | Lg | bkt_ema100 | +32% | 34% | +1.59 | +0.84 | +1.30 | +1.8% / -0.9% | +1% / +26% / +4% | 262 | 61% | +32k | +0k | +9% |
| ema | E24_200_s6 | Sb | bkt_ema100 | +112% | 16% | +4.41 | +2.25 | +10.29 | +3.3% / +2.0% | +12% / +66% / +14% | 236 | 59% | +0k | +107k | +77% |
| ema | E24_200_s6 | LgSb | bkt_ema100 | +117% | 23% | +3.44 | +1.85 | +7.50 | +3.7% / +1.5% | +2% / +78% / +20% | 398 | 74% | +32k | +77k | +61% |
| ema | E24_200_s6 | Lb | bkt_ema100 | +6% | 35% | +0.64 | +0.38 | +0.23 | +0.5% / -0.7% | +20% / -4% / -8% | 239 | 66% | +4k | +0k | -11% |
| ema | E24_200_s6 | Sg | bkt_ema100 | +53% | 20% | +3.14 | +1.71 | +3.67 | +2.0% / +1.8% | -1% / +33% / +17% | 186 | 53% | +0k | +54k | +33% |
| ema | E24_200_s6 | LbSg | bkt_ema100 | +52% | 22% | +2.19 | +1.29 | +3.18 | +2.0% / +1.6% | +2% / +44% / +3% | 321 | 79% | +5k | +45k | +20% |
| ema | E24_200_s6 | Lg | bkt_ema200 | -11% | 34% | -0.04 | -0.02 | -0.41 | +0.1% / -1.5% | -2% / +5% / -14% | 232 | 51% | -11k | +0k | -26% |
| ema | E24_200_s6 | Sb | bkt_ema200 | +51% | 21% | +2.55 | +1.28 | +3.28 | +2.1% / +0.1% | +0% / +56% / -4% | 244 | 58% | +0k | +47k | +25% |
| ema | E24_200_s6 | LgSb | bkt_ema200 | +29% | 36% | +1.47 | +0.81 | +1.06 | +1.9% / -0.5% | -7% / +58% / -12% | 410 | 73% | -16k | +41k | -5% |
| ema | E24_200_s6 | Lb | bkt_ema200 | +40% | 41% | +1.83 | +0.97 | +1.34 | +2.0% / -0.2% | +12% / +37% / -9% | 245 | 67% | +37k | +0k | +17% |
| ema | E24_200_s6 | Sg | bkt_ema200 | +55% | 19% | +3.21 | +1.75 | +4.00 | +2.1% / +1.3% | +6% / +37% / +6% | 178 | 48% | +0k | +55k | +35% |
| ema | E24_200_s6 | LbSg | bkt_ema200 | +82% | 32% | +2.78 | +1.52 | +3.70 | +3.2% / +1.5% | +9% / +76% / -5% | 344 | 77% | +14k | +67k | +41% |
| ema | E24_200_s6 | Lg | bkt_ema480 | -15% | 40% | -0.40 | -0.26 | -0.47 | -0.3% / -0.7% | +19% / -8% / -23% | 164 | 36% | -14k | +0k | -26% |
| ema | E24_200_s6 | Sb | bkt_ema480 | +27% | 28% | +1.70 | +0.92 | +1.32 | +1.4% / +0.0% | -3% / +26% / +5% | 235 | 55% | +0k | +28k | +7% |
| ema | E24_200_s6 | LgSb | bkt_ema480 | -1% | 32% | +0.42 | +0.26 | -0.05 | +0.3% / -0.6% | +10% / -2% / -9% | 379 | 71% | -25k | +22k | -26% |
| ema | E24_200_s6 | Lb | bkt_ema480 | +22% | 42% | +1.24 | +0.68 | +0.69 | +1.3% / -0.9% | +9% / +24% / -10% | 252 | 62% | +18k | +0k | +1% |
| ema | E24_200_s6 | Sg | bkt_ema480 | +57% | 19% | +3.72 | +1.80 | +4.16 | +2.0% / +0.0% | +3% / +43% / +6% | 137 | 36% | +0k | +57k | +41% |
| ema | E24_200_s6 | LbSg | bkt_ema480 | +91% | 32% | +2.95 | +1.53 | +4.13 | +3.3% / +0.8% | -3% / +97% / +0% | 336 | 77% | +9k | +75k | +48% |
| ema | E24_200_s6 | Lg | breadth | -19% | 36% | -0.70 | -0.46 | -0.68 | -0.7% / -1.6% | +1% / -10% / -11% | 191 | 42% | -20k | +0k | -30% |
| ema | E24_200_s6 | Sb | breadth | +49% | 23% | +2.47 | +1.33 | +2.99 | +1.8% / +1.3% | +0% / +32% / +13% | 249 | 60% | +0k | +45k | +23% |
| ema | E24_200_s6 | LgSb | breadth | +46% | 26% | +1.97 | +1.11 | +2.45 | +1.8% / +0.3% | +7% / +21% / +12% | 383 | 71% | -1k | +42k | +8% |
| ema | E24_200_s6 | Lb | breadth | +27% | 42% | +1.45 | +0.79 | +0.88 | +1.6% / -0.4% | +16% / +17% / -6% | 277 | 71% | +25k | +0k | +4% |
| ema | E24_200_s6 | Sg | breadth | +25% | 21% | +1.82 | +1.09 | +1.59 | +1.2% / +0.2% | -1% / +19% / +6% | 153 | 44% | +0k | +26k | +11% |
| ema | E24_200_s6 | LbSg | breadth | +45% | 24% | +2.02 | +1.09 | +2.53 | +2.1% / +0.4% | +0% / +44% / +0% | 331 | 79% | +8k | +35k | +13% |
| ema | E24_200_s6 | Lg | btc_ret7d | -11% | 43% | -0.10 | -0.06 | -0.32 | -0.2% / -1.8% | +16% / -5% / -20% | 230 | 53% | -12k | +0k | -25% |
| ema | E24_200_s6 | Sb | btc_ret7d | +71% | 16% | +3.50 | +1.78 | +6.28 | +2.5% / +1.3% | +17% / +33% / +10% | 193 | 50% | +0k | +72k | +48% |
| ema | E24_200_s6 | LgSb | btc_ret7d | +2% | 37% | +0.49 | +0.31 | +0.09 | +0.3% / -0.3% | +13% / +11% / -18% | 370 | 77% | -32k | +32k | -23% |
| ema | E24_200_s6 | Lb | btc_ret7d | +21% | 39% | +1.27 | +0.68 | +0.71 | +1.6% / -1.3% | +18% / +18% / -13% | 237 | 62% | +20k | +0k | +1% |
| ema | E24_200_s6 | Sg | btc_ret7d | +53% | 19% | +2.84 | +1.53 | +3.92 | +2.1% / +1.9% | +2% / +41% / +6% | 200 | 52% | +0k | +54k | +31% |
| ema | E24_200_s6 | LbSg | btc_ret7d | +62% | 22% | +2.35 | +1.28 | +3.97 | +2.6% / -0.3% | +2% / +50% / +6% | 359 | 77% | +7k | +50k | +25% |
| ema | E24_200_s6 | Lg | hmm2 | -34% | 49% | -1.16 | -0.67 | -0.84 | -1.2% / -2.2% | -20% / +1% / -18% | 221 | 53% | -35k | +0k | -44% |
| ema | E24_200_s6 | Sb | hmm2 | -8% | 25% | -0.12 | -0.07 | -0.41 | +0.0% / -0.4% | -4% / +7% / -10% | 209 | 53% | +0k | -8k | -21% |
| ema | E24_200_s6 | LgSb | hmm2 | -31% | 54% | -0.80 | -0.47 | -0.70 | -0.5% / -3.3% | -15% / +11% / -26% | 372 | 75% | -23k | -8k | -47% |
| ema | E24_200_s6 | Lb | hmm2 | +12% | 30% | +0.89 | +0.53 | +0.50 | +0.7% / -1.0% | +28% / -5% / -8% | 211 | 53% | +12k | +0k | -5% |
| ema | E24_200_s6 | Sg | hmm2 | +90% | 14% | +4.41 | +2.18 | +9.20 | +2.9% / +1.1% | +8% / +44% / +22% | 183 | 45% | +0k | +91k | +65% |
| ema | E24_200_s6 | LbSg | hmm2 | +35% | 32% | +1.68 | +0.99 | +1.50 | +1.6% / +0.7% | +1% / +20% / +11% | 352 | 77% | -15k | +47k | +3% |
| ema | E48_200_s5 | L | - | +10% | 49% | +0.92 | +0.48 | +0.27 | +1.2% / -0.9% | +2% / +57% / -31% | 327 | 75% | +7k | +0k | -15% |
| ema | E48_200_s5 | S | - | +41% | 19% | +2.19 | +1.22 | +2.91 | +1.6% / +0.8% | +4% / +19% / +14% | 310 | 70% | +0k | +36k | +10% |
| ema | E48_200_s5 | B | - | +121% | 29% | +3.59 | +1.75 | +6.12 | +4.2% / +2.8% | -17% / +167% / -0% | 521 | 82% | +46k | +72k | +48% |
| ema | E48_200_s5 | Lg | btc_ema100 | -12% | 38% | -0.26 | -0.15 | -0.41 | -0.2% / -1.1% | +4% / +11% / -24% | 247 | 57% | -15k | +0k | -27% |
| ema | E48_200_s5 | Sb | btc_ema100 | +46% | 17% | +2.53 | +1.37 | +3.76 | +1.9% / +0.9% | +3% / +38% / +3% | 249 | 60% | +0k | +46k | +20% |
| ema | E48_200_s5 | LgSb | btc_ema100 | +56% | 29% | +2.24 | +1.18 | +2.63 | +2.6% / +2.3% | -6% / +98% / -16% | 458 | 81% | +10k | +41k | +9% |
| ema | E48_200_s5 | Lg | btc_ema200 | -17% | 43% | -0.51 | -0.28 | -0.49 | -0.4% / -1.3% | +3% / +12% / -28% | 232 | 53% | -20k | +0k | -30% |
| ema | E48_200_s5 | Sb | btc_ema200 | +40% | 17% | +2.34 | +1.34 | +3.19 | +1.7% / +0.7% | +4% / +34% / +0% | 224 | 56% | +0k | +40k | +17% |
| ema | E48_200_s5 | LgSb | btc_ema200 | +21% | 43% | +1.22 | +0.70 | +0.66 | +1.4% / +0.7% | +6% / +68% / -32% | 421 | 78% | -25k | +43k | -12% |
| ema | E48_200_s5 | Lg | btc_ema480 | +3% | 26% | +0.48 | +0.27 | +0.15 | +0.4% / +0.0% | +3% / +12% / -11% | 179 | 41% | -0k | +0k | -11% |
| ema | E48_200_s5 | Sb | btc_ema480 | +57% | 20% | +3.31 | +1.64 | +3.97 | +2.1% / +0.3% | -6% / +43% / +16% | 209 | 53% | +0k | +52k | +33% |
| ema | E48_200_s5 | LgSb | btc_ema480 | +62% | 27% | +2.64 | +1.37 | +3.23 | +2.6% / +1.5% | -0% / +60% / +1% | 366 | 75% | +4k | +54k | +21% |
| ema | E48_200_s5 | Lg | bkt_ema100 | +18% | 31% | +1.24 | +0.61 | +0.74 | +1.3% / -0.3% | -13% / +53% / -12% | 273 | 61% | +16k | +0k | -5% |
| ema | E48_200_s5 | Sb | bkt_ema100 | +51% | 19% | +2.77 | +1.37 | +3.67 | +2.1% / +0.6% | -1% / +56% / -2% | 268 | 61% | +0k | +51k | +23% |
| ema | E48_200_s5 | LgSb | bkt_ema100 | +94% | 34% | +3.08 | +1.52 | +4.02 | +3.6% / +3.4% | -16% / +149% / -8% | 487 | 82% | +42k | +51k | +33% |
| ema | E48_200_s5 | Lg | bkt_ema200 | +12% | 34% | +1.03 | +0.51 | +0.46 | +1.0% / -0.3% | -11% / +54% / -19% | 230 | 50% | +9k | +0k | -6% |
| ema | E48_200_s5 | Sb | bkt_ema200 | +6% | 23% | +0.67 | +0.39 | +0.35 | +0.6% / -0.2% | -11% / +32% / -10% | 263 | 60% | +0k | +6k | -14% |
| ema | E48_200_s5 | LgSb | bkt_ema200 | +41% | 32% | +1.88 | +0.96 | +1.75 | +2.2% / +2.2% | -22% / +117% / -16% | 457 | 80% | +20k | +18k | -1% |
| ema | E48_200_s5 | Lg | bkt_ema480 | -24% | 38% | -1.14 | -0.69 | -0.78 | -0.5% / -0.1% | -9% / +5% / -21% | 171 | 37% | -23k | +0k | -34% |
| ema | E48_200_s5 | Sb | bkt_ema480 | +27% | 24% | +1.83 | +0.98 | +1.51 | +1.2% / +0.0% | -13% / +35% / +8% | 232 | 55% | +0k | +23k | +6% |
| ema | E48_200_s5 | LgSb | bkt_ema480 | +22% | 25% | +1.32 | +0.71 | +1.14 | +1.4% / +0.5% | -20% / +41% / +7% | 389 | 76% | +1k | +18k | -11% |
| ema | E48_200_s5 | Lg | breadth | -13% | 35% | -0.33 | -0.17 | -0.48 | -0.3% / -1.0% | -10% / +5% / -8% | 206 | 44% | -14k | +0k | -26% |
| ema | E48_200_s5 | Sb | breadth | +27% | 21% | +1.65 | +0.92 | +1.75 | +1.3% / +0.0% | -6% / +35% / +0% | 280 | 63% | +0k | +27k | +2% |
| ema | E48_200_s5 | LgSb | breadth | +30% | 31% | +1.61 | +0.84 | +1.32 | +1.7% / +0.4% | -13% / +63% / -8% | 443 | 77% | -10k | +38k | -7% |
| ema | E48_200_s5 | Lg | btc_ret7d | +17% | 46% | +1.19 | +0.63 | +0.50 | +1.0% / -1.0% | +19% / +43% / -30% | 223 | 51% | +15k | +0k | -1% |
| ema | E48_200_s5 | Sb | btc_ret7d | +48% | 19% | +2.83 | +1.52 | +3.58 | +1.9% / +0.4% | +7% / +29% / +8% | 194 | 51% | +0k | +48k | +28% |
| ema | E48_200_s5 | LgSb | btc_ret7d | +92% | 31% | +3.24 | +1.69 | +4.24 | +3.2% / +1.8% | +19% / +83% / -12% | 376 | 77% | +8k | +82k | +44% |
| ema | E48_200_s5 | Lg | hmm2 | -22% | 40% | -0.83 | -0.44 | -0.70 | -0.6% / -1.5% | -18% / +19% / -20% | 199 | 48% | -24k | +0k | -33% |
| ema | E48_200_s5 | Sb | hmm2 | -15% | 22% | -0.78 | -0.51 | -0.85 | -0.4% / -0.0% | -6% / -6% / -3% | 192 | 47% | +0k | -15k | -27% |
| ema | E48_200_s5 | LgSb | hmm2 | -30% | 39% | -1.03 | -0.59 | -0.97 | -0.8% / -3.2% | -23% / +12% / -19% | 370 | 76% | -19k | -13k | -48% |
| z | Z48_2 | L | - | -55% | 59% | -2.16 | -1.78 | -1.09 | -2.7% / -2.5% | -8% / -14% / -44% | 961 | 98% | -56k | +0k | -84% |
| z | Z48_2 | S | - | -90% | 93% | -3.80 | -3.50 | -1.02 | -7.1% / -5.8% | -60% / -77% / +8% | 1243 | 97% | +0k | -90k | -97% |
| z | Z48_2 | B | - | -92% | 94% | -5.17 | -4.58 | -1.03 | -8.5% / -7.8% | -70% / -62% / -34% | 1542 | 100% | -16k | -76k | -98% |
| z | Z48_2 | Lg | btc_ema100 | -39% | 45% | -2.60 | -2.00 | -1.05 | -1.8% / -2.5% | -18% / +2% / -27% | 384 | 65% | -40k | +0k | -60% |
| z | Z48_2 | Sb | btc_ema100 | -70% | 76% | -2.59 | -2.36 | -1.04 | -3.9% / -3.8% | -39% / -52% / +3% | 667 | 76% | +0k | -70k | -83% |
| z | Z48_2 | LgSb | btc_ema100 | -84% | 85% | -3.83 | -3.47 | -1.07 | -6.1% / -4.5% | -53% / -51% / -29% | 968 | 96% | -17k | -66k | -93% |
| z | Z48_2 | Lb | btc_ema100 | -45% | 51% | -1.76 | -1.48 | -1.05 | -2.0% / -0.7% | -18% / -11% / -25% | 749 | 81% | -45k | +0k | -75% |
| z | Z48_2 | Sg | btc_ema100 | -77% | 81% | -3.33 | -2.97 | -1.06 | -4.4% / -1.2% | -46% / -58% / +1% | 817 | 75% | +0k | -77k | -88% |
| z | Z48_2 | LbSg | btc_ema100 | -86% | 88% | -4.07 | -3.57 | -1.05 | -6.3% / -3.2% | -47% / -62% / -31% | 1367 | 100% | -14k | -72k | -96% |
| z | Z48_2 | Lg | btc_ema200 | -46% | 50% | -2.91 | -2.33 | -1.09 | -2.2% / -3.1% | -24% / -8% / -22% | 387 | 58% | -46k | +0k | -63% |
| z | Z48_2 | Sb | btc_ema200 | -41% | 58% | -1.12 | -0.98 | -0.86 | -1.4% / -1.2% | -21% / -32% / +10% | 630 | 72% | +0k | -41k | -65% |
| z | Z48_2 | LgSb | btc_ema200 | -67% | 73% | -2.37 | -2.07 | -1.05 | -3.4% / -2.2% | -42% / -34% / -15% | 959 | 96% | -26k | -41k | -85% |
| z | Z48_2 | Lb | btc_ema200 | -57% | 61% | -2.69 | -2.30 | -1.09 | -3.0% / -1.6% | -23% / -10% / -37% | 707 | 76% | -57k | +0k | -79% |
| z | Z48_2 | Sg | btc_ema200 | -84% | 86% | -4.03 | -3.73 | -1.05 | -5.9% / -2.5% | -57% / -61% / -4% | 776 | 66% | +0k | -84k | -92% |
| z | Z48_2 | LbSg | btc_ema200 | -91% | 93% | -4.65 | -4.21 | -1.03 | -7.7% / -4.6% | -63% / -62% / -35% | 1345 | 99% | -16k | -75k | -97% |
| z | Z48_2 | Lg | btc_ema480 | -30% | 36% | -1.84 | -1.45 | -1.03 | -1.2% / +0.0% | -10% / -5% / -18% | 354 | 48% | -31k | +0k | -52% |
| z | Z48_2 | Sb | btc_ema480 | -47% | 65% | -1.38 | -1.21 | -0.87 | -1.6% / -1.1% | -24% / -42% / +19% | 686 | 67% | +0k | -47k | -70% |
| z | Z48_2 | LgSb | btc_ema480 | -66% | 74% | -2.22 | -1.93 | -1.01 | -3.1% / -3.7% | -32% / -43% / -12% | 1020 | 97% | -18k | -49k | -86% |
| z | Z48_2 | Lb | btc_ema480 | -51% | 55% | -2.21 | -1.87 | -1.10 | -2.5% / -1.3% | -5% / -20% / -35% | 679 | 71% | -51k | +0k | -74% |
| z | Z48_2 | Sg | btc_ema480 | -84% | 86% | -4.27 | -4.03 | -1.06 | -6.0% / -1.6% | -54% / -62% / -11% | 655 | 53% | +0k | -84k | -91% |
| z | Z48_2 | LbSg | btc_ema480 | -92% | 93% | -5.03 | -4.62 | -1.04 | -8.4% / -6.5% | -55% / -67% / -45% | 1260 | 100% | -11k | -81k | -97% |
| z | Z48_2 | Lg | bkt_ema100 | -29% | 36% | -2.00 | -1.48 | -0.97 | -1.1% / -1.8% | -4% / -3% / -24% | 351 | 61% | -29k | +0k | -51% |
| z | Z48_2 | Sb | bkt_ema100 | -61% | 67% | -2.86 | -2.51 | -1.05 | -2.9% / -3.2% | -30% / -43% / -2% | 630 | 77% | +0k | -60k | -77% |
| z | Z48_2 | LgSb | bkt_ema100 | -73% | 74% | -4.05 | -3.42 | -1.11 | -4.3% / -4.9% | -35% / -46% / -24% | 906 | 96% | -12k | -61k | -88% |
| z | Z48_2 | Lb | bkt_ema100 | -61% | 66% | -2.77 | -2.38 | -1.07 | -3.4% / -2.3% | -24% / -16% / -39% | 774 | 80% | -61k | +0k | -80% |
| z | Z48_2 | Sg | bkt_ema100 | -83% | 87% | -3.65 | -3.29 | -1.04 | -5.7% / -2.7% | -48% / -63% / -12% | 854 | 73% | +0k | -83k | -92% |
| z | Z48_2 | LbSg | bkt_ema100 | -88% | 91% | -4.31 | -3.75 | -1.03 | -6.9% / -5.2% | -60% / -57% / -29% | 1417 | 100% | -20k | -68k | -96% |
| z | Z48_2 | Lg | bkt_ema200 | -28% | 35% | -1.94 | -1.47 | -0.98 | -1.2% / -1.6% | -7% / -7% / -17% | 331 | 52% | -29k | +0k | -50% |
| z | Z48_2 | Sb | bkt_ema200 | -62% | 69% | -2.52 | -2.26 | -1.04 | -3.0% / -2.6% | -28% / -45% / -4% | 659 | 72% | +0k | -62k | -78% |
| z | Z48_2 | LgSb | bkt_ema200 | -72% | 73% | -3.03 | -2.65 | -1.10 | -4.0% / -3.9% | -32% / -49% / -18% | 959 | 96% | -13k | -59k | -88% |
| z | Z48_2 | Lb | bkt_ema200 | -54% | 60% | -2.31 | -1.96 | -1.07 | -2.9% / -2.3% | -16% / -14% / -37% | 753 | 80% | -55k | +0k | -79% |
| z | Z48_2 | Sg | bkt_ema200 | -81% | 86% | -3.72 | -3.31 | -1.03 | -5.6% / -3.1% | -41% / -61% / -17% | 743 | 61% | +0k | -81k | -90% |
| z | Z48_2 | LbSg | bkt_ema200 | -89% | 92% | -4.34 | -3.87 | -1.03 | -7.7% / -5.7% | -51% / -58% / -49% | 1354 | 100% | -15k | -75k | -97% |
| z | Z48_2 | Lg | bkt_ema480 | -26% | 32% | -1.77 | -1.36 | -1.00 | -0.9% / +0.0% | -7% / -14% / -8% | 298 | 39% | -26k | +0k | -46% |
| z | Z48_2 | Sb | bkt_ema480 | -56% | 71% | -1.73 | -1.55 | -0.93 | -2.3% / -1.4% | -27% / -48% / +15% | 749 | 72% | +0k | -56k | -76% |
| z | Z48_2 | LgSb | bkt_ema480 | -71% | 79% | -2.54 | -2.27 | -1.01 | -3.5% / -2.9% | -33% / -59% / +6% | 1034 | 96% | -19k | -53k | -88% |
| z | Z48_2 | Lb | bkt_ema480 | -48% | 52% | -1.99 | -1.67 | -1.10 | -2.3% / -0.9% | -6% / -7% / -40% | 714 | 75% | -49k | +0k | -75% |
| z | Z48_2 | Sg | bkt_ema480 | -76% | 81% | -3.52 | -3.25 | -1.04 | -4.8% / -0.7% | -44% / -57% / -1% | 562 | 46% | +0k | -76k | -85% |
| z | Z48_2 | LbSg | bkt_ema480 | -87% | 90% | -4.05 | -3.63 | -1.03 | -6.8% / -5.8% | -46% / -59% / -41% | 1231 | 100% | -10k | -77k | -95% |
| z | Z48_2 | Lg | breadth | -26% | 36% | -1.98 | -1.48 | -0.90 | -1.0% / -1.1% | -1% / -10% / -17% | 271 | 47% | -27k | +0k | -45% |
| z | Z48_2 | Sb | breadth | -75% | 80% | -2.92 | -2.67 | -1.04 | -4.5% / -4.4% | -37% / -57% / -8% | 801 | 83% | +0k | -75k | -87% |
| z | Z48_2 | LgSb | breadth | -82% | 84% | -3.46 | -3.16 | -1.06 | -5.6% / -5.4% | -40% / -62% / -22% | 1036 | 96% | -7k | -75k | -93% |
| z | Z48_2 | Lb | breadth | -59% | 62% | -2.65 | -2.25 | -1.10 | -3.1% / -2.3% | -16% / -16% / -42% | 779 | 82% | -59k | +0k | -81% |
| z | Z48_2 | Sg | breadth | -78% | 81% | -3.92 | -3.61 | -1.06 | -5.1% / -1.6% | -42% / -51% / -22% | 556 | 52% | +0k | -78k | -86% |
| z | Z48_2 | LbSg | breadth | -88% | 90% | -4.29 | -3.83 | -1.04 | -6.9% / -4.9% | -54% / -54% / -44% | 1262 | 100% | -19k | -69k | -96% |
| z | Z48_2 | Lg | btc_ret7d | -31% | 39% | -1.67 | -1.32 | -0.98 | -1.3% / -1.2% | -5% / -10% / -19% | 439 | 59% | -31k | +0k | -55% |
| z | Z48_2 | Sb | btc_ret7d | -36% | 55% | -0.86 | -0.74 | -0.80 | -1.0% / -0.6% | -27% / -25% / +16% | 665 | 69% | +0k | -36k | -63% |
| z | Z48_2 | LgSb | btc_ret7d | -53% | 64% | -1.46 | -1.23 | -0.97 | -2.1% / -1.6% | -35% / -18% / -12% | 1033 | 97% | -12k | -41k | -82% |
| z | Z48_2 | Lb | btc_ret7d | -47% | 54% | -2.01 | -1.69 | -1.04 | -2.2% / -0.8% | -12% / -14% / -29% | 643 | 70% | -47k | +0k | -73% |
| z | Z48_2 | Sg | btc_ret7d | -82% | 84% | -3.88 | -3.55 | -1.05 | -5.2% / -1.3% | -48% / -63% / -6% | 729 | 64% | +0k | -82k | -90% |
| z | Z48_2 | LbSg | btc_ret7d | -90% | 91% | -4.52 | -4.09 | -1.04 | -7.3% / -4.2% | -56% / -66% / -31% | 1282 | 98% | -16k | -74k | -97% |
| z | Z48_2 | Lg | hmm2 | -62% | 65% | -3.28 | -2.85 | -1.10 | -3.5% / -2.4% | -20% / -19% / -42% | 546 | 61% | -63k | +0k | -79% |
| z | Z48_2 | Sb | hmm2 | -84% | 87% | -4.34 | -4.08 | -1.04 | -6.1% / -3.7% | -52% / -67% / +2% | 703 | 65% | +0k | -84k | -91% |
| z | Z48_2 | LgSb | hmm2 | -93% | 93% | -5.24 | -4.85 | -1.04 | -8.9% / -7.4% | -59% / -70% / -43% | 1207 | 99% | -19k | -74k | -98% |
| z | Z48_2 | Lb | hmm2 | -15% | 42% | -0.51 | -0.40 | -0.47 | -0.5% / +0.0% | +13% / -3% / -23% | 502 | 63% | -15k | +0k | -49% |
| z | Z48_2 | Sg | hmm2 | -44% | 57% | -1.14 | -0.99 | -0.92 | -1.3% / +0.0% | -30% / -22% / +4% | 631 | 61% | +0k | -44k | -66% |
| z | Z48_2 | LbSg | hmm2 | -54% | 59% | -1.35 | -1.14 | -1.07 | -2.0% / -1.0% | -25% / -25% / -18% | 1091 | 99% | -8k | -46k | -82% |
| z | Z72_3 | L | - | -44% | 51% | -2.04 | -1.68 | -1.03 | -2.0% / -2.4% | -6% / -24% / -21% | 414 | 76% | -44k | +0k | -60% |
| z | Z72_3 | S | - | -76% | 81% | -3.09 | -2.71 | -1.04 | -4.6% / -2.8% | -46% / -55% / -3% | 642 | 82% | +0k | -76k | -86% |
| z | Z72_3 | B | - | -86% | 88% | -4.24 | -3.69 | -1.05 | -6.5% / -5.2% | -51% / -63% / -21% | 933 | 98% | -18k | -68k | -93% |
| z | Z72_3 | Lg | btc_ema100 | +17% | 11% | +2.40 | +1.23 | +2.08 | +0.7% / +0.0% | +9% / +12% / -4% | 81 | 26% | +17k | +0k | +9% |
| z | Z72_3 | Sb | btc_ema100 | -38% | 45% | -1.56 | -1.37 | -1.02 | -1.4% / -0.5% | -5% / -34% / -1% | 240 | 52% | +0k | -38k | -49% |
| z | Z72_3 | LgSb | btc_ema100 | -25% | 35% | -0.81 | -0.67 | -0.90 | -0.7% / -0.0% | +3% / -26% / -2% | 318 | 70% | +16k | -41k | -43% |
| z | Z72_3 | Lg | btc_ema200 | +7% | 13% | +0.87 | +0.55 | +0.70 | +0.3% / +0.0% | -4% / +9% / +3% | 105 | 31% | +7k | +0k | -2% |
| z | Z72_3 | Sb | btc_ema200 | -14% | 30% | -0.36 | -0.29 | -0.60 | -0.1% / +0.0% | +4% / -19% / +1% | 234 | 52% | +0k | -14k | -29% |
| z | Z72_3 | LgSb | btc_ema200 | -6% | 33% | +0.07 | +0.06 | -0.22 | +0.3% / +1.7% | +1% / -11% / +5% | 336 | 72% | +8k | -13k | -29% |
| z | Z72_3 | Lg | btc_ema480 | -0% | 14% | +0.13 | +0.09 | -0.03 | +0.0% / +0.0% | -0% / +6% / -6% | 121 | 29% | -0k | +0k | -10% |
| z | Z72_3 | Sb | btc_ema480 | -26% | 46% | -0.86 | -0.71 | -0.71 | -0.6% / +0.0% | +1% / -33% / +8% | 262 | 50% | +0k | -26k | -40% |
| z | Z72_3 | LgSb | btc_ema480 | -27% | 44% | -0.81 | -0.65 | -0.76 | -0.7% / -0.2% | +1% / -29% / +2% | 382 | 73% | -1k | -26k | -46% |
| z | Z72_3 | Lg | bkt_ema100 | +12% | 10% | +2.21 | +1.07 | +1.50 | +0.5% / +0.0% | +7% / +6% / -2% | 55 | 23% | +12k | +0k | +6% |
| z | Z72_3 | Sb | bkt_ema100 | -19% | 29% | -1.10 | -0.85 | -0.80 | -0.5% / +0.0% | +1% / -17% / -3% | 177 | 48% | +0k | -19k | -30% |
| z | Z72_3 | LgSb | bkt_ema100 | -9% | 24% | -0.36 | -0.25 | -0.49 | -0.0% / +0.2% | +8% / -12% / -5% | 232 | 62% | +11k | -20k | -26% |
| z | Z72_3 | Lg | bkt_ema200 | +2% | 13% | +0.38 | +0.24 | +0.20 | +0.1% / +0.0% | -3% / +6% / -1% | 72 | 23% | +2k | +0k | -5% |
| z | Z72_3 | Sb | bkt_ema200 | -28% | 33% | -1.32 | -1.08 | -1.06 | -0.7% / -0.9% | -6% / -17% / -7% | 219 | 50% | +0k | -28k | -40% |
| z | Z72_3 | LgSb | bkt_ema200 | -23% | 28% | -0.88 | -0.69 | -1.02 | -0.4% / -0.4% | -4% / -12% / -8% | 285 | 68% | +3k | -25k | -39% |
| z | Z72_3 | Lg | bkt_ema480 | +2% | 12% | +0.39 | +0.26 | +0.26 | +0.2% / +0.0% | -3% / +3% / +3% | 93 | 22% | +2k | +0k | -6% |
| z | Z72_3 | Sb | bkt_ema480 | -41% | 51% | -1.54 | -1.32 | -0.98 | -1.4% / -0.4% | -13% / -33% / +1% | 287 | 55% | +0k | -41k | -53% |
| z | Z72_3 | LgSb | bkt_ema480 | -40% | 51% | -1.38 | -1.17 | -0.95 | -1.3% / -0.1% | -15% / -31% / +3% | 379 | 72% | +2k | -42k | -56% |
| z | Z72_3 | Lg | breadth | +9% | 11% | +1.54 | +0.83 | +1.09 | +0.4% / +0.0% | +5% / +6% / -2% | 55 | 20% | +9k | +0k | +3% |
| z | Z72_3 | Sb | breadth | -34% | 44% | -1.25 | -1.04 | -0.94 | -1.1% / -1.3% | +1% / -32% / -4% | 311 | 60% | +0k | -34k | -49% |
| z | Z72_3 | LgSb | breadth | -28% | 41% | -0.88 | -0.72 | -0.84 | -0.7% / -0.6% | +5% / -27% / -6% | 366 | 72% | +10k | -38k | -48% |
| z | Z72_3 | Lg | btc_ret7d | +5% | 17% | +0.59 | +0.40 | +0.40 | +0.3% / +0.0% | +2% / +11% / -7% | 131 | 36% | +5k | +0k | -6% |
| z | Z72_3 | Sb | btc_ret7d | -35% | 43% | -1.24 | -1.03 | -1.00 | -1.3% / -0.6% | -21% / -8% / -11% | 296 | 54% | +0k | -35k | -49% |
| z | Z72_3 | LgSb | btc_ret7d | -34% | 39% | -1.07 | -0.87 | -1.06 | -1.2% / -1.2% | -23% / +2% / -16% | 416 | 77% | +4k | -38k | -53% |
| z | Z72_3 | Lg | hmm2 | -54% | 57% | -3.60 | -3.28 | -1.12 | -3.0% / -1.7% | -18% / -27% / -24% | 248 | 46% | -54k | +0k | -64% |
| z | Z72_3 | Sb | hmm2 | -67% | 71% | -3.41 | -3.02 | -1.07 | -3.9% / -1.3% | -31% / -51% / -3% | 395 | 54% | +0k | -67k | -77% |
| z | Z72_3 | LgSb | hmm2 | -84% | 85% | -4.70 | -4.26 | -1.06 | -6.5% / -4.8% | -41% / -63% / -25% | 632 | 85% | -26k | -58k | -91% |
| z | Z24_2p5 | L | - | -58% | 62% | -2.75 | -2.31 | -1.08 | -3.3% / -2.8% | -28% / -11% / -34% | 1045 | 98% | -58k | +0k | -84% |
| z | Z24_2p5 | S | - | -85% | 86% | -4.15 | -3.75 | -1.07 | -6.3% / -6.7% | -61% / -58% / -10% | 1395 | 98% | +0k | -85k | -95% |
| z | Z24_2p5 | B | - | -94% | 94% | -5.48 | -4.99 | -1.03 | -9.7% / -8.4% | -76% / -51% / -45% | 2023 | 100% | -33k | -61k | -99% |
| z | Z24_2p5 | Lg | btc_ema100 | -24% | 31% | -1.70 | -1.30 | -0.97 | -1.1% / -1.3% | -12% / +5% / -18% | 377 | 58% | -24k | +0k | -48% |
| z | Z24_2p5 | Sb | btc_ema100 | -63% | 65% | -3.32 | -2.99 | -1.11 | -3.5% / -3.4% | -26% / -44% / -11% | 656 | 71% | +0k | -63k | -79% |
| z | Z24_2p5 | LgSb | btc_ema100 | -73% | 74% | -3.78 | -3.31 | -1.10 | -4.7% / -3.7% | -35% / -43% / -26% | 1012 | 97% | -13k | -59k | -89% |
| z | Z24_2p5 | Lg | btc_ema200 | -36% | 42% | -2.52 | -2.07 | -1.06 | -1.8% / -1.6% | -18% / -3% / -20% | 389 | 55% | -36k | +0k | -59% |
| z | Z24_2p5 | Sb | btc_ema200 | -55% | 56% | -2.68 | -2.31 | -1.14 | -2.6% / -3.5% | -23% / -33% / -11% | 673 | 67% | +0k | -55k | -74% |
| z | Z24_2p5 | LgSb | btc_ema200 | -71% | 73% | -3.65 | -3.16 | -1.11 | -4.4% / -4.4% | -36% / -36% / -30% | 1043 | 97% | -23k | -48k | -90% |
| z | Z24_2p5 | Lg | btc_ema480 | -38% | 43% | -2.65 | -2.21 | -1.07 | -1.9% / -0.3% | -20% / -8% / -16% | 378 | 46% | -38k | +0k | -57% |
| z | Z24_2p5 | Sb | btc_ema480 | -55% | 55% | -2.44 | -2.09 | -1.17 | -2.4% / -2.2% | -17% / -38% / -11% | 777 | 66% | +0k | -55k | -76% |
| z | Z24_2p5 | LgSb | btc_ema480 | -72% | 73% | -3.43 | -2.95 | -1.11 | -4.3% / -4.6% | -35% / -42% / -26% | 1145 | 97% | -27k | -45k | -90% |
| z | Z24_2p5 | Lg | bkt_ema100 | -23% | 27% | -1.99 | -1.48 | -1.06 | -1.0% / -1.3% | -11% / -0% / -12% | 338 | 57% | -23k | +0k | -42% |
| z | Z24_2p5 | Sb | bkt_ema100 | -45% | 52% | -2.62 | -2.14 | -1.04 | -1.9% / -3.2% | -26% / -32% / +9% | 624 | 72% | +0k | -45k | -67% |
| z | Z24_2p5 | LgSb | bkt_ema100 | -59% | 60% | -3.48 | -2.83 | -1.14 | -3.1% / -3.9% | -32% / -35% / -7% | 943 | 97% | -14k | -45k | -82% |
| z | Z24_2p5 | Lg | bkt_ema200 | -31% | 34% | -2.60 | -2.04 | -1.10 | -1.5% / -1.3% | -17% / -6% / -12% | 332 | 47% | -31k | +0k | -51% |
| z | Z24_2p5 | Sb | bkt_ema200 | -59% | 59% | -3.27 | -2.85 | -1.16 | -2.8% / -3.6% | -30% / -29% / -17% | 711 | 71% | +0k | -59k | -77% |
| z | Z24_2p5 | LgSb | bkt_ema200 | -72% | 72% | -4.14 | -3.57 | -1.12 | -4.2% / -5.4% | -42% / -33% / -28% | 1030 | 97% | -19k | -53k | -88% |
| z | Z24_2p5 | Lg | bkt_ema480 | -29% | 31% | -2.32 | -1.87 | -1.18 | -1.3% / +0.0% | -19% / -8% / -5% | 295 | 37% | -29k | +0k | -46% |
| z | Z24_2p5 | Sb | bkt_ema480 | -61% | 61% | -2.85 | -2.50 | -1.15 | -2.9% / -3.6% | -30% / -39% / -9% | 842 | 70% | +0k | -61k | -80% |
| z | Z24_2p5 | LgSb | bkt_ema480 | -72% | 72% | -3.53 | -3.09 | -1.12 | -4.2% / -5.3% | -42% / -44% / -14% | 1133 | 97% | -18k | -54k | -89% |
| z | Z24_2p5 | Lg | breadth | -28% | 31% | -2.38 | -1.87 | -1.13 | -1.3% / -1.1% | -13% / +1% / -18% | 282 | 42% | -28k | +0k | -44% |
| z | Z24_2p5 | Sb | breadth | -70% | 71% | -3.63 | -3.20 | -1.11 | -4.0% / -4.9% | -33% / -48% / -13% | 856 | 79% | +0k | -70k | -85% |
| z | Z24_2p5 | LgSb | breadth | -80% | 80% | -4.40 | -3.89 | -1.09 | -5.4% / -6.2% | -43% / -49% / -31% | 1122 | 98% | -14k | -66k | -92% |
| z | Z24_2p5 | Lg | btc_ret7d | -20% | 30% | -1.21 | -0.94 | -0.81 | -1.0% / -0.7% | -6% / -1% / -14% | 436 | 54% | -20k | +0k | -48% |
| z | Z24_2p5 | Sb | btc_ret7d | -47% | 54% | -2.07 | -1.75 | -1.05 | -2.1% / -2.8% | -20% / -30% / -7% | 713 | 66% | +0k | -47k | -70% |
| z | Z24_2p5 | LgSb | btc_ret7d | -55% | 62% | -2.20 | -1.82 | -1.03 | -2.8% / -3.2% | -20% / -30% / -19% | 1125 | 98% | -10k | -44k | -83% |
| z | Z24_2p5 | Lg | hmm2 | -53% | 59% | -2.94 | -2.56 | -1.05 | -2.9% / -2.2% | -22% / -11% / -32% | 581 | 58% | -53k | +0k | -73% |
| z | Z24_2p5 | Sb | hmm2 | -74% | 78% | -4.04 | -3.74 | -1.06 | -4.9% / -3.4% | -54% / -49% / +9% | 767 | 63% | +0k | -74k | -87% |
| z | Z24_2p5 | LgSb | hmm2 | -88% | 89% | -5.03 | -4.62 | -1.04 | -7.7% / -6.6% | -62% / -54% / -29% | 1337 | 99% | -21k | -67k | -96% |

## Appendix B. The first combo test (concentrated sizing, NOT used: see section 4.3)

| short parameters | mode | gate | note | total | max DD | Sortino | Sharpe | Calmar | 11d mean / median | thirds | trades | active days | long P&L | short P&L | stress total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E24_200_s6 | Lg+Sbad | btc_ema480 | short slots 1 | +111% | 20% | +4.11 | +2.01 | +8.05 | +3.7% / +1.2% | +21% / +67% / +5% | 331 | 69% | +115k | -4k | +66% |
| E24_200_s6 | Lg+Sbad | btc_ema480 | short slots 2 | +133% | 20% | +4.42 | +2.21 | +9.85 | +4.1% / +2.1% | +25% / +82% / +2% | 381 | 75% | +108k | +25k | +77% |
| E48_200_s5 | Lg+Sbad | btc_ema480 | short slots 1 | +141% | 21% | +4.81 | +2.33 | +10.09 | +4.4% / +2.3% | +21% / +89% / +6% | 321 | 65% | +120k | +22k | +91% |
| E48_200_s5 | Lg+Sbad | btc_ema480 | short slots 2 | +190% | 23% | +5.73 | +2.72 | +13.17 | +5.0% / +3.3% | +21% / +92% / +24% | 365 | 73% | +136k | +44k | +120% |
| E24_200_s6 | Lg+Salw | btc_ema480 | short slots 1 | +205% | 20% | +6.20 | +2.70 | +15.92 | +5.5% / +1.2% | +13% / +133% / +16% | 335 | 66% | +167k | +39k | +137% |
| E24_200_s6 | Lg+Salw | btc_ema480 | short slots 2 | +189% | 33% | +5.34 | +2.60 | +9.03 | +5.3% / +2.6% | -5% / +122% / +37% | 392 | 74% | +123k | +66k | +113% |
| E48_200_s5 | Lg+Salw | btc_ema480 | short slots 1 | +271% | 19% | +7.44 | +3.12 | +23.39 | +6.4% / +2.6% | +26% / +119% / +34% | 343 | 64% | +221k | +50k | +187% |
| E48_200_s5 | Lg+Salw | btc_ema480 | short slots 2 | +259% | 20% | +6.65 | +3.11 | +21.51 | +6.0% / +3.6% | +29% / +109% / +34% | 396 | 74% | +165k | +83k | +166% |
| E24_200_s6 | Lg+Sbad | bkt_ema200 | short slots 1 | +130% | 30% | +4.26 | +2.02 | +6.43 | +4.4% / +0.8% | +1% / +131% / -1% | 406 | 71% | +110k | +21k | +75% |
| E24_200_s6 | Lg+Sbad | bkt_ema200 | short slots 2 | +138% | 31% | +4.02 | +2.00 | +6.66 | +4.5% / +0.7% | +6% / +138% / -6% | 459 | 77% | +89k | +44k | +72% |
| E48_200_s5 | Lg+Sbad | bkt_ema200 | short slots 1 | +92% | 30% | +3.20 | +1.67 | +4.46 | +3.6% / +1.3% | +3% / +98% / -6% | 424 | 73% | +74k | +18k | +43% |
| E48_200_s5 | Lg+Sbad | bkt_ema200 | short slots 2 | +97% | 32% | +3.16 | +1.68 | +4.42 | +3.8% / +1.3% | +2% / +120% / -12% | 479 | 81% | +61k | +37k | +39% |
| E24_200_s6 | Lg+Salw | bkt_ema200 | short slots 1 | +159% | 28% | +4.80 | +2.18 | +8.76 | +5.1% / +0.8% | -2% / +154% / +4% | 416 | 70% | +121k | +39k | +94% |
| E24_200_s6 | Lg+Salw | bkt_ema200 | short slots 2 | +184% | 34% | +4.76 | +2.36 | +8.53 | +5.4% / +2.6% | -16% / +158% / +31% | 452 | 76% | +100k | +87k | +102% |
| E48_200_s5 | Lg+Salw | bkt_ema200 | short slots 1 | +196% | 29% | +5.68 | +2.49 | +10.52 | +5.6% / +2.0% | +8% / +134% / +18% | 427 | 71% | +148k | +49k | +119% |
| E48_200_s5 | Lg+Salw | bkt_ema200 | short slots 2 | +171% | 26% | +4.63 | +2.31 | +10.26 | +5.0% / +2.7% | +15% / +110% / +12% | 480 | 78% | +82k | +82k | +92% |
| E24_200_s6 | Lg+Sbad | btc_ret7d | short slots 1 | +134% | 23% | +4.63 | +2.17 | +8.85 | +4.1% / +1.9% | +33% / +80% / -2% | 339 | 70% | +103k | +31k | +82% |
| E24_200_s6 | Lg+Sbad | btc_ret7d | short slots 2 | +160% | 27% | +4.83 | +2.29 | +9.08 | +4.7% / +2.7% | +43% / +82% / -0% | 390 | 75% | +119k | +41k | +96% |
| E48_200_s5 | Lg+Sbad | btc_ret7d | short slots 1 | +141% | 22% | +5.07 | +2.27 | +9.48 | +4.3% / +2.0% | +24% / +92% / +1% | 341 | 70% | +105k | +35k | +88% |
| E48_200_s5 | Lg+Sbad | btc_ret7d | short slots 2 | +210% | 21% | +6.17 | +2.70 | +16.09 | +5.5% / +3.4% | +34% / +107% / +12% | 384 | 76% | +145k | +65k | +133% |
| E24_200_s6 | Lg+Salw | btc_ret7d | short slots 1 | +203% | 23% | +5.98 | +2.58 | +13.61 | +5.5% / +2.5% | +29% / +133% / +1% | 356 | 70% | +149k | +52k | +132% |
| E24_200_s6 | Lg+Salw | btc_ret7d | short slots 2 | +214% | 27% | +5.65 | +2.71 | +12.35 | +5.5% / +2.8% | +4% / +142% / +24% | 402 | 76% | +103k | +109k | +129% |
| E48_200_s5 | Lg+Salw | btc_ret7d | short slots 1 | +216% | 23% | +6.35 | +2.70 | +14.61 | +5.7% / +2.3% | +26% / +110% / +20% | 368 | 68% | +162k | +52k | +141% |
| E48_200_s5 | Lg+Salw | btc_ret7d | short slots 2 | +258% | 18% | +6.82 | +2.98 | +22.69 | +6.0% / +3.4% | +31% / +110% / +30% | 422 | 76% | +154k | +91k | +165% |
| E24_200_s6 | L+Salw | - | ungated, 2 short slots | +187% | 33% | +4.37 | +2.17 | +8.90 | +5.5% / +1.8% | +4% / +159% / +6% | 526 | 83% | +72k | +116k | +89% |
