"""Bitcoin volatility-regime filter after Haryani, Chandra and Tarigan (2026),
"Market Regime Detection in Bitcoin Time Series Using K-Means Clustering and
Hidden Markov Models", J. Digit. Mark. Digit. Curr. 3(1), doi:10.47738/jdmdc.v3i1.57.

The paper fits a three-state Gaussian HMM, initialised from K-Means clusters,
to standardized log returns and rolling volatility. scripts/fit_regime_hmm.py
does that fit offline on hourly candles. This module only applies the fitted
parameters with a causal forward filter in pure Python. It is a research
diagnostic: the states are persistent but did not predict direction out of
sample, so no order logic reads it.
"""
from collections import deque
import json
import math
from pathlib import Path

PARAMS=Path(__file__).resolve().parents[1]/'config/regime_hmm.json'
WINDOW=24  # hours of returns in the rolling volatility feature


def density(z,mean,cov):
    """Bivariate normal density."""
    (a,b),(_,d)=cov;det=a*d-b*b;x=z[0]-mean[0];y=z[1]-mean[1]
    return math.exp(-.5*(d*x*x-2*b*x*y+a*y*y)/det)/(2*math.pi*math.sqrt(det))


class RegimeFilter:
    """Forward filter for one coin. The two features are the log return over `return_bars` hours and the standard
    deviation of hourly log returns over `vol_bars` hours (1 and 24 unless the parameter file says otherwise)."""
    def __init__(self,params=None):
        self.p=params or json.loads(PARAMS.read_text())
        self.span=int(self.p.get('return_bars',1));self.window=int(self.p.get('vol_bars',WINDOW))
        self.returns=deque(maxlen=max(self.span,self.window));self.previous=None;self.alpha=None

    def update(self,close):
        """Advance one completed hourly close. Returns P(state | closes so far), or None while warming up."""
        if self.previous is not None:self.returns.append(math.log(close/self.previous))
        self.previous=close
        if len(self.returns)<self.returns.maxlen:return None
        recent=list(self.returns);tail=recent[-self.window:]
        mean=sum(tail)/self.window
        volatility=math.sqrt(max(0,sum(x*x for x in tail)/self.window-mean*mean))
        z=[(value-m)/s for value,m,s in zip((sum(recent[-self.span:]),volatility),self.p['feature_mean'],self.p['feature_std'])]
        states=range(len(self.p['means']))
        prior=self.p['start'] if self.alpha is None else [sum(self.alpha[i]*self.p['transition'][i][j] for i in states) for j in states]
        posterior=[prior[k]*density(z,self.p['means'][k],self.p['covariances'][k]) for k in states]
        total=sum(posterior)
        # An observation too extreme for every state carries no information; keep the prior.
        self.alpha=[x/total for x in posterior] if total>0 else prior
        return self.alpha

    @property
    def label(self):
        """'BULL', 'BEAR' or 'CHOP' for a three-state coin model, or None while warming up."""
        if self.alpha is None:return None
        state=max(range(len(self.alpha)),key=self.alpha.__getitem__)
        return 'BULL' if state==self.p['bull_state'] else 'BEAR' if state==self.p['bear_state'] else 'CHOP'

    @property
    def calm(self):
        """True when the most likely state is the low-volatility one."""
        return self.alpha is not None and max(range(len(self.alpha)),key=self.alpha.__getitem__)==self.p['calm_state']
