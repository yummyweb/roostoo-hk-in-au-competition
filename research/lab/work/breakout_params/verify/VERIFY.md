# breakout_params: independent replication and attack

Design panel only (`harness.load('design')`, rows 744 to 7,519). Scripts and raw output are in this folder:
`v1_report.py` / `v1_report.json` (standard report, 40-cut look-ahead check), `v2_fragility.py` / `v2_fragility.json`
(coins, months, neighbours, restart-flat windows, stop timing, slippage, late entry, noise, placebo entries),
`v3_extra.py` / `v3_extra.json` (activity, position size against volume, trade bootstrap). `v2_print.py` prints the tables.

## Verdict

| candidate | status | one-line reason |
|---|---|---|
| candidate_1 (10% in 12h, 120h high, 4-ATR trail, 4 slots) | **survives** | Replicates exactly, causal, 2 of 3 thirds positive under stress, 14 of 14 neighbours agree, beats both placebos, still positive at 75 bp extra slippage. The last third is negative (-9% under stress) and five trades supply all the profit. |
| candidate_2 (same entry, 6% trail, 4 slots) | **weak** | Replicates exactly, causal, all three thirds positive under stress, 12 of 12 neighbours agree. But thin: negative at 50 bp slippage, -5% under stress without its three best coins, +9% under stress if the stop is taken intrabar. |
| candidate_3 (candidate 1 with 6 slots) | **survives** | Same as candidate 1 with a smaller tail: 16 of 16 neighbours agree, stress thirds +42% / +39% / -6%. |

The researcher's overall label ("weak edge") is fair and I would keep it. The claimed numbers are all correct; nothing
needed correcting. What I add is that the evidence is statistically modest (see "How strong") and that candidate 2 is
the thinnest of the three on costs, not the safest.

## 1. Replication

`evalkit.report(make, P, check=True, cuts=40)` on the files as shipped. Every claimed figure matches to the digit.

| | total | max drawdown | 11-day mean / median | thirds | stress total | stress thirds | trades | look-ahead check |
|---|---|---|---|---|---|---|---|---|
| candidate_1 | +183.1% | 32.6% | +5.22% / +0.98% | +83% / +63% / -5% | +141.6% | +73% / +53% / -9% | 234 | pass (40 cuts) |
| candidate_2 | +78.2% | 19.2% | +2.63% / +0.57% | +20% / +38% / +7% | +46.1% | +12% / +28% / +2% | 299 | pass (40 cuts) |
| candidate_3 | +108.3% | 27.2% | +3.48% / +0.44% | +48% / +45% / -3% | +84.3% | +42% / +39% / -6% | 278 | pass (40 cuts) |

No rejected orders; the most orders sent in one hour is 4, 4 and 5. A fill occurs on 65%, 64% and 66% of days.

## 2. Code read (`bo.py`, `candidate_*.py`)

- No look-ahead found. `ind.ret`, `ind.rmax`, `ind.atr` are trailing; `on_bar(t)` reads row `t` only; the trailing
  level uses `Position.hi`, which the harness has updated only through bar `t`. Nothing is fitted. The universe,
  volume and BTC filters in `bo.py` are off in all three candidates.
- No abuse of the fill model. All three use market orders only and judge the stop on the hourly close, so there is no
  limit entry, no bracket, no maker fee and no intrabar stop in play. Every exit is a market sale at the next open
  (`by_reason` is 100% `signal`). **Taker-only execution is therefore the reported number itself.**
- No bugs that change results. The stop level ratchets through `self.lvl` keyed by (pair, entry bar), the lockout is
  set at the decision bar, and a sale and its replacement purchase go out in the same hour with the sale first.
- One thing a reader should know: `self.warm = max(72, mw, hw, atr_n)` is 120 bars, fine for a start at 744.

## 3. Costs

| | default (taker) | stress | +10 bp slip | +20 bp | +30 bp | +50 bp | +75 bp |
|---|---|---|---|---|---|---|---|
| candidate_1 | +183% | +142% | +158% | +130% | +105% | +65% | +24% |
| candidate_2 | +78% | +46% | +58% | +37% | +16% | **-13%** | -40% |
| candidate_3 | +108% | +84% | +94% | +77% | +61% | +34% | +7% |

Slippage columns are default costs with `slip_bps` raised to that value on every fill (default is 2). Candidate 2
breaks even at roughly 40 bp per side; candidates 1 and 3 need more than 75 bp. The last third is negative for
candidates 1 and 3 at every cost level and turns negative for candidate 2 from 30 bp.

Position size is about 1% of the entry hour's dollar volume at the median, and above 10% in 8% of candidate 1's trades
(3 to 4% for the others). Those large-share trades made +$68k of candidate 1's +$184k. The mock exchange fills at the
quote, so this matters only if the fill model is tightened.

## 4. Fragility

| | candidate_1 | candidate_2 | candidate_3 |
|---|---|---|---|
| best coin | TUT (+$58k) | ZEC (+$29k) | TUT (+$32k) |
| total with best coin's trades zeroed | +126% | +50% | +77% |
| total with best coin dropped from the universe (rerun) | +107% | +48% | +77% |
| same, stress costs | +78% | +23% | +57% |
| total with the three best coins dropped (rerun) / stress | +69% / +46% | +11% / **-5%** | +41% / +26% |
| best calendar month | 2025-07 (+58%) | 2025-09 (+30%) | 2025-07 (+38%) |
| total without the best month / stress | +80% / +58% | +37% / +14% | +51% / +36% |
| positive months | 6 of 10 | 5 of 10 | 6 of 10 |
| net P&L without the five best trades / stress | -$18k / -$42k | -$9k / -$30k | +$9k / -$10k |
| median trade return | -1.9% | -1.4% | -2.1% |
| coins with positive P&L | 25 of 44 | 26 of 46 | 26 of 46 |

Neighbours (each numeric parameter moved about 25% either way, one at a time; 14, 12 and 16 runs):

| | 11-day mean keeps its sign, default | same, stress | stress positive in at least 2 of 3 thirds | last third negative under stress | range of stress totals |
|---|---|---|---|---|---|
| candidate_1 | 14 of 14 | 14 of 14 | 14 of 14 | 13 of 14 | +81% to +176% |
| candidate_2 | 12 of 12 | 12 of 12 | 12 of 12 | 6 of 12 | +27% to +92% |
| candidate_3 | 16 of 16 | 16 of 16 | 16 of 16 | 14 of 16 | +59% to +142% |

Restart-flat 11-day windows (`h.fresh_windows(P, make, days=11, step_days=3, start=744)`, 91 windows):

| | mean | median | win | worst | >= +10% | <= -5% | <= -10% | stress mean / median |
|---|---|---|---|---|---|---|---|---|
| candidate_1 | +5.4% | +1.6% | 53% | -15.9% | 33% | 24% | 9% | +4.8% / +0.9% |
| candidate_2 | +2.8% | +0.9% | 59% | -9.4% | 19% | 9% | 0% | +2.0% / +0.4% |
| candidate_3 | +3.8% | +0.5% | 52% | -11.1% | 25% | 16% | 1% | +3.3% / +0.4% |

Other attacks:

| | candidate_1 | candidate_2 | candidate_3 |
|---|---|---|---|
| stop taken intrabar instead of on the hourly close, default / stress | +179% / +125% | +43% / **+9%** | +100% / +70% |
| every entry sent one hour late, default / stress | +217% / +171% | +101% / +67% | +112% / +88% |
| 20% of entry chances vetoed at random, stress, 10 seeds (min / median / max) | +105% / +142% / +197% | +21% / +52% / +82% | +57% / +90% / +134% |
| same, last third (min / max) | -21% / +5% | -3% / +16% | -10% / +3% |
| activity: 14-day spans with a fill on 8 or more days (worst span) | 69% (2 days) | 69% (2 days) | 71% (2 days) |

Late entry does not hurt, so the result does not rest on the exact fill at the first open after the signal.

## 5. Placebo

There is no regime filter, so I applied the same idea to the entry signal, keeping exits, slots and costs unchanged:

| entries taken from | candidate_1 | candidate_2 | candidate_3 |
|---|---|---|---|
| the real signal | +183% | +78% | +108% |
| another coin's signal at the same hour (8 random pairings) | -26% to +32%, mean +7% | -36% to +16%, mean -4% | -20% to +18%, mean -1% |
| the coin's own signal 1,000 to 2,500 bars late (4 shifts) | +28%, -34%, -25%, -31% | -16%, -61%, -43%, -41% | +11%, -35%, -20%, -20% |

Both placebos sit near or below zero with the same number of trades, so the profit comes from which coin is bought and
when, not from market-wide timing or from the exit rule alone.

## How strong

- Mean return per trade is +2.2% (candidate 1), +0.9% (candidate 2), +1.8% (candidate 3) with t-statistics of 2.1,
  1.7 and 2.1. Resampling the trades with replacement, the summed P&L is positive in 91%, 90% and 94% of resamples at
  default costs and 87%, 81% and 90% under stress. With 693 settings examined on the same data, that is suggestive,
  not significant.
- 9 trades returned 40% or more in candidates 1 and 3 (3 in candidate 2). The rule is a wait for one of those.
- The most recent third (December to March) is flat to negative in nearly every neighbour of candidates 1 and 3.
- Nothing here has seen the held-back data; I did not load it.

## Corrected numbers

None. Every figure in the track's recommendation reproduced. Additions to carry forward: best-coin and best-month
removals, the slippage break-even (about 40 bp for candidate 2, above 75 bp for candidates 1 and 3), the placebo
results and the bootstrap odds above.
