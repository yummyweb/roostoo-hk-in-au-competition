#!/usr/bin/env python3
"""Replay the live config over independent 14-day episodes with the research engine.

Each episode starts flat with $100k. The 50-asset history has already been
inspected, so this is a reproducible sanity check of what is deployed, not a
fresh holdout. Needs scripts/setup-lstm.sh (NumPy) and data/binance-50-1h.csv.
"""
from dataclasses import replace
from pathlib import Path
import json
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roostoo.cli import get_rules
from roostoo.data import read_csv
from roostoo.ranking import LOOKBACK,execution_features,fit_scores,market_features,replay
from roostoo.strategy import Config


def main():
    c=Config(**json.loads(Path(sys.argv[1] if len(sys.argv)>1 else 'config/live_candidate.json').read_text()))
    bars,manifest=read_csv('data/binance-50-1h.csv');rules=get_rules(bars)
    market=market_features(bars);n=len(market['timestamps']);horizon=14*24
    scores,_,_=fit_scores(market,c.rank_model,int(n*.6));features=execution_features(market,scores)
    starts=range(LOOKBACK,n-horizon,horizon)
    for name,config in (('base costs',c),('stress costs',replace(c,fee_bps=20,spread_bps=10,slippage_bps=10))):
        ms=[replay(bars,config,manifest,rules,features,s,s+horizon)['metrics'] for s in starts]
        rets=[m['total_return'] for m in ms]
        print(f"{name}: episodes {len(ms)} | return mean {statistics.mean(rets):+.2%} median {statistics.median(rets):+.2%} "
              f"worst {min(rets):+.2%} profitable {sum(r>0 for r in rets)/len(rets):.0%} | "
              f"drawdown mean {statistics.mean(m['max_drawdown'] for m in ms):.2%} worst {max(m['max_drawdown'] for m in ms):.2%} | "
              f"active days median {statistics.median(m['active_days'] for m in ms)} min {min(m['active_days'] for m in ms)} | "
              f"turnover mean {statistics.mean(m['turnover'] for m in ms):.1f}x fees mean ${statistics.mean(m['fees'] for m in ms):,.0f}")


if __name__=='__main__':main()
