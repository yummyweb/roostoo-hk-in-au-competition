#!/usr/bin/env python3
"""Fit the per-coin regime model the regime-legs runner reads (config/coin_regime.json).

Method of Haryani, Chandra and Tarigan (2026), doi:10.47738/jdmdc.v3i1.57, on hourly candles: two features per coin
and hour (the 24-hour log return and the 24-hour standard deviation of hourly log returns), standardised; K-Means
with K=3; then a three-state Gaussian HMM started from the clusters and trained with Baum-Welch. One model is shared
by all 50 coins. The state with the highest mean return is BULL, the lowest BEAR, the middle one CHOP.

The windows were chosen on the design period only (research/lab/work/team_final/REPORT.txt). This script fits the
model on all history for live use and checks that the runner's pure-Python filter gives the same labels.
Needs research/lab/build_panels.py to have been run, and scripts/setup-lstm.sh (NumPy, scikit-learn).
"""
from pathlib import Path
import json
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'research/lab')]
import harness, ind, regime
from roostoo.regime_hmm import RegimeFilter

RETURN_BARS,VOL_BARS=24,24
OUTPUT=ROOT/'config/coin_regime.json'


def main():
    panel=harness.load('full')
    x=np.stack([ind.logret(panel.C,RETURN_BARS),ind.realized_vol(panel.C,VOL_BARS)],-1)
    first=max(RETURN_BARS,VOL_BARS);flat=x[first:].reshape(-1,2);mean=flat.mean(0);std=flat.std(0);z=(x[first:]-mean)/std
    model=regime.fit(z,K=3);order=np.argsort(model['mu'][:,0])   # by mean return: BEAR, CHOP, BULL
    # BEAR and CHOP differ little in mean return, so a refit on other data can swap which volatility tier is which.
    tiers=lambda means,states:[sorted(m[1] for m in means).index(means[k][1]) for k in states]
    old=json.loads(OUTPUT.read_text()) if OUTPUT.exists() else None
    if old and tiers(old['means'],[old['bear_state'],old['chop_state'],old['bull_state']])!=tiers(model['mu'].tolist(),[int(k) for k in order]) and '--accept-new-labels' not in sys.argv:
        raise SystemExit('The labels moved to different volatility tiers than the current file; inspect the fit, then rerun with --accept-new-labels')
    stamp=lambda ms:time.strftime('%Y-%m-%dT%H:%MZ',time.gmtime(int(ms)/1000))
    params=dict(return_bars=RETURN_BARS,vol_bars=VOL_BARS,feature_mean=mean.tolist(),feature_std=std.tolist(),
                means=model['mu'].tolist(),covariances=model['cov'].tolist(),transition=model['A'].tolist(),start=model['pi'].tolist(),
                bear_state=int(order[0]),chop_state=int(order[1]),bull_state=int(order[2]),log_likelihood=model['ll'],
                source='Haryani, Chandra, Tarigan (2026) doi:10.47738/jdmdc.v3i1.57',data='Binance 1h closes, 50 pairs',
                first_candle=stamp(panel.ts[0]),last_candle=stamp(panel.ts[-1]))
    OUTPUT.write_text(json.dumps(params,indent=1)+'\n')
    labels=regime.forward(z,model).argmax(-1);raw=model['mu']*std+mean
    for name,k in (('BEAR',order[0]),('CHOP',order[1]),('BULL',order[2])):
        print(f"{name}: mean {RETURN_BARS}h return {raw[k,0]:+.2%}, mean hourly volatility {raw[k,1]:.2%}, "
              f"{np.mean(labels==k):.0%} of coin-hours, stays with probability {model['A'][k,k]:.3f}")
    changes=(labels[1:]!=labels[:-1]).sum()/panel.N/(len(labels)/336)
    print(f"label changes per coin per 14 days: {changes:.1f}; EM iterations {model['iters']}, converged {model['converged']}")
    # The runner warms each coin with its last 1,000 closes; its labels must match the full-history filter.
    names={int(order[0]):'BEAR',int(order[1]):'CHOP',int(order[2]):'BULL'};agree=total=0
    for j,pair in enumerate(panel.pairs):
        live=RegimeFilter(params);seen=[]
        for close in panel.C[-1000:,j]:live.update(float(close));seen.append(live.label)
        expected=[names[int(s)] for s in labels[-500:,j]]
        agree+=sum(a==b for a,b in zip(seen[-500:],expected));total+=500
    print(f'runner filter agrees with the fit on {agree/total:.2%} of the last 500 hours across {panel.N} coins')
    print(f'wrote {OUTPUT}')


if __name__=='__main__':main()
