"""Candidate 1 (track regime_trendchop) - the team's architecture, honest version.

K-Means (K=2, walk-forward, refit every 2 weeks on an expanding window) labels each coin-hour "trending" or "chopping"
from four trend-vs-chop features: Kaufman efficiency ratio over 72h and 168h, the number of EMA24/EMA100 crosses in the
last 168h, and |EMA24-EMA100|/ATR24. In the "trending" state it trades the EMA 24/100 cross LONG only, and only while the
cross is at most 15 hours old (resting limit entry 5 bp inside the close, market fallback, 3-ATR trailing stop, exit on
the cross back). In the "chopping" state it holds cash: z-score mean reversion lost in every state we tested.
No shorts: the short side showed no information from the label (a shifted placebo label did as well).
Everything is fitted inside make() on past data only.  Check with h.causality_check(make, panel, cuts=8) (slow fit).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.abspath(os.path.join(HERE, '..', '..'))
for _p in (LAB, HERE):
    if _p not in sys.path: sys.path.insert(0, _p)
import tc
from strategies import EmaCross, Portfolio

FRESH = 15


def make(panel):
    lab = tc.kmeans_labels(panel, 'core4', K=2, use_hmm=False, first_train=1000, step=336)   # 1 = higher efficiency ratio = trending
    trend = lab == 1
    return Portfolio(panel, [EmaCross(panel, 24, 100, side='long', entry='limit', fresh=FRESH, allow_long=trend)], slots=4)
