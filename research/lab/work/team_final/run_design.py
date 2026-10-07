"""Task (b): the 9 (R, V) feature-window pairs on the DESIGN panel only. Writes design_windows.json."""
import os, sys, json, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tf
import harness as h, evalkit

START = 1900
HERE = os.path.dirname(os.path.abspath(__file__))


def leg_side(r):
    """Net P&L and trade count of closed trades by leg and side."""
    out = {f'{tag}_{side}': dict(n=0, pnl=0.) for tag in ('ema', 'mr') for side in ('long', 'short')}
    for x in r.trades:
        g = out[f"{x['tag']}_{'long' if x['side'] > 0 else 'short'}"]; g['n'] += 1; g['pnl'] += x['pnl']
    return out


def regime_stats(P, R, V, start=START):
    lab, models = tf.regime_labels(P, R, V); X = tf.features(P, R, V); seg = lab[start:]; m = models[-1]
    raw = (m['mu'] * m['sd'] + m['mean'])[m['order']]                       # last fitted model, raw units, BEAR/CHOP/BULL
    return dict(share=[float((seg == k).mean()) for k in range(3)], unknown=float((seg < 0).mean()),
                changes_per_coin_14d=float((seg[1:] != seg[:-1]).sum() / P.N / ((len(seg) - 1) / 336)),
                model_means=raw.tolist(), label_means=[X[start:][seg == k].mean(0).tolist() for k in range(3)],
                first_label_row=int(np.argmax((lab >= 0).any(1))), fits=len(models), all_converged=bool(all(x['converged'] for x in models)))


if __name__ == '__main__':
    P = h.load('design'); res = []
    for R in (24, 72, 168):
        for V in (24, 72, 168):
            t0 = time.time(); make = lambda p, R=R, V=V: tf.TeamFinal(p, R, V)
            o = evalkit.report(make, P, start=START, name=f'R{R} V{V}', check=False, verbose=False)
            r = h.backtest(P, make(P), start=START)
            o.update(R=R, V=V, regime=regime_stats(P, R, V), leg_side=leg_side(r),
                     fresh=h.fresh_windows(P, make, days=11, step_days=3, start=START))
            res.append(o); json.dump(res, open(os.path.join(HERE, 'design_windows.json'), 'w'), indent=1, default=float)
            s, g, f = o['summary'], o['regime'], o['fresh']
            print(f"R{R:3} V{V:3} | BEAR/CHOP/BULL {g['share'][0]:.0%}/{g['share'][1]:.0%}/{g['share'][2]:.0%} chg/14d {g['changes_per_coin_14d']:.1f} | "
                  f"tot {s['total_return']:+.1%} mdd {s['max_drawdown']:.1%} thirds {' '.join(f'{x['total']:+.1%}' for x in o['thirds'])} stress {o['stress']['total_return']:+.1%} | "
                  f"{' '.join(f'{k}:{v['pnl']:+.0f}({v['n']})' for k, v in o['leg_side'].items())} | trades {s['trades']} active {s['active_day_share']:.0%} | "
                  f"fresh mean {f['mean']:+.2%} med {f['median']:+.2%} win {f['win']:.0%} worst {f['worst']:+.1%} | {time.time() - t0:.0f}s", flush=True)
