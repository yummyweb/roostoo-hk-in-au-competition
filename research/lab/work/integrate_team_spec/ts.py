"""integrate_team_spec: the team's architecture in one self-contained class.

    regime label per coin (K-Means, walk-forward)  ->  'trend': EMA crossover leg (long and short)
                                                     'chop' : z-score mean-reversion leg (long only)
    optional market-direction rule: BTC hourly close above its 480 h EMA = good (longs only), else bad (shorts only)

Every array is built from the panel given to the constructor helpers; state comes from the book only.
Leg parameters are the plateau centres found by the first-round tracks and are NOT tuned here:
  EMA leg  (ema_risk/candidate_1): EMA 48/200, entry within 3 bars of the cross, 6 x ATR(24) trailing stop, exit on the
           opposite cross, 4 positions, each sized so that its initial stop loses 1% of equity (capped at 1/4 of equity).
  MR leg   (z_risk/candidate_2):   168 h z-score <= -3.0, long only, market entry, sell at the first hourly close with
           z >= 0 or after 48 h, 20% disaster stop, up to 10 small positions, 12 h cooldown.
"""
import os, sys
import numpy as np

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if LAB not in sys.path: sys.path.insert(0, LAB)
from sklearn.cluster import KMeans
import ind                              # shared, read-only lab module
from harness import Order


# ---------------------------------------------------------------------------------------------- regime labels
def core4(P):
    """(T, N, 4) causal trend-vs-chop features: efficiency ratio 72 h and 168 h, EMA24/EMA100 crosses in the last
    168 h, |EMA24 - EMA100| / ATR24. (The 'core4' set of the regime_trendchop track.)"""
    C = P.C; e24 = ind.ema(C, 24); e100 = ind.ema(C, 100); atr = ind.atr(P.H, P.L, C, 24)
    return np.stack([ind.efficiency_ratio(C, 72), ind.efficiency_ratio(C, 168), ind.cross_count(e24, e100, 168),
                     np.abs(e24 - e100) / atr], -1)


_MEMO = []          # [(panel, key, labels)], last 3 panels only: saves refitting when make() is called again on the SAME panel object


def kmeans_labels(P, first_train=456, step=336, sub=60_000, seed=0):
    """Walk-forward K-Means, K=2, one model for all coins, refit every `step` bars (2 weeks) on everything seen so far
    (a fixed-seed random subsample of at most `sub` coin-hours, standardised with the mean/sd of that same past data).
    The bars [end, end+step) are labelled with the model fitted on bars < end, so a label never sees its own future.
    1 = the cluster with the higher 72 h efficiency ratio ('trend'), 0 = 'chop', -1 = not known yet.
    Same procedure as regime.walk_forward(use_hmm=False), with a smaller subsample so the look-ahead check can run 40 cuts."""
    key = (first_train, step, sub, seed)
    for k, (p, kk, lab) in enumerate(_MEMO):
        if p is P and kk == key:
            _MEMO.append(_MEMO.pop(k)); return lab
    X = core4(P); T, N, d = X.shape; first = int(np.argmax(np.isfinite(X).all(-1).all(1)))
    lab = np.full((T, N), -1)
    for end in range(first + first_train, T, step):
        tr = X[first:end].reshape(-1, d); tr = tr[np.isfinite(tr).all(1)]; mean = tr.mean(0); sd = tr.std(0)
        idx = np.random.default_rng(seed).choice(len(tr), min(len(tr), sub), replace=False)
        km = KMeans(2, n_init=3, random_state=seed).fit((tr[idx] - mean) / sd)
        rank = np.empty(2, int); rank[np.argsort(km.cluster_centers_[:, 0])] = np.arange(2)
        hi = min(T, end + step); Z = (X[end:hi] - mean) / sd; okz = np.isfinite(Z).all(-1)
        dist = ((np.where(okz[..., None], Z, 0.)[:, :, None, :] - km.cluster_centers_[None, None]) ** 2).sum(-1)
        lab[end:hi] = np.where(okz, rank[dist.argmin(-1)], -1)
    _MEMO.append((P, key, lab)); del _MEMO[:-3]
    return lab


def threshold_labels(P, thr=1.25):
    """Plain rule with no fitting: trend where |EMA24 - EMA100| / ATR24 > thr."""
    g = core4(P)[..., 3]; lab = np.full(g.shape, -1); ok = np.isfinite(g); lab[ok] = g[ok] > thr; return lab


def shift_labels(lab, k=1000):
    """Placebo: the same labels k bars late (same frequency and persistence, no information about now)."""
    out = np.full(lab.shape, -1); out[k:] = lab[:-k]; return out


def perm_labels(lab, seed=0):
    """Placebo: every coin gets another coin's label path (keeps market-wide timing, removes coin information)."""
    rng = np.random.default_rng(seed); N = lab.shape[1]
    while True:
        p = rng.permutation(N)
        if not (p == np.arange(N)).any(): break
    return lab[:, p]


def btc_good(P, n=480):
    """(T,) bool, causal: BTC hourly close above its n-hour EMA. False during warm-up."""
    b = P.C[:, [P.i('BTC/USD')]]; e = ind.ema(b, n)[:, 0]
    return np.isfinite(e) & (b[:, 0] > e)


def _age(state):
    """Bars since the boolean state last switched on (10**6 where it is off)."""
    age = np.zeros(state.shape, int)
    for t in range(1, len(state)): age[t] = np.where(state[t], np.where(state[t - 1], age[t - 1] + 1, 0), 10 ** 6)
    age[0] = 10 ** 6; return age


# ---------------------------------------------------------------------------------------------- the strategy
class TeamSpec:
    """EMA-cross leg (tag 'ema') and z-score mean-reversion leg (tag 'mr') with separate position budgets.

    ema_long / ema_short / mr_long: optional (T, N) boolean arrays; a NEW position needs True at the decision bar.
    Exits never depend on the gates: an open position leaves by its own rules.
    stop_mode 'intrabar': protective levels sit in the book and fire inside the hour (the bot's one-minute poll).
    stop_mode 'close'   : levels are judged on the completed hourly candle and left with a market order next bar.
    """
    def __init__(self, panel, ema_long=None, ema_short=None, mr_long=None, use_ema=True, use_mr=True,
                 fast=48, slow=200, stop_atr=6., atr_n=24, fresh=3, cooldown=6, ema_slots=4, risk=.01, expo=.99,
                 mr_n=168, mr_z=3.0, mr_stop=.20, mr_hold=48, mr_slots=10, mr_frac=.05, mr_cool=12, mr_take=False,
                 stop_mode='intrabar'):
        P = self.P = panel; C = P.C
        self.f = ind.ema(C, fast); self.s = ind.ema(C, slow); self.atr = ind.atr(P.H, P.L, C, atr_n)
        self.gap = (self.f - self.s) / self.atr
        self.up = self.f > self.s; self.dn = self.f < self.s; self.age_up = _age(self.up); self.age_dn = _age(self.dn)
        self.mean = ind.sma(C, mr_n); self.sd = ind.rstd(C, mr_n)
        self.z = (C - self.mean) / np.where(self.sd > 0, self.sd, np.nan)
        self.ema_long, self.ema_short, self.mr_long, self.use_ema, self.use_mr = ema_long, ema_short, mr_long, use_ema, use_mr
        self.stop_atr, self.fresh, self.cooldown, self.ema_slots, self.risk, self.expo = stop_atr, fresh, cooldown, ema_slots, risk, expo
        self.mr_z, self.mr_stop, self.mr_hold, self.mr_slots, self.mr_frac, self.mr_cool, self.mr_take = mr_z, mr_stop, mr_hold, mr_slots, mr_frac, mr_cool, mr_take
        self.stop_mode = stop_mode; self.warm = max(3 * slow, 2 * mr_n)
        self.block = {}; self.lvl = {}; self.ntr = 0

    def _trail(self, t, p, book):
        """Ratchet the EMA leg's stop level; return True if (close mode) the completed bar closed through it."""
        i = p.pair; a = self.atr[t, i]; c = self.P.C[t, i]; key = (i, p.t_in)
        if p.side > 0:
            lv = max(self.lvl.get(key, 0.), max(p.hi, c) - self.stop_atr * a) if np.isfinite(a) else self.lvl.get(key, 0.)
            hit = c <= lv
        else:
            lv = min(self.lvl.get(key, 1e18), min(p.lo, c) + self.stop_atr * a) if np.isfinite(a) else self.lvl.get(key, 1e18)
            hit = c >= lv
        self.lvl[key] = lv
        if self.stop_mode == 'intrabar':
            book.set_stop(i, lv); return False
        return bool(hit)

    def on_bar(self, t, book):
        P = self.P; C = P.C[t]; orders = []; closing = set()
        for x in book.trades[self.ntr:]:                      # mean-reversion cooldown after any exit of that leg
            if x['tag'] == 'mr' and x['pair'] not in book.pos: self.block[x['pair']] = max(self.block.get(x['pair'], -1), x['t_out'] + self.mr_cool)
        self.ntr = len(book.trades)
        self.lvl = {k: v for k, v in self.lvl.items() if k[0] in book.pos and book.pos[k[0]].t_in == k[1]}
        n_ema = n_mr = n_short = 0
        for p in list(book.pos.values()):
            i = p.pair
            if p.tag == 'ema':
                cross = (self.f[t, i] < self.s[t, i]) if p.side > 0 else (self.f[t, i] > self.s[t, i])
                if cross:
                    orders.append(Order(i, 'SELL' if p.side > 0 else 'COVER', tag='ema')); closing.add(i); self.block[i] = t + self.cooldown
                elif self._trail(t, p, book):
                    orders.append(Order(i, 'SELL' if p.side > 0 else 'COVER', tag='ema')); closing.add(i)
                else:
                    n_ema += 1; n_short += p.side < 0
            elif p.tag == 'mr':
                zi = self.z[t, i]
                if zi >= 0 or t - p.t_in >= self.mr_hold or (self.stop_mode == 'close' and C[i] <= p.entry * (1 - self.mr_stop)):
                    orders.append(Order(i, 'SELL', tag='mr')); closing.add(i)
                else:
                    n_mr += 1
                    if self.mr_take and np.isfinite(self.mean[t, i]): book.set_take(i, self.mean[t, i])
        if t < self.warm: return orders
        eq = book.equity; taken = set()
        if self.use_ema and n_ema < self.ema_slots:
            cand = []
            for i in range(P.N):
                g = self.gap[t, i]
                if i in book.pos or book.has_pending(i) or self.block.get(i, -1) > t or not np.isfinite(g): continue
                if self.up[t, i] and self.age_up[t, i] <= self.fresh and (self.ema_long is None or self.ema_long[t, i]):
                    cand.append((float(g), i, 'BUY'))
                elif self.dn[t, i] and self.age_dn[t, i] <= self.fresh and (self.ema_short is None or self.ema_short[t, i]):
                    cand.append((float(-g), i, 'SHORT'))
            for _, i, kind in sorted(cand, key=lambda x: -x[0]):
                if n_ema >= self.ema_slots: break
                dist = self.stop_atr * self.atr[t, i] / C[i]
                if not (0 < dist < 1): continue
                usd = min(eq * self.expo / self.ema_slots, self.risk * eq / dist)
                st = C[i] * (1 - dist) if kind == 'BUY' else C[i] * (1 + dist)
                orders.append(Order(i, kind, usd=usd, stop=st if self.stop_mode == 'intrabar' else 0., tag='ema'))
                taken.add(i); n_ema += 1
        if self.use_mr and n_mr < self.mr_slots:
            z = self.z[t]; sel = np.isfinite(z) & (z <= -self.mr_z)
            if self.mr_long is not None: sel &= self.mr_long[t]
            for i in sorted(np.nonzero(sel)[0], key=lambda j: z[j]):
                if n_mr >= self.mr_slots: break
                i = int(i)
                if i in book.pos or i in taken or book.has_pending(i) or self.block.get(i, -1) > t: continue
                orders.append(Order(i, 'BUY', usd=eq * self.mr_frac, stop=C[i] * (1 - self.mr_stop) if self.stop_mode == 'intrabar' else 0., tag='mr'))
                n_mr += 1
        return orders


# ---------------------------------------------------------------------------------------------- wiring
def build(panel, label='km', direction='none', inverse=False, gate_ema=True, gate_mr=True, mr_dir=True, **kw):
    """Assemble the team's map on `panel`.
    label     : 'km' (walk-forward K-Means), 'thr' (|EMA24-EMA100|/ATR24 > 1.25), 'none' (no regime switch),
                'shift' (K-Means labels 1,000 bars late), 'perm<k>' (each coin gets another coin's K-Means labels).
    inverse   : swap the map (EMA in 'chop', mean reversion in 'trend').
    direction : 'none' (long and short always) or 'btc' (BTC close above its 480 h EMA: longs only; else shorts only).
    mr_dir    : with direction='btc', whether the (long-only) mean-reversion leg also needs a good market."""
    T, N = panel.C.shape; el = es = ml = None
    if label != 'none':
        lab = threshold_labels(panel) if label == 'thr' else kmeans_labels(panel)
        if label == 'shift': lab = shift_labels(lab)
        elif label.startswith('perm'): lab = perm_labels(lab, int(label[4:]))
        trend, chop = lab == 1, lab == 0
        if inverse: trend, chop = chop, trend
        if gate_ema: el = es = trend
        if gate_mr: ml = chop
    if direction == 'btc':
        good = np.broadcast_to(btc_good(panel)[:, None], (T, N)); bad = ~good
        el = good if el is None else el & good; es = bad if es is None else es & bad
        if mr_dir: ml = good if ml is None else ml & good
    return TeamSpec(panel, ema_long=el, ema_short=es, mr_long=ml, **kw)
