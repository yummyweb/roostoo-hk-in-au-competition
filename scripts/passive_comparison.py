#!/usr/bin/env python3
"""Diagnostic 20%-invested passive reference, chosen after observing ensemble exposure.

Not a selection candidate or independent holdout experiment. Same evaluation
period and order/cost/risk engine. Remaining 80% starts in cash.
"""
from dataclasses import replace
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roostoo.data import read_csv
from roostoo.cli import get_rules
from roostoo.strategy import Config,Indicators
from roostoo.engine import run
from roostoo.report import save_run
from itertools import groupby


def main():
    bars,m=read_csv('data/binance-20-1h.csv');rules=get_rules(bars);pairs=len(rules)
    n=len(bars)//pairs;start=int(n*.8);warm=720
    bars=bars[(start-warm)*pairs:]
    c=Config(strategy='buy_hold',max_position=.2/pairs,max_exposure=.2)
    states={p:Indicators(c) for p in rules}
    f=[{b.pair:states[b.pair].update(b) for b in rows} for _,rows in groupby(bars,key=lambda b:b.timestamp)]
    r=run(bars,c,m,rules,start_index=warm,precomputed=f)
    stress=run(bars,replace(c,fee_bps=20,spread_bps=10,slippage_bps=10),m,rules,start_index=warm,precomputed=f)
    r['name']='Passive basket / 20% initial budget'
    r['warnings'].insert(0,'Diagnostic reference chosen after observing ensemble exposure; not used to select the strategy. Initial budget is 20%; exposure subsequently drifts.')
    save_run(r,'runs/ranking-risk-study/passive20')
    Path('runs/ranking-risk-study/passive-comparison.json').write_text(json.dumps(dict(metrics=r['metrics'],stress=stress['metrics']),indent=2))
    print(json.dumps(dict(metrics=r['metrics'],stress=stress['metrics']),indent=2))

if __name__=='__main__':main()
