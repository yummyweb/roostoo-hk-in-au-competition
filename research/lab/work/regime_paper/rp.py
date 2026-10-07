"""Shared helpers for the regime_paper track: features, causal labels (cached), proxies."""
import sys, os, time
LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, LAB)
import numpy as np
import harness as h, ind, regime

HERE = os.path.dirname(os.path.abspath(__file__)); CACHE = os.path.join(HERE, 'cache')
START = 744; STEP = 720


def features(P, rw, vw, scope='coin'):
    """(T, N or 1, 2): log return over rw bars, rolling std of 1-bar log returns over vw bars (the paper's two features)."""
    C = P.C
    if scope == 'btc':
        C = C[:, [P.i('BTC/USD')]]
    elif scope == 'basket':            # equal-weight basket index, rebalanced hourly
        r = np.nan_to_num(ind.ret(P.C, 1)).mean(1); C = np.cumprod(1 + r)[:, None]
    r = ind.logret(C, rw); v = ind.realized_vol(C, vw); v[:vw] = np.nan
    return np.stack([r, v], -1)


def canonical(lab_ret, models, start=START, step=STEP):
    """Relabel so a state keeps its identity across refits: each refit's states are matched to the previous refit's
    (nearest means in raw feature units, Hungarian); ids are the first model's return order. Uses fitted models only: causal."""
    from scipy.optimize import linear_sum_assignment
    out = lab_ret.copy(); prev = None; ids = None; maps = []
    for j, m in enumerate(models):
        raw = (m['mu'] * m['sd'] + m['mean'])[m['order']]             # state means in raw units, return-ordered
        if prev is None: ids = np.arange(len(raw))
        else:
            sc = raw.std(0) + prev.std(0) + 1e-12; cost = (((raw[:, None] - prev[None]) / sc) ** 2).sum(-1)
            r, c = linear_sum_assignment(cost); new = np.empty(len(raw), int); new[r] = ids_prev[c]; ids = new
        seg = slice(m['end'], m['end'] + step); blk = lab_ret[seg]; out[seg] = np.where(blk >= 0, ids[np.clip(blk, 0, None)], -1)
        canon = np.empty_like(raw); canon[ids] = raw; prev = canon; ids_prev = np.arange(len(raw)); maps.append(ids.copy())
    return out, np.array(maps)


def labels(P, rw, vw, K=3, hmm=True, scope='coin', iters=40, cache=True, start=START, step=STEP):
    """Causal labels (T, N) int8, -1 where unknown. Returns (lab_ret, lab_canon, maps):
    lab_ret   - states numbered at every refit by the training mean of the return feature (0 = most bearish), as in the paper;
    lab_canon - the same states with identities matched across refits (ids = first model's return order);
    maps[j,s] - canonical id of return-ordered state s under refit j (rows differ => the return ordering flipped)."""
    key = f'{scope}_r{rw}_v{vw}_K{K}_{"hmm" if hmm else "km"}'; f = os.path.join(CACHE, key + '.npz')
    if cache and os.path.exists(f):
        z = np.load(f); return z['lab'], z['canon'], z['maps']
    X = features(P, rw, vw, scope); ok = np.isfinite(X).all(-1); first = int(np.argmax(ok.all(1)))
    lab, probs, models = regime.walk_forward(X, first_train=start - first, step=step, K=K, order_by=0, iters=iters, use_hmm=hmm)
    canon, maps = canonical(lab, models, start, step)
    if lab.shape[1] == 1: lab = np.repeat(lab, P.N, 1); canon = np.repeat(canon, P.N, 1)
    lab = lab.astype(np.int8); canon = canon.astype(np.int8)
    if cache: np.savez_compressed(f, lab=lab, canon=canon, maps=maps)
    return lab, canon, maps


def proxies(P):
    C = P.C; e24 = ind.ema(C, 24); e100 = ind.ema(C, 100); z48 = ind.zscore(C, 48)
    return np.sign(e24 - e100), -np.clip(z48, -3, 3)


def fwd(P, n):
    out = np.full(P.C.shape, np.nan); out[:-n] = P.C[n:] / P.C[:-n] - 1; return out


def shift_placebo(lab, k=1000, start=START):
    out = lab.copy(); out[start:] = np.roll(lab[start:], k, axis=0); return out


def perm_placebo(lab, seed=0):
    return lab[:, np.random.default_rng(seed).permutation(lab.shape[1])]
