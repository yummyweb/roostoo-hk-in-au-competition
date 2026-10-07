# Verification of track `regime_paper` - candidate_1

Independent replication on `design` only. Scripts and logs are in this folder (`v1.py` replicate, `v2.py` look-ahead,
`v3.py` costs / concentration / placebo, `v4.py` neighbours and fresh windows; `*.log`, `*.json`).

**Decision: refuted as an edge.** The reported numbers replicate to the last digit and the code is causal, so the
researcher's own verdict ("no-edge", filed for completeness) is confirmed. The candidate is not better than a placebo
gate of the same frequency and persistence, is about equal to cash after stress costs, and its whole profit is one
month and two coins.

## 1. Replication

`evalkit.report(candidate_1.make, P)`:

| metric | claimed | reproduced |
|---|---|---|
| total return | +27.67% | +27.67% |
| max drawdown | 21.93% | 21.93% |
| 11-day windows mean / median | +1.143% / 0 | +1.143% / 0 |
| windows >= +10% / <= -10% | 10.7% / 0% | 10.7% / 0% |
| thirds | +10.2% / -6.6% / +24.0% | +10.2% / -6.6% / +24.0% |
| stress total / 11-day mean | +1.6% / +0.21% | +1.6% / +0.21% |
| trades, active days | 217, 35% | 217, 35% |
| long P&L | +27,669 | +27,669 |

Exit split: 182 stop exits +42,223, 35 signal exits -14,555. Limit fill rate 87% (66% under stress). 0 rejects, at most 4 orders per hour.

Look-ahead: `make` takes 6.6 s on the real panel but 13-20 s on each altered panel (EM runs longer on the random
path), and a 40-cut run was stopped unfinished after 15 minutes on a loaded machine, so the test was run with
**8 cuts**, as the task allows: `h.causality_check` returned `(True, None)`. I added a stricter comparison: on each of
the 9 altered panels the full label array and the full allow array before the cut were compared with the originals
row by row. Zero mismatches at all cuts (2255, 3007, 3758, 4510, 5262, 6013, 6765, 7517).

## 2. Code reading

No look-ahead and no bug found.

- Features (`rp.features`): `ind.logret(C, 6)` and `ind.realized_vol(C, 24)` of BTC, both trailing.
- `regime.walk_forward`: scaler mean/std and the fit use rows `[first, end)` only; rows `[end, end+720)` are labelled
  with the forward filter (filtered probabilities, no smoothing). Refits warm-start from the previous model.
- `rp.canonical`: matches states across refits from fitted model means only.
- `gates.vol_state`: at refit `e` uses labels and realised volatility on rows `[744, e)`, applies to `[e, e+720)`.
  Nothing is allowed before bar 1464. The "lowest-volatility state" is canonical state 0 at all nine refits, so this
  map is a constant in practice; `min_n` and the volatility window used for the map have no effect.
- Fill model: buy limit 5 bp inside the close, 2-bar life, then market; stop at close - 3 x ATR(24), always well below the
  limit; no take-profit. No zero-distance bracket, no same-bar stop/limit abuse.
- Detail in the write-up, not a defect: the state volatility that picks the allowed state is averaged over all 50 coins
  under the BTC label, not BTC's own volatility.
- The label is on for 25% of bars from bar 1464, in 51 separate episodes, and only 4% and 6% of bars in the last two
  refit blocks. That is few independent episodes and near-idle at the end of the sample.

## 3. Costs

| variant | total | 11-day mean | thirds |
|---|---|---|---|
| as filed, default costs | +27.7% | +1.14% | +10% / -7% / +24% |
| as filed, `evalkit.STRESS` | +1.6% | +0.21% | +1.0% / -13.8% / +16.7% |
| taker-only (market entries), default | +41.9% | +1.62% | +17% / -4% / +27% |
| taker-only, STRESS | +18.7% | +0.88% | +10% / -11% / +21% |
| limit, cancel if unfilled | +28.5% | +1.18% | +9% / -6% / +25% |
| only maker fee = taker fee | +24.7% | +1.05% | |
| only limits must trade 30 bp through | +18.8% | +0.85% | |
| only 3x spread | +19.3% | +0.86% | |
| only stop overshoot 15 bp + slip 5 bp | +21.5% | +0.94% | |
| without the 6 coarse-tick pairs, default | **-3.3%** | -0.08% | +9% / -3% / -9% |
| without the 6 coarse-tick pairs, STRESS | **-20.2%** | -0.85% | +2% / -8% / -15% |

The result does not depend on the maker fee or on a generous limit fill: market entries are better than the limit
entries (the limit is filled on dips and misses the strongest starts). It does depend on two of the six coins whose
limit prices cannot be placed finely (PEPE, STO).

## 4. Fragility

- Sub-periods: default +10.2% / -6.6% / +24.0%; stress +1.0% / -13.8% / +16.7%. Two of three are positive under stress,
  the first by one percent.
- Coins: 49 traded, 22 profitable. STO/USD +15,374 (11 trades) and PEPE/USD +13,761 (2 trades) are together larger
  than the whole profit (+27,669). Without the best coin (STO dropped from the universe): **+9.9%** default,
  **-10.7%** stress (zeroing its trades: +12.3%). Without the top three coins: -6.7%.
- Trades: the best 5 of 217 trades made +49,601; the other 212 lost 21,932.
- Months: positive in 4 of 10. January 2026 was +35.7%; without it **-5.9%** default, **-23.4%** stress.
- Neighbours, each numeric parameter +-25% one at a time, 36 variants (EMA fast/slow, stop multiple, ATR length, limit
  offset, order life, signal freshness, cooldown, slots, return window 4/5/7/8, volatility window, K 2/4, EM iterations,
  refit step, first-fit bar, map volatility window, map minimum count):
  11-day mean keeps its sign in **35 of 36 (97%)** at default costs (only K=2 flips: -9.9%); under stress the 11-day
  mean is positive in 26 of 36 (72%) and the total is positive in 20 of 36, mean stress total +0.6%.
  Six of the 36 are inert (identical trades), so 29 of 30 and 20 of 30 among those that change anything.
  All neighbours share the same episodes and the same January, so this agreement is not independent evidence.
  K-Means seed 1 gives the identical label.
- Fresh-start 11-day windows (`h.fresh_windows`, step 3 days, start 744, 91 windows): mean **+1.17%**, median 0.0%,
  38% positive, 11% at or above +10%, none at or below -10%, worst -6.4%. Under stress: mean +0.22%, median 0.0%,
  29% positive. From bar 1464 (81 windows): mean +1.22%, median 0.0%. The median window makes nothing.

## 5. Placebo

Same allow array rolled in time inside the tradeable span (bars 1464 on), so frequency and persistence are identical:

| roll (bars) | default total | stress total |
|---|---|---|
| 500 | -13.0% | -30.7% |
| **1000** | **-13.1%** | **-29.9%** |
| 1500 | -22.2% | -38.9% |
| 2000 | +43.8% | +17.6% |
| 2500 | +1.0% | -18.9% |
| 3000 | +21.0% | +0.7% |
| 3500 | +22.5% | -1.5% |
| 4000 | +51.6% | +15.8% |
| 4500 | +62.2% | +29.4% |
| 5000 | +12.7% | -5.3% |
| 5500 | -10.5% | -29.4% |
| real label | +27.7% | +1.6% |

The real label beats the 1,000-bar placebo, but 3 of 11 placebos beat it under both cost sets (rank 4 of 12).
Placebo mean +14.2% default / -8.3% stress, 7 of 11 positive at default costs. The researcher's own construction
(labels shifted, low-vol state re-identified) reproduces: shift 1000 -22.8%, shift 2000 +33.2%, shift 3000 -37.5%.
For scale: the ungated rule from bar 1464 returns -46.3% (-74.6% stress) and the complement gate -59.9%. Most of the
gap between gated and ungated comes from being in the market a quarter of the time during a bear market, which any
gate of this frequency delivers; the label's own contribution is not separable from chance in this sample.

## Corrected numbers

| | value |
|---|---|
| design total / max drawdown | +27.7% / 21.9% (confirmed) |
| 11-day window mean, continuous / fresh-start | +1.14% / +1.17% (median 0 in both) |
| stress total | +1.6% (confirmed) |
| taker-only total, default / stress | +41.9% / +18.7% |
| without best coin (STO) | +9.9% default, -10.7% stress |
| without best month (2026-01) | -5.9% default, -23.4% stress |
| without the 6 coarse-tick pairs | -3.3% default, -20.2% stress |
| neighbours with same sign of 11-day mean | 97% default, 72% stress |
| placebos at least as good | 3 of 11 |
| active days | 35% (needs 8 of 14) |

## Not done

- The look-ahead test used 8 cuts, not 40.
- Placebo, concentration and neighbour tests were not repeated for the taker-only variant, which is the stronger
  form of the same rule (+18.7% under stress); it shares the same trades in January, STO and PEPE.
