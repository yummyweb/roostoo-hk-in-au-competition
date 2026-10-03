# Paper synthesis and strategy decision

I reviewed all 34 PDFs in `collection of papers/` and extracted the claims that could be tested with our Binance spot OHLCV, exchange rules, and one-fill-per-minute simulator. The papers do not justify choosing a newer model because it is newer. Their common warning is the translation chain: information must be available at the decision time, survive portfolio construction, execute after fees and spread, and remain useful in later regimes.

## What the papers support

- **Crypto trading survey (Fang et al., 2003.11352v5)**: the literature is broad, but datasets, costs, survivorship and evaluation protocols vary. Use multiple assets, causal features and explicit baselines.
- **Multi-timeframe confirmation (ssrn-6683818)**: requiring a slower trend to agree filters noise, but its nine-trade ETH sample is too small for a performance claim. We use multi-horizon confirmation as a portfolio gate, not as proof of alpha.
- **Asset classification, trading and portfolio management (ssrn-6277859)**: time-series momentum is most useful in volatile or bearish regimes; heavy tails and correlations make naive mean-variance sizing unsafe. We use volatility budgeting and cash when trend votes disagree.
- **Crypto asset pricing and efficiency (ssrn-3898534)**: volume-weighted and market-index factors matter, and efficiency varies by sampling interval and regime. We add a dollar-volume gate and avoid uniform exposure to illiquid assets.
- **Pairs Trading in Crypto (ssrn-6188418)**: pair selection needs correlation/cointegration, structural filters and stability diagnostics. We did not deploy naive pairs because the current spot simulator cannot guarantee simultaneous legs and the supplied competition rules make execution sequencing material.
- **Short-horizon mean reversion (2608.21888)**: the sign reversal is detectable, but its gross edge peaks near 1.3 bps per trade against at least 5 bps round-trip spot costs. We explicitly reject a high-frequency reversal overlay with hourly taker execution.
- **L2 liquidity-state transitions (2607.09230)**: liquidity state is predictive around event windows, but the effect is demonstrated with L2 and trade-flow data, not our hourly candles. We do not fabricate order-book features.
- **Frequency-controlled information bars (2608.26158)**: tick-built information bars differ from bars made from one-minute OHLCV. We keep the strategy on synchronized hourly candles and do not claim tick-level evidence.
- **Regime-aware PPO-HRAP (2610.01325)**: portfolio state, drawdown, turnover and regime priors belong in the objective. Its SPY-only result does not transfer automatically; our deterministic risk controls implement the transferable part.
- **Model replacement gating (2607.28577)**: challengers should run in shadow and replace an incumbent only after delayed, paired evidence. The selected research preset is frozen; there is no live self-retraining.
- **AI profitability review (2609.04917)**: no general AI architecture has established persistent, capacity-aware net alpha across regimes. This is why LSTM, ridge, boosted trees and trend rules are compared on the same data and stress costs.
- **Grid trading critique (ssrn-7376359)**: apparent grid gains can be exposure, maker-fee assumptions or incomplete fills. We do not use grids.
- **Algorithmic trading architecture (ssrn-7273019), shared models/order flow (2610.01897), DRL execution (2610.00619), autonomous deep learning (ssrn-3438824), DRL patents (ssrn-3570254), Generative AI in trading (ssrn-5209125), QuantCode Model (2609.39420), and adaptive human/AI trading (ssrn-6477100)**: these are architecture, governance, execution-game, or workflow contributions. None provides a validated spot alpha that can be copied into this competition.
- **Volatility loss choice (2609.27024)**: forecast-level calibration can matter as much as model choice. We use realized volatility for sizing and evaluate net portfolio outcomes rather than treating a low forecast loss as a trading result.
- **Prediction-market hedging (2609.14267), event-linked Kalshi research (2610.00173), and exchange/platform/legal papers (ssrn-2884777, ssrn-3620154, ssrn-3719545, ssrn-3723132, ssrn-4405361)**: these address hedging instruments, event-contract availability, platform mechanics, legal risk and financial stability. They do not create an available Roostoo spot signal.
- **The remaining empirical and methodological papers**—quantitative ML trading (DSMM2019 preprint), crypto asset classification, crypto market efficiency, order-flow/liquidity and related SSRN studies—reinforce the same design requirements: cross-asset diversification, regime conditioning, volume/liquidity awareness, and strict out-of-sample testing.

## Implemented paper-informed strategy

The new **Diversified Trend Ensemble** uses 50 actual, tradable Binance/Roostoo crypto pairs. Each asset receives equal votes from positive 3-, 7-, 14- and 30-day returns. Allocations are inverse-volatility weighted, capped at 20% per asset, limited to a 15% annualized portfolio volatility budget, and restricted to the most liquid assets when the preset says so. Daily partial rebalancing, a 2% drift band, next-open fills, modeled spread/slippage and the 8% drawdown halt remain in force.

The 50-asset universe contains 619,600 synchronized hourly rows from May 2, 2025 through September 30, 2026. Every source file is a real Binance public spot history; the common window is the intersection of available coverage. No synthetic pre-listing candles are inserted. The asset list is fixed before the 50-asset replay, but current membership still creates survivorship bias.

The final preset was selected on two validation blocks before its later replay. The validation candidates were ridge 72-hour ranking and trend ensembles with 15%/25% volatility budgets and liquidity gates of 15/25/50 assets. The validation objective was return minus 1.5 times maximum drawdown. The selected candidate was the conservative 15% trend ensemble across all 50 assets. Its later replay returned 2.63% with 0.65% maximum drawdown and 2.50% under higher costs. It had seven 14-day episodes: mean 0.91%, median −0.15%, worst −0.79%, and six of seven reached eight active days. The positive mean includes one +6.96% episode; it is not a guarantee.

A liquidity-filtered 15%/25% or higher-volatility candidate produced larger later returns in diagnostic comparisons, but those configurations were not selected by validation. Keeping them would be selecting on the later period. They remain in `runs/ranking-50-final-study/` for audit.

## What this means

The strategy is more defensible than the LSTM because it trades a slower, interpretable cross-asset signal, controls concentration and costs, and uses a fixed broad universe. The 50-asset expansion does not automatically increase returns: breadth diluted exposure and shortened the common history. The evidence still does not establish a competition-winning edge. The correct next step is a frozen prospective paper period with the exact 50-asset list, current Roostoo quotes, order cadence and reconciliation—not further tuning on this historical sample.

Artifacts:

- Dataset assembly: `scripts/assemble_universe.py`
- 50-asset data: `data/binance-50-1h.csv`
- Selected config: `config/ranking_candidate.json`
- Final run: `runs/diversified-trend-50/run.json`
- Full architecture study: `runs/ranking-50-final-study/study.json`
