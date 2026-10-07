"""shorts_direction candidate 1: the direction rule, with NO shorts. Long breakouts in good markets, cash in bad ones.

Direction rule: the market is "good" while BTC's hourly close is above its own 480-hour (20-day) EMA.
Long book   : baselines.Breakout unchanged (24h return >= 8% and a close at the 72h high; sell when an hourly close is 6%
              below the high since entry; 12h lock-out; 4 equal slots; market orders), entries allowed only in good markets.
              Open longs are NOT force-closed when the market turns bad; they leave by their own trailing exit.
Design (rows 744+, default costs): about +107%, max drawdown 19%, 11-day windows mean +3.6% / median +0.3%,
thirds +23% / +66% / +1%, stress costs +73%. Ungated benchmark: +40%, 43%, +2.1% / -0.6%, +12% / +61% / -23%, stress +4%.
Plateau: all 16 EMA gates of 150-960 h (on BTC or on the equal-weight basket) beat the ungated rule, at default and stress costs.
Caveats: (1) two coins (STO, TUT) carry about 70% of the profit. Without them the gated rule made +30% (ungated +19%), and the
per-trade gap between good-market and bad-market entries disappears (t 1.2 with them, 0.0 without). What survives is the
risk-off effect: fewer trades and a smaller drawdown in a falling market, not better trades. (2) Fills on only about 45% of
days; 59% of 14-day windows had fewer than 8 active days. (3) The same gate made EMA-cross longs WORSE.
Verdict of the track: weak edge for the gate as a risk switch; shorts do not earn their fees.
Everything is computed inside make() from the panel it is given; nothing is fitted.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # the lab directory
import numpy as np
import ind
from harness import Order

GATE_EMA, SLOTS, MOVE, TRAIL, LOCK = 480, 4, .08, .06, 12


def market_state(panel, n=GATE_EMA):
    """(T,) int, causal: +1 while BTC's close is above its n-hour EMA, -1 while at or below it, 0 during warm-up."""
    btc = panel.C[:, [panel.i('BTC/USD')]]; e = ind.ema(btc, n)[:, 0]
    return np.where(np.isfinite(e), np.where(btc[:, 0] > e, 1, -1), 0)


class GatedBreakout:
    """baselines.Breakout with an entry gate: new longs only while state[t] == 1. `skip` = pair indices never bought."""
    def __init__(self, panel, state, slots=SLOTS, move=MOVE, trail=TRAIL, lock=LOCK, expo=.99, skip=()):
        self.P = panel; self.r24 = ind.ret(panel.C, 24); self.top = ind.rmax(panel.C, 72); self.state = state
        self.slots, self.move, self.trail, self.lock_bars, self.expo, self.skip = slots, move, trail, lock, expo, set(skip); self.locked = {}

    def on_bar(self, t, book):
        if t < 72: return []
        C = self.P.C[t]; orders = []; held = 0
        for p in book.longs():
            if p.tag != 'breakout': continue
            if C[p.pair] <= max(p.hi, p.entry) * (1 - self.trail):
                orders.append(Order(p.pair, 'SELL', tag='breakout')); self.locked[p.pair] = t + self.lock_bars
            else:
                held += 1
        if self.state[t] != 1: return orders
        r = self.r24[t]
        for i in np.argsort(-np.nan_to_num(r, nan=-9)):
            if held >= self.slots or not r[i] >= self.move: break
            if i in book.pos or i in self.skip or self.locked.get(i, -1) > t or C[i] < self.top[t, i] * .999: continue
            orders.append(Order(int(i), 'BUY', usd=book.equity * self.expo / self.slots, tag='breakout')); held += 1
        return orders


def make(panel):
    return GatedBreakout(panel, market_state(panel))
