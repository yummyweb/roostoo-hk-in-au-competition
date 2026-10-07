"""ema_windows candidate_2.
SHORT only (the 'shorts when the market is bad' leg). EMA 24h / 200h cross-down, 6-ATR(24h) trailing stop, 4 slots.
Verdict on design data: positive in all thirds after stress costs, but 94% of coins fell in this period (passive equal-weight short: +49%).
Use only behind a market-regime gate (allow_short); expect it to lose in a rising market.
Everything is computed inside make(panel) from the panel it is given (causal EMAs / ATR from ind.py); nothing is fitted.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # the lab directory
from strategies import EmaCross, Portfolio


def make(panel, allow_long=None, allow_short=None):
    """allow_long / allow_short: optional (T, N) boolean arrays from a regime filter (must themselves be causal)."""
    part = EmaCross(panel, fast=24, slow=200, trend=0, side='short', stop_atr=6., atr_n=24, trail=True, fresh=3, cooldown=6,
                    entry='market', allow_long=allow_long, allow_short=allow_short, tag='ema')
    return Portfolio(panel, [part], slots=4)
