"""candidate_1 - LEAST-BAD use of the paper's regime filter. Track verdict: NO EDGE. Filed for completeness, not for trading.

What it is: EmaCross(24, 100) long, limit entries, ATR(24)x3 trailing stop, 4 equal slots (strategies.py defaults), with new
entries allowed only while Bitcoin is in the LOWEST-VOLATILITY state of the paper's model:
  features  6h log return and 24h rolling volatility of BTC/USD, z-scored on the training window;
  model     K-Means (K=3) -> 3-state Gaussian HMM, expanding window, refit every 720 bars, first fit ends at bar 744
            (regime.walk_forward); state identities matched across refits (rp.canonical);
  map       at each refit the allowed state is the one with the lowest average 24h realised volatility so far.
ZScoreMR and shorts are OFF: no state of any labelling made them pay (see REPORT.md).
Everything is fitted inside make(panel) on past data only. make() refits the HMM ~10 times (several seconds), so the
look-ahead test was run as h.causality_check(make, panel, cuts=8).

Why it is not a recommendation: +27.7% on design at default costs but +1.6% under stress costs, the middle third is
negative, it trades on only ~35% of days (the competition needs 8 of 14), the neighbouring labellings range from -22% to
+23%, and a placebo label (the same label shifted 2,000 bars) scored +33%.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(os.path.dirname(HERE))
for p in (LAB, HERE):
    if p not in sys.path: sys.path.insert(0, p)
import ind, gates

SPEC = dict(scope='btc', rw=6, vw=24, K=3, hmm=True)


def make(panel):
    canon = gates.causal_labels(panel, SPEC['scope'], SPEC['rw'], SPEC['vw'], SPEC['K'], SPEC['hmm'])
    allow = gates.vol_state(canon, SPEC['K'], 'lo', ind.realized_vol(panel.C, 24))
    return gates.portfolio(panel, allow, None, None, 'E', slots=4)
