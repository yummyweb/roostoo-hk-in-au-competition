"""Parameterised rewrite of baselines.Breakout for the breakout_params track.

With the defaults it reproduces baselines.Breakout order for order (checked in sweep.py). Every feature is built from
the panel given to the constructor, and on_bar(t) reads row t only.
"""
import numpy as np
from harness import Order
import ind

COARSE = ('PEPE', '1000CHEEMS', 'SHIB', 'BONK', 'STO', 'LISTA')   # price tick above 10 bp (README)


class BO:
    def __init__(self, panel, move=.08, trail=.06, slots=4, mw=24, hw=72, lock=12, expo=.99,
                 atr_k=0., atr_n=24, stop='close', entry='market', limit_bps=5., ttl=1, fallback='market',
                 drop_coarse=False, top_n=0, vol_n=720, surge=0., surge_n=1, btc_ema=0, drop=(), skip=0., seed=0, tag='breakout'):
        P = self.P = panel; C = P.C
        self.r = ind.ret(C, mw)                                   # momentum over mw hours
        self.top = ind.rmax(C, hw) if hw else None                # highest close of the last hw hours (0 = no condition)
        self.atr = ind.atr(P.H, P.L, C, atr_n) if atr_k else None
        ok = np.ones(C.shape, bool)
        names = [p.split('/')[0] for p in P.pairs]
        if drop_coarse: ok &= np.array([n not in COARSE for n in names])[None, :]
        if drop: ok &= np.array([n not in drop for n in names])[None, :]
        if top_n:                                                 # top-N by trailing dollar volume (vol_n hours), causal
            dv = ind.sma(C * P.V, vol_n); rank = (-np.nan_to_num(dv, nan=-1.)).argsort(1).argsort(1)
            ok &= (rank < top_n) & np.isfinite(dv)
        if surge:                                                 # mean volume of the last surge_n hours above surge x its 72h mean
            vs = ind.sma(P.V, surge_n) / ind.sma(P.V, 72); ok &= np.nan_to_num(vs, nan=0.) > surge
        if btc_ema:                                               # market filter: BTC close above its EMA
            b = P.i('BTC/USD'); e = ind.ema(C[:, [b]], btc_ema)[:, 0]; ok &= (C[:, b] > e)[:, None]
        if skip:                                                  # research only: randomly veto a share of entry chances (noise test)
            ok &= np.random.default_rng(seed).random(C.shape) >= skip
        self.ok = ok
        self.move, self.trail, self.slots, self.lock, self.expo = move, trail, slots, lock, expo
        self.atr_k, self.stop, self.entry, self.limit_bps, self.ttl, self.fallback, self.tag = atr_k, stop, entry, limit_bps, ttl, fallback, tag
        self.warm = max(72, mw, hw, atr_n if atr_k else 0)
        self.locked = {}; self.lvl = {}; self.ntr = 0

    def _level(self, t, p):
        ref = max(p.hi, p.entry)
        raw = ref - self.atr_k * self.atr[t, p.pair] if self.atr_k else ref * (1 - self.trail)
        key = (p.pair, p.t_in); lv = max(self.lvl.get(key, 0.), raw); self.lvl = {k: v for k, v in self.lvl.items() if k[0] != p.pair}
        self.lvl[key] = lv; return lv

    def on_bar(self, t, book):
        if t < self.warm: return []
        C = self.P.C[t]; orders = []; held = 0
        for tr in book.trades[self.ntr:]:                         # intrabar stops fired since the last call: start the lockout
            if tr['reason'] == 'stop': self.locked[tr['pair']] = tr['t_out'] + self.lock
        self.ntr = len(book.trades)
        for p in book.longs():
            lv = self._level(t, p)
            if self.stop == 'close':
                if C[p.pair] <= lv:
                    orders.append(Order(p.pair, 'SELL', tag=self.tag)); self.locked[p.pair] = t + self.lock
                else:
                    held += 1
            else:
                book.set_stop(p.pair, lv); held += 1
        pend = {o.pair for o, _ in book.pending if o.kind == 'BUY'}; held += len(pend)
        r = self.r[t]
        for i in np.argsort(-np.nan_to_num(r, nan=-9)):
            if held >= self.slots or not r[i] >= self.move: break
            if i in book.pos or i in pend or self.locked.get(i, -1) > t or not self.ok[t, i]: continue
            if self.top is not None and C[i] < self.top[t, i] * .999: continue
            i = int(i); usd = book.equity * self.expo / self.slots; st = 0.
            if self.stop != 'close':
                st = C[i] - self.atr_k * self.atr[t, i] if self.atr_k else C[i] * (1 - self.trail)
                if not np.isfinite(st) or st <= 0: continue
            if self.entry == 'market':
                orders.append(Order(i, 'BUY', usd=usd, stop=st, tag=self.tag))
            else:
                orders.append(Order(i, 'BUY', usd=usd, limit=C[i] * (1 - self.limit_bps / 1e4), ttl=self.ttl,
                                    fallback=self.fallback, stop=st, tag=self.tag))
            held += 1
        return orders
