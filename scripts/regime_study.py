#!/usr/bin/env python3
"""Evaluate profit-first, low-turnover regime-adaptive portfolios."""
import argparse, json, sys
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roostoo.data import read_csv
from roostoo.ranking import fit_scores, market_features, replay
from roostoo.regime import regime_features
from roostoo.rules import PairRule
from roostoo.strategy import Config


def rules_for(bars):
    info=json.loads(Path('config/exchange_info.json').read_text()).get('TradePairs', {})
    pairs=sorted({b.pair for b in bars})
    missing=[p for p in pairs if p not in info or not info[p].get('CanTrade',False)]
    if missing:
        raise ValueError(f'Execution universe contains pairs without current Roostoo rules: {missing[:5]}')
    return {p:PairRule(int(info[p]['AmountPrecision']),int(info[p]['PricePrecision']),
                       float(info[p]['MiniOrder']),bool(info[p]['CanTrade'])) for p in pairs}


def pick(m):
    return {k:m[k] for k in ('total_return','max_drawdown','sharpe','sortino','calmar','fills','closed_trades','active_days','average_exposure','turnover')}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--data',default='data/binance-broad-1h.csv'); parser.add_argument('--output',default='runs/regime-study'); args=parser.parse_args()
    data=args.data; out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    bars,manifest=read_csv(data)
    # Use the broad Binance universe to classify market regimes, while
    # restricting simulated orders to currently tradable Roostoo crypto pairs.
    info=json.loads(Path('config/exchange_info.json').read_text()).get('TradePairs', {})
    tradeable=sorted(p for p in {b.pair for b in bars}
                     if p in info and info[p].get('CanTrade') and info[p].get('AssetType')=='crypto')
    if len(tradeable)<2:
        raise ValueError('Regime study needs at least two current Roostoo crypto pairs')
    tradeable_set=set(tradeable)
    execution_bars=[b for b in bars if b.pair in tradeable_set]
    rules=rules_for(execution_bars)
    market=market_features(bars); n=len(market['timestamps']); scores,_,_=fit_scores(market,'regime_adaptive',int(n*.6)); broad_features=regime_features(market,scores)
    features=[{p:f[p] for p in tradeable} for f in broad_features]
    blocks=[('b1',720,2160),('b2',2160,3600),('b3',3600,5040),('b4',5040,6480),('tail',6480,n)]
    candidates={
      'regime_profit_v55_top5':Config(strategy='cross_asset',rank_model='regime_adaptive',target_volatility=.55,max_exposure=.8,max_position=.25,top_n=5,rank_liquidity_top_n=50,rank_min_trend_strength=.5,regime_min_move=.03,regime_hold_bars=24,rebalance_bars=48,rebalance_band=.05),
      'regime_profit_v80_top3':Config(strategy='cross_asset',rank_model='regime_adaptive',target_volatility=.8,max_exposure=.8,max_position=.30,top_n=3,rank_liquidity_top_n=50,rank_min_trend_strength=.5,regime_min_move=.05,regime_hold_bars=24,rebalance_bars=72,rebalance_band=.05),
      'regime_profit_v40_top8':Config(strategy='cross_asset',rank_model='regime_adaptive',target_volatility=.4,max_exposure=.8,max_position=.20,top_n=8,rank_liquidity_top_n=75,rank_min_trend_strength=.5,regime_min_move=.03,regime_hold_bars=24,rebalance_bars=48,rebalance_band=.05),
    }
    results=[]
    for name,c in candidates.items():
        row={'name':name,'config':c.__dict__,'blocks':{}}
        for label,start,end in blocks:
            b=replay(execution_bars,c,manifest,rules,features,start,end)['metrics']; s=replay(execution_bars,replace(c,fee_bps=20,spread_bps=10,slippage_bps=10),manifest,rules,features,start,end)['metrics']
            row['blocks'][label]={'base':pick(b),'stress':pick(s)}; print(json.dumps({'candidate':name,'block':label,'return':b['total_return'],'stress':s['total_return'],'fills':b['fills']}),flush=True)
        vals=[x['base']['total_return'] for x in row['blocks'].values()]; stress=[x['stress']['total_return'] for x in row['blocks'].values()]
        avg=lambda key: sum(x['base'][key] for x in row['blocks'].values() if x['base'][key] is not None) / max(1,sum(x['base'][key] is not None for x in row['blocks'].values()))
        row['summary']={'mean_return':sum(vals)/len(vals),'median_return':sorted(vals)[len(vals)//2],'mean_stress_return':sum(stress)/len(stress),'worst_return':min(vals),'positive_blocks':sum(x>0 for x in vals),'mean_sharpe':avg('sharpe'),'mean_sortino':avg('sortino'),'mean_calmar':avg('calmar'),'mean_fills':sum(x['base']['fills'] for x in row['blocks'].values())/len(vals)}
        results.append(row)
    (out/'results.json').write_text(json.dumps({'data':data,'asset_count':len(market['pairs']),'execution_asset_count':len(tradeable),'execution_assets':tradeable,'timestamps':n,'blocks':blocks,'results':results,'selection':'Choose only on b1-b4; tail remains report-only.','warnings':['Regimes use the broad Binance discovery universe; orders are restricted to current Roostoo crypto pairs with exchange rules.','Historical listing and survivorship bias remain; higher target volatility is exploratory.']},indent=2,allow_nan=False))


if __name__=='__main__': main()
