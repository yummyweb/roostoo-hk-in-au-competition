"""Trend-vs-chop features and causal labels. Everything here is a pure function of the panel it is given."""
import sys, os
LAB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if LAB not in sys.path: sys.path.insert(0, LAB)
import numpy as np
import ind, regime


def _rcorr(a, b, n):
    """Rolling correlation of two (T,N) series over n bars (causal)."""
    ma, mb = ind.sma(a, n), ind.sma(b, n)
    cov = ind.sma(a * b, n) - ma * mb
    va = ind.sma(a * a, n) - ma * ma; vb = ind.sma(b * b, n) - mb * mb
    den = np.sqrt(np.maximum(va, 0) * np.maximum(vb, 0))
    return cov / np.where(den > 0, den, np.nan)


def _lag(x, k):
    out = np.full(x.shape, np.nan); out[k:] = x[:-k]; return out


def features(P):
    """dict name -> (T,N). All causal."""
    C, H, L = P.C, P.H, P.L
    f = {}
    for n in (24, 72, 168): f[f'er{n}'] = ind.efficiency_ratio(C, n)
    e9, e21, e24, e100 = (ind.ema(C, n) for n in (9, 21, 24, 100))
    f['cc9_72'] = ind.cross_count(e9, e21, 72); f['cc9_168'] = ind.cross_count(e9, e21, 168)
    f['cc24_72'] = ind.cross_count(e24, e100, 72); f['cc24_168'] = ind.cross_count(e24, e100, 168)
    atr = ind.atr(H, L, C, 24)
    f['gap'] = (e24 - e100) / atr                      # signed
    f['gapabs'] = np.abs(f['gap'])
    r1 = ind.logret(C, 1); r24 = ind.logret(C, 24); r6 = ind.logret(C, 6)
    v1 = ind.rstd(r1, 168) ** 2; v24 = ind.rstd(r24, 168) ** 2
    f['vr'] = v24 / np.where(v1 > 0, 24 * v1, np.nan)  # >1 trending, <1 mean-reverting
    f['ac1'] = _rcorr(r1, _lag(r1, 1), 168)
    f['ac6'] = _rcorr(r6, _lag(r6, 6), 336)
    rv24, rv168, rv720 = (ind.rstd(r1, n) for n in (24, 168, 720))
    f['dvol'] = np.log(np.where(rv24 > 0, rv24, np.nan) / np.where(rv168 > 0, rv168, np.nan))   # volatility change
    f['lvol'] = np.log(np.where(rv168 > 0, rv168, np.nan))                                       # level (log hourly sd)
    hi, lo = ind.rmax(H, 168), ind.rmin(L, 168)
    f['dhi'] = (hi - C) / atr; f['dlo'] = (C - lo) / atr
    rng = np.where(hi > lo, hi - lo, np.nan)
    f['pos'] = (C - lo) / rng                          # 0 = at the 7-day low, 1 = at the high
    f['edge'] = np.abs(2 * f['pos'] - 1)
    f['ema_sign'] = np.sign(e24 - e100)
    f['z48'] = ind.zscore(C, 48)
    return f


SETS = {
    'core4': ['er72', 'er168', 'cc24_168', 'gapabs'],
    'agn8': ['er72', 'er168', 'cc24_168', 'gapabs', 'vr', 'ac1', 'ac6', 'edge'],
    'agn10v': ['er72', 'er168', 'cc24_168', 'gapabs', 'vr', 'ac1', 'ac6', 'edge', 'dvol', 'lvol'],
    'dir3': ['gap', 'er72', 'pos'],
    'all15': ['er72', 'er24', 'er168', 'cc9_72', 'cc9_168', 'cc24_72', 'cc24_168', 'gapabs', 'vr', 'ac1', 'ac6',
              'lvol', 'dvol', 'dhi', 'dlo'],
}


def stack(f, names):
    return np.stack([f[n] for n in names], -1)


def kmeans_labels(P, set_name='core4', K=2, use_hmm=False, first_train=1000, step=336, f=None):
    """Causal walk-forward labels 0..K-1 ordered by the first feature of the set (-1 = unknown)."""
    f = features(P) if f is None else f
    X = stack(f, SETS[set_name])
    lab, probs, models = regime.walk_forward(X, first_train=first_train, step=step, K=K, order_by=0, use_hmm=use_hmm, iters=40)
    return lab


def threshold_labels(x, q=.5, win=720, minp=336):
    """Non-ML baseline: 1 where the feature is above its own trailing cross-coin pooled quantile, else 0 (-1 unknown).

    The cut-off at row t is the q-quantile of all coins' values in rows [t-win, t-1], recomputed every 24 bars.
    """
    T, N = x.shape; lab = np.full((T, N), -1)
    cut = np.nan
    for t in range(T):
        if t % 24 == 0 and t >= minp:
            w = x[max(0, t - win):t]; w = w[np.isfinite(w)]
            cut = np.quantile(w, q) if len(w) > 500 else np.nan
        if np.isfinite(cut):
            ok = np.isfinite(x[t]); lab[t, ok] = (x[t, ok] > cut)
    return lab


def fixed_labels(x, thr):
    lab = np.full(x.shape, -1); ok = np.isfinite(x); lab[ok] = x[ok] > thr; return lab


def shift_placebo(lab, k=1000):
    """Same labels k bars late: same frequency and persistence, no information about now."""
    out = np.full(lab.shape, -1); out[k:] = lab[:-k]; return out


def perm_placebo(lab, seed=0):
    """Each coin gets another coin's label path: keeps market-wide timing, removes coin-specific information."""
    rng = np.random.default_rng(seed); N = lab.shape[1]
    while True:
        p = rng.permutation(N)
        if not (p == np.arange(N)).any(): break
    return lab[:, p]


def runs(mask):
    """Mean run length (bars) of True runs, per-column pooled."""
    m = mask.astype(int); d = np.diff(np.vstack([np.zeros((1, m.shape[1]), int), m, np.zeros((1, m.shape[1]), int)]), axis=0)
    starts = (d == 1).sum(); return m.sum() / max(1, starts)
