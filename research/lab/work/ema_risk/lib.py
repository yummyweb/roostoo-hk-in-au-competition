"""ema_risk track: risk-management / execution extensions of strategies.EmaCross and strategies.Portfolio.

EmaX   - EmaCross + fixed-percent stop (fixed or trailing), time stop, take-profit, exit by cross or by trailing stop
         only, and a cooldown that also applies after a stop-out (the base class only blocks after a signal exit).
PortX  - Portfolio + risk-based sizing (stop hit loses `risk` of equity, capped at the slot), a drawdown brake
         (new entries shrink linearly to zero as equity falls `brake` below its 7-day high) and a BTC hedge.
run()  - evalkit.report plus the three ratios and the share of peak open profit retained.
"""
import sys, json, collections
from pathlib import Path
import numpy as np

LAB = Path(__file__).resolve().parents[2]
if str(LAB) not in sys.path: sys.path.insert(0, str(LAB))
import harness as h, evalkit, ind            # noqa: E402
from harness import Order                    # noqa: E402
from strategies import EmaCross, Portfolio   # noqa: E402

HERE = Path(__file__).resolve().parent


class EmaX(EmaCross):
    def __init__(self, panel, *a, pct_stop=0., pct_trail=False, max_hold=0, exit='cross', take_pct=0., cool_stop=None, **k):
        super().__init__(panel, *a, **k)
        self.pct_stop, self.pct_trail, self.max_hold, self.exit, self.take_pct = pct_stop, pct_trail, max_hold, exit, take_pct
        self.cool_stop = cool_stop; self.held = set()
        if exit == 'trail' and not (self.stop_atr or pct_stop): raise ValueError('trail-only exit needs a stop')

    def manage(self, t, book):
        out = []; C = self.P.C[t]; now = set()
        for p in list(book.pos.values()):
            if p.tag != self.tag: continue
            i = p.pair; a = self.atr[t, i]; now.add(i)
            cross = (self.f[t, i] < self.s[t, i]) if p.side > 0 else (self.f[t, i] > self.s[t, i])
            if (cross and self.exit == 'cross') or (self.max_hold and t - p.t_in >= self.max_hold):
                out.append(Order(i, 'SELL' if p.side > 0 else 'COVER', tag=self.tag)); self.block[i] = t + self.cooldown
            elif self.pct_stop:
                if self.pct_trail:
                    if p.side > 0: book.set_stop(i, max(p.stop, max(p.hi, C[i]) * (1 - self.pct_stop)))
                    else: book.set_stop(i, min(p.stop or 1e18, min(p.lo, C[i]) * (1 + self.pct_stop)))
            elif self.trail and self.stop_atr and np.isfinite(a):
                if p.side > 0: book.set_stop(i, max(p.stop, max(p.hi, C[i]) - self.stop_atr * a))
                else: book.set_stop(i, min(p.stop or 1e18, min(p.lo, C[i]) + self.stop_atr * a))
        if self.cool_stop is not None:                       # positions that vanished without our order: stop or target
            for i in self.held - now:
                self.block[i] = max(self.block.get(i, -1), t + self.cool_stop)
        self.held = now
        return out

    def candidates(self, t, book):
        out = super().candidates(t, book)
        if self.pct_stop or self.take_pct:
            C = self.P.C[t]
            for _, o in out:
                s = 1 if o.kind == 'BUY' else -1
                if self.pct_stop: o.stop = C[o.pair] * (1 - s * self.pct_stop)
                if self.take_pct: o.take = C[o.pair] * (1 + s * self.take_pct)
        return out


class PortX(Portfolio):
    """Same slot logic as Portfolio; the hedge position (tag 'hedge') does not use a slot."""
    def __init__(self, panel, parts, slots=4, expo=.99, max_short=None, risk=0., brake=0., brake_days=7, hedge=0.,
                 hedge_of='long', hedge_pair='BTC/USD', rebalance=.25):
        super().__init__(panel, parts, slots, expo, max_short)
        self.risk, self.brake, self.hedge, self.hedge_of, self.reb = risk, brake, hedge, hedge_of, rebalance
        self.eqhist = collections.deque(maxlen=brake_days * 24); self.hb = panel.i(hedge_pair)
        if hedge:                                            # the parts must leave the hedge pair alone
            mask = np.ones((panel.T, panel.N), bool); mask[:, self.hb] = False
            for part in parts:
                part.allow_long = mask if part.allow_long is None else part.allow_long & mask
                part.allow_short = mask if part.allow_short is None else part.allow_short & mask

    def on_bar(self, t, book):
        orders = []; C = self.P.C[t]
        for part in self.parts: orders += part.manage(t, book)
        closing = {o.pair for o in orders}
        own = [p for p in book.pos.values() if p.tag != 'hedge']
        used = len([p for p in own if p.pair not in closing]) + len({o.pair for o, _ in book.pending if o.kind == 'BUY' and o.tag != 'hedge'})
        shorts = len([p for p in own if p.side < 0 and p.pair not in closing]); free = self.slots - used
        scale = 1.
        if self.brake:
            self.eqhist.append(book.equity); scale = float(np.clip(1 - (1 - book.equity / max(self.eqhist)) / self.brake, 0., 1.))
        if free > 0:
            ranked = [sorted(part.candidates(t, book), key=lambda x: -x[0]) for part in self.parts]; taken = set(); k = 0
            while free > 0 and any(ranked):
                lst = ranked[k % len(ranked)]; k += 1
                if not lst: continue
                _, o = lst.pop(0)
                if o.pair in taken or o.pair in closing: continue
                if o.kind == 'SHORT' and shorts >= self.max_short: continue
                usd = book.equity * self.expo / self.slots
                if self.risk and o.stop > 0:
                    dist = abs(C[o.pair] - o.stop) / C[o.pair]
                    if dist > 0: usd = min(usd, self.risk * book.equity / dist)
                usd *= scale
                if usd < 10.: continue
                if o.kind == 'SHORT': shorts += 1
                o.usd = usd; orders.append(o); taken.add(o.pair); free -= 1
        if self.hedge: orders += self._hedge(t, book, orders, closing)
        return orders

    def _hedge(self, t, book, orders, closing):
        C = self.P.C[t]; b = self.hb; sgn = 1 if self.hedge_of == 'long' else -1
        expo = sum(p.qty * C[p.pair] for p in book.pos.values() if p.tag != 'hedge' and p.side == sgn and p.pair not in closing)
        expo += sum(o.usd for o in orders if o.kind == ('BUY' if sgn > 0 else 'SHORT') and o.limit <= 0)
        target = self.hedge * expo; hp = book.pos.get(b); opn, cls = ('SHORT', 'COVER') if sgn > 0 else ('BUY', 'SELL')
        if hp is None:
            return [Order(b, opn, usd=target, tag='hedge')] if target > 50. else []
        cur = hp.qty * C[b]
        if target <= 50.: return [Order(b, cls, tag='hedge')]
        if cur > target * (1 + self.reb): return [Order(b, cls, frac=float(1 - target / cur), tag='hedge')]
        if cur < target * (1 - self.reb):
            if sgn < 0: return [Order(b, 'BUY', usd=target - cur, tag='hedge')]      # a long hedge can be added to
            return [Order(b, 'COVER', tag='hedge')]                                   # a short cannot: close, reopen next bar
        return []


# ---- evaluation -------------------------------------------------------------------------------------------------
_STASH = []
_orig_backtest = h.backtest


def _bt(*a, **k):
    r = _orig_backtest(*a, **k); _STASH.append(r); return r


def retained(trades, P, tag=None):
    """Share of peak open profit kept. Peak = best price between entry and the bar before the exit bar."""
    mfe, ret = [], []
    for x in trades:
        if x['tag'] == 'hedge' or (tag and x['tag'] != tag): continue
        a, b, i = x['t_in'], x['t_out'], x['pair']
        if x['side'] > 0: peak = max(P.H[a:b, i].max() if b > a else x['entry'], x['entry']); m = peak / x['entry'] - 1
        else: peak = min(P.L[a:b, i].min() if b > a else x['entry'], x['entry']); m = 1 - peak / x['entry']
        mfe.append(m); ret.append(x['ret'])
    mfe, ret = np.array(mfe), np.array(ret)
    if not len(mfe): return {}
    big = mfe >= .05
    return dict(n=len(mfe), avg_mfe=float(mfe.mean()), avg_ret=float(ret.mean()), kept=float(ret.sum() / mfe.sum()) if mfe.sum() > 0 else float('nan'),
                n_big=int(big.sum()), kept_big=float(ret[big].sum() / mfe[big].sum()) if big.any() else float('nan'),
                med_capture_big=float(np.median(ret[big] / mfe[big])) if big.any() else float('nan'),
                avg_bars=float(np.mean([x['bars'] for x in trades if x['tag'] != 'hedge'])))


def run(make, P, name, group='', params=None, check=False, **kw):
    """evalkit.report (so numbers are comparable across tracks) plus the per-trade retention statistics."""
    _STASH.clear(); h.backtest = _bt
    try: o = evalkit.report(make, P, name=name, check=check, verbose=False, **kw)
    finally: h.backtest = _orig_backtest
    r = _STASH[0]; o['kept'] = retained(r.trades, P); o['group'] = group; o['params'] = params or {}
    pp = r.by('pair'); tot = sum(v['pnl'] for v in pp.values())
    top = sorted(pp.items(), key=lambda kv: -kv[1]['pnl'])[:3]
    o['top_pairs'] = [(P.pairs[k], float(v['pnl'])) for k, v in top]; o['pnl_total'] = float(tot)
    _STASH.clear()
    return o


def row(o):
    s, w, st, k = o['summary'], o['windows11'], o['stress'], o['kept']
    bs = o['by_side']; L = bs.get('long', {}).get('pnl', 0.); S = bs.get('short', {}).get('pnl', 0.)
    return dict(name=o['name'], group=o['group'], tot=s['total_return'], mdd=s['max_drawdown'], sharpe=s['sharpe'], sortino=s['sortino'],
                calmar=s['calmar'], comp=s['composite'], w11=w.get('mean', float('nan')), w11med=w.get('median', float('nan')),
                p10=w.get('p_ge_10', float('nan')), m10=w.get('p_le_m10', float('nan')), thirds=[t['total'] for t in o['thirds']],
                trades=s['trades'], win=s['win_rate'], to=s['turnover_x'], fill=s['limit_fill_rate'], active=s['active_day_share'],
                bars=s['avg_bars_held'], stress=st['total_return'], stress_w11=st['w11_mean'], long=L, short=S,
                kept=k.get('kept', float('nan')), kept_big=k.get('kept_big', float('nan')), mfe=k.get('avg_mfe', float('nan')))


HDR = '| variant | total | maxDD | Sharpe | Sortino | Calmar | 11d mean | 11d med | >=+10% | <=-10% | thirds | trades | win | t/o | active | stress tot | stress 11d | long P&L | short P&L | kept |'
SEP = '|' + '---|' * 20


def md(o, name=None):
    r = row(o) if 'summary' in o else o
    f = lambda x, p='+.1%': ('n/a' if x is None or not np.isfinite(x) else format(x, p))
    return (f"| {name or r['name']} | {f(r['tot'])} | {f(r['mdd'], '.0%')} | {f(r['sharpe'], '+.2f')} | {f(r['sortino'], '+.2f')} | {f(r['calmar'], '+.2f')} | "
            f"{f(r['w11'], '+.2%')} | {f(r['w11med'], '+.2%')} | {f(r['p10'], '.0%')} | {f(r['m10'], '.0%')} | {' '.join(f'{x:+.0%}' for x in r['thirds'])} | "
            f"{r['trades']} | {f(r['win'], '.0%')} | {r['to']:.0f}x | {f(r['active'], '.0%')} | {f(r['stress'])} | {f(r['stress_w11'], '+.2%')} | "
            f"{r['long']:+,.0f} | {r['short']:+,.0f} | {f(r['kept'], '+.0%')} |")


def line(o):
    r = row(o)
    return (f"{r['name'][:44]:44} tot {r['tot']:+7.1%} mdd {r['mdd']:4.0%} Sh {r['sharpe']:+5.2f} So {r['sortino']:+5.2f} Ca {r['calmar']:+5.2f} | 11d {r['w11']:+6.2%} med {r['w11med']:+6.2%} "
            f"| 3rds {' '.join(f'{x:+4.0%}' for x in r['thirds'])} | n {r['trades']:4d} win {r['win']:3.0%} to {r['to']:4.0f}x bars {r['bars']:5.1f} act {r['active']:3.0%} fill {r['fill']:4.0%} "
            f"| stress {r['stress']:+6.1%} {r['stress_w11'] or 0:+6.2%} | L {r['long']:+7.0f} S {r['short']:+7.0f} | kept {r['kept']:+5.0%} big {r['kept_big']:+5.0%}")


class Log:
    def __init__(self, path):
        self.path = HERE / path; self.rows = []
    def add(self, o):
        self.rows.append(o); print(line(o), flush=True)
    def save(self):
        json.dump(self.rows, open(self.path, 'w'), default=float)


W = {'fast': dict(fast=12, slow=55, trend=200), 'med': dict(fast=24, slow=100, trend=300), 'slow': dict(fast=48, slow=200, trend=0)}


def mk(w, side='long', slots=4, port=None, **k):
    """make(panel) for window set w (name or dict) with EmaX keyword overrides k and PortX overrides port."""
    wk = W[w] if isinstance(w, str) else w
    return lambda p: PortX(p, [EmaX(p, side=side, **{**wk, **k})], slots=slots, **(port or {}))
