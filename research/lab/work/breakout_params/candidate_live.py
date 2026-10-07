"""The live preset (config/live_candidate.json): +8% in 12h, close within 0.1% of the 120h high, 4-ATR(24h) trailing
stop judged on the hourly close, 4 slots, 12h lockout, market orders. Same rule as candidate_1 with the entry move
at the lower end of the plateau, chosen because it trades on more days."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bo import BO


def make(panel):
    return BO(panel, mw=12, move=.08, hw=120, atr_k=4, atr_n=24, slots=4, lock=12)
