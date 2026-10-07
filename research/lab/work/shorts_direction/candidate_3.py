"""shorts_direction candidate 3: the team's rule as stated ("long in good markets, short in bad ones, always trading"),
in its least-bad form. LEAST-BAD FOR THE SHORT LEG, NOT A PROVEN SHORT EDGE.

Direction rule: good while BTC's hourly close is above its 480h EMA, bad otherwise.
Good markets  : breakout longs (24h return >= 8% and a close at the 72h high; exit 6% below the high since entry).
Bad markets   : EMA-cross shorts (fast 24h below slow 200h, entry within 3 bars of the cross, 6-ATR(24h) trailing stop,
                cover on the opposite cross), at most 2 of the 4 slots. Positions are not force-closed when the state flips.
Design (rows 744+, default costs): about +130%, max drawdown 22%, thirds +20% / +80% / +6%, stress costs +75%; the short leg
earned about $24k of $131k and raised the share of days with a fill from 45% to 75%.
Why "least-bad": (1) the mirrored breakdown short (16 settings) and z-score shorts lose; this is the only short leg that did not.
(2) The direction signal is not what made the shorts pay: shorting only in GOOD markets earned as much, and shorting always
earned more (12 of 12 comparisons). (3) All of the short profit came from the middle third (-$2k / +$27k / -$1k), and with
one short slot instead of two the same leg lost $5k. (4) The short leg is about -0.4 to -0.5 beta to the basket: in the
11-day blocks where the basket rose it lost 1-7% per block in all 40 EMA settings tested. Beyond being short the market its
alpha (run alone, short only in bad markets) is about +1.2% per 11 days (t 1.0), +0.5% after stress costs (t 0.5); the median
of the 40 always-on settings is +0.2% / -1.5%. At stress costs the short leg's profit inside this candidate is $4k, not $24k.
Use it for activity, size it small, and expect it to cost money if the market rallies. Long book: candidate 1's caveats apply.
Everything is computed inside make() from the panel it is given; nothing is fitted.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # the lab directory
import numpy as np
import ind
from harness import Order
from strategies import EmaCross

GATE_EMA, SLOTS, SHORT_SLOTS, MOVE, TRAIL, LOCK = 480, 4, 2, .08, .06, 12
FAST, SLOW, STOP_ATR = 24, 200, 6.


def market_state(panel, n=GATE_EMA):
    """(T,) int, causal: +1 while BTC's close is above its n-hour EMA, -1 while at or below it, 0 during warm-up."""
    btc = panel.C[:, [panel.i('BTC/USD')]]; e = ind.ema(btc, n)[:, 0]
    return np.where(np.isfinite(e), np.where(btc[:, 0] > e, 1, -1), 0)


class LongBreakoutShortEma:
    def __init__(self, panel, state, slots=SLOTS, short_slots=SHORT_SLOTS, move=MOVE, trail=TRAIL, lock=LOCK, expo=.99):
        self.P = panel; self.r24 = ind.ret(panel.C, 24); self.top = ind.rmax(panel.C, 72); self.state = state
        self.slots, self.short_slots, self.move, self.trail, self.lock_bars, self.expo = slots, short_slots, move, trail, lock, expo; self.locked = {}
        bad = np.repeat((state == -1)[:, None], panel.N, 1)
        self.part = EmaCross(panel, fast=FAST, slow=SLOW, side='short', stop_atr=STOP_ATR, atr_n=24, trail=True, fresh=3, cooldown=6,
                             entry='market', allow_short=bad, tag='ema')

    def on_bar(self, t, book):
        if t < 72: return []
        C = self.P.C[t]; orders = []; held = 0
        shorts = [p for p in book.pos.values() if p.tag == 'ema']; cap = self.slots - len(shorts)       # longs use the slots shorts do not hold
        for p in book.longs():
            if p.tag != 'breakout': continue
            if C[p.pair] <= max(p.hi, p.entry) * (1 - self.trail):
                orders.append(Order(p.pair, 'SELL', tag='breakout')); self.locked[p.pair] = t + self.lock_bars
            else:
                held += 1
        if self.state[t] == 1:
            r = self.r24[t]
            for i in np.argsort(-np.nan_to_num(r, nan=-9)):
                if held >= cap or not r[i] >= self.move: break
                if i in book.pos or self.locked.get(i, -1) > t or C[i] < self.top[t, i] * .999: continue
                orders.append(Order(int(i), 'BUY', usd=book.equity * self.expo / self.slots, tag='breakout')); held += 1
        orders += self.part.manage(t, book)                                                             # covers, trailing stops
        closing = {o.pair for o in orders if o.kind in ('SELL', 'COVER')}; taken = {o.pair for o in orders}
        n_short = len([p for p in shorts if p.pair not in closing])
        n_all = len([i for i in book.pos if i not in closing]) + len([o for o in orders if o.kind in ('BUY', 'SHORT')])
        for _, o in sorted(self.part.candidates(t, book), key=lambda x: -x[0]):
            if n_short >= self.short_slots or n_all >= self.slots: break
            if o.pair in taken: continue
            o.usd = book.equity * self.expo / self.slots; orders.append(o); n_short += 1; n_all += 1
        return orders


def make(panel):
    return LongBreakoutShortEma(panel, market_state(panel))
