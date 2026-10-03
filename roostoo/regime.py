"""Causal market-regime features for the profit-first cross-asset strategy."""


def regime_features(market, scores):
    """Build per-asset frames with delayed, broad-regime state.

    Every value is calculated from candles through the current close. The
    classifier intentionally has a cash state: the long-only strategy trades
    only after broad participation confirms a directional market.
    """
    np = __import__('numpy')
    returns = market['returns']
    horizons = (72, 168, 336, 720)
    breadth = {h: np.mean(returns[h] > 0, axis=1) for h in horizons}
    basket = {h: np.mean(returns[h], axis=1) for h in horizons}
    sigma = np.median(market['sigma'], axis=1)
    raw = []
    for i in range(len(scores)):
        if breadth[72][i] >= .62 and breadth[168][i] >= .55 and breadth[336][i] >= .50 and basket[168][i] > 0:
            state = 'BULL'
        elif breadth[72][i] >= .52 and basket[72][i] > 0 and basket[168][i] < 0:
            state = 'RECOVERY'
        elif breadth[72][i] <= .38 and breadth[168][i] <= .45 and basket[168][i] < 0:
            state = 'BEAR'
        else:
            state = 'CHOP'
        raw.append(state)
    age = 0; previous = None; ages = []
    for state in raw:
        age = age + 1 if state == previous else 1
        ages.append(age)
        previous = state
    frames = []
    npairs = len(market['pairs'])
    for i in range(len(scores)):
        frame = {}
        state = raw[i]
        for j, pair in enumerate(market['pairs']):
            momentum_72 = float(returns[72][i, j]); momentum_168 = float(returns[168][i, j])
            # Require a meaningful move before fees. This is a ranking feature,
            # not a future return label.
            setup = (momentum_168 if state == 'BULL' else momentum_72) / max(float(market['sigma'][i, j]), .002)
            frame[pair] = dict(ready=i >= 720, close=float(market['close'][i, j]),
                slow=float(market['slow'][i, j]), volatility=float(market['sigma'][i, j]),
                momentum=momentum_72, momentum_72=momentum_72, momentum_168=momentum_168,
                rank_score=float(scores[i, j]), setup_score=setup,
                dollar_volume=float(np.mean(market['dollar_volume'][max(0, i-167):i+1, j])),
                trend_strength=sum(returns[h][i, j] > 0 for h in horizons) / len(horizons),
                market_regime=state, regime_age=ages[i], market_breadth_72=float(breadth[72][i]),
                market_breadth_168=float(breadth[168][i]), market_return_72=float(basket[72][i]),
                market_return_168=float(basket[168][i]), market_sigma=float(sigma[i]))
        frames.append(frame)
    return frames
