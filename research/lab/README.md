# Roostoo research lab

This is the harness as the research agents used it on 7 October 2026; the text below was their brief. Results and
conclusions are in `../README.md`. Build the panels first with `python research/lab/build_panels.py`.

Shared, read-only research harness. It was audited by three independent reviewers (about 1,300 tests: accounting
against an independent ledger, timing and look-ahead, fill rules, indicators, the regime model) and every defect they
found is fixed and covered by `selftest.py`. **Do not edit `harness.py`, `ind.py`, `regime.py`, `baselines.py` or anything in `data/`.**
`strategies.py` is also shared and read-only: copy from it or subclass it. Write your own code under `work/<your-track>/`.

Python: the repository's `.venv-lstm/bin/python` (NumPy, SciPy, scikit-learn; no pandas).
Run from this directory or add it to `sys.path`.

## The competition (what the strategy is for)

- Roostoo mock exchange, $100,000 start, about 11 days of trading left (ends Oct 17, 2026). The team is currently around -1.5%.
- Ranking: first a gate on total return (top 20 in region), then `0.4*Sortino + 0.3*Sharpe + 0.3*Calmar`.
- Spot long and 1x short only, no leverage. At most one order per minute. No HFT, market-making or arbitrage.
- Fees: spot MARKET (taker) 0.10%, spot LIMIT that rests (maker) 0.05%. Shorts: 0.10% of position value at open and at close,
  for market and limit alike; a short close always executes at the market ask. A short can lose at most its collateral.
- The bot decides from completed hourly candles and can poll quotes every minute.

## Data

`harness.load(name)` returns a `Panel` of hourly Binance candles (the exchange mirrors Binance prices):

| name | rows | period | who may use it |
|---|---|---|---|
| `design` | 7,519 | 2025-05-02 to 2026-03-11, 50 pairs | explorers: all tuning and selection |
| `select` | 10,025 | 2025-05-02 to 2026-06-24 | integrators only: rows 7,519+ are the selection period |
| `full` | 12,532 | 2025-05-02 to 2026-10-06 | verifiers only: rows 10,025+ are the final holdout |
| `early12` | 5,128 | 2024-10-01 to 2025-05-02, 12 majors | verifiers only: an older out-of-sample set |

`Panel`: `O, H, L, C, V` are `(T, N)` arrays, `pairs` the names, `ts` open times in ms, `hs` each pair's half-spread
(fraction; median about 1.2 bp, up to 13 bp for the smallest coins), `i('BTC/USD')` the column index.
The design period was a bear market: the average coin fell 45%, BTC 32%. A long-only rule that looks good here is not
automatically good, and a short rule that looks good here may just be riding that bear market. Check sub-periods.

## Harness in one example

```python
import harness as h, ind
from harness import Order

class MyStrategy:
    def __init__(self, panel, fast=20, slow=100):
        self.P = panel
        self.f = ind.ema(panel.C, fast); self.s = ind.ema(panel.C, slow)   # causal, computed once
    def on_bar(self, t, book):
        # Called at the close of bar t. Use rows <= t only. Orders execute during bar t+1.
        orders = []
        for i in range(self.P.N):
            up = self.f[t, i] > self.s[t, i]
            pos = book.pos.get(i)
            if up and pos is None and not book.has_pending(i):
                orders.append(Order(i, 'BUY', usd=book.equity * .1, limit=self.P.C[t, i] * .999, ttl=2,
                                    fallback='cancel', stop=self.P.C[t, i] * .95, tag='trend'))
            elif not up and pos is not None and pos.side > 0:
                orders.append(Order(i, 'SELL', tag='trend'))
        return orders

P = h.load('design')
make = lambda panel: MyStrategy(panel)
r = h.backtest(P, make(P), start=744)          # leave room for indicator warm-up
print(r.summary()); print(r.windows(11)); print(r.by('tag')); print(r.by('reason'))
print(h.causality_check(make, P))               # must return (True, None)
```

Timing and fills (all in `Book.process_bar`), for bar t+1 after a decision at the close of bar t:

1. Market orders fill at the open of t+1, at the ask (buy) or bid (sell), plus slippage, taker fee.
   `SHORT` and `COVER` are always market fills with the short fee.
2. A `BUY`/`SELL` with `limit>0` rests for `ttl` bars. It fills at the limit price with the maker fee once the bar's low
   (buy) or high (sell) trades through it by the pair's full spread plus `through_bps`, or if the bar opens beyond it.
   A limit that is already marketable when placed (buy limit >= last close) is treated as a taker market order.
   Unfilled at expiry: `fallback` is `'cancel'` or `'market'` (taker at the next open). An order that has expired and
   will not trade again is already gone when `on_bar` runs. A resting `SELL` is removed when its position closes, never
   fills in the bar its limit entry filled, and loses to a stop touched in the same bar. A limit `BUY` on a pair that is
   short (or a `SHORT` on a pair with a resting `BUY`) is rejected.
3. Then protective levels on open positions: a stop (`Position.stop`) fills at the stop price (never above the open, nor
   above a limit fill made in the same bar), less spread, slippage and `stop_slip_bps` of overshoot, as a taker. The
   exchange has no stop orders: a stop is the bot sending a market order after its one-minute poll. A long's `take` is a resting maker sale at that price; a short's `take` is a market
   cover. If a bar touches both, the stop wins. A take-profit never fires in the bar its limit entry filled.
   Strategies trail stops by calling `book.set_stop(pair, level)` each bar.

`book`: `cash`, `free_cash`, `equity`, `pos` (dict pair index -> `Position` with `side, qty, entry, t_in, tag, stop, take,
hi, lo`), `longs()`, `shorts()`, `pending`, `has_pending(i)`, `cancel(i)`, `set_stop`, `set_take`.
One net position per pair. Buys are capped by free cash (no leverage); cash can dip below zero only by the close fee of a
short whose loss reached its collateral. `frac` must be in (0, 1] and every order field finite, or the harness raises.

`Costs(maker_bps=5, taker_bps=10, short_bps=10, spread_mult=1, slip_bps=2, stop_slip_bps=8, through_bps=2)` is the default.
The stress case is `evalkit.STRESS` (maker fills charged like takers, 3x spreads, more overshoot, limits must trade
30 bp through). How the real exchange fills resting orders has not been measured, so a result that needs the maker fee
or a generous fill rule to be positive is not a result. Six pairs have a price tick above 10 bp (PEPE, 1000CHEEMS, SHIB,
BONK, STO, LISTA): limit prices on them cannot be placed finely, so check any limit-order result without them.

Results: `r.eq` hourly equity, `r.trades`, `r.summary()` (return, drawdown, Sharpe/Sortino/Calmar/composite, trades,
win rate, fees, turnover, limit fill rate, share of days with a fill), `r.windows(days=11)` (distribution over every
11-day stretch of the continuous run), `r.by('tag'|'side'|'reason'|'pair')`. `h.fresh_windows(panel, make, days=11)`
restarts flat for each window (slower; closer to a new competition). `composite` is NaN when a ratio is undefined (no
losing day, no drawdown) and Calmar dominates it on short spans: compare the three ratios separately and use nan-aware
functions.

`h.causality_check(make, panel)` replaces every candle after each of 40 cut points with an unrelated random path,
rebuilds the strategy with `make(altered_panel)`, and requires every earlier order, stop, target and resting order to
be identical. So `make(panel)` must build every feature from the panel it is given (never from a panel captured outside),
and the strategy must work when started `warm=400` bars before any point (indicators come from the panel, not from
having been run since bar 0). The check fails if the strategy never acts or ignores its panel. It catches full-sample
fits at once and one-bar slips with high probability, not certainty: still read your indexing.

`strategies.py` has reference implementations of the two families under study: `EmaCross` (fast/slow EMA, optional
trend EMA, ATR trailing stop, long/short/both), `ZScoreMR` (rolling z-score entry, exit at the mean with a resting maker
sale, hard stop, time limit, optional RSI and confirmation) and `Portfolio(panel, parts, slots)` which gives them shared
equal slots. Both parts take `entry='market'|'limit'` and `allow_long` / `allow_short` (T, N) boolean arrays, which is
where a regime filter plugs in. Example: `make = lambda p: Portfolio(p, [EmaCross(p, 24, 100), ZScoreMR(p, 48, 2.)], slots=4)`.

`evalkit.report(make, panel, name=...)` runs the standard evaluation in one call (summary, 11-day windows, thirds,
P&L by tag/side/exit reason, stress costs, look-ahead check), prints one line and returns a dict. Use it for every
variant you report so numbers are comparable across tracks; `evalkit.save(dict, path)` writes it as JSON.

`ind.py`: `sma, ema, wma, rstd, zscore, rmax, rmin, ret, logret, rsi, atr, bollinger, efficiency_ratio, cross_count,
realized_vol`. All causal, `(T, N)` in and out, NaN during warm-up.

`regime.py`: the K-Means-initialised Gaussian HMM of Haryani, Chandra and Tarigan (2026). `walk_forward(X, first_train,
step, K, order_by, use_hmm)` takes `(T, N, d)` features and returns labels that never see the future (one model shared
across coins, refit on an expanding window). The paper text is in `data/paper57.txt`.

## Benchmarks (default costs, `start=744`)

| split | strategy | total | max drawdown | 11-day windows: mean / median / >=+10% / <=-10% |
|---|---|---|---|---|
| design | `baselines.Breakout` (the rule now on branch v2) | +40% | 43% | +2.1% / -0.6% / 23% / 12% |
| design | BTC buy and hold | -32% | 50% | -1.5% / -1.2% / 2% / 11% |
| design | `EmaCross(9, 21, 55)` long, 4 slots (textbook windows on hourly candles) | -87% | 89% | -7.0% / -8.9% / 10% / 43% |
| design | `EmaCross(24, 100)` long, limit entries | -39% | 58% | -1.5% / -2.8% / 15% / 18% |
| design | `ZScoreMR(48, 2.0)` long, limit entries | -50% | 56% | -2.3% / -1.5% / 6% / 16% |
| design | cash | 0% | 0% | 0 |

The breakout benchmark's three sub-periods returned +12%, +61%, -23%, and +4% in total under stress costs: even the
best rule found so far is fragile. "Beats cash after stress costs in most sub-periods" is the bar; beating the breakout
benchmark is the goal.

## Rules of evidence

- Explorers use `design` only. Do not load the other panels. Selection and holdout runs are done by other agents.
- Every candidate must pass `h.causality_check`. Anything fitted (scalers, clusters, thresholds from quantiles) must be
  fitted on past data only, inside the strategy, so the check can catch it.
- Report what you tried, including what failed, and how many variants you ran. Prefer a plateau of nearby parameter
  values that all work over one best setting. Split the design period into thirds and report each.
- Always report: total return, max drawdown, 11-day window mean/median/win/tails, trades, win rate, turnover, fees,
  P&L by tag and by side, the stress-cost result, and the share of days with a fill (the competition needs trades on
  at least 8 of 14 days).
- A result that depends on one coin, one month, or the exact parameter value is noise. Say so.
- Earlier findings on this data (do not assume, re-test if relevant): a long-only breakout rule is the only thing found
  with a positive average so far; buying dips (mean reversion) in a market labelled "chop" lost in 22 variants; shorting
  breakdowns lost on average; a Bitcoin volatility-regime HMM was stable but did not predict direction.
