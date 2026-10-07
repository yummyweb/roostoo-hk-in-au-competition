"""Reference implementations of the two strategy families under study, built on harness.py.

EmaCross  - trend following: fast EMA above/below slow EMA, optional slower trend filter, ATR trailing stop.
ZScoreMR  - mean reversion: price far from its rolling mean in standard deviations, exit at the mean, hard stop.
Portfolio - runs one or more of these parts with a shared number of equal slots.

Each part owns the positions whose tag equals its `tag`. A part exposes:
    manage(t, book)     -> exit orders for its own positions (it also trails stops / targets through the book)
    candidates(t, book) -> [(score, Order)] for new entries; Portfolio sets the order size.
`allow_long` / `allow_short` are optional (T, N) boolean arrays (a regime filter): entries need True at row t.
"""
import numpy as np
from harness import Order
import ind


def _entry(part, i, kind, price, stop, take=0.):
    """Entry order: market, or a resting limit `limit_bps` inside the last close with a time limit."""
    if kind == 'SHORT' or part.entry == 'market':
        return Order(i, kind, stop=stop, take=take, tag=part.tag)
    return Order(i, kind, limit=price * (1 - part.limit_bps / 1e4), ttl=part.ttl, fallback=part.fallback, stop=stop, take=take, tag=part.tag)


class EmaCross:
    def __init__(self, panel, fast=9, slow=21, trend=0, side='long', stop_atr=3., atr_n=24, trail=True, fresh=3,
                 cooldown=6, entry='market', limit_bps=5., ttl=2, fallback='market', allow_long=None, allow_short=None,
                 min_gap=0., tag='ema'):
        P = self.P = panel; C = P.C
        self.f = ind.ema(C, fast); self.s = ind.ema(C, slow); self.tr = ind.ema(C, trend) if trend else None
        self.atr = ind.atr(P.H, P.L, C, atr_n); self.gap = (self.f - self.s) / self.atr
        up = self.f > self.s; dn = self.f < self.s
        if self.tr is not None: up &= C > self.tr; dn &= C < self.tr
        self.up, self.dn = up, dn
        # bars since the state last switched on: an entry is allowed only while the signal is at most `fresh` bars old
        self.age_up = self._age(up); self.age_dn = self._age(dn)
        self.side, self.stop_atr, self.trail, self.fresh, self.cooldown = side, stop_atr, trail, fresh, cooldown
        self.entry, self.limit_bps, self.ttl, self.fallback, self.tag, self.min_gap = entry, limit_bps, ttl, fallback, tag, min_gap
        self.allow_long, self.allow_short = allow_long, allow_short; self.block = {}; self.warm = max(slow, trend, atr_n) * 3

    @staticmethod
    def _age(state):
        age = np.zeros(state.shape, int)
        for t in range(1, len(state)): age[t] = np.where(state[t], np.where(state[t - 1], age[t - 1] + 1, 0), 10 ** 6)
        age[0] = 10 ** 6; return age

    def manage(self, t, book):
        out = []; C = self.P.C[t]
        for p in list(book.pos.values()):
            if p.tag != self.tag: continue
            i = p.pair; a = self.atr[t, i]
            if p.side > 0:
                if self.f[t, i] < self.s[t, i]: out.append(Order(i, 'SELL', tag=self.tag)); self.block[i] = t + self.cooldown
                elif self.trail and self.stop_atr: book.set_stop(i, max(p.stop, max(p.hi, C[i]) - self.stop_atr * a))
            else:
                if self.f[t, i] > self.s[t, i]: out.append(Order(i, 'COVER', tag=self.tag)); self.block[i] = t + self.cooldown
                elif self.trail and self.stop_atr: book.set_stop(i, min(p.stop or 1e18, min(p.lo, C[i]) + self.stop_atr * a))
        return out

    def candidates(self, t, book):
        if t < self.warm: return []
        out = []; C = self.P.C[t]
        for i in range(self.P.N):
            if i in book.pos or book.has_pending(i) or self.block.get(i, -1) > t or not np.isfinite(self.gap[t, i]): continue
            a = self.atr[t, i]
            if self.side in ('long', 'both') and self.up[t, i] and self.age_up[t, i] <= self.fresh and self.gap[t, i] >= self.min_gap \
                    and (self.allow_long is None or self.allow_long[t, i]):
                out.append((float(self.gap[t, i]), _entry(self, i, 'BUY', C[i], C[i] - self.stop_atr * a if self.stop_atr else 0.)))
            elif self.side in ('short', 'both') and self.dn[t, i] and self.age_dn[t, i] <= self.fresh and -self.gap[t, i] >= self.min_gap \
                    and (self.allow_short is None or self.allow_short[t, i]):
                out.append((float(-self.gap[t, i]), _entry(self, i, 'SHORT', C[i], C[i] + self.stop_atr * a if self.stop_atr else 0.)))
        return out


class ZScoreMR:
    def __init__(self, panel, n=48, z_in=2., z_out=0., stop_pct=.05, max_hold=48, rsi_n=14, rsi_max=0., confirm=False,
                 side='long', cooldown=12, entry='market', limit_bps=5., ttl=2, fallback='cancel', maker_exit=True,
                 allow_long=None, allow_short=None, tag='mr'):
        P = self.P = panel; C = P.C
        self.mean = ind.sma(C, n); self.sd = ind.rstd(C, n); self.z = (C - self.mean) / np.where(self.sd > 0, self.sd, np.nan)
        self.rsi = ind.rsi(C, rsi_n) if rsi_max else None
        self.n, self.z_in, self.z_out, self.stop_pct, self.max_hold, self.rsi_max = n, z_in, z_out, stop_pct, max_hold, rsi_max
        self.confirm, self.side, self.cooldown, self.maker_exit = confirm, side, cooldown, maker_exit
        self.entry, self.limit_bps, self.ttl, self.fallback, self.tag = entry, limit_bps, ttl, fallback, tag
        self.allow_long, self.allow_short = allow_long, allow_short; self.block = {}; self.warm = max(n, rsi_n) * 2

    def manage(self, t, book):
        out = []
        for p in list(book.pos.values()):
            if p.tag != self.tag: continue
            i = p.pair; z = self.z[t, i]; target = self.mean[t, i] - p.side * self.z_out * self.sd[t, i]
            done = (z >= -self.z_out) if p.side > 0 else (z <= self.z_out)
            if done or t - p.t_in >= self.max_hold:
                out.append(Order(i, 'SELL' if p.side > 0 else 'COVER', tag=self.tag)); self.block[i] = t + self.cooldown
            elif self.maker_exit and p.side > 0 and np.isfinite(target):
                book.set_take(i, target)        # rest a maker sale at the (moving) mean
            elif p.side < 0 and np.isfinite(target):
                book.set_take(i, target)
        return out

    def candidates(self, t, book):
        if t < self.warm: return []
        out = []; C = self.P.C[t]; prev = self.P.C[t - 1]
        for i in range(self.P.N):
            z = self.z[t, i]
            if not np.isfinite(z) or i in book.pos or book.has_pending(i) or self.block.get(i, -1) > t: continue
            if self.side in ('long', 'both') and z <= -self.z_in and (not self.rsi_max or self.rsi[t, i] <= self.rsi_max) \
                    and (not self.confirm or C[i] > prev[i]) and (self.allow_long is None or self.allow_long[t, i]):
                out.append((float(-z), _entry(self, i, 'BUY', C[i], C[i] * (1 - self.stop_pct) if self.stop_pct else 0.)))
            elif self.side in ('short', 'both') and z >= self.z_in and (not self.rsi_max or self.rsi[t, i] >= 100 - self.rsi_max) \
                    and (not self.confirm or C[i] < prev[i]) and (self.allow_short is None or self.allow_short[t, i]):
                out.append((float(z), _entry(self, i, 'SHORT', C[i], C[i] * (1 + self.stop_pct) if self.stop_pct else 0.)))
        return out


class Portfolio:
    """Shared equal slots across parts. Free slots go to the highest-scoring candidates, alternating between parts."""
    def __init__(self, panel, parts, slots=4, expo=.99, max_short=None):
        self.P, self.parts, self.slots, self.expo = panel, parts, slots, expo
        self.max_short = slots if max_short is None else max_short

    def on_bar(self, t, book):
        orders = []
        for part in self.parts: orders += part.manage(t, book)
        closing = {o.pair for o in orders}
        used = len([i for i in book.pos if i not in closing]) + len({o.pair for o, _ in book.pending if o.kind == 'BUY'})
        shorts = len([p for p in book.shorts() if p.pair not in closing]); free = self.slots - used
        if free <= 0: return orders
        ranked = [sorted(part.candidates(t, book), key=lambda x: -x[0]) for part in self.parts]; taken = set(); k = 0
        while free > 0 and any(ranked):
            lst = ranked[k % len(ranked)]; k += 1
            if not lst: continue
            _, o = lst.pop(0)
            if o.pair in taken or o.pair in closing: continue
            if o.kind == 'SHORT':
                if shorts >= self.max_short: continue
                shorts += 1
            o.usd = book.equity * self.expo / self.slots; orders.append(o); taken.add(o.pair); free -= 1
        return orders
