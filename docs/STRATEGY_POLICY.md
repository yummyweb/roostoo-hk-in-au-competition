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
- Donchian breakout variants: low turnover and sometimes positive under stress,
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
its fees exceeded its gross edge, so it is retired. The runner now trades a
four-slot breakout rotation with trailing stops, a deliberate high-variance
choice for the return screen; the strength-gated trend ensemble with a gradual
drawdown brake remains the supported lower-risk preset. Any promotion
requires a frozen paper period, current Roostoo quotes, and reconciliation of
the exact account and pair rules.
