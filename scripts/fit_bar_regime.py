#!/usr/bin/env python3
"""Fit the per-coin regime model for bars shorter than an hour (config/coin_regime_<minutes>m.json).

    scripts/fit_bar_regime.py [bar minutes] [candle minutes] [return bars] [volatility bars]   (default 15 5 24 24)

The method of scripts/fit_coin_regime.py (K-Means, then a three-state Gaussian HMM; Haryani, Chandra and Tarigan,
2026) on bar closes: each coin's log return over `return bars` and the standard deviation of its one-bar log returns
over `volatility bars`. One model is shared by all coins; highest mean return is BULL, lowest BEAR, the middle CHOP.
Bars are taken from data/candles_<candle minutes>m (scripts/fetch_candles.py). Needs scripts/setup-lstm.sh (NumPy).
"""
from pathlib import Path
import json
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'research/lab')]
import ind, regime
from roostoo.regime_hmm import RegimeFilter

ARGS=[int(v) for v in sys.argv[1:]]+[15,5,24,24][len(sys.argv)-1:]
BAR,CANDLE,RETURN_BARS,VOL_BARS=ARGS
OUTPUT=ROOT/f'config/coin_regime_{BAR}m.json'


def panel():
    """(timestamps, pairs, closes[T,N]) of the coins that share the full recorded timeline."""
    step=CANDLE*60000;span=BAR*60000
    series={path.stem+'/USD':json.loads(path.read_text()) for path in sorted((ROOT/f'data/candles_{CANDLE}m').glob('*.json'))}
    length=max(len(rows) for rows in series.values());end=max(rows[-1][0] for rows in series.values() if rows)
    full={pair:[row for row in rows if (row[0]+step)%span==0] for pair,rows in series.items()    # the candle that closes each bar
          if len(rows)==length and rows[-1][0]==end and all(b[0]-a[0]==step for a,b in zip(rows,rows[1:]))}
    pairs=sorted(full);return [row[0] for row in full[pairs[0]]],pairs,np.array([[row[1] for row in full[pair]] for pair in pairs]).T


def main():
    stamps,pairs,closes=panel()
    x=np.stack([ind.logret(closes,RETURN_BARS),ind.realized_vol(closes,VOL_BARS)],-1)
    first=max(RETURN_BARS,VOL_BARS);flat=x[first:].reshape(-1,2);mean=flat.mean(0);std=flat.std(0);z=(x[first:]-mean)/std
    model=regime.fit(z,K=3);order=np.argsort(model['mu'][:,0])   # by mean return: BEAR, CHOP, BULL
    stamp=lambda ms:time.strftime('%Y-%m-%dT%H:%MZ',time.gmtime(int(ms)/1000))
    params=dict(return_bars=RETURN_BARS,vol_bars=VOL_BARS,feature_mean=mean.tolist(),feature_std=std.tolist(),
                means=model['mu'].tolist(),covariances=model['cov'].tolist(),transition=model['A'].tolist(),start=model['pi'].tolist(),
                bear_state=int(order[0]),chop_state=int(order[1]),bull_state=int(order[2]),log_likelihood=model['ll'],
                source='Haryani, Chandra, Tarigan (2026) doi:10.47738/jdmdc.v3i1.57',data=f'Binance {BAR}m closes, {len(pairs)} pairs',
                first_candle=stamp(stamps[0]),last_candle=stamp(stamps[-1]))
    OUTPUT.write_text(json.dumps(params,indent=1)+'\n')
    labels=regime.forward(z,model).argmax(-1);raw=model['mu']*std+mean
    for name,k in (('BEAR',order[0]),('CHOP',order[1]),('BULL',order[2])):
        print(f"{name}: mean {RETURN_BARS}-bar return {raw[k,0]:+.2%}, mean one-bar volatility {raw[k,1]:.3%}, "
              f"{np.mean(labels==k):.0%} of coin-bars, stays with probability {model['A'][k,k]:.4f}")
    changes=(labels[1:]!=labels[:-1]).sum()/len(pairs)/(len(labels)*BAR/1440)
    print(f"label changes per coin per day: {changes:.1f}; EM iterations {model['iters']}, converged {model['converged']}")
    # The runner warms each coin with its last 1,000 closes; its labels must match the full-history filter.
    names={int(order[0]):'BEAR',int(order[1]):'CHOP',int(order[2]):'BULL'};agree=total=0
    for j in range(len(pairs)):
        live=RegimeFilter(params);seen=[]
        for close in closes[-1000:,j]:live.update(float(close));seen.append(live.label)
        expected=[names[int(s)] for s in labels[-500:,j]]
        agree+=sum(a==b for a,b in zip(seen[-500:],expected));total+=500
    print(f'runner filter agrees with the fit on {agree/total:.2%} of the last 500 bars across {len(pairs)} coins')
    print(f'wrote {OUTPUT}')


if __name__=='__main__':main()
