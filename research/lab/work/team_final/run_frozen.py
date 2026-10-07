"""Task (c): the frozen candidate, once per period. Usage: python work/team_final/run_frozen.py check | <panel> <start>
Appends one record per call to frozen_periods.json."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import candidate_1
from run_design import leg_side, regime_stats
import harness as h, exam

if sys.argv[1] == 'check':
    P = h.load('design'); ok, detail = h.causality_check(candidate_1.make, P, cuts=8, start=744)
    print('causality_check(make, design, cuts=8, start=744):', ok, detail)
    json.dump(dict(ok=bool(ok), detail=None if detail is None else str(detail)), open(os.path.join(HERE, 'causality.json'), 'w'))
else:
    name, start = sys.argv[1], int(sys.argv[2]); P = h.load(name); make = candidate_1.make
    o = exam.score(make, P, start, P.T); r = h.backtest(P, make(P), start=start)
    o.update(panel=name, start=start, end=int(P.T), leg_side=leg_side(r), rejects=r.rejects, regime=regime_stats(P, candidate_1.R, candidate_1.V, start),
             coins=float(np.mean(P.C[-1] / P.C[start] - 1)), btc=float(P.C[-1, P.i('BTC/USD')] / P.C[start, P.i('BTC/USD')] - 1))
    path = os.path.join(HERE, 'frozen_periods.json'); res = json.load(open(path)) if os.path.exists(path) else []
    res.append(o); json.dump(res, open(path, 'w'), indent=1, default=float)
    print(f"{name} rows {start}..{P.T} | coins {o['coins']:+.1%} BTC {o['btc']:+.1%} | tot {o['total']:+.1%} mdd {o['mdd']:.1%} stress {o['stress']:+.1%} Sharpe {o['sharpe']:.2f} | "
          f"fresh mean {o['f_mean']:+.2%} med {o['f_med']:+.2%} win {o['f_win']:.0%} worst {o['f_worst']:+.1%} | trades {o['trades']} active {o['active']:.0%} | "
          f"{' '.join(f'{k}:{v['pnl']:+.0f}({v['n']})' for k, v in o['leg_side'].items())} | "
          f"BEAR/CHOP/BULL {'/'.join(f'{x:.0%}' for x in o['regime']['share'])} chg/14d {o['regime']['changes_per_coin_14d']:.1f}")
