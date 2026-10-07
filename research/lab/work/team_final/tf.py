"""team_final: the team's strategy in one self-contained class.

    regime label per coin and hour (K-Means-initialised 3-state Gaussian HMM, walk-forward, one model for all coins)
        BULL -> EMA 48/200 crossover leg, long        (tag 'ema')
        BEAR -> EMA 48/200 crossover leg, short       (tag 'ema')
        CHOP -> 168 h z-score mean-reversion leg, long and short   (tag 'mr')

Every decision is made at the close of the completed hourly candle t from rows <= t and is a market order that fills
at the open of t+1. No Position.stop, no take levels, no limit orders: every exit is judged on the hourly close.
Everything, including the regime labels, is built inside TeamFinal(panel, ...) from the panel it is given.
"""
import os, sys
import numpy as np

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if LAB not in sys.path: sys.path.insert(0, LAB)
import ind, regime                      # shared, read-only lab modules
from harness import Order

BEAR, CHOP, BULL = 0, 1, 2              # regime.walk_forward numbers the states by their mean return feature, lowest first
FIRST_TRAIN, STEP = 1500, 336           # first fit on 1,500 bars, refit every 336 bars (14 days) on everything seen so far
TIE = 1e-9                              # a close within 1e-9 (relative) of the trailing level counts as AT it: prices sit on
                                        # a tick grid, so exact ties happen and the rolling-sum ATR carries ~1e-14 of rounding


# ---------------------------------------------------------------------------------------------- regime labels
def features(P, R, V):
    """(T, N, 2) causal features: the R-hour log return and the V-hour rolling (population) standard deviation of
    1-hour log returns. NaN during warm-up (rows < R and rows < V)."""
    return np.stack([ind.logret(P.C, R), ind.rstd(ind.logret(P.C, 1), V)], -1)


_MEMO = []          # [(panel, key, (labels, models))], last 3 only: saves refitting when make() is called again on the SAME panel object


def regime_labels(P, R, V, first_train=FIRST_TRAIN, step=STEP):
    """Walk-forward labels (T, N): 0 = BEAR, 1 = CHOP, 2 = BULL, -1 = not known yet; and the list of fitted models.
    The bars [end, end+step) are labelled by the forward filter of the model fitted on bars < end."""
    key = (R, V, first_train, step)
    for k, (p, kk, out) in enumerate(_MEMO):
        if p is P and kk == key:
            _MEMO.append(_MEMO.pop(k)); return out
    lab, _, models = regime.walk_forward(features(P, R, V), first_train=first_train, step=step, K=3, order_by=0, use_hmm=True)
    _MEMO.append((P, key, (lab, models))); del _MEMO[:-3]
    return lab, models


def _age(state):
    """Bars since the boolean state last switched on (0 = the bar it switched on; 10**6 where it is off)."""
    age = np.zeros(state.shape, int)
    for t in range(1, len(state)): age[t] = np.where(state[t], np.where(state[t - 1], age[t - 1] + 1, 0), 10 ** 6)
    age[0] = 10 ** 6; return age


# ---------------------------------------------------------------------------------------------- the strategy
class TeamFinal:
    def __init__(self, panel, R, V, first_train=FIRST_TRAIN, step=STEP):
        P = self.P = panel; C = P.C
        self.lab, self.models = regime_labels(P, R, V, first_train, step)
        self.f = ind.ema(C, 48); self.s = ind.ema(C, 200); self.atr = ind.atr(P.H, P.L, C, 24)
        self.gap = (self.f - self.s) / self.atr
        self.age_up = _age(self.f > self.s); self.age_dn = _age(self.f < self.s)
        sd = ind.rstd(C, 168); self.z = (C - ind.sma(C, 168)) / np.where(sd > 0, sd, np.nan)
        self.block = {}     # pair -> first bar at which a new entry is allowed again
        self.lvl = {}       # (pair, t_in) -> trailing level of an open EMA position
        self.ntr = 0        # trades already seen in book.trades

    def _trail_hit(self, t, p):
        """Ratchet the EMA position's trailing level; True if the completed bar closed at or through it."""
        i = p.pair; a = self.atr[t, i]; c = self.P.C[t, i]; key = (i, p.t_in)
        if p.side > 0:
            lv = max(self.lvl.get(key, 0.), max(p.hi, c) - 6 * a); hit = c <= lv * (1 + TIE)
        else:
            lv = min(self.lvl.get(key, 1e18), min(p.lo, c) + 6 * a); hit = c >= lv * (1 - TIE)
        self.lvl[key] = lv; return bool(hit)

    def on_bar(self, t, book):
        if t < 600: return []
        P = self.P; C = P.C[t]; orders = []
        for x in book.trades[self.ntr:]:                      # 12-bar cooldown after any mean-reversion exit
            if x['tag'] == 'mr': self.block[x['pair']] = max(self.block.get(x['pair'], -1), x['t_out'] + 12)
        self.ntr = len(book.trades)
        self.lvl = {k: v for k, v in self.lvl.items() if k[0] in book.pos and book.pos[k[0]].t_in == k[1]}
        n_ema = n_mr = 0
        for p in list(book.pos.values()):                     # exits: never depend on the label
            i = p.pair; out = 'SELL' if p.side > 0 else 'COVER'
            if p.tag == 'ema':
                back = self.f[t, i] < self.s[t, i] if p.side > 0 else self.f[t, i] > self.s[t, i]
                if back:
                    orders.append(Order(i, out, tag='ema')); self.block[i] = max(self.block.get(i, -1), t + 6)
                elif self._trail_hit(t, p):
                    orders.append(Order(i, out, tag='ema'))
                else:
                    n_ema += 1
            elif p.tag == 'mr':
                z = self.z[t, i]
                if p.side > 0: done = z >= 0 or C[i] <= p.entry * .80
                else: done = z <= 0 or C[i] >= p.entry * 1.20
                if done or t - p.t_in >= 48:
                    orders.append(Order(i, out, tag='mr'))
                else:
                    n_mr += 1
        eq = book.equity; lab = self.lab[t]; taken = set()
        if n_ema < 4:                                         # EMA crossover leg: BULL -> long, BEAR -> short
            cand = []
            for i in range(P.N):
                g = self.gap[t, i]
                if i in book.pos or self.block.get(i, -1) > t or not np.isfinite(g): continue
                if lab[i] == BULL and self.age_up[t, i] <= 12: cand.append((float(g), i, 'BUY'))
                elif lab[i] == BEAR and self.age_dn[t, i] <= 12: cand.append((float(-g), i, 'SHORT'))
            for _, i, kind in sorted(cand, key=lambda x: -x[0]):
                if n_ema >= 4: break
                d = 6 * self.atr[t, i] / C[i]
                orders.append(Order(i, kind, usd=min(.2475 * eq, .01 * eq / d), tag='ema')); taken.add(i); n_ema += 1
        if n_mr < 10:                                         # mean-reversion leg: CHOP only, long and short
            z = self.z[t]
            for i in sorted(np.nonzero((lab == CHOP) & (np.abs(z) >= 3.0))[0], key=lambda j: -abs(z[j])):
                if n_mr >= 10: break
                i = int(i)
                if i in book.pos or i in taken or self.block.get(i, -1) > t: continue
                orders.append(Order(i, 'BUY' if z[i] < 0 else 'SHORT', usd=.05 * eq, tag='mr')); n_mr += 1
        return orders
