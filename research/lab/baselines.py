"""Reference strategies. Breakout is the rule currently on branch v2 (market orders, hourly-close trailing stop)."""
import numpy as np
from harness import Order
import ind


class Breakout:
    def __init__(self, panel, slots=4, move=.08, trail=.06, lock=12, expo=.99):
        self.P = panel; self.r24 = ind.ret(panel.C, 24); self.top = ind.rmax(panel.C, 72)
        self.slots, self.move, self.trail, self.lock_bars, self.expo = slots, move, trail, lock, expo; self.locked = {}

    def on_bar(self, t, book):
        if t < 72: return []
        C = self.P.C[t]; orders = []; held = 0
        for p in book.longs():
            if C[p.pair] <= max(p.hi, p.entry) * (1 - self.trail):
                orders.append(Order(p.pair, 'SELL', tag='breakout')); self.locked[p.pair] = t + self.lock_bars
            else:
                held += 1
        r = self.r24[t]
        for i in np.argsort(-np.nan_to_num(r, nan=-9)):
            if held >= self.slots or not r[i] >= self.move: break
            if i in book.pos or self.locked.get(i, -1) > t or C[i] < self.top[t, i] * .999: continue
            orders.append(Order(int(i), 'BUY', usd=book.equity * self.expo / self.slots, tag='breakout')); held += 1
        return orders


class BuyHold:
    def __init__(self, panel, pair='BTC/USD'):
        self.i = panel.i(pair); self.done = False

    def on_bar(self, t, book):
        if self.done: return []
        self.done = True; return [Order(self.i, 'BUY', usd=book.equity * .99, tag='hold')]
