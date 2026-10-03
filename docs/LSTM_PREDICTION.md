# LSTM Prediction

A real PyTorch recurrent forecasting model trained from Binance spot market candles. The desktop strategy is named **LSTM Prediction**, and its configuration identifier is `lstm_prediction`.

## Data source and universe

The official Binance public market-data host is `https://data-api.binance.vision`. Discovery uses `/api/v3/exchangeInfo`; historical hourly OHLCV uses `/api/v3/klines`. No API key is required. Binance USDT prices are mapped to Roostoo USD instruments as an explicit proxy.

The fixed research universe contains 20 assets: BTC, ETH, SOL, BNB, XRP, DOGE, ADA, LINK, AVAX, SUI, LTC, AAVE, DOT, NEAR, UNI, TRX, FIL, ARB, ICP, and APT. The first twelve are the original subset; the last eight expand it at the user's request. All have Binance USDT spot history and matching tradable Roostoo USD instruments. This is a fixed research choice, not a historical ranking of the best-performing assets.

The combined CSV covers 2024-10-01 through 2026-09-30 inclusive: 17,520 completed hourly candles per asset, or 350,400 rows. The downloader rejects missing assets, gaps, incomplete date coverage, and mismatched timelines. No synthetic pre-listing candles are inserted. Its manifest records Binance provenance and checksums of reused source files.

```sh
SSL_CERT_FILE=/etc/ssl/cert.pem python3 scripts/download_history.py \
  --assets BTC,ETH,SOL,BNB,XRP,DOGE,ADA,LINK,AVAX,SUI,LTC,AAVE,DOT,NEAR,UNI,TRX,FIL,ARB,ICP,APT \
  --reuse data/binance-all --output data/binance-20-1h.csv
```

The reuse directory is optional; missing histories are fetched from Binance. Files for other assets in that directory are ignored. The earlier broad download was stopped; its already completed files remain cached but are excluded from this experiment. The optional `download_binance_universe.py` discovery utility is not needed for this 20-asset workflow.

The selection uses assets available today. It does not reconstruct delisted assets or point-in-time historical membership, so survivorship remains a research limitation.

## Model and signal

One pooled LSTM learns across the 20 selected assets. Default architecture: one LSTM layer with 16 hidden units and a linear output head. Inputs are the previous 24 hourly candles represented by:

- Log returns over 1, 6 and 24 hours.
- Candle range relative to close and open-to-close log return.
- Log volume relative to its trailing 24-hour mean.
- Trailing 24-hour return volatility and price deviation from the trailing mean.

All features are causal. The target is `100 × log(close[t+12] / close[t])`; the prediction is converted back into a future price and simple percentage return. Forecasting returns avoids teaching the model that a high nominal Bitcoin price is itself a buy signal.

The first 60% of the timeline trains the model and scaler. The next 20% selects the best of six epochs using validation Huber loss. Training labels must finish strictly before the training boundary; validation labels must finish before the evaluation boundary. Training sequences are sampled every three hours; evaluation predicts every hour. AdamW, gradient clipping, fixed seed, deterministic CPU operations, and a small network limit complexity. Test prices never determine scaling, epoch selection or entry thresholds.

The final 20% generates the reported trading equity curve. The model remains frozen throughout it. These markets were explored by earlier strategy studies; the split prevents implementation leakage but does not make the market history newly unseen research data.

A long entry requires forecast return greater than round-trip fees, modeled spread, two-sided slippage, and a fixed 0.30% extra margin. At default costs the hurdle is 0.60%. Optional short entries use the symmetric negative threshold and the engine's 1× collateral model. Signals fill on the next candle open, obey precision/cash/exposure constraints, and receive ATR-based position sizing. Exits occur on the 12-hour holding horizon, an opposing forecast, a trailing stop, or the portfolio drawdown halt. No forecast is treated as a guaranteed fill or profit.

## Train and inspect

```sh
./scripts/setup-lstm.sh
.venv-lstm/bin/python -m roostoo.cli lstm \
  --data data/binance-20-1h.csv \
  --config config/lstm_prediction.json \
  --output runs/lstm-prediction-20
```

The isolated environment uses Python 3.12. `requirements-lstm.lock` records the exact installed versions; `requirements-lstm.txt` gives compatible major-version ranges.

The training command writes:

- `model.pt`: fitted weights, preprocessing metadata and configuration. This project does not load untrusted checkpoints.
- `model.json`: architecture, partition boundaries, scaler, training losses, selected epoch and weight checksum.
- `forecasts.jsonl`: forecast timestamp, availability time, future target time, predicted price/return, and eventual observed return where available.
- `run.json` and the usual auditable trade, signal, order, metric and equity files.

Open `run.json` in Flight Deck. Each LSTM trade includes its forecast price, return, horizon, entry hurdle and exit reason. Run assumptions show forecast error and model details. New backtest → **LSTM Prediction** → choose the historical hourly CSV trains the same model through the desktop bridge. Training synthetic demo data is intentionally rejected.

The app searches its ancestor directories for `.venv-lstm/bin/python`; on this Mac the app bundle in the project finds that environment. If the app is moved elsewhere, set `ROOSTOO_PYTHON` to the ML Python before launching. The environment is not embedded in the app bundle. Other strategies remain dependency-free.

## Evaluation

The fixed 20-asset run is saved in `runs/lstm-prediction-20/run.json`. Evaluation covers 2026-05-08 00:00 UTC to 2026-10-01 00:00 UTC (exclusive). Epoch 2 was selected on validation loss; no evaluation-driven parameter tuning was performed.

| Measure | Result |
| --- | ---: |
| Net return after modeled costs | +0.991% |
| Final marked equity, from $100,000 | $100,991.15 |
| Maximum drawdown | 7.074% |
| Sharpe, UTC daily returns | 0.307 |
| Closed trades / open trades at end | 104 / 1 |
| Fills / active UTC days | 209 / 52 |
| Win rate on closed trades | 48.08% |
| Higher-cost return | −2.086% |
| Forecast return MAE / no-change MAE | 1.7989% / 1.7923% |
| Direction accuracy / always-up accuracy | 50.743% / 49.665% |
| Forecast/actual return correlation | −0.0053 |

Base execution costs are 10 bps fees per side, 4 bps full spread and 3 bps slippage per side. Stress uses 20/10/10 bps respectively, keeping forecasts and the original entry hurdle frozen. The analytical fully invested equal-weight basket returned +34.22% over the same window; it has much higher exposure than the strategy's 2.51% average exposure and does not use the engine's order throttle. One position remains marked open, without a hypothetical exit commission.

This model has **not demonstrated a robust predictive or trading edge**: forecast errors trail the no-change baseline and higher execution costs erase the trading gain. Active days over this long evaluation do not establish the competition's eight-active-days-in-fourteen requirement. Earlier 12-asset artifacts are exploratory and use an earlier execution revision, so they are not a controlled comparison against this final run.

Price forecasts are compared with a no-change price forecast using return MAE and RMSE. Direction accuracy excludes exactly flat outcomes and includes an always-up baseline; the excluded count and correlation are reported. Trading results include fees and slippage, plus a higher-cost sensitivity replay using the same frozen predictions and original entry hurdle. Negative results and sparse activity are reported without retuning against the evaluation period.

Tests mutate future market data and assert that earlier features, training scalers, selected weights and preceding predictions remain identical. Other tests check horizon-purged splits, the cost hurdle, optional shorts, forecast-driven exits, data requirements, and actual desktop training.

This addition is a backtesting/research strategy. The existing autonomous runner remains allocation-only; LSTM has not been deployed to the competition account.
