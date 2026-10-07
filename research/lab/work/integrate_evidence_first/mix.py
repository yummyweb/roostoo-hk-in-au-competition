"""integrate_evidence_first: one class that runs the surviving legs side by side in one account.

Legs (each owns the positions carrying its tag; every feature is built from the panel given to the constructor):
  'breakout' - long when the 12 h return >= 10% and the close is within 0.1% of the 120 h high; exit when an hourly close
               is 4 x ATR(24) below the highest high since entry (ratcheted); 12 h lockout; market orders.
               Optional gate on NEW entries: BTC hourly close above its 480 h EMA.
  'ema'      - EMA fast/slow crossover (48/200), entry within 3 bars of the cross, exit on the opposite cross or a
               6 x ATR(24) trailing stop; long, short or both; each position sized so the stop loses `risk` of the
               leg's capital (capped at the leg's slot). The stop is either intrabar (Position.stop) or judged on the
               hourly close (market order at the next open).
  'mr'       - slow z-score dip-buy sleeve (168 h, z <= -3, 2/3 at market + 1/3 resting one sd lower, resting sale at the
               mean, 48 h limit, 20% disaster stop). Port of z_risk/zr.py, restricted to its own tag.

Capital: `wb`, `we`, `wz` are each leg's share of account equity (sleeves, re-read from equity at every entry), or
`shared=S` puts breakout and EMA positions in S common equal slots. `brake=X` stops all new entries while equity is more
than X below its 7-day high.
"""
import collections
import numpy as np
import ind
from harness import Order


def _age(state):
    age = np.zeros(state.shape, int)
    for t in range(1, len(state)): age[t] = np.where(state[t], np.where(state[t - 1], age[t - 1] + 1, 0), 10 ** 6)
    age[0] = 10 ** 6; return age


class Mix:
    def __init__(self, panel, wb=.5, we=.5, wz=0., shared=0, expo=.99,
                 # breakout leg (plateau centre of breakout_params, frozen)
                 bo_mw=12, bo_move=.10, bo_hw=120, bo_atr_k=4., bo_slots=4, bo_lock=12, bo_gate=True, gate_ema=480,
                 # EMA leg (plateau centre of ema_windows / ema_risk, frozen)
                 fast=48, slow=200, ema_k=6., ema_side='both', ema_stop='intrabar', ema_slots=4, risk=.01, fresh=3,
                 cooldown=6, ema_gate=False, max_short=None,
                 # z-score sleeve (z_risk candidate 2, frozen)
                 z_n=168, z_in=3., z_stop=.20, z_hold=48, z_slots=10, z_cool=12, z_mode='limit',
                 atr_n=24, brake=0., brake_days=7):
        P = self.P = panel; C = P.C
        self.wb, self.we, self.wz, self.shared, self.expo = wb, we, wz, shared, expo
        self.atr = ind.atr(P.H, P.L, C, atr_n)
        b = P.i('BTC/USD'); e = ind.ema(C[:, [b]], gate_ema)[:, 0]
        self.state = np.where(np.isfinite(e), np.where(C[:, b] > e, 1, -1), 0)      # +1 good, -1 bad, 0 warm-up
        # breakout
        self.r = ind.ret(C, bo_mw); self.top = ind.rmax(C, bo_hw)
        self.bo_move, self.bo_k, self.bo_slots, self.bo_lock, self.bo_gate = bo_move, bo_atr_k, bo_slots, bo_lock, bo_gate
        self.bo_warm = max(72, bo_mw, bo_hw, atr_n); self.locked = {}; self.bo_lvl = {}
        # ema
        self.f = ind.ema(C, fast); self.s = ind.ema(C, slow); self.gap = (self.f - self.s) / self.atr
        self.up = self.f > self.s; self.dn = self.f < self.s; self.age_up = _age(self.up); self.age_dn = _age(self.dn)
        self.ema_k, self.ema_side, self.ema_stop, self.ema_slots, self.risk = ema_k, ema_side, ema_stop, ema_slots, risk
        self.fresh, self.cooldown, self.ema_gate = fresh, cooldown, ema_gate
        self.max_short = ema_slots if max_short is None else max_short
        self.ema_warm = max(slow, atr_n) * 3; self.block = {}; self.ema_lvl = {}; self.ema_plan = {}
        # z-score sleeve
        if wz:
            self.zm = ind.sma(C, z_n); self.zs = ind.rstd(C, z_n); self.z = (C - self.zm) / np.where(self.zs > 0, self.zs, np.nan)
        self.z_in, self.z_stop, self.z_hold, self.z_slots, self.z_cool, self.z_warm = z_in, z_stop, z_hold, z_slots, z_cool, max(z_n, atr_n) * 2
        self.z_mode = z_mode; self.zblock = {}; self.zst = {}; self.zplan = {}; self.ntr = 0
        self.brake = brake; self.eqhist = collections.deque(maxlen=brake_days * 24)

    # ------------------------------------------------------------------------------------------------------------
    def on_bar(self, t, book):
        P = self.P; C = P.C[t]; A = self.atr[t]; orders = []; closing = set()
        eq = book.equity
        self.eqhist.append(eq)
        halted = bool(self.brake) and eq < (1 - self.brake) * max(self.eqhist)
        pend = {o.pair for o, _ in book.pending if o.kind == 'BUY'}

        # ---- exits: breakout (hourly close through the ratcheted 4-ATR level)
        n_bo = 0
        if self.wb or self.shared:
            for p in book.longs():
                if p.tag != 'breakout': continue
                i = p.pair; key = (i, p.t_in); raw = max(p.hi, p.entry) - self.bo_k * A[i]
                lv = max(self.bo_lvl.get(key, 0.), raw if np.isfinite(raw) else 0.)
                self.bo_lvl = {k: v for k, v in self.bo_lvl.items() if k[0] != i}; self.bo_lvl[key] = lv
                if C[i] <= lv:
                    orders.append(Order(i, 'SELL', tag='breakout')); closing.add(i); self.locked[i] = t + self.bo_lock
                else:
                    n_bo += 1
        # ---- exits: EMA (opposite cross, or the 6-ATR trail: intrabar via Position.stop, or on the hourly close)
        n_ema = 0; n_short = 0
        if self.we or self.shared:
            for p in list(book.pos.values()):
                if p.tag != 'ema': continue
                i = p.pair; a = A[i]; key = (i, p.t_in)
                cross = (self.f[t, i] < self.s[t, i]) if p.side > 0 else (self.f[t, i] > self.s[t, i])
                out = cross
                if not out and np.isfinite(a):
                    if self.ema_stop == 'intrabar':
                        if p.side > 0: book.set_stop(i, max(p.stop, max(p.hi, C[i]) - self.ema_k * a))
                        else: book.set_stop(i, min(p.stop or 1e18, min(p.lo, C[i]) + self.ema_k * a))
                    else:
                        prev = self.ema_lvl.get(key, self.ema_plan.get(i, 0.))
                        if p.side > 0:
                            lv = max(prev, max(p.hi, C[i]) - self.ema_k * a); out = C[i] <= lv
                        else:
                            lv = min(prev or 1e18, min(p.lo, C[i]) + self.ema_k * a); out = C[i] >= lv
                        self.ema_lvl = {k: v for k, v in self.ema_lvl.items() if k[0] != i}; self.ema_lvl[key] = lv
                if out:
                    orders.append(Order(i, 'SELL' if p.side > 0 else 'COVER', tag='ema')); closing.add(i)
                    self.block[i] = t + self.cooldown
                else:
                    n_ema += 1; n_short += p.side < 0
        # ---- z-score sleeve: exits and scale-in orders
        if self.wz: orders += self._z_manage(t, book, closing)
        if halted: return orders

        cash = book.free_cash                               # plus what this bar's exits will release (sells go out first)
        for i in closing:
            p = book.pos[i]
            cash += p.qty * C[i] * .995 if p.side > 0 else max(0., p.collateral + p.qty * (p.entry - C[i])) * .995
        def afford(usd):                                    # an entry goes out only if at least half its size is free
            nonlocal cash
            if cash < .5 * usd: return 0.
            usd = min(usd, cash); cash -= usd; return usd

        # ---- entries: breakout
        if self.shared: cap_bo = self.shared - n_ema; slot_bo = eq * self.expo / self.shared
        else: cap_bo = self.bo_slots; slot_bo = eq * self.wb * self.expo / self.bo_slots
        if (self.wb or self.shared) and t >= self.bo_warm and (not self.bo_gate or self.state[t] == 1):
            r = self.r[t]
            for i in np.argsort(-np.nan_to_num(r, nan=-9)):
                if n_bo >= cap_bo or not r[i] >= self.bo_move: break
                if i in book.pos or i in pend or self.locked.get(i, -1) > t or C[i] < self.top[t, i] * .999: continue
                usd = afford(slot_bo)
                if usd <= 0: break
                orders.append(Order(int(i), 'BUY', usd=usd, tag='breakout')); n_bo += 1
        # ---- entries: EMA cross
        if (self.we or self.shared) and t >= self.ema_warm:
            if self.shared: cap_e = self.shared - n_bo; slot_e = eq * self.expo / self.shared; cap_eq = eq
            else: cap_e = self.ema_slots; slot_e = eq * self.we * self.expo / self.ema_slots; cap_eq = eq * self.we
            taken = {o.pair for o in orders}; cand = []
            for i in range(P.N):
                g = self.gap[t, i]
                if i in book.pos or i in pend or i in taken or self.block.get(i, -1) > t or not np.isfinite(g): continue
                if self.ema_side in ('long', 'both') and self.up[t, i] and self.age_up[t, i] <= self.fresh \
                        and (not self.ema_gate or self.state[t] == 1):
                    cand.append((float(g), i, 1))
                elif self.ema_side in ('short', 'both') and self.dn[t, i] and self.age_dn[t, i] <= self.fresh \
                        and (not self.ema_gate or self.state[t] == -1):
                    cand.append((float(-g), i, -1))
            for _, i, sgn in sorted(cand, key=lambda x: -x[0]):
                if n_ema >= cap_e: break
                if sgn < 0 and n_short >= self.max_short: continue
                stop = C[i] - sgn * self.ema_k * A[i]
                if not stop > 0: continue                    # 6 ATR wider than the price: no trade
                usd = afford(min(slot_e, self.risk * cap_eq / (abs(C[i] - stop) / C[i])))
                if usd < 10.: continue
                self.ema_plan[i] = float(stop)
                orders.append(Order(i, 'BUY' if sgn > 0 else 'SHORT', usd=usd, stop=float(stop) if self.ema_stop == 'intrabar' else 0., tag='ema'))
                n_ema += 1; n_short += sgn < 0
        # ---- entries: z-score dips
        if self.wz and t >= self.z_warm: orders += self._z_enter(t, book, closing, {o.pair for o in orders}, afford)
        return orders

    # ---- z-score sleeve (z_risk/zr.py with entry='market', scale=True, exit='take', long only) -----------------------
    def _z_manage(self, t, book, closing):
        out = []; z = self.z[t]; mean = self.zm[t]
        for x in book.trades[self.ntr:]:
            if x['tag'] == 'mr' and x['pair'] not in book.pos: self.zblock[x['pair']] = t + self.z_cool
        self.ntr = len(book.trades)
        for i in list(self.zst):
            if i not in book.pos or book.pos[i].tag != 'mr': del self.zst[i]
        for i, p in list(book.pos.items()):
            if p.tag != 'mr': continue
            s = self.zst.get(i)
            if s is None: s = self.zst[i] = dict(q=p.qty, scaled=False, **self.zplan.get(i, dict(lvl2=0., usd2=0.)))
            if p.qty > s['q'] * 1.05: s['scaled'] = True
            s['q'] = p.qty
            if z[i] >= 0 or t - p.t_in >= self.z_hold or (self.z_mode == 'market' and self.P.C[t, i] <= p.entry * (1 - self.z_stop)):
                out.append(Order(i, 'SELL', tag='mr')); closing.add(i); continue
            if self.z_mode == 'market': continue             # hourly market orders only: no resting sale, no scale-in
            if np.isfinite(mean[i]): book.set_take(i, mean[i])
            if not s['scaled'] and s['lvl2'] > 0 and not book.has_pending(i):
                out.append(Order(i, 'BUY', usd=s['usd2'], limit=s['lvl2'], ttl=1, tag='mr'))
        return out

    def _z_enter(self, t, book, closing, taken, afford):
        out = []; z = self.z[t]; C = self.P.C[t]
        held = len([p for p in book.pos.values() if p.tag == 'mr' and p.pair not in closing])
        free = self.z_slots - held; slot = book.equity * self.wz * self.expo / self.z_slots
        for i in np.argsort(np.nan_to_num(z, nan=9)):
            if free <= 0 or not z[i] <= -self.z_in: break
            i = int(i)
            if i in book.pos or i in taken or book.has_pending(i) or self.zblock.get(i, -1) > t: continue
            lim = self.z_mode == 'limit'; usd = afford(slot * 2 / 3 if lim else slot)
            if usd <= 0: break
            self.zplan[i] = dict(lvl2=float(C[i] - self.zs[t, i]) if lim else 0., usd2=slot / 3)
            out.append(Order(i, 'BUY', usd=usd, stop=float(C[i] * (1 - self.z_stop)) if lim else 0., tag='mr')); free -= 1
        return out
