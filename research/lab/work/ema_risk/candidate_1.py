"""Candidate 1 (best for the three ratios). EMA 48/200 crossover, long and short, no trend filter. Exit: 6 x ATR(24) trailing stop or the opposite cross. 4 slots, each position sized so that hitting its initial stop loses 1% of equity (capped at the slot). Market entries. Verdict of the track: weak edge, carried by the short side in a falling market.

Frozen. Everything is built from the panel passed to make(); nothing is fitted.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parents[1])):
    if _p not in sys.path: sys.path.insert(0, _p)
from lib import EmaX, PortX   # noqa: E402  (subclasses of strategies.EmaCross / strategies.Portfolio)


def make(panel):
    part = EmaX(panel, fast=48, slow=200, trend=0, side='both', stop_atr=6., atr_n=24, trail=True, fresh=3, cooldown=6,
                entry='market', exit='cross')
    return PortX(panel, [part], slots=4, risk=.01)
