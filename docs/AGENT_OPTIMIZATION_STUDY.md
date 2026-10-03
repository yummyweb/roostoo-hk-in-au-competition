# Parallel optimization study — October 4, 2026

Three independent research agents examined the current 50-asset Diversified Trend Ensemble. They used the existing Binance hourly dataset and execution simulator. Agents were instructed to avoid production-file edits, report costs and drawdown, and use chronological validation.

The control is the frozen `trend_budget_vol15_liq50` preset in `config/ranking_candidate.json`: later return **+2.63%**, maximum drawdown **0.65%**, higher-cost return **+2.50%**.

## Regime and signal track

This track tested minimum positive trend votes, 3/7/14/30-day horizon changes, broad-market regime gates, liquidity breadth, rebalance cadence, drift bands, volatility targets and per-asset caps. Its selection score was the mean of validation return minus 1.5 times maximum drawdown over the 60–70% and 70–80% blocks.

The validation-selected broad-market gate returned only **+0.10%** in the later period and **−0.11%** under stress. The best later diagnostic required at least three positive trend votes: **+9.49%**, **2.40% drawdown**, and **+7.63% stress**, but validation included **−8.37%** in one block. It remains rejected. The full artifacts are in `runs/agent-regime/`.

## Relative-value and pairs track

The agent tested rolling beta-adjusted spreads with causal lookback/entry/exit/holding rules and simultaneous two-leg next-open fills. A selected APT/BTC configuration made **+15.40% validation** but **−8.76% final stress**. Another S/STO pair reached **+103.1% validation** but **−7.86% final**, **−9.06% at 25 bps per leg**. These are classic selection reversals, and the current spot simulator cannot guarantee simultaneous exchange fills or short-leg availability. The pair artifact is `runs/agent-pairs/research.json`.

## Portfolio and risk track

With the current trend signal held fixed, the agent tested strength gates, top-N breadth, volatility targets and rebalancing. Later diagnostics reached **+8.71%** with **+6.42% stress** for a strength gate and **+15.66%** with **+12.56% stress** for a top-20 allocation. Those results were not selected using the project’s two-validation-block protocol; they used a broader 60–80% validation summary and were reported after the final period was already known. They are therefore exploratory and remain unpromoted.

## Decision

The portfolio study's reproducible strength-gated candidate is now available as `config/ranking_candidate_strength50.json`. It keeps assets with at least 2 of 4 positive trend votes, uses a 20% volatility target, 20% per-asset cap, 1% drift band and 24-hour rebalance. The production replay reproduces **+8.71%** final return, **5.50%** maximum drawdown and **+6.42%** at higher modeled costs; validation was **+8.50%**. The final period was already present in the study and remains exploratory historical evaluation, so this preset is clearly labeled a research candidate and does not replace the conservative default.

No agent produced a validated net return above 50%, and no result supports a guaranteed competition outcome. The higher later returns are selection-sensitive and the pairs/regime alternatives reverse under validation or cost stress. The next meaningful optimization is prospective: freeze the 50-asset universe and rules, paper trade with current Roostoo quotes, and collect decisions, fills, slippage and active-day evidence before tuning again.
