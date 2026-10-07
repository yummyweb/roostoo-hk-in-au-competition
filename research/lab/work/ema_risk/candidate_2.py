"""Candidate 2 (best for the 11-day-window mean). Same rule as candidate 1 with full-size slots (24.75% of equity each, no risk cap). Higher mean, about twice the drawdown.

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
    return PortX(panel, [part], slots=4)
