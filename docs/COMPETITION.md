# Competition constraints and readiness

Read from all 59 pages of `plan.pdf`, the 35-page scanned API guide (OCR), and the backtesting plan. The research report contains duplicated material and some contradictory judging summaries; the explicit screening sequence below is the working interpretation.

## Rules that affect the implementation

- Preparation: October 1–3. Trading: October 4–17, 14 full days. At least eight active trading days, with an unspecified minimum amount of strategy activity each day.
- Screening: compliance first; then regional top 20 by portfolio return; then `0.4 × Sortino + 0.3 × Sharpe + 0.3 × Calmar`; then implementation/code review. A later generic 40/30/20/10 judging rubric is inconsistent with this sequence and needs organizer confirmation.
- $100,000 competition starting portfolio. The public exchange metadata and the general test account actually report $50,000; they must not override the competition specification.
- One trade per minute globally. No HFT, market-making, or arbitrage. Only 1× spot long/short, no leverage. Individual accounts can still prohibit shorts.
- Taker commission 0.1%; maker commission 0.05%. Older API sample commission percentages differ; research uses the competition rates. Short opening and closing are documented at 0.1%, including short limit openings.
- Autonomous competition trades, transparent source and commit history, and an AWS-hosted bot. No manual competition-account trading.
- Repository submission before October 14; activity and strategy provenance are required, not just a pretty equity curve.

## Problems found in the supplied examples

The FreqAI example computes a future-volatility quantile over the entire dataset. That leaks future distribution information into the regime labels. It also equates high volatility with trending, which is not generally valid. None of that code was copied into the causal strategy engine.

The API guide's old ticker example uses seconds; calls need 13-digit milliseconds. Signed bodies use sorted decoded `key=value` pairs with the literal slash in pair names. `Success=false` can accompany HTTP 200. Current balances use `SpotWallet`/`MarginWallet`, not the older `Wallet` example.

Roostoo has no documented historical candles endpoint. Binance OHLCV is an external proxy and cannot establish historical Roostoo fill quality. Current pair precision also does not resolve survivorship or historical listing rules.

## Promotion requirements

1. A candidate must survive economically meaningful validation and cost stress. Preserve all failed experiments. Later historical periods already inspected are no longer fresh holdouts.
2. Record actual Roostoo spread, timing, and failure behavior prospectively. Reconcile canary fills, fee coin, precision, and returned balances. Test shorts separately if a chosen strategy needs them.
3. Run the same decision logic prospectively without tuning on the subsequent results. Watch activity across a rolling 14-day horizon; do not manufacture token trades to satisfy the rule.
4. Validate the implemented persistent allocation runner under live-account failure scenarios: persisted intent before submission, state reconciliation at startup, no blind retry after POST timeout, account-wide 60-second throttle, stale-price lockout, and a single-process lock. Unit tests cover ambiguity and restart blocking; broader live-account crash/recovery validation remains.
5. Configure the actual EC2 host, service restart, secrets, monitoring, and competition account. Those AWS access details are not in the supplied workspace. Submit the open-source repository and freeze a traceable deployment revision.

The current project completes research infrastructure and desktop inspection. It does not claim these outstanding deployment requirements are complete.
