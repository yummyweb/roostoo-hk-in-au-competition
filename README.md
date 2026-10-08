# Flight Deck — Roostoo Research

A native macOS desktop trade explorer and a deterministic Python research engine for the Roostoo competition. The workspace includes real historical datasets, reproducible experiments, an authenticated API adapter, and a general-account execution canary.

**Current strategy status: research, not deployment-ready.** The supplied strategy ideas did not establish a robust edge after costs. See [the results](docs/RESEARCH_RESULTS.md). The desktop app displays actual backtest outcomes, including losses.

## Open the desktop app

On this Mac, double-click **`dist/Flight Deck-darwin-arm64/Flight Deck.app`**. Python 3.10+ must be installed; the app finds Homebrew Python automatically. The native bundle is local and unsigned/not notarized for distribution.

To run from source:

```sh
nvm use
npm ci
npm start
```

Node 22.12+ is required for current Electron tooling. The base Python engine has no third-party runtime dependencies; LSTM Prediction uses the separate PyTorch environment below. The paper/live runner uses POSIX process locking and is intended for macOS/Linux.

- Click any trade marker or ledger row to inspect prices, sizing, fees, thesis, and exit reason.
- Switch between equity, asset price, and drawdown. Scroll to zoom, drag to pan, click the lower timeline to navigate.
- Filter by pair, direction, outcome, or text. Sort by entry time or net P&L.
- Use **New backtest** to import a CSV and run the actual Python engine.
- **Open run** loads any generated `run.json`. **Export trades** exports the filtered ledger; **Run assumptions** exports the complete run.
- The bundled example is one real, explicitly exploratory 14-day episode. A new backtest without an imported CSV uses a clearly labeled synthetic fixture.

## LSTM Prediction

The **LSTM Prediction** strategy trains a PyTorch LSTM from Binance hourly OHLCV and trades its 12-hour price forecasts after a cost hurdle. Use **New backtest → LSTM Prediction**, choose a real hourly market CSV, and run. The first 60% trains, the next 20% selects an epoch, and only the last 20% contributes to reported trading results.

```sh
./scripts/setup-lstm.sh
SSL_CERT_FILE=/etc/ssl/cert.pem python3 scripts/download_history.py --assets BTC,ETH,SOL,BNB,XRP,DOGE,ADA,LINK,AVAX,SUI,LTC,AAVE,DOT,NEAR,UNI,TRX,FIL,ARB,ICP,APT --reuse data/binance-all --output data/binance-20-1h.csv
.venv-lstm/bin/python -m roostoo.cli lstm --data data/binance-20-1h.csv --config config/lstm_prediction.json --output runs/lstm-prediction-20
```

The fixed universe expands from 12 to 20 assets, using 350,400 actual Binance hourly candles. The downloader reuses only the selected assets and checks complete synchronized coverage. [Model, data and validation details](docs/LSTM_PREDICTION.md). Open `runs/lstm-prediction-20/run.json` in the app to inspect the finished run: +0.99% net return, 7.07% maximum drawdown, and −2.09% with higher costs. Forecast error did not beat the no-change baseline, so this remains research.

## Paper-informed 50-asset strategy

I reviewed all 34 supplied papers. Their useful common signal is a design discipline: multi-horizon trend and regime confirmation can reduce noise; volume/liquidity and volatility controls matter; short-horizon reversal and grid returns are too small or too cost-sensitive to assume; and no general AI architecture has established durable net alpha. The implemented **Diversified Trend Ensemble** uses 50 synchronized Binance/Roostoo crypto pairs, 3/7/14/30-day trend votes, dollar-volume gating, inverse-volatility sizing, a 15% annual volatility budget, 20% per-asset caps, partial daily rebalancing, and the existing execution costs and drawdown halt.

The selected 50-asset preset returned **+2.63%** on its later replay with **0.65% maximum drawdown** and **+2.50% under higher costs**. Seven 14-day episodes averaged +0.91%, but the median was −0.15% and one episode supplied most of the gain. This is a research candidate, not a promise to win. [Paper synthesis, all rejected ideas, asset list, and selection protocol](docs/PAPER_SYNTHESIS.md).

The parallel portfolio study also produced an explicitly exploratory strength-gated preset, [`config/ranking_candidate_strength50.json`](config/ranking_candidate_strength50.json). It requires at least two of four positive trend horizons, targets 20% annualized volatility, caps each asset at 20%, rebalances every 24 hours and ignores 1% allocation drift. Its reproduced later replay returned **+8.71%** with **5.50% maximum drawdown** and **+6.42% under higher modeled costs**; the contiguous validation slice returned **+8.50%**. These figures use previously inspected history and are not a guarantee or a live deployment recommendation. Open [`runs/diversified-trend-50-strength/run.json`](runs/diversified-trend-50-strength/run.json) to inspect its trades in Flight Deck.

Three parallel optimization tracks were also run. Regime gates, pairs and portfolio variants produced higher later-period diagnostics, but none survived the project’s two-block validation without hindsight risk. The strongest pair validation reversed to a loss; the strongest portfolio diagnostics used a weaker selection protocol. [Parallel agent study and rejected candidates](docs/AGENT_OPTIMIZATION_STUDY.md).

I also screened Binance's current 503 USDT spot symbols and downloaded the top 250 by 24-hour quote volume for a fixed one-year hourly study. After removing new listings without full coverage, 215 assets and 1,883,400 candles remained. Trend breadth, strength gates and cross-sectional momentum were tested across five contiguous blocks with higher-cost stress. The best broad variant was positive in only 3/5 blocks and negative under mean cost stress, so the expansion did not replace the 50-asset candidate. See [the broad-universe report](runs/broad-universe-study/REPORT.md) and reproduce the data with `scripts/download_broad_universe.py` and `scripts/assemble_broad_universe.py`.

The 50-asset data contains 619,600 real hourly Binance rows from May 2, 2025 through September 30, 2026. Rebuild it with:

```sh
.venv-lstm/bin/python scripts/assemble_universe.py
.venv-lstm/bin/python -m roostoo.cli backtest --data data/binance-50-1h.csv --config config/ranking_candidate.json --output runs/diversified-trend-50
.venv-lstm/bin/python -m roostoo.cli backtest --data data/binance-50-1h.csv --config config/ranking_candidate_strength50.json --output runs/diversified-trend-50-strength
```

Open `runs/diversified-trend-50/run.json` in Flight Deck, or choose **New backtest → Diversified trend ensemble** and select the 50-asset CSV. The application uses the actual Python engine and displays trend votes, volatility, executions and costs per trade.

## Reproduce the research

```sh
python3 -m unittest discover -s tests -v
python3 -m roostoo.cli demo
python3 scripts/download_history.py --start 2024-10-01 --end 2026-10-01
python3 -m roostoo.cli research --data data/binance-1h.csv --output runs/research
python3 scripts/competition_windows.py
python3 scripts/download_history.py --assets BTC,ETH,SOL,BNB,XRP,DOGE,ADA,LINK,AVAX,SUI,LTC,AAVE --reuse data/binance-1h.csv --output data/universe-1h.csv
python3 scripts/universe_study.py
python3 scripts/allocation_study.py
```

On this machine, Python HTTPS needs the system trust store: prefix network commands with `SSL_CERT_FILE=/etc/ssl/cert.pem`. TLS verification remains enabled.

Local datasets contain 52,560 rows for three assets and 210,240 rows for twelve assets. CSV manifests record source, timestamps, and the USDT→USD proxy assumption. Binance data is **not historical Roostoo execution data**. Current Roostoo pair rules are saved in `config/exchange_info.json`; they are not point-in-time historical listing rules.

An individual replay:

```sh
python3 -m roostoo.cli backtest --data data/universe-1h.csv --config config/candidate.json --output runs/custom
```

`config/candidate.json` is the latest **research candidate**, not an approved live configuration. Every run writes config, rules, source checksum, source-code hash, metrics, signals, orders, FIFO trades, equity CSV, a report, and the desktop `run.json`.

## Input CSV

```csv
timestamp,pair,open,high,low,close,volume
1735689600000,BTC/USD,93500,94000,93000,93800,100
```

`timestamp` is candle **open time**, in 13-digit UTC milliseconds. Include at least three candles per pair, in chronological order, with one complete shared timeline across pairs. Duplicate rows, missing intervals, mismatched timelines, nonfinite values, and invalid OHLC ranges are rejected. Strategy periods are in bars; the research defaults assume hourly candles.

A sibling `your-data.manifest.json` should declare `source`, `synthetic`, and provenance. An import without it is labeled unverified in its manifest.

## Strategy and execution

The engine supports EMA/momentum trends, conditional pullbacks, cost-filtered reversion, daily relative-momentum rotation, volatility-budgeted partial allocation, capped buy-and-hold, and cash. These are research hypotheses, not promises of alpha.

Signals observe completed candles; market orders fill at the next open. Buys use modeled ask, sells use modeled bid, with adverse slippage and fees. There is one global fill per event and at least 60 seconds between fills; hourly replay is deliberately more restrictive than the API's minute limit. There is no order-book, queue, partial-exchange-fill, limit-order, or intrabar-stop model.

Shorts reserve collateral plus opening fees. Closing uses the ask; gross loss is capped at collateral before closing fees, matching the guide. Spot inventory and short collateral cannot be spent twice. Allocation orders can partially rebalance inventory using FIFO lot accounting. A partial sale splits its original lot, so lot counts differ from exchange order counts.

The drawdown halt latches for the run and schedules liquidation through the same order throttle. Gaps and delayed liquidation can exceed the threshold. Open inventory is marked at bid/ask without hypothetical exit fees; it is not forcibly liquidated at the dataset end. Minimum-order dust can remain.

Metrics use daily UTC equity returns, 365 days/year, zero risk-free/target return. Undefined ratios are `null`; annualized ratios are withheld for samples under seven days and remain unstable over short periods. The official sampling convention is not specified in the supplied rules. Passive benchmark charts use a fully invested equal-weight basket; the separate capped buy-and-hold experiment uses the same engine restrictions.

## API and prospective data

```sh
python3 -m roostoo.cli collect --output data/roostoo-tickers.jsonl --samples 1440 --interval 60
```

This records public raw ticker responses, server clocks, and failures. It does not submit orders. Historical candles are not exposed by the documented Roostoo API.

`python3 -m roostoo.cli check-account` reads balances and shorts using `ROOSTOO_API_KEY` / `ROOSTOO_API_SECRET` from the shell. The live API returns `SpotWallet`, while the PDF's older example uses `Wallet`; both are recognized by the account tools.

The finite general-test canary uses **separate** `ROOSTOO_TEST_API_KEY` / `ROOSTOO_TEST_API_SECRET` variables:

```sh
python3 scripts/test_account_canary.py --execute-general-canary --output runs/canary/journal.json
```

It spends approximately $10 of mock USD, verifies a market BUY, waits 61 seconds, and sells the resulting BTC. It journals intent before POST and never retries ambiguous mutations. A journal that already exists blocks a repeat; reconcile with the exchange before any restart. Do not point this script at competition credentials.

The persistent allocation runner defaults to local paper execution:

```sh
python3 -m roostoo.bot --config config/candidate.json --state runs/paper/state.json
```

It warms hourly indicators from completed Binance candles, uses current Roostoo bid/ask quotes, journals decisions and state, waits at least 60 seconds between submissions, and blocks on stale quotes or ambiguous outcomes. `deploy/roostoo-paper.service` is a paper-mode AWS service template. An explicit `--live` option exists for controlled validation, but **has not been deployed or validated as a production competition executor**. It submits only market spot orders, supports allocation only, and requires a flat, reconciled starting wallet. A timeout after submission latches an unresolved intent rather than retrying. The general-account canary validates transport, not all autonomous live recovery behavior. The research has not earned competition promotion. See [competition constraints and readiness](docs/COMPETITION.md) for the concrete remaining requirements.

## Desktop development

```sh
npm run test:ui
npm run package
```

UI tests launch the real native Electron application and exercise the Python bridge. Screenshots are saved in `artifacts/`. The renderer is sandboxed, has no Node access, and cannot navigate to external content. File access is through native pickers and a narrow preload interface.

Source PDFs contain team credentials. They are excluded from Git and app packaging, along with environment files, datasets, run directories, and internal workspace directories. No credentials are embedded in the implementation.

## AWS runner

See [`docs/AWS_DEPLOYMENT.md`](docs/AWS_DEPLOYMENT.md) and [`deploy/aws_start.sh`](deploy/aws_start.sh). The script installs an Amazon Linux EC2 systemd service and defaults to paper mode. It reads credentials from `/etc/roostoo/roostoo.env`; real keys are never committed. Setting `ROOSTOO_LIVE=1` is an explicit account-owner action after reconciliation and prospective paper testing. The runner now uses the team's regime strategy (long and short) in `config/live_candidate.json`.

The retirement rules and current architecture recommendation are in [`docs/STRATEGY_POLICY.md`](docs/STRATEGY_POLICY.md). The exact titles of the 34 supplied papers are indexed in [`docs/PAPER_TITLES.md`](docs/PAPER_TITLES.md).

### Headless EC2 bot only

The desktop app is not required on AWS. On a fresh Ubuntu EC2 instance, run:

```sh
git clone https://github.com/yummyweb/roostoo-hk-in-au-competition.git /tmp/roostoo
sudo install -d -m 0750 /etc/roostoo
sudo install -m 0600 /tmp/roostoo/deploy/roostoo.env.example /etc/roostoo/roostoo.env
sudoedit /etc/roostoo/roostoo.env       # add the API key and secret; leave ROOSTOO_LIVE=0 initially
sudo bash /tmp/roostoo/deploy/aws_start.sh
sudo journalctl -u roostoo-bot -f
```

For the hackathon account, launch the provided `Hackathon-Starter-Template` in
`ap-southeast-2` (Sydney), then use EC2 Session Manager to open the terminal.
SSH and EC2 Instance Connect are unavailable in that account; the installer
supports its Amazon Linux image through `dnf`.

### Updating the running bot

For strategy/config changes on an existing account, use the updater from the
Session Manager terminal. The first time, pull to obtain the new script:

```sh
cd /opt/roostoo
sudo systemctl stop roostoo-bot
sudo git pull --ff-only origin "$(git symbolic-ref --short HEAD)"
sudo bash deploy/aws_update.sh
sudo systemctl status roostoo-bot --no-pager
sudo journalctl -u roostoo-bot -n 50 --no-pager
```

For subsequent updates, the updater itself stops the service, pulls the branch
checked out on the server (`v4` for the current live rule), migrates the
selected ledger, regenerates the unit, and starts the service:

```sh
sudo bash /opt/roostoo/deploy/aws_update.sh
```

The updater backs up the state beside the existing ledger and appends a
`config_migration` event to its journal. It preserves fills, cash, inventory,
equity peak, drawdown halt, and last submission time. Unsubmitted pending
signals and cached targets are cleared so the new strategy recalculates them.
For the breakout preset, saved trailing-stop levels are cleared and the
high-water marks kept, so each stop is rebuilt at the first hourly decision.
A switch to the regime strategy from another one starts with an empty position
book: every holding the old strategy left is sold and any short covered, one
order per minute, before new entries on those coins. A parameter change within
the regime strategy keeps its positions, trailing levels and re-entry locks and
clears only the order queue.
It supports long-only allocation, breakout, regime-adaptive and trend-ensemble settings, and the long/short regime-legs strategy;
it does not convert arbitrary strategy schemas. Mode switches, changes to
`initial_cash`, unresolved submissions, exchange pending orders and held assets
outside the new universe block migration. Open shorts block a migration to any
preset other than `regime_legs`; a migration to `regime_legs` accepts them and
the runner covers the ones it did not open.
A failed migration leaves the service stopped and the ledger unchanged.
The previous config must be verifiable from the existing `.jsonl` journal.

The updater reads `ROOSTOO_CONFIG` and `ROOSTOO_STATE` from
`/etc/roostoo/roostoo.env`. Keep the **existing live ledger path**. If your config
is a local copy such as `live_candidate_updated.json`, Git will not update that
copy. To use the repository's current live preset, edit the environment file
before running the updater:

```sh
sudoedit /etc/roostoo/roostoo.env
# Set ROOSTOO_CONFIG=/opt/roostoo/config/live_candidate.json
# Keep ROOSTOO_STATE pointing to the existing live ledger.
```

The live candidate is the team's regime strategy (`rank_model: regime_legs`)
on 5-minute bars: a regime label per coin decides which rule trades it, long
or short. Entries are decided when each 5-minute bar closes; exits are also
checked every minute on live quotes.

- **Bars.** Roostoo has no candle endpoint, so the runner builds its bars from
  the mid of Roostoo's own quotes for the 65 crypto pairs it quotes
  (`config/universe-crypto.json`; the 21 tokenised stocks are left out, and
  OMNI and TON are listed without a quote), closing one at the first cycle
  after each five minutes. On start each pair's history is filled from Binance
  5-minute closes, so a restart does not wait days. `bar_minutes` may be 1, 5,
  15, 30 (bars from quotes) or 60 (hourly Binance candles); every window below
  is counted in bars, 12 to the hour.
- **Regime.** Each coin is labelled BULL, BEAR or CHOP by a three-state hidden
  Markov model started from K-Means clusters (Haryani, Chandra and Tarigan,
  2026) on two features, its 12-hour return and the 4-hour volatility of its
  5-minute returns. One model serves all coins (`config/coin_regime_5m.json`,
  fitted by `scripts/fit_bar_regime.py`); the runner applies it with a forward
  filter, so a label uses only past bars. In the fit BULL coins had risen 4.1%
  over 12 hours on average, BEAR coins had fallen 3.7%, CHOP coins were quiet.
- **BULL and BEAR: EMA crossover.** Buy a BULL coin within 40 minutes of its
  80-minute EMA (16 bars) crossing above its 320-minute EMA (64 bars), short a
  BEAR coin within 40 minutes of the cross below, and only once the fast EMA
  is at least 0.2% of the price beyond the slow one. The order is sent only
  while the price is still moving that way (the momentum test below); until
  then it waits, at most to the end of the bar. At most four positions, the
  widest gap first, 15% of equity each. Exit when the EMAs cross back; the
  coin then waits 80 minutes.
- **CHOP: z-score mean reversion.** Buy a CHOP coin 2.5 standard deviations
  below its 8-hour mean and short one 2.5 above; 10% of equity each, at most
  four. Exit when the price is back across the mean or after 4 hours; the
  coin then waits 80 minutes.
- **Every minute, on the live bid (longs) or ask (shorts)** (`legs.watch`).
  Profit is counted after both fees; momentum comes from the runner's own
  record of each minute's quotes.
  - *Stop-loss*: 2% against the entry price.
  - *Momentum* (`legs.moving`): a steep move (1% or more the position's way in
    the last 30 minutes) is judged over those 30 minutes and has to keep 0.3%
    of it; anything gentler is judged over the last 5 minutes and has to show
    0.05%, so a stall is seen sooner.
  - *Momentum hold*: a crossover position that is at least 1% in profit, or a
    mean-reversion position at least 1.5% in profit, is held while the price
    is still moving its way and closed as soon as that move stalls.
  - *Profit lock*: once a position has been more than 1% in profit, it is
    closed if the price falls 0.75% from its best since entry.
  - *Fast-fall cut*: a losing position is closed when the price has moved 1.5%
    against it within 30 minutes.
- **Loss brake.** While equity is 2% or more below its highest value of the
  last 24 hours nothing new is opened; open positions keep their own exits.

Orders are market orders, one per minute, exits before entries. Shorts are 1x through the exchange's
short endpoints; an interrupted short request is settled from the exchange's
position list, and if the account is not allowed to short the long side keeps
trading. `roostoo/legs.py` holds the decision functions: the runner calls
them, and the research harness calls `decide` through
`research/lab/work/live_legs/`.

The same rules were first run live on October 8 on hourly Binance candles as
`config/regime_hourly_candidate.json` (48/200-hour EMAs, entry within 12 hours
of the cross and at 3 standard deviations of the 168-hour mean, risk-sized
crossover positions with a 6 x ATR(24h) trailing stop, 5% mean-reversion
positions held up to 48 hours, no minute exits). That evening the team added
the minute exits, larger sizes, looser entries and the loss brake
(`config/regime_hourly_exits_candidate.json`, branch `v4`), and then asked for
shorter bars, shorter windows, more coins and selling by momentum (branch `v5`).

`scripts/replay_bars.py` replays the runner itself over recorded candle closes
(`scripts/fetch_candles.py`), with the same fees and order throttle. On the 12
days to October 8 the live preset lost 13.5% (worst drop 14.0%), placing 60
orders a day and paying 0.66% of the account a day in fees; 48% of its trades
won, the winners averaging +1.0% of the position and the losers -1.5%. The
15-minute preset it replaced (`config/regime_15m_candidate.json`: 4/16-hour
EMAs, 24-hour z-score, no momentum test on entries) lost 7.8% over the same
days. None of some sixty variants replayed on one-minute, 5-minute and
15-minute bars (windows from 30 minutes to 24 hours, weaker and stronger entry
triggers, tighter and wider stops, with and without the momentum rules) made
money over those days: before costs the average trade earned at most about
0.1% of its position, against about 0.3% of fees, spread and slippage per
round trip. The team chose to run it.

Every window of the hourly preset except the two regime features came from the October 7 study
([`research/`](research/README.md)); the regime windows were chosen on the
design period among nine pairs. Run through that harness the hourly preset returned
+17.7% on the design period, +3.5% on the selection period, -13.5% on the
holdout and -19.2% on the older 12-coin set (+7.0%, -1.6%, -18.2%, -20.8%
under stress costs), trading on 84-93% of days. It roughly breaks even while
prices fall and loses in a broad rally. The study's breakout rule returned
+173%, +26%, +102% and +72% over the same periods; the team chose the regime
strategy, and the breakout preset stays in `config/breakout_candidate.json`
(point `ROOSTOO_CONFIG` at it to switch back). `scripts/test_short_canary.py`
opens and closes one 10 USD short on a general test account to show how the
exchange reports short positions; run it before relying on the short side.

The lower-risk alternative is the strength-gated trend ensemble
(`config/ranking_candidate_strength50.json` plus `drawdown_brake: 0.04`), which
the runner also supports: daily targets from 3/7/14/30-day trend votes, a 20%
volatility target, and exposure that scales to zero as equity falls 4% below
its 168-hour peak. Replayed by `scripts/live_windows.py` (34 independent
14-day episodes in the repository's own engine) it gave +0.40% mean with a
3.57% worst drawdown. A pair quoted wider than 1% is skipped for that cycle instead of
blocking the others, and a failed candle refresh keeps the previous targets.

The earlier regime-adaptive preset (three assets, six-hour refresh, 1% trailing
exit) was retired on October 6: in an hourly replay it flipped regime several
times a day and paid more in fees than its signal earned. Updating does not guarantee that a trade will occur. Plain `git pull` plus
restart still blocks an active ledger whose config hash changed; use
`aws_update.sh` for that case.

`aws_start.sh` installs Python and systemd, starts only `roostoo.bot`, and
keeps its persistent ledger at `/opt/roostoo/runs/aws/state.json`. It does not
install Node, Electron, or the desktop bundle. The service polls once per
minute, warms completed Binance hourly candles, reads current Roostoo quotes,
and remains paper-only unless `ROOSTOO_LIVE=1` is set in the root-owned env
file. An existing paper ledger cannot be reused in live mode; follow the
[paper-to-live transition procedure](docs/AWS_DEPLOYMENT.md#switching-an-existing-paper-deployment-to-live)
to preserve it and select the correct ledger. For subsequent restarts using
the same mode and ledger:

```sh
sudo systemctl restart roostoo-bot
sudo journalctl -u roostoo-bot -f
sudo systemctl stop roostoo-bot  # emergency stop; reconcile any in-flight order
```

Check the headless service logs with:

```sh
sudo systemctl status roostoo-bot --no-pager
sudo journalctl -u roostoo-bot -n 100 --no-pager   # recent entries
sudo journalctl -u roostoo-bot -f                  # follow live output
sudo journalctl -u roostoo-bot -b --no-pager       # logs since this boot
```

The runner also writes its durable event ledger to
`/opt/roostoo/runs/aws/state.jsonl`. Inspect it with
`sudo tail -f /opt/roostoo/runs/aws/state.jsonl`.

For a foreground smoke test without systemd, use paper mode and a finite cycle:

```sh
cd /opt/roostoo
set -a; . /etc/roostoo/roostoo.env; set +a
ROOSTOO_LIVE=0 .venv/bin/python -m roostoo.bot --config "$ROOSTOO_CONFIG" --state runs/aws/manual-state.json --cycles 1
```
