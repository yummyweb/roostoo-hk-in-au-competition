#!/usr/bin/env python3
"""Independent 14-day competition episodes. All selection uses training episodes.

This is follow-up research on the same dataset, not a newly untouched holdout.
Each episode starts flat with a new $100k wallet and its own drawdown halt.
"""
from dataclasses import asdict,replace
from pathlib import Path
import json
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roostoo.data import read_csv
from roostoo.engine import run
from roostoo.strategy import Config
from roostoo.cli import get_rules
from roostoo.report import save_run


def main():
    bars,manifest=read_csv('data/binance-1h.csv'); rules=get_rules(bars)
    pairs=len(rules); n=len(bars)//pairs; horizon=14*24; warmup=3*336
    configs=[Config(),Config(allow_short=True),Config(fast=48,slow=168,momentum=72,max_hold_bars=168,cooldown_bars=12),
             Config(fast=48,slow=168,momentum=72,max_hold_bars=168,cooldown_bars=12,allow_short=True),
             Config(fast=96,slow=336,momentum=168,max_hold_bars=336,cooldown_bars=24)]
    starts=list(range(warmup,n-horizon+1,horizon))
    first=int(len(starts)*.6);second=int(len(starts)*.8)
    def evaluate(c, indices, stress=False):
        output=[]
        for start in indices:
            frame=bars[(start-warmup)*pairs:(start+horizon)*pairs]
            r=run(frame,c,manifest,rules,start_index=warmup)
            output.append({'start':r['evaluation_start'],'end':r['evaluation_end'],'metrics':r['metrics']})
        return output
    def summary(rows):
        ms=[r['metrics'] for r in rows]; rets=[m['total_return'] for m in ms]
        return {'episodes':len(ms),'mean_return':statistics.mean(rets),'median_return':statistics.median(rets),
                'worst_return':min(rets),'profitable_fraction':sum(r>0 for r in rets)/len(rets),
                'mean_max_drawdown':statistics.mean(m['max_drawdown'] for m in ms),
                'median_active_days':statistics.median(m['active_days'] for m in ms),
                'eight_active_days_fraction':sum(m['active_days']>=8 for m in ms)/len(ms),
                'mean_fees':statistics.mean(m['fees'] for m in ms)}
    candidates=[]
    for c in configs:
        rows=evaluate(c,starts[:first]); s=summary(rows)
        # Fixed economic selection criterion, not Sharpe on tiny samples.
        score=s['median_return']-s['mean_max_drawdown']
        candidates.append({'config':asdict(c),'train':s,'selection_score':score,'training_episodes':rows})
        print(c.fast,c.slow,c.allow_short,s,flush=True)
    chosen=max(candidates,key=lambda c:c['selection_score'])
    config=Config(**chosen['config'])
    validation=evaluate(config,starts[first:second]); holdout=evaluate(config,starts[second:])
    stress=evaluate(replace(config,fee_bps=20,spread_bps=10,slippage_bps=10),starts[second:])
    result={'method':'Independent, non-overlapping 14-day episodes; fresh flat wallet per episode; 60/20/20 chronological groups',
            'caveat':'Follow-up research: the last 20% period was already inspected in the initial study. This is not a fresh untouched holdout.',
            'candidates':candidates,'selected_config':asdict(config),'validation':summary(validation),
            'later_period':summary(holdout),'stress':summary(stress),'validation_episodes':validation,'later_episodes':holdout,
            'readiness':'NOT READY: require prospective paper validation and eight active days in competition conditions.'}
    path=Path('runs/competition-windows');path.mkdir(parents=True,exist_ok=True)
    (path/'study.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    start=starts[-1]
    last=run(bars[(start-warmup)*pairs:(start+horizon)*pairs],config,manifest,rules,start_index=warmup)
    last['warnings'].insert(0,result['caveat'])
    save_run(last,path/'latest-episode')
    print('Validation:',result['validation']);print('Later period:',result['later_period']);print('Stress:',result['stress'])

if __name__=='__main__':main()
