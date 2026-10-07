"""integrate_team_spec candidate 1 (A) - the team's architecture, faithful version. NOT RECOMMENDED: see REPORT.txt.

Regime filter : per coin and hour, walk-forward K-Means (K=2, one model for all coins, refit every 336 h on all past data)
                on four trend-vs-chop features (efficiency ratio 72 h and 168 h, EMA24/EMA100 crosses in the last 168 h,
                |EMA24-EMA100|/ATR24). Cluster with the higher efficiency ratio = 'trend', the other = 'chop'.
'trend' coin  : EMA 48/200 crossover, long on an up-cross and short on a down-cross, entry allowed up to 12 hourly bars
                after the cross (the label needs the gap to open, so the leg's own 3-bar limit leaves almost no trades),
                6 x ATR(24) trailing stop, exit on the opposite cross, at most 4 positions, each sized so its initial
                stop loses 1% of equity (capped at 24.75% of equity).
'chop' coin   : z-score mean reversion, long only: buy when the 168 h z-score <= -3.0, 5% of equity each, at most 10,
                sell at the first hourly close with z >= 0 or after 48 h, 20% disaster stop, 12 h cooldown.
Market orders only. Long and short in every market (no BTC direction rule). Everything is built inside make(panel).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ts

PARAMS = dict(label='km', direction='none', fresh=12, stop_mode='intrabar')


def make(panel):
    return ts.build(panel, **PARAMS)
