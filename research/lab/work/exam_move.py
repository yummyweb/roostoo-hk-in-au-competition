import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'work/breakout_params')
import numpy as np, harness as h, exam
from bo import BO
def days8(r, ts, start):
    """Share of 14-day spans with a fill on at least 8 UTC days, and the worst span."""
    day = ts // 86_400_000; fills = sorted({int(day[t]) for t in r_fills}); d0 = int(day[start]); d1 = int(day[-1]); out = []
    for s in range(d0, d1 - 13): out.append(sum(1 for d in fills if s <= d < s + 14))
    return np.mean(np.array(out) >= 8), min(out), float(np.median(out))
for name, start in (('design', 744), ('select', 7519), ('full', 10025), ('early12', 400)):
    P = h.load(name)
    for move, slots in ((.10, 4), (.08, 4), (.06, 4), (.08, 6)):
        make = lambda p, move=move, slots=slots: BO(p, mw=12, move=move, hw=120, atr_k=4, atr_n=24, slots=slots, lock=12)
        o = exam.score(make, P, start, P.T)
        bk = h.Book(100000., P, h.Costs()); r = h.backtest(P, make(P), start=start)
        # fills per UTC day from the trade log (entries and exits)
        r_fills = sorted({x['t_in'] for x in r.trades} | {x['t_out'] for x in r.trades})
        share, worst, med = days8(r, P.ts, start)
        print(f"{name:8} move {move:.0%} slots {slots} | total {o['total']:+7.1%} mdd {o['mdd']:5.1%} stress {o['stress']:+7.1%} Sharpe {o['sharpe']:5.2f} | fresh 11d mean {o['f_mean']:+6.2%} med {o['f_med']:+6.2%} win {o['f_win']:4.0%} worst {o['f_worst']:+6.1%} >=10% {o['f_ge10']:4.0%} | trades {o['trades']:4d} | 14d spans with >=8 active days {share:4.0%} (median {med:.0f}, worst {worst})", flush=True)
