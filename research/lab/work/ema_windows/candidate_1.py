"""ema_windows candidate_1.
BOTH sides. EMA 24h / 200h cross, no trend line, 6-ATR(24h) trailing stop, entry within 3 bars of the cross, 4 slots, market entries.
Verdict on design data: weak edge. +59% (stress +17%), but one month and three coins carry it and the short leg earns 3/4 of the profit in a bear market.
Everything is computed inside make(panel) from the panel it is given (causal EMAs / ATR from ind.py); nothing is fitted.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # the lab directory
from strategies import EmaCross, Portfolio


def make(panel, allow_long=None, allow_short=None):
    """allow_long / allow_short: optional (T, N) boolean arrays from a regime filter (must themselves be causal)."""
    part = EmaCross(panel, fast=24, slow=200, trend=0, side='both', stop_atr=6., atr_n=24, trail=True, fresh=3, cooldown=6,
                    entry='market', allow_long=allow_long, allow_short=allow_short, tag='ema')
    return Portfolio(panel, [part], slots=4)
