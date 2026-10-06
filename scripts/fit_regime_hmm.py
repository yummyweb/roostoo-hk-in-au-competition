#!/usr/bin/env python3
"""Fit and validate the Bitcoin regime HMM. Research only: it is not used for trading.

Method of Haryani, Chandra and Tarigan (2026): standardized log return and
rolling volatility, K-Means (K=3) segmentation, then a three-state Gaussian HMM
initialised from the clusters and trained with Baum-Welch. Here the candles are
hourly and the volatility window is 24 hours.

The script first fits on the first 60% of history and reports, on the unseen
last 40%, how persistent the filtered states are and how the market moved after
the calm state compared with the others. It then fits on all history and writes
config/regime_hmm.json. On the 50-pair history the states are persistent
volatility states, but the calm state does not reliably predict market
direction: the sign of the difference depends on the sub-period and on which
hours are sampled. See docs/STRATEGY_POLICY.md.
Needs scripts/setup-lstm.sh (NumPy, scikit-learn) and data/binance-50-1h.csv.
"""
from pathlib import Path
import json
import sys
import numpy as np
from sklearn.cluster import KMeans
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roostoo.data import read_csv
from roostoo.regime_hmm import PARAMS,WINDOW,RegimeFilter


def log_density(x,means,covariances):
    out=np.empty((len(x),len(means)))
    for k,(mean,cov) in enumerate(zip(means,covariances)):
        lower=np.linalg.cholesky(cov);z=np.linalg.solve(lower,(x-mean).T)
        out[:,k]=-.5*(z*z).sum(0)-np.log(np.diag(lower)).sum()-np.log(2*np.pi)
    return out


def fit(x,states=3,iterations=60,kmeans=True,seed=0):
    """Baum-Welch for a full-covariance Gaussian HMM, started from K-Means labels (or random ones)."""
    n,d=x.shape
    labels=KMeans(states,n_init=10,random_state=seed).fit_predict(x) if kmeans else np.random.default_rng(seed).integers(0,states,n)
    means=np.array([x[labels==k].mean(0) for k in range(states)])
    covariances=np.array([np.cov(x[labels==k].T)+1e-4*np.eye(d) for k in range(states)])
    transition=np.ones((states,states))
    for i,j in zip(labels[:-1],labels[1:]):transition[i,j]+=1
    transition/=transition.sum(1,keepdims=True);start=np.bincount(labels,minlength=states)/n;previous=-np.inf
    for _ in range(iterations):
        logs=log_density(x,means,covariances);peak=logs.max(1,keepdims=True);b=np.exp(logs-peak)
        alpha=np.empty((n,states));scale=np.empty(n);a=start*b[0];scale[0]=a.sum();alpha[0]=a/scale[0]
        for t in range(1,n):
            a=(alpha[t-1]@transition)*b[t];scale[t]=a.sum();alpha[t]=a/scale[t]
        likelihood=float(np.log(scale).sum()+peak.sum())
        beta=np.empty((n,states));beta[-1]=1
        for t in range(n-2,-1,-1):beta[t]=(transition@(b[t+1]*beta[t+1]))/scale[t+1]
        gamma=alpha*beta;gamma/=gamma.sum(1,keepdims=True)
        xi=(alpha[:-1,:,None]*transition[None]*(b[1:]*beta[1:])[:,None,:]/scale[1:,None,None]).sum(0)
        transition=xi/xi.sum(1,keepdims=True);start=gamma[0];weight=gamma.sum(0)
        means=(gamma.T@x)/weight[:,None]
        covariances=np.array([((x-means[k]).T*gamma[:,k])@(x-means[k])/weight[k]+1e-4*np.eye(d) for k in range(states)])
        if likelihood-previous<1e-6*abs(likelihood):break
        previous=likelihood
    return dict(means=means,covariances=covariances,transition=transition,start=start,log_likelihood=likelihood)


def features(closes):
    returns=np.diff(np.log(closes))
    volatility=np.array([returns[i-WINDOW+1:i+1].std() for i in range(WINDOW-1,len(returns))])
    return np.column_stack([returns[WINDOW-1:],volatility])


def parameters(closes):
    raw=features(closes);mean=raw.mean(0);std=raw.std(0);model=fit((raw-mean)/std)
    volatility=model['means'][:,1]
    return dict(feature_mean=mean.tolist(),feature_std=std.tolist(),means=model['means'].tolist(),
                covariances=model['covariances'].tolist(),transition=model['transition'].tolist(),start=model['start'].tolist(),
                calm_state=int(volatility.argmin()),turbulent_state=int(volatility.argmax()),log_likelihood=model['log_likelihood'])


def main():
    bars,_=read_csv('data/binance-50-1h.csv');pairs=sorted({b.pair for b in bars});count=len(pairs)
    close=np.array([b.close for b in bars]).reshape(-1,count);btc=close[:,pairs.index('BTC/USD')]
    market=np.log(close).mean(1);n=len(btc);cut=int(n*.6)
    p=parameters(btc[:cut]);live=RegimeFilter(p);state=[]
    for value in btc:
        alpha=live.update(float(value));state.append(-1 if alpha is None else int(np.argmax(alpha)))
    state=np.array(state);tail=state[cut:];calm=state==p['calm_state']
    print(f'Validation: fitted on the first {cut} hours, applied causally to the next {n-cut}.')
    print(f"  state changes per 14 days: {(tail[1:]!=tail[:-1]).sum()/(len(tail)/336):.1f}; calm {np.mean(tail==p['calm_state']):.0%} of hours, turbulent {np.mean(tail==p['turbulent_state']):.0%}")
    hours=np.arange(cut,n-72);ahead=market[hours+72]-market[hours]
    print(f'  equal-weight market over the next 72h, all hours: after calm {ahead[calm[hours]].mean():+.2%}, after other states {ahead[~calm[hours]].mean():+.2%}')
    # Non-overlapping 72h samples can start at any of 72 offsets; an edge should not depend on the offset.
    gaps=[ahead[o::72][calm[hours][o::72]].mean()-ahead[o::72][~calm[hours][o::72]].mean() for o in range(72)]
    print(f'  calm minus other by sampling offset: min {min(gaps):+.2%}, median {np.median(gaps):+.2%}, max {max(gaps):+.2%}; calm better in {np.mean(np.array(gaps)>0):.0%} of offsets')
    third=len(hours)//3
    for label,part in (('first third',hours[:third]),('middle third',hours[third:2*third]),('last third',hours[2*third:])):
        move=market[part+72]-market[part]
        print(f'  {label}: after calm {move[calm[part]].mean():+.2%}, after other states {move[~calm[part]].mean():+.2%}')
    final=parameters(btc);raw=features(btc);z=(raw-raw.mean(0))/raw.std(0)
    print(f"All history: log-likelihood with K-Means initialisation {final['log_likelihood']:.0f}, with random initialisation {fit(z,kmeans=False)['log_likelihood']:.0f}")
    final.update(source='Haryani, Chandra, Tarigan (2026) doi:10.47738/jdmdc.v3i1.57',data='Binance BTCUSDT 1h closes',
                 first_timestamp=bars[0].timestamp,last_timestamp=bars[-1].timestamp,window_hours=WINDOW)
    PARAMS.write_text(json.dumps(final,indent=2)+'\n');print(f'Wrote {PARAMS}')


if __name__=='__main__':main()
