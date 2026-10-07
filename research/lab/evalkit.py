"""One-call standard report so every track reports the same numbers the same way."""
import json
import numpy as np
import harness as h

# Harsh but plausible: maker fills charged like takers, wider spreads, more overshoot, limits must trade well through.
STRESS = h.Costs(maker_bps=10, taker_bps=15, short_bps=15, spread_mult=3, slip_bps=5, stop_slip_bps=15, through_bps=30)


def report(make, panel, start=744, end=None, name='', check=True, cuts=40, verbose=True):
    """Run `make(panel)` over [start, end) and return a dict of the standard metrics.

    Includes: summary, 11-day rolling windows, the same split into three equal sub-periods, P&L by tag / side / exit
    reason, the stress-cost rerun, and (if check) the look-ahead test.
    """
    end = panel.T if end is None else end
    r = h.backtest(panel, make(panel), start=start, end=end); s = r.summary(); w = r.windows(11)
    cut = np.linspace(0, len(r.eq) - 1, 4).astype(int)
    thirds = [dict(total=float(r.eq[b] / r.eq[a] - 1), **{k: v for k, v in h.windows(r.eq[a:b + 1], 11).items() if k in ('mean', 'median', 'win')})
              for a, b in zip(cut[:-1], cut[1:])]
    rs = h.backtest(panel, make(panel), STRESS, start, end); ws = rs.windows(11)
    out = dict(name=name, rows=[int(start), int(end)], summary=s, windows11=w, thirds=thirds,
               by_tag=r.by('tag'), by_side={('long' if k > 0 else 'short'): v for k, v in r.by('side').items()}, by_reason=r.by('reason'),
               stress=dict(total_return=rs.summary()['total_return'], max_drawdown=rs.summary()['max_drawdown'], w11_mean=ws.get('mean'), w11_median=ws.get('median')),
               rejects=r.rejects, max_orders_per_hour=r.max_orders_per_hour)
    if check:
        ok, diff = h.causality_check(make, panel, cuts=cuts, start=start); out['causality_ok'] = bool(ok); out['causality_diff'] = None if ok else str(diff)
    if verbose: print(line(out))
    return out


def line(o):
    s, w, st = o['summary'], o['windows11'], o['stress']
    sides = ' '.join(f"{k}:{v['pnl']:+.0f}({v['n']})" for k, v in o['by_side'].items())
    return (f"{o['name'][:38]:38} tot {s['total_return']:+7.1%} mdd {s['max_drawdown']:5.1%} comp {s['composite']:+6.2f} | 11d mean {w.get('mean', 0):+6.2%} med {w.get('median', 0):+6.2%} "
            f"win {w.get('win', 0):4.0%} >=10% {w.get('p_ge_10', 0):4.0%} <=-10% {w.get('p_le_m10', 0):4.0%} | thirds {' '.join(f'{t['total']:+.0%}' for t in o['thirds'])} | "
            f"trades {s['trades']} win {s['win_rate']:.0%} t/o {s['turnover_x']:.0f}x fill {s['limit_fill_rate']:.0%} active {s['active_day_share']:.0%} | "
            f"stress tot {st['total_return']:+.1%} 11d {st['w11_mean'] or 0:+.2%} | {sides} | causal {o.get('causality_ok', 'n/a')}")


def save(o, path):
    json.dump(o, open(path, 'w'), indent=1, default=float)
