"""Candidate 3 (the short leg of candidate 1 on its own, for use when a regime filter says the market is bad). Bear-market dependent: the design period fell 45% on average, so this is flattered. Not for use without a market filter.

Frozen. Everything is built from the panel passed to make(); nothing is fitted.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parents[1])):
    if _p not in sys.path: sys.path.insert(0, _p)
from lib import EmaX, PortX   # noqa: E402  (subclasses of strategies.EmaCross / strategies.Portfolio)


def make(panel):
    part = EmaX(panel, fast=48, slow=200, trend=0, side='short', stop_atr=6., atr_n=24, trail=True, fresh=3, cooldown=6,
                entry='market', exit='cross')
    return PortX(panel, [part], slots=4, risk=.01)
