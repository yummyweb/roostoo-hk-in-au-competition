"""z_risk track: z-score mean reversion with every risk / execution option under test in one class.

ZR(panel, n, z_in, ...) is self-contained (does not use strategies.Portfolio) so that stops, scaling in, band limits and
partial exits can be combined. Everything is computed from the panel passed in; state comes from the book only.
"""
import os, sys
import numpy as np

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if LAB not in sys.path: sys.path.insert(0, LAB)
import ind
from harness import Order

HI_TICK = ('PEPE/USD', '1000CHEEMS/USD', 'SHIB/USD', 'BONK/USD', 'STO/USD', 'LISTA/USD')


class ZR:
    def __init__(self, panel, n=48, z_in=2., side='long', stop_pct=.05, stop_z=0., stop_atr=0., atr_n=24, max_hold=48,
                 scale=False, slots=4, entry='market', under_bps=5., ttl=2, fallback='cancel', band_taker=True,
                 exit='take', partial=False, cooldown=12, expo=.99, exclude=(), allow_long=None, allow_short=None, tag='mr', min_breadth=0, max_breadth=0):
        P = self.P = panel; C = P.C
        self.mean = ind.sma(C, n); self.sd = ind.rstd(C, n)
        self.z = (C - self.mean) / np.where(self.sd > 0, self.sd, np.nan)
        self.atr = ind.atr(P.H, P.L, C, atr_n) if stop_atr else None
        self.ok = np.ones(P.N, bool)
        for name in exclude:
            if name in P.pairs: self.ok[P.i(name)] = False
        self.n, self.z_in, self.side = n, z_in, side
        self.stop_pct, self.stop_z, self.stop_atr, self.max_hold = stop_pct, stop_z, stop_atr, max_hold
        self.scale, self.slots, self.entry, self.under_bps, self.ttl, self.fallback = scale, slots, entry, under_bps, ttl, fallback
        self.band_taker, self.exit, self.partial, self.cooldown, self.expo, self.tag = band_taker, exit, partial, cooldown, expo, tag
        self.allow_long, self.allow_short = allow_long, allow_short
        if min_breadth or max_breadth:   # breadth = how many coins are under their band at the same close (causal: row t only)
            cnt = (self.z <= -z_in).sum(1); okb = (cnt >= min_breadth) & ((cnt <= max_breadth) if max_breadth else True)
            self.allow_long = np.broadcast_to(okb[:, None], self.z.shape)
        self.block = {}; self.st = {}; self.plan = {}; self.ntr = 0; self.warm = max(n, atr_n) * 2

    # stop level for a long entered at `ref` (short: mirrored)
    def _stop(self, t, i, ref, side=1):
        if self.stop_pct: return ref * (1 - side * self.stop_pct)
        if self.stop_z: return ref - side * self.stop_z * self.sd[t, i]
        if self.stop_atr: return ref - side * self.stop_atr * self.atr[t, i]
        return 0.

    def on_bar(self, t, book):
        orders = []; closing = set(); z = self.z[t]; mean = self.mean[t]; sd = self.sd[t]; C = self.P.C[t]
        # positions that were closed since the last bar (by us, a stop, a target or a resting sale) start their cooldown
        tr = book.trades
        for x in tr[self.ntr:]:
            if x['pair'] not in book.pos: self.block[x['pair']] = t + self.cooldown
        self.ntr = len(tr)
        for i in list(self.st):
            if i not in book.pos: del self.st[i]
        # ---- manage open positions
        for i, p in list(book.pos.items()):
            s = self.st.get(i)
            if s is None:
                s = self.st[i] = dict(q=p.qty, half=False, scaled=False, **self.plan.get(i, dict(lvl2=0., usd2=0.)))
            if p.qty > s['q'] * 1.05: s['scaled'] = True
            if p.qty < s['q'] * .95: s['half'] = True
            s['q'] = p.qty; zi = z[i]
            if p.side > 0:
                if zi >= 0 or t - p.t_in >= self.max_hold:
                    orders.append(Order(i, 'SELL', tag=self.tag)); closing.add(i); continue
                if self.exit == 'take' and np.isfinite(mean[i]): book.set_take(i, mean[i])
                if self.partial and not s['half'] and np.isfinite(zi):
                    hp = mean[i] - .5 * self.z_in * sd[i]
                    if C[i] >= hp: orders.append(Order(i, 'SELL', frac=.5, tag=self.tag))
                    elif self.exit == 'take': orders.append(Order(i, 'SELL', frac=.5, limit=hp, ttl=1, tag=self.tag))
                if self.scale and not s['scaled'] and s['lvl2'] > 0 and not book.has_pending(i):
                    orders.append(Order(i, 'BUY', usd=s['usd2'], limit=s['lvl2'], ttl=1, tag=self.tag))
            else:
                if zi <= 0 or t - p.t_in >= self.max_hold:
                    orders.append(Order(i, 'COVER', tag=self.tag)); closing.add(i); continue
                if self.exit == 'take' and np.isfinite(mean[i]): book.set_take(i, mean[i])
        # ---- new entries
        if t < self.warm: return orders
        pend = {o.pair for o, _ in book.pending if o.kind == 'BUY' and o.pair not in book.pos}
        free = self.slots - len([i for i in book.pos if i not in closing]) - len(pend)
        if free <= 0: return orders
        slot = book.equity * self.expo / self.slots; cand = []
        fin = np.isfinite(z) & self.ok
        if self.side in ('long', 'both'):
            sel = fin if self.entry == 'band' else fin & (z <= -self.z_in)
            if self.allow_long is not None: sel = sel & self.allow_long[t]
            for i in np.nonzero(sel)[0]: cand.append((float(-z[i]), int(i), 1))
        if self.side in ('short', 'both'):
            sel = fin & (z >= self.z_in)
            if self.allow_short is not None: sel = sel & self.allow_short[t]
            for i in np.nonzero(sel)[0]: cand.append((float(z[i]), int(i), -1))
        cand.sort(key=lambda x: -x[0])
        for _, i, sgn in cand:
            if free <= 0: break
            if i in book.pos or i in pend or book.has_pending(i) or self.block.get(i, -1) > t: continue
            if sgn < 0:
                orders.append(Order(i, 'SHORT', usd=slot, stop=self._stop(t, i, C[i], -1), tag=self.tag)); free -= 1; continue
            usd = slot * (2 / 3 if self.scale else 1.)
            if self.entry == 'market':
                ref = C[i]; o = Order(i, 'BUY', usd=usd, stop=self._stop(t, i, ref), tag=self.tag)
            elif self.entry == 'under':
                ref = C[i] * (1 - self.under_bps / 1e4)
                o = Order(i, 'BUY', usd=usd, limit=ref, ttl=self.ttl, fallback=self.fallback, stop=self._stop(t, i, ref), tag=self.tag)
            else:   # 'band': rest at the band from the last close; a close already under the band is marketable (taker) or a limit just under it
                band = mean[i] - self.z_in * sd[i]
                ref = band if (band < C[i] or self.band_taker) else C[i] * (1 - self.under_bps / 1e4)
                o = Order(i, 'BUY', usd=usd, limit=ref, ttl=1, stop=self._stop(t, i, min(ref, C[i])), tag=self.tag)
            if self.scale: self.plan[i] = dict(lvl2=float(min(ref, C[i]) - sd[i]), usd2=slot / 3)
            orders.append(o); free -= 1
        return orders
