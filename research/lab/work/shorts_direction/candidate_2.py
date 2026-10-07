"""shorts_direction candidate 2: candidate 1 plus a standing BTC short as a HEDGE (the only use of shorts this track can defend).

Long book: breakout longs in good markets only (BTC close above its 480h EMA), 4 slots sized on 67% of equity, BTC itself never bought.
Hedge    : a BTC short with collateral = 33% of equity, always on; covered and re-opened only when its size drifts more than
           30% from target (about 2 round trips in 9 months, so its fees are negligible).
Design (rows 744+, default costs): about +84%, max drawdown 13%, Sortino 4.8 / Sharpe 2.4 / Calmar 9.4, thirds +14% / +47% / +9%,
stress costs +63%. Candidate 1 alone: +107%, drawdown 19%, 4.2 / 2.0 / 8.3. So the hedge trades total return for smoother equity.
Read with care: BTC fell 32% in the design period, so the hedge was paid to exist (about +0.35% per 11 days). With BTC's
drift removed the hedged book is no better than the same long book at the same reduced size (Sortino 4.1 vs 4.3, Sharpe 2.1
vs 2.1, drawdown 11% vs 12%), and it should be expected to COST money in a rising market. It is a bet that BTC keeps
falling plus a smaller long book, not a profit source. The long book carries candidate 1's caveats (two coins, few active days).
Everything is computed inside make() from the panel it is given; nothing is fitted.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # the lab directory
import numpy as np
import ind
from harness import Order

GATE_EMA, SLOTS, MOVE, TRAIL, LOCK, HEDGE, BAND = 480, 4, .08, .06, 12, .33, .30


def market_state(panel, n=GATE_EMA):
    """(T,) int, causal: +1 while BTC's close is above its n-hour EMA, -1 while at or below it, 0 during warm-up."""
    btc = panel.C[:, [panel.i('BTC/USD')]]; e = ind.ema(btc, n)[:, 0]
    return np.where(np.isfinite(e), np.where(btc[:, 0] > e, 1, -1), 0)


class HedgedGatedBreakout:
    def __init__(self, panel, state, slots=SLOTS, move=MOVE, trail=TRAIL, lock=LOCK, hedge=HEDGE, band=BAND):
        self.P = panel; self.r24 = ind.ret(panel.C, 24); self.top = ind.rmax(panel.C, 72); self.state = state
        self.slots, self.move, self.trail, self.lock_bars, self.hedge, self.band = slots, move, trail, lock, hedge, band
        self.expo = .99 * (1 - hedge); self.b = panel.i('BTC/USD'); self.locked = {}

    def on_bar(self, t, book):
        if t < 72: return []
        C = self.P.C[t]; orders = []; held = 0; b = self.b
        for p in book.longs():
            if p.tag != 'breakout': continue
            if C[p.pair] <= max(p.hi, p.entry) * (1 - self.trail):
                orders.append(Order(p.pair, 'SELL', tag='breakout')); self.locked[p.pair] = t + self.lock_bars
            else:
                held += 1
        if self.state[t] == 1:
            r = self.r24[t]
            for i in np.argsort(-np.nan_to_num(r, nan=-9)):
                if held >= self.slots or not r[i] >= self.move: break
                if i in book.pos or i == b or self.locked.get(i, -1) > t or C[i] < self.top[t, i] * .999: continue
                orders.append(Order(int(i), 'BUY', usd=book.equity * self.expo / self.slots, tag='breakout')); held += 1
        p = book.pos.get(b); target = book.equity * self.hedge
        if p is None:
            orders.append(Order(b, 'SHORT', usd=target, tag='hedge'))
        elif p.side < 0 and abs(p.qty * C[b] / target - 1) > self.band:
            orders.append(Order(b, 'COVER', tag='hedge'))                 # re-opened at the right size on the next bar
        return orders


def make(panel):
    return HedgedGatedBreakout(panel, market_state(panel))
