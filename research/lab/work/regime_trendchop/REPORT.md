# Track regime_trendchop - is "trending vs chopping" forecastable enough to pay for switching strategies?

Design data only (`harness.load('design')`, 7,519 hourly bars, 50 pairs). All code in this folder.
Verdict: **weak-edge** (one narrow use of the label works on design data; the switching idea itself does not).

## Short answer

1. The trend/chop state is persistent (with K=2 a coin is in the same state 24h later 63-84% of the time) but it barely predicts
   pay-offs. "Trend-following pays more in the trend state" has the right sign in most labelings and is about
   +20 bp per 24h with t between 1.0 and 1.7: not distinguishable from zero, and smaller than a round trip at stress costs.
2. Switching does not pay. Z-score mean reversion lost money in **every** state of **every** labeling (long: 0 of 21
   gated variants positive, short: 1 of 21) and the "chop" gate did not beat a placebo label of the same frequency. The honest map
   has no mean-reversion leg.
3. EMA crossover gated by "trend" needs care: at the hour EMA24 crosses EMA100 the gap is zero, so a trend
   classifier says "chop" by construction. With the reference setting (enter within 3 bars of the cross) the trend gate
   from K-Means removes 90-99% of trades (687 -> 9..69). Entering any time the state says trend (no freshness limit) loses (-9% to -67%).
4. The one thing that works: buy **within about 6-24 hours of the up-cross, only if the coin is already classed as trending**
   (in practice: the EMA gap has already opened to 1-1.5 ATR). All 7 freshness values from 6 to 24 h are positive for the
   K-Means core4 label at default and at stress costs; the shifted placebo label is +2% to -15% at default and -31% to -47% at stress. This is the same edge as
   the long-only breakout benchmark (buy fast, strong up-moves early, trail a stop), found from the other side.
5. K-Means adds nothing over a single threshold: the K=2 "trend" cluster is almost exactly |EMA24-EMA100|/ATR above ~1.25
   (P(trend | |gap| < 1.25) = 0.6%). `EmaCross(..., min_gap=1.25)` does as well or better. The HMM on top is worse
   (smoother labels arrive later; the value is in being early).
6. Shorts: no evidence. In the trend state the short side is about as good with a shifted placebo label as with the real
   one (bear-market tape, not information), and 0 of 9 gated short variants are positive at stress costs.
7. Caveats that keep this at weak-edge: about 640 variants were run; the two candidates sit at the peak (freshness 15) of
   a plateau whose average is well below the peak (K-Means: +41% against +74%); without the three best coins both are negative at stress costs;
   removing the six coarse-tick coins halves the result; with the standard split two of three thirds are about flat and
   the middle third carries the total; the median 11-day window is about zero.

## Method

- `tc.py`: 19 causal features. Trend-vs-chop set: Kaufman efficiency ratio 24/72/168h; EMA 9/21 and 24/100 cross counts
  over 72/168h; |EMA24-EMA100|/ATR24 (and signed); variance ratio var(24h ret)/(24 var(1h ret)) over 168h; lag-1
  autocorrelation of 1h returns (168h window) and of 6h returns (336h); log(rv24/rv168) and log rv168; distance from the
  7-day high and low in ATR, position in the 7-day range and its distance from the middle ("edge").
- Labelings (31): K-Means walk-forward (`regime.walk_forward`, first fit on 1,000 bars, refit every 336 bars, expanding
  window, one model for all coins) on five feature sets (`core4`, `agn8`, `agn10v`, `dir3`, `all15`) x K in {2,3,4};
  K-Means-initialised HMM (refit every 720 bars) on six of them; ten non-ML thresholds (one feature against its trailing
  30-day pooled quantile). States are ordered by the first feature, so "top" = most trending and "bottom" = most choppy
  (for `dir3`: bottom = downtrend, middle = chop, top = uptrend). Labels exist from bar 1,267, so sweeps use `start=1400`
  for gated, ungated, placebo and benchmark alike. Finalists are also reported with the standard `start=744`.
- Predictive test: trend proxy sign(EMA24-EMA100) x forward return, mean-reversion proxy -clip(z48,-3,3) x forward
  return, 24h and 72h, sampled every 24/72 bars (non-overlapping); each sample is the cross-coin mean within the state;
  t = mean / standard error over time. Thirds reported.
- Trading test: `strategies.EmaCross(24,100)` long (limit entries) and short, `strategies.ZScoreMR(48,2.0)` long (limit) and
  short, 4 slots, gated by `allow_long` / `allow_short`. Each gate is compared with the ungated rule, the inverse gate,
  and two placebos of identical frequency and persistence: the same labels 1,000 bars late, and each coin given another
  coin's label path. Because gating a losing rule "improves" it just by trading less, the comparison that matters is
  net bp per trade against the placebos.
- Costs: default and `evalkit.STRESS`, both from `evalkit.report`. Variants run: 610 in `results.jsonl` + 29 in
  `final.jsonl` = **639 backtested variants**, plus 31 labelings in the predictive test.
- Look-ahead: sweeps use labels cached from the design panel (no check). The two candidate files compute everything inside
  `make(panel)` and both pass `h.causality_check(make, panel, cuts=8)` (8 cuts, not 40, because candidate 1 refits K-Means
  on each of the 18 rebuilt panels; about 75 s).

## Benchmarks on the sweep window (start=1400)

| strategy | total | max DD | 11d mean / median | thirds | stress total | trades |
|---|---|---|---|---|---|---|
| baselines.Breakout | +14.9% | 43% | +1.9% / -1.3% | +21% +14% -17% | -13.0% | 423 |
| EmaCross(24,100) long ungated, fresh 3 / 24 / none | -48% / -40% / -47% | 58-62% | -2.3% / -3.8% | -5% -44% -2% | -75% / -80% / -85% | 687 / 963 / 1193 |
| EmaCross(24,100) short ungated, fresh 3 / 24 / none | +6% / -25% / -59% | 24-64% | +0.7% / -0.2% | -11% +18% +1% | -35% / -64% / -86% | 620 / 899 / 1250 |
| ZScoreMR(48,2) long ungated | -42% | 56% | -2.0% / -1.4% | +13% -11% -43% | -81% | 838 |
| ZScoreMR(48,2) short ungated | -87% | 92% | -6.9% / -4.9% | -60% -71% +10% | -95% | 1126 |

The ungated short EMA result (+6%) flips to -25% and -59% when only the freshness window changes: noise.

## The finding: freshness x trend gate, long EMA 24/100 (start=1400)

Total return at default costs (stress costs in brackets). "shift" = same label 1,000 bars late.

| entry allowed up to N h after the cross | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 36 | 48 | 72 | any time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| K-Means core4 K=2, trend | -1% (-4%) | +21% (+13%) | +17% (+4%) | +26% (+5%) | +74% (+38%) | +66% (+28%) | +46% (+11%) | +36% (+3%) | +9% (-26%) | +6% (-38%) | +1% (-48%) | -26% (-69%) |
| same, shift placebo | -40% | +2% (-31%) | -5% (-38%) | -9% (-44%) | -7% (-45%) | -5% (-46%) | -8% (-47%) | -15% | -29% (-64%) | -40% (-71%) | -49% (-78%) | -72% |
| K-Means agn8 K=2, trend | -0% (-12%) | +14% (-4%) | +18% (-9%) | +43% (+8%) | +87% (+40%) | +81% (+35%) | +56% (+12%) | +31% (-5%) | +2% (-35%) | -1% (-44%) | +33% (-31%) | -23% (-70%) |
| threshold: gapabs above trailing median | +1% (2 trades) | +4% (-5%) | - | +35% (+9%) | - | +80% (+23%) | - | +52% (-4%) | -6% (-46%) | -34% (-66%) | -15% (-62%) | -30% (-72%) |
| trades (core4 row) | 40 | 61 | 103 | 143 | 178 | 221 | 247 | 281 | 368 | 454 | 546 | 771 |

Non-ML fixed threshold `EmaCross(24,100, long, limit, min_gap=g, fresh=N)`, total (stress):

| min_gap (ATR) | N=9 | 12 | 15 | 18 | 21 | 24 | 48 |
|---|---|---|---|---|---|---|---|
| 0.5 | - | +5% (-42%) | - | - | - | -3% (-56%) | -60% (-86%) |
| 1.0 | +68% (+23%) | +71% (+12%) | +103% (+20%) | +64% (-3%) | +52% (-14%) | +54% (-13%) | -53% (-78%) |
| 1.25 | +50% (+16%) | - | +85% (+25%) | +73% (+8%) | +46% (-13%) | - | - |
| 1.5 | +19% (+1%) | +46% (+20%) | +67% (+25%) | +69% (+22%) | +70% (+16%) | +46% (+0%) | -32% (-64%) |
| 2.0 | - | +8% (-3%) | - | - | - | -6% (-29%) | -28% (-58%) |
| 3.0 | - | +9% (+8%) | - | - | - | +9% (+2%) | -11% (-26%) |

Plateau: min_gap 1.0-1.5 x freshness 9-24: 16 of 16 cells positive at default costs (mean +61%), 12 of 16 positive at stress
(mean +9%). Outside it (gap 0.5 or >= 2.0, freshness >= 36) the result is flat to strongly negative. The response is
peaked at freshness 15-18, about twice its neighbours: expect the neighbours' level, not the peak.

HMM instead of K-Means (freshness 24): core4 K=2 +19% (stress -15%), agn8 K=2 -12% (stress -44%), against +36% and +31%
for plain K-Means. Smoothing delays the label.

Full map variants (freshness 24, start=1400), long P&L / short P&L:

| map | core4 K=2 | agn8 K=2 | gapabs threshold |
|---|---|---|---|
| trend -> EMA long+short | +25% (stress -19%), long +33.5k / short -9.8k | +59% (-7%), +14.6k / +42.6k | +60% (-21%), +33.9k / +23.5k |
| same with shifted placebo label | +51% (-33%), +16.7k / +33.4k | +40% (-41%), +8.7k / +30.4k | -34% (-76%) |
| trend -> EMA long, chop -> z-score MR long | -43% (-81%) | -51% (-84%) | -34% (-75%) |
| trend -> EMA long+short, chop -> MR long | -46% (-79%) | -46% (-82%) | -39% (-80%) |

The short leg earns as much with a placebo label as with the real one; the mean-reversion leg turns every map negative.

## Finalists

Standard report (`evalkit.report`, start=744, default costs; labels start at bar 1,267 so candidate 1 is in cash for the
first 22 days):

| | candidate_1 (K-Means gate) | candidate_2 (gap threshold) | Breakout |
|---|---|---|---|
| total return | +65.9% | +89.8% | +40.3% |
| max drawdown | 17.4% | 21.4% | 43% |
| Sharpe / Sortino / Calmar | 1.54 / 5.08 / 5.30 | 1.73 / 4.38 / 6.04 | - |
| 11-day windows mean / median | +2.53% / -0.44% | +3.27% / +0.48% | +2.11% / -0.61% |
| 11-day win rate, >= +10%, <= -10% | 40%, 15%, 1.5% | 53%, 21%, 2.2% | -, 23%, 12% |
| thirds (default) | -5% / +53% / +14% | +2% / +81% / +3% | +12% / +61% / -23% |
| stress total, 11d mean | +30.3%, +1.52% | +20.2%, +1.50% | +4.2%, +0.92% |
| thirds (stress) | -10% / +37% / +6% | -14% / +53% / -8% | +1% / +44% / -28% |
| trades, win rate | 189, 31% | 352, 35% | - |
| turnover, fees | 116x, $8.9k | 258x, $20.0k | - |
| limit fill rate | 95% | 90% | n/a |
| share of days with a fill | 43% | 60% | 80% (start 1400) |
| P&L by side | long +$65.9k, no shorts | long +$89.2k, no shorts | long only |
| exits | 188 trailing stop, 1 cross-back | 352 trailing stop | - |
| look-ahead check (cuts=8) | pass | pass | - |

Robustness (start=1400, where candidate 1 is +73.8% / stress +37.6%, thirds +21/+22/+18, stress thirds +11/+12/+11; candidate 2 is
+84.9% / stress +24.8%, thirds +28/+31/+10, stress thirds +11/+13/-1):

| check | candidate_1 | candidate_2 |
|---|---|---|
| market entries instead of limits | +73.8% (stress +50.5%) | +80.1% (stress +41.2%) |
| six coarse-tick pairs removed | +31.9% (stress +9.5%), thirds +21/+16/-6 | +46.2% (stress +8.6%), thirds +39/+24/-16 |
| 8 slots instead of 4 | +30.0% (stress +11.2%), max DD 10.8% | +36.8% (stress +4.1%), max DD 16.1% |
| 30-day blocks positive | 5 of 8 | 5 of 8 |
| pairs traded / profitable | 49 / 22 | 50 / 22 |
| P&L without the 3 best pairs (default / stress) | +$10k / -$16k (best: TUT, STO, FIL) | +$27k / -$16k (best: STO, ZEC, TUT) |

The result does not depend on the maker fee (market entries are as good). It does depend on a few large winners, as
every trend rule does (win rate 31-35%); the benchmark breakout has the same property (without its 3 best pairs -$43k).
Activity: candidate 1 trades on 43% of days, below the competition's 8-of-14 requirement; candidate 2 is at 60%, just above it.

## Answers to the brief

1. Persistence: K-Means states last 9-51 h on average (stay-24h probability 0.37-0.84; 0.63-0.84 for K=2), HMM states 23-60 h (0.5-0.7),
   threshold states 9-184 h. Persistent enough to trade on.
2. Prediction: the largest |t| in about 900 state-level cells is 2.7 (and it is a negative mean-reversion pay-off); the top-minus-bottom difference in the 24h trend proxy is
   +14 to +28 bp (t 0.9-1.7) for the efficiency-ratio based labelings and about zero for cross counts and variance ratio; the
   mean-reversion proxy is negative in the chop state too (-16 to -36 bp at 24h; long side t down to -2.6). By thirds the
   signs are mostly consistent but no third is individually significant.
3. Gating: see the tables. Chop gate on z-score MR: no value (long: -3 bp/trade against the shift placebo, better in 8/21;
   every variant loses). Trend gate on EMA long: no value at freshness 3 (no trades) or without a freshness limit;
   +57 bp/trade over the shift placebo (8/9) and +53 over the coin-permuted placebo (9/9) at freshness 24.
4. Direction in the trend state: only the long side carries information from the label. Short side at freshness 24:
   +4 bp/trade over the shift placebo (5/9), 4/9 positive at default costs, 0/9 at stress.

## What failed

Mean reversion in any state; shorting spikes (-25 to -110 bp per trade everywhere, worst in the trend state); EMA entries
at the cross with a trend gate; EMA entries late in an established trend; HMM smoothing; K = 3 or 4 (no cleaner than K = 2);
the directional clusters (`dir3`: one positive cell, "short the rallies in the downtrend cluster" +9% with K-Means, -21% with
the HMM on the same features: noise); cross counts, variance ratio and autocorrelation as trend/chop features (no predictive
content at all).

## Recommendation

- If the team keeps the regime-switching design: trend state -> EMA 24/100 long, entries only 6-24 h after the cross
  (candidate 1); chop state -> cash. Drop the mean-reversion leg and the shorts: neither has evidence here.
- Candidate 2 is the same rule without the classifier and is the one I would rather run: nothing to refit, same or
  better numbers, more active days.
- Size expectations from the plateau, not the peak: roughly +1.5% to +2.5% per 11 days on average at default costs, +0.5% to +1.2% at
  stress, median near zero, and a 10-20% chance of +10% or better in a given 11-day window (design data). Both candidates
  share their edge and their winners with the breakout benchmark; they are not a diversifier for it.
- What would have to be true for the full switching design to work: mean reversion would need a positive expectancy
  somewhere, and in this sample it has none.

## Files

`tc.py` features and labels; `gen_labels.py`; `describe.py` -> `describe.md` (full predictive tables); `gate_bt.py` ->
`results.jsonl`; `tables.py` -> `tables_f3.md`, `tables_f24.md`, `tables_f1000000.md` (full gating grids); `final.py` ->
`final.jsonl`, `candidate_1.json`, `candidate_2.json`; `candidate_1.py`, `candidate_2.py`.

# Appendix A - gating grids (start=1400)

## Freshness 3 (reference setting)

### EL: EmaCross(24,100) LONG, limit entry (f3). Gate = trend (top state)
Gated columns: total | maxDD | 11d mean / median | thirds | stress total | trades | avg net bp per trade. Others: total / avg bp per trade / trades.
| labeling | gated: total | maxDD | 11d mean/med | thirds | stress | trades | bp/trade | inverse gate | placebo shift-1000 | placebo coin-permuted | middle state |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UNGATED | -48% | 58% | -2.3% / -3.8% | -5% -44% -2% | -75% | 687 | -32 | - | - | - | - |
| core4-2-km | -1% | 9% | -0.0% / +0.0% | -2% +1% +0% | -4% | 40 | -2 | -45% / -29bp / n683 | -40% / -56bp / n338 | -37% / -49bp / n336 | - |
| core4-3-km | -1% | 9% | -0.0% / +0.0% | -1% -3% +3% | -4% | 26 | -17 | -34% / -41bp / n379 | -33% / -49bp / n299 | -19% / -25bp / n271 | - |
| core4-4-km | +1% | 5% | +0.0% / +0.0% | +1% +2% -2% | -0% | 9 | +41 | -37% / -42bp / n410 | -2% / +3bp / n189 | -2% / +3bp / n172 | - |
| agn8-2-km | -0% | 12% | +0.1% / -0.4% | -2% -0% +2% | -12% | 69 | +3 | -47% / -32bp / n681 | -35% / -42bp / n367 | -30% / -31bp / n385 | - |
| agn8-3-km | -3% | 11% | -0.1% / +0.0% | -5% -1% +3% | -10% | 49 | -21 | -17% / -8bp / n507 | -21% / -25bp / n310 | -22% / -28bp / n303 | - |
| agn8-4-km | +4% | 6% | +0.2% / +0.0% | -0% +2% +3% | +2% | 20 | +84 | -27% / -15bp / n567 | -18% / -34bp / n184 | -17% / -41bp / n162 | - |
| all15-3-km | -19% | 22% | -0.9% / +0.0% | -10% -10% +1% | -24% | 41 | -202 | -31% / -29bp / n443 | -20% / -29bp / n264 | -8% / -5bp / n266 | - |
| core4-2-hmm | -11% | 16% | -0.5% / -0.1% | +1% -11% -1% | -16% | 54 | -81 | -45% / -30bp / n679 | -46% / -51bp / n432 | -28% / -22bp / n459 | - |
| core4-3-hmm | -13% | 18% | -0.6% / -0.1% | -1% -13% +1% | -18% | 47 | -116 | -39% / -29bp / n570 | -47% / -65bp / n373 | -35% / -42bp / n353 | - |
| agn8-2-hmm | -18% | 25% | -0.8% / -0.8% | -11% -9% +1% | -28% | 115 | -67 | -45% / -30bp / n670 | -50% / -58bp / n434 | -21% / -13bp / n487 | - |
| agn8-3-hmm | -32% | 36% | -1.7% / -1.2% | -4% -23% -8% | -44% | 153 | -100 | -31% / -17bp / n632 | -34% / -54bp / n290 | -33% / -42bp / n330 | - |
| er72-0.5-thr | -20% | 37% | -0.6% / -2.3% | -15% -10% +5% | -43% | 311 | -21 | -34% / -21bp / n631 | -19% / -10bp / n500 | -33% / -28bp / n475 | - |
| er72-0.7-thr | -13% | 35% | -0.2% / -1.5% | -11% +3% -5% | -24% | 171 | -25 | -44% / -29bp / n672 | -29% / -32bp / n365 | -22% / -22bp / n323 | - |
| er168-0.5-thr | -48% | 57% | -2.6% / -3.5% | -7% -37% -12% | -64% | 343 | -71 | -29% / -16bp / n606 | -18% / -9bp / n506 | -29% / -24bp / n446 | - |
| er168-0.7-thr | -15% | 30% | -0.6% / -1.3% | +10% -11% -13% | -23% | 114 | -51 | -42% / -27bp / n664 | -14% / -12bp / n328 | -28% / -41bp / n290 | - |
| gapabs-0.5-thr | +1% | 1% | +0.1% / +0.0% | +0% +0% +1% | +1% | 2 | +237 | -48% / -32bp / n686 | -38% / -35bp / n482 | -23% / -16bp / n455 | - |
| edge-0.5-thr | -17% | 40% | -0.6% / -1.7% | -11% -17% +13% | -40% | 324 | -16 | -45% / -31bp / n641 | -43% / -39bp / n504 | -29% / -23bp / n476 | - |
| vr-0.5-thr | -38% | 51% | -1.8% / -2.9% | -10% -30% -1% | -60% | 415 | -40 | -36% / -31bp / n509 | -44% / -48bp / n459 | -41% / -43bp / n448 | - |
| cc24_168-0.5-thr | -34% | 52% | -1.6% / -2.7% | -0% -30% -6% | -57% | 354 | -44 | -30% / -20bp / n549 | -57% / -58bp / n543 | -24% / -14bp / n523 | - |
| dir3-3-km | -11% | 33% | -0.1% / -1.8% | -2% -5% -5% | -30% | 235 | -11 | -9% / -265bp / n15 | -21% / -34bp / n232 | -34% / -52bp / n306 | -42% / -28bp / n661 |
| dir3-3-hmm | -9% | 31% | -0.2% / -1.2% | +7% -17% +2% | -35% | 277 | -8 | -2% / -75bp / n10 | -31% / -51bp / n268 | -31% / -40bp / n338 | -44% / -30bp / n651 |

Per-trade edge of the real gate over: shift placebo median +7 bp (better in 13/21); coin-permuted placebo median +6 bp (12/21); inverse gate median -0 bp (10/21). Ungated: -32 bp/trade.
Gated variants with positive total return: 3/21; positive under stress costs: 2/21.

### ES: EmaCross(24,100) SHORT (f3). Gate = trend (top state)
Gated columns: total | maxDD | 11d mean / median | thirds | stress total | trades | avg net bp per trade. Others: total / avg bp per trade / trades.
| labeling | gated: total | maxDD | 11d mean/med | thirds | stress | trades | bp/trade | inverse gate | placebo shift-1000 | placebo coin-permuted | middle state |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UNGATED | +6% | 24% | +0.7% / -0.2% | -11% +18% +1% | -35% | 620 | +9 | - | - | - | - |
| core4-2-km | -1% | 9% | -0.0% / +0.0% | -1% +0% +0% | -2% | 8 | -40 | +2% / +6bp / n619 | +5% / +9bp / n323 | -26% / -31bp / n352 | - |
| core4-3-km | -1% | 8% | -0.0% / +0.0% | -1% +0% +0% | -1% | 5 | -57 | -2% / +2bp / n359 | +21% / +31bp / n288 | -27% / -37bp / n305 | - |
| core4-4-km | +3% | 7% | +0.1% / +0.0% | +0% +3% +0% | +3% | 4 | +334 | -15% / -14bp / n367 | -0% / +3bp / n185 | +6% / +17bp / n199 | - |
| agn8-2-km | -0% | 10% | +0.0% / +0.0% | -1% +3% -3% | -2% | 21 | -2 | +2% / +6bp / n620 | +27% / +32bp / n351 | -18% / -15bp / n398 | - |
| agn8-3-km | +4% | 7% | +0.2% / +0.0% | +0% +5% -1% | +3% | 10 | +170 | +3% / +7bp / n477 | +14% / +23bp / n302 | -20% / -21bp / n335 | - |
| agn8-4-km | +5% | 7% | +0.2% / +0.0% | +0% +5% +0% | +5% | 2 | +1052 | +6% / +9bp / n536 | +3% / +11bp / n180 | -22% / -53bp / n178 | - |
| all15-3-km | -7% | 8% | -0.3% / +0.0% | +1% -5% -3% | -11% | 20 | -139 | +23% / +26bp / n402 | -12% / -16bp / n265 | -35% / -56bp / n290 | - |
| core4-2-hmm | +4% | 11% | +0.2% / +0.0% | -2% +6% -0% | +1% | 32 | +53 | +4% / +7bp / n612 | +17% / +21bp / n401 | -10% / -6bp / n437 | - |
| core4-3-hmm | +5% | 9% | +0.2% / +0.0% | +0% +6% -1% | +3% | 21 | +98 | +12% / +12bp / n547 | +26% / +32bp / n351 | -11% / -8bp / n368 | - |
| agn8-2-hmm | -2% | 16% | -0.0% / +0.0% | -4% -4% +7% | -11% | 80 | -10 | +11% / +11bp / n615 | +30% / +31bp / n410 | -14% / -8bp / n468 | - |
| agn8-3-hmm | -15% | 15% | -0.5% / -0.5% | -5% -4% -6% | -22% | 106 | -57 | +7% / +9bp / n592 | -2% / +1bp / n292 | -28% / -40bp / n311 | - |
| er72-0.5-thr | -30% | 33% | -1.5% / -1.6% | -14% -6% -14% | -44% | 243 | -57 | +3% / +7bp / n592 | +3% / +6bp / n451 | -32% / -26bp / n497 | - |
| er72-0.7-thr | -12% | 16% | -0.5% / -0.5% | -12% +3% -4% | -18% | 91 | -56 | +10% / +11bp / n611 | -15% / -17bp / n334 | -23% / -28bp / n343 | - |
| er168-0.5-thr | -3% | 26% | +0.0% / -0.8% | -13% -0% +12% | -27% | 325 | -0 | +7% / +10bp / n561 | -12% / -8bp / n454 | +8% / +12bp / n452 | - |
| er168-0.7-thr | +4% | 12% | +0.3% / +0.0% | -1% +5% +1% | -8% | 124 | +14 | +2% / +6bp / n605 | +23% / +31bp / n317 | +22% / +31bp / n313 | - |
| gapabs-0.5-thr | +5% | 7% | +0.2% / +0.0% | +0% +3% +2% | +5% | 3 | +638 | +6% / +9bp / n620 | +3% / +7bp / n461 | -34% / -35bp / n436 | - |
| edge-0.5-thr | -14% | 28% | -0.5% / -1.3% | -12% -6% +3% | -34% | 301 | -17 | +22% / +18bp / n585 | +13% / +16bp / n476 | +11% / +15bp / n464 | - |
| vr-0.5-thr | +2% | 20% | +0.2% / -1.0% | -2% -2% +5% | -26% | 420 | +5 | -10% / -5bp / n469 | -4% / +0bp / n454 | -13% / -11bp / n416 | - |
| cc24_168-0.5-thr | -5% | 23% | -0.0% / -0.3% | -12% -3% +11% | -24% | 283 | -4 | -2% / +2bp / n523 | +14% / +14bp / n501 | +4% / +6bp / n498 | - |
| dir3-3-km | +2% | 5% | +0.1% / +0.0% | +1% +2% -1% | -1% | 8 | +106 | -4% / -6bp / n124 | -1% / -0bp / n212 | -35% / -66bp / n252 | +9% / +10bp / n611 |
| dir3-3-hmm | -2% | 4% | -0.1% / +0.0% | -0% -2% +0% | -6% | 30 | -28 | +17% / +53bp / n136 | +10% / +17bp / n253 | -38% / -59bp / n312 | +12% / +12bp / n606 |

Per-trade edge of the real gate over: shift placebo median -18 bp (better in 9/21); coin-permuted placebo median -2 bp (10/21); inverse gate median -8 bp (9/21). Ungated: +9 bp/trade.
Gated variants with positive total return: 9/21; positive under stress costs: 6/21.

### ML: ZScoreMR(48,2) LONG, limit entry (f3). Gate = chop (bottom state)
Gated columns: total | maxDD | 11d mean / median | thirds | stress total | trades | avg net bp per trade. Others: total / avg bp per trade / trades.
| labeling | gated: total | maxDD | 11d mean/med | thirds | stress | trades | bp/trade | inverse gate | placebo shift-1000 | placebo coin-permuted | middle state |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UNGATED | -42% | 56% | -2.0% / -1.4% | +13% -11% -43% | -81% | 838 | -22 | - | - | - | - |
| core4-2-km | -57% | 65% | -3.2% / -2.8% | +3% -33% -38% | -84% | 723 | -43 | -49% / -42bp / n576 | -55% / -45bp / n638 | -57% / -42bp / n743 | - |
| core4-3-km | -54% | 60% | -3.1% / -2.6% | +0% -25% -39% | -79% | 634 | -45 | -33% / -26bp / n525 | -49% / -46bp / n537 | -60% / -52bp / n655 | - |
| core4-4-km | -56% | 62% | -3.3% / -3.8% | +5% -39% -31% | -78% | 524 | -59 | -26% / -23bp / n442 | -56% / -64bp / n477 | -55% / -54bp / n559 | - |
| agn8-2-km | -61% | 68% | -3.8% / -3.1% | -4% -40% -33% | -85% | 681 | -53 | -57% / -48bp / n635 | -48% / -38bp / n616 | -60% / -46bp / n733 | - |
| agn8-3-km | -59% | 64% | -3.5% / -3.0% | -6% -28% -39% | -81% | 599 | -55 | -49% / -44bp / n568 | -47% / -39bp / n576 | -65% / -59bp / n667 | - |
| agn8-4-km | -37% | 43% | -1.6% / -1.1% | -16% -3% -22% | -68% | 497 | -33 | -36% / -45bp / n367 | -44% / -42bp / n502 | -62% / -64bp / n585 | - |
| all15-3-km | -64% | 68% | -4.1% / -3.4% | -7% -36% -39% | -85% | 668 | -57 | -32% / -27bp / n474 | -51% / -45bp / n581 | -60% / -52bp / n662 | - |
| core4-2-hmm | -51% | 59% | -2.8% / -1.7% | +0% -31% -29% | -79% | 661 | -39 | -49% / -35bp / n681 | -40% / -30bp / n573 | -65% / -59bp / n666 | - |
| core4-3-hmm | -47% | 55% | -2.4% / -1.6% | -2% -17% -35% | -79% | 614 | -38 | -47% / -38bp / n606 | -35% / -29bp / n506 | -52% / -44bp / n611 | - |
| agn8-2-hmm | -56% | 63% | -3.2% / -2.2% | -1% -38% -28% | -82% | 641 | -48 | -54% / -40bp / n695 | -48% / -42bp / n555 | -62% / -55bp / n666 | - |
| agn8-3-hmm | -36% | 48% | -1.6% / -0.7% | -1% -17% -22% | -72% | 574 | -27 | -47% / -46bp / n508 | -47% / -45bp / n503 | -67% / -69bp / n613 | - |
| er72-0.5-thr | -61% | 65% | -3.6% / -2.8% | -3% -30% -42% | -81% | 628 | -57 | -39% / -25bp / n692 | -55% / -41bp / n690 | -68% / -61bp / n704 | - |
| er72-0.7-thr | -65% | 71% | -4.1% / -2.9% | -4% -32% -46% | -84% | 726 | -55 | -41% / -35bp / n529 | -54% / -36bp / n756 | -60% / -44bp / n772 | - |
| er168-0.5-thr | -56% | 61% | -3.2% / -2.7% | -16% -30% -26% | -80% | 644 | -48 | -55% / -42bp / n690 | -57% / -45bp / n684 | -64% / -56bp / n677 | - |
| er168-0.7-thr | -51% | 59% | -2.7% / -1.8% | +4% -35% -27% | -83% | 739 | -35 | -52% / -49bp / n562 | -49% / -32bp / n758 | -53% / -36bp / n750 | - |
| gapabs-0.5-thr | -48% | 58% | -2.4% / -2.0% | +9% -27% -34% | -75% | 678 | -35 | -52% / -41bp / n653 | -45% / -31bp / n656 | -63% / -54bp / n694 | - |
| edge-0.5-thr | -42% | 49% | -1.9% / -1.5% | -1% -20% -27% | -72% | 566 | -35 | -54% / -42bp / n681 | -56% / -43bp / n687 | -57% / -44bp / n691 | - |
| vr-0.5-thr | -50% | 59% | -2.7% / -2.2% | +0% -16% -41% | -81% | 711 | -35 | -47% / -36bp / n649 | -48% / -33bp / n678 | -47% / -33bp / n686 | - |
| cc24_168-0.5-thr | -57% | 62% | -3.4% / -3.0% | -14% -30% -29% | -80% | 611 | -52 | -38% / -22bp / n747 | -49% / -38bp / n633 | -58% / -53bp / n613 | - |
| dir3-3-km | -43% | 53% | -2.2% / -1.3% | -2% -3% -40% | -78% | 657 | -29 | -27% / -141bp / n90 | -66% / -90bp / n453 | -39% / -33bp / n529 | -61% / -60bp / n604 |
| dir3-3-hmm | -53% | 61% | -3.2% / -2.0% | -9% -11% -42% | -79% | 662 | -41 | -35% / -67bp / n248 | -55% / -65bp / n473 | -47% / -42bp / n550 | -41% / -34bp / n565 |

Per-trade edge of the real gate over: shift placebo median -3 bp (better in 8/21); coin-permuted placebo median +3 bp (15/21); inverse gate median -4 bp (9/21). Ungated: -22 bp/trade.
Gated variants with positive total return: 0/21; positive under stress costs: 0/21.

### MS: ZScoreMR(48,2) SHORT (f3). Gate = chop (bottom state)
Gated columns: total | maxDD | 11d mean / median | thirds | stress total | trades | avg net bp per trade. Others: total / avg bp per trade / trades.
| labeling | gated: total | maxDD | 11d mean/med | thirds | stress | trades | bp/trade | inverse gate | placebo shift-1000 | placebo coin-permuted | middle state |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UNGATED | -87% | 92% | -6.9% / -4.9% | -60% -71% +10% | -95% | 1126 | -71 | - | - | - | - |
| core4-2-km | -62% | 73% | -3.5% / -4.1% | -48% -25% -2% | -82% | 897 | -39 | -87% / -104bp / n750 | -69% / -55bp / n805 | -89% / -85bp / n994 | - |
| core4-3-km | -36% | 53% | -1.4% / -1.5% | -42% +4% +5% | -66% | 763 | -19 | -80% / -90bp / n685 | -56% / -51bp / n612 | -84% / -85bp / n844 | - |
| core4-4-km | -54% | 61% | -3.2% / -2.4% | -45% -7% -10% | -73% | 655 | -43 | -78% / -97bp / n591 | -41% / -37bp / n511 | -68% / -61bp / n707 | - |
| agn8-2-km | -57% | 67% | -2.9% / -2.9% | -41% -21% -6% | -79% | 839 | -36 | -87% / -93bp / n838 | -57% / -42bp / n752 | -87% / -79bp / n979 | - |
| agn8-3-km | -63% | 67% | -3.8% / -5.7% | -52% -6% -19% | -81% | 759 | -49 | -83% / -90bp / n750 | -42% / -31bp / n629 | -83% / -81bp / n830 | - |
| agn8-4-km | -55% | 57% | -2.9% / -4.1% | -37% -12% -19% | -74% | 636 | -47 | -81% / -114bp / n564 | -35% / -27bp / n568 | -72% / -65bp / n745 | - |
| all15-3-km | -41% | 54% | -2.0% / -2.5% | -35% -11% +1% | -69% | 757 | -24 | -82% / -101bp / n663 | -39% / -29bp / n610 | -84% / -87bp / n829 | - |
| core4-2-hmm | -70% | 75% | -4.6% / -4.5% | -53% -29% -10% | -85% | 822 | -55 | -85% / -83bp / n889 | -51% / -39bp / n671 | -75% / -64bp / n827 | - |
| core4-3-hmm | -61% | 64% | -3.6% / -3.7% | -45% -10% -21% | -79% | 727 | -48 | -79% / -77bp / n782 | -57% / -52bp / n607 | -79% / -76bp / n765 | - |
| agn8-2-hmm | -59% | 64% | -3.3% / -3.6% | -35% -22% -19% | -78% | 764 | -43 | -89% / -89bp / n947 | -39% / -27bp / n652 | -84% / -81bp / n853 | - |
| agn8-3-hmm | -60% | 63% | -3.4% / -3.1% | -42% -16% -18% | -78% | 682 | -50 | -77% / -78bp / n727 | -19% / -9bp / n567 | -68% / -56bp / n750 | - |
| er72-0.5-thr | -47% | 54% | -2.2% / -2.2% | -34% -10% -12% | -71% | 745 | -31 | -86% / -84bp / n920 | -64% / -43bp / n873 | -90% / -100bp / n901 | - |
| er72-0.7-thr | -47% | 62% | -2.3% / -2.7% | -43% -11% +4% | -74% | 873 | -25 | -88% / -109bp / n758 | -76% / -55bp / n1001 | -86% / -77bp / n1002 | - |
| er168-0.5-thr | -62% | 68% | -3.6% / -2.1% | -38% -32% -9% | -80% | 746 | -48 | -83% / -75bp / n924 | -65% / -47bp / n813 | -80% / -73bp / n856 | - |
| er168-0.7-thr | -73% | 82% | -5.0% / -5.1% | -47% -46% -8% | -88% | 913 | -55 | -75% / -72bp / n737 | -76% / -56bp / n975 | -88% / -82bp / n1004 | - |
| gapabs-0.5-thr | -65% | 74% | -3.9% / -4.0% | -42% -39% +0% | -83% | 883 | -44 | -84% / -87bp / n826 | -66% / -50bp / n823 | -80% / -72bp / n846 | - |
| edge-0.5-thr | -43% | 55% | -1.9% / -2.1% | -20% -27% -3% | -70% | 723 | -27 | -91% / -100bp / n940 | -68% / -50bp / n860 | -71% / -50bp / n914 | - |
| vr-0.5-thr | -81% | 85% | -6.3% / -5.2% | -55% -51% -16% | -91% | 902 | -72 | -47% / -30bp / n756 | -69% / -52bp / n829 | -81% / -78bp / n828 | - |
| cc24_168-0.5-thr | -68% | 75% | -4.6% / -3.9% | -37% -47% -4% | -83% | 716 | -60 | -81% / -66bp / n934 | -75% / -70bp / n761 | -66% / -54bp / n745 | - |
| dir3-3-km | +9% | 11% | +0.4% / +0.2% | -2% +4% +7% | -4% | 143 | +26 | -88% / -95bp / n866 | -54% / -62bp / n467 | -35% / -29bp / n515 | -43% / -27bp / n722 |
| dir3-3-hmm | -21% | 30% | -0.9% / -1.5% | -14% -12% +4% | -39% | 292 | -31 | -90% / -102bp / n882 | -66% / -82bp / n506 | -74% / -80bp / n650 | -60% / -52bp / n654 |

Per-trade edge of the real gate over: shift placebo median +5 bp (better in 13/21); coin-permuted placebo median +29 bp (20/21); inverse gate median +53 bp (20/21). Ungated: -71 bp/trade.
Gated variants with positive total return: 1/21; positive under stress costs: 0/21.

N results in file: 610

## Freshness 24
### EL: EmaCross(24,100) LONG, limit entry (f24). Gate = trend (top state)
Gated columns: total | maxDD | 11d mean / median | thirds | stress total | trades | avg net bp per trade. Others: total / avg bp per trade / trades.
| labeling | gated: total | maxDD | 11d mean/med | thirds | stress | trades | bp/trade | inverse gate | placebo shift-1000 | placebo coin-permuted | middle state |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UNGATED | -40% | 58% | -1.3% / -3.7% | -5% -27% -14% | -80% | 963 | -13 | - | - | - | - |
| core4-2-km | +36% | 28% | +2.0% / -0.2% | +29% +7% -2% | +3% | 281 | +57 | -54% / -26bp / n953 | -15% / -4bp / n559 | -60% / -55bp / n615 | - |
| agn8-2-km | +31% | 33% | +2.0% / -0.0% | +25% +15% -9% | -5% | 357 | +43 | -48% / -21bp / n941 | -28% / -13bp / n600 | -56% / -42bp / n694 | - |
| agn8-3-km | +36% | 28% | +2.1% / +0.0% | +33% +8% -5% | -1% | 280 | +59 | -55% / -37bp / n772 | -23% / -14bp / n520 | -49% / -42bp / n585 | - |
| core4-2-hmm | +19% | 36% | +1.6% / -0.6% | +30% +4% -12% | -15% | 347 | +35 | -63% / -36bp / n956 | -54% / -38bp / n684 | -38% / -18bp / n765 | - |
| agn8-2-hmm | -12% | 44% | +0.2% / -2.3% | +6% +5% -22% | -44% | 443 | -0 | -57% / -30bp / n946 | -44% / -27bp / n675 | -39% / -18bp / n800 | - |
| er72-0.7-thr | +2% | 36% | +0.8% / -0.4% | +15% -2% -10% | -36% | 425 | +13 | -47% / -20bp / n946 | -25% / -11bp / n631 | -35% / -23bp / n601 | - |
| er168-0.5-thr | -39% | 50% | -1.5% / -3.0% | -4% -28% -12% | -68% | 654 | -23 | -51% / -25bp / n889 | -29% / -9bp / n781 | -53% / -32bp / n772 | - |
| gapabs-0.5-thr | +52% | 27% | +2.6% / +0.6% | +43% -0% +7% | -4% | 354 | +60 | -49% / -21bp / n956 | -52% / -31bp / n755 | -31% / -13bp / n738 | - |
| edge-0.5-thr | -9% | 46% | +0.5% / -2.0% | +16% -12% -11% | -56% | 676 | +2 | -66% / -41bp / n907 | -41% / -20bp / n794 | -24% / -7bp / n800 | - |

Per-trade edge of the real gate over: shift placebo median +57 bp (better in 8/9); coin-permuted placebo median +53 bp (9/9); inverse gate median +64 bp (9/9). Ungated: -13 bp/trade.
Gated variants with positive total return: 6/9; positive under stress costs: 1/9.

### ES: EmaCross(24,100) SHORT (f24). Gate = trend (top state)
Gated columns: total | maxDD | 11d mean / median | thirds | stress total | trades | avg net bp per trade. Others: total / avg bp per trade / trades.
| labeling | gated: total | maxDD | 11d mean/med | thirds | stress | trades | bp/trade | inverse gate | placebo shift-1000 | placebo coin-permuted | middle state |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UNGATED | -25% | 38% | -0.8% / -1.8% | -28% +20% -13% | -64% | 899 | -9 | - | - | - | - |
| core4-2-km | -13% | 17% | -0.5% / -0.7% | -11% +2% -5% | -27% | 204 | -22 | -23% / -7bp / n895 | +12% / +14bp / n552 | -32% / -21bp / n618 | - |
| agn8-2-km | +24% | 19% | +1.1% / -0.2% | -11% +26% +11% | -1% | 278 | +39 | -25% / -9bp / n892 | +50% / +34bp / n574 | -25% / -12bp / n672 | - |
| agn8-3-km | -4% | 18% | +0.1% / -0.6% | -12% +10% -0% | -20% | 217 | +1 | -12% / -3bp / n752 | +8% / +12bp / n529 | -24% / -14bp / n597 | - |
| core4-2-hmm | -11% | 26% | -0.3% / -1.7% | -19% +12% -1% | -32% | 317 | -8 | -24% / -9bp / n892 | -0% / +5bp / n657 | -23% / -10bp / n719 | - |
| agn8-2-hmm | +21% | 19% | +1.3% / -0.5% | -11% +29% +4% | -11% | 341 | +29 | -28% / -11bp / n893 | +23% / +18bp / n639 | -5% / +2bp / n734 | - |
| er72-0.7-thr | -39% | 40% | -1.8% / -1.9% | -17% -8% -20% | -55% | 373 | -49 | -20% / -6bp / n886 | -13% / -5bp / n606 | -18% / -8bp / n619 | - |
| er168-0.5-thr | -7% | 44% | +0.0% / -1.0% | -33% +16% +20% | -40% | 550 | -2 | -11% / -0bp / n848 | -28% / -12bp / n742 | +1% / +6bp / n703 | - |
| gapabs-0.5-thr | +12% | 21% | +0.9% / -1.0% | -13% +30% -1% | -16% | 350 | +20 | -26% / -10bp / n887 | -1% / +4bp / n728 | -26% / -13bp / n701 | - |
| edge-0.5-thr | +39% | 18% | +2.1% / -0.3% | -5% +46% -0% | -11% | 544 | +30 | -31% / -13bp / n895 | +21% / +15bp / n750 | -9% / +0bp / n739 | - |

Per-trade edge of the real gate over: shift placebo median +4 bp (better in 5/9); coin-permuted placebo median +15 bp (6/9); inverse gate median +3 bp (6/9). Ungated: -9 bp/trade.
Gated variants with positive total return: 4/9; positive under stress costs: 0/9.


## No freshness limit
### EL: EmaCross(24,100) LONG, limit entry (f1000000). Gate = trend (top state)
Gated columns: total | maxDD | 11d mean / median | thirds | stress total | trades | avg net bp per trade. Others: total / avg bp per trade / trades.
| labeling | gated: total | maxDD | 11d mean/med | thirds | stress | trades | bp/trade | inverse gate | placebo shift-1000 | placebo coin-permuted | middle state |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UNGATED | -47% | 61% | -1.6% / -6.5% | -20% -8% -28% | -85% | 1193 | -14 | - | - | - | - |
| core4-2-km | -26% | 51% | -0.3% / -2.7% | -14% +18% -27% | -69% | 771 | -8 | -69% / -33bp / n1228 | -72% / -52bp / n894 | -62% / -31bp / n1053 | - |
| agn8-2-km | -23% | 52% | -0.1% / -2.5% | -11% +16% -26% | -70% | 836 | -4 | -73% / -37bp / n1217 | -67% / -42bp / n924 | -62% / -29bp / n1151 | - |
| agn8-3-km | -9% | 49% | +0.4% / -2.5% | +1% +24% -27% | -58% | 754 | +4 | -77% / -49bp / n1110 | -62% / -39bp / n851 | -57% / -29bp / n1032 | - |
| core4-2-hmm | -42% | 55% | -1.5% / -4.9% | -22% +1% -26% | -77% | 913 | -17 | -79% / -45bp / n1271 | -60% / -31bp / n956 | -62% / -26bp / n1180 | - |
| agn8-2-hmm | -48% | 61% | -1.9% / -5.6% | -21% -3% -32% | -81% | 954 | -20 | -79% / -47bp / n1237 | -55% / -26bp / n945 | -68% / -31bp / n1219 | - |
| er72-0.7-thr | -40% | 53% | -0.8% / -4.8% | -25% +9% -26% | -76% | 858 | -14 | -66% / -30bp / n1214 | -67% / -37bp / n1018 | -52% / -23bp / n1027 | - |
| er168-0.5-thr | -67% | 75% | -3.8% / -6.8% | -43% -28% -21% | -89% | 1066 | -35 | -47% / -17bp / n1177 | -58% / -23bp / n1148 | -53% / -21bp / n1134 | - |
| gapabs-0.5-thr | -30% | 50% | -0.8% / -2.9% | -15% +3% -19% | -72% | 856 | -10 | -70% / -33bp / n1261 | -68% / -32bp / n1117 | -61% / -26bp / n1189 | - |
| edge-0.5-thr | -36% | 62% | -0.8% / -3.8% | +25% -28% -29% | -80% | 1088 | -8 | -72% / -39bp / n1157 | -59% / -24bp / n1187 | -53% / -19bp / n1186 | - |
| dir3-3-km | -50% | 61% | -1.7% / -5.8% | -24% +4% -36% | -83% | 957 | -20 | -13% / -125bp / n45 | -53% / -40bp / n677 | -63% / -52bp / n733 | -74% / -39bp / n1239 |
| dir3-3-hmm | -42% | 56% | -1.2% / -5.3% | -24% -0% -23% | -80% | 1040 | -13 | -0% / -4bp / n39 | -49% / -33bp / n725 | -65% / -51bp / n794 | -79% / -42bp / n1327 |

Per-trade edge of the real gate over: shift placebo median +20 bp (better in 10/11); coin-permuted placebo median +17 bp (10/11); inverse gate median +27 bp (9/11). Ungated: -14 bp/trade.
Gated variants with positive total return: 0/11; positive under stress costs: 0/11.

### ES: EmaCross(24,100) SHORT (f1000000). Gate = trend (top state)
Gated columns: total | maxDD | 11d mean / median | thirds | stress total | trades | avg net bp per trade. Others: total / avg bp per trade / trades.
| labeling | gated: total | maxDD | 11d mean/med | thirds | stress | trades | bp/trade | inverse gate | placebo shift-1000 | placebo coin-permuted | middle state |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UNGATED | -59% | 64% | -3.4% / -4.1% | -45% -19% -8% | -86% | 1250 | -24 | - | - | - | - |
| core4-2-km | -45% | 51% | -2.0% / -3.5% | -31% -17% -3% | -74% | 874 | -22 | -45% / -15bp / n1245 | -22% / -5bp / n972 | -59% / -28bp / n1112 | - |
| agn8-2-km | -46% | 50% | -2.0% / -2.8% | -33% -16% -3% | -75% | 921 | -22 | -61% / -26bp / n1261 | -24% / -6bp / n986 | -58% / -26bp / n1165 | - |
| agn8-3-km | -51% | 54% | -2.3% / -3.5% | -31% -24% -6% | -76% | 869 | -28 | -48% / -18bp / n1189 | -29% / -9bp / n962 | -58% / -28bp / n1098 | - |
| core4-2-hmm | -55% | 57% | -2.8% / -4.2% | -38% -18% -13% | -81% | 1018 | -28 | -37% / -11bp / n1248 | -25% / -7bp / n1015 | -66% / -32bp / n1207 | - |
| agn8-2-hmm | -51% | 56% | -2.5% / -3.8% | -34% -21% -6% | -80% | 1036 | -23 | -47% / -16bp / n1259 | -37% / -13bp / n1030 | -56% / -23bp / n1213 | - |
| er72-0.7-thr | -58% | 58% | -3.1% / -3.5% | -29% -28% -17% | -81% | 931 | -33 | -52% / -20bp / n1242 | -35% / -12bp / n1082 | -52% / -21bp / n1155 | - |
| er168-0.5-thr | -44% | 52% | -2.0% / -2.8% | -41% -6% -0% | -78% | 1092 | -17 | -62% / -27bp / n1247 | -57% / -26bp / n1146 | -52% / -21bp / n1179 | - |
| gapabs-0.5-thr | -54% | 57% | -2.7% / -4.2% | -39% -18% -9% | -81% | 992 | -28 | -55% / -21bp / n1259 | -47% / -17bp / n1164 | -68% / -34bp / n1205 | - |
| edge-0.5-thr | -51% | 54% | -2.5% / -3.4% | -32% -13% -17% | -81% | 1120 | -22 | -47% / -16bp / n1261 | -66% / -31bp / n1213 | -55% / -22bp / n1223 | - |
| dir3-3-km | -14% | 17% | -0.6% / -0.2% | -1% -13% -0% | -24% | 143 | -41 | -45% / -19bp / n1025 | -32% / -17bp / n743 | -39% / -16bp / n1018 | -57% / -24bp / n1251 |
| dir3-3-hmm | -10% | 10% | -0.4% / -0.2% | -3% -5% -2% | -18% | 123 | -34 | -46% / -19bp / n1074 | -38% / -21bp / n812 | -47% / -18bp / n1106 | -51% / -17bp / n1299 |

Per-trade edge of the real gate over: shift placebo median -16 bp (better in 2/11); coin-permuted placebo median -0 bp (5/11); inverse gate median -8 bp (2/11). Ungated: -24 bp/trade.
Gated variants with positive total return: 0/11; positive under stress costs: 0/11.


# Appendix B - persistence and predictive content of every labeling

## Per-state table (bars 1400..7519). Payoffs in bp per trade-proxy, t from non-overlapping time samples
| labeling | state | freq | run h | stay24 | stay72 | trend24 bp (t) | trend72 bp (t) | long-side 72 (t) | short-side 72 (t) | MR24 bp (t) | MR72 bp (t) | MR long-side 24 (t) | trend24 by thirds bp | MR24 by thirds bp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | - | 1 | - | - | - | -4 (-0.2) | +17 (+0.4) | -22 (-0.3) | +40 (+0.5) | -21 (-0.8) | -8 (-0.1) | -18 (-0.6) | -28 / +6 / +7 | +23 / -57 / -6 |
| core4-2-km | 0 | 0.65 | 34 | 0.80 | 0.67 | -4 (-0.2) | +4 (+0.1) | -46 (-0.6) | +46 (+0.6) | -16 (-0.7) | +20 (+0.3) | -38 (-1.3) | -33 / -1 / +15 | +38 / -41 / -45 |
| core4-2-km | 1 | 0.35 | 18 | 0.63 | 0.39 | +11 (+0.5) | +62 (+1.0) | -58 (-0.5) | +75 (+0.8) | -46 (-1.3) | -78 (-0.8) | -22 (-0.5) | -32 / +49 / +3 | +16 / -101 / +24 |
| core4-3-km | 0 | 0.41 | 27 | 0.70 | 0.49 | -4 (-0.2) | -27 (-0.5) | -93 (-1.1) | +58 (+0.7) | -28 (-1.2) | +2 (+0.0) | -64 (-2.0) | -29 / -1 / +8 | +19 / -62 / -21 |
| core4-3-km | 1 | 0.30 | 31 | 0.71 | 0.51 | -4 (-0.2) | -14 (-0.2) | -68 (-0.7) | +43 (+0.5) | -28 (-1.0) | +26 (+0.3) | -46 (-1.4) | -53 / +42 / -12 | +48 / -71 / -56 |
| core4-3-km | 2 | 0.29 | 16 | 0.59 | 0.31 | +9 (+0.4) | +66 (+1.0) | +33 (+0.2) | +61 (+0.6) | -28 (-0.7) | -47 (-0.5) | -14 (-0.3) | -29 / +46 / +8 | +33 / -94 / +21 |
| core4-4-km | 0 | 0.30 | 19 | 0.60 | 0.38 | -13 (-0.7) | -30 (-0.5) | -96 (-1.3) | +8 (+0.1) | -28 (-1.1) | -31 (-0.4) | -68 (-1.9) | -30 / +17 / -55 | +27 / -63 / +14 |
| core4-4-km | 1 | 0.31 | 21 | 0.63 | 0.44 | -4 (-0.2) | +1 (+0.0) | +23 (+0.2) | +87 (+1.0) | -21 (-0.8) | +47 (+0.5) | -47 (-1.5) | -53 / +9 / +9 | +56 / -55 / -58 |
| core4-4-km | 2 | 0.19 | 9 | 0.37 | 0.21 | -13 (-0.5) | -130 (-1.6) | -192 (-1.5) | -110 (-0.9) | -30 (-0.9) | +117 (+1.2) | -44 (-1.0) | -30 / -18 / +23 | +6 / -85 / -42 |
| core4-4-km | 3 | 0.20 | 14 | 0.54 | 0.23 | +9 (+0.3) | +84 (+1.0) | +7 (+0.0) | +174 (+1.8) | -20 (-0.4) | -152 (-1.2) | -47 (-0.7) | -32 / +28 / +10 | +87 / -59 / -3 |
| agn8-2-km | 0 | 0.61 | 25 | 0.76 | 0.62 | -4 (-0.2) | -3 (-0.1) | -56 (-0.8) | +38 (+0.5) | -22 (-1.0) | +37 (+0.5) | -40 (-1.4) | -27 / -7 / +17 | +36 / -38 / -49 |
| agn8-2-km | 1 | 0.39 | 16 | 0.63 | 0.42 | +9 (+0.4) | +71 (+1.1) | +63 (+0.4) | +86 (+0.9) | -36 (-1.1) | -93 (-1.0) | -14 (-0.3) | -30 / +46 / +15 | +0 / -88 / +4 |
| agn8-3-km | 0 | 0.42 | 22 | 0.73 | 0.56 | -4 (-0.2) | -6 (-0.1) | -56 (-0.7) | +74 (+0.8) | -21 (-0.9) | +14 (+0.2) | -49 (-1.7) | -33 / +3 / +10 | +13 / -6 / -53 |
| agn8-3-km | 1 | 0.26 | 18 | 0.67 | 0.47 | -20 (-0.9) | -60 (-0.9) | -17 (-0.2) | -98 (-0.9) | -10 (-0.3) | +84 (+0.9) | -2 (-0.1) | -44 / -41 / +21 | +67 / -130 / -39 |
| agn8-3-km | 2 | 0.31 | 14 | 0.58 | 0.34 | +18 (+0.7) | +77 (+1.1) | +87 (+0.6) | +47 (+0.4) | -47 (-1.2) | -83 (-0.8) | +7 (+0.1) | -26 / +57 / +27 | +29 / -108 / -4 |
| agn8-4-km | 0 | 0.33 | 15 | 0.63 | 0.43 | +4 (+0.2) | +24 (+0.5) | -18 (-0.2) | +84 (+0.9) | -50 (-2.1) | +33 (+0.4) | -77 (-2.6) | -15 / +3 / +24 | -17 / -36 / -50 |
| agn8-4-km | 1 | 0.23 | 15 | 0.64 | 0.43 | -16 (-0.7) | -73 (-1.0) | -39 (-0.4) | -44 (-0.4) | -5 (-0.2) | +39 (+0.4) | -5 (-0.1) | -59 / -61 / +11 | +50 / -42 / -49 |
| agn8-4-km | 2 | 0.28 | 10 | 0.52 | 0.37 | +17 (+0.7) | +39 (+0.6) | -16 (-0.1) | +69 (+0.7) | -27 (-0.9) | -41 (-0.4) | -34 (-0.8) | -18 / +16 / +64 | +36 / -10 / -69 |
| agn8-4-km | 3 | 0.16 | 13 | 0.49 | 0.19 | +16 (+0.5) | +44 (+0.5) | -11 (-0.1) | +98 (+0.8) | -42 (-0.8) | -39 (-0.3) | -20 (-0.3) | -10 / +9 / -0 | +25 / -54 / +66 |
| agn10v-2-km | 0 | 0.61 | 26 | 0.76 | 0.63 | -4 (-0.2) | +2 (+0.0) | -57 (-0.8) | +38 (+0.5) | -23 (-1.0) | +33 (+0.5) | -45 (-1.6) | -24 / -3 / +13 | +30 / -43 / -44 |
| agn10v-2-km | 1 | 0.39 | 16 | 0.62 | 0.41 | +12 (+0.5) | +71 (+1.1) | +57 (+0.4) | +71 (+0.7) | -37 (-1.1) | -99 (-0.9) | -2 (-0.0) | -28 / +46 / +18 | +5 / -87 / -0 |
| agn10v-3-km | 0 | 0.42 | 22 | 0.73 | 0.56 | -4 (-0.2) | -13 (-0.3) | -37 (-0.5) | +40 (+0.5) | -23 (-1.0) | +13 (+0.2) | -44 (-1.5) | -31 / +3 / +16 | +10 / -35 / -55 |
| agn10v-3-km | 1 | 0.26 | 18 | 0.67 | 0.47 | -21 (-0.9) | -33 (-0.5) | -40 (-0.4) | -82 (-0.8) | -2 (-0.1) | +75 (+0.8) | -7 (-0.2) | -45 / -67 / +16 | +72 / -28 / -39 |
| agn10v-3-km | 2 | 0.31 | 14 | 0.58 | 0.35 | +22 (+0.9) | +83 (+1.2) | -16 (-0.1) | +98 (+0.9) | -40 (-1.0) | -86 (-0.8) | -20 (-0.4) | -17 / +66 / +14 | +33 / -136 / +19 |
| agn10v-4-km | 0 | 0.33 | 15 | 0.62 | 0.44 | +17 (+0.8) | +25 (+0.5) | -24 (-0.3) | +133 (+1.5) | -46 (-1.9) | +25 (+0.3) | -86 (-2.7) | -7 / +22 / +23 | -6 / -34 / -53 |
| agn10v-4-km | 1 | 0.23 | 16 | 0.65 | 0.44 | -41 (-1.7) | -52 (-0.7) | -40 (-0.4) | +3 (+0.0) | +20 (+0.7) | +46 (+0.5) | +10 (+0.2) | -42 / -68 / +19 | +42 / -20 / -39 |
| agn10v-4-km | 2 | 0.28 | 10 | 0.51 | 0.36 | +10 (+0.4) | +35 (+0.6) | -87 (-0.7) | +71 (+0.7) | -21 (-0.7) | -66 (-0.7) | -32 (-0.8) | -21 / +15 / +61 | +26 / -18 / -62 |
| agn10v-4-km | 3 | 0.16 | 12 | 0.49 | 0.19 | +18 (+0.5) | +100 (+1.1) | +172 (+0.8) | +141 (+1.2) | -46 (-0.8) | -116 (-0.9) | -21 (-0.3) | -29 / +49 / -12 | +47 / -87 / +101 |
| dir3-2-km | 0 | 0.62 | 51 | 0.84 | 0.71 | -2 (-0.1) | +32 (+0.5) | -72 (-0.6) | +27 (+0.3) | -28 (-0.9) | -11 (-0.2) | -31 (-0.8) | -56 / +26 / +18 | +29 / -67 / -19 |
| dir3-2-km | 1 | 0.38 | 31 | 0.74 | 0.53 | +10 (+0.5) | -8 (-0.1) | -15 (-0.2) | +38 (+0.1) | -58 (-1.7) | +7 (+0.1) | -66 (-2.2) | +6 / +40 / -18 | +10 / -164 / -14 |
| dir3-3-km | 0 | 0.32 | 17 | 0.65 | 0.37 | +25 (+0.8) | +77 (+0.9) | +nan (+nan) | +77 (+0.9) | -19 (-0.5) | -101 (-0.9) | -24 (-0.5) | -23 / +60 / +46 | +66 / -67 / -35 |
| dir3-3-km | 1 | 0.47 | 14 | 0.61 | 0.46 | -6 (-0.3) | +3 (+0.1) | -68 (-0.9) | +57 (+0.7) | -29 (-1.3) | +19 (+0.3) | -46 (-1.5) | -25 / -19 / +3 | +13 / -37 / -43 |
| dir3-3-km | 2 | 0.21 | 14 | 0.59 | 0.29 | -9 (-0.3) | +10 (+0.1) | +7 (+0.1) | +nan (+nan) | -77 (-1.2) | -161 (-0.7) | -65 (-1.4) | -24 / +106 / -64 | +36 / -291 / +12 |
| dir3-4-km | 0 | 0.24 | 13 | 0.57 | 0.25 | +2 (+0.0) | +15 (+0.1) | +nan (+nan) | +15 (+0.1) | -2 (-0.0) | -14 (-0.1) | -1 (-0.0) | -71 / +21 / +28 | +65 / -43 / -3 |
| dir3-4-km | 1 | 0.36 | 12 | 0.53 | 0.40 | +7 (+0.3) | +78 (+1.2) | -4 (-0.0) | +80 (+1.0) | -46 (-1.7) | -57 (-0.8) | -55 (-1.6) | -57 / +35 / +29 | +23 / -85 / -62 |
| dir3-4-km | 2 | 0.28 | 11 | 0.51 | 0.33 | -1 (-0.0) | -50 (-0.8) | -49 (-0.7) | -45 (-0.2) | -49 (-1.8) | +69 (+0.8) | -66 (-2.1) | +9 / -50 / -18 | -4 / -85 / -21 |
| dir3-4-km | 3 | 0.12 | 11 | 0.50 | 0.16 | -9 (-0.2) | +102 (+0.7) | +102 (+0.7) | +nan (+nan) | -59 (-0.6) | -240 (-0.8) | -141 (-1.8) | -38 / +103 / -56 | +80 / -316 / +59 |
| all15-2-km | 0 | 0.63 | 35 | 0.80 | 0.67 | +1 (+0.0) | +19 (+0.4) | -39 (-0.5) | +83 (+1.1) | -20 (-0.8) | +18 (+0.2) | -35 (-1.2) | -30 / +5 / +14 | +37 / -44 / -38 |
| all15-2-km | 1 | 0.37 | 21 | 0.67 | 0.46 | -5 (-0.2) | -4 (-0.1) | -30 (-0.3) | +10 (+0.1) | -17 (-0.5) | +26 (+0.3) | -14 (-0.3) | -43 / +30 / +18 | +37 / -88 / -5 |
| all15-3-km | 0 | 0.41 | 22 | 0.71 | 0.53 | -8 (-0.4) | -19 (-0.4) | -86 (-1.1) | +38 (+0.4) | -18 (-0.7) | +28 (+0.4) | -46 (-1.5) | -31 / -2 / +6 | +25 / -27 / -26 |
| all15-3-km | 1 | 0.32 | 19 | 0.66 | 0.47 | +12 (+0.5) | +66 (+1.1) | +73 (+0.6) | +97 (+1.2) | -34 (-1.1) | -54 (-0.6) | -27 (-0.7) | +4 / +16 / -3 | +40 / -99 / -56 |
| all15-3-km | 2 | 0.27 | 18 | 0.62 | 0.38 | -9 (-0.4) | -6 (-0.1) | -44 (-0.3) | +20 (+0.2) | -27 (-0.7) | -37 (-0.3) | -26 (-0.5) | -42 / -9 / +1 | +53 / -69 / +5 |
| all15-4-km | 0 | 0.32 | 19 | 0.66 | 0.46 | -7 (-0.3) | -26 (-0.6) | -43 (-0.5) | +75 (+0.9) | -18 (-0.8) | +33 (+0.5) | -55 (-1.7) | -35 / +3 / +7 | +32 / -29 / -28 |
| all15-4-km | 1 | 0.25 | 16 | 0.61 | 0.40 | -1 (-0.1) | +50 (+0.8) | +23 (+0.2) | +23 (+0.2) | -27 (-0.8) | +70 (+0.7) | -28 (-0.7) | -20 / +4 / -14 | +40 / -100 / -98 |
| all15-4-km | 2 | 0.20 | 16 | 0.58 | 0.37 | -9 (-0.3) | -67 (-0.7) | -78 (-0.5) | -38 (-0.3) | -26 (-0.8) | -50 (-0.4) | -43 (-0.9) | -33 / +18 / +16 | +39 / -41 / -65 |
| all15-4-km | 3 | 0.23 | 17 | 0.60 | 0.34 | +9 (+0.3) | +122 (+1.5) | +102 (+0.7) | +155 (+1.7) | -48 (-1.0) | -148 (-1.2) | -0 (-0.0) | -25 / +24 / +40 | +54 / -131 / -32 |
| er72-0.5-thr | 0 | 0.51 | 12 | 0.61 | 0.49 | -5 (-0.3) | +33 (+0.7) | -24 (-0.3) | +62 (+0.8) | -31 (-1.4) | -27 (-0.4) | -39 (-1.3) | -27 / -2 / +7 | +0 / -26 / -61 |
| er72-0.5-thr | 1 | 0.49 | 12 | 0.60 | 0.49 | -2 (-0.1) | +24 (+0.4) | +86 (+0.7) | +7 (+0.1) | -26 (-0.7) | -61 (-0.7) | +12 (+0.3) | -42 / +17 / -5 | +35 / -110 / +17 |
| er72-0.7-thr | 0 | 0.70 | 22 | 0.78 | 0.70 | -6 (-0.3) | +21 (+0.4) | -44 (-0.7) | +56 (+0.7) | -21 (-0.9) | +4 (+0.1) | -28 (-1.0) | -32 / -3 / +11 | +27 / -27 / -48 |
| er72-0.7-thr | 1 | 0.30 | 9 | 0.48 | 0.29 | +7 (+0.2) | +39 (+0.5) | +110 (+0.7) | +62 (+0.7) | -53 (-1.0) | -90 (-0.8) | +9 (+0.2) | -31 / +42 / -50 | +21 / -157 / +102 |
| er168-0.5-thr | 0 | 0.51 | 20 | 0.75 | 0.59 | -21 (-1.0) | -26 (-0.5) | +17 (+0.2) | +25 (+0.3) | -17 (-0.7) | +95 (+1.2) | -26 (-0.8) | -40 / -37 / -5 | +10 / -27 / -24 |
| er168-0.5-thr | 1 | 0.49 | 19 | 0.73 | 0.56 | +6 (+0.3) | +42 (+0.8) | +11 (+0.1) | +75 (+0.9) | -19 (-0.7) | -30 (-0.4) | -25 (-0.7) | -22 / +34 / +15 | +30 / -94 / +12 |
| er168-0.7-thr | 0 | 0.71 | 36 | 0.86 | 0.76 | -6 (-0.3) | -1 (-0.0) | -47 (-0.7) | +53 (+0.7) | -19 (-0.8) | +36 (+0.5) | -30 (-1.0) | -32 / -10 / +12 | +26 / -42 / -25 |
| er168-0.7-thr | 1 | 0.29 | 15 | 0.66 | 0.43 | +18 (+0.7) | +44 (+0.7) | -4 (-0.0) | +71 (+0.8) | -21 (-0.6) | -21 (-0.2) | -26 (-0.6) | +14 / +47 / +15 | +37 / -73 / +37 |
| gapabs-0.5-thr | 0 | 0.51 | 45 | 0.67 | 0.51 | +7 (+0.4) | +15 (+0.3) | -36 (-0.5) | +12 (+0.1) | -27 (-1.1) | +42 (+0.5) | -51 (-1.7) | -24 / +12 / +12 | +49 / -71 / -54 |
| gapabs-0.5-thr | 1 | 0.49 | 43 | 0.66 | 0.50 | +1 (+0.0) | +32 (+0.6) | +13 (+0.1) | +66 (+0.8) | -32 (-1.0) | -72 (-0.9) | -19 (-0.5) | -26 / +20 / +19 | +6 / -73 / -20 |
| gapabs-0.7-thr | 0 | 0.70 | 72 | 0.81 | 0.70 | -3 (-0.2) | +1 (+0.0) | -43 (-0.6) | +32 (+0.4) | -18 (-0.7) | +14 (+0.2) | -28 (-0.9) | -29 / +19 / -0 | +37 / -73 / -14 |
| gapabs-0.7-thr | 1 | 0.30 | 31 | 0.56 | 0.31 | -0 (-0.0) | +45 (+0.7) | +67 (+0.5) | +52 (+0.5) | -31 (-0.9) | -67 (-0.7) | -59 (-1.2) | -40 / +5 / +28 | +25 / -41 / -29 |
| vr-0.5-thr | 0 | 0.51 | 68 | 0.82 | 0.67 | -4 (-0.2) | +22 (+0.4) | -20 (-0.2) | +81 (+0.9) | -8 (-0.3) | -13 (-0.2) | -34 (-1.0) | -36 / +15 / -10 | +40 / -40 / +6 |
| vr-0.5-thr | 1 | 0.49 | 65 | 0.81 | 0.66 | -10 (-0.5) | +1 (+0.0) | -26 (-0.3) | -11 (-0.1) | -25 (-0.9) | -17 (-0.2) | -10 (-0.3) | -17 / -1 / -4 | -2 / -66 / -28 |
| edge-0.5-thr | 0 | 0.51 | 14 | 0.64 | 0.53 | -7 (-0.4) | +0 (+0.0) | -34 (-0.5) | +51 (+0.6) | -36 (-1.6) | +42 (+0.6) | -57 (-2.0) | -19 / -15 / +17 | +18 / -38 / -42 |
| edge-0.5-thr | 1 | 0.49 | 13 | 0.62 | 0.51 | +10 (+0.5) | +41 (+0.7) | +56 (+0.5) | +50 (+0.6) | -21 (-0.7) | -94 (-1.1) | -23 (-0.6) | -10 / +36 / +13 | +16 / -66 / -23 |
| cc24_168-0.5-thr | 0 | 0.39 | 119 | 0.84 | 0.65 | -2 (-0.1) | +3 (+0.1) | -91 (-1.0) | +42 (+0.5) | -34 (-1.2) | -15 (-0.2) | -30 (-0.9) | -37 / +30 / -1 | +26 / -94 / -33 |
| cc24_168-0.5-thr | 1 | 0.61 | 184 | 0.90 | 0.78 | -7 (-0.4) | -3 (-0.1) | -15 (-0.2) | +100 (+1.3) | -17 (-0.6) | -1 (-0.0) | -28 (-0.9) | -31 / -0 / +7 | +27 / -44 / -9 |
| cc9_72-0.5-thr | 0 | 0.42 | 46 | 0.70 | 0.42 | -5 (-0.2) | +16 (+0.3) | -44 (-0.6) | +37 (+0.5) | -11 (-0.4) | +10 (+0.1) | -19 (-0.6) | -24 / -0 / -6 | +32 / -46 / -4 |
| cc9_72-0.5-thr | 1 | 0.58 | 64 | 0.79 | 0.59 | -6 (-0.3) | +28 (+0.5) | +14 (+0.2) | +66 (+0.9) | -22 (-0.8) | -30 (-0.4) | -12 (-0.3) | -33 / +4 / +8 | +19 / -61 / -4 |
| core4-2-hmm | 0 | 0.49 | 58 | 0.70 | 0.54 | -7 (-0.4) | -27 (-0.6) | -59 (-0.8) | +32 (+0.4) | -6 (-0.3) | +72 (+0.9) | -38 (-1.2) | -39 / +1 / -3 | +49 / -35 / -34 |
| core4-2-hmm | 1 | 0.51 | 60 | 0.71 | 0.56 | +2 (+0.1) | +36 (+0.7) | -59 (-0.6) | +87 (+1.1) | -34 (-1.2) | -55 (-0.7) | -28 (-0.8) | -24 / +25 / +10 | +17 / -78 / -12 |
| core4-3-hmm | 0 | 0.34 | 28 | 0.53 | 0.33 | -4 (-0.2) | +11 (+0.2) | -1 (-0.0) | -21 (-0.2) | -12 (-0.5) | -24 (-0.3) | -50 (-1.5) | -23 / +12 / +4 | +53 / -38 / -71 |
| core4-3-hmm | 1 | 0.26 | 28 | 0.56 | 0.32 | -23 (-1.0) | -103 (-1.4) | -83 (-0.9) | +6 (+0.1) | -35 (-1.1) | +78 (+0.9) | -29 (-0.8) | -32 / -18 / -20 | +1 / -106 / -3 |
| core4-3-hmm | 2 | 0.39 | 46 | 0.66 | 0.41 | +4 (+0.2) | +24 (+0.4) | +1 (+0.0) | +64 (+0.7) | -26 (-0.8) | -63 (-0.7) | -31 (-0.7) | -28 / +28 / +13 | +19 / -59 / +7 |
| dir3-3-hmm | 0 | 0.38 | 58 | 0.73 | 0.51 | +24 (+0.8) | +78 (+1.0) | +nan (+nan) | +78 (+1.0) | -14 (-0.4) | -78 (-0.9) | -24 (-0.6) | -29 / +54 / +43 | +57 / -44 / -41 |
| dir3-3-hmm | 1 | 0.34 | 28 | 0.51 | 0.36 | -7 (-0.4) | -15 (-0.3) | -51 (-0.6) | +19 (+0.2) | -37 (-1.4) | +25 (+0.3) | -68 (-1.8) | -43 / -8 / +13 | +40 / -69 / -57 |
| dir3-3-hmm | 2 | 0.28 | 51 | 0.68 | 0.45 | +5 (+0.2) | +30 (+0.3) | +36 (+0.4) | +nan (+nan) | -86 (-1.7) | -91 (-0.7) | -62 (-1.7) | -11 / +71 / -24 | -15 / -277 / +6 |
| agn8-3-hmm | 0 | 0.37 | 34 | 0.59 | 0.42 | -5 (-0.3) | +20 (+0.4) | -46 (-0.6) | +49 (+0.5) | -30 (-1.2) | +39 (+0.5) | -55 (-1.6) | -24 / -17 / +18 | +21 / -35 / -47 |
| agn8-3-hmm | 1 | 0.34 | 34 | 0.60 | 0.44 | +14 (+0.6) | +60 (+1.0) | -33 (-0.3) | +96 (+1.1) | -30 (-1.0) | -104 (-1.3) | -43 (-1.1) | -17 / +44 / +23 | +7 / -48 / -14 |
| agn8-3-hmm | 2 | 0.30 | 39 | 0.64 | 0.41 | +1 (+0.0) | +22 (+0.4) | -7 (-0.1) | +83 (+1.0) | -25 (-0.7) | +21 (+0.2) | -33 (-0.7) | -20 / +14 / +21 | +23 / -114 / -11 |
| agn8-2-hmm | 0 | 0.47 | 42 | 0.67 | 0.51 | -10 (-0.6) | +4 (+0.1) | -44 (-0.6) | +25 (+0.3) | -17 (-0.8) | +42 (+0.6) | -42 (-1.5) | -32 / -14 / +9 | +35 / -56 / -30 |
| agn8-2-hmm | 1 | 0.53 | 46 | 0.70 | 0.56 | +3 (+0.1) | +25 (+0.4) | -19 (-0.2) | +72 (+0.9) | -28 (-0.9) | -37 (-0.5) | -9 (-0.3) | -18 / +22 / +10 | +14 / -47 / -6 |
| core4-4-hmm | 0 | 0.23 | 23 | 0.45 | 0.18 | +9 (+0.5) | +21 (+0.4) | +15 (+0.2) | -29 (-0.3) | -33 (-1.3) | -48 (-0.6) | -45 (-1.3) | -13 / +6 / +21 | +63 / -68 / -71 |
| core4-4-hmm | 1 | 0.27 | 26 | 0.54 | 0.33 | -13 (-0.5) | -116 (-1.5) | -69 (-0.7) | -56 (-0.5) | -44 (-1.3) | +96 (+1.0) | -52 (-1.3) | -28 / -8 / -26 | -17 / -110 / -21 |
| core4-4-hmm | 2 | 0.25 | 39 | 0.60 | 0.40 | -10 (-0.4) | +26 (+0.4) | -21 (-0.2) | +92 (+1.0) | -22 (-0.7) | -22 (-0.3) | -30 (-0.7) | -34 / -14 / +19 | -7 / -13 / +6 |
| core4-4-hmm | 3 | 0.25 | 41 | 0.61 | 0.34 | -18 (-0.8) | +2 (+0.0) | -9 (-0.1) | +22 (+0.2) | -22 (-0.7) | -34 (-0.4) | +9 (+0.2) | -44 / +11 / -17 | +29 / -97 / +4 |

## Top state minus bottom state (same timestamps, cross-coin): does "trend" pay trend-following more and mean-reversion less?
| labeling | trend24 diff bp (t) | trend72 diff bp (t) | long-side72 diff (t) | short-side72 diff (t) | MR24 diff bp (t) | MR72 diff bp (t) | trend24 diff by thirds (t) | MR24 diff by thirds (t) |
|---|---|---|---|---|---|---|---|---|
| core4-2-km | +19 (+1.3) | +42 (+1.1) | -8 (-0.1) | -35 (-0.7) | -45 (-1.7) | -104 (-1.5) | +5 (+0.2) / +51 (+1.5) / +1 (+0.0) | -24 (-0.6) / -62 (-1.2) / +29 (+0.8) |
| core4-3-km | +17 (+0.9) | +76 (+1.3) | +65 (+0.6) | +9 (+0.1) | -21 (-0.8) | -52 (-0.7) | +8 (+0.3) / +42 (+0.9) / +22 (+0.9) | +2 (+0.0) / -45 (-0.8) / -30 (-0.7) |
| core4-4-km | +16 (+0.6) | +66 (+0.7) | -39 (-0.2) | +164 (+2.0) | -18 (-0.5) | -79 (-0.7) | +20 (+0.4) / +11 (+0.2) / +9 (+0.2) | +9 (+0.1) / -20 (-0.3) / -18 (-0.3) |
| agn8-2-km | +21 (+1.4) | +66 (+1.5) | +85 (+0.8) | -17 (-0.3) | -32 (-1.4) | -132 (-1.7) | +3 (+0.1) / +52 (+1.6) / +10 (+0.5) | -43 (-1.1) / -50 (-1.1) / +4 (+0.1) |
| agn8-3-km | +21 (+1.1) | +54 (+1.0) | +91 (+1.1) | -95 (-1.0) | -40 (-1.3) | -85 (-1.0) | +10 (+0.4) / +46 (+1.0) / +24 (+1.1) | +5 (+0.1) / -110 (-1.6) / -1 (-0.0) |
| agn8-4-km | +16 (+0.5) | +18 (+0.2) | -127 (-1.1) | -58 (-0.6) | -18 (-0.4) | -72 (-0.6) | +7 (+0.1) / +9 (+0.2) / -9 (-0.2) | +32 (+0.4) / -27 (-0.3) / +43 (+0.5) |
| agn10v-2-km | +23 (+1.5) | +61 (+1.2) | +103 (+0.9) | -25 (-0.4) | -31 (-1.3) | -134 (-1.5) | +2 (+0.1) / +49 (+1.5) / +17 (+0.9) | -32 (-0.8) / -45 (-0.9) / -5 (-0.1) |
| agn10v-3-km | +28 (+1.3) | +69 (+1.4) | +46 (+0.6) | +20 (+0.3) | -38 (-1.2) | -87 (-1.0) | +13 (+0.4) / +59 (+1.2) / +12 (+0.6) | -2 (-0.1) / -104 (-1.4) / +22 (+0.5) |
| agn10v-4-km | +15 (+0.5) | +84 (+0.9) | +42 (+0.2) | -85 (-1.0) | -55 (-1.0) | -144 (-1.1) | -34 (-0.6) / +77 (+1.1) / -16 (-0.3) | +42 (+0.5) / -123 (-1.3) / +74 (+0.7) |
| dir3-2-km | +36 (+0.9) | -65 (-0.5) | +29 (+0.4) | -38 (-0.3) | -35 (-0.8) | +65 (+0.6) | +58 (+1.0) / +25 (+0.2) / +3 (+0.1) | +8 (+0.2) / -100 (-0.9) / -5 (-0.1) |
| dir3-3-km | -84 (-0.9) | -83 (-0.3) | +nan (+nan) | +nan (+nan) | -35 (-0.2) | -310 (-0.7) | -127 (-1.1) / +49 (+0.2) / -156 (-1.4) | +159 (+0.9) / -298 (-0.8) / +148 (+0.9) |
| dir3-4-km | -13 (-0.0) | +815 (+1.0) | +nan (+nan) | +nan (+nan) | -242 (-0.5) | -1843 (-1.3) | -14 (-0.0) / +365 (+0.7) / +12 (+0.0) | +73 (+0.1) / -1024 (-1.1) / -61 (-0.2) |
| all15-2-km | -2 (-0.1) | -30 (-0.7) | -12 (-0.1) | -15 (-0.2) | -9 (-0.5) | +7 (+0.1) | -10 (-0.4) / +26 (+0.8) / +18 (+1.3) | -10 (-0.3) / -43 (-1.2) / -5 (-0.2) |
| all15-3-km | -4 (-0.2) | -2 (-0.0) | +70 (+0.9) | +25 (+0.3) | -27 (-1.0) | -44 (-0.6) | -14 (-0.3) / -9 (-0.2) / +15 (+0.8) | +23 (+0.4) / -49 (-1.0) / -40 (-1.2) |
| all15-4-km | +6 (+0.2) | +106 (+1.3) | +111 (+1.1) | -7 (-0.1) | -40 (-1.0) | -172 (-1.6) | -9 (-0.2) / +29 (+0.4) / +34 (+1.2) | +30 (+0.4) / -103 (-1.2) / -69 (-1.3) |
| er72-0.5-thr | +9 (+0.5) | +9 (+0.2) | +143 (+1.4) | -10 (-0.2) | -7 (-0.3) | -71 (-0.9) | -11 (-0.4) / +16 (+0.4) / +5 (+0.2) | +26 (+0.6) / -80 (-1.1) / +41 (+1.1) |
| er72-0.7-thr | +16 (+0.6) | +17 (+0.3) | +149 (+1.2) | +26 (+0.6) | -41 (-0.9) | -100 (-1.0) | +1 (+0.0) / +37 (+0.7) / -9 (-0.3) | -8 (-0.1) / -137 (-1.5) / +78 (+1.7) |
| er168-0.5-thr | +24 (+1.3) | +63 (+1.0) | -26 (-0.4) | -25 (-0.5) | -10 (-0.5) | -135 (-2.3) | +21 (+0.8) / +69 (+1.7) / +28 (+1.1) | +14 (+0.5) / -68 (-1.3) / +0 (+0.0) |
| er168-0.7-thr | +24 (+1.1) | +24 (+0.4) | -83 (-1.0) | -48 (-1.2) | -28 (-1.2) | -56 (-0.8) | +42 (+1.6) / +53 (+1.0) / +9 (+0.4) | -17 (-0.5) / -34 (-0.6) / +18 (+0.4) |
| gapabs-0.5-thr | +2 (+0.2) | +19 (+0.5) | +54 (+0.7) | +42 (+0.7) | -21 (-0.9) | -117 (-1.7) | +4 (+0.2) / +9 (+0.3) / +29 (+1.5) | -50 (-1.5) / -1 (-0.0) / -16 (-0.5) |
| gapabs-0.7-thr | +4 (+0.3) | +27 (+0.7) | +27 (+0.3) | +26 (+0.4) | -23 (-1.0) | -69 (-1.0) | -7 (-0.3) / -15 (-0.5) / +20 (+1.0) | -14 (-0.4) / +27 (+0.5) / -13 (-0.4) |
| vr-0.5-thr | -6 (-0.5) | -23 (-0.6) | +33 (+0.6) | -33 (-0.8) | -21 (-1.4) | -1 (-0.0) | +18 (+0.8) / -21 (-0.9) / +1 (+0.0) | -42 (-1.6) / -27 (-0.8) / -34 (-1.3) |
| edge-0.5-thr | +28 (+1.7) | +45 (+0.9) | +114 (+1.2) | +10 (+0.2) | -10 (-0.4) | -145 (-2.1) | +9 (+0.3) / +56 (+1.7) / +30 (+1.1) | -24 (-0.7) / -35 (-0.8) / -41 (-1.1) |
| cc24_168-0.5-thr | -6 (-0.4) | -6 (-0.1) | -42 (-0.6) | +4 (+0.1) | +14 (+0.7) | +5 (+0.1) | +7 (+0.2) / -30 (-1.0) / +8 (+0.4) | +1 (+0.0) / +50 (+1.1) / +6 (+0.3) |
| cc9_72-0.5-thr | -2 (-0.2) | -1 (-0.0) | +42 (+0.8) | +30 (+0.9) | -7 (-0.5) | -14 (-0.3) | -9 (-0.4) / +5 (+0.3) / +14 (+0.8) | -1 (-0.0) / -14 (-0.4) / -6 (-0.3) |
| core4-2-hmm | +14 (+1.0) | +65 (+1.7) | -1 (-0.0) | +39 (+0.8) | -41 (-1.9) | -130 (-2.2) | +15 (+0.8) / +24 (+0.8) / +11 (+0.6) | -32 (-1.1) / -43 (-0.9) / -2 (-0.1) |
| core4-3-hmm | +17 (+0.9) | -6 (-0.1) | +42 (+0.4) | +25 (+0.4) | -35 (-1.2) | -34 (-0.4) | +5 (+0.2) / +35 (+0.8) / +17 (+0.7) | -42 (-1.1) / -39 (-0.6) / +33 (+0.7) |
| dir3-3-hmm | -18 (-0.3) | +14 (+0.1) | +nan (+nan) | +nan (+nan) | -88 (-1.1) | -196 (-0.9) | -36 (-0.3) / +24 (+0.2) / -30 (-0.3) | -11 (-0.1) / -288 (-1.3) / +55 (+0.6) |
| agn8-3-hmm | +18 (+1.0) | +15 (+0.3) | +46 (+0.5) | +38 (+0.6) | -13 (-0.5) | +2 (+0.0) | +13 (+0.5) / +54 (+1.1) / +16 (+0.7) | -21 (-0.5) / -84 (-1.3) / -16 (-0.3) |
| agn8-2-hmm | +19 (+1.4) | +27 (+0.7) | +48 (+0.6) | +21 (+0.4) | -22 (-1.0) | -90 (-1.4) | +19 (+0.9) / +35 (+1.1) / +20 (+1.0) | -28 (-0.9) / +10 (+0.2) / -15 (-0.4) |
| core4-4-hmm | -23 (-1.0) | -12 (-0.2) | +63 (+0.7) | +33 (+0.5) | +7 (+0.2) | -0 (-0.0) | -33 (-1.0) / +11 (+0.2) / -3 (-0.1) | -13 (-0.3) / -45 (-0.5) / +8 (+0.1) |
