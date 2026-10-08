# Strategy research, 7 October 2026

This folder holds the study behind the bot's presets (`config/live_candidate.json`, `config/breakout_candidate.json`): the test harness, every
candidate strategy's code, the written reports, and the scripts that reproduce the tables below.

## The question

The team proposed a regime-switching design: a K-Means regime filter (Haryani, Chandra and Tarigan, 2026) choosing
between an EMA-crossover trend rule and a z-score mean-reversion rule, each with its own risk rules, maker (limit)
orders where possible, and shorts when the market is bad. The task was to pick every window and parameter by testing,
and to find the most profitable honest version.

## Method

- **Harness** (`lab/harness.py`): hourly candles, decisions at the close of bar t, execution during bar t+1; long and
  1x short with the exchange's fee rules (taker 0.10%, maker 0.05%, shorts 0.10% each way and market-only closes);
  resting limit orders; intrabar stops with overshoot; per-pair spreads. It was audited three times by independent
  reviewers (about 1,300 tests: accounting against an independent ledger, timing, fill rules, indicators, the regime
  model). Every defect found is fixed and covered by `lab/selftest.py`.
- **Three-way split** of the 50-pair hourly history (2025-05-02 to 2026-10-06): the first 60% is the *design* period,
  where everything was tuned; the next 20% is the *selection* period, used once to choose among frozen candidates;
  the last 20% is the *holdout*, looked at after the choice. A fourth set, 12 majors from 2024-10 to 2025-05, is an
  older out-of-sample check.
- **Look-ahead check** (`harness.causality_check`): every candle after a cut is replaced with an unrelated random path
  and the strategy rebuilt; every earlier order, stop and resting order must be unchanged. All candidates pass.
- **Costs**: default costs as above, and a stress case (maker fills charged as takers, 3x spreads, more slippage).
- **Replication**: each track's recommendation was re-run and attacked by a separate reviewer (parameter neighbours,
  best coin and best month removed, placebo signals). Tracks were told that "no edge" is an acceptable answer.
- About 8,500 strategy variants were run on the design period across 11 tracks.

## Results

Total return over each period (default costs; 4 equal slots unless stated). The market column is the average coin.

| Strategy | Design (282 d, market -45%) | Selection (104 d, -11%) | Holdout (104 d, +60%) | 12 majors 2024-25 (197 d, +49%) |
|---|---:|---:|---:|---:|
| **Breakout: +8% in 12 h at a 120 h high, 4 x ATR trail (`config/breakout_candidate.json`)** | **+173%** | **+26%** | **+102%** | **+72%** |
| Same with a 10% entry (the design-period plateau centre) | +183% | +34% | +84% | +46% |
| Same with a 10% entry and a fixed 6% trail | +78% | +17% | +24% | +31% |
| First breakout settings: +8% in 24 h at a 72 h high, 6% trail | +40% | +21% | -8% | +34% |
| Previous rule behind a BTC > 480 h EMA gate | +107% | +6% | -19% | +34% |
| EMA 48/200 long+short, 6 x ATR trail, 1% risk per trade | +95% | -10% | -1% | -5% |
| EMA 24/200 long only, 4 x ATR trail | +66% | +3% | -3% | -3% |
| EMA 24/200 short only, 6 x ATR trail | +80% | -32% | -43% | -12% |
| Z-score dip-buy, 168 h mean, z <= -3.0, 10 small slots | +15% | -15% | +13% | -12% |
| Z-score dip-buy, 168 h mean, z <= -2.5 | -2% | -21% | +13% | -15% |
| Team design as specified: K-Means regime -> EMA or z-score | +23% | +6% | +3% | not run |
| EMA and z-score side by side, no regime switch | +85% | -22% | +6% | not run |
| Breakout 67% + EMA long/short 67% in separate sleeves | +175% | -5% | +37% | not run |

Under stress costs the tuned breakout rule returned +126%, +15%, +86% and +65% in the four periods.

The tuned breakout rule on fresh-start 11-day windows (a new account every 3 days, as in the competition):

| Period | Mean | Median | Windows above zero | Worst | Windows at +10% or more |
|---|---:|---:|---:|---:|---:|
| Design | +5.3% | +1.6% | 57% | -14% | 33% |
| Selection | +1.8% | -1.6% | 41% | -14% | 19% |
| Holdout | +13.4% | +0.7% | 53% | -23% | 34% |
| 12 majors | +3.2% | 0.0% | 47% | -8% | 16% |

So the typical 11 days is about flat; the average is carried by the one window in three or four that catches a
runner. About five trades out of a few hundred supply the profit in every period.

## What each idea came to

- **Z-score mean reversion**: no edge. On the design period 0 of 675 window settings were positive after stress costs
  and 324 of 326 risk variants lost. The dip-buy earns about nothing before costs and a round trip costs about 28 bp.
  Tight stops made it worse (the freed slot is refilled with the next falling coin); shorting spikes lost more than
  buying dips. The least-bad form lost in three of the four periods.
- **EMA crossover**: the textbook 9/21/55 on hourly candles lost 77-89%. A slow version (1-2 day against 8 day
  average, wide 6 x ATR stop) looked good in design, long+short, and then lost in all three out-of-sample periods.
- **K-Means / HMM regime filter**: the paper's return-and-volatility model gives persistent states but no information
  on whether trend following or mean reversion will pay; it did no better than the same labels shifted in time. A
  version built on trend/chop features blocks 80-90% of both legs' entries, because a crossover happens exactly when
  the trend measure is lowest and a z-score of -3 is itself a strong directional move.
- **Choosing coins by character**: a coin's trending or choppy character does not persist into the next 11 days (rank
  correlation about 0 +/- 0.04); only volatility persists (+0.77).
- **Shorts when the market is bad**: none of nine market-direction signals predicted the market. Short rules made
  money only while prices fell and lost in every rising stretch. A BTC trend gate on breakout entries helped in design
  and hurt in both later periods.
- **Maker-only execution**: not viable. On minute data a limit a few basis points away fills 58% of the time within
  5 minutes and 88% within an hour, and the orders that miss are the winners. Shorts and stops are market orders by
  the exchange's rules. The saving is at most about 0.2% per 11 days.
- **Risk rules**: tight stops (2-3 x ATR, 2-5%) lose in every family; wide trailing stops judged on the hourly close
  work. Holding a losing position and hoping, and hedging with a standing BTC short, both failed out of sample.
- **Breakout**: the only family positive in all four periods. Its parameters sit on a plateau: move 8-12% over
  6-12 h, high window 72-240 h, trail 3-4.5 x ATR(24 h) on the hourly close, 3-6 slots, lockout immaterial.

## The team strategy with hourly exits (8 October)

After this study the team chose to run its own design: a per-coin BULL/BEAR/CHOP label (the paper's K-Means plus HMM
on the 24-hour return and 24-hour volatility) picking between the EMA 48/200 crossover (long in BULL, short in BEAR)
and 168-hour z-score mean reversion (both ways in CHOP), with the risk rules found above. The two regime windows were
chosen on the design period among nine pairs (`lab/work/team_final/REPORT.txt`). `lab/work/live_legs/` runs the
repository's own decision function (`roostoo/legs.py`) in the harness; an independent implementation of the same
specification (`lab/work/team_final/`) gives identical trades.

| Period | Total | Max drawdown | Stress costs | Fresh 11-day mean / median | Days with a trade |
|---|---:|---:|---:|---:|---:|
| Design | +17.7% | 16.6% | +7.0% | +1.2% / +0.9% | 84% |
| Selection | +3.5% | 19.3% | -1.6% | -0.2% / -0.1% | 91% |
| Holdout | -13.5% | 15.7% | -18.2% | -0.2% / -0.7% | 93% |
| 12 majors | -19.2% | 19.7% | -20.8% | -1.3% / -1.3% | 66% |

P&L by leg over the four periods: EMA longs -$4k / +$4k / +$8k / -$11k, EMA shorts +$29k / -$2k / -$18k / +$2k,
mean-reversion longs -$3k / -$1k / +$3k / -$3k, mean-reversion shorts -$4k / -$2k / -$8k / -$7k.
Reproduce with `ROOSTOO_REPO=$PWD .venv-lstm/bin/python research/lab/work/live_legs/periods.py` (run from
`research/lab`). These numbers are for `config/regime_hourly_candidate.json`. The live preset has since gained exits
checked every minute, larger positions, looser entries and a loss brake, and then moved to 15-minute bars with
windows about ten times shorter (root README). None of that was run in this harness, which works on hourly
candles; `scripts/replay_bars.py` replays the runner itself on recorded 5-minute closes instead, and its result
for the live preset is in the root README.

## The breakout rule and why its numbers

| Parameter | Value | Reason | Range that behaves the same |
|---|---|---|---|
| Entry move | +8% over 12 h | Well above a 0.26% round trip and a normal hour's noise; a large move in a short time is what separates runners | 8-12% over 6-12 h |
| Breakout high | close within 0.1% of the 120 h high | Filters bounces inside a falling range | 72-240 h |
| Trailing exit | 4 x ATR(24 h) under the highest price since entry, hourly close, only ratchets up | Scales with each coin's volatility; tight stops lose | 3-4.5 x ATR |
| Slots | 4 equal slots | 2 has 50-70% drawdowns; 8-10 dilutes return faster than risk | 3-6 |
| Lockout after exit | 12 h | No systematic effect | 0-48 h |
| Orders | market | The misses of limit orders are the winners | |

The 8% and 10% entries are indistinguishable on return (each is ahead in two of the four periods). 8% was chosen
because it trades on more days: on the design period 81% of 14-day spans had a trade on at least 8 days, against 69%
for 10%, and the competition requires 8 active days.

## Caveats

- All four periods use the same 50 (or 12) coins and one cost model; the mock exchange fills at the quoted price,
  and a quarter of the account is 10-25% of an hour's volume in the smallest coins.
- The comparison of 8% with 10% was made after the holdout had been seen. Both are inside the design-period plateau.
- The rule is about flat in a typical 11-day window and has lost 14-23% in its worst ones. It is a high-variance,
  positively skewed bet, not a steady earner.

## Reproduce

```sh
.venv-lstm/bin/python research/lab/build_panels.py      # needs data/binance-50-1h.csv and data/universe-1h.csv
cd research/lab
../../.venv-lstm/bin/python selftest.py                 # harness accounting, fills and look-ahead checks
../../.venv-lstm/bin/python exam.py design 744          # every candidate on the design period
../../.venv-lstm/bin/python exam.py select 7519         # selection period
../../.venv-lstm/bin/python exam.py full 10025          # holdout
../../.venv-lstm/bin/python exam.py early12 400         # 12 majors, 2024-25
../../.venv-lstm/bin/python work/exam_move.py           # the 6% / 8% / 10% entry comparison and active-day counts
```

`lab/README.md` documents the harness. `lab/work/<track>/` has each track's candidate code (`candidate_n.py` exposes
`make(panel)`), its report and the reviewer's `verify/` notes. The same rule runs in the repository's own engine with
`scripts/live_windows.py`.
