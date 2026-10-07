# z_risk: independent verification

Design panel only (`harness.load('design')`, 7,519 rows, start=744). Scripts and raw output are in this folder:
`v1.py` (standard report, 40-cut look-ahead check), `v2.py` (costs, taker-only, concentration, neighbours, fresh
windows; results in `verify_results.json`), `v3.py` (event study, residual checks), `v4.py` (strategy-level placebo).

## Verdicts

| candidate | verdict | one line |
|---|---|---|
| candidate_1 (n=168, z<=-2.5) | **refuted as a strategy** (the track's own "no edge" claim is confirmed) | Replicates exactly and is causal, but it is not better than cash: -1.7% at default costs, -13.9% under stress. |
| candidate_2 (n=168, z<=-3.0) | **weak** | Replicates exactly, is causal and does not depend on the fill model, but the whole profit is one month, the stress result does not hold in the neighbours, and the signal picks no better coins than a random swap. |

The track's verdict "no-edge" stands. Candidate 2 is a lead at most, and a weaker one than the report suggests.

## 1. Replication

Both files import and run. Every headline number matches the claim to the last digit.

| | total | max drawdown | 11-day mean / median | thirds | stress total | stress 11-day mean | trades | active days | look-ahead check (40 cuts) |
|---|---|---|---|---|---|---|---|---|---|
| candidate_1 | -1.66% | 26.4% | -0.19% / +0.63% | +8.8% / -13.6% / +4.7% | -13.9% | -0.71% | 436 | 68% | pass |
| candidate_2 | +15.28% | 17.3% | +0.52% / +0.27% | +15.4% / -7.5% / +7.9% | +5.0% | +0.14% | 289 | 51% | pass |

Stress by thirds: candidate_1 +5.6% / -17.9% / -0.6%; candidate_2 +13.3% / -10.3% / +3.2%.

`REPORT.md` is not in the track folder (only `gen_report.py` and the logs), so the report text could not be checked
against the logs; the numbers above were checked against `log_final.txt` and the candidate JSON files.

## 2. Code review (`zr.py`, the paths the candidates use)

- No look-ahead found. The z-score, mean and standard deviation are read at row t; market entries fill at the open of
  t+1; the 20% stop is set from the signal close; the target is the mean at row t, resting during t+1.
- No fill-model abuse. The stop is 20% under a market entry. The target is far from the entry (3 sd). The scale-in
  limit fills on 3% of placements, so it barely matters.
- State (cooldown, scale plan) comes from the book and survives a warm start; the look-ahead check passes.
- `cooldown` is effectively a dead parameter: 0, 9, 15 and 48 hours give the same result within 0.3 points.
- Two realism gaps, neither changes the verdict: (a) the hourly re-pricing of the resting target uses
  `book.set_take`, which the harness does not count as an order, so real order traffic is higher than the reported
  13 to 14 per hour; (b) up to 13 entries are filled at the same open, while the exchange allows one order per minute.

## 3. Costs

| | default | stress | taker-only (no resting orders) | taker-only, stress | maker fee = taker fee | limits must trade 30 bp through |
|---|---|---|---|---|---|---|
| candidate_1 | -1.7% | -13.9% | -4.5% | -13.4% | -2.5% | -5.5% |
| candidate_2 | +15.3% | +5.0% | +13.4% | +6.5% | +14.6% | +11.8% |

Taker-only = market exit after a close above the mean or at the time limit, scale-in by market order after a close at
or below the scale level (look-ahead check passes, 12 cuts). Candidate 2 does not need the maker fee or a generous
limit fill. A stripped version (market in, 48-hour time exit, 20% stop, no target, no scaling) returns +18.7%
(stress +9.9%), so the target and the scaling add nothing.

## 4. Fragility

| | candidate_1 | candidate_2 |
|---|---|---|
| best coin's trades set to zero | -5.3% (TUT) | +12.0% (HBAR) |
| best coin dropped from the universe | -4.6% | +15.7% |
| best three coins dropped | -5.8% (stress -16.9%) | +12.0% (stress +2.7%) |
| six coarse-tick coins dropped | +3.3% (stress -7.6%) | +14.8% (stress +5.7%) |
| best month removed (Feb 2026) | -12.2% (stress -21.9%) | **-0.4% (stress -8.1%)** |
| positive months | 6 of 10 | 6 of 10 |
| run started 4 days later (same rules) | -6.9% | **+9.6%** |
| daily-return t-statistic | 0.07 | 0.69 |
| weekly block bootstrap, share of resamples above zero | 46% | 74% (5th to 95th percentile -21% to +68%) |
| fresh 11-day windows, step 3 days (91 windows): mean / median / win | -0.31% / +0.37% / 56% | +0.34% / +0.14% / 56% |
| same, stress costs: mean | -0.82% | **-0.02%** |
| same, taker-only: mean | -0.41% | +0.29% |

Neighbours, one parameter changed by about 25% (n 126/210, z_in x0.75/x1.25, stop 15%/25%, max_hold 36/60, slots
8/12, cooldown 9/15; 12 per candidate):

- candidate_1: 10 of 12 keep the negative 11-day mean (83%); 11 of 12 negative under stress. The two positive ones are
  z_in=3.125 (which is candidate 2) and max_hold=60 (+0.07%).
- candidate_2: 10 of 12 keep the positive 11-day mean at default costs (83%), but only **4 of 12 under stress (33%)**,
  and two of those four are the dead cooldown parameter. Totals: n=126 +2.7%, n=210 +4.2%, n=240 -1.3%, n=336 +2.4%,
  z_in=2.25 -10.6%, z_in=3.75 +5.7%, max_hold=24 +0.2%, max_hold=36 -3.9%, max_hold=60 +16.1%, slots=4 +2.0%,
  slots=8 +10.6%, stop 15% +3.2%. n=168 is a peak, not a plateau: every other window length is within 4 points of
  zero, and the third sub-period turns negative for n=126, 210 and 240 (-12%, -5%, -12%).

The claimed fresh-window mean (+0.56%, step 4 days) drops to +0.34% at step 3 days.

## 5. Placebo (no regime filter in these candidates; the entry signal was tested the same way)

Same simple exits for every signal (market entry, 48-hour time exit, 20% stop, 10 slots), only the entry changes
(`v4.py`):

| entry signal, z168 <= -3.0 | total | stress |
|---|---|---|
| real signal | +18.7% | +9.9% |
| signal shifted by 250 / 500 / 750 / 1000 / 1500 / 2000 bars | -16.7% / -41.5% / -21.1% / +8.1% / -7.6% / -6.2% | all below the real signal |
| same entry times, but a different coin (index +7 / +13 / +19 / +25 / +31 / +43) | +18.5% / +14.1% / +22.7% / +15.6% / +23.5% / -0.6% | +10.1% / +5.5% / +14.2% / +7.4% / +14.3% / -8.0% |

- The real signal beats all six time-shifted placebos, so the timing carries something on this sample.
- It does not beat buying a different coin at the same moments (placebo mean +15.6%, two of six higher). The coin's
  own z-score adds nothing. Candidate 2 is a "buy the market after a broad sell-off" bet, not coin-level mean reversion.
- Event study, gross 48-hour return after a z168 <= -3.0 event (585 events on 92 days): +108 bp raw, but -17 bp
  relative to the average coin over the same 48 hours (day-clustered t 0.26). By month the raw mean runs from
  -179 bp (Oct 2025) to +576 bp (Feb 2026).
- For z168 <= -2.5 the real signal (-2.6%) is inside the placebo range (6 of 12 placebos do as well or better).

## Corrected reading of the claims

- "candidate_1 is least-bad, not an edge": confirmed. Do not trade it.
- "candidate_2 is a weak lead": confirmed as weak, with these corrections. Without February 2026 it is -0.4% (-8.1%
  under stress). Under stress only 4 of 12 one-step neighbours stay positive. Starting four days later gives +9.6%
  instead of +15.3%. Fresh 11-day windows average zero under stress. It has roughly 92 independent event days, a
  daily t-statistic of 0.69, and it trades on 51% of days (the competition needs 8 of 14). Its return comes from
  when it buys, not from which coin it buys.
- "17 of 20 nearby settings above zero": the probe covered n=168 and n=240 only, and candidate 2 is the top of that
  grid; the next-best setting away from n=168, z=3.0 is +7.6% or lower.
