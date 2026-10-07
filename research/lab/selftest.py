"""Accounting, fill-model and look-ahead checks for the harness. Run: python selftest.py"""
import numpy as np
import harness as h
from harness import Order, Panel, Costs, backtest
import ind, baselines

def flat_panel(closes, highs=None, lows=None, opens=None):
    c = np.array(closes, float)[:, None]; o = np.array(opens, float)[:, None] if opens is not None else np.vstack([c[:1], c[:-1]])
    hi = np.array(highs, float)[:, None] if highs is not None else np.maximum(o, c); lo = np.array(lows, float)[:, None] if lows is not None else np.minimum(o, c)
    a = np.stack([o, hi, lo, c, np.ones_like(c)], -1); return Panel(np.arange(len(c)) * 3600000, ['X/USD'], a, [0.])

class Script:
    def __init__(self, plan): self.plan = plan
    def on_bar(self, t, book): return self.plan.get(t, [])

Z = Costs(maker_bps=5, taker_bps=10, short_bps=10, slip_bps=0, stop_slip_bps=0, through_bps=0)
# 1. API guide short example: 10,000 collateral at 50,000, cover at 48,000 -> fee 10, pnl 400, close fee 9.6
p = flat_panel([50000, 50000, 48000, 48000], opens=[50000, 50000, 48000, 48000])
r = backtest(p, Script({0: [Order(0, 'SHORT', usd=10000)], 1: [Order(0, 'COVER')]}), Z)
assert abs(r.eq[-1] - (100000 - 10 + 400 - 9.6)) < 1e-6, r.eq[-1]
# 2. market round trip: buy at open 100, sell at open 110, taker both sides
p = flat_panel([100, 100, 110, 110], opens=[100, 100, 110, 110])
r = backtest(p, Script({0: [Order(0, 'BUY', usd=10000)], 1: [Order(0, 'SELL')]}), Z)
assert abs(r.eq[-1] - (100000 - 10 + 1000 - 11)) < 1e-6, r.eq[-1]
assert abs(sum(x['pnl'] for x in r.trades) - (r.eq[-1] - 100000)) < 1e-6
# 3. limit buy below market fills only when traded through, at the limit, with the maker fee
p = flat_panel([100, 100, 100, 100], lows=[100, 99.5, 98.9, 100], opens=[100, 100, 100, 100])
r = backtest(p, Script({0: [Order(0, 'BUY', usd=9900, limit=99., ttl=5)]}), Z)
assert len(r.trades) == 0 and abs(r.eq[-1] - (100000 - 4.95 + 100 * 1.)) < 1e-6 and r.limit_fill_rate == 1., (r.eq[-1], r.limit_fill_rate)
r = backtest(p, Script({0: [Order(0, 'BUY', usd=9900, limit=99., ttl=1)]}), Z)
assert r.eq[-1] == 100000 and r.limit_fill_rate == 0.            # low 99.5 in the only live bar: no fill
r = backtest(p, Script({0: [Order(0, 'BUY', usd=9900, limit=99., ttl=1, fallback='market')]}), Z)
assert abs(r.eq[-1] - (100000 - 9.9)) < 1e-6                     # unfilled, then taker at the next open (100)
# 4. marketable limit is a taker; stop fills at the stop, gap fills at the open
r = backtest(p, Script({0: [Order(0, 'BUY', usd=10000, limit=101.)]}), Z); assert abs(r.fees - 10) < 1e-9
p = flat_panel([100, 100, 95, 95], lows=[100, 100, 94, 95], opens=[100, 100, 99, 95])
r = backtest(p, Script({0: [Order(0, 'BUY', usd=10000, stop=97.)]}), Z)
assert r.trades[0]['reason'] == 'stop' and abs(r.trades[0]['exit'] - 97) < 1e-9
p = flat_panel([100, 100, 95, 95], lows=[100, 100, 94, 95], opens=[100, 100, 96, 95])
r = backtest(p, Script({0: [Order(0, 'BUY', usd=10000, stop=97.)]}), Z); assert abs(r.trades[0]['exit'] - 96) < 1e-9
# 5. take-profit on a long is a maker sale at the target; never in the bar a limit entry filled
p = flat_panel([100, 100, 100, 104], highs=[100, 100, 103, 104], lows=[100, 98, 100, 100], opens=[100, 100, 100, 100])
r = backtest(p, Script({0: [Order(0, 'BUY', usd=10000, take=102.)]}), Z); assert r.trades[0]['reason'] == 'take' and r.trades[0]['t_out'] == 2
p2 = flat_panel([100, 100, 100, 104], highs=[100, 103, 103, 104], lows=[100, 98, 100, 100], opens=[100, 100, 100, 100])
r = backtest(p2, Script({0: [Order(0, 'BUY', usd=9900, limit=99., take=102.)]}), Z); assert r.trades[0]['t_out'] == 2, r.trades
# 6. short stop and capped loss
p = flat_panel([100, 100, 130, 130], highs=[100, 100, 131, 130], opens=[100, 100, 100, 130])
r = backtest(p, Script({0: [Order(0, 'SHORT', usd=10000, stop=110.)]}), Z); assert abs(r.trades[0]['exit'] - 110) < 1e-9 and r.trades[0]['pnl'] < -1000
p = flat_panel([100, 100, 250, 250], opens=[100, 100, 250, 250])
r = backtest(p, Script({0: [Order(0, 'SHORT', usd=10000)], 1: [Order(0, 'COVER')]}), Z); assert abs(r.eq[-1] - (100000 - 10 - 10000 - 25)) < 1e-6, r.eq[-1]
# 6b. audit regressions
# a stop above a same-bar limit fill cannot sell above the fill; a gap through the stop on an add-on fill uses the open
p = flat_panel([100, 100, 100, 100], lows=[100, 98, 100, 100], opens=[100, 100, 100, 100])
r = backtest(p, Script({0: [Order(0, 'BUY', usd=9900, limit=99., stop=99.5)]}), Z)
assert r.trades[0]['reason'] == 'stop' and abs(r.trades[0]['exit'] - 99.) < 1e-9 and r.trades[0]['pnl'] < 0, r.trades
p = flat_panel([100, 100, 80, 80], highs=[100, 100, 80, 80], lows=[100, 100, 80, 80], opens=[100, 100, 80, 80])
r = backtest(p, Script({0: [Order(0, 'BUY', usd=10000, stop=95.)], 1: [Order(0, 'BUY', usd=1000, limit=96., ttl=3)]}), Z)
assert all(abs(x['exit'] - 80.) < 1e-9 for x in r.trades), r.trades
# a resting SELL limit loses to a stop touched in the same bar, and never fills in the bar its limit entry filled
p = flat_panel([100, 100, 100, 100], highs=[100, 100, 103, 100], lows=[100, 100, 97, 100], opens=[100, 100, 100, 100])
r = backtest(p, Script({0: [Order(0, 'BUY', usd=10000, stop=98.)], 1: [Order(0, 'SELL', limit=102., ttl=3)]}), Z)
assert r.trades[0]['reason'] == 'stop' and abs(r.trades[0]['exit'] - 98) < 1e-9, r.trades
# a resting SELL dies with its position; an expired limit is invisible to the strategy; a limit BUY cannot merge into a short
r = backtest(flat_panel([100] * 6, lows=[100, 100, 97, 100, 100, 100], highs=[100, 100, 100, 100, 100, 104]),
             Script({0: [Order(0, 'BUY', usd=10000, stop=98.)], 1: [Order(0, 'SELL', limit=103., ttl=9)], 3: [Order(0, 'BUY', usd=10000)]}), Z)
assert len(r.trades) == 1 and r.trades[0]['reason'] == 'stop', r.trades
class Peek:
    def __init__(self): self.seen = []
    def on_bar(self, t, book):
        self.seen.append((t, book.has_pending(0), round(book.free_cash))); return [Order(0, 'BUY', usd=5000, limit=90., ttl=1)] if t == 0 else []
pk = Peek(); backtest(flat_panel([100] * 4), pk, Z); assert pk.seen[1] == (1, False, 100000), pk.seen
r = backtest(flat_panel([100, 100, 100, 100], lows=[100, 100, 98, 100]), Script({0: [Order(0, 'SHORT', usd=10000)], 1: [Order(0, 'BUY', usd=5000, limit=99., ttl=5)]}), Z)
assert r.rejects == 1 and abs(r.eq[-1] - 99990) < 1e-6, (r.rejects, r.eq[-1])
r = backtest(flat_panel([100, 100, 100, 100], lows=[100, 100, 98, 100]), Script({0: [Order(0, 'BUY', usd=5000, limit=99., ttl=5)], 1: [Order(0, 'SHORT', usd=10000)]}), Z)
assert r.rejects == 1 and not any(x.side < 0 for x in []), r.rejects
for bad in (-1., 0., 1.5):
    try: backtest(flat_panel([100] * 4), Script({0: [Order(0, 'BUY', usd=10000)], 1: [Order(0, 'SELL', frac=bad)]}), Z); raise SystemExit('frac not validated')
    except ValueError: pass
# the trade-through threshold includes the pair's spread
pp = flat_panel([100, 100, 100, 100], lows=[100, 98.99, 100, 100]); pp.hs = np.array([.001])
r = backtest(pp, Script({0: [Order(0, 'BUY', usd=9900, limit=99., ttl=1)]}), Costs(slip_bps=0, stop_slip_bps=0, through_bps=0)); assert r.limit_fill_rate == 0.
# indicators survive another indicator's warm-up
xx = np.cumsum(np.random.default_rng(1).normal(0, 1, (400, 3)), 0) + 100
assert np.isfinite(ind.sma(ind.rsi(xx, 14), 20)[60:]).all() and np.isfinite(ind.ema(ind.sma(xx, 10), 5)[30:]).all() and np.isnan(ind.sma(ind.rsi(xx, 14), 20)[:33]).all()
# 7. real data: equity identity, baseline, look-ahead detector
P = h.load('full'); make = lambda panel: baselines.Breakout(panel)
r = backtest(P, make(P)); s = r.summary(); w = r.windows(11)
open_pnl = r.eq[-1] - 100000 - sum(x['pnl'] for x in r.trades)
print('breakout full history:', {k: round(v, 4) for k, v in s.items() if k in ('total_return', 'max_drawdown', 'trades', 'win_rate', 'turnover_x', 'active_day_share')}, 'open pnl', round(open_pnl))
print('  rolling 11d windows:', {k: round(v, 4) for k, v in w.items()})
fw = h.fresh_windows(P, make, step_days=1, start=744); print('  fresh-start 11d windows:', {k: round(v, 4) for k, v in fw.items()})
ok, diff = h.causality_check(make, P); assert ok, diff
class Cheat:
    def __init__(self, panel): self.P = panel
    def on_bar(self, t, book):
        up = self.P.C[min(t + 1, self.P.T - 1), 0] > self.P.C[t, 0]
        if up and 0 not in book.pos: return [Order(0, 'BUY', usd=1000)]
        return [Order(0, 'SELL')] if not up and 0 in book.pos else []
ok, diff = h.causality_check(lambda panel: Cheat(panel), P); assert not ok, 'one-bar peek not detected'
class Scaler:  # full-sample statistic: a subtler leak
    def __init__(self, panel): self.P = panel; self.z = (panel.C[:, 0] - panel.C[:, 0].mean()) / panel.C[:, 0].std()
    def on_bar(self, t, book):
        if self.z[t] < -1 and 0 not in book.pos: return [Order(0, 'BUY', usd=1000)]
        return [Order(0, 'SELL')] if self.z[t] > 0 and 0 in book.pos else []
ok, diff = h.causality_check(lambda panel: Scaler(panel), P); assert not ok, 'full-sample leak not detected'
class PeekGreen:  # scale-free peek: will the next candle close above its open?
    def __init__(self, panel): self.P = panel
    def on_bar(self, t, book):
        n = min(t + 1, self.P.T - 1); up = self.P.C[n, 0] > self.P.O[n, 0]
        if up and 0 not in book.pos: return [Order(0, 'BUY', usd=1000)]
        return [Order(0, 'SELL')] if not up and 0 in book.pos else []
ok, diff = h.causality_check(lambda panel: PeekGreen(panel), P); assert not ok, 'candle-shape peek not detected'
class StopPeek:  # look-ahead that acts only through set_stop
    def __init__(self, panel): self.P = panel
    def on_bar(self, t, book):
        if 0 not in book.pos: return [Order(0, 'BUY', usd=1000)]
        book.set_stop(0, self.P.L[min(t + 1, self.P.T - 1), 0] * .999); return []
ok, diff = h.causality_check(lambda panel: StopPeek(panel), P); assert not ok and diff['kind'].startswith('stop'), diff
class Idle:
    def __init__(self, panel): pass
    def on_bar(self, t, book): return []
ok, diff = h.causality_check(lambda panel: Idle(panel), P, cuts=4); assert not ok and 'never acted' in diff['reason']
class ExitSlip(baselines.Breakout):  # sparse strategy whose exit peeks one bar ahead
    def on_bar(self, t, book):
        keep = self.P.C; self.P.C = np.vstack([keep[1:], keep[-1:]]) if False else keep
        out = []
        for p in book.longs():
            if self.P.C[min(t + 1, self.P.T - 1), p.pair] <= max(p.hi, p.entry) * (1 - self.trail): out.append(Order(p.pair, 'SELL', tag='x')); self.locked[p.pair] = t + self.lock_bars
        held = len(book.pos) - len(out); r = self.r24[t]
        for i in np.argsort(-np.nan_to_num(r, nan=-9)):
            if held >= self.slots or not r[i] >= self.move: break
            if i in book.pos or self.locked.get(i, -1) > t or self.P.C[t, i] < self.top[t, i] * .999: continue
            out.append(Order(int(i), 'BUY', usd=book.equity * self.expo / self.slots, tag='x')); held += 1
        return out
ok, diff = h.causality_check(lambda panel: ExitSlip(panel, slots=1, move=.25), P); assert not ok, 'sparse exit slip not detected'
r = backtest(flat_panel([100] * 6, highs=[100] * 6), Script({0: [Order(0, 'BUY', usd=10000)], 1: [Order(0, 'SELL', limit=110., ttl=2, fallback='market'), Order(0, 'SELL', limit=105., frac=.5, ttl=2, fallback='market')]}), Z); assert len(r.trades) >= 1
frozen = baselines.Breakout(P)
ok, diff = h.causality_check(lambda panel: baselines.Breakout(P), P, cuts=4); assert not ok and 'no reaction' in diff['reason'], diff
r = backtest(P, baselines.BuyHold(P)); print('BTC buy and hold:', round(r.summary()['total_return'], 4), 'vs raw', round(P.C[-1, P.i('BTC/USD')] / P.O[1, P.i('BTC/USD')] - 1, 4))
x = np.cumsum(np.random.default_rng(0).normal(0, 1, (300, 2)), 0) + 100
assert np.allclose(ind.sma(x, 5)[10], x[6:11].mean(0)) and np.allclose(ind.rstd(x, 5)[10], x[6:11].std(0)) and np.allclose(ind.rmax(x, 7)[20], x[14:21].max(0))
assert np.allclose(ind.wma(x, 3)[10], (x[8] + 2 * x[9] + 3 * x[10]) / 6) and np.allclose(ind.ema([[110.], [112.], [115.], [114.], [118.], [120.]] and np.array([[110.], [112.], [115.], [114.], [118.], [120.]]), 5)[5], 115.8667, atol=1e-3)
print('ALL CHECKS PASSED')
