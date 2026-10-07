"""Candidate 2 (track regime_trendchop) - the non-ML equivalent of candidate 1: one threshold on one feature.

EMA 24/100 cross, LONG only, entered only while the cross is at most 15 hours old AND the gap has already opened to at
least 1.25 ATR24 ((EMA24-EMA100)/ATR24 >= 1.25). Resting limit entry 5 bp inside the close with market fallback,
3-ATR trailing stop, exit on the cross back. No classifier, nothing fitted. Cash otherwise; no mean reversion; no shorts.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.abspath(os.path.join(HERE, '..', '..'))
if LAB not in sys.path: sys.path.insert(0, LAB)
from strategies import EmaCross, Portfolio

FRESH = 15; MIN_GAP = 1.25


def make(panel):
    return Portfolio(panel, [EmaCross(panel, 24, 100, side='long', entry='limit', fresh=FRESH, min_gap=MIN_GAP)], slots=4)
