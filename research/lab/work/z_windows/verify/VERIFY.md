# z_windows: independent verification

Data: `harness.load('design')` only, rows 744+. Scripts: `v1.py` (standard report, 40-cut look-ahead check), `v2.py` (costs,
fragility, neighbours, fresh windows, placebo), `v3.py` (liquidity, single-coin dependence across the plateau). Raw output:
`step1.json`, `step2.json`, `step3.json`.

Track verdict "no-edge": **confirmed.** Neither candidate is an edge. Candidate 1 is weak, candidate 2 is refuted.

| | candidate 1 (BTC-gated dip-buy) | candidate 2 (n=240, z_in=3.5, no gate) |
|---|---|---|
| Status | **weak** | **refuted** (not better than cash) |
| Reported numbers reproduce | yes, exactly | yes, exactly |
| Look-ahead check (40 cuts) | pass | pass |
| Total / max drawdown | +7.17% / 4.9% | +2.23% / 25.0% |
| 11-day windows mean / median | +0.24% / 0.00% | +0.22% / +0.42% |
| Trades / win rate | 27 / 59% | 125 / 39% |
| Stress total / 11-day mean | +4.75% / +0.15% | -7.09% / -0.16% |
| Thirds, default | +5.3% / -1.1% / +2.9% | +23.2% / +1.6% / -18.3% |
| Thirds, stress | +3.5% / -1.4% / +2.6% | +21.1% / -3.6% / -20.4% |
| Taker fee on every fill | +6.94% | +2.02% |
| Market exits instead of resting sale | +8.36% (stress +6.43%) | +4.16% (stress -5.03%) |
| Best coin | TUT, +$7,419 of +$7,174 net | 1000CHEEMS, +$10,016 of +$2,227 net |
| Without best coin (dropped from universe) | **-0.31%** (stress -1.90%) | -5.88% (stress -13.79%) |
| Without best month | +1.80% (stress -0.02%), month = Jul 2025 | -6.08% (stress -14.02%), month = Jun 2025 |
| Without best trade / best three | +$4,263 / +$134 | -$9,236 / -$20,036 |
| Neighbours (+-25%, one at a time) with same-sign 11-day mean | 17 of 18 (stress 15 of 18) | 8 of 14 positive (stress 1 of 14 positive) |
| Fresh-start 11-day windows (91), mean | +0.30% (stress +0.21%), median 0, 38% positive | -0.01% (stress -0.39%) |
| Trade-return t-statistic | 1.11 (bootstrap P(mean <= 0) = 0.13) | 0.33 |

## Candidate 1

Code: nothing fitted; BTC gate is `ind.ret(C_btc, 24)` at row t, entries are market orders at the next open, stop is 5% under the
signal close, target is a resting sale at the moving mean set one bar after entry. No look-ahead, no bracket abuse, no bug found.
The result does not depend on the maker fee or the limit-fill rule: charging takers on every fill costs 0.2 points, and
replacing the resting sale with a market exit improves it.

What the original report missed:

1. **One coin is the whole profit.** TUT made +$7,419 in 9 trades (Jul-Aug and one in Oct 2025); the net is +$7,174. With TUT
   removed the strategy is -0.31% (stress -1.90%) on 18 trades. The report excluded the six coarse-tick coins so one coin would
   not carry the number, and a different coin carries it anyway. Across the claimed plateau, without TUT: n=48 -2.7%, n=96 -2.4%,
   n=120 +4.5%, n=168 +4.2%, floor 1.5% -2.6%, floor 2% -2.7%, z_in 2.5 -4.2%, BTC lookback 30h +5.7%, 48h +3.4%, 12h -3.8%.
   Mixed signs on 6 to 39 trades.
2. **TUT is the thinnest coin traded.** Half-spread 4.0 bp (panel median 1.2 bp), median hourly volume about $61k. The $25k
   market orders were 7% to 13% of the entry bar's whole volume in 6 of the 9 TUT trades. The harness charges 2 bp of slippage
   (5 bp in stress). On a mock exchange that fills at the quoted price this may not matter; on a real book it would.
3. **Plateau is narrower than stated.** Floor +2% at n=72, z_in=3 with coarse coins out is -0.6% (stress -1.2%), not positive.
   BTC lookback 18h gives +0.5% (stress -1.4%), 12h gives -2.4%. n=54 gives -0.3% (stress -2.3%). z_in=2.25 gives -5.0%.
4. **Sample is tiny.** 27 trades, t = 1.1. Six of them are PAXG (a gold token) for a combined -$1,070.

What holds up:

- **Placebo.** The gate is on 26% of hours. Shifting the same label array by 1,000 bars gives -26.7% (stress -34.0%) on 124
  trades. Over 28 shifts (+-250 to +-3,500 bars): mean total -17.4%, 4 of 28 positive, 2 of 28 at or above the real +7.2%
  (1 of 28 under stress), and 0 of 28 match the real per-trade return (+1.07% against a placebo mean of -0.56%, best +0.80%).
  The gate is doing something a random label of the same frequency does not. Most of what it does is cut the trade count
  (27 trades against about 130 for a placebo and 388 ungated): dips of 3 standard deviations are rare while BTC is rising.
- Positive after stress in two of three sub-periods; the last third's profit does not come from TUT (ZEC, AAVE, WIF).

Decision: weak. Causal and replicated, better than placebo, but it is 27 trades with one thin coin supplying all of the profit
and a zero result once that coin or its best month is removed. Expect about zero, as the original report says.

## Candidate 2

Code is the shared `ZScoreMR` with no filter; nothing to leak. The numbers replicate and confirm the original description:
negative after stress (-7.1%), stress thirds +21% / -4% / -20% (one of three positive), negative without its best coin, its
best month or its best trade, 13 of 14 neighbours negative under stress, fresh-window mean about zero and negative under
stress. z_in 2.6 at the same window is -43%. It is not better than cash and should not be traded or used as a base for a gate
on the strength of this evidence.
