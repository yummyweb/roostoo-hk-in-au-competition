"""breakout_params candidate 3. Lower-variance version of candidate 1: same rule with 6 slots instead of 4.
Long only. Nothing is fitted: every feature is a causal rolling statistic of the panel passed to make()."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bo import BO


def make(panel):
    return BO(panel, mw=12, move=.10, hw=120, atr_k=4, atr_n=24, slots=6, lock=12)
