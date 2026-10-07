"""K-Means-initialised Gaussian HMM (Haryani, Chandra, Tarigan 2026) for many assets at once.

One model is shared across assets: X is (T, N, d), each asset is an independent chain.
Use walk_forward() to get labels that never see the future.
"""
import numpy as np
from sklearn.cluster import KMeans


def _logpdf(X, mu, cov):
    d = X.shape[-1]; out = np.empty(X.shape[:-1] + (len(mu),))
    for k in range(len(mu)):
        L = np.linalg.cholesky(cov[k]); z = np.linalg.solve(L, (X.reshape(-1, d) - mu[k]).T)
        out[..., k] = (-.5 * (z * z).sum(0) - np.log(np.diag(L)).sum() - .5 * d * np.log(2 * np.pi)).reshape(X.shape[:-1])
    return out


def forward(X, model):
    """Filtered P(state_t | observations up to t) for each chain: (T, N, K). Rows with NaN features keep the prior."""
    T, N, _ = X.shape; A, pi = model['A'], model['pi']; K = len(pi)
    ok = np.isfinite(X).all(-1); lb = _logpdf(np.where(ok[..., None], X, 0.), model['mu'], model['cov'])
    B = np.exp(lb - lb.max(-1, keepdims=True)); B[~ok] = 1.
    al = np.empty((T, N, K)); a = pi * B[0]; al[0] = a / a.sum(-1, keepdims=True)
    for t in range(1, T):
        a = (al[t - 1] @ A) * B[t]; al[t] = a / a.sum(-1, keepdims=True)
    return al


def fit(X, K=3, iters=150, seed=0, kmeans_init=True, init=None):
    """Baum-Welch on pooled chains. X: (T, N, d), finite everywhere. Returns dict(mu, cov, A, pi, ll, iters, converged).

    Starts from K-Means clusters (the paper's method), from random labels, or from an earlier model passed as `init`.
    iters=0 returns the K-Means initialisation itself (cluster means, covariances and label transition counts).
    """
    T, N, d = X.shape; flat = X.reshape(-1, d); rng = np.random.default_rng(seed)
    if init is not None:
        lab = None
    elif kmeans_init:
        km = KMeans(K, n_init=5, random_state=seed).fit(flat[rng.choice(len(flat), min(len(flat), 200_000), replace=False)])
        lab = km.predict(flat).reshape(T, N)
    else:
        lab = rng.integers(0, K, (T, N))
    if init is not None:
        mu, cov, A, pi = (np.array(init[k], float) for k in ('mu', 'cov', 'A', 'pi'))
    else:
        mu = np.array([flat[lab.ravel() == k].mean(0) for k in range(K)])
        cov = np.array([np.cov(flat[lab.ravel() == k].T) + 1e-4 * np.eye(d) for k in range(K)])
        A = np.ones((K, K)); np.add.at(A, (lab[:-1].ravel(), lab[1:].ravel()), 1); A /= A.sum(1, keepdims=True)
        pi = np.bincount(lab[0], minlength=K) / N + 1e-6; pi /= pi.sum()
    prev = -np.inf; ll = prev; done = 0; converged = iters == 0
    for done in range(1, iters + 1):
        lb = _logpdf(X, mu, cov); peak = lb.max(-1, keepdims=True); B = np.exp(lb - peak)
        al = np.empty((T, N, K)); c = np.empty((T, N)); a = pi * B[0]; c[0] = a.sum(-1); al[0] = a / c[0][:, None]
        for t in range(1, T):
            a = (al[t - 1] @ A) * B[t]; c[t] = a.sum(-1); al[t] = a / c[t][:, None]
        ll = float(np.log(c).sum() + peak.sum())
        be = np.empty((T, N, K)); be[-1] = 1; xi = np.zeros((K, K))
        for t in range(T - 2, -1, -1):
            w = B[t + 1] * be[t + 1]; be[t] = (w @ A.T) / c[t + 1][:, None]
            xi += np.einsum('ni,ij,nj->ij', al[t], A, w / c[t + 1][:, None])
        g = al * be; g /= g.sum(-1, keepdims=True); gf = g.reshape(-1, K); w = gf.sum(0)
        A = xi / xi.sum(1, keepdims=True); pi = g[0].mean(0); mu = (gf.T @ flat) / w[:, None]
        cov = np.array([((flat - mu[k]).T * gf[:, k]) @ (flat - mu[k]) / w[k] + 1e-4 * np.eye(d) for k in range(K)])
        if ll - prev < 1e-6 * abs(ll): converged = True; break
        prev = ll
    return dict(mu=mu, cov=cov, A=A, pi=pi, ll=ll, iters=done, converged=converged)


def walk_forward(X, first_train=3000, step=720, K=3, order_by=0, iters=150, seed=0, use_hmm=True):
    """Causal labels. X: (T, N, d) raw features (NaN allowed during warm-up).

    Every `step` bars, standardize with the mean/std of the data seen so far, fit on it, then label the next
    `step` bars with the forward filter (or the nearest K-Means centroid if use_hmm=False). The first fit starts from
    K-Means; later refits start from the previous model so they converge quickly. States are renumbered
    0..K-1 by their mean of feature `order_by` in the training data. Returns (labels (T,N) int, -1 where unknown;
    probabilities (T,N,K); list of fitted models).
    """
    T, N, d = X.shape; ok = np.isfinite(X).all(-1); first = int(np.argmax(ok.all(1)))
    labels = np.full((T, N), -1); probs = np.zeros((T, N, K)); models = []; last = None
    for end in range(first + first_train, T, step):
        tr = X[first:end]; mean = tr.reshape(-1, d).mean(0); sd = tr.reshape(-1, d).std(0); Z = (X[first:min(T, end + step)] - mean) / sd
        m = fit(Z[:end - first], K, iters if use_hmm else 0, seed, init=last if use_hmm else None); last = m if use_hmm else None; order = np.argsort(m['mu'][:, order_by]); rank = np.empty(K, int); rank[order] = np.arange(K)
        if use_hmm:
            al = forward(Z, m)[end - first:]
        else:
            dist = ((Z[end - first:, :, None, :] - m['mu'][None, None]) ** 2).sum(-1); al = np.eye(K)[dist.argmin(-1)]
        hi = min(T, end + step); labels[end:hi] = rank[al.argmax(-1)]; probs[end:hi] = al[..., order]
        models.append(dict(end=end, mean=mean, sd=sd, order=order, **m))
    return labels, probs, models
