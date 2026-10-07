"""z_windows candidate 2 -- LEAST-BAD UNGATED z-score setting, NOT AN EDGE (it is roughly flat because it rarely trades).

Plain long-only z-score mean reversion with no filter: z = (close - SMA_240) / std_240, enter at z <= -3.5 (market),
exit at the 240h mean (resting maker sale / market on an hourly close above it), stop 5%, time limit 48h, 4 slots.
Design (rows 744+): about +2% total, -7% under stress costs, thirds +23% / +2% / -18%, 125 trades, and its best coin
(1000CHEEMS) earned more than the whole net profit. Filed only as the reference "best plain window" for a regime
filter to gate through allow_long; do not run it on its own.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from strategies import ZScoreMR, Portfolio

N, Z_IN, Z_OUT, STOP, MAX_HOLD, SLOTS = 240, 3.5, 0.0, .05, 48, 4


def make(panel):
    part = ZScoreMR(panel, n=N, z_in=Z_IN, z_out=Z_OUT, stop_pct=STOP, max_hold=MAX_HOLD, side='long', entry='market')
    return Portfolio(panel, [part], slots=SLOTS)
