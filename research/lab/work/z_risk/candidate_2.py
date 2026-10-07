"""z_risk candidate 2 - EXPLORATORY LEAD, NOT VALIDATED (design: about +13%, stress about +4%, one third negative).

Same rule set as candidate 1 with a deeper entry (168-hour z-score, z <= -3.0). The threshold is outside the three
reference entries of this track and was found in a small neighbour probe, it trades on about half of the days only,
and its result is within noise of zero under stress costs. Use it only as the mean-reversion leg to be re-tested.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(os.path.dirname(HERE))
for p in (LAB, HERE):
    if p not in sys.path: sys.path.insert(0, p)
from zr import ZR

PARAMS = dict(n=168, z_in=3.0, side='long', stop_pct=.20, max_hold=48, scale=True, slots=10, entry='market', exit='take', cooldown=12)


def make(panel):
    return ZR(panel, **PARAMS)
