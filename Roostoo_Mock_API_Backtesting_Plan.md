# Backtesting with the Roostoo Mock API

This plan describes how to build a repeatable backtesting workflow around the Roostoo mock API documented in this repository.

The API host used by the examples is:

```text
https://mock-api.roostoo.com
```

The plan covers spot trading through `/v3` and short positions through `/v6`. Partner endpoints under `/v2` are for competition and account administration; they are not needed to simulate a trading strategy.

## 1. Decide which backtest you are building

There are two useful modes:

| Mode | Purpose | Main data source |
| --- | --- | --- |
| Offline replay | Evaluate a strategy deterministically against a saved market timeline | Locally stored ticker snapshots or another historical dataset |
| API-connected paper run | Check that signing, order construction, state handling, and API responses work correctly | Live responses from the mock API |

Use offline replay to measure strategy performance. Use the API-connected run to validate integration behavior. A mock API request by itself does not create historical candles or a historical order book.

## 2. Confirm the API's backtesting limits

The repository documents these market-data endpoints:

- `GET /v3/serverTime` returns the server clock.
- `GET /v3/exchangeInfo` returns tradable pairs, precision, and minimum order rules.
- `GET /v3/ticker` returns current ticker values such as `MaxBid`, `MinAsk`, `LastPrice`, `Change`, and trade values.

The documentation does not provide a historical candles endpoint, historical trades endpoint, or historical order-book endpoint. Therefore, an offline backtest needs one of these inputs:

1. **Recorded snapshots:** poll `/v3/ticker` at a fixed interval and store each response with a local timestamp.
2. **Synthetic market data:** generate a deterministic price series for development and unit tests.
3. **An external historical dataset:** normalize it to the fields used by the simulator, while keeping the Roostoo execution and precision rules.

Do not describe a result as a historical Roostoo performance result unless the input data is actually historical and its provenance is recorded.

## 3. Capture and normalize market data

### 3.1 Snapshot collector

For each polling interval:

1. Call `/v3/serverTime` and save the returned `ServerTime`.
2. Call `/v3/ticker` for each pair you want to trade, or call it without `pair` to capture all listed tickers.
3. Store the response, HTTP status, local receive time, and request parameters as an immutable raw record.
4. Record failures and gaps instead of silently dropping them.

A raw snapshot record should contain at least:

```json
{
  "received_at_ms": 1580762734517,
  "server_time_ms": 1580762734517,
  "pair": "BTC/USD",
  "max_bid": 9318.45,
  "min_ask": 9319.42,
  "last_price": 9319.35,
  "change_24h": -0.0095,
  "coin_trade_value": 53001.931315,
  "unit_trade_value": 496450629.05850565,
  "raw_response": {}
}
```

Store the raw JSON as well as normalized columns. The raw response lets you audit a result when the API schema or your parser changes.

### 3.2 Data-quality checks

Before a snapshot enters a backtest:

- Confirm the pair exists in `/v3/exchangeInfo` and `CanTrade` is true.
- Confirm timestamps are 13-digit milliseconds.
- Reject or flag snapshots where `MaxBid > MinAsk` unless the source explicitly permits it.
- Detect duplicate timestamps, out-of-order records, and long gaps.
- Keep the original precision; do not round prices or quantities during ingestion.
- Record the data-collection interval and timezone (use UTC internally).

### 3.3 Build a replay timeline

Sort snapshots by server time, then group them into a fixed simulation clock such as 1 second, 5 seconds, or 1 minute. Define the rule for multiple observations in one interval, for example “use the last valid snapshot.” Keep the original event time so the simulator can model latency.

## 4. Read exchange rules before simulating orders

Call `/v3/exchangeInfo` at the beginning of every run and save the exact response with the run configuration.

For each pair, use:

- `PricePrecision` to round prices to the allowed decimal precision.
- `AmountPrecision` to round quantities down to the allowed decimal precision.
- `MiniOrder` to verify that `order_price * order_amount > MiniOrder`.
- `InitialWallet` as the starting balance when your test is meant to mimic a competition account.

Keep a single normalization function so live requests and offline simulation apply the same rules.

## 5. Implement a strategy interface

Keep the strategy independent from HTTP and portfolio accounting. A strategy should receive a market event and a read-only portfolio view, then return an intent.

```python
class Strategy:
    def on_start(self, context):
        pass

    def on_market(self, event, portfolio):
        # Return zero or more intents.
        return []

    def on_finish(self, context):
        pass
```

An intent can be represented as:

```python
{
    "action": "BUY",          # BUY, SELL, SHORT_OPEN, SHORT_CLOSE
    "pair": "BTC/USD",
    "order_type": "MARKET",   # or LIMIT
    "quantity": 0.01,
    "price": None,
    "reason": "moving_average_cross"
}
```

For short positions, use `collateral` for `SHORT_OPEN` and either `close_qty` or `close_pct` for `SHORT_CLOSE`.

## 6. Simulate spot execution

### 6.1 Market orders

Use the documented ticker sides consistently:

- A simulated BUY fills at `MinAsk`.
- A simulated SELL fills at `MaxBid`.

Apply a configurable latency or slippage model before filling. At minimum, support:

```text
fill_price = observed_side_price * (1 + slippage)
```

Use positive slippage for a buy and negative slippage for a sell. If the dataset does not contain depth, do not claim that the simulation models partial fills or market impact.

### 6.2 Limit orders

The API documents LIMIT orders as pending maker orders when they do not immediately match. A basic replay model is:

- BUY limit fills when a later `MinAsk` is less than or equal to the limit price.
- SELL limit fills when a later `MaxBid` is greater than or equal to the limit price.
- An order remains pending until it fills, is canceled, expires under your chosen policy, or the backtest ends.

Use a conservative tie rule. If the same snapshot both triggers a limit order and generates the signal, fill on the next snapshot unless you have tick-level data that establishes the sequence.

Track each simulated order with an internal ID and preserve:

- submitted time;
- pair, side, type, price, and quantity;
- filled quantity and average fill price;
- status (`PENDING`, `FILLED`, `CANCELED`);
- commission and cash/asset changes.

### 6.3 Fees

The spot examples expose `CommissionCoin`, `CommissionChargeValue`, and `CommissionPercent`. Configure the simulator with the commission schedule appropriate to the mock competition or test. If the schedule is unknown, run sensitivity cases rather than silently assuming zero fees.

## 7. Simulate short positions

The short endpoints use `/v6` and the same signed authentication model as the signed `/v3` endpoints.

### 7.1 Opening

`POST /v6/short_open` takes:

- `pair`;
- `collateral` in USD, with a documented minimum of 1;
- optional `order_type=LIMIT` and `price`;
- `timestamp`.

A market short fills at the current `MaxBid`. The documented quantity is approximately:

```text
short_qty = floor(collateral / entry_price, AmountPrecision)
```

The documentation charges an open fee of 0.1% of the position value. Deduct that fee when the position is accepted and reserve collateral while the position is open or pending.

For a LIMIT short, keep the collateral and fee reserved while the order is pending. Fill it according to the same trigger rule used by the API description, then convert the pending order into an open position.

### 7.2 Closing

`POST /v6/short_close` always fills at the current `MinAsk` in the documented model.

Use these rules:

```text
realized_pnl = closed_qty * (entry_price - close_price)
close_fee = closed_qty * close_price * 0.001
return_amount = closed_collateral + realized_pnl - close_fee
```

`close_qty` takes precedence over `close_pct`. If neither is provided, close the whole position. Clamp a requested quantity to the open quantity so the simulator cannot turn a short into a long position.

### 7.3 Mark-to-market

At every market event calculate:

```text
unrealized_pnl = short_qty * (entry_price - current_min_ask)
position_value = collateral + unrealized_pnl
unrealized_pnl_pct = unrealized_pnl / collateral
```

Keep open-position collateral separate from free USD. This prevents the backtest from spending margin twice.

## 8. Build the portfolio and accounting engine

The accounting engine should be the only component allowed to mutate balances. It should maintain:

- free balances by asset;
- locked balances for pending spot orders;
- open spot positions or inventory lots;
- open short positions and reserved collateral;
- realized PnL;
- unrealized PnL;
- commissions;
- order and fill history;
- equity curve snapshots.

At each event, process in a fixed order:

1. advance the clock;
2. update market marks;
3. fill eligible pending orders;
4. release locks for fills or cancellations;
5. call the strategy;
6. validate and submit new intents;
7. record an end-of-event portfolio snapshot.

This ordering must be documented because changing it can create look-ahead bias.

## 9. Avoid common backtest errors

- **Look-ahead bias:** never let a signal see a future ticker or a same-tick fill unless the data proves the order of events.
- **Timestamp mismatch:** use 13-digit milliseconds for API calls and store all internal times in UTC.
- **Wrong side of the market:** buy against `MinAsk`, sell against `MaxBid`.
- **Ignoring precision:** apply `PricePrecision`, `AmountPrecision`, and `MiniOrder` before submitting an order.
- **Free-balance leakage:** lock funds for pending orders and short collateral.
- **Unrealistic fills:** ticker data does not reveal queue position, depth, or partial-fill behavior.
- **Fee omission:** report results with and without fees, and include fee totals in the run output.
- **Survivorship bias:** retain delisted or unavailable pairs in the data manifest rather than selecting only successful runs.
- **Using API state as history:** `/v3/query_order` and `/v6/short_positions` describe the current mock account; they are not substitutes for a historical event stream.

## 10. Validate the simulator against the API

Before trusting strategy results, run a small deterministic validation suite against the mock API or a fixture that reproduces its documented responses.

### Authentication tests

- Verify the sorted `key=value&...` signature string.
- Verify HMAC-SHA256 with the secret key.
- Verify GET signatures use query parameters and POST signatures use the form body.
- Verify the 60-second timestamp window.
- Verify signed POST requests send `Content-Type: application/x-www-form-urlencoded`.

### Order tests

- MARKET BUY and SELL use the expected ticker side.
- LIMIT orders remain pending until their trigger condition.
- Canceling by `order_id`, by `pair`, and with no filter follows the documented behavior.
- Querying by `order_id` rejects incompatible optional filters.
- Precision and minimum-order checks reject invalid orders.

### Short tests

- Market opening uses `MaxBid`.
- Closing uses `MinAsk`.
- Open and close fees are applied once.
- Partial close reduces quantity and collateral proportionally.
- Full close removes the position.
- A close request larger than the open quantity is clamped.

## 11. Produce reproducible run artifacts

Every backtest run should write a directory such as:

```text
runs/2026-10-01T12-00-00Z/
├── config.json             # strategy parameters and simulator settings
├── exchange_info.json      # exact exchange rules used
├── data_manifest.json      # input files, ranges, and checksums
├── signals.jsonl           # strategy decisions
├── orders.jsonl            # submitted, filled, and canceled orders
├── equity_curve.csv        # timestamp, cash, inventory, margin, equity
├── metrics.json             # summary statistics
└── report.md               # human-readable results and caveats
```

Include the strategy version or Git commit, Python version, random seed, fee model, slippage model, latency model, data interval, and starting wallet. A result without these fields cannot be reliably reproduced.

## 12. Report useful metrics

At minimum, report:

- total return and annualized return;
- starting and ending equity;
- maximum drawdown and drawdown duration;
- volatility and downside deviation;
- Sharpe and Sortino ratios, with the assumed period and risk-free rate;
- total trades, winning trades, losing trades, win rate, and profit factor;
- average win, average loss, expectancy, and average holding time;
- gross PnL, commissions, slippage cost, and net PnL;
- exposure, turnover, and time in the market;
- for shorts: open/close fees, margin utilization, liquidation or max-loss events, and open-position PnL.

Always show the equity curve and a table of assumptions beside the results.

## 13. Recommended implementation sequence

### Phase 1 — Fixtures and rules

- Save representative `/v3/exchangeInfo` and `/v3/ticker` responses.
- Implement timestamp, precision, pair, and minimum-order validation.
- Implement HMAC signing as a separate tested utility.

### Phase 2 — Market data and replay

- Build the snapshot collector and raw-data store.
- Normalize snapshots into a deterministic replay timeline.
- Add gap and quality checks.

### Phase 3 — Spot simulator

- Implement balances, pending orders, market fills, limit fills, cancellation, and commissions.
- Compare simulated state transitions with the documented `/v3` response shapes.

### Phase 4 — Short simulator

- Implement collateral reservation, open fees, mark-to-market PnL, partial close, full close, and close fees.
- Add tests for price movement in favor of and against the short.

### Phase 5 — Strategy and reporting

- Add the strategy interface and one deliberately simple baseline strategy.
- Generate run artifacts, metrics, equity curves, and assumptions.
- Run parameter sensitivity and out-of-sample tests.

### Phase 6 — API-connected paper validation

- Run the same order adapter against the mock API using test credentials.
- Compare API responses and account state with the local simulator.
- Keep this validation separate from performance results.

## 14. Minimal project layout

```text
backtest/
├── collect_tickers.py       # optional live snapshot collector
├── data.py                   # raw storage and replay timeline
├── rules.py                  # exchange precision and validation
├── signing.py                # HMAC request signing
├── execution.py              # spot and short fill models
├── portfolio.py              # balances, locks, margin, and PnL
├── strategy.py               # strategy interface and implementations
├── engine.py                 # deterministic event loop
├── metrics.py                # performance statistics
├── report.py                 # CSV/Markdown outputs
└── tests/
    ├── fixtures/
    ├── test_signing.py
    ├── test_spot_execution.py
    ├── test_short_execution.py
    └── test_replay_ordering.py
```

Start with a deterministic fixture and a single pair. Add more pairs, external data, and realistic execution assumptions only after the accounting and event ordering tests pass.
