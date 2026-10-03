# Research results — October 1, 2026

**Decision: no candidate is ready for competition deployment.** This is a rejection result, not a failed software test. We have a working evaluation and inspection system; we do not have demonstrated alpha.

## Data and experiment design

Two years of hourly Binance spot candles, October 1, 2024 through September 30, 2026. The expanded universe is BTC, ETH, SOL, BNB, XRP, DOGE, ADA, LINK, AVAX, SUI, LTC, and AAVE. All are currently listed on Roostoo. USDT is mapped to USD as an explicit proxy. Historical Roostoo spreads, depth, listing histories, and impact are unavailable.

The first study used 60/20/20 chronological training/validation/holdout over three assets. The selected trend strategy earned +9.78% on training, lost 7.30% on validation and 5.91% on holdout, and hit its drawdown halt. A passive equal-weight basket gained 18.24% over that holdout, with materially different exposure and risk.

The later studies use 49 independent, non-overlapping 14-day episodes: 29 training, 10 validation, 10 later-period evaluation. Each starts with a flat $100,000 wallet. Configurations are chosen on training only. **Because we already inspected later history, subsequent studies are exploratory and cannot be called fresh untouched holdouts.** Returns below are arithmetic means across separate competitions, not a compounded continuous strategy.

Base execution assumptions: 10 bps fee per side, 4 bps spread, 3 bps adverse slippage per side. Stress: 20 bps fee, 10 bps spread, 10 bps slippage. Orders use the next candle open. The 8% drawdown halt is a trigger, not a guaranteed loss limit.

## Selected candidates by experiment

| Experiment | Validation mean | Later mean | Later median | Stress mean | Later ≥8 active days |
| --- | ---: | ---: | ---: | ---: | ---: |
| Three-asset contest windows | -0.41% | +0.95% | -0.15% | +0.31% | 50% |
| Twelve-asset strategy search | -0.44% | -0.24% | -0.05% | -0.69% | 40% |
| Partial allocation | -0.70% | +1.15% | -0.80% | -0.04% | 90% |

The partial-allocation candidate's positive later average is concentrated in a few winning episodes: only 30% of those episodes were profitable. Its negative median, negative validation mean, and slightly negative stressed mean make it unsuitable for promotion. None of the broader search's candidates passed its combined training profitability/activity gate. A fallback is still saved for inspection; **the saved candidate is not an endorsement**.

## What changed based on evidence

- Replaced the document's future-volatility label approach with causal indicators. The provided full-data quantile would leak information.
- Evaluated both absolute return and risk, because leaderboard qualification occurs before the composite-score screen.
- Added contest-length episodes; a permanently halted multi-month run is a poor proxy for a fresh 14-day competition.
- Expanded beyond three assets and tested daily rotation, pullback, mean reversion, and partial allocation. Preserved negative results.
- Added FIFO partial sales and volatility budgets to measure whether lower turnover helps. It did not produce a robust enough edge.
- Treat at least eight active days as a reported feasibility constraint. Do not manufacture trades for eligibility. The organizer's “enough trades” definition still needs clarification.

## Integration evidence

Authenticated reads succeeded against the general testing account. Its balance schema is `SpotWallet`/`MarginWallet`, and its starting cash is $50,000, unlike the competition's $100,000.

The finite general-account canary completed a roughly $10 BTC market buy and sell, with more than 60 seconds between them. Both commissions were 0.1% charged in USD. The final BTC balance was zero. The journal is `runs/canary/journal.json`. No competition-account trades were placed.

The persistent paper runner completed three public-data cycles and two local simulated fills using current Roostoo quotes. It retained its wallet, pending intent, global throttle, and peak-equity state. This is an integration check, not performance evidence. Twenty-five automated tests cover accounting, causality, FIFO partial sales, the risk halt, signed payloads, and ambiguous-order restart blocking.

The desktop app is connected to the actual engine and supports per-trade inspection, chart markers, filtering, sorting, JSON import/export, CSV export, and new backtests. The bundled historical episode is illustrative, not selectively presented as performance evidence.

## Next evidence needed

Prospective paper observations with the model frozen, confirmation of exact scoring/activity rules, and execution validation under the same cadence and universe. The current data does not support a prediction that any tested candidate will win. Reusing the same history for more parameter search would weaken, not strengthen, that claim.
