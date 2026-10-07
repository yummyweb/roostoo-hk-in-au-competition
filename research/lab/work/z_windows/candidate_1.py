"""z_windows candidate 1 -- LEAST-BAD, NOT A PROVEN EDGE (track verdict: no-edge for plain z-score mean reversion).

Long-only z-score dip-buy, gated by a condition that needs no regime model: only enter while BTC's own 24h return
is >= +1%. z = (close - SMA_72) / std_72, enter at z <= -3.0 (market), exit at the 72h mean (resting maker sale at the
moving mean, or market when the hourly close is back above it), hard stop 5%, time limit 48h, 4 equal slots.
The six coins with a price tick above 10 bp are excluded: with them the design result is carried by ONE trade
(1000CHEEMS flash-crash bar of 2025-10-27, +39% in one hour) that a live bot is unlikely to have filled.
Design (rows 744+): about +7% total, +5% under stress costs, only 27 trades in 282 days (fills on ~12% of days).
Everything is computed inside make() from the panel it is given; nothing is fitted.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import ind
from strategies import ZScoreMR, Portfolio

N, Z_IN, Z_OUT, STOP, MAX_HOLD, SLOTS, BTC_FLOOR = 72, 3.0, 0.0, .05, 48, 4, .01
COARSE = ('PEPE/USD', '1000CHEEMS/USD', 'SHIB/USD', 'BONK/USD', 'STO/USD', 'LISTA/USD')


def make(panel):
    btc = ind.ret(panel.C[:, [panel.i('BTC/USD')]], 24)                      # (T, 1), causal
    ok = np.repeat(np.nan_to_num(btc, nan=-9.) >= BTC_FLOOR, panel.N, 1)
    ok &= np.array([p not in COARSE for p in panel.pairs])[None, :]
    part = ZScoreMR(panel, n=N, z_in=Z_IN, z_out=Z_OUT, stop_pct=STOP, max_hold=MAX_HOLD, side='long', entry='market', allow_long=ok)
    return Portfolio(panel, [part], slots=SLOTS)
