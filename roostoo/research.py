"""Chronological selection on training only, a validation block, untouched holdout.

Small candidate set avoids large hyperparameter fishing. Validation and holdout
have separate fresh wallets; warmup bars cannot trade or enter their metrics.
"""
from dataclasses import replace
from itertools import groupby
from .engine import run
from .strategy import Config


def evaluate(bars, manifest, rules):
    timestamps=list(dict.fromkeys(b.timestamp for b in bars))
    n=len(timestamps)
    if n<1000:
        raise ValueError('Research needs at least 1,000 candles per pair')
    cut1,cut2=int(n*.6),int(n*.8)
    train=[b for b in bars if b.timestamp<timestamps[cut1]]
    validation=[b for b in bars if timestamps[cut1-128]<=b.timestamp<timestamps[cut2]]
    holdout=[b for b in bars if b.timestamp>=timestamps[cut2-128]]
    candidates=[Config(),Config(fast=24,slow=96),Config(strategy='hybrid'),Config(allow_short=True)]
    leaderboard=[]
    for c in candidates:
        result=run(train,c,manifest,rules)
        m=result['metrics']
        # No unstable annualized Calmar in selection. Penalize drawdowns and fee churn.
        score=m['total_return']-2*m['max_drawdown']-m['fees']/c.initial_cash
        leaderboard.append({'config':result['config'],'metrics':m,'selection_score':score})
    leaderboard.sort(key=lambda x:x['selection_score'],reverse=True)
    chosen=Config(**leaderboard[0]['config'])
    valid=run(validation,chosen,manifest,rules,start_index=128)
    final=run(holdout,chosen,manifest,rules,start_index=128)
    stress=run(holdout,replace(chosen,fee_bps=20,spread_bps=10,slippage_bps=10),manifest,rules,start_index=128)
    cash=run(holdout,replace(chosen,strategy='cash'),manifest,rules,start_index=128)
    # Same engine, same caps and cadence. Also expose passive full-allocation chart benchmark.
    hold=run(holdout,replace(chosen,strategy='buy_hold',allow_short=False),manifest,rules,start_index=128)
    summary={'method':'60% train / 20% validation / 20% untouched holdout; 128 prior candles warm indicators',
             'selection':'Training return - 2 * max drawdown - fees / starting equity; candidate list fixed in code',
             'training_candidates':leaderboard,'selected_config':final['config'],
             'validation':valid['metrics'],'holdout':final['metrics'],'cost_stress':stress['metrics'],
             'cash_baseline':cash['metrics'],'capped_buy_hold_baseline':hold['metrics'],
             'passive_basket_return':final['equity_curve'][-1]['benchmark']/chosen.initial_cash-1,
             'holdout_start':timestamps[cut2], 'data_manifest':manifest,
             'decision':'Research only: require positive holdout and stress returns, stable subperiods, then paper execution validation.'}
    return summary,final
