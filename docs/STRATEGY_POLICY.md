# Strategy policy

The research rule is simple: a strategy must make money in most chronological
validation blocks and remain positive under the higher cost model before it can
enter prospective paper testing. A later tail period is report-only. Adding
assets is for discovering repeatable signals; it is not permission to trade every
symbol.

Retired from active exploration:

- LSTM price forecasting: forecast error did not beat the no-change baseline;
  the 20-asset replay made 0.99% and lost 2.09% under higher costs.
- Ridge and boosted-tree cross-sectional rankings: unstable between blocks and
  later periods; model complexity did not translate into durable net returns.
- Mean reversion, pullback, hybrid, grid and high-frequency reversal ideas:
  their gross moves were too small or their execution assumptions were too
  cost-sensitive for this hourly, low-turnover competition.
- Naive pairs: a strong validation pair reversed to a later loss and degraded
  under stress; the exchange cannot guarantee simultaneous legs.
- Broad always-on trend and passive baselines: useful benchmarks, but not an
  active edge and not a reason to increase the universe.
- K-Means plus Hidden Markov regime filter (Haryani, Chandra and Tarigan,
  2026): on hourly Bitcoin returns and 24-hour volatility it finds three
  persistent volatility states, about 13 changes per 14 days against about 62
  for the breadth classifier. The calm state did not reliably predict market
  direction out of sample: the sign changed between sub-periods and sampling
  offsets, and gating breakout entries on it helped one half of the test
  period and hurt the other. `scripts/fit_regime_hmm.py` reproduces the Bitcoin
  fit and the validation. That market-wide gate is not used for orders; since
  October 8 the same method, fitted per coin on the 24-hour return and
  volatility (`scripts/fit_coin_regime.py`, `config/coin_regime.json`), labels
  each coin for the live regime strategy through `roostoo/regime_hmm.py`.
- Mean reversion gated on the breadth classifier's CHOP label: buying pairs two
  or more standard deviations below their own rolling mean lost on average in
  every tested window, stop and filter variant; shorting the mirror image lost
  more.
- EMA crossover, z-score mean reversion and a K-Means regime switch between
  them (October 7 study, `research/README.md`): the 9/21/55 crossover lost
  77-89% on hourly candles; a slow 48/200 long+short version made +95% on the
  design period and then lost in all three held-back periods; no z-score
  setting was positive after stress costs on the design period and the
  least-bad one lost in three of four periods; the regime switch added nothing
  over a placebo label. The team nevertheless runs this design live since
  October 8 (last paragraph), including shorts in BEAR and CHOP coins. A
  Bitcoin trend gate on entries, a standing Bitcoin hedge and maker-only
  execution were tested in the same study and are not used.
- Earlier Donchian channel breakout variants (before October 6; the
  momentum-gated breakout kept as `config/breakout_candidate.json` is a
  different rule, see the last paragraph): low turnover and sometimes positive under stress,
  but they still lost in broad chronological blocks. A breakout exception in
  BEAR/CHOP was especially poor and remains retired.

The strongest existing historical candidate is the 50-asset strength-gated
trend ensemble (`config/ranking_candidate_strength50.json`): +8.71% on its
later replay and +6.42% under higher modeled costs. That history was already
inspected, so it is research evidence only.

The regime study now builds a causal BULL/RECOVERY/BEAR/CHOP state from the
222-asset discovery panel, then restricts simulated orders to 64 current
Roostoo `CanTrade` crypto pairs. Its v80/top3 candidate was positive in 3 of 4
selection blocks and averaged +1.99% under stress, but gains were concentrated
in one block and the dataset is historical and selection-sensitive. Freeze it
for a prospective paper test; do not call it a winner or silently deploy it.

The architecture worth testing prospectively is therefore a two-stage,
low-turnover pipeline:

1. Classify the broad market causally from trailing 72/168/336/720-hour return,
   breadth, basket return and dispersion. Require a persistent BULL or RECOVERY
   state; stay in cash in BEAR or CHOP.
2. Within the current trade-enabled universe, require a positive slow trend,
   multi-horizon trend strength and a 3–5% move hurdle. Rank liquid candidates,
   select at most three, rebalance every 72 hours with a 5% drift band, and use
   inverse-volatility weights with an exploratory 80% target. The paper
   architecture used a 3–5% hurdle; the short-window live paper preset uses a
   2% hurdle and must be evaluated separately.

The headless runner briefly ran a short-window version of this regime logic
(October 5-6). In an hourly replay it flipped regime several times a day and
its fees exceeded its gross edge, so it is retired. On October 8 the team chose
to run its own design live: a per-coin BULL/BEAR/CHOP label picking between an
EMA crossover (long and short) and z-score mean reversion (README, "Updating
the running bot"), and that evening added exits checked every minute (2%
stop-loss, 1% profit lock, 1% mean-reversion profit target), larger positions
and a 2% loss brake, and then moved the strategy to shorter bars built from
Roostoo's quotes, first 15-minute and then 5-minute (80/320-minute EMAs,
8-hour z-score, all 65 quoted crypto pairs, entries and profit-taking tied to
momentum, and from branch `v7` trend entries on a pullback plus a steep-drop
buy). A replay of the runner over the 12 days to October 8 lost 15.6% for the
live preset, 13.5% on 5-minute bars before those entries and 7.8% on 15-minute
bars, and no replayed variant made money (README). The four-slot breakout rotation with ATR trailing stops, the
only family positive in every held-back period of the October 7 study, stays
available as `config/breakout_candidate.json`; the strength-gated trend ensemble with a gradual
drawdown brake remains the supported lower-risk preset. Any promotion
requires a frozen paper period, current Roostoo quotes, and reconciliation of
the exact account and pair rules.
