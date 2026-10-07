"""Research harness for the Roostoo competition.

Hourly bars, long and short, maker/taker fees, resting limit orders, intrabar
stops. Decisions are made at the close of bar t from data up to and including
bar t; they execute during bar t+1. Read README.md before using it.
"""
from dataclasses import dataclass
from pathlib import Path
import math
import pickle
import numpy as np

LAB = Path(__file__).resolve().parent


@dataclass
class Costs:
    maker_bps: float = 5.0     # spot LIMIT order that rests and is filled
    taker_bps: float = 10.0    # spot MARKET order (and marketable limits, stops)
    short_bps: float = 10.0    # short open and short close; the API charges 0.1% for market and limit alike
    spread_mult: float = 1.0   # multiplier on each pair's measured half-spread
    slip_bps: float = 2.0      # extra adverse slippage on every market or stop fill
    stop_slip_bps: float = 15.0  # further overshoot on stops: bot-side market orders sent after a one-minute poll (minute-data estimate)
    through_bps: float = 2.0   # a resting limit fills only once price trades through it by the pair's full spread plus this


class Panel:
    """T x N hourly candles. O,H,L,C,V are (T,N) arrays; hs is each pair's half-spread as a fraction."""
    def __init__(self, ts, pairs, a, hs):
        self.ts = np.asarray(ts); self.pairs = list(pairs); self.a = np.asarray(a, float)
        self.O, self.H, self.L, self.C, self.V = (self.a[:, :, k] for k in range(5))
        self.T, self.N = self.C.shape; self.hs = np.asarray(hs, float)

    def i(self, pair):
        return self.pairs.index(pair)

    def mutated_after(self, cut, seed=0):
        """Copy whose candles from index `cut` on are an unrelated random path with unrelated candle shapes."""
        rng = np.random.default_rng(seed); a = self.a.copy(); n = self.T - cut; N = self.N
        r = rng.normal(0, .02, (n, N)); r[0] += rng.choice([-1., 1.], N) * rng.uniform(.05, .25, N)
        C = a[cut - 1, :, 3] * np.exp(np.cumsum(r, 0)); O = np.vstack([a[cut - 1:cut, :, 3], C[:-1]]) * np.exp(rng.normal(0, .002, (n, N)))
        H = np.maximum(O, C) * (1 + np.abs(rng.normal(0, .01, (n, N)))); L = np.minimum(O, C) * (1 - np.abs(rng.normal(0, .01, (n, N))))
        a[cut:, :, 0], a[cut:, :, 1], a[cut:, :, 2], a[cut:, :, 3] = O, H, L, C; a[cut:, :, 4] *= rng.uniform(.2, 5., (n, N))
        return Panel(self.ts, self.pairs, a, self.hs)


def load(name='design'):
    """'design' (first 60% of history), 'select' (first 80%), 'full', or 'early12' (12 majors, Oct 2024-May 2025)."""
    with open(LAB / 'data' / f'panel_{name}.pkl', 'rb') as f:
        ts, pairs, a, hs = pickle.load(f)
    return Panel(ts, pairs, a, hs)


@dataclass
class Order:
    pair: int               # column index in the panel
    kind: str               # 'BUY' | 'SELL' (spot long side) | 'SHORT' | 'COVER'
    usd: float = 0.         # BUY: dollars to spend. SHORT: collateral to lock. Ignored for SELL/COVER.
    frac: float = 1.        # SELL/COVER: fraction of the position to close
    limit: float = 0.       # BUY/SELL only. 0 = market at the next open; >0 = resting limit price
    ttl: int = 1            # bars a limit order rests before it expires
    fallback: str = 'cancel'  # at expiry: 'cancel', or 'market' (taker at the following open)
    stop: float = 0.        # protective stop level attached to the resulting position (0 = none)
    take: float = 0.        # take-profit level attached to the resulting position (0 = none)
    tag: str = ''           # free label, carried into the trade log


@dataclass
class Position:
    pair: int
    side: int               # +1 long, -1 short
    qty: float
    entry: float            # average entry price, before fees
    t_in: int
    tag: str = ''
    stop: float = 0.
    take: float = 0.
    collateral: float = 0.  # shorts only
    fees: float = 0.        # entry-side fees paid so far
    hi: float = 0.          # highest high since entry
    lo: float = 0.          # lowest low since entry
    born: int = -1          # bar index of the most recent limit fill into this position
    born_px: float = 0.     # price of that limit fill


class Book:
    """Account state. Strategies read it and may call set_stop / set_take / cancel."""
    def __init__(self, cash, panel, costs):
        self.cash = float(cash); self.P = panel; self.c = costs; self.pos = {}
        self.pending = []; self.trades = []; self.t = 0; self.equity = float(cash)
        self.fees = 0.; self.turnover = 0.; self.fills = []; self.limits_placed = 0; self.limits_filled = 0
        self.rejects = 0; self.orders_by_bar = {}

    # ---- helpers for strategies -------------------------------------------------
    @property
    def locked(self):
        return sum(o.usd for o, _ in self.pending if o.kind == 'BUY')

    @property
    def free_cash(self):
        return self.cash - self.locked

    def longs(self):
        return [p for p in self.pos.values() if p.side > 0]

    def shorts(self):
        return [p for p in self.pos.values() if p.side < 0]

    def set_stop(self, pair, level):
        if pair in self.pos: self.pos[pair].stop = float(level)

    def set_take(self, pair, level):
        if pair in self.pos: self.pos[pair].take = float(level)

    def cancel(self, pair=None):
        self.pending = [(o, e) for o, e in self.pending if pair is not None and o.pair != pair]

    def has_pending(self, pair):
        return any(o.pair == pair for o, _ in self.pending)

    # ---- fills ------------------------------------------------------------------
    def _fee(self, notional, bps, t):
        fee = notional * bps / 1e4; self.cash -= fee; self.fees += fee; self.turnover += notional
        self.fills.append(t); return fee

    def _open_long(self, o, price, bps, t, by_limit):
        p = self.pos.get(o.pair)
        if p is not None and p.side < 0: self.rejects += 1; return False      # one net position per pair
        spend = min(o.usd, max(0., (self.cash if by_limit else self.free_cash)) / (1 + bps / 1e4))
        if spend < 1.: self.rejects += 1; return False
        qty = spend / price; self.cash -= spend; fee = self._fee(spend, bps, t)
        if p is None:
            self.pos[o.pair] = Position(o.pair, 1, qty, price, t, o.tag, o.stop, o.take, 0., fee, price, price, t if by_limit else -1, price if by_limit else 0.)
        else:
            p.entry = (p.entry * p.qty + price * qty) / (p.qty + qty); p.qty += qty; p.fees += fee
            if o.stop: p.stop = max(p.stop, o.stop)                       # an add-on never loosens the existing stop
            if o.take: p.take = o.take
            if by_limit: p.born = t; p.born_px = price
        return True

    def _close(self, p, price, bps, t, reason, frac=1.):
        if not 0. < frac <= 1.: raise ValueError(f'frac must be in (0, 1], got {frac}')
        qty = p.qty * frac; notional = qty * price; share = qty / p.qty
        if p.side > 0:
            self.cash += notional; fee = self._fee(notional, bps, t); pnl = qty * (price - p.entry)
        else:
            pnl = max(-p.collateral * share, qty * (p.entry - price))   # a short cannot lose more than its collateral
            self.cash += p.collateral * share + pnl; fee = self._fee(notional, bps, t)
        entry_fee = p.fees * share
        self.trades.append(dict(pair=p.pair, side=p.side, tag=p.tag, t_in=p.t_in, t_out=t, entry=p.entry, exit=price,
                                qty=qty, pnl=pnl - fee - entry_fee, ret=(pnl - fee - entry_fee) / (qty * p.entry),
                                bars=t - p.t_in, reason=reason))
        p.fees -= entry_fee; p.collateral -= p.collateral * share; p.qty -= qty
        if frac >= 1. or p.qty * price < 1.:
            del self.pos[p.pair]                                         # a resting sale dies with its position
            self.pending = [(o, e) for o, e in self.pending if not (o.pair == p.pair and o.kind == 'SELL')]

    def _market(self, o, t):
        P, c = self.P, self.c; i = o.pair; adj = P.hs[i] * c.spread_mult + c.slip_bps / 1e4
        ask = P.O[t, i] * (1 + adj); bid = P.O[t, i] * (1 - adj); p = self.pos.get(i)
        if o.kind == 'BUY':
            if p is not None and p.side < 0: self.rejects += 1; return
            self._open_long(o, ask, c.taker_bps, t, False)
        elif o.kind == 'SELL':
            if p is None or p.side < 0: self.rejects += 1; return
            self._close(p, bid, c.taker_bps, t, 'signal', o.frac)
        elif o.kind == 'SHORT':
            if p is not None or any(q.pair == i and q.kind == 'BUY' for q, _ in self.pending): self.rejects += 1; return
            collateral = min(o.usd, max(0., self.free_cash) / (1 + c.short_bps / 1e4))
            if collateral < 1.: self.rejects += 1; return
            qty = collateral / bid; self.cash -= collateral; fee = self._fee(collateral, c.short_bps, t)
            self.pos[i] = Position(i, -1, qty, bid, t, o.tag, o.stop, o.take, collateral, fee, bid, bid)
        elif o.kind == 'COVER':
            if p is None or p.side > 0: self.rejects += 1; return
            self._close(p, ask, c.short_bps, t, 'signal', o.frac)
        else:
            raise ValueError(f'unknown order kind {o.kind}')

    def process_bar(self, t, new_orders):
        """Everything that happens during bar t: opens, resting limits, then stops and targets."""
        P, c = self.P, self.c; O, H, L = P.O[t], P.H[t], P.L[t]; prev = P.C[t - 1]
        if len(new_orders) > 60: raise ValueError('more than 60 orders in one hour breaks the one-order-per-minute rule')
        self.orders_by_bar[t] = len(new_orders)
        for o, expiry in [x for x in self.pending if x[1] < t]:      # expired last bar
            if (o, expiry) not in self.pending: continue                # pruned when its position closed a moment ago
            self.pending.remove((o, expiry))
            if o.fallback == 'market': self._market(o, t)
        for o in new_orders:
            if not all(math.isfinite(x) for x in (o.usd, o.frac, o.limit, o.stop, o.take)): raise ValueError(f'non-finite field in {o}')
            if o.limit <= 0 or o.kind in ('SHORT', 'COVER'):
                self._market(o, t)
            elif (o.kind == 'BUY' and o.limit >= prev[o.pair]) or (o.kind == 'SELL' and o.limit <= prev[o.pair]):
                self._market(o, t)                                    # marketable at placement: executes as a taker
            else:
                held = self.pos.get(o.pair)
                if o.kind == 'BUY':
                    if held is not None and held.side < 0: self.rejects += 1; continue
                    o.usd = min(o.usd, max(0., self.free_cash) / (1 + c.maker_bps / 1e4))
                    if o.usd < 1.: self.rejects += 1; continue
                elif held is None or held.side < 0:
                    self.rejects += 1; continue
                self.pending.append((o, t + max(1, o.ttl) - 1)); self.limits_placed += 1
        for o, expiry in list(self.pending):
            if (o, expiry) not in self.pending: continue                # removed when its position closed earlier in this loop
            i = o.pair; thr = 2 * P.hs[i] * c.spread_mult + c.through_bps / 1e4; p = self.pos.get(i)
            if o.kind == 'BUY' and min(O[i], L[i]) <= o.limit * (1 - thr):
                self.pending.remove((o, expiry))
                if self._open_long(o, o.limit, c.maker_bps, t, True): self.limits_filled += 1
            elif o.kind == 'SELL' and max(O[i], H[i]) >= o.limit * (1 + thr):
                # Same pessimistic ordering as take-profits: never in the bar a limit entry filled, and a stop touched in the bar wins.
                if p is None or p.side < 0 or p.born == t or (p.stop > 0 and L[i] <= p.stop and O[i] < o.limit): continue
                self.pending.remove((o, expiry)); self.limits_filled += 1; self._close(p, o.limit, c.maker_bps, t, 'limit', o.frac)
        for i, p in list(self.pos.items()):
            adj = P.hs[i] * c.spread_mult + c.slip_bps / 1e4; over = c.stop_slip_bps / 1e4
            thr = 2 * P.hs[i] * c.spread_mult + c.through_bps / 1e4
            if p.side > 0:
                if p.stop > 0 and L[i] <= p.stop:
                    # Exit no higher than the stop, the open, or (for a limit fill in this bar) the fill price itself.
                    px = min(p.stop, O[i], p.born_px) if p.born == t else min(p.stop, O[i])
                    self._close(p, px * (1 - adj - over), c.taker_bps, t, 'stop'); continue
                if p.take > 0 and p.born != t and max(O[i], H[i]) >= p.take * (1 + thr):
                    self._close(p, p.take, c.maker_bps, t, 'take'); continue
            else:
                if p.stop > 0 and H[i] >= p.stop:
                    self._close(p, max(p.stop, O[i]) * (1 + adj + over), c.short_bps, t, 'stop'); continue
                if p.take > 0 and L[i] <= p.take:
                    self._close(p, min(p.take, O[i]) * (1 + adj + over), c.short_bps, t, 'take'); continue
            if p.born != t: p.hi = max(p.hi, H[i])                     # a limit fill may have come after the bar's high
            p.lo = min(p.lo, L[i])
        # Orders that used up their time and will not trade again are gone before the strategy looks at the book.
        self.pending = [(o, e) for o, e in self.pending if e > t or o.fallback == 'market']

    def mark(self, t):
        P, c = self.P, self.c; value = self.cash
        for i, p in self.pos.items():
            adj = P.hs[i] * c.spread_mult
            value += p.qty * P.C[t, i] * (1 - adj) if p.side > 0 else max(0., p.collateral + p.qty * (p.entry - P.C[t, i] * (1 + adj)))
        self.equity = value; return value


class Result:
    def __init__(self, eq, book, start, order_log, state_log):
        self.eq = eq; self.trades = book.trades; self.start = start; self.order_log = order_log; self.state_log = state_log
        self.fees = book.fees; self.turnover = book.turnover; self.rejects = book.rejects
        self.limit_fill_rate = book.limits_filled / book.limits_placed if book.limits_placed else float('nan')
        day = book.P.ts // 86_400_000                                   # UTC calendar days
        self.active_days = len({int(day[t]) for t in book.fills}); self.days = int(day[start + len(eq) - 1] - day[start]) + 1
        self.max_orders_per_hour = max(book.orders_by_bar.values(), default=0)

    def summary(self):
        s = summary(self.eq); tr = self.trades; wins = [x['pnl'] for x in tr if x['pnl'] > 0]; losses = [x['pnl'] for x in tr if x['pnl'] <= 0]
        s.update(trades=len(tr), win_rate=len(wins) / len(tr) if tr else float('nan'),
                 avg_win=float(np.mean(wins)) if wins else 0., avg_loss=float(np.mean(losses)) if losses else 0.,
                 profit_factor=sum(wins) / -sum(losses) if losses and sum(losses) < 0 else float('nan'),
                 fees=self.fees, turnover_x=self.turnover / self.eq[0], limit_fill_rate=self.limit_fill_rate,
                 active_day_share=self.active_days / max(1., self.days), avg_bars_held=float(np.mean([x['bars'] for x in tr])) if tr else 0.)
        return s

    def by(self, key):
        """Net P&L, trade count and win rate grouped by a trade field ('tag', 'side', 'reason', 'pair')."""
        out = {}
        for x in self.trades:
            g = out.setdefault(x[key], dict(n=0, pnl=0., wins=0)); g['n'] += 1; g['pnl'] += x['pnl']; g['wins'] += x['pnl'] > 0
        return {k: dict(n=v['n'], pnl=v['pnl'], win_rate=v['wins'] / v['n'], avg_ret=float(np.mean([x['ret'] for x in self.trades if x[key] == k]))) for k, v in out.items()}

    def windows(self, days=11, step=24):
        return windows(self.eq, days, step)


def backtest(panel, strategy, costs=None, start=0, end=None, cash=100_000.):
    """Run `strategy` (an object with on_bar(t, book) -> list[Order]) from bar `start` to `end`."""
    c = costs or Costs(); end = panel.T if end is None else end
    book = Book(cash, panel, c); eq = np.empty(end - start); orders = []; log = []; state = []
    for t in range(start, end):
        book.t = t
        if t > start: book.process_bar(t, orders)
        eq[t - start] = book.mark(t)
        orders = list(strategy.on_bar(t, book) or []) if t < end - 1 else []
        for o in orders: log.append((t, o.pair, o.kind, round(o.usd, 2), round(o.frac, 4), float(f'{o.limit:.6g}'), o.ttl, float(f'{o.stop:.6g}'), float(f'{o.take:.6g}')))
        # Stops, targets and resting orders are decisions too: record them so the look-ahead test sees them.
        state.append((t, tuple(sorted((i, float(f'{p.stop:.6g}'), float(f'{p.take:.6g}')) for i, p in book.pos.items())),
                      tuple(sorted((o.pair, o.kind, float(f'{o.limit:.6g}'), e) for o, e in book.pending))))
    return Result(eq, book, start, log, state)


def summary(eq):
    """Competition-style metrics from an hourly equity curve (daily returns, 365-day year)."""
    eq = np.asarray(eq, float); total = eq[-1] / eq[0] - 1; peak = np.maximum.accumulate(eq); mdd = float((1 - eq / peak).max())
    daily = eq[::24]; r = daily[1:] / daily[:-1] - 1; days = (len(eq) - 1) / 24
    vol = r.std(ddof=1) if len(r) > 1 else 0.; down = math.sqrt(float((np.minimum(0, r) ** 2).mean())) if len(r) else 0.
    ann = (1 + total) ** (365 / days) - 1 if days > 0 and total > -1 else -1.
    sharpe = r.mean() / vol * math.sqrt(365) if vol > 1e-12 else float('nan')
    sortino = r.mean() / down * math.sqrt(365) if down > 1e-12 else float('nan')
    calmar = ann / mdd if mdd > 1e-9 else float('nan')
    return dict(total_return=float(total), annualized=float(ann), max_drawdown=mdd, sharpe=float(sharpe), sortino=float(sortino),
                calmar=float(calmar), composite=float(.4 * sortino + .3 * sharpe + .3 * calmar), days=days)


def windows(eq, days=11, step=24):
    """Return and max drawdown of every `days`-long stretch of one continuous equity curve."""
    eq = np.asarray(eq, float); n = days * 24; out = []
    for s in range(0, len(eq) - n, step):
        w = eq[s:s + n + 1]; out.append((w[-1] / w[0] - 1, float((1 - w / np.maximum.accumulate(w)).max())))
    a = np.array(out)
    if not len(a): return {}
    r, m = a[:, 0], a[:, 1]
    return dict(n=len(r), mean=float(r.mean()), median=float(np.median(r)), p10=float(np.percentile(r, 10)), p90=float(np.percentile(r, 90)),
                worst=float(r.min()), best=float(r.max()), win=float((r > 0).mean()), p_ge_1p5=float((r >= .015).mean()),
                p_ge_5=float((r >= .05).mean()), p_ge_10=float((r >= .10).mean()), p_le_m5=float((r <= -.05).mean()),
                p_le_m10=float((r <= -.10).mean()), mdd_mean=float(m.mean()), mdd_worst=float(m.max()))


def fresh_windows(panel, make_strategy, costs=None, days=11, step_days=4, start=0, end=None):
    """Like windows(), but restarts the strategy flat with fresh cash for every window (slower, closer to a new competition)."""
    end = panel.T if end is None else end; n = days * 24; curves = []
    for s in range(start, end - n, step_days * 24):
        curves.append(backtest(panel, make_strategy(panel), costs, s, s + n + 1).eq)
    r = np.array([c[-1] / c[0] - 1 for c in curves]); m = np.array([(1 - c / np.maximum.accumulate(c)).max() for c in curves])
    return dict(n=len(r), mean=float(r.mean()), median=float(np.median(r)), worst=float(r.min()), best=float(r.max()), win=float((r > 0).mean()),
                p_ge_1p5=float((r >= .015).mean()), p_ge_10=float((r >= .10).mean()), p_le_m5=float((r <= -.05).mean()),
                p_le_m10=float((r <= -.10).mean()), mdd_mean=float(m.mean()), mdd_worst=float(m.max()))


def causality_check(make_strategy, panel, cuts=40, warm=400, costs=None, start=744):
    """Look-ahead detector. Returns (ok, detail).

    At each of `cuts` cut points, every candle from the cut onward is replaced by an unrelated random path and the
    strategy is rebuilt on that altered panel. Every decision before the cut (orders, stop and target levels, resting
    orders) must be identical on both panels. Cuts are placed right after bars where the strategy was actually in the
    market or acting (found with one ordinary run from `start`), so sparse strategies are tested where they are exposed.
    Each short run starts `warm` bars before its cut; one extra pair of runs covers the whole stretch from `start`.

    What a pass means: nothing built inside make_strategy(panel) uses future rows, with high probability. It does NOT
    cover arrays computed outside make_strategy and captured by it (a filter precomputed on the full panel passes):
    build everything inside. A slip of k bars only shows in the k bars before a cut, so detection is probabilistic.
    The check fails if the strategy never acted, or never reacted to the panel it was given.
    """
    base = backtest(panel, make_strategy(panel), costs, start, panel.T)
    busy = sorted({x[0] for x in base.order_log} | {x[0] for x in base.state_log if x[1] or x[2]})
    busy = [t for t in busy if start + 5 <= t < panel.T - 2]
    if not busy:
        return False, dict(reason='the strategy never acted, so nothing was checked')
    picks = [busy[i] + 1 for i in np.linspace(0, len(busy) - 1, cuts).astype(int)]   # cut just after an active bar

    def differ(a, b, cut):
        if a.order_log != b.order_log:
            for x, y in zip(a.order_log, b.order_log):
                if x != y: return dict(cut=cut, kind='order', original=x, altered=y)
            return dict(cut=cut, kind='order count', original=len(a.order_log), altered=len(b.order_log))
        sa = [x for x in a.state_log if x[0] < cut]; sb = [x for x in b.state_log if x[0] < cut]   # bar `cut` itself is altered
        if sa != sb:
            x, y = next((x, y) for x, y in zip(sa, sb) if x != y)
            return dict(cut=cut, kind='stop/target/resting order', original=x, altered=y)
        return None

    for k, cut in enumerate(picks):
        other = panel.mutated_after(cut, seed=k); lo = max(start, cut - warm)
        d = differ(backtest(panel, make_strategy(panel), costs, lo, cut + 1), backtest(other, make_strategy(other), costs, lo, cut + 1), cut)
        if d: return False, d
    cut = picks[-1]; other = panel.mutated_after(cut, seed=777)                      # one comparison over the strategy's whole life
    d = differ(backtest(panel, make_strategy(panel), costs, start, cut + 1), backtest(other, make_strategy(other), costs, start, cut + 1), cut)
    if d: return False, dict(d, run='from start')
    reacted = False                                                                    # same prices, features from an altered panel
    for k in (len(picks) // 5, len(picks) // 2, len(picks) * 4 // 5):
        cut = picks[k]; other = panel.mutated_after(cut, seed=900 + k); lo = max(start, cut - warm); hi = min(panel.T, cut + 3 * warm)
        a = backtest(panel, make_strategy(panel), costs, lo, hi); b = backtest(panel, make_strategy(other), costs, lo, hi)
        if a.order_log != b.order_log or a.state_log != b.state_log: reacted = True; break
    if not reacted:
        return False, dict(reason='no reaction to the panel passed to make_strategy was observed; build every feature inside make(panel)')
    return True, None
