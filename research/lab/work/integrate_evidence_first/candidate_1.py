"""integrate_evidence_first candidate 1: the best mix. Breakout longs + EMA 48/200 long/short, two capital sleeves, hourly decisions, market orders only.

Sleeve A, 'breakout' (67% of equity, 4 equal slots of 16.6% of equity each):
  enter LONG at the next open when the 12 h return >= 10% AND the close is within 0.1% of the highest close of the last 120 h
  AND BTC's hourly close is above its 480 h EMA (gate on new entries only; open trades are not force-closed);
  strongest 12 h return first. Exit when an hourly close is at or below (highest high since entry - 4 x ATR(24)), the level
  only ever rising; 12 h lockout on that coin after an exit.
Sleeve B, 'ema' (67% of equity, 4 slots):
  enter LONG within 3 bars of EMA(48) crossing above EMA(200), SHORT within 3 bars of crossing below (no market gate, no
  third trend line); largest |EMA48-EMA200|/ATR(24) first. Size = min(16.6% of equity, 0.67% of equity / stop distance),
  stop distance = 6 x ATR(24) / close. Exit on the opposite cross (then 6 h block on that coin), or when an hourly close is
  through the trailing level (long: max(high since entry, close) - 6 ATR, ratcheting up; short mirrored).
All orders are market orders at the next hourly open. No intrabar stops, no limit orders. Nothing is fitted.
Design (rows 744+, default costs): see REPORT.txt.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parents[1])):
    if _p not in sys.path: sys.path.insert(0, _p)
from mix import Mix   # noqa: E402  (same folder)

PARAMS = dict(wb=.67, we=.67, wz=0., bo_mw=12, bo_move=.10, bo_hw=120, bo_atr_k=4., bo_slots=4, bo_lock=12, bo_gate=True, gate_ema=480,
              fast=48, slow=200, ema_k=6., ema_side='both', ema_stop='close', ema_slots=4, risk=.01, fresh=3, cooldown=6, ema_gate=False,
              atr_n=24, brake=0.)


def make(panel):
    return Mix(panel, **PARAMS)
