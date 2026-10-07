"""z_risk candidate 1 - LEAST-BAD, NOT AN EDGE (design: about -2%, stress about -14%).

Mean reversion on the team's slow reference entry (168-hour z-score, z <= -2.5), long only, with the rule set that
lost least in the risk/execution sweep: market entry at the open after the signal bar, 2/3 of a slot first and 1/3
more one standard deviation lower, maker sale resting at the moving mean, 48-hour time limit, 12-hour cooldown,
ten small slots, and only a wide 20% disaster stop (tight stops cost money in every reference entry).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(os.path.dirname(HERE))
for p in (LAB, HERE):
    if p not in sys.path: sys.path.insert(0, p)
from zr import ZR

PARAMS = dict(n=168, z_in=2.5, side='long', stop_pct=.20, max_hold=48, scale=True, slots=10, entry='market', exit='take', cooldown=12)


def make(panel):
    return ZR(panel, **PARAMS)
