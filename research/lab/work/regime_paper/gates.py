"""Causal state-to-strategy maps and the gated reference portfolio.

At every monthly refit e the map is rebuilt from the labelled past only:
  EmaCross longs allowed in states whose past trend payoff  sign(EMA24-EMA100) x 72h forward return averaged > 0,
  ZScoreMR longs allowed in states whose past MR payoff     -clip(z48,-3,3) x 24h forward return averaged > 0,
  shorts allowed in the bearish state = the state with the lowest average trailing 24h return so far.
Forward returns are used only where they were fully realised before e. No trading before the first map exists."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, rp, ind, regime
from strategies import EmaCross, ZScoreMR, Portfolio


def causal_maps(panel, canon, K, start=rp.START, step=rp.STEP, min_n=200):
    T, N = panel.C.shape; trend, mr = rp.proxies(panel); pt = np.nan_to_num(trend) * rp.fwd(panel, 72); pm = np.nan_to_num(mr) * rp.fwd(panel, 24)
    r24 = ind.ret(panel.C, 24); ALe = np.zeros((T, N), bool); ALm = np.zeros((T, N), bool); AS = np.zeros((T, N), bool); log = []
    for e in range(start + step, T, step):
        L = canon[start:e]; ok_e = []; ok_m = []; back = []
        for s in range(K):
            m = L == s; mt = m.copy(); mt[max(0, e - start - 72):] = False; mm = m.copy(); mm[max(0, e - start - 24):] = False
            ok_e.append(mt.sum() >= min_n and pt[start:e][mt].mean() > 0); ok_m.append(mm.sum() >= min_n and pm[start:e][mm].mean() > 0)
            back.append(r24[start:e][m].mean() if m.sum() >= min_n else np.inf)
        bear = int(np.argmin(back)); blk = canon[e:e + step]
        ALe[e:e + step] = np.isin(blk, np.flatnonzero(ok_e)); ALm[e:e + step] = np.isin(blk, np.flatnonzero(ok_m)); AS[e:e + step] = blk == bear
        log.append((e, [int(x) for x in ok_e], [int(x) for x in ok_m], bear))
    return ALe, ALm, AS, log


def causal_labels(panel, scope, rw, vw, K, hmm, start=rp.START, step=rp.STEP, iters=40):
    X = rp.features(panel, rw, vw, scope); first = int(np.argmax(np.isfinite(X).all(-1).all(1)))
    lab, _, models = regime.walk_forward(X, first_train=start - first, step=step, K=K, order_by=0, iters=iters, use_hmm=hmm)
    canon, _ = rp.canonical(lab, models, start, step)
    return np.repeat(canon, panel.N, 1) if canon.shape[1] == 1 else canon


def portfolio(panel, ALe=None, ALm=None, AS=None, which='EMS', slots=4):
    parts = []
    if 'E' in which: parts.append(EmaCross(panel, 24, 100, entry='limit', allow_long=ALe))
    if 'M' in which: parts.append(ZScoreMR(panel, 48, 2., entry='limit', allow_long=ALm))
    if 'S' in which: parts.append(EmaCross(panel, 24, 100, side='short', allow_short=AS, tag='short'))
    return Portfolio(panel, parts, slots=slots)


def vol_state(canon, K, which, by, start=rp.START, step=rp.STEP, min_n=200):
    """(T,N) bool: True where the label is the state with the lowest ('lo') or highest ('hi') average of `by` over the
    labelled past, re-identified at every refit. Nothing is allowed before the first refit after `start`."""
    A = np.zeros(canon.shape, bool)
    for e in range(start + step, canon.shape[0], step):
        L = canon[start:e]; m = [by[start:e][L == s].mean() if (L == s).sum() >= min_n else np.nan for s in range(K)]
        if not np.isfinite(m).any(): continue
        A[e:e + step] = canon[e:e + step] == (np.nanargmin(m) if which == 'lo' else np.nanargmax(m))
    return A
