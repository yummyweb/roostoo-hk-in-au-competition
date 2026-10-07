"""integrate_competition_fit candidate 2: "aggressive". Self-contained and frozen.

Breakout longs with NO gate + EMA 48/200 long and short, both risk-sized at twice the balanced size, stops on hourly closes.
  Gate           : none (the gate removes the right tail along with the left).
  Risk per trade : breakout 2.0% of equity at its stop, EMA 1.0% of equity at its stop.

Common rules (first-round plateau centres, not re-tuned here)
  Breakout longs : hourly close up >= 10% over 12 h AND within 0.1% of the highest close of the last 120 h. Market buy at
                   the next open. Exit: an hourly close at or below (highest high since entry - 4 x ATR(24h)), level never
                   lowered; market sell at the next open; that coin is locked for 12 h. Up to 4 positions, strongest 12 h
                   move first.
  EMA 48/200     : long when EMA(48h) crosses above EMA(200h), short when it crosses below; entry only within 3 hourly bars
                   of the cross. Exit on the opposite cross (then 6 h cooldown on that coin) or when an hourly close passes
                   the trailing level = best price since entry -/+ 6 x ATR(24h) (level never loosened); market order at the
                   next open. Up to 4 positions, widest EMA gap (in ATRs) first.
  Sizing         : position dollars = risk x equity / (stop distance as a fraction of price), capped at 24.75% of equity
                   (99% / 4) and at the free cash. Stop distance = 4 x ATR / price (breakout), 6 x ATR / price (EMA).
  Shared cash    : exits first, then breakout entries, then EMA entries; an entry is skipped when free cash is below half
                   of its intended size. One position per coin; a coin held by one leg is not traded by the other.
Everything is computed inside make(panel) from the panel it is given. Nothing is fitted.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # the lab directory (harness.py, ind.py)
import numpy as np
import ind
from harness import Order


class Feat:
    """All indicators, causal, from one panel."""
    def __init__(self, P, mw=12, hw=120, atr_n=24, fast=48, slow=200, gate=480):
        C = P.C
        self.r = ind.ret(C, mw); self.top = ind.rmax(C, hw); self.atr = ind.atr(P.H, P.L, C, atr_n)
        self.f = ind.ema(C, fast); self.s = ind.ema(C, slow); self.gap = (self.f - self.s) / self.atr
        self.up = self.f > self.s; self.dn = self.f < self.s
        self.age_up = self._age(self.up); self.age_dn = self._age(self.dn)
        b = P.i('BTC/USD'); e = ind.ema(C[:, [b]], gate)[:, 0]
        self.good = np.isfinite(e) & (C[:, b] > e)          # market state: BTC close above its 480 h EMA
        self.bad = np.isfinite(e) & (C[:, b] <= e)
        self.warm = max(hw, 3 * slow, gate)

    @staticmethod
    def _age(state):
        age = np.zeros(state.shape, int)
        for t in range(1, len(state)): age[t] = np.where(state[t], np.where(state[t - 1], age[t - 1] + 1, 0), 10 ** 6)
        age[0] = 10 ** 6; return age


class Combo:
    def __init__(self, panel, feat=None, bo_slots=4, bo_share=.99, bo_gate=False, bo_risk=0., move=.10, atr_k=4., lock=12,
                 ema_side='', ema_slots=4, ema_share=.99, ema_risk=.01, ema_stop_atr=6., fresh=3, cooldown=6,
                 ema_regime=False, ema_stop='intrabar', hedge=0., band=.30):
        self.P = panel; self.F = feat or Feat(panel); self.b = panel.i('BTC/USD')
        self.bo_slots, self.bo_share, self.bo_gate, self.bo_risk = bo_slots, bo_share, bo_gate, bo_risk
        self.move, self.atr_k, self.lock = move, atr_k, lock
        self.ema_side, self.ema_slots, self.ema_share, self.ema_risk = ema_side, ema_slots, ema_share, ema_risk
        self.ema_stop_atr, self.fresh, self.cooldown, self.ema_regime, self.ema_stop = ema_stop_atr, fresh, cooldown, ema_regime, ema_stop
        self.hedge, self.band = hedge, band
        self.locked = {}; self.lvl = {}; self.block = {}; self.elvl = {}

    # ---- breakout leg -------------------------------------------------------------------------------------------
    def _bo_level(self, t, p):
        raw = max(p.hi, p.entry) - self.atr_k * self.F.atr[t, p.pair]
        key = (p.pair, p.t_in); lv = max(self.lvl.get(key, 0.), raw)
        self.lvl = {k: v for k, v in self.lvl.items() if k[0] != p.pair}; self.lvl[key] = lv; return lv

    def on_bar(self, t, book):
        F = self.F
        if t < F.warm: return []
        C = self.P.C[t]; orders = []; closing = set(); avail = book.free_cash
        # 1. exits ---------------------------------------------------------------------------------------------
        bo_held = 0; ema_held = 0
        for p in list(book.pos.values()):
            i = p.pair
            if p.tag == 'breakout':
                if C[i] <= self._bo_level(t, p):
                    orders.append(Order(i, 'SELL', tag='breakout')); self.locked[i] = t + self.lock; closing.add(i); avail += p.qty * C[i]
                else: bo_held += 1
            elif p.tag == 'ema':
                a = F.atr[t, i]; cross = (F.f[t, i] < F.s[t, i]) if p.side > 0 else (F.f[t, i] > F.s[t, i])
                out = cross
                if not out:
                    if p.side > 0: lv = max(p.stop if self.ema_stop == 'intrabar' else self.elvl.get((i, p.t_in), 0.), max(p.hi, C[i]) - self.ema_stop_atr * a)
                    else: lv = min((p.stop if self.ema_stop == 'intrabar' else self.elvl.get((i, p.t_in), 0.)) or 1e18, min(p.lo, C[i]) + self.ema_stop_atr * a)
                    if self.ema_stop == 'intrabar': book.set_stop(i, lv)
                    else:                                    # stop judged on the hourly close, market order at the next open
                        self.elvl = {k: v for k, v in self.elvl.items() if k[0] != i}; self.elvl[(i, p.t_in)] = lv
                        out = (C[i] <= lv) if p.side > 0 else (C[i] >= lv)
                if out:
                    orders.append(Order(i, 'SELL' if p.side > 0 else 'COVER', tag='ema')); closing.add(i)
                    if cross: self.block[i] = t + self.cooldown
                    avail += p.qty * C[i] if p.side > 0 else p.collateral
                else: ema_held += 1
        eq = book.equity
        # 2. hedge: standing BTC short -----------------------------------------------------------------------
        if self.hedge:
            hp = book.pos.get(self.b); target = eq * self.hedge
            if hp is None:
                orders.append(Order(self.b, 'SHORT', usd=target, tag='hedge')); avail -= target
            elif hp.side < 0 and abs(hp.qty * C[self.b] / target - 1) > self.band:
                orders.append(Order(self.b, 'COVER', tag='hedge')); closing.add(self.b)      # re-opened at the right size next bar
        scale = 1 - self.hedge
        taken = set()

        def place(o, usd):
            nonlocal avail
            if avail < .5 * usd or usd < 10.: return False
            o.usd = float(min(usd, avail * .995)); orders.append(o); avail -= o.usd; taken.add(o.pair); return True

        # 3. breakout entries --------------------------------------------------------------------------------
        if self.bo_slots and (not self.bo_gate or F.good[t]):
            r = F.r[t]; slot = eq * self.bo_share * scale / self.bo_slots
            for i in np.argsort(-np.nan_to_num(r, nan=-9)):
                if bo_held >= self.bo_slots or not r[i] >= self.move: break
                i = int(i)
                if i in book.pos or self.locked.get(i, -1) > t or C[i] < F.top[t, i] * .999: continue
                if self.hedge and i == self.b: continue
                usd = slot
                if self.bo_risk:
                    dist = self.atr_k * F.atr[t, i] / C[i]
                    if not np.isfinite(dist) or dist <= 0: continue
                    usd = min(slot, self.bo_risk * eq / dist)
                if place(Order(i, 'BUY', tag='breakout'), usd): bo_held += 1
        # 4. EMA-cross entries -------------------------------------------------------------------------------
        if self.ema_side and ema_held < self.ema_slots:
            cands = []; slot = eq * self.ema_share * scale / self.ema_slots
            for i in range(self.P.N):
                if i in book.pos or i in taken or self.block.get(i, -1) > t or not np.isfinite(F.gap[t, i]): continue
                if self.hedge and i == self.b: continue
                a = F.atr[t, i]
                if self.ema_side in ('long', 'both') and F.up[t, i] and F.age_up[t, i] <= self.fresh and (not self.ema_regime or F.good[t]):
                    cands.append((float(F.gap[t, i]), i, 'BUY', C[i] - self.ema_stop_atr * a))
                elif self.ema_side in ('short', 'both') and F.dn[t, i] and F.age_dn[t, i] <= self.fresh and (not self.ema_regime or F.bad[t]):
                    cands.append((float(-F.gap[t, i]), i, 'SHORT', C[i] + self.ema_stop_atr * a))
            for _, i, kind, st in sorted(cands, key=lambda x: -x[0]):
                if ema_held >= self.ema_slots: break
                dist = abs(C[i] - st) / C[i]
                if not dist > 0: continue
                usd = min(slot, self.ema_risk * eq / dist) if self.ema_risk else slot
                o = Order(i, kind, stop=float(st) if self.ema_stop == 'intrabar' else 0., tag='ema')
                if self.ema_stop != 'intrabar': self.elvl = {k: v for k, v in self.elvl.items() if k[0] != i}
                if place(o, usd): ema_held += 1
        return orders


PARAMS = {'bo_slots': 4, 'bo_gate': False, 'bo_risk': 0.02, 'ema_side': 'both', 'ema_slots': 4, 'ema_risk': 0.01, 'ema_stop': 'close'}


def make(panel):
    return Combo(panel, **PARAMS)
