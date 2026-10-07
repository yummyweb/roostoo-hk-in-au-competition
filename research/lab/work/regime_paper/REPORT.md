# Track `regime_paper` - the K-Means -> HMM regime filter of paper57 as a strategy selector

**Verdict: no-edge.** The paper's filter does not tell us when to run EMA-crossover trend following and when to run
z-score mean reversion, and its "bearish" state is not a good time to short. It is a volatility-state detector and
nothing more. The one real thing it carries is relative: EMA-cross long entries taken while the market is in the
filter's low-volatility state lose much less than the rest (robust against placebo labels across the whole grid), but
that does not turn into a result that beats cash after stress costs, and it is negative in the middle third of the
design period in every version.

Design data only (7,519 hourly bars, 50 pairs). Nothing here has seen the selection or holdout rows.

## Method

- Features exactly as the paper: log return over `rw` bars and rolling standard deviation of 1-bar log returns over `vw`
  bars, z-scored on the training window; K-Means (K clusters), then a K-state Gaussian HMM initialised from the clusters
  (`regime.walk_forward`). Expanding window, first fit ends at bar 744, refit every 720 bars (10 fits), labels by the
  forward filter only. EM capped at 40 iterations per fit (later fits warm-start from the previous one) to fit the time budget.
- Three scopes: `coin` (one model pooled over 50 coins, a label per coin), `btc` (BTC/USD alone, one label for the
  market), `basket` (equal-weight basket index, one label for the market).
- Grid, **162 labellings**: K-Means for all of rw {1,6,24,72} x vw {24,72,168} x K {2,3,4} x 3 scopes (108); HMM with K=3
  for all 12 feature pairs x 3 scopes (36); HMM with K=2 and K=4 on the diagonal (1,24), (24,72), (72,168) x 3 scopes (18).
- State identity. The paper names states by their mean return. That ordering is not stable: in 47 of 54 HMM labellings
  and 72 of 108 K-Means labellings the return ranking of the states changed at one or more refits (the states are separated by
  volatility, their mean returns are all close to zero). All results below therefore use identities matched across
  refits (nearest state means, Hungarian matching, `rp.canonical`; causal).
- Step 3 (does the label predict?): for each state, next-24h and next-72h (a) coin return, (b) trend payoff
  sign(EMA24-EMA100) x forward return, (c) mean-reversion payoff -clip(z48,-3,3) x forward return, sampled every 24 / 72
  bars so samples do not overlap; one cross-sectional average per sample time, t-statistic across sample times, and the
  same by design thirds. 2,916 cells in total. Every count is compared with the same count on placebo labels (the
  label array rolled by 1,000 / 2,000 / 3,000 bars: same state frequencies, same persistence, same coins, wrong time).
- Step 4a (whole grid, trade level): each reference strategy run once ungated with 50 slots so every signal is an
  independent trade (EmaCross(24,100) long with limit entries: 2,085 trades; ZScoreMR(48,2.0) long with limit entries:
  5,195; EmaCross(24,100) short: 2,066; default costs). Each trade is tagged with the label at its decision bar. Gate
  rules: (i) out-of-fold map - a state is allowed in one third if its trades averaged > 0 in the other two; (ii) "shorts
  only in the bearish state"; (iii) fixed prior maps - lowest-vol or highest-vol state, identified causally. Each gated
  P&L is ranked against the same rule applied to 19 time-shifted placebo labels (rank 1 of 20 = p <= 0.05).
- Step 4b/4c (full backtests, `evalkit.report`, 4 slots, start 744): causal state-to-strategy maps rebuilt at every
  refit from the labelled past (`gates.causal_maps`), and the fixed low-vol map, each against the ungated strategy and
  against the same construction on placebo labels. Gated runs cannot trade before bar 1464 (no map yet), so the
  like-for-like ungated reference is the "ungated-late" row.
- Counts: 162 labellings; 9 gate rules x 162 = 1,458 trade-level gate evaluations (each against 19 placebos); 83
  full-backtest reports (8 ungated, 26 gated on real labels, 48 on placebo labels, 1 candidate with the look-ahead check).

## Results

**1. Persistence.** HMM labels are usable: median 5.5 label changes per coin per 14 days (range 0.8 to 20.9 across the
54 HMM labellings), median spell 30 hours. Plain K-Means labels are not regimes: median 26 changes per 14 days (range 5
to 132), median spell 3.5 hours - a K-Means "state" is mostly "this bar was a big bar". Table A has every labelling.

**2. What the states are.** Volatility levels. Paper-literal per-coin label (rw 1, vw 24, K 3, HMM): state shares
42% / 41% / 17% with hourly vol 0.93% / 0.51% / 1.71% and trailing 24h return -0.5% / -0.1% / +0.4%. On BTC alone:
54% / 24% / 23%, vol 0.93% / 0.67% / 1.01%. There is no state that is "bullish" in the sense of what comes next.

**3. Does the label predict?** No.
- Cells whose state-vs-rest contrast has |t| >= 2 and one sign in all three thirds: **67 of 2,916 with the real
  labels, against 113, 53 and 188 with the three placebo shifts** (mean 118). The real labels are inside the placebo range.
- Forward coin return: reliably positive (|t|>=2, same sign in all thirds) in 0 of 972 state cells; reliably negative
  in 23 (it was a bear market).
- Trend payoff reliably positive in 6 of 972 cells, mean-reversion payoff in 13 of 972: chance level, and never the
  same state for neighbouring settings. In the paper-literal labellings (Table B) no cell at all passes, and most
  change sign between thirds - the same thing that happened with the earlier Bitcoin-only model.
- Both payoff proxies are positive on average at 72h in about two thirds of all states (319 and 323 of 486), so they do not
  separate "trend regime" from "mean-reversion regime" at all.

**4a. Trade-level gate test over the whole grid** (Tables C and E).
- Ungated, every reference strategy loses per trade at default costs: EmaCross long -28 bp, ZScoreMR long -60 bp
  (it wins on most days and loses heavily on crash days, hence a positive day-weighted t next to a negative mean),
  EmaCross short -19 bp even in a bear market.
- EmaCross long: the out-of-fold map beats all 19 placebos in 38 of 162 labellings (8 expected by chance). With the
  fixed prior map "only in the lowest-volatility state" it is 61 of 162, median rank 3 of 20, and the selected trades'
  mean is above zero in 109 of 162 labellings (median +9 bp; +30 to +38 bp for the HMM labellings, up to +100 bp for the best).
  This is a plateau across return window, volatility window, K and scope: it is real information. But the selected
  trades are positive in all three thirds in **1 of 162** labellings: the middle third is negative almost everywhere
  (typically -15 to -65 bp per trade), and the day-clustered t-statistics of the selected trades are between -1 and +1.2.
- ZScoreMR long: nothing. Out-of-fold map beats all placebos in 5 of 162 (8 expected), median rank 13. Low-vol state
  only: mean -56 bp; high-vol state only: -54 bp. Mean reversion loses in every regime of every labelling. The only
  positive pockets are 1-hour K-Means clusters on BTC ("BTC just printed a big up bar", e.g. btc rw 1 vw 72 K 3:
  435 trades, +78 bp, positive in all thirds, day-clustered t 1.1): that is a bounce-confirmation trigger, not a regime,
  it is not significant, and the same labelling with the causal map lost 45.7% in the full backtest.
- Shorts: nothing. Out-of-fold map 1 of 162; "shorts only in the bearish state" 4 of 162 with **median rank 15 of 20**,
  i.e. shorting in the state the paper would call bearish is worse than shorting at random times (the state is
  entered after the fall, and the bounce hits the short). High-vol state only: -39 bp per trade; low-vol: -31 bp.

**4b. Full backtests with causal maps** (Table D; 5 labellings: the paper-literal one per coin and on BTC, the best
EMA labelling, the best per-coin HMM, the best mean-reversion K-Means):

- E: ungated from bar 1464 -46.3% (stress -74.6%); gated, real labels: +8.4%, -37.2%, -18.2%, -30.7%, -27.4% (mean -21.0%; stress mean -48.1%, stress > 0 in 0 of 5); gated, placebo labels: mean -31.8%, range -56.0% to -3.8%; real beats both its placebos in 1 of 5; real-label thirds positive: [0, 1, 3] of 5 per third
- M: ungated from bar 1464 -42.4% (stress -80.8%); gated, real labels: -13.7%, -45.7%, -22.2%, -16.9%, -49.2% (mean -29.5%; stress mean -58.7%, stress > 0 in 0 of 5); gated, placebo labels: mean -19.9%, range -42.6% to +2.9%; real beats both its placebos in 1 of 5; real-label thirds positive: [2, 2, 0] of 5 per third
- S: ungated from bar 1464 +4.2% (stress -36.6%); gated, real labels: -2.8%, -1.5%, -3.0%, -5.6%, -4.2% (mean -3.4%; stress mean -28.2%, stress > 0 in 0 of 5); gated, placebo labels: mean +0.4%, range -26.3% to +58.5%; real beats both its placebos in 2 of 5; real-label thirds positive: [0, 4, 2] of 5 per third
- EMS: ungated from bar 1464 -59.9% (stress -89.7%); gated, real labels: -34.0%, -42.2%, -41.5%, -31.7%, -59.1% (mean -41.7%; stress mean -77.0%, stress > 0 in 0 of 5); real-label thirds positive: [0, 1, 1] of 5 per third

No gated strategy is positive under stress costs (0 of 20). Gating roughly halves the losses of the long strategies,
and placebo gates do the same, because both simply trade about half as often. The team's full design
(EMA + MR + shorts, each gated) returned -32% to -59% (stress -72% to -86%) with the real labels.
Ungated shorts made +24.3% on the whole period (thirds +11% / +22% / -8%; -27.4% under stress) and the regime gate made
them worse, not better.

**4c. Full backtests of the one thing that survived: EMA-cross longs only in the low-volatility state** (Table F,
6 labellings x 4 label versions). Real labels: +27.7%, +22.7%, +10.2%, -5.5%, -9.8%, -22.4% (mean +3.8%); placebo
labels: mean -21.9%, best +33.2%. Under stress costs the real-label mean is -23.5% and one of six is above zero
(+1.6%). The middle third is negative in all six. So the gate is informative (about +26 points against placebo, about +50
against the ungated strategy) and still not a strategy.

## What failed

- The premise. No labelling in the grid separates "trend works" from "mean reversion works". The two payoffs are not
  opposites in this data: mean reversion (long dips) lost in every state, and trend following (long) was at best flat.
- The paper's naming of states by mean return: unstable from refit to refit at hourly frequency (119 of 162 labellings).
- "Shorts in the bearish state": worse than placebo.
- Plain K-Means labels: too jumpy to be a regime (median spell 3.5 h).
- Per-coin versus market-level: no meaningful difference; the BTC-level label is the cheapest and did as well as any.
- K: 2, 3 and 4 behave alike (K=4 only splits the volatility axis more finely).

## Recommendation

1. Do not use the regime label to switch between the two strategies, and do not use its bearish state as the short
   trigger. If the other tracks find a version of ZScoreMR or of the short leg that works, it will be for reasons other
   than this filter.
2. If the team wants the paper's filter in the system, the only defensible role is an on/off switch for the trend leg:
   **new EMA-cross long entries only while BTC is in the HMM's lowest-volatility state.** Plateau at trade level: 46 of
   the 54 HMM labellings (15-16 of 18 in each scope: BTC, basket, per coin; all return windows, K 2-4) have a positive
   mean trade in that state. The plateau does not survive to the 4-slot portfolio (Table F: -22% to +28%). A plain rolling-volatility
   threshold would very likely do the same job without an HMM; that was not tested here.
3. `candidate_1.py` (labelled least-bad, not a recommendation to trade): BTC, rw 6, vw 24, K 3, HMM, low-vol state gates
   EmaCross(24,100) long, 4 slots. Design: +27.7%, max drawdown 21.9%, thirds +10% / -7% / +24%, 11-day windows mean
   +1.14% / median 0.00% / >=+10% in 11% / <=-10% in 0%, 217 trades, 30% win rate, turnover 117x, fees $9,180,
   stress +1.6% (11-day mean +0.21%), fills on 35% of days. Passes `h.causality_check(make, panel, cuts=8)` (make() refits
   the HMM about ten times, so 8 cuts rather than 40). Why it is not a result: it was chosen as the best of 6 full
   backtests which were themselves the top of 162 labellings; its nearest neighbour (rw 1 instead of 6) returned -5.5%;
   a placebo label returned +33.2%; it needs default costs to be positive; it trades on too few days for the
   competition's activity rule (8 of 14 days) and is below the breakout benchmark (+40%).

What would have to be true for the filter to work as the team intends: mean reversion would need a positive expectancy
in some identifiable state (none found), and the trend leg's low-vol advantage would have to hold in a period like the
middle third of the design data (it did not).

## What is left on this track

- Nothing more on design data for the filter as a strategy selector: the answer is no and more tuning would be fitting noise.
- Not done here, worth one short test by whoever owns the trend leg: a plain rolling-volatility threshold on BTC as the
  on/off switch, compared with the HMM's low-vol state (same idea, no model to refit).
- Not done here: `h.fresh_windows` on the candidate, the six coarse-tick pairs excluded, and K=2/4 HMM off the diagonal.
- Selection-period and holdout runs of `candidate_1.py` belong to the integrators and verifiers; expectation from this
  report is that it does not clear the bar.

Files: `rp.py` (features, labels, state matching, placebos), `gates.py` (causal maps, gated portfolio), `describe.py`,
`gate_trades.py`, `lowvol.py`, `gate_bt.py`, `gate_bt2.py`, `tables.py`; `states_full.csv` has all 2,916 state cells;
`gate_bt.json`, `gate_bt2.json`, `candidate_1.json` have the full `evalkit` output of every backtest.

---

# Tables

### Table A. Every labelling (one row each)

flips = refits at which the paper's return ordering of the states changed; chg/14d = label changes per coin per 14 days; spell = median spell in hours; states = share of time / trailing 24h return % / average 24h realised hourly vol % of the coins for each state (ids matched across refits, 0 = most bearish at the first fit); info = cells (state x payoff x horizon) whose state-vs-rest contrast has |t|>=2 and one sign in all thirds, real label vs the mean of 3 time-shifted placebos; E/M/S = rank of the out-of-fold gated trade P&L among 19 placebo shifts (1 = beats all, i.e. p<=0.05; 10 = median); Sb = same for "short only in the bearish state".

| scope | model | K | ret w | vol w | flips | chg/14d | spell h | states: share / ret24% / vol% | info real/placebo | E | M | S | Sb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| coin | hmm | 2 | 1 | 24 | 2 | 8.5 | 17 | 31% / -0.0 / 1.43 ; 69% / -0.2 / 0.64 | 0/0.0 of 12 | 10 | 20 | 8 | 12 |
| coin | hmm | 2 | 24 | 72 | 0 | 3.8 | 28 | 72% / -0.3 / 0.70 ; 28% / +0.4 / 1.39 | 0/0.7 of 12 | 13 | 19 | 6 | 4 |
| coin | hmm | 2 | 72 | 168 | 0 | 2.0 | 56 | 75% / -0.3 / 0.73 ; 25% / +0.4 / 1.36 | 0/2.7 of 12 | 15 | 20 | 9 | 6 |
| coin | hmm | 3 | 1 | 24 | 1 | 11.3 | 20 | 42% / -0.5 / 0.93 ; 41% / -0.1 / 0.51 ; 17% / +0.4 / 1.71 | 0/0.3 of 18 | 16 | 16 | 11 | 20 |
| coin | hmm | 3 | 1 | 72 | 1 | 5.7 | 28 | 41% / -0.4 / 0.93 ; 17% / +0.4 / 1.58 ; 42% / -0.1 / 0.56 | 0/0.3 of 18 | 1 | 17 | 3 | 16 |
| coin | hmm | 3 | 1 | 168 | 4 | 4.1 | 17 | 41% / -0.4 / 0.94 ; 17% / +0.1 / 1.50 ; 42% / -0.0 / 0.59 | 1/1.0 of 18 | 1 | 18 | 4 | 17 |
| coin | hmm | 3 | 6 | 24 | 1 | 11.0 | 21 | 41% / -0.1 / 0.51 ; 43% / -0.5 / 0.92 ; 17% / +0.5 / 1.72 | 0/0.7 of 18 | 11 | 17 | 10 | 20 |
| coin | hmm | 3 | 6 | 72 | 0 | 5.6 | 30 | 42% / -0.4 / 0.93 ; 41% / -0.1 / 0.56 ; 17% / +0.5 / 1.58 | 0/0.3 of 18 | 1 | 18 | 5 | 17 |
| coin | hmm | 3 | 6 | 168 | 2 | 4.0 | 22 | 41% / -0.4 / 0.93 ; 18% / +0.2 / 1.49 ; 42% / -0.0 / 0.59 | 1/1.0 of 18 | 1 | 19 | 7 | 17 |
| coin | hmm | 3 | 24 | 24 | 1 | 9.0 | 25 | 41% / -0.2 / 0.51 ; 43% / -0.5 / 0.93 ; 16% / +1.0 / 1.74 | 0/1.0 of 18 | 10 | 20 | 9 | 20 |
| coin | hmm | 3 | 24 | 72 | 1 | 4.2 | 48 | 41% / -0.2 / 0.56 ; 43% / -0.5 / 0.93 ; 16% / +0.9 / 1.59 | 0/0.7 of 18 | 1 | 18 | 4 | 14 |
| coin | hmm | 3 | 24 | 168 | 1 | 2.8 | 48 | 41% / -0.6 / 0.92 ; 18% / +0.5 / 1.49 ; 41% / +0.0 / 0.58 | 2/0.3 of 18 | 1 | 20 | 12 | 14 |
| coin | hmm | 3 | 72 | 24 | 1 | 8.1 | 26 | 38% / -1.6 / 0.88 ; 43% / +0.5 / 0.60 ; 19% / +1.2 / 1.57 | 0/0.3 of 18 | 14 | 14 | 2 | 20 |
| coin | hmm | 3 | 72 | 72 | 0 | 3.6 | 64 | 43% / -0.4 / 0.93 ; 41% / -0.3 / 0.56 ; 16% / +0.8 / 1.57 | 0/0.7 of 18 | 1 | 19 | 3 | 10 |
| coin | hmm | 3 | 72 | 168 | 1 | 5.9 | 32 | 40% / -1.5 / 0.86 ; 41% / +0.7 / 0.65 ; 19% / +0.8 / 1.44 | 2/1.3 of 18 | 8 | 17 | 4 | 18 |
| coin | hmm | 4 | 1 | 24 | 1 | 14.5 | 16 | 27% / -0.5 / 1.11 ; 36% / -0.2 / 0.71 ; 11% / +0.9 / 1.97 ; 27% / -0.1 / 0.47 | 0/2.0 of 24 | 6 | 14 | 5 | 16 |
| coin | hmm | 4 | 24 | 72 | 1 | 5.4 | 40 | 27% / -0.6 / 1.04 ; 28% / -0.1 / 0.49 ; 33% / -0.3 / 0.80 ; 11% / +1.3 / 1.77 | 0/1.3 of 24 | 1 | 18 | 6 | 2 |
| coin | hmm | 4 | 72 | 168 | 4 | 4.8 | 37 | 31% / -1.0 / 0.78 ; 14% / +0.6 / 1.58 ; 26% / +0.4 / 0.54 ; 30% / -0.1 / 0.99 | 0/0.3 of 24 | 1 | 16 | 1 | 13 |
| coin | km | 2 | 1 | 24 | 2 | 54.8 | 2 | 19% / +0.2 / 1.54 ; 81% / -0.2 / 0.73 | 0/0.7 of 12 | 16 | 19 | 15 | 14 |
| coin | km | 2 | 1 | 72 | 1 | 41.7 | 2 | 27% / -0.2 / 1.18 ; 73% / -0.1 / 0.78 | 0/0.7 of 12 | 13 | 18 | 7 | 2 |
| coin | km | 2 | 1 | 168 | 0 | 31.8 | 2 | 15% / -0.4 / 1.44 ; 85% / -0.1 / 0.79 | 2/1.3 of 12 | 3 | 19 | 8 | 14 |
| coin | km | 2 | 6 | 24 | 1 | 25.3 | 4 | 81% / -0.3 / 0.74 ; 19% / +0.4 / 1.51 | 2/0.0 of 12 | 13 | 17 | 10 | 9 |
| coin | km | 2 | 6 | 72 | 0 | 18.4 | 4 | 70% / -0.7 / 0.82 ; 30% / +1.2 / 1.04 | 0/0.7 of 12 | 14 | 16 | 13 | 16 |
| coin | km | 2 | 6 | 168 | 0 | 17.8 | 4 | 17% / -1.7 / 1.38 ; 83% / +0.2 / 0.78 | 0/1.3 of 12 | 6 | 14 | 8 | 17 |
| coin | km | 2 | 24 | 24 | 0 | 9.9 | 5 | 86% / -1.2 / 0.77 ; 14% / +6.5 / 1.61 | 0/2.0 of 12 | 13 | 17 | 12 | 14 |
| coin | km | 2 | 24 | 72 | 0 | 10.2 | 4 | 85% / -1.2 / 0.78 ; 15% / +5.7 / 1.47 | 0/0.7 of 12 | 12 | 17 | 13 | 13 |
| coin | km | 2 | 24 | 168 | 1 | 12.7 | 4 | 64% / +0.7 / 0.84 ; 36% / -1.6 / 0.97 | 0/0.0 of 12 | 12 | 16 | 14 | 20 |
| coin | km | 2 | 72 | 24 | 0 | 6.5 | 5 | 87% / -0.8 / 0.78 ; 13% / +4.0 / 1.62 | 0/2.0 of 12 | 12 | 16 | 11 | 14 |
| coin | km | 2 | 72 | 72 | 0 | 5.3 | 5 | 87% / -0.7 / 0.79 ; 13% / +3.6 / 1.55 | 0/1.3 of 12 | 14 | 16 | 12 | 9 |
| coin | km | 2 | 72 | 168 | 2 | 5.6 | 4 | 84% / -0.6 / 0.80 ; 16% / +2.2 / 1.33 | 0/2.0 of 12 | 13 | 16 | 14 | 9 |
| coin | km | 3 | 1 | 24 | 0 | 92.0 | 1 | 15% / -1.0 / 1.46 ; 70% / -0.3 / 0.67 ; 15% / +1.2 / 1.36 | 0/0.7 of 18 | 9 | 2 | 16 | 10 |
| coin | km | 3 | 1 | 72 | 0 | 104.3 | 1 | 22% / -1.1 / 1.19 ; 68% / -0.1 / 0.71 ; 9% / +1.8 / 1.45 | 2/0.7 of 18 | 15 | 12 | 3 | 16 |
| coin | km | 3 | 1 | 168 | 1 | 106.5 | 1 | 11% / -0.8 / 1.41 ; 58% / -0.3 / 0.75 ; 32% / +0.4 / 0.96 | 0/0.3 of 18 | 6 | 15 | 2 | 16 |
| coin | km | 3 | 6 | 24 | 0 | 41.8 | 3 | 17% / -2.8 / 1.36 ; 71% / -0.2 / 0.67 ; 13% / +3.5 / 1.47 | 0/0.3 of 18 | 13 | 13 | 4 | 18 |
| coin | km | 3 | 6 | 72 | 0 | 44.0 | 3 | 22% / -2.6 / 1.20 ; 69% / +0.1 / 0.70 ; 9% / +3.8 / 1.50 | 1/0.7 of 18 | 10 | 12 | 2 | 18 |
| coin | km | 3 | 6 | 168 | 1 | 46.1 | 3 | 11% / -2.3 / 1.39 ; 58% / -0.6 / 0.74 ; 31% / +1.5 / 0.97 | 2/1.0 of 18 | 11 | 11 | 3 | 17 |
| coin | km | 3 | 24 | 24 | 0 | 20.6 | 4 | 22% / -5.8 / 1.27 ; 69% / +0.3 / 0.66 ; 10% / +8.9 / 1.61 | 0/1.0 of 18 | 13 | 14 | 5 | 19 |
| coin | km | 3 | 24 | 72 | 0 | 24.2 | 3 | 25% / -5.4 / 1.17 ; 65% / +0.6 / 0.68 ; 9% / +8.4 / 1.57 | 0/0.3 of 18 | 12 | 14 | 4 | 19 |
| coin | km | 3 | 24 | 168 | 1 | 23.1 | 3 | 14% / -5.5 / 1.28 ; 66% / -0.8 / 0.72 ; 20% / +5.8 / 1.18 | 1/1.3 of 18 | 14 | 17 | 7 | 18 |
| coin | km | 3 | 72 | 24 | 0 | 14.8 | 4 | 26% / -3.0 / 1.20 ; 65% / +0.2 / 0.65 ; 9% / +5.5 / 1.70 | 0/2.0 of 18 | 15 | 8 | 2 | 10 |
| coin | km | 3 | 72 | 72 | 0 | 13.5 | 4 | 27% / -2.7 / 1.15 ; 65% / +0.2 / 0.68 ; 9% / +4.9 / 1.61 | 0/1.0 of 18 | 17 | 8 | 3 | 10 |
| coin | km | 3 | 72 | 168 | 0 | 13.7 | 3 | 23% / -2.7 / 1.12 ; 67% / +0.1 / 0.72 ; 10% / +4.2 / 1.47 | 0/2.3 of 18 | 14 | 1 | 5 | 17 |
| coin | km | 4 | 1 | 24 | 2 | 113.9 | 1 | 22% / -1.2 / 1.13 ; 3% / +1.7 / 2.80 ; 60% / -0.2 / 0.62 ; 16% / +1.0 / 1.25 | 1/0.3 of 24 | 17 | 7 | 9 | 11 |
| coin | km | 4 | 1 | 72 | 3 | 118.2 | 1 | 21% / -1.1 / 1.10 ; 3% / +1.2 / 2.46 ; 58% / -0.2 / 0.65 ; 18% / +1.0 / 1.13 | 0/1.7 of 24 | 10 | 1 | 12 | 14 |
| coin | km | 4 | 1 | 168 | 0 | 123.6 | 1 | 22% / -1.1 / 1.06 ; 5% / -0.3 / 1.95 ; 55% / -0.1 / 0.66 ; 18% / +1.0 / 1.10 | 1/1.7 of 24 | 3 | 1 | 6 | 16 |
| coin | km | 4 | 6 | 24 | 0 | 54.4 | 3 | 8% / -2.3 / 1.43 ; 39% / -1.0 / 0.75 ; 44% / +0.2 / 0.76 ; 9% / +3.5 / 1.60 | 0/1.7 of 24 | 16 | 9 | 16 | 18 |
| coin | km | 4 | 6 | 72 | 5 | 55.6 | 2 | 22% / -2.5 / 1.11 ; 3% / +1.9 / 2.41 ; 57% / -0.2 / 0.64 ; 18% / +2.6 / 1.12 | 0/0.3 of 24 | 13 | 9 | 4 | 18 |
| coin | km | 4 | 6 | 168 | 0 | 58.1 | 2 | 23% / -2.5 / 1.05 ; 5% / -0.8 / 1.92 ; 55% / -0.1 / 0.65 ; 17% / +2.9 / 1.13 | 0/0.3 of 24 | 10 | 7 | 2 | 19 |
| coin | km | 4 | 24 | 24 | 0 | 26.6 | 4 | 10% / -5.9 / 1.32 ; 42% / -1.8 / 0.76 ; 41% / +1.5 / 0.77 ; 6% / +9.9 / 1.83 | 0/1.0 of 24 | 20 | 8 | 16 | 15 |
| coin | km | 4 | 24 | 72 | 1 | 29.7 | 3 | 11% / -5.6 / 1.29 ; 42% / -1.9 / 0.76 ; 38% / +1.6 / 0.76 ; 9% / +7.9 / 1.54 | 0/1.3 of 24 | 5 | 8 | 10 | 16 |
| coin | km | 4 | 24 | 168 | 0 | 31.3 | 3 | 28% / -4.7 / 1.03 ; 5% / -1.9 / 1.84 ; 51% / +0.4 / 0.63 ; 16% / +6.8 / 1.19 | 0/1.0 of 24 | 5 | 11 | 14 | 19 |
| coin | km | 4 | 72 | 24 | 2 | 17.8 | 4 | 11% / -2.6 / 1.25 ; 44% / -1.0 / 0.77 ; 38% / +0.6 / 0.77 ; 8% / +4.7 / 1.66 | 1/1.3 of 24 | 19 | 13 | 12 | 8 |
| coin | km | 4 | 72 | 72 | 0 | 16.3 | 4 | 13% / -2.7 / 1.19 ; 51% / -0.8 / 0.74 ; 31% / +1.2 / 0.84 ; 5% / +6.0 / 1.90 | 1/2.7 of 24 | 15 | 16 | 2 | 10 |
| coin | km | 4 | 72 | 168 | 2 | 17.9 | 3 | 32% / -2.5 / 1.04 ; 50% / +0.2 / 0.64 ; 4% / +1.3 / 1.88 ; 14% / +3.5 / 1.14 | 0/0.7 of 24 | 18 | 5 | 4 | 19 |
| btc | hmm | 2 | 1 | 24 | 3 | 7.5 | 25 | 50% / +0.2 / 0.74 ; 50% / -0.5 / 1.03 | 0/0.0 of 12 | 1 | 18 | 12 | 12 |
| btc | hmm | 2 | 24 | 72 | 1 | 4.0 | 34 | 47% / -0.2 / 0.79 ; 53% / -0.1 / 0.97 | 0/0.0 of 12 | 1 | 13 | 11 | 4 |
| btc | hmm | 2 | 72 | 168 | 0 | 0.8 | 169 | 74% / -0.3 / 0.92 ; 26% / +0.3 / 0.79 | 0/0.0 of 12 | 5 | 13 | 4 | 9 |
| btc | hmm | 3 | 1 | 24 | 1 | 12.1 | 18 | 54% / -0.2 / 0.93 ; 24% / +0.5 / 0.67 ; 23% / -0.7 / 1.01 | 0/1.0 of 18 | 3 | 15 | 12 | 12 |
| btc | hmm | 3 | 1 | 72 | 2 | 5.1 | 39 | 32% / +0.2 / 0.77 ; 38% / -0.4 / 0.91 ; 31% / -0.3 / 0.98 | 0/0.7 of 18 | 2 | 13 | 10 | 20 |
| btc | hmm | 3 | 1 | 168 | 3 | 2.4 | 47 | 34% / -0.0 / 0.82 ; 14% / +0.8 / 0.85 ; 52% / -0.5 / 0.94 | 0/2.3 of 18 | 3 | 9 | 12 | 13 |
| btc | hmm | 3 | 6 | 24 | 2 | 12.1 | 19 | 28% / +0.4 / 0.67 ; 30% / +0.1 / 0.84 ; 42% / -0.6 / 1.07 | 0/1.3 of 18 | 1 | 11 | 9 | 16 |
| btc | hmm | 3 | 6 | 72 | 2 | 5.8 | 32 | 34% / -0.1 / 0.82 ; 25% / +0.2 / 0.78 ; 41% / -0.4 / 1.01 | 0/1.0 of 18 | 1 | 9 | 8 | 14 |
| btc | hmm | 3 | 6 | 168 | 4 | 2.3 | 73 | 59% / -0.2 / 0.89 ; 23% / -0.2 / 0.91 ; 18% / +0.2 / 0.83 | 0/0.0 of 18 | 13 | 8 | 10 | 6 |
| btc | hmm | 3 | 24 | 24 | 0 | 13.2 | 20 | 35% / -3.0 / 1.05 ; 39% / +0.2 / 0.72 ; 26% / +3.1 / 0.93 | 1/0.0 of 18 | 1 | 14 | 7 | 19 |
| btc | hmm | 3 | 24 | 72 | 3 | 4.9 | 40 | 39% / -0.4 / 0.81 ; 40% / -0.3 / 1.01 ; 21% / +0.7 / 0.79 | 0/1.3 of 18 | 10 | 7 | 9 | 5 |
| btc | hmm | 3 | 24 | 168 | 3 | 2.0 | 56 | 54% / -0.6 / 0.94 ; 17% / +0.1 / 0.87 ; 29% / +0.6 / 0.80 | 0/2.3 of 18 | 3 | 15 | 10 | 16 |
| btc | hmm | 3 | 72 | 24 | 2 | 8.6 | 23 | 37% / -0.2 / 0.75 ; 44% / -0.4 / 1.05 ; 19% / +0.5 / 0.77 | 1/0.7 of 18 | 1 | 8 | 11 | 5 |
| btc | hmm | 3 | 72 | 72 | 3 | 5.9 | 26 | 31% / -0.4 / 0.84 ; 46% / -0.6 / 0.98 ; 23% / +1.0 / 0.77 | 1/0.7 of 18 | 1 | 9 | 7 | 15 |
| btc | hmm | 3 | 72 | 168 | 3 | 2.4 | 42 | 32% / -0.2 / 0.82 ; 52% / -0.4 / 0.95 ; 16% / +0.7 / 0.82 | 0/1.7 of 18 | 9 | 6 | 4 | 13 |
| btc | hmm | 4 | 1 | 24 | 5 | 17.0 | 12 | 28% / +0.5 / 0.67 ; 25% / -0.1 / 0.83 ; 26% / -0.3 / 1.03 ; 21% / -0.9 / 1.07 | 0/2.0 of 24 | 1 | 9 | 3 | 1 |
| btc | hmm | 4 | 24 | 72 | 4 | 7.8 | 23 | 19% / -0.5 / 0.84 ; 30% / +0.2 / 0.78 ; 16% / -0.0 / 0.81 ; 36% / -0.3 / 1.03 | 1/0.7 of 24 | 1 | 16 | 19 | 19 |
| btc | hmm | 4 | 72 | 168 | 7 | 3.6 | 29 | 26% / -0.2 / 0.82 ; 42% / -0.2 / 0.98 ; 21% / +0.4 / 0.82 ; 11% / -0.8 / 0.84 | 0/0.7 of 24 | 4 | 15 | 2 | 1 |
| btc | km | 2 | 1 | 24 | 1 | 35.0 | 2 | 59% / +0.1 / 0.76 ; 41% / -0.5 / 1.07 | 0/0.7 of 12 | 3 | 16 | 10 | 12 |
| btc | km | 2 | 1 | 72 | 0 | 27.9 | 2 | 59% / -0.2 / 0.85 ; 41% / -0.0 / 0.94 | 0/0.0 of 12 | 11 | 15 | 16 | 13 |
| btc | km | 2 | 1 | 168 | 3 | 6.6 | 2 | 50% / +0.2 / 0.82 ; 50% / -0.5 / 0.95 | 0/1.3 of 12 | 2 | 14 | 9 | 16 |
| btc | km | 2 | 6 | 24 | 1 | 26.7 | 5 | 59% / +0.0 / 0.77 ; 41% / -0.4 / 1.05 | 0/0.0 of 12 | 3 | 17 | 7 | 6 |
| btc | km | 2 | 6 | 72 | 0 | 18.9 | 4 | 60% / -0.5 / 0.86 ; 40% / +0.3 / 0.92 | 0/0.0 of 12 | 10 | 17 | 12 | 16 |
| btc | km | 2 | 6 | 168 | 1 | 8.3 | 5 | 50% / +0.0 / 0.83 ; 50% / -0.3 / 0.94 | 0/1.3 of 12 | 1 | 14 | 6 | 15 |
| btc | km | 2 | 24 | 24 | 0 | 16.3 | 6 | 65% / -1.3 / 0.91 ; 35% / +2.1 / 0.84 | 0/0.0 of 12 | 16 | 14 | 8 | 17 |
| btc | km | 2 | 24 | 72 | 1 | 12.9 | 4 | 56% / -0.4 / 0.82 ; 44% / +0.2 / 0.97 | 0/0.0 of 12 | 3 | 16 | 3 | 9 |
| btc | km | 2 | 24 | 168 | 1 | 6.5 | 4 | 51% / -0.3 / 0.85 ; 49% / +0.0 / 0.93 | 0/1.3 of 12 | 3 | 15 | 9 | 9 |
| btc | km | 2 | 72 | 24 | 1 | 13.6 | 6 | 63% / -0.0 / 0.78 ; 37% / -0.4 / 1.07 | 0/0.0 of 12 | 3 | 18 | 15 | 15 |
| btc | km | 2 | 72 | 72 | 1 | 7.0 | 9 | 65% / -0.0 / 0.84 ; 35% / -0.4 / 0.98 | 0/0.0 of 12 | 10 | 16 | 4 | 15 |
| btc | km | 2 | 72 | 168 | 1 | 7.4 | 5 | 53% / -0.1 / 0.85 ; 47% / -0.2 / 0.93 | 0/0.7 of 12 | 8 | 16 | 3 | 18 |
| btc | km | 3 | 1 | 24 | 0 | 119.4 | 1 | 25% / -0.9 / 1.01 ; 48% / +0.3 / 0.73 ; 27% / -0.2 / 1.05 | 0/0.7 of 18 | 1 | 3 | 12 | 8 |
| btc | km | 3 | 1 | 72 | 1 | 125.7 | 1 | 30% / -0.8 / 0.93 ; 33% / +0.0 / 0.99 ; 37% / +0.2 / 0.76 | 1/0.3 of 18 | 3 | 1 | 13 | 5 |
| btc | km | 3 | 1 | 168 | 1 | 128.3 | 1 | 32% / -0.7 / 0.91 ; 38% / -0.1 / 0.93 ; 31% / +0.4 / 0.81 | 0/1.0 of 18 | 3 | 1 | 8 | 2 |
| btc | km | 3 | 6 | 24 | 0 | 54.1 | 3 | 23% / -2.0 / 1.04 ; 48% / +0.3 / 0.73 ; 29% / +0.6 / 1.02 | 0/1.0 of 18 | 1 | 15 | 9 | 19 |
| btc | km | 3 | 6 | 72 | 1 | 49.9 | 3 | 30% / -1.6 / 0.94 ; 34% / +0.5 / 0.98 ; 36% / +0.5 / 0.76 | 1/0.0 of 18 | 5 | 10 | 7 | 13 |
| btc | km | 3 | 6 | 168 | 1 | 49.8 | 3 | 28% / -1.6 / 0.94 ; 39% / +0.2 / 0.92 ; 32% / +0.7 / 0.80 | 1/1.3 of 18 | 14 | 8 | 4 | 15 |
| btc | km | 3 | 24 | 24 | 0 | 23.3 | 5 | 30% / -3.5 / 1.07 ; 48% / +0.3 / 0.73 ; 22% / +3.4 / 0.98 | 0/1.0 of 18 | 2 | 3 | 6 | 19 |
| btc | km | 3 | 24 | 72 | 1 | 26.1 | 3 | 38% / -2.9 / 0.97 ; 27% / +2.4 / 0.95 ; 35% / +0.8 / 0.74 | 2/0.0 of 18 | 4 | 8 | 10 | 12 |
| btc | km | 3 | 24 | 168 | 2 | 25.1 | 4 | 32% / +1.5 / 0.88 ; 38% / -2.9 / 0.96 ; 30% / +1.6 / 0.80 | 0/0.0 of 18 | 8 | 6 | 5 | 16 |
| btc | km | 3 | 72 | 24 | 3 | 19.1 | 5 | 44% / -0.2 / 0.75 ; 31% / -1.5 / 1.12 ; 25% / +1.5 / 0.85 | 1/0.3 of 18 | 2 | 15 | 17 | 16 |
| btc | km | 3 | 72 | 72 | 1 | 15.0 | 4 | 47% / -1.1 / 0.97 ; 19% / +1.5 / 0.91 ; 35% / +0.3 / 0.76 | 2/0.3 of 18 | 3 | 8 | 13 | 16 |
| btc | km | 3 | 72 | 168 | 1 | 13.1 | 5 | 55% / -1.0 / 0.94 ; 23% / +1.0 / 0.86 ; 23% / +0.8 / 0.79 | 1/0.0 of 18 | 9 | 5 | 4 | 17 |
| btc | km | 4 | 1 | 24 | 4 | 124.2 | 1 | 15% / -1.1 / 0.96 ; 27% / -0.7 / 1.09 ; 46% / +0.3 / 0.73 ; 13% / +0.6 / 0.94 | 0/2.3 of 24 | 1 | 2 | 11 | 6 |
| btc | km | 4 | 1 | 72 | 1 | 129.0 | 1 | 20% / -0.9 / 0.93 ; 28% / -0.2 / 1.02 ; 36% / +0.1 / 0.75 ; 16% / +0.4 / 0.91 | 0/1.3 of 24 | 1 | 8 | 13 | 5 |
| btc | km | 4 | 1 | 168 | 3 | 96.9 | 1 | 12% / -1.4 / 0.96 ; 37% / -0.3 / 0.95 ; 39% / +0.2 / 0.80 ; 12% / +0.4 / 0.92 | 0/1.0 of 24 | 2 | 8 | 4 | 1 |
| btc | km | 4 | 6 | 24 | 3 | 64.9 | 3 | 17% / -2.3 / 1.03 ; 41% / +0.2 / 0.71 ; 23% / -0.5 / 1.07 ; 19% / +1.4 / 0.92 | 0/1.3 of 24 | 1 | 3 | 8 | 18 |
| btc | km | 4 | 6 | 72 | 1 | 59.7 | 3 | 19% / -2.2 / 0.96 ; 27% / -0.0 / 1.01 ; 37% / +0.1 / 0.76 ; 18% / +1.2 / 0.89 | 1/0.3 of 24 | 1 | 13 | 16 | 13 |
| btc | km | 4 | 6 | 168 | 3 | 53.7 | 3 | 14% / -2.7 / 0.99 ; 36% / -0.2 / 0.93 ; 38% / +0.2 / 0.79 ; 13% / +1.8 / 0.91 | 0/1.0 of 24 | 1 | 11 | 10 | 7 |
| btc | km | 4 | 24 | 24 | 1 | 30.9 | 4 | 21% / -3.7 / 1.17 ; 38% / +0.0 / 0.71 ; 26% / +0.4 / 0.86 ; 15% / +3.5 / 0.98 | 0/1.0 of 24 | 1 | 16 | 8 | 20 |
| btc | km | 4 | 24 | 72 | 2 | 27.6 | 4 | 23% / -3.5 / 1.08 ; 32% / +0.0 / 0.75 ; 20% / +2.4 / 0.97 ; 24% / +0.7 / 0.80 | 2/0.3 of 24 | 2 | 5 | 7 | 20 |
| btc | km | 4 | 24 | 168 | 1 | 31.3 | 4 | 28% / -3.8 / 1.02 ; 29% / +1.1 / 0.89 ; 30% / +0.6 / 0.78 ; 13% / +3.0 / 0.84 | 0/1.0 of 24 | 3 | 3 | 5 | 17 |
| btc | km | 4 | 72 | 24 | 4 | 21.0 | 5 | 40% / -0.2 / 0.74 ; 27% / -1.9 / 1.13 ; 16% / +1.7 / 0.96 ; 17% / +1.3 / 0.79 | 0/0.0 of 24 | 1 | 15 | 15 | 11 |
| btc | km | 4 | 72 | 72 | 2 | 19.8 | 4 | 35% / -1.4 / 1.01 ; 29% / +0.6 / 0.77 ; 16% / +1.5 / 0.90 ; 20% / -0.3 / 0.82 | 3/1.0 of 24 | 1 | 6 | 5 | 10 |
| btc | km | 4 | 72 | 168 | 2 | 17.6 | 4 | 41% / -1.4 / 0.97 ; 25% / +0.8 / 0.86 ; 25% / +0.4 / 0.79 ; 9% / +1.6 / 0.83 | 0/1.0 of 24 | 5 | 4 | 14 | 8 |
| basket | hmm | 2 | 1 | 24 | 2 | 8.7 | 24 | 33% / -0.9 / 1.19 ; 67% / +0.2 / 0.74 | 2/0.7 of 12 | 1 | 20 | 9 | 20 |
| basket | hmm | 2 | 24 | 72 | 1 | 3.5 | 63 | 45% / -0.2 / 0.88 ; 55% / -0.1 / 0.89 | 0/1.3 of 12 | 14 | 15 | 9 | 2 |
| basket | hmm | 2 | 72 | 168 | 1 | 2.2 | 55 | 28% / -0.1 / 1.07 ; 72% / -0.2 / 0.82 | 0/0.0 of 12 | 9 | 13 | 15 | 10 |
| basket | hmm | 3 | 1 | 24 | 4 | 12.6 | 19 | 18% / -1.3 / 1.35 ; 38% / -0.1 / 0.91 ; 44% / +0.3 / 0.67 | 0/0.7 of 18 | 4 | 19 | 3 | 15 |
| basket | hmm | 3 | 1 | 72 | 6 | 5.6 | 30 | 17% / -0.7 / 1.24 ; 30% / -0.1 / 0.94 ; 53% / +0.0 / 0.74 | 2/0.7 of 18 | 1 | 11 | 12 | 9 |
| basket | hmm | 3 | 1 | 168 | 4 | 2.8 | 58 | 18% / -0.7 / 1.17 ; 41% / -0.1 / 0.86 ; 41% / +0.1 / 0.79 | 0/0.0 of 18 | 9 | 7 | 4 | 19 |
| basket | hmm | 3 | 6 | 24 | 1 | 13.1 | 20 | 44% / -0.2 / 0.85 ; 19% / -1.2 / 1.35 ; 37% / +0.5 / 0.70 | 0/0.3 of 18 | 17 | 20 | 17 | 16 |
| basket | hmm | 3 | 6 | 72 | 6 | 5.4 | 31 | 26% / -0.7 / 1.11 ; 53% / -0.0 / 0.74 ; 21% / +0.2 / 0.97 | 2/0.3 of 18 | 2 | 17 | 17 | 15 |
| basket | hmm | 3 | 6 | 168 | 4 | 3.1 | 44 | 18% / -0.6 / 1.17 ; 42% / -0.2 / 0.86 ; 40% / +0.1 / 0.79 | 0/0.0 of 18 | 12 | 9 | 4 | 20 |
| basket | hmm | 3 | 24 | 24 | 1 | 12.2 | 20 | 16% / -4.0 / 1.29 ; 49% / -0.1 / 0.69 ; 35% / +1.6 / 0.97 | 0/0.7 of 18 | 1 | 19 | 8 | 20 |
| basket | hmm | 3 | 24 | 72 | 1 | 5.3 | 32 | 20% / -1.3 / 1.11 ; 57% / -0.1 / 0.75 ; 23% / +0.8 / 1.03 | 1/0.0 of 18 | 2 | 15 | 14 | 10 |
| basket | hmm | 3 | 24 | 168 | 4 | 3.4 | 48 | 17% / -0.5 / 1.17 ; 50% / -0.4 / 0.83 ; 33% / +0.4 / 0.83 | 0/0.0 of 18 | 18 | 17 | 13 | 19 |
| basket | hmm | 3 | 72 | 24 | 4 | 10.9 | 21 | 24% / -0.5 / 0.94 ; 51% / -0.1 / 0.73 ; 24% / +0.1 / 1.18 | 0/0.0 of 18 | 1 | 6 | 6 | 19 |
| basket | hmm | 3 | 72 | 72 | 0 | 5.7 | 38 | 25% / -1.8 / 1.07 ; 49% / -0.1 / 0.75 ; 25% / +1.4 / 0.97 | 2/0.0 of 18 | 4 | 16 | 18 | 14 |
| basket | hmm | 3 | 72 | 168 | 2 | 1.7 | 82 | 71% / -0.1 / 0.81 ; 16% / +0.3 / 1.12 ; 13% / -1.0 / 1.04 | 0/0.7 of 18 | 7 | 12 | 4 | 11 |
| basket | hmm | 4 | 1 | 24 | 6 | 20.9 | 11 | 24% / +0.4 / 0.80 ; 17% / -1.4 / 1.36 ; 31% / -0.3 / 0.87 ; 27% / +0.3 / 0.68 | 2/0.3 of 24 | 16 | 20 | 3 | 15 |
| basket | hmm | 4 | 24 | 72 | 6 | 7.1 | 27 | 12% / -1.7 / 1.30 ; 43% / +0.2 / 0.73 ; 25% / -0.7 / 0.93 ; 21% / +0.7 / 0.93 | 2/0.7 of 24 | 3 | 16 | 10 | 6 |
| basket | hmm | 4 | 72 | 168 | 2 | 2.3 | 79 | 58% / +0.3 / 0.79 ; 17% / -0.7 / 1.17 ; 25% / -0.8 / 0.91 ; 0% / nan / nan | 2/0.7 of 24 | 5 | 7 | 14 | 12 |
| basket | km | 2 | 1 | 24 | 1 | 42.4 | 2 | 50% / -0.4 / 0.95 ; 50% / +0.1 / 0.82 | 0/0.0 of 12 | 17 | 12 | 9 | 8 |
| basket | km | 2 | 1 | 72 | 2 | 36.4 | 2 | 26% / -0.5 / 1.11 ; 74% / -0.0 / 0.81 | 0/0.0 of 12 | 12 | 11 | 13 | 8 |
| basket | km | 2 | 1 | 168 | 1 | 22.9 | 2 | 86% / -0.0 / 0.86 ; 14% / -0.9 / 1.08 | 0/0.0 of 12 | 15 | 16 | 8 | 19 |
| basket | km | 2 | 6 | 24 | 0 | 20.8 | 5 | 21% / -1.9 / 1.19 ; 79% / +0.3 / 0.81 | 0/0.0 of 12 | 14 | 10 | 17 | 20 |
| basket | km | 2 | 6 | 72 | 4 | 14.3 | 5 | 24% / -0.7 / 1.11 ; 76% / +0.0 / 0.82 | 0/0.7 of 12 | 11 | 10 | 15 | 16 |
| basket | km | 2 | 6 | 168 | 1 | 11.3 | 5 | 86% / +0.1 / 0.85 ; 14% / -1.5 / 1.09 | 0/0.7 of 12 | 13 | 19 | 16 | 18 |
| basket | km | 2 | 24 | 24 | 0 | 13.7 | 7 | 22% / -4.0 / 1.13 ; 78% / +1.0 / 0.82 | 0/0.7 of 12 | 15 | 13 | 4 | 20 |
| basket | km | 2 | 24 | 72 | 2 | 16.1 | 5 | 33% / -2.6 / 1.06 ; 67% / +1.1 / 0.80 | 0/0.7 of 12 | 10 | 13 | 7 | 10 |
| basket | km | 2 | 24 | 168 | 2 | 11.1 | 6 | 23% / -2.8 / 1.02 ; 77% / +0.7 / 0.85 | 0/0.0 of 12 | 4 | 13 | 10 | 19 |
| basket | km | 2 | 72 | 24 | 1 | 12.9 | 6 | 66% / +0.5 / 0.77 ; 34% / -1.4 / 1.11 | 0/0.0 of 12 | 14 | 18 | 6 | 12 |
| basket | km | 2 | 72 | 72 | 0 | 10.4 | 4 | 34% / -1.6 / 1.06 ; 66% / +0.6 / 0.80 | 0/0.0 of 12 | 17 | 12 | 6 | 10 |
| basket | km | 2 | 72 | 168 | 2 | 9.7 | 4 | 28% / -1.5 / 1.01 ; 72% / +0.4 / 0.84 | 0/2.0 of 12 | 15 | 13 | 6 | 18 |
| basket | km | 3 | 1 | 24 | 2 | 119.6 | 1 | 12% / -1.4 / 1.05 ; 56% / +0.1 / 0.79 ; 32% / -0.1 / 1.00 | 2/0.3 of 18 | 6 | 10 | 18 | 10 |
| basket | km | 3 | 1 | 72 | 1 | 121.6 | 1 | 27% / -1.1 / 0.96 ; 62% / +0.2 / 0.81 ; 11% / +0.5 / 1.13 | 1/1.0 of 18 | 8 | 2 | 5 | 8 |
| basket | km | 3 | 1 | 168 | 1 | 120.9 | 1 | 27% / -1.1 / 0.95 ; 63% / +0.2 / 0.84 ; 10% / -0.1 / 1.05 | 0/0.7 of 18 | 13 | 9 | 6 | 16 |
| basket | km | 3 | 6 | 24 | 0 | 49.3 | 3 | 12% / -2.6 / 1.12 ; 53% / -0.2 / 0.80 ; 35% / +0.7 / 0.94 | 2/0.3 of 18 | 8 | 11 | 12 | 20 |
| basket | km | 3 | 6 | 72 | 1 | 48.5 | 3 | 28% / -1.9 / 0.97 ; 60% / +0.4 / 0.81 ; 12% / +1.4 / 1.10 | 0/0.7 of 18 | 7 | 2 | 15 | 19 |
| basket | km | 3 | 6 | 168 | 3 | 47.1 | 3 | 10% / +0.3 / 1.01 ; 39% / -1.4 / 0.91 ; 51% / +0.7 / 0.84 | 0/0.7 of 18 | 14 | 11 | 18 | 8 |
| basket | km | 3 | 24 | 24 | 0 | 25.2 | 5 | 9% / -4.7 / 1.28 ; 53% / -1.4 / 0.83 ; 38% / +2.7 / 0.87 | 0/0.3 of 18 | 6 | 17 | 11 | 20 |
| basket | km | 3 | 24 | 72 | 0 | 26.2 | 4 | 10% / -4.4 / 1.18 ; 56% / -1.2 / 0.84 ; 34% / +2.8 / 0.88 | 0/0.3 of 18 | 6 | 16 | 14 | 20 |
| basket | km | 3 | 24 | 168 | 2 | 26.8 | 3 | 9% / -4.0 / 1.16 ; 56% / -1.5 / 0.85 ; 35% / +2.9 / 0.88 | 0/0.0 of 18 | 10 | 14 | 7 | 20 |
| basket | km | 3 | 72 | 24 | 0 | 16.5 | 4 | 13% / -2.5 / 1.30 ; 61% / -0.5 / 0.79 ; 26% / +1.7 / 0.90 | 1/0.0 of 18 | 3 | 15 | 19 | 18 |
| basket | km | 3 | 72 | 72 | 0 | 12.8 | 5 | 11% / -1.4 / 1.15 ; 61% / -0.5 / 0.85 ; 28% / +1.2 / 0.86 | 0/0.0 of 18 | 6 | 15 | 7 | 9 |
| basket | km | 3 | 72 | 168 | 1 | 14.2 | 4 | 59% / -0.7 / 0.85 ; 10% / -1.7 / 1.12 ; 31% / +1.5 / 0.88 | 0/0.3 of 18 | 8 | 9 | 5 | 17 |
| basket | km | 4 | 1 | 24 | 3 | 119.3 | 1 | 17% / -1.5 / 1.04 ; 58% / +0.3 / 0.72 ; 6% / -1.5 / 1.48 ; 19% / +0.2 / 1.06 | 0/1.3 of 24 | 1 | 2 | 9 | 10 |
| basket | km | 4 | 1 | 72 | 3 | 116.1 | 1 | 16% / -1.5 / 1.01 ; 10% / -0.2 / 1.15 ; 55% / +0.1 / 0.75 ; 19% / +0.2 / 1.03 | 0/1.3 of 24 | 1 | 7 | 6 | 13 |
| basket | km | 4 | 1 | 168 | 5 | 132.1 | 1 | 19% / -1.4 / 0.97 ; 9% / -0.6 / 1.06 ; 55% / +0.2 / 0.80 ; 17% / +0.3 / 1.00 | 2/0.3 of 24 | 6 | 17 | 9 | 1 |
| basket | km | 4 | 6 | 24 | 2 | 60.1 | 3 | 5% / -3.3 / 1.51 ; 31% / -1.4 / 0.91 ; 18% / +0.8 / 1.11 ; 46% / +0.7 / 0.72 | 1/0.3 of 24 | 13 | 6 | 11 | 16 |
| basket | km | 4 | 6 | 72 | 1 | 57.4 | 3 | 19% / -2.5 / 1.03 ; 52% / -0.0 / 0.74 ; 10% / +0.5 / 1.15 ; 20% / +1.3 / 0.99 | 0/0.3 of 24 | 8 | 4 | 11 | 20 |
| basket | km | 4 | 6 | 168 | 4 | 64.9 | 2 | 22% / -2.3 / 0.96 ; 8% / -1.0 / 1.12 ; 53% / +0.4 / 0.79 ; 18% / +1.2 / 0.98 | 1/1.7 of 24 | 5 | 4 | 16 | 16 |
| basket | km | 4 | 24 | 24 | 1 | 30.3 | 4 | 6% / -5.2 / 1.48 ; 32% / -2.9 / 0.95 ; 18% / +4.3 / 1.04 ; 44% / +0.7 / 0.70 | 0/0.7 of 24 | 8 | 15 | 8 | 18 |
| basket | km | 4 | 24 | 72 | 1 | 29.6 | 4 | 7% / -3.9 / 1.31 ; 37% / -2.7 / 0.90 ; 19% / +3.5 / 0.99 ; 36% / +1.3 / 0.73 | 2/0.0 of 24 | 7 | 5 | 5 | 10 |
| basket | km | 4 | 24 | 168 | 2 | 31.5 | 3 | 29% / -3.9 / 0.96 ; 5% / -2.9 / 1.38 ; 47% / +1.0 / 0.77 ; 19% / +3.5 / 0.93 | 1/0.7 of 24 | 6 | 10 | 4 | 19 |
| basket | km | 4 | 72 | 24 | 3 | 20.0 | 5 | 31% / -1.7 / 0.96 ; 6% / -2.5 / 1.52 ; 49% / +0.4 / 0.72 ; 14% / +2.5 / 1.02 | 0/1.7 of 24 | 1 | 14 | 8 | 19 |
| basket | km | 4 | 72 | 72 | 2 | 16.6 | 4 | 27% / -1.7 / 1.02 ; 53% / +0.2 / 0.75 ; 6% / -1.1 / 1.33 ; 14% / +2.3 / 0.98 | 0/0.0 of 24 | 1 | 16 | 8 | 18 |
| basket | km | 4 | 72 | 168 | 2 | 21.4 | 4 | 36% / -1.8 / 0.93 ; 6% / -1.8 / 1.31 ; 18% / +1.8 / 0.93 ; 40% / +0.7 / 0.76 | 0/0.7 of 24 | 1 | 13 | 11 | 6 |

### Table B. Does the state predict the payoff? (paper-literal labellings and the shortlist)

Mean payoff in % per state over non-overlapping samples (one cross-sectional average per sample time), t-statistic, then the three design thirds. `*` = |t|>=2 and one sign in all thirds.


**coin_r1_v24_K3_hmm** (flips 1, 11.3 changes/14d, median spell 20h)

| state | share | trailing ret24% | vol% | h | coin return: mean (t) [thirds] | trend payoff: mean (t) [thirds] | MR payoff: mean (t) [thirds] |
|---|---|---|---|---|---|---|---|
| 0 | 42% | -0.5 | 0.93 | 24 | -0.2 (-0.8) [+0.4 -0.4 -0.6] | -0.2 (-1.1) [-0.5 -0.1 -0.1] | -0.0 (-0.1) [+0.2 -0.3 +0.0] |
| 0 | 42% | -0.5 | 0.93 | 72 | -0.2 (-0.3) [+1.1 -0.7 -1.1] | -0.3 (-0.5) [+0.0 -0.6 -0.2] | +0.9 (+0.9) [+2.1 +1.3 -0.8] |
| 1 | 41% | -0.1 | 0.51 | 24 | -0.1 (-0.9) [+0.1 -0.3 -0.3] | +0.0 (+0.0) [-0.1 +0.1 -0.0] | -0.3 (-1.4) [+0.0 -0.3 -0.6] |
| 1 | 41% | -0.1 | 0.51 | 72 | -0.3 (-0.6) [+0.5 -0.8 -0.6] | -0.1 (-0.3) [-0.0 +0.1 -0.4] | -0.0 (-0.0) [+0.5 +0.6 -1.2] |
| 2 | 17% | +0.4 | 1.71 | 24 | +0.0 (+0.1) [+0.1 +0.7 -0.8] | -0.1 (-0.3) [-0.3 +0.1 -0.1] | -0.3 (-0.5) [+0.8 -1.4 -0.2] |
| 2 | 17% | +0.4 | 1.71 | 72 | -0.2 (-0.2) [+0.1 +1.2 -2.3] | +0.9 (+1.1) [+1.2 +1.7 -0.5] | +1.1 (+0.8) [+3.4 +0.1 -0.4] |

**btc_r1_v24_K3_hmm** (flips 1, 12.1 changes/14d, median spell 18h)

| state | share | trailing ret24% | vol% | h | coin return: mean (t) [thirds] | trend payoff: mean (t) [thirds] | MR payoff: mean (t) [thirds] |
|---|---|---|---|---|---|---|---|
| 0 | 54% | -0.2 | 0.93 | 24 | -0.2 (-0.8) [-0.2 +0.1 -0.6] | -0.3 (-1.2) [-0.4 -0.3 -0.2] | +0.2 (+0.4) [+0.2 +0.2 +0.1] |
| 0 | 54% | -0.2 | 0.93 | 72 | -0.4 (-0.5) [+1.1 +0.1 -2.4] | -0.1 (-0.1) [+0.2 -0.4 +0.1] | +0.6 (+0.7) [+2.3 +0.9 -1.2] |
| 1 | 24% | +0.5 | 0.67 | 24 | -0.2 (-0.5) [+0.4 -0.3 -1.2] | +0.4 (+1.6) [+0.3 +0.4 +0.7] | -0.4 (-0.9) [+0.4 -0.4 -1.8] |
| 1 | 24% | +0.5 | 0.67 | 72 | -0.2 (-0.1) [-0.6 -1.3 +2.3] | -0.1 (-0.1) [+0.6 -0.1 -1.6] | -0.5 (-0.2) [+0.1 +2.2 -5.4] |
| 2 | 23% | -0.7 | 1.01 | 24 | +0.1 (+0.2) [+1.0 -1.4 +0.5] | -0.1 (-0.1) [-0.9 +0.9 -0.0] | -0.5 (-0.7) [+0.0 -1.8 +0.1] |
| 2 | 23% | -0.7 | 1.01 | 72 | -1.1 (-0.9) [+1.9 -7.0 -1.1] | +1.5 (+1.4) [+0.5 +5.5 +0.7] | +1.1 (+0.5) [+2.9 -5.6 +2.3] |

**basket_r1_v24_K3_hmm** (flips 4, 12.6 changes/14d, median spell 19h)

| state | share | trailing ret24% | vol% | h | coin return: mean (t) [thirds] | trend payoff: mean (t) [thirds] | MR payoff: mean (t) [thirds] |
|---|---|---|---|---|---|---|---|
| 0 | 18% | -1.3 | 1.35 | 24 | -0.9 (-1.7) [-0.6 -1.3 -0.7] | +0.2 (+0.5) [-0.5 +0.8 -0.0] | -0.1 (-0.1) [+0.2 -0.9 +0.9] |
| 0 | 18% | -1.3 | 1.35 | 72 | -2.0 (-2.0) [+0.3 -1.9 -4.0] | +1.0 (+1.3) [+0.4 +0.2 +2.8] | +0.3 (+0.2) [+4.1 -0.2 -2.1] |
| 1 | 38% | -0.1 | 0.91 | 24 | +0.4 (+1.2) [+1.4 +0.6 -0.7] | -0.1 (-0.5) [-0.3 -0.3 +0.3] | -0.1 (-0.2) [+0.4 +0.2 -0.8] |
| 1 | 38% | -0.1 | 0.91 | 72 | +0.0 (+0.0) [+1.5 +0.7 -1.8] | +0.4 (+0.4) [+1.5 +0.8 -0.8] | +0.9 (+0.6) [+2.6 +0.6 -0.2] |
| 2 | 44% | +0.3 | 0.67 | 24 | -0.3 (-0.9) [-0.4 -0.5 -0.0] | -0.2 (-0.7) [-0.2 +0.1 -0.3] | -0.2 (-0.4) [+0.1 -0.5 -0.2] |
| 2 | 44% | +0.3 | 0.67 | 72 | -0.1 (-0.1) [+0.5 -1.5 +0.2] | -0.3 (-0.5) [-0.2 -0.1 -0.6] | +0.2 (+0.1) [+0.6 +1.0 -1.1] |

**btc_r6_v24_K3_hmm** (flips 2, 12.1 changes/14d, median spell 19h)

| state | share | trailing ret24% | vol% | h | coin return: mean (t) [thirds] | trend payoff: mean (t) [thirds] | MR payoff: mean (t) [thirds] |
|---|---|---|---|---|---|---|---|
| 0 | 28% | +0.4 | 0.67 | 24 | -0.3 (-0.6) [+0.1 -0.4 -1.1] | +0.2 (+0.7) [-0.2 +0.3 +0.8] | -0.3 (-0.6) [+0.4 -0.2 -1.9] |
| 0 | 28% | +0.4 | 0.67 | 72 | +0.0 (+0.0) [-0.2 -1.3 +2.3] | -0.7 (-0.7) [-0.6 -0.1 -1.6] | +0.6 (+0.3) [+1.9 +2.2 -5.4] |
| 1 | 30% | +0.1 | 0.84 | 24 | +0.2 (+0.7) [-0.0 +0.3 +0.7] | -0.1 (-0.5) [-0.2 -0.0 -0.2] | +0.3 (+0.7) [+0.3 +0.0 +0.5] |
| 1 | 30% | +0.1 | 0.84 | 72 | +0.7 (+0.7) [+2.0 +1.2 -1.9] | +0.2 (+0.2) [+0.9 -0.8 +0.4] | +2.3 (+1.8) [+2.7 +2.5 +1.5] |
| 2 | 42% | -0.6 | 1.07 | 24 | -0.3 (-0.8) [+0.9 -0.5 -0.6] | -0.2 (-0.7) [-0.8 +0.1 -0.2] | -0.2 (-0.5) [-0.2 -0.5 +0.0] |
| 2 | 42% | -0.6 | 1.07 | 72 | -1.6 (-1.8) [+0.5 -2.1 -2.0] | +0.8 (+1.2) [+1.5 +1.2 +0.2] | -0.9 (-0.8) [-0.2 -1.7 -0.7] |

**coin_r24_v72_K3_hmm** (flips 1, 4.2 changes/14d, median spell 48h)

| state | share | trailing ret24% | vol% | h | coin return: mean (t) [thirds] | trend payoff: mean (t) [thirds] | MR payoff: mean (t) [thirds] |
|---|---|---|---|---|---|---|---|
| 0 | 41% | -0.2 | 0.56 | 24 | -0.2 (-0.9) [+0.2 -0.5 -0.2] | +0.1 (+0.8) [-0.0 +0.4 -0.0] | -0.4 (-1.6) [-0.2 -0.5 -0.5] |
| 0 | 41% | -0.2 | 0.56 | 72 | -0.2 (-0.3) [+1.0 -0.9 -0.6] | +0.1 (+0.2) [+0.3 +0.1 -0.1] | +0.0 (+0.0) [+0.1 +0.9 -1.0] |
| 1 | 43% | -0.5 | 0.93 | 24 | -0.3 (-1.0) [+0.3 -0.5 -0.6] | -0.1 (-0.3) [-0.3 +0.2 -0.0] | -0.2 (-0.5) [+0.2 -0.6 -0.1] |
| 1 | 43% | -0.5 | 0.93 | 72 | -0.7 (-1.0) [+0.9 -1.3 -1.8] | +0.2 (+0.3) [+0.4 +0.2 -0.0] | +0.3 (+0.4) [+2.0 -0.1 -0.9] |
| 2 | 16% | +0.9 | 1.59 | 24 | +0.1 (+0.3) [+0.2 +0.8 -1.0] | -0.1 (-0.4) [-0.5 -0.3 +0.6] | -0.1 (-0.2) [+0.6 -0.5 -0.5] |
| 2 | 16% | +0.9 | 1.59 | 72 | +0.1 (+0.1) [+0.8 +1.5 -2.6] | +1.4 (+1.7) [+0.1 +2.0 +2.3] | -0.1 (-0.0) [+2.6 +0.1 -3.7] |

**btc_r1_v72_K3_km** (flips 1, 125.7 changes/14d, median spell 1h)

| state | share | trailing ret24% | vol% | h | coin return: mean (t) [thirds] | trend payoff: mean (t) [thirds] | MR payoff: mean (t) [thirds] |
|---|---|---|---|---|---|---|---|
| 0 | 30% | -0.8 | 0.93 | 24 | +0.1 (+0.3) [+0.8 -0.1 -0.7] | -0.2 (-0.5) [-0.4 -0.1 +0.1] | -0.9 (-1.8) [-0.3 -1.8 -1.1] |
| 0 | 30% | -0.8 | 0.93 | 72 | -0.5 (-0.5) [+0.2 -1.4 -0.9] | +0.3 (+0.4) [+0.2 +1.6 -0.2] | +0.6 (+0.4) [+3.4 -4.5 -0.4] |
| 1 | 33% | +0.0 | 0.99 | 24 | -0.5 (-1.4) [-0.5 -0.4 -0.7] | -0.3 (-1.1) [-1.3 +0.0 -0.3] | +1.2 (+2.4) [+2.2 +0.4 +1.6]* |
| 1 | 33% | +0.0 | 0.99 | 72 | -1.3 (-1.2) [-2.1 -0.4 -2.5] | +0.6 (+0.7) [-1.8 +0.3 +1.8] | +0.3 (+0.2) [+1.9 +0.5 -0.6] |
| 2 | 37% | +0.2 | 0.76 | 24 | -0.1 (-0.3) [-0.1 -0.3 +0.1] | +0.3 (+1.2) [+0.2 +0.4 +0.2] | -0.5 (-1.0) [+0.1 +0.0 -1.5] |
| 2 | 37% | +0.2 | 0.76 | 72 | +0.1 (+0.1) [+2.2 -1.0 -0.9] | -0.2 (-0.3) [+1.1 -0.7 -0.9] | +0.4 (+0.3) [-1.2 +4.2 -1.9] |

### Table C. Trade-level gate test, summary over the whole grid

Ungated reference trades (50 slots, default costs): EmaCross(24,100) long: 2085 trades, mean -28 bp, t -3.1, sum by thirds +15% / -537% / -70%; ZScoreMR(48,2) long: 5195 trades, mean -60 bp, t +2.9, sum by thirds -442% / -1514% / -1155%; EmaCross(24,100) short: 2066 trades, mean -19 bp, t -1.8, sum by thirds -73% / -197% / -126%

| strategy | labellings | rank 1 of 20 (p<=0.05) | rank <=2 (p<=0.10) | expected by chance | median rank | labellings whose out-of-fold gated trades sum > 0 |
|---|---|---|---|---|---|---|
| EmaCross long | 162 | 38 | 46 | 8 / 16 | 6 | 57 |
| ZScoreMR long | 162 | 5 | 10 | 8 / 16 | 13 | 17 |
| EmaCross short (CV map) | 162 | 1 | 8 | 8 / 16 | 8 | 25 |
| EmaCross short (bearish state only) | 162 | 4 | 8 | 8 / 16 | 15 | 11 |
- coin/hmm (18 labellings): rank-1 counts E 9, M 0, S 1, Sbear 0
- coin/km (36 labellings): rank-1 counts E 0, M 3, S 0, Sbear 0
- btc/hmm (18 labellings): rank-1 counts E 9, M 0, S 0, Sbear 2
- btc/km (36 labellings): rank-1 counts E 11, M 2, S 0, Sbear 1
- basket/hmm (18 labellings): rank-1 counts E 4, M 0, S 0, Sbear 0
- basket/km (36 labellings): rank-1 counts E 5, M 0, S 0, Sbear 1

### Table D. Full backtests (evalkit.report, start=744, 4 slots, causal maps)

| run | total | max DD | 11d mean | 11d median | >=+10% | <=-10% | thirds | trades | win | active days | long P&L | short P&L | stress total | stress 11d mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ungated E | -39.4% | 57.8% | -1.47% | -2.81% | 15% | 18% | +4% / -32% / -14% | 743 | 28% | 93% | -39664 | +0 | -74.0% | -4.59% |
| ungated-late E | -46.3% | 57.8% | -2.02% | -2.64% | 12% | 18% | -8% / -32% / -14% | 683 | 27% | 83% | -46598 | +0 | -74.6% | -4.83% |
| ungated M | -50.4% | 56.3% | -2.27% | -1.49% | 6% | 16% | -7% / -7% / -42% | 920 | 57% | 97% | -50929 | +0 | -85.8% | -6.91% |
| ungated-late M | -42.4% | 56.3% | -1.83% | -0.60% | 6% | 14% | +8% / -7% / -42% | 826 | 58% | 87% | -43056 | +0 | -80.8% | -5.89% |
| ungated S | +24.3% | 24.0% | +1.07% | +0.29% | 12% | 4% | +11% / +22% / -8% | 669 | 37% | 91% | +0 | +23494 | -27.4% | -1.03% |
| ungated-late S | +4.2% | 24.0% | +0.54% | +0.00% | 10% | 4% | -7% / +22% / -8% | 615 | 36% | 82% | +0 | +3592 | -36.6% | -1.41% |
| ungated EMS | -56.7% | 67.9% | -2.77% | -2.92% | 13% | 28% | -5% / -35% / -30% | 1391 | 42% | 98% | -62899 | +6207 | -89.7% | -8.16% |
| ungated-late EMS | -59.9% | 67.9% | -2.91% | -2.26% | 12% | 27% | -12% / -35% / -30% | 1263 | 41% | 88% | -58940 | -973 | -89.7% | -8.01% |
| btc_r6_v24_K3_hmm real E | -18.2% | 37.2% | -0.57% | +0.00% | 7% | 5% | -4% / -16% / +1% | 359 | 26% | 49% | -18580 | +0 | -42.9% | -1.90% |
| btc_r6_v24_K3_hmm real M | -22.2% | 42.4% | -0.78% | +0.00% | 3% | 6% | +9% / +6% / -33% | 323 | 58% | 48% | -22249 | +0 | -47.2% | -2.25% |
| btc_r6_v24_K3_hmm real S | -3.0% | 21.4% | +0.14% | -0.33% | 8% | 1% | -17% / +24% / -6% | 330 | 33% | 53% | +0 | -3615 | -24.9% | -0.85% |
| btc_r6_v24_K3_hmm real EMS | -41.5% | 49.3% | -1.61% | -1.10% | 7% | 15% | -10% / -1% / -35% | 830 | 38% | 81% | -38971 | -2799 | -72.5% | -4.40% |
| btc_r6_v24_K3_hmm shift1000 E | -47.3% | 54.7% | -2.29% | -2.20% | 7% | 6% | -6% / -29% / -21% | 443 | 26% | 64% | -47299 | +0 | -65.6% | -3.93% |
| btc_r6_v24_K3_hmm shift1000 M | -42.6% | 48.8% | -2.06% | -0.05% | 1% | 12% | -4% / -18% / -27% | 361 | 51% | 49% | -43238 | +0 | -62.0% | -3.62% |
| btc_r6_v24_K3_hmm shift1000 S | +31.5% | 19.3% | +1.36% | +0.00% | 10% | 0% | +8% / +34% / -9% | 266 | 41% | 43% | +0 | +30654 | +6.3% | +0.51% |
| btc_r6_v24_K3_hmm shift3000 E | -3.8% | 28.8% | +0.20% | +0.00% | 8% | 5% | -13% / +6% / +5% | 320 | 31% | 47% | -4316 | +0 | -35.3% | -1.31% |
| btc_r6_v24_K3_hmm shift3000 M | -6.1% | 43.4% | -0.11% | +0.00% | 2% | 6% | +23% / +7% / -29% | 389 | 60% | 57% | -7682 | +0 | -43.5% | -2.08% |
| btc_r6_v24_K3_hmm shift3000 S | +6.2% | 19.6% | +0.27% | +0.00% | 0% | 0% | +4% / -3% / +6% | 266 | 41% | 47% | +0 | +6235 | -14.4% | -0.60% |
| btc_r1_v24_K3_hmm real E | +8.4% | 42.2% | +0.72% | +0.00% | 13% | 8% | -4% / +10% / +3% | 326 | 28% | 43% | +7894 | +0 | -21.1% | -0.46% |
| btc_r1_v24_K3_hmm real M | -13.7% | 39.8% | -0.31% | +0.00% | 4% | 5% | +2% / +31% / -35% | 422 | 58% | 57% | -14583 | +0 | -48.2% | -2.27% |
| btc_r1_v24_K3_hmm real S | -2.8% | 20.1% | -0.12% | +0.00% | 2% | 2% | -5% / -6% / +9% | 253 | 38% | 47% | +0 | -2797 | -22.0% | -0.99% |
| btc_r1_v24_K3_hmm real EMS | -34.0% | 57.3% | -1.25% | -0.61% | 6% | 14% | -6% / +6% / -33% | 810 | 42% | 82% | -20969 | -13319 | -71.9% | -4.44% |
| btc_r1_v24_K3_hmm shift1000 E | -8.6% | 41.7% | -0.01% | -0.66% | 15% | 10% | +16% / -23% / +1% | 360 | 28% | 50% | -8937 | +0 | -41.1% | -1.67% |
| btc_r1_v24_K3_hmm shift1000 M | +2.9% | 16.2% | +0.18% | +0.00% | 3% | 1% | +2% / +6% / -5% | 171 | 62% | 29% | +2863 | +0 | -16.0% | -0.63% |
| btc_r1_v24_K3_hmm shift1000 S | -18.3% | 22.5% | -0.72% | -0.52% | 0% | 0% | -10% / -11% / +2% | 202 | 32% | 37% | +0 | -18313 | -30.9% | -1.36% |
| btc_r1_v24_K3_hmm shift3000 E | -56.0% | 61.0% | -2.89% | -1.66% | 3% | 13% | -12% / -36% / -22% | 425 | 24% | 58% | -56049 | +0 | -71.0% | -4.44% |
| btc_r1_v24_K3_hmm shift3000 M | -39.7% | 57.6% | -1.78% | -0.36% | 2% | 12% | +20% / -20% / -37% | 528 | 57% | 71% | -39686 | +0 | -69.1% | -4.35% |
| btc_r1_v24_K3_hmm shift3000 S | +58.5% | 16.6% | +2.13% | +0.25% | 9% | 0% | +4% / +31% / +17% | 357 | 40% | 61% | +0 | +57523 | +18.8% | +0.97% |
| coin_r1_v24_K3_hmm real E | -30.7% | 44.4% | -1.21% | -1.68% | 9% | 7% | -20% / -16% / +3% | 477 | 25% | 66% | -31131 | +0 | -57.1% | -3.01% |
| coin_r1_v24_K3_hmm real M | -16.9% | 37.9% | -0.50% | +0.00% | 3% | 7% | -7% / -4% / -6% | 429 | 53% | 55% | -16950 | +0 | -57.3% | -3.10% |
| coin_r1_v24_K3_hmm real S | -5.6% | 29.2% | -0.01% | -0.15% | 6% | 2% | -8% / +7% / -4% | 408 | 35% | 71% | +0 | -6201 | -31.5% | -1.26% |
| coin_r1_v24_K3_hmm real EMS | -31.7% | 57.6% | -0.93% | -1.88% | 11% | 14% | -18% / -19% / +4% | 1001 | 37% | 87% | -23717 | -8231 | -75.2% | -4.74% |
| coin_r1_v24_K3_hmm shift1000 E | -41.8% | 48.9% | -1.74% | -2.11% | 7% | 12% | +1% / -25% / -23% | 509 | 29% | 75% | -42141 | +0 | -66.0% | -3.76% |
| coin_r1_v24_K3_hmm shift1000 M | -29.1% | 39.3% | -1.21% | +0.00% | 1% | 9% | -3% / -22% / -6% | 468 | 57% | 61% | -29115 | +0 | -65.2% | -3.97% |
| coin_r1_v24_K3_hmm shift1000 S | +9.0% | 23.4% | +0.56% | +0.00% | 6% | 2% | +3% / +15% / -8% | 407 | 40% | 69% | +0 | +8888 | -22.7% | -0.78% |
| coin_r1_v24_K3_hmm shift3000 E | -27.1% | 44.8% | -0.98% | +0.00% | 7% | 8% | +7% / -31% / -1% | 393 | 27% | 56% | -27459 | +0 | -52.2% | -2.53% |
| coin_r1_v24_K3_hmm shift3000 M | -35.8% | 52.6% | -1.57% | +0.00% | 1% | 8% | +13% / -12% / -35% | 610 | 55% | 70% | -35843 | +0 | -74.2% | -5.02% |
| coin_r1_v24_K3_hmm shift3000 S | -11.0% | 22.4% | -0.36% | -0.33% | 3% | 0% | +2% / -4% / -10% | 219 | 36% | 53% | +0 | -11019 | -27.4% | -1.15% |
| coin_r24_v72_K3_hmm real E | -27.4% | 41.9% | -0.89% | -0.41% | 11% | 12% | -5% / -21% / -4% | 534 | 27% | 70% | -27837 | +0 | -57.3% | -2.88% |
| coin_r24_v72_K3_hmm real M | -49.2% | 52.6% | -2.36% | +0.00% | 1% | 11% | -3% / -16% / -38% | 451 | 53% | 49% | -49228 | +0 | -68.4% | -4.19% |
| coin_r24_v72_K3_hmm real S | -4.2% | 27.8% | -0.01% | -0.05% | 5% | 3% | -2% / +0% / -2% | 383 | 36% | 67% | +0 | -4699 | -29.7% | -1.22% |
| coin_r24_v72_K3_hmm real EMS | -59.1% | 62.4% | -2.85% | -2.16% | 11% | 23% | -9% / -22% / -43% | 1090 | 37% | 86% | -44658 | -14641 | -86.4% | -7.02% |
| coin_r24_v72_K3_hmm shift1000 E | -28.5% | 46.9% | -0.94% | -0.27% | 9% | 10% | +5% / -26% / -8% | 461 | 27% | 65% | -28903 | +0 | -56.2% | -2.80% |
| coin_r24_v72_K3_hmm shift1000 M | -29.9% | 43.5% | -1.29% | +0.00% | 0% | 10% | -8% / -26% / +3% | 348 | 57% | 49% | -29887 | +0 | -54.9% | -2.98% |
| coin_r24_v72_K3_hmm shift1000 S | -6.2% | 17.8% | +0.05% | -0.55% | 5% | 0% | -4% / -1% / -1% | 272 | 34% | 55% | +0 | -6216 | -27.4% | -0.94% |
| coin_r24_v72_K3_hmm shift3000 E | -22.9% | 44.7% | -0.67% | +0.00% | 7% | 11% | +8% / -15% / -16% | 392 | 28% | 55% | -23331 | +0 | -49.3% | -2.23% |
| coin_r24_v72_K3_hmm shift3000 M | -0.7% | 21.2% | +0.01% | +0.00% | 0% | 1% | +0% / -1% / +0% | 169 | 59% | 20% | -655 | +0 | -17.9% | -0.74% |
| coin_r24_v72_K3_hmm shift3000 S | -26.3% | 32.8% | -1.08% | -0.93% | 1% | 0% | -2% / -15% / -11% | 241 | 32% | 53% | +0 | -26361 | -41.6% | -1.97% |
| btc_r1_v72_K3_km real E | -37.2% | 48.8% | -1.60% | -0.97% | 6% | 9% | -12% / -23% / -7% | 486 | 25% | 63% | -37511 | +0 | -62.2% | -3.48% |
| btc_r1_v72_K3_km real M | -45.7% | 51.5% | -2.19% | -0.60% | 0% | 7% | -5% / -3% / -41% | 471 | 54% | 63% | -46365 | +0 | -72.1% | -4.67% |
| btc_r1_v72_K3_km real S | -1.5% | 22.2% | +0.21% | -0.04% | 8% | 2% | -14% / +11% / +4% | 452 | 38% | 72% | +0 | -2022 | -32.8% | -1.28% |
| btc_r1_v72_K3_km real EMS | -42.2% | 48.8% | -1.72% | -1.83% | 10% | 15% | -18% / -17% / -16% | 1008 | 36% | 87% | -37661 | -4726 | -78.9% | -5.58% |
| btc_r1_v72_K3_km shift1000 E | -45.9% | 55.9% | -2.00% | -1.25% | 10% | 16% | -7% / -36% / -9% | 616 | 27% | 77% | -46210 | +0 | -72.7% | -4.55% |
| btc_r1_v72_K3_km shift1000 M | -11.7% | 24.7% | -0.44% | +0.00% | 0% | 2% | +1% / -13% / +0% | 191 | 59% | 23% | -11650 | +0 | -27.6% | -1.22% |
| btc_r1_v72_K3_km shift1000 S | -21.6% | 30.5% | -0.70% | -0.80% | 4% | 0% | -8% / -7% / -9% | 392 | 33% | 60% | +0 | -21594 | -43.9% | -1.98% |
| btc_r1_v72_K3_km shift3000 E | -35.6% | 44.4% | -1.43% | -0.26% | 6% | 12% | -3% / -24% / -13% | 479 | 29% | 62% | -35601 | +0 | -62.7% | -3.46% |
| btc_r1_v72_K3_km shift3000 M | -6.7% | 26.1% | -0.16% | +0.00% | 2% | 4% | +2% / -7% / -1% | 248 | 60% | 34% | -6685 | +0 | -37.6% | -1.74% |
| btc_r1_v72_K3_km shift3000 S | -17.6% | 28.7% | -0.51% | -0.40% | 4% | 2% | -1% / -13% / -4% | 429 | 33% | 68% | +0 | -17578 | -42.1% | -1.88% |

### Table E. Fixed prior maps at trade level, whole grid (no map selection)

The allowed state is identified causally at each refit as the lowest- or highest-volatility state so far. Rank is among 19 time-shifted placebo labels.

| rule | rank 1 of 20 | rank <=2 | expected by chance | median rank | median mean trade (bp) | labellings with mean > 0 | positive in all three thirds |
|---|---|---|---|---|---|---|---|
| EmaCross long only in the low-vol state | 61 | 79 | 8 / 16 | 3 | +9 | 109 of 162 | 1 |
| ZScoreMR long only in the low-vol state | 8 | 19 | 8 / 16 | 10 | -56 | 4 of 162 | 0 |
| ZScoreMR long only in the high-vol state | 9 | 22 | 8 / 16 | 8 | -54 | 17 of 162 | 3 |
| EmaCross short only in the high-vol state | 3 | 11 | 8 / 16 | 8 | -39 | 15 of 162 | 3 |
| EmaCross short only in the low-vol state | 2 | 10 | 8 / 16 | 12 | -31 | 4 of 162 | 0 |

### Table F. Full backtests of "EmaCross(24,100) long only in the low-vol state" (4 slots, evalkit.report) against placebo labels

| run | allowed share | total | max DD | 11d mean | 11d median | >=+10% | <=-10% | thirds | trades | win | active days | stress total | stress 11d mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lowvol-E btc_r1_v24_K3_hmm real | 24% | -5.5% | 31.1% | -0.08% | +0.00% | 8% | 2% | -16% / -7% / +21% | 222 | 26% | 36% | -23.8% | -0.95% |
| lowvol-E btc_r1_v24_K3_hmm shift1000 | 27% | -7.2% | 23.7% | -0.18% | +0.00% | 1% | 1% | +4% / +2% / -13% | 232 | 30% | 37% | -24.2% | -0.99% |
| lowvol-E btc_r1_v24_K3_hmm shift2000 | 18% | +21.5% | 18.0% | +0.91% | +0.00% | 8% | 0% | +14% / -12% / +20% | 157 | 34% | 29% | +0.9% | +0.18% |
| lowvol-E btc_r1_v24_K3_hmm shift3000 | 40% | -46.1% | 58.5% | -2.26% | -1.06% | 4% | 12% | -17% / -41% / +11% | 330 | 27% | 48% | -64.0% | -3.78% |
| lowvol-E btc_r6_v24_K3_hmm real | 25% | +27.7% | 21.9% | +1.14% | +0.00% | 11% | 0% | +10% / -7% / +24% | 217 | 30% | 35% | +1.6% | +0.21% |
| lowvol-E btc_r6_v24_K3_hmm shift1000 | 25% | -22.8% | 29.3% | -0.92% | -0.06% | 1% | 3% | -11% / +1% / -14% | 241 | 28% | 36% | -42.9% | -2.10% |
| lowvol-E btc_r6_v24_K3_hmm shift2000 | 28% | +33.2% | 28.1% | +1.47% | +0.00% | 14% | 3% | +9% / +11% / +10% | 255 | 29% | 37% | -1.1% | +0.27% |
| lowvol-E btc_r6_v24_K3_hmm shift3000 | 36% | -37.5% | 51.7% | -1.60% | -1.06% | 4% | 7% | -21% / -28% / +11% | 294 | 27% | 43% | -56.6% | -2.98% |
| lowvol-E basket_r6_v24_K3_hmm real | 38% | -9.8% | 40.3% | -0.20% | -0.90% | 10% | 3% | +2% / -17% / +6% | 335 | 30% | 50% | -36.6% | -1.57% |
| lowvol-E basket_r6_v24_K3_hmm shift1000 | 29% | +12.3% | 28.2% | +0.68% | +0.00% | 9% | 2% | +13% / -11% / +12% | 251 | 32% | 40% | -18.4% | -0.57% |
| lowvol-E basket_r6_v24_K3_hmm shift2000 | 34% | -22.9% | 43.9% | -0.87% | -0.61% | 7% | 6% | +14% / -37% / +8% | 324 | 28% | 48% | -47.4% | -2.34% |
| lowvol-E basket_r6_v24_K3_hmm shift3000 | 17% | -23.0% | 31.7% | -0.95% | +0.00% | 0% | 0% | -3% / -15% / -6% | 146 | 30% | 24% | -35.0% | -1.56% |
| lowvol-E coin_r1_v24_K3_hmm real | 40% | -22.4% | 46.7% | -0.82% | -1.57% | 7% | 3% | -7% / -22% / +7% | 413 | 27% | 70% | -45.7% | -2.20% |
| lowvol-E coin_r1_v24_K3_hmm shift1000 | 42% | -42.4% | 49.3% | -2.02% | -1.75% | 0% | 4% | +1% / -26% / -23% | 384 | 32% | 69% | -62.4% | -3.63% |
| lowvol-E coin_r1_v24_K3_hmm shift2000 | 39% | -33.0% | 46.8% | -1.36% | -1.51% | 7% | 9% | +5% / -31% / -7% | 431 | 27% | 70% | -58.1% | -3.15% |
| lowvol-E coin_r1_v24_K3_hmm shift3000 | 42% | -26.1% | 38.7% | -0.98% | -1.44% | 5% | 7% | +4% / -1% / -28% | 415 | 31% | 70% | -51.8% | -2.63% |
| lowvol-E coin_r1_v72_K3_hmm real | 41% | +10.2% | 36.1% | +0.62% | -0.79% | 11% | 0% | +19% / -19% / +14% | 417 | 29% | 71% | -26.7% | -0.95% |
| lowvol-E coin_r1_v72_K3_hmm shift1000 | 42% | -18.3% | 36.3% | -0.60% | -1.14% | 7% | 6% | +6% / -18% / -6% | 398 | 30% | 69% | -45.7% | -2.18% |
| lowvol-E coin_r1_v72_K3_hmm shift2000 | 39% | -57.9% | 62.0% | -3.22% | -2.53% | 0% | 12% | -11% / -30% / -33% | 426 | 25% | 67% | -71.6% | -4.69% |
| lowvol-E coin_r1_v72_K3_hmm shift3000 | 43% | -39.6% | 48.4% | -1.84% | -2.29% | 3% | 6% | +6% / -31% / -18% | 431 | 26% | 73% | -61.9% | -3.62% |
| lowvol-E btc_r6_v168_K3_km real | 26% | +22.7% | 26.7% | +1.02% | +0.00% | 11% | 1% | +8% / -4% / +18% | 236 | 31% | 38% | -9.9% | -0.22% |
| lowvol-E btc_r6_v168_K3_km shift1000 | 36% | -30.1% | 50.0% | -1.14% | +0.00% | 7% | 8% | -4% / -25% / -4% | 315 | 24% | 42% | -48.8% | -2.30% |
| lowvol-E btc_r6_v168_K3_km shift2000 | 39% | -35.8% | 44.7% | -1.57% | -0.36% | 1% | 6% | -11% / -17% / -13% | 369 | 29% | 55% | -58.9% | -3.22% |
| lowvol-E btc_r6_v168_K3_km shift3000 | 34% | -18.2% | 39.0% | -0.54% | +0.00% | 5% | 4% | +12% / -18% / -11% | 305 | 26% | 42% | -39.8% | -1.67% |

Mean over the 6 real labels: +3.8% (stress -23.5%); mean over the 18 placebo labels: -21.9% (stress -43.8%); best placebo +33.2%; real range -22.4% to +27.7%.
