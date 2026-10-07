"""breakout_params candidate 2. Smallest change to the live rule: only the three entry numbers move (+10% in 12h, 120h high); the 6% trailing stop on the hourly close, 4 slots, 12h lockout and market orders stay.
Long only. Nothing is fitted: every feature is a causal rolling statistic of the panel passed to make()."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bo import BO


def make(panel):
    return BO(panel, mw=12, move=.10, hw=120, trail=.06, slots=4, lock=12)
