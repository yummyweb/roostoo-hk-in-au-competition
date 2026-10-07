"""Independent audit of tf.TeamFinal against the written spec. Usage: python work/team_final/test_tf.py R V [panel] [start]

1. Features: brute-force recomputation of the two regime features at random (t, coin) points.
2. Rules: the strategy is run once; before every on_bar call the book is photographed. A second, separately written
   rule engine (its own EMA / ATR / SMA / std code, its own trailing level recomputed from the candles since entry,
   its own cooldown book-keeping) then says which orders the spec requires at that bar, and the two lists must be equal
   at every bar: same coins, same order kinds, same dollar sizes, same tags.
3. Mechanics: market orders only, no stop/take levels, nothing before bar 600, at most 4 EMA and 10 MR positions,
   every exit recorded by the harness as a strategy order ('signal'), never as a stop or take fill.
The regime labels themselves are taken from tf.regime_labels (regime.walk_forward); their causality is covered by
h.causality_check and the filter arithmetic by live_check.py.
"""
import os, sys
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as swv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tf
import harness as h

R, V = int(sys.argv[1]), int(sys.argv[2]); name = sys.argv[3] if len(sys.argv) > 3 else 'design'
start = int(sys.argv[4]) if len(sys.argv) > 4 else 1900
P = h.load(name); T, N = P.C.shape; C, H, L = P.C, P.H, P.L

# ---- 1. features
X = tf.features(P, R, V); rng = np.random.default_rng(1); worst = 0.
for _ in range(300):
    t = int(rng.integers(max(R, V), T)); i = int(rng.integers(N))
    r1 = np.log(C[t - V + 1:t + 1, i] / C[t - V:t, i])
    worst = max(worst, abs(X[t, i, 0] - np.log(C[t, i] / C[t - R, i])), abs(X[t, i, 1] - r1.std()) / r1.std())
assert worst < 1e-6, worst
assert np.isnan(X[:max(R, V)]).any(-1).all() and np.isfinite(X[max(R, V):]).all()
print(f'features ok (largest difference from brute force {worst:.1e}; finite from row {max(R, V)})')


# ---- 2. independent indicators
def roll(x, n, fn):
    out = np.full(x.shape, np.nan); out[n - 1:] = fn(swv(x, n, axis=0), -1); return out

def ema(x, n):
    out = np.full(x.shape, np.nan); out[n - 1] = x[:n].mean(0)
    for t in range(n, len(x)): out[t] = x[t] * 2 / (n + 1) + out[t - 1] * (1 - 2 / (n + 1))
    return out

e48, e200 = ema(C, 48), ema(C, 200)
pc = np.vstack([C[:1], C[:-1]]); atr = roll(np.max([H - L, abs(H - pc), abs(L - pc)], 0), 24, np.mean)
z = (C - roll(C, 168, np.mean)) / roll(C, 168, np.std)
up, dn = e48 > e200, e48 < e200
lab, _ = tf.regime_labels(P, R, V)


def age(state, t, i):
    """Bars since the state switched on at or before t (None if it is off)."""
    if not state[t, i]: return None
    k = 0
    while t - k - 1 >= 0 and state[t - k - 1, i]: k += 1
    return k


class Spy:
    def __init__(self, inner): self.inner = inner; self.snap = {}
    def on_bar(self, t, book):
        pos = {i: (p.side, p.tag, p.t_in, p.entry) for i, p in book.pos.items()}
        out = self.inner.on_bar(t, book)
        self.snap[t] = (pos, book.equity, [(o.pair, o.kind, o.usd, o.tag, o.limit, o.stop, o.take, o.frac) for o in out or []])
        return out


spy = Spy(tf.TeamFinal(P, R, V)); r = h.backtest(P, spy, start=start)
block = {}; nord = 0; nbars = 0; kinds = {}
for t in range(start, T - 1):
    pos, eq, got = spy.snap[t]; want = []; n_ema = n_mr = 0; nbars += 1
    assert t >= 600 or not got
    for i, (side, tag, t_in, entry) in pos.items():
        out = 'SELL' if side > 0 else 'COVER'
        if tag == 'ema':
            back = e48[t, i] < e200[t, i] if side > 0 else e48[t, i] > e200[t, i]
            u = np.arange(t_in, t + 1)
            if side > 0:
                hh = np.maximum(np.maximum.accumulate(H[u, i]), entry)        # the harness starts `hi` at the fill price
                level = (np.maximum(hh, C[u, i]) - 6 * atr[u, i]).max(); hit = C[t, i] <= level * (1 + 1e-9)
            else:
                ll = np.minimum(np.minimum.accumulate(L[u, i]), entry)
                level = (np.minimum(ll, C[u, i]) + 6 * atr[u, i]).min(); hit = C[t, i] >= level * (1 - 1e-9)
            if back: block[i] = max(block.get(i, -1), t + 6)                  # no new entry at bars t+1 .. t+5
            if back or hit: want.append((i, out, 0., 'ema'))
            else: n_ema += 1
        else:
            if side > 0: done = z[t, i] >= 0 or C[t, i] <= .8 * entry
            else: done = z[t, i] <= 0 or C[t, i] >= 1.2 * entry
            if done or t - t_in >= 48:
                want.append((i, out, 0., 'mr')); block[i] = max(block.get(i, -1), t + 1 + 12)   # fills at t+1; 12 bars from there
            else: n_mr += 1
    free = [i for i in range(N) if i not in pos and block.get(i, -1) <= t]
    cand = []
    for i in free:
        a_up, a_dn = age(up, t, i), age(dn, t, i)
        if lab[t, i] == 2 and a_up is not None and a_up <= 12: cand.append((abs(e48[t, i] - e200[t, i]) / atr[t, i], i, 'BUY'))
        if lab[t, i] == 0 and a_dn is not None and a_dn <= 12: cand.append((abs(e48[t, i] - e200[t, i]) / atr[t, i], i, 'SHORT'))
    chosen = set()
    for g, i, kind in sorted(cand, reverse=True)[:max(0, 4 - n_ema)]:
        d = 6 * atr[t, i] / C[t, i]; want.append((i, kind, min(.2475 * eq, .01 * eq / d), 'ema')); chosen.add(i)
    mr = sorted(((abs(z[t, i]), i) for i in free if i not in chosen and lab[t, i] == 1 and abs(z[t, i]) >= 3.0), reverse=True)
    for az, i in mr[:max(0, 10 - n_mr)]:
        want.append((i, 'BUY' if z[t, i] < 0 else 'SHORT', .05 * eq, 'mr'))
    for o in got: assert o[4] == 0 and o[5] == 0 and o[6] == 0 and o[7] == 1, ('limit/stop/take/frac used', t, o)
    a = sorted((o[0], o[1], o[3]) for o in got); b = sorted((w[0], w[1], w[3]) for w in want)
    assert a == b, (t, 'strategy', a, 'spec', b)
    for o in got:
        w = next(w for w in want if w[0] == o[0])
        if o[1] in ('BUY', 'SHORT'): assert abs(o[2] - w[2]) <= 1e-6 * eq, (t, o, w)
        kinds[(o[3], o[1])] = kinds.get((o[3], o[1]), 0) + 1
    nord += len(got)
    held = [p for i, p in pos.items()]
    assert sum(1 for p in held if p[1] == 'ema') <= 4 and sum(1 for p in held if p[1] == 'mr') <= 10

assert all(x['reason'] == 'signal' for x in r.trades)
print(f'rules ok: {nbars} bars, {nord} orders identical to the independent rule engine; by leg/kind {kinds}')
print(f'trades {len(r.trades)}, rejected orders (cash) {r.rejects}, max orders in one hour {r.max_orders_per_hour}, '
      f'exit reasons {sorted({x["reason"] for x in r.trades})}')
for x in r.trades:
    if x['tag'] == 'mr': assert x['bars'] <= 49
print('max bars held by an MR trade:', max((x['bars'] for x in r.trades if x['tag'] == 'mr'), default=None))
