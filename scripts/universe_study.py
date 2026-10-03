#!/usr/bin/env python3
"""Competition-horizon research across twelve predefined liquid assets.

Precompute features causally once per model; never rank configs on the later group.
Later group is reused historical data, explicitly exploratory after the first study.
"""
from dataclasses import asdict,replace
from itertools import groupby
from pathlib import Path
import json
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roostoo.data import read_csv
from roostoo.engine import run
from roostoo.strategy import Config,Indicators
from roostoo.cli import get_rules
from roostoo.report import save_run


def summary(rows):
    ms=[r['metrics'] for r in rows]; rets=[m['total_return'] for m in ms]
    return {'episodes':len(ms),'mean_return':statistics.mean(rets),'median_return':statistics.median(rets),
            'worst_return':min(rets),'profitable_fraction':sum(r>0 for r in rets)/len(rets),
            'mean_max_drawdown':statistics.mean(m['max_drawdown'] for m in ms),
            'median_active_days':statistics.median(m['active_days'] for m in ms),
            'eight_active_days_fraction':sum(m['active_days']>=8 for m in ms)/len(ms),
            'mean_fees':statistics.mean(m['fees'] for m in ms)}


def main(configs=None, folder_name='runs/universe-study'):
    bars,manifest=read_csv('data/universe-1h.csv'); rules=get_rules(bars)
    pairs=len(rules); n=len(bars)//pairs; horizon=14*24; warmup=3*336
    common=dict(max_hold_bars=168,stop_atr=6,cooldown_bars=12)
    configs=configs or [Config(strategy='trend',**common),Config(strategy='trend',allow_short=True,**common),
             Config(strategy='pullback',**common),
             Config(strategy='reversion',stop_atr=4,max_hold_bars=24,cooldown_bars=6),
             Config(strategy='reversion',stop_atr=4,max_hold_bars=24,cooldown_bars=6,allow_short=True),
             Config(strategy='rotation',fast=24,slow=168,momentum=72,stop_atr=8,cooldown_bars=24,top_n=3),
             Config(strategy='rotation',fast=24,slow=168,momentum=72,stop_atr=8,cooldown_bars=24,top_n=3,allow_short=True),
             Config(strategy='rotation',fast=48,slow=336,momentum=168,stop_atr=10,cooldown_bars=24,top_n=3),
             Config(strategy='rotation',fast=48,slow=336,momentum=168,stop_atr=10,cooldown_bars=24,top_n=3,allow_short=True)]
    starts=list(range(warmup,n-horizon+1,horizon))
    first=int(len(starts)*.6);second=int(len(starts)*.8)
    def precompute(c):
        states={p:Indicators(c) for p in rules}
        return [{b.pair:states[b.pair].update(b) for b in group} for t,group in groupby(bars,key=lambda b:b.timestamp)]
    def evaluate(c,indices,features):
        output=[]
        for start in indices:
            r=run(bars[start*pairs:(start+horizon)*pairs],c,manifest,rules,precomputed=features[start:start+horizon])
            output.append({'start':r['evaluation_start'],'end':r['evaluation_end'],'metrics':r['metrics'],
                           'passive_return':r['equity_curve'][-1]['benchmark']/c.initial_cash-1})
        return output
    candidates=[]; feature_key=None;features=None
    for c in configs:
        key=(c.fast,c.slow,c.momentum)
        if key!=feature_key:features=precompute(c);feature_key=key
        rows=evaluate(c,starts[:first],features); s=summary(rows)
        # Strict activity gate on training; no token trades manufactured to satisfy it.
        eligible=s['eight_active_days_fraction']>=.8 and s['mean_return']>0
        score=s['mean_return']-.5*s['mean_max_drawdown']
        candidates.append({'config':asdict(c),'train':s,'activity_eligible':eligible,'selection_score':score,'training_episodes':rows})
        print(c.strategy,c.momentum,c.allow_short,s,flush=True)
    eligible=[c for c in candidates if c['activity_eligible']]
    chosen=max(eligible or candidates,key=lambda c:c['selection_score']);config=Config(**chosen['config']);features=precompute(config)
    validation=evaluate(config,starts[first:second],features);later=evaluate(config,starts[second:],features)
    stress=evaluate(replace(config,fee_bps=20,spread_bps=10,slippage_bps=10),starts[second:],features)
    result={'method':'Independent non-overlapping 14-day episodes, flat starting wallet; 60/20/20 chronological groups; features have causal prehistory',
            'caveat':'Exploratory follow-up on previously exposed history. No fresh untouched holdout claim.',
            'manifest':manifest,'candidates':candidates,'selected_config':asdict(config),'selection_activity_gate_met':bool(eligible),
            'validation':summary(validation),'later_period':summary(later),'stress':summary(stress),
            'validation_episodes':validation,'later_episodes':later,
            'readiness':'PAPER ONLY pending prospective results, account capability validation, and operational checks.'}
    folder=Path(folder_name);folder.mkdir(parents=True,exist_ok=True)
    (folder/'study.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    Path('config/candidate.json').write_text(json.dumps(asdict(config),indent=2))
    start=starts[-1]
    last=run(bars[start*pairs:(start+horizon)*pairs],config,manifest,rules,precomputed=features[start:start+horizon])
    last['warnings'].insert(0,result['caveat']);save_run(last,folder/'latest-episode')
    print('Selected:',chosen['config']);print('Validation:',result['validation']);print('Later:',result['later_period']);print('Stress:',result['stress'])

if __name__=='__main__':main()
