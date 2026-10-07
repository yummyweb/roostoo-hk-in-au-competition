"""integrate_team_spec candidate 2 (B) - the team's two legs side by side, WITHOUT the regime switch.

The single change from candidate 1: the K-Means label no longer decides which leg may trade a coin. Both legs may open in
any coin at any time (one position per coin; the EMA leg has priority on the rare hour both signal), each with its own
budget and risk rules, and the EMA leg goes back to its own 3-bar entry limit.
EMA leg : EMA 48/200 crossover on hourly closes. Up-cross = buy, down-cross = short, entry only within 3 bars of the
          cross; initial and trailing stop 6 x ATR(24) from the best price since entry (about 8%); exit on the opposite
          cross (then 6 bars before the coin can be re-entered); at most 4 positions; size = min(24.75% of equity,
          1% of equity / stop distance); candidates ranked by |EMA48-EMA200|/ATR24.
MR leg  : buy when close is <= 3.0 standard deviations below its 168 h mean; 5% of equity each, at most 10 positions;
          sell at the first hourly close at or above the mean, or after 48 h; 20% disaster stop; 12 h cooldown per coin.
'Long when good, short when bad' is done per coin by the direction of the cross; the BTC 480 h EMA gate is NOT used
(it cut the result from +95% to +37% on design). Market orders only. Nothing is fitted.
STOP_MODE 'close' (frozen choice) = every stop is judged on the completed hourly candle and left with a market order at
the next open, so the bot needs no intrabar logic. 'intrabar' = stops fire inside the hour from the one-minute poll
(design +110% instead of +85% in one continuous run, but no better over fresh 11-day windows; see REPORT.txt).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ts

STOP_MODE = 'close'
PARAMS = dict(label='none', direction='none', fresh=3, stop_mode=STOP_MODE)


def make(panel):
    return ts.build(panel, **PARAMS)
