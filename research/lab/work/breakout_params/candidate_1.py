"""breakout_params candidate 1. Plateau centre: +10% in 12h, close at a 120h high, 4-ATR(24h) trailing stop judged on the hourly close, 4 slots, 12h lockout, market orders.
Long only. Nothing is fitted: every feature is a causal rolling statistic of the panel passed to make()."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bo import BO


def make(panel):
    return BO(panel, mw=12, move=.10, hw=120, atr_k=4, atr_n=24, slots=4, lock=12)
