"""Run the repository's own decision code (roostoo.legs.decide) inside the research harness.

The live runner and this adapter call the same function with the same inputs, so a backtest here is a backtest of
what trades live. Inputs are built with the lab's NumPy indicators; labels come from regime.walk_forward (causal).
"""
import os, sys
import numpy as np

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.environ.get('ROOSTOO_REPO') or os.path.dirname(os.path.dirname(LAB))
for path in (LAB, REPO):
    if path not in sys.path: sys.path.insert(0, path)
import ind, regime                      # lab modules
from harness import Order
from roostoo.legs import decide         # the live decision function

NAMES = {0: 'BEAR', 1: 'CHOP', 2: 'BULL'}
_MEMO = []


def _age(state):
    age = np.zeros(state.shape, int)
    for t in range(1, len(state)): age[t] = np.where(state[t], np.where(state[t - 1], age[t - 1] + 1, 0), 10 ** 6)
    age[0] = 10 ** 6; return age


def walk_forward_labels(P, return_bars, vol_bars, first_train=1500, step=336):
    """(T, N) labels 0 BEAR / 1 CHOP / 2 BULL (-1 unknown): the paper's K-Means + HMM, refitted on past data only."""
    key = (return_bars, vol_bars, first_train, step)
    for k, (p, kk, lab) in enumerate(_MEMO):
        if p is P and kk == key:
            _MEMO.append(_MEMO.pop(k)); return lab
    X = np.stack([ind.logret(P.C, return_bars), ind.realized_vol(P.C, vol_bars)], -1)
    lab = regime.walk_forward(X, first_train=first_train, step=step, K=3, order_by=0, use_hmm=True)[0]
    _MEMO.append((P, key, lab)); del _MEMO[:-3]
    return lab


class RepoLegs:
    def __init__(self, panel, config, return_bars, vol_bars, labels=None):
        P = self.P = panel; c = self.c = config; C = P.C
        self.f = ind.ema(C, c.fast); self.s = ind.ema(C, c.slow); self.atr = ind.atr(P.H, P.L, C, 24)
        self.up = _age(self.f > self.s); self.dn = _age(self.f < self.s)
        mean = ind.sma(C, c.mr_window); sd = ind.rstd(C, c.mr_window); self.z = (C - mean) / np.where(sd > 0, sd, np.nan)
        self.lab = walk_forward_labels(P, return_bars, vol_bars) if labels is None else labels
        self.warm = max(3 * c.slow, 2 * c.mr_window); self.pos = {}; self.locks = {}

    def on_bar(self, t, book):
        P = self.P; names = P.pairs
        for i, p in book.pos.items():                      # positions filled since the last call enter our book
            if names[i] not in self.pos:
                self.pos[names[i]] = dict(leg=p.tag, side=p.side, entry=p.entry, bar=p.t_in, high=p.entry, low=p.entry, level=None)
        for name in [n for n in self.pos if P.i(n) not in book.pos]: del self.pos[name]
        num = lambda x: None if not np.isfinite(x) else float(x)
        features = {name: dict(ready=t >= self.warm, close=float(P.C[t, i]), bar_high=float(P.H[t, i]), bar_low=float(P.L[t, i]),
                               atr_24=float(self.atr[t, i]), ema_fast=num(self.f[t, i]), ema_slow=num(self.s[t, i]),
                               age_up=int(self.up[t, i]), age_down=int(self.dn[t, i]), z=num(self.z[t, i])) for i, name in enumerate(names)}
        labels = {name: NAMES.get(int(self.lab[t, i])) for i, name in enumerate(names)}
        exits, entries = decide(features, labels, self.pos, self.locks, self.c, t)
        orders = [Order(P.i(p), 'SELL' if self.pos[p]['side'] > 0 else 'COVER', tag=self.pos[p]['leg']) for p in exits]
        orders += [Order(P.i(p), 'BUY' if side > 0 else 'SHORT', usd=weight * book.equity, tag=leg) for p, side, leg, weight in entries]
        return orders
