"""integrate_evidence_first candidate 2: the best LONG-ONLY mix, which is the tuned breakout alone behind the BTC gate.

Every long-only addition tested (EMA-cross longs at 20-100% weight, gated or not; the z-score dip sleeve as a sleeve) lowered
at least two of the three ratios, so the best long-only "mix" is one leg:
  enter LONG at the next open when the 12 h return >= 10% AND the close is within 0.1% of the highest close of the last 120 h
  AND BTC's hourly close is above its 480 h EMA (gate on new entries only); strongest 12 h return first; 4 equal slots of
  24.75% of equity. Exit when an hourly close is at or below (highest high since entry - 4 x ATR(24)), the level only ever
  rising; 12 h lockout on that coin after an exit. Market orders at the next hourly open only. Nothing is fitted.
This is exactly what the live bot does today with different numbers plus one BTC EMA. It trades on only about 40% of days and
not at all while BTC is under its 480 h EMA.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parents[1])):
    if _p not in sys.path: sys.path.insert(0, _p)
from mix import Mix   # noqa: E402  (same folder)

PARAMS = dict(wb=1., we=0., wz=0., bo_mw=12, bo_move=.10, bo_hw=120, bo_atr_k=4., bo_slots=4, bo_lock=12, bo_gate=True, gate_ema=480,
              atr_n=24, brake=0.)


def make(panel):
    return Mix(panel, **PARAMS)
