"""team_final candidate 1 - the team's strategy, frozen.

Regime per coin and hour: 24 h log return and 24 h rolling std of 1 h log returns, standardised on the training data,
    K-Means (K=3) -> 3-state Gaussian HMM, one model for all coins, first fit on 1,500 bars, refit every 336 bars on
    everything seen so far, labels from the forward filter. Highest mean return = BULL, lowest = BEAR, middle = CHOP.
BULL : EMA 48/200 long,  entry while the up state is at most 12 bars old.   } at most 4, ranked by |EMA48-EMA200|/ATR24,
BEAR : EMA 48/200 short, entry while the down state is at most 12 bars old. } size min(24.75% of equity, 1% of equity / d),
       d = 6 x ATR24 / close; exit on the cross back (then 6 bars blocked) or an hourly close through the 6 x ATR24 trail.
CHOP : 168 h z-score: buy at z <= -3, short at z >= +3, 5% of equity each, at most 10; exit at the first hourly close
       back across z = 0, after 48 bars, or 20% against the entry; 12-bar cooldown.
Market orders only; every exit is judged on the hourly close. The only chosen values are R and V (design period, 9 pairs).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tf

R, V = 24, 24


def make(panel):
    return tf.TeamFinal(panel, R, V)
