
Reading: at the centre a limit 2 to 10 bp under the close fills about 95% of the time in the next hour, but the 4 to 5% it misses are the
coins that never looked back: every one of the 8 to 12 missed trades was a winner in five of the six settings, averaging about +9% against +1.9% for the trades that fill, and
they carry about a fifth of the whole profit. Falling back to a market order after the limit expires buys those coins about 4% higher.
For the current rule the 10 bp / 1 bar limit would have missed 33 trades worth +$58k while the 416 it filled lost $18k between them.
In the full reruns the limit variants still come out ahead of market orders at the centre (default +239% to +266% against +183%; stress +155% to +198% against +142%)
because the fee and spread saved on the other 95% is larger, and because a cancelled order is simply re-sent the next hour while the signal
holds. Around the current rule the same change is a wash under stress (-8% to +22% against +4%). How the real exchange fills resting orders has not been measured,
so the candidates use market orders; a limit a few bp under the close for one hour with a market fallback is an optional extra, never a limit that gives up.

## What failed or did not matter

- **Fixed-percentage trail around the current entry rule**: no stable optimum. 6% and 8% are positive, 10% and 15% are negative, 4% is negative under stress; the axis is jagged even after averaging. The 6% value is not wrong, it is just not distinguishable from 8%.
- **Intrabar stop** (sell on the one-minute poll as soon as the trail is touched): clearly worse for tight trails. Current rule +40% becomes -7% (stress -39%); almost the whole intrabar table is negative under stress for trails up to 8% and for 2 to 3 ATR (three cells sit between +2% and +6%). Only a wide stop (4 ATR and up) is indifferent to it (centre: +179% intrabar against +183% on the close). Keep judging the stop on the hourly close.
- **Longer momentum windows**: 48h is no better than 24h (stress -17% to +11% on the perturbed averages); 72h is negative under stress in every column with the first third at -30% to -10%.
- **Scaling the move with the window** (4% in 6h, 5.7% in 12h): mostly negative under stress (6h: -78% to +2%; 12h: -47% to +18%). What helps is a large move in a short time, not a short window as such.
- **No high condition** (hw=0): works at 6h and 24h, fails at 12h and 72h for the current rule; not a plateau. A long high window (72h to 240h) is safer.
- **Top-N by dollar volume**: removes the edge (top 20: -9% for the current rule, +5% at the centre; top 40: -15% and +40%). The profit is made in the smaller half of the list.
- **Dropping the six coarse-tick coins**: costs a little (current +35% against +40%; centre +156% against +183%, last third -15% against -5%) but nothing depends on them.
- **Volume surge**: helps the current rule (stress +1% to +43% against +4%, last third -20% to +16% against -23%) but adds nothing once the entry is sharper (centre +159% to +196% against +183%). Redundant with the sharper move; not used.
- **BTC above its EMA**: for the current rule 100h gives 0%, 200h +53%, 400h +110% (not monotone, so not trusted); at the centre it lowers the return (+75% to +148% against +183%), lowers the drawdown a little (27 to 29% against 33%) and cuts the share of days with a fill to 35 to 52%, which breaks the 8-of-14-days requirement. Not used.
- **Lockout**: 0 to 48 hours makes no systematic difference (centre +183% to +244%, current +25% to +86% at 6% trail). Keep 12.
- **2 slots**: highest variance and the worst drawdowns (47 to 68%), more than 20% of 11-day windows below -10%. **8 to 10 slots**: dilutes the return faster than the risk (Sharpe 1.5 to 1.7 against 1.9 at 4 slots).

## The plateau and its centre

| parameter | good region (neighbours agree, stress positive) | centre | current | current inside? |
|---|---|---|---|---|
| move and momentum window | 8 to 12% measured over 6 to 12 hours (equivalently 12 to 15% over 24 hours) | 10% over 12h | 8% over 24h | on the edge: positive in total, last third -23% |
| breakout-high window | 72h to 240h, better from 96h up | 120h | 72h | inside, low side |
| trailing stop | 3 to 4.5 x ATR(12 to 24h) on the hourly close, or 4 to 8% fixed on the sharper entry | 4 x ATR(24h) | 6% fixed | 6% is fine on the sharper entry, weak on the current one |
| stop judged on | hourly close | hourly close | hourly close | inside |
| slots | 3 to 6 | 4 (6 for lower variance) | 4 | inside |
| lockout | 0 to 48h, immaterial | 12h | 12h | inside |
| entry order | market; limit optional | market | market | inside |
| universe | all 50 pairs | all | all | inside |

Evidence for the entry change (the part that matters most): with the 6% trail kept, 11 of the 12 cells in momentum window {6, 12}h x move {8, 10, 12}% x high window {72, 120}h
have all three thirds at or above zero and all 12 are positive under stress in 4 of 4 perturbed runs; the current cell (24h, 8%, 72h) has thirds +12% / +61% / -22% and is positive under stress in 4 of 6 runs.
With a 3 or 4 ATR trail the same block returns +14% to +186% (stress +2% to +146%; with the 120h high +46% to +186% and stress +32% to +146%), every cell positive under stress in 4 of 4 runs and every third at or above -5%.
Evidence for the ATR trail: on the current entry rule the 4 ATR column is positive at every move from 3% to 20% (default +66% to +141%, stress +21% to +87%) where the percentage columns change sign;
ATR 2.5 to 4.5 with a 12h or 24h ATR window are all positive under stress in 4 of 4 runs on both entry rules tested.

How strong is it? Moderate, not strong.

1. It is one 10-month bear-market sample and the settings were chosen on it (693 settings looked at). Expect the held-back data to give a good deal less than the design numbers.
2. In the current rule and in all three candidates the five best trades are about 90% to 270% of the net profit and the median trade loses about 2%. About five events decide the result, so the data cannot really tell two good settings apart; it can only tell the good region from the bad one.
3. The last third is flat to slightly negative even at the centre (-5%, -9% under stress). The change removes most of the damage of the hard period; it does not make money in it.
4. The typical 11 days is small: median continuous 11-day window +1.0% (candidate 1), +0.6% (candidate 2); restart-flat median +1.6% and +0.7%. The mean (+5.2%, +2.6%) comes from the one window in three that catches a runner.
5. Activity: the sharper entry trades on fewer days. The current rule has a fill on 8 or more days in 95% of 14-day spans; the candidates in about 70% (worst span: 2 days). If the 8-of-14 rule must be met by this rule alone, use move 8% at the centre (81%, total +173%, stress +126%) or 6% (87%, +150%, stress +101%); both are inside the plateau.
6. Size: a quarter of the account is about $25,000 per position, which is 10 to 25% of an average hour's Binance volume in the smallest coins (TUT, STO, LISTA, 1000CHEEMS). The mock exchange fills at the quoted price, a real one would not.

## Recommendation

1. **candidate_1.py** (plateau centre): buy a coin that is up at least 10% in 12 hours and closing within 0.1% of its 120-hour high; trail a stop 4 x ATR(24h) under the highest high since entry, judged on the hourly close; 4 equal slots; 12h lockout after an exit; market orders. Design +183%, max drawdown 33%, thirds +83% / +63% / -5%, stress +142%.
2. **candidate_2.py** (most even, smallest code change: three numbers): same entry, keep the 6% trail. Design +78%, max drawdown 19%, thirds +20% / +38% / +7%, stress +46% (stress thirds +12% / +28% / +2%), no continuous 11-day window below -11%. This is the one that best fits "even across thirds and survives stress".
3. **candidate_3.py** (lower variance): candidate 1 with 6 slots. Design +108%, max drawdown 27%, thirds +48% / +45% / -3%, stress +84%, 2% of 11-day windows below -10% against 10%.

All three pass `h.causality_check`. Nothing is fitted; every input is a causal rolling statistic.

What would have to be true for this to work in the next 11 days: at least one or two coins must run 40% or more after a 10% surge to a five-day high. In the design data that happened in roughly one 11-day window in three
(35% of windows at or above +10% for candidate 1, 18% for candidate 2); in the other two the rule finishes within a few percent of zero, and in about one in ten (candidate 1) it loses more than 10%.

## Files

- `bo.py` parameterised rule; `sweep.py`, `stage2.py`, `stage3.py`, `stage4.py`, `final.py` the runs; `tables.py`, `build_report.py` the tables.
- `results.jsonl` every evaluation; `diag.json` concentration, limit misses, restart-flat windows; `report_*.json` the standard `evalkit.report` output for the current rule and the three candidates.
