"""Task (d): pure-Python forward filter from coin_regime.json, checked against the lab's filtered labels.

regime_labels(closes, model) is the function to port to the bot: no NumPy, only `math`.
"""
import json, math, os, sys


def regime_labels(closes, model):
    """closes: one coin's hourly closes, oldest first. model: the dict in coin_regime.json.
    Returns one label per close: 'BULL', 'BEAR', 'CHOP', or None while there is too little history for the features."""
    R, V = model['return_bars'], model['vol_bars']; fm, fs = model['feature_mean'], model['feature_std']
    A, mu = model['transition'], model['means']; K = len(mu)
    name = {model['bull_state']: 'BULL', model['bear_state']: 'BEAR', model['chop_state']: 'CHOP'}
    inv = []                                                    # per state: inverse covariance (a, b, c) and log-determinant
    for (s00, s01), (_, s11) in model['covariances']:
        det = s00 * s11 - s01 * s01; inv.append((s11 / det, -s01 / det, s00 / det, math.log(det)))
    lr = [0.] + [math.log(closes[t] / closes[t - 1]) for t in range(1, len(closes))]
    out = []; alpha = None
    for t in range(len(closes)):
        if t < max(R, V): out.append(None); continue
        w = lr[t - V + 1:t + 1]; m = sum(w) / V
        z0 = (math.log(closes[t] / closes[t - R]) - fm[0]) / fs[0]
        z1 = (math.sqrt(sum((x - m) ** 2 for x in w) / V) - fm[1]) / fs[1]
        lb = []
        for k in range(K):
            d0, d1 = z0 - mu[k][0], z1 - mu[k][1]; a, b, c, logdet = inv[k]
            lb.append(-.5 * (a * d0 * d0 + 2 * b * d0 * d1 + c * d1 * d1) - .5 * logdet - math.log(2 * math.pi))
        top = max(lb); B = [math.exp(x - top) for x in lb]
        prior = model['start'] if alpha is None else [sum(alpha[j] * A[j][k] for j in range(K)) for k in range(K)]
        alpha = [prior[k] * B[k] for k in range(K)]; tot = sum(alpha); alpha = [x / tot for x in alpha]
        out.append(name[max(range(K), key=lambda k: alpha[k])])
    return out


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
    import numpy as np
    import live_fit                                              # puts the lab on sys.path
    import harness as h, regime
    model = json.load(open(os.path.join(HERE, 'coin_regime.json'))); P = h.load('full')
    m = dict(mu=np.array(model['means']), cov=np.array(model['covariances']), A=np.array(model['transition']), pi=np.array(model['start']))
    X = live_fit.tf.features(P, model['return_bars'], model['vol_bars']); first = max(model['return_bars'], model['vol_bars'])
    Z = (X[first:] - np.array(model['feature_mean'])) / np.array(model['feature_std'])
    lab = regime.forward(Z, m).argmax(-1)                        # the lab's filtered labels, rows first..T-1
    name = np.array(['', '', ''], dtype=object)
    name[model['bull_state']] = 'BULL'; name[model['bear_state']] = 'BEAR'; name[model['chop_state']] = 'CHOP'
    small = P.pairs[int(np.argmax(P.hs))]                        # the pair with the widest spread
    for pair in ('BTC/USD', small):
        i = P.i(pair); want = list(name[lab[-500:, i]])
        got = regime_labels([float(x) for x in P.C[:, i]], model)[-500:]
        cold = regime_labels([float(x) for x in P.C[-1200:, i]], model)[-500:]     # only the last 1,200 closes, started from `start`
        agree = lambda a: sum(x == y for x, y in zip(a, want)) / 500
        print(f"{pair}: last 500 hours, pure-Python filter vs lab labels: agreement {agree(got):.1%} with the full history, "
              f"{agree(cold):.1%} from the last 1,200 closes only | lab labels BULL {want.count('BULL')} BEAR {want.count('BEAR')} CHOP {want.count('CHOP')}")
