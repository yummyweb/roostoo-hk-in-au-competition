"""Causal cross-asset ranking, with horizon-purged training and fixed risk caps.

Models estimate future excess log returns across the available universe. Scores
rank assets; they are not calibrated price forecasts. Trading uses next opens.
"""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import math

MODEL_NAMES = {'momentum': 'Momentum ensemble', 'ridge_72': 'Ridge ranking · 72h',
               'boosted_24': 'Boosted trees · 24h', 'boosted_72': 'Boosted trees · 72h',
               'trend_budget': 'Diversified trend ensemble',
               'regime_adaptive': 'Regime-adaptive trend rotation'}
LOOKBACK = 720


def dependencies():
    try:
        import numpy as np
        import sklearn
    except ImportError as exc:
        raise RuntimeError('Cross-Asset Ranking needs scripts/setup-lstm.sh (NumPy and scikit-learn).') from exc
    return np, sklearn


def rolling_mean(x, window):
    np, _ = dependencies()
    cumulative = np.concatenate([np.zeros((1, x.shape[1])), np.cumsum(x, axis=0)], axis=0)
    index = np.arange(len(x)); start = np.maximum(0, index-window+1)
    return (cumulative[index+1]-cumulative[start])/(index-start+1)[:, None]


def market_features(bars):
    """Every row uses only prices/volume observed through that candle close."""
    np, _ = dependencies()
    pairs = sorted({b.pair for b in bars})
    grouped = {p: [] for p in pairs}
    for b in bars: grouped[b.pair].append(b)
    close = np.array([[b.close for b in grouped[p]] for p in pairs]).T
    opening = np.array([[b.open for b in grouped[p]] for p in pairs]).T
    volume = np.log1p(np.array([[b.volume for b in grouped[p]] for p in pairs]).T)
    dollar_volume = np.array([[b.volume*b.close for b in grouped[p]] for p in pairs]).T
    spread = np.array([[(b.high-b.low)/b.close for b in grouped[p]] for p in pairs]).T
    logs = np.log(close); changes = np.zeros_like(close); changes[1:] = np.diff(logs, axis=0)
    features = []; names = []; returns = {}
    for horizon in (6, 24, 72, 168, 336, 720):
        ret = logs-logs[np.maximum(0, np.arange(len(logs))-horizon)]
        returns[horizon] = ret
        market = ret.mean(axis=1, keepdims=True)
        features.extend([ret, ret-market, np.broadcast_to(market, ret.shape)])
        names.extend([f'log_return_{horizon}', f'excess_return_{horizon}', f'market_return_{horizon}'])
    variance = np.maximum(0, rolling_mean(changes**2, 168)-rolling_mean(changes, 168)**2)
    sigma = np.sqrt(variance)
    slow = rolling_mean(close, 168)
    features.extend([sigma, spread, volume-rolling_mean(volume, 168), close/slow-1,
                     changes, np.abs(returns[168])/np.maximum(rolling_mean(np.abs(changes),168)*168,1e-8)])
    names.extend(['volatility_168', 'range_fraction', 'relative_log_volume_168',
                  'mean_deviation_168', 'return_1', 'efficiency_168'])
    x = np.stack(features, axis=-1)
    return dict(pairs=pairs, timestamps=np.array([b.timestamp for b in grouped[pairs[0]]]),
                close=close, opening=opening, x=x, names=names, sigma=sigma, slow=slow, returns=returns,
                dollar_volume=dollar_volume)


def training_rows(length, train_end, horizon):
    # Labels end at OPEN(t+1+horizon), strictly before the training boundary.
    return list(range(LOOKBACK, min(train_end, length)-horizon-1, 6))


def fit_scores(market, model_name, train_end):
    np, sklearn = dependencies()
    if model_name not in MODEL_NAMES: raise ValueError('Unknown ranking model')
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from threadpoolctl import threadpool_limits
    x = market['x']; n, assets, dimensions = x.shape
    horizon = 24 if model_name == 'boosted_24' else 72
    indices = training_rows(n, train_end, horizon)
    if len(indices) < 100: raise ValueError('Cross-Asset Ranking requires at least 2,400 hourly candles per asset')
    model = None
    if model_name in ('momentum','trend_budget','regime_adaptive'):
        # Equal vote from distinct 3/7/14/30-day horizons, scaled by past risk.
        scores = sum(market['returns'][h]/math.sqrt(h) for h in (72,168,336,720))/4
        scores = scores/np.maximum(market['sigma'], .002)
    else:
        indices = np.array(indices)
        future = np.log(market['opening'][indices+1+horizon]/market['opening'][indices+1])
        target = np.clip(future-future.mean(axis=1,keepdims=True), -.30, .30)*100
        if model_name == 'ridge_72':
            model = make_pipeline(StandardScaler(), Ridge(alpha=1000))
        else:
            model = HistGradientBoostingRegressor(loss='squared_error', max_iter=120,
                max_leaf_nodes=7, learning_rate=.05, min_samples_leaf=100,
                l2_regularization=10, early_stopping=False, random_state=42)
        with threadpool_limits(limits=4):
            model.fit(x[indices].reshape(-1,dimensions), target.reshape(-1))
            scores = model.predict(x.reshape(-1,dimensions)).reshape(n,assets)/100
    digest = hashlib.sha256(np.asarray(scores[train_end:],dtype='<f8').tobytes()).hexdigest()
    metadata = dict(architecture=MODEL_NAMES[model_name], model_name=model_name,
        train_end_exclusive=int(market['timestamps'][train_end]),
        last_train_label_timestamp=int(market['timestamps'][int(indices[-1])+1+horizon]),
        train_samples=len(indices)*assets if model is not None else 0,
        forecast_horizon_bars=horizon if model is not None else None,
        feature_names=market['names'], prediction_sha256=digest,
        sklearn_version=sklearn.__version__,
        target='Cross-sectional excess log return, next open to horizon open; scores rank assets, not price targets',
        method='First 60% for fitting, horizon-purged labels. Architecture selected on two validation blocks in next 20%. Final 20% is previously explored evaluation history.')
    if model is None:
        metadata.update(train_end_exclusive=None,last_train_label_timestamp=None,
            target='Equal votes from trailing 72/168/336/720-hour returns; no fitted price forecast',
            method='Fixed causal trend rules, with architecture/risk selected on two validation blocks in the middle 20%. Final 20% is previously explored evaluation history.')
    return scores, metadata, model


def execution_features(market, scores):
    np, _ = dependencies()
    frames=[]
    for i in range(len(scores)):
        frame={}
        for j,p in enumerate(market['pairs']):
            frame[p]=dict(ready=i>=LOOKBACK, close=float(market['close'][i,j]),
                slow=float(market['slow'][i,j]), volatility=float(market['sigma'][i,j]),
                momentum=float(market['returns'][72][i,j]), rank_score=float(scores[i,j]),
                dollar_volume=float(np.mean(market['dollar_volume'][max(0,i-167):i+1,j])),
                trend_strength=sum(market['returns'][h][i,j]>0 for h in (72,168,336,720))/4)
        frames.append(frame)
    return frames


def ranking_targets(features, c, interval):
    if c.rank_model == 'regime_adaptive':
        ready = [f for f in features.values() if f.get('ready')]
        if not ready:
            return {}
        state = ready[0].get('market_regime', 'CHOP')
        if state not in ('BULL', 'RECOVERY') or ready[0].get('regime_age', 0) < c.regime_hold_bars:
            return {}
        candidates = []
        for pair, f in features.items():
            if not f.get('ready') or f.get('trend_strength', 0) < c.rank_min_trend_strength:
                continue
            if f.get('close', 0) <= f.get('slow', 0):
                continue
            move = f.get('momentum_168', 0) if state == 'BULL' else f.get('momentum_72', 0)
            if move < c.regime_min_move:
                continue
            candidates.append((pair, f))
        liquid = sorted(candidates, key=lambda row:(-row[1].get('dollar_volume', 0), row[0]))[:c.rank_liquidity_top_n]
        ranked = sorted(liquid, key=lambda row:(-row[1].get('setup_score', -1e9), row[0]))[:c.top_n]
        if not ranked:
            return {}
        sigmas = {p:max(.2, f['volatility']*math.sqrt(365*86400000/interval)) for p, f in ranked}
        inverses = sum(1/s for s in sigmas.values())
        raw = {p:min(c.max_position, c.max_exposure/s/inverses) for p, s in sigmas.items()}
        risk = sum(raw[p]*sigmas[p] for p in raw)
        target = c.target_volatility if state == 'BULL' else c.target_volatility*.5
        scale = min(1, target/risk) if risk else 0
        return {p:w*scale for p,w in raw.items() if w > 0}
    if c.rank_model=='trend_budget':
        # Independent trend votes allocate across the whole universe. Keep cash
        # for inactive assets instead of reallocating their budget to a few winners.
        # Apply the strength gate before inverse-volatility normalization. This
        # keeps excluded assets from diluting the risk budget of eligible ones.
        ranked_liquidity=sorted((p for p,f in features.items()
                                 if f['ready'] and f['trend_strength'] >= c.rank_min_trend_strength),
                                key=lambda p:(-features[p].get('dollar_volume',0.),p))[:c.rank_liquidity_top_n]
        sigmas={p:max(.2,features[p]['volatility']*math.sqrt(365*86400000/interval)) for p in ranked_liquidity}
        inverses=sum(1/s for s in sigmas.values())
        raw={p:min(c.max_position,c.max_exposure*features[p]['trend_strength']/s/inverses)
             for p,s in sigmas.items()
             if features[p]['ready']}
        risk=sum(raw[p]*sigmas[p] for p in raw)
        scale=min(1,c.target_volatility/risk) if risk else 0
        return {p:w*scale for p,w in raw.items() if w>0}
    # Positive absolute trend gate avoids buying relative winners in a falling market.
    eligible=[(p,f) for p,f in features.items() if f['ready'] and f['momentum']>0 and f['close']>f['slow']]
    ranked=sorted(eligible,key=lambda row:(-row[1]['rank_score'],row[0]))[:c.top_n]
    if not ranked: return {}
    sigmas={p:max(.2,f['volatility']*math.sqrt(365*86400000/interval)) for p,f in ranked}
    inverses=sum(1/s for s in sigmas.values())
    raw={p:min(c.max_position,c.max_exposure/s/inverses) for p,s in sigmas.items()}
    risk=sum(raw[p]*s for p,s in sigmas.items())
    factor=min(1,c.target_volatility/risk) if risk else 0
    return {p:w*factor for p,w in raw.items()}


def validate_input(bars,c,manifest):
    from .data import validate_bars
    c.validate()
    if validate_bars(bars)!=3600000: raise ValueError('Cross-Asset Ranking requires hourly candles')
    if manifest.get('synthetic'): raise ValueError('Choose historical hourly CSV data for Cross-Asset Ranking')
    if c.allow_short: raise ValueError('Cross-Asset Ranking uses long-only partial allocation')
    count=len({b.pair for b in bars})
    if count<2 or len(bars)//count<2400: raise ValueError('Cross-Asset Ranking requires at least 2 assets and 2,400 hourly candles each')


def replay(bars,c,manifest,rules,features,start,end=None,metadata=None):
    from .allocation import run_allocation
    # Features may be built on a wider discovery universe than the execution
    # bars. Slice by the bars' synchronized pair count so filtered execution
    # universes retain the same hourly timeline.
    pairs=len({b.pair for b in bars}); end=end or len(features)
    # Features already contain prehistory. Replay only the evaluation slice.
    r=run_allocation(bars[start*pairs:end*pairs],c,manifest,rules,precomputed=features[start:end])
    r['name']='Cross-Asset Ranking / '+MODEL_NAMES[c.rank_model]
    if metadata: r['ranking_model']=metadata
    r['warnings'].insert(0,'Exploratory evaluation on previously inspected history; not a fresh research holdout.')
    return r


def run_ranking(bars,c,manifest,rules):
    validate_input(bars,c,manifest)
    market=market_features(bars);n=len(market['timestamps'])
    scores,metadata,_=fit_scores(market,c.rank_model,int(n*.6))
    metadata['selection_role']='Supplied research preset; this replay does not select an architecture on the imported dataset.'
    if c.rank_model == 'regime_adaptive':
        from .regime import regime_features
        features=regime_features(market,scores)
        metadata.update(target='Causal broad-market regime and trailing trend gates; scores rank eligible assets',
            method='Fixed causal regime rules using trailing 72/168/336/720-hour returns, breadth, liquidity and volatility. No fitted future-return labels are used; historical evaluation is exploratory.')
    else:
        features=execution_features(market,scores)
    result=replay(bars,c,manifest,rules,features,int(n*.8),metadata=metadata)
    stress=replay(bars,replace(c,fee_bps=20,spread_bps=10,slippage_bps=10),manifest,rules,features,int(n*.8))
    result['ranking_model']['cost_stress_metrics']=stress['metrics']
    return result
