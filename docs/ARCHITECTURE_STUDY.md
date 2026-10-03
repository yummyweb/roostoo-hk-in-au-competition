# Architecture and portfolio study — October 1, 2026

**Research candidate: Diversified trend ensemble, with a 15% annual volatility budget.** On the same 20-asset Binance evaluation used for LSTM, it returned +6.70% after modeled costs, versus LSTM's +0.99%. Maximum drawdown fell from 7.07% to 3.53%; higher-cost return rose from −2.09% to +5.87%. This is an improvement on reused historical data, not proof of a future edge or competition readiness.

## Why change the approach

The LSTM's 12-hour forecasts had slightly worse MAE than predicting no price change, approximately zero forecast/return correlation, and 2.51% average portfolio exposure. Raising its risk budget would scale a weak signal. The alternatives tested longer horizons, relative asset selection and lower-turnover portfolio construction.

Ridge regression and shallow histogram gradient-boosted trees predicted 24/72-hour **cross-sectional excess log returns**, measured from the next candle open to a future open. Features include returns over 6/24/72/168/336/720 hours, excess returns versus the contemporaneous basket, basket regime, 168-hour volatility, range, relative volume, mean deviation and path efficiency. They rank assets; they do not claim calibrated price forecasts. Asset IDs and future data are not features. Fitted labels are purged strictly before the training boundary; the ridge scaler fits training only. Trees use 120 fixed iterations, seven leaves, regularization and no random validation split.

The selected alternative uses **no fitted predictor**. Each asset receives four equal votes from positive trailing 3-, 7-, 14-, and 30-day returns. An asset with three positive horizons gets 75% of its inverse-volatility allocation. Inactive asset budgets remain in cash. Allocations are capped per asset and scaled to a conservative aggregate volatility estimate assuming perfect correlation. It uses all 20 assets rather than concentrating in the top few predictions.

Targets refresh daily and use the existing FIFO partial-rebalance engine. Changes smaller than 2% of equity are generally ignored; exiting an invalidated target can still trade below that drift threshold, subject to exchange minimums. This avoids repeatedly paying for entire round trips. Entries and trims execute on later candle opens, one global fill per hourly event. No intrabar stops, exchange depth, maker fills or leverage are assumed.

## Experiment design and all results

Dataset: 350,400 real hourly Binance candles, October 1, 2024 through September 30, 2026, across the fixed 20-asset universe. Binance USDT is a proxy for Roostoo USD; current universe membership has survivorship limitations.

Fit on the first 60%; compare architectures on two separate fresh-wallet validation blocks (60–70% and 70–80%). Freeze selection before each experiment's final-period replays. Selection score is the mean of `return − 1.5 × max drawdown` across validation blocks. The final 20% is May 8 through September 30, 2026 (146 elapsed days, UTC).

The first experiment fixed four candidates with a 35% annual volatility budget: momentum, ridge, and two tree horizons. All later replays lost money. After inspecting that failure, one explicitly exploratory follow-up fixed four candidates: ridge and the diversified trend ensemble at 15% or 25% volatility targets. Both complete experiments remain on disk. **The follow-up was motivated after inspecting the first experiment's later period; this is not an untouched holdout.** Eight new candidate configurations were evaluated in total.

| Candidate | Validation block 1 | Validation block 2 | Later net return | Later max drawdown | Higher-cost return |
| --- | ---: | ---: | ---: | ---: | ---: |
| momentum | -2.11% | -3.91% | -0.38% | 8.20% | -1.40% |
| ridge_72 | -3.27% | +5.38% | -4.50% | 8.24% | -4.48% |
| boosted_24 | -7.22% | -2.33% | -4.12% | 8.08% | -5.46% |
| boosted_72 | -3.92% | -3.54% | -2.95% | 8.33% | -3.01% |
| ridge_72_vol15 | -5.22% | +3.64% | -6.45% | 8.50% | -6.60% |
| ridge_72_vol25 | -3.96% | +5.17% | -5.40% | 8.35% | -5.27% |
| trend_budget_vol15 | -3.99% | +3.07% | +6.70% | 3.53% | +5.87% |
| trend_budget_vol25 | -3.37% | +1.19% | +19.21% | 7.79% | -4.48% |

The selected `trend_budget_vol15` was best among the follow-up's risky candidates on the validation score. Its validation returns were −3.99% and +3.07%; their mean is still negative. Cash earns zero in this simulator and beats every new candidate's validation selection score. Selection therefore produces a **research candidate**, not authorization to deploy or an established edge.

The 25% trend ensemble's +19.21% later return is not the chosen result: it ranked worse on validation and lost 4.48% under higher costs after triggering its risk halt. The halt remains latched for the run; it is never reset to hide losses. Costs can change when that halt triggers, so stressed trades need not exactly match the base path.

## Comparison with the existing LSTM

| Measure | LSTM Prediction | Selected trend ensemble |
| --- | ---: | ---: |
| Net return | +0.99% | +6.70% |
| Maximum drawdown | 7.07% | 3.53% |
| Sharpe, UTC daily returns | 0.31 | 1.85 |
| Higher-cost return | −2.09% | +5.87% |
| Fees | $1,483.59 | $391.12 |
| Fills | 209 | 151 |
| Average exposure | 2.51% | 19.19% |
| Active UTC days | 52 | 82 |

This changes both signals and portfolio construction. The extra exposure means the return improvement cannot be attributed solely to better prediction. Both retain an 8% portfolio drawdown halt and at most 80% exposure; the new per-asset cap is 20% versus LSTM's 30%. The new architecture scales a portfolio volatility budget instead of sizing each trade from ATR stops. Its realized annual volatility was 8.94%, versus LSTM's 9.44%. The volatility budget is an estimate, not a guarantee.

As a diagnostic chosen after observing exposure, a passive basket with 20% initial capital budget and 80% cash earned **+6.27%**, with **7.18% drawdown**, and **+6.22% under higher costs**. Its exposure averaged 17.72% and drifted after entry. It used the same next-open/cost/risk engine and traded on only one day. Thus the ensemble's main historical benefit is lower drawdown with more ongoing activity; it has not convincingly demonstrated return alpha over passive exposure. The fully invested analytical basket returned +34.22%, with substantially different risk and no order throttling.

Base costs: 10 bps fee per side, 4 bps full spread, 3 bps slippage per side. Stress: 20/10/10 bps respectively. No parameters are reselected for stress. Open lots are marked at bid without hypothetical exit commissions; FIFO partial sales make trade counts lot-based. The selected final run has 105 closed lots and 12 open lots.

## Competition-length results

Ten complete, non-overlapping 14-day episodes use fresh wallets and the same frozen model/rules; they cover 140 days of the 146-day evaluation. These are independent episodes, not a compounded strategy or permission to restart a halted live wallet.

- Mean return: +0.503%; median: −0.013%; worst: −1.847%.
- Higher-cost mean: +0.403%; median: −0.077%.
- Five of ten base episodes were profitable; four of ten with higher costs.
- Six of ten episodes reached at least eight active UTC days.
- The best episode earned +5.82%, so the positive average is concentrated.

This does not satisfy a reliable eight-active-days-in-fourteen competition constraint. “Active” here means any fill; the organizer's minimum meaningful activity definition remains unresolved. No token trades are inserted to satisfy it.

## Reproduce and inspect

```sh
./scripts/setup-lstm.sh
.venv-lstm/bin/python scripts/ranking_study.py
.venv-lstm/bin/python scripts/ranking_study.py --risk-followup --output runs/ranking-risk-study
.venv-lstm/bin/python -m roostoo.cli backtest \
  --data data/binance-20-1h.csv \
  --config config/ranking_candidate.json \
  --output runs/diversified-trend-20
.venv-lstm/bin/python scripts/passive_comparison.py
.venv-lstm/bin/python -m unittest discover -s tests -v
```

`runs/ranking-study` and `runs/ranking-risk-study` retain experiment plans, choices frozen before later replays, every candidate's run, cost sensitivity and selected 14-day episode metrics. Rerunning the first study writes its selected preset; rerun the follow-up second to restore the documented trend ensemble preset. The trading bot's `config/candidate.json` remains the separate original allocation candidate.

Open `runs/diversified-trend-20/run.json` in Flight Deck. The inspector shows each entry's trend votes and trailing volatility, alongside executions and P&L. **New backtest → Diversified trend ensemble** uses `config/ranking_candidate.json`; it does not select or tune on a newly imported dataset. It evaluates only the last 20%, with earlier candles supplying causal history. The desktop remains connected to the actual Python engine. Models trained through manual configuration fit on the first 60%.

The environment adds scikit-learn to NumPy/PyTorch; exact installed versions are recorded in `requirements-lstm.lock`. Selected fitted candidates serialize a local model artifact for audit, but the application does not load user-supplied model checkpoints.

Future-data mutation tests cover features, fitted predictions and preceding orders; other checks cover purged labels, trend cash retention, allocation caps, accounting, next-open fills and the actual desktop preset. This strategy is available for research replay only. It has not been wired into autonomous competition execution.
