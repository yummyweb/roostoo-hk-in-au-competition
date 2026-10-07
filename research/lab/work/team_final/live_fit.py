"""Task (d): fit the regime model once on ALL rows of the full panel and write coin_regime.json for live use."""
import os, sys, json, datetime
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tf, candidate_1
import harness as h, regime

HERE = os.path.dirname(os.path.abspath(__file__))


def fit_full(P, R, V):
    """Standardise every coin-hour with finite features with its own mean/sd, fit K-Means -> 3-state Gaussian HMM.
    Returns (Z, first, mean, sd, model): Z is (T - first, N, 2), `first` the first row with finite features."""
    X = tf.features(P, R, V); first = max(R, V); assert np.isfinite(X[first:]).all() and not np.isfinite(X[:first]).all(-1).any()
    flat = X[first:].reshape(-1, 2); mean = flat.mean(0); sd = flat.std(0); Z = (X[first:] - mean) / sd
    return Z, first, mean, sd, regime.fit(Z, K=3)


if __name__ == '__main__':
    R, V = candidate_1.R, candidate_1.V; P = h.load('full')
    Z, first, mean, sd, m = fit_full(P, R, V); order = np.argsort(m['mu'][:, 0])     # by mean return feature, lowest first
    iso = lambda ms: datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    out = dict(return_bars=R, vol_bars=V, feature_mean=mean.tolist(), feature_std=sd.tolist(),
               means=m['mu'].tolist(), covariances=m['cov'].tolist(), transition=m['A'].tolist(), start=m['pi'].tolist(),
               bull_state=int(order[2]), bear_state=int(order[0]), chop_state=int(order[1]),
               log_likelihood=m['ll'], first_timestamp_ms=int(P.ts[0]), last_timestamp_ms=int(P.ts[-1]),
               first_timestamp=iso(P.ts[0]), last_timestamp=iso(P.ts[-1]),
               notes=dict(features='x0 = ln(close[t] / close[t - return_bars]); x1 = population std of the last vol_bars 1-hour log returns; '
                                   'z = (x - feature_mean) / feature_std; means and covariances are in z units',
                          filter='alpha[t] ~ (alpha[t-1] @ transition) * N(z[t]; means[k], covariances[k]); alpha at the first row = start * N(...); label = argmax',
                          timestamps='candle open times, UTC', rows=int(P.T), pairs=int(P.N), coin_hours=int(Z.shape[0] * Z.shape[1]),
                          em_iterations=int(m['iters']), converged=bool(m['converged'])))
    json.dump(out, open(os.path.join(HERE, 'coin_regime.json'), 'w'), indent=1)
    al = regime.forward(Z, m).argmax(-1); raw = m['mu'] * sd + mean
    for name, k in (('BEAR', order[0]), ('CHOP', order[1]), ('BULL', order[2])):
        print(f"{name}: state {k}, mean {R}h log return {raw[k, 0]:+.4f}, mean {V}h hourly vol {raw[k, 1]:.4f}, share of coin-hours (filtered, in-sample) {np.mean(al == k):.1%}, "
              f"P(stay) {m['A'][k, k]:.4f}")
    print('log likelihood', m['ll'], 'iterations', m['iters'], 'converged', m['converged'])
