import sys, time; sys.path.insert(0, '.'); sys.path.insert(0, 'work/live_legs')
import harness as h, exam, evalkit
from candidate_1 import make
for name, start in (('design', 1900), ('select', 7519), ('full', 10025), ('early12', 1900)):
    P = h.load(name); t0 = time.time(); o = exam.score(make, P, start, P.T)
    r = h.backtest(P, make(P), start=start); tag = r.by('tag'); side = r.by('side')
    legs = {}
    for x in r.trades: k = f"{x['tag']}_{'long' if x['side'] > 0 else 'short'}"; legs[k] = legs.get(k, 0) + x['pnl']
    print(f"{name:8} total {o['total']:+7.1%} mdd {o['mdd']:5.1%} stress {o['stress']:+7.1%} Sharpe {o['sharpe']:5.2f} Sortino {o['sortino']:5.2f} | fresh 11d mean {o['f_mean']:+6.2%} med {o['f_med']:+6.2%} win {o['f_win']:4.0%} worst {o['f_worst']:+6.1%} best {o['f_best']:+6.1%} | trades {o['trades']} active {o['active']:.0%} | " + ' '.join(f"{k}:{v:+.0f}" for k, v in sorted(legs.items())) + f" ({time.time() - t0:.0f}s)", flush=True)
