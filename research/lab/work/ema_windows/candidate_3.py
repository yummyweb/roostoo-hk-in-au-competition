"""ema_windows candidate_3.
LONG only. LEAST-BAD LONG LEG, NOT AN EDGE: EMA 24h / 200h cross-up, 4-ATR(24h) trailing stop, 4 slots.
Design result +66% (stress +13%) is one coin (TUT = 99% of net profit); without its three best coins it loses. Last third -21%.
Filed so the integrator has a long trend leg to gate with allow_long; do not run it ungated.
Everything is computed inside make(panel) from the panel it is given (causal EMAs / ATR from ind.py); nothing is fitted.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # the lab directory
from strategies import EmaCross, Portfolio


def make(panel, allow_long=None, allow_short=None):
    """allow_long / allow_short: optional (T, N) boolean arrays from a regime filter (must themselves be causal)."""
    part = EmaCross(panel, fast=24, slow=200, trend=0, side='long', stop_atr=4., atr_n=24, trail=True, fresh=3, cooldown=6,
                    entry='market', allow_long=allow_long, allow_short=allow_short, tag='ema')
    return Portfolio(panel, [part], slots=4)
