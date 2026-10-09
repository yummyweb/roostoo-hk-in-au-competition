"""The team's regime strategy: a per-coin regime label picks the leg.

  BULL coin : EMA crossover, long   - buy within `ema_fresh_bars` of the fast EMA crossing above the slow one
  BEAR coin : EMA crossover, short  - short within `ema_fresh_bars` of the fast EMA crossing below the slow one
  CHOP coin : z-score mean reversion - buy at z <= -mr_entry_z, short at z >= +mr_entry_z
  BEAR coin : steep-drop buy        - buy a bar that closes crash_drop below the previous close (if switched on)

Entries and the slow exits are decided once per hour from the completed candle. `decide` is the single
implementation: the live runner calls it, and the research harness calls it through research/lab/work/live_legs/,
so both trade the same rule. `watch` holds the exits the runner checks every minute on live quotes.
"""
EMA,MR,CRASH='ema','mr','crash'
TIE=1e-9    # prices sit on a tick grid: a close within this (relative) of the trailing level counts as at it


def decide(features,labels,book,locks,c,bar):
    """One hourly decision.

    features: pair -> Indicators row of the completed candle (close, bar_high, bar_low, atr_24, ema_fast, ema_slow,
              age_up, age_down, z, ready).
    labels:   pair -> 'BULL' | 'BEAR' | 'CHOP' | None.
    book:     pair -> open position {'leg', 'side' (+1 long, -1 short), 'entry', 'bar' (index of the bar it filled in),
              'high', 'low', 'level'}. Water marks and trailing levels are updated in place.
    locks:    pair -> first bar at which the pair may be entered again; updated in place.
    bar:      index of the completed candle.
    Returns (exits, entries): exits is a list of pairs to close in full; entries is a list of
    (pair, side, leg, equity_weight) in priority order. Exits never depend on the label.
    """
    exits=[];held={EMA:0,MR:0}
    for pair,p in book.items():
        f=features[pair];close=f['close'];side=p['side']
        p['high']=max(p['high'],f['bar_high']);p['low']=min(p['low'],f['bar_low'])
        if p['leg']==EMA:
            fast,slow,atr=f['ema_fast'],f['ema_slow'],f['atr_24']
            if c.pullback:   # entered against the short-term move, so the averages crossing back is no signal: it has a time limit
                if bar-p['bar']>=c.max_hold_bars:exits.append(pair);locks[pair]=bar+c.cooldown_bars;continue
            elif fast is not None and slow is not None and (fast<slow if side>0 else fast>slow):
                exits.append(pair);locks[pair]=bar+c.cooldown_bars;continue      # the cross that opened it has reversed
            if c.stop_loss:hit=False   # a fixed stop-loss and the profit lock in watch() replace the ATR trail
            elif side>0:   # the trailing level only ever tightens
                p['level']=max(p['level'] or 0.,max(p['high'],close)-c.stop_atr*atr);hit=close<=p['level']*(1+TIE)
            else:
                p['level']=min(p['level'] or float('inf'),min(p['low'],close)+c.stop_atr*atr);hit=close>=p['level']*(1-TIE)
            if hit:exits.append(pair);continue
        elif p['leg']==MR:
            z=f['z'];back=z is not None and (z>=0 if side>0 else z<=0)
            against=close<=p['entry']*(1-c.mr_stop) if side>0 else close>=p['entry']*(1+c.mr_stop)
            if back or against or bar-p['bar']>=c.mr_hold_bars:
                exits.append(pair);locks[pair]=bar+1+c.mr_cooldown_bars;continue
        elif bar-p['bar']>=c.mr_hold_bars:                                           # a steep-drop buy: only its time limit is judged here
            exits.append(pair);locks[pair]=bar+1+c.mr_cooldown_bars;continue
        held[EMA if p['leg']==EMA else MR]+=1                                        # a steep-drop buy uses a mean-reversion slot
    entries=[];taken=set()
    def free(pair):
        return pair not in book and pair not in taken and locks.get(pair,-1)<=bar and features[pair].get('ready')
    crashes=[(f['close']/f['bar_high']-1,pair) for pair,f in sorted(features.items())
             if c.crash_drop and labels.get(pair)=='BEAR' and free(pair) and f['close']<=f['bar_high']*(1-c.crash_drop)]
    for _,pair in sorted(crashes):                                                # steepest drop first
        if held[MR]>=c.mr_slots:break
        entries.append((pair,1,CRASH,c.mr_fraction));taken.add(pair);held[MR]+=1
    trend=[]
    for pair in sorted(features):
        f=features[pair]
        if not free(pair) or f['ema_fast'] is None or f['ema_slow'] is None or not f['atr_24']>0:continue
        if abs(f['ema_fast']-f['ema_slow'])<c.ema_min_gap*f['close']:continue           # a hairline cross is not a trend yet
        gap=(f['ema_fast']-f['ema_slow'])/f['atr_24']
        if c.pullback:                                                                  # enter a trend on a move against it, the larger first
            move=f.get('momentum',0.)
            if gap<0 and move>=c.pullback and labels.get(pair)=='BEAR' and c.allow_short:trend.append((-move,pair,-1))
            elif gap>0 and move<=-c.pullback and labels.get(pair)=='BULL':trend.append((move,pair,1))
            continue
        if gap>0 and f['age_up']<=c.ema_fresh_bars and labels.get(pair)=='BULL':trend.append((-gap,pair,1))
        elif gap<0 and f['age_down']<=c.ema_fresh_bars and labels.get(pair)=='BEAR' and c.allow_short:trend.append((gap,pair,-1))
    for _,pair,side in sorted(trend):                                            # widest gap in ATRs first
        if held[EMA]>=c.top_n:break
        distance=c.stop_loss or c.stop_atr*features[pair]['atr_24']/features[pair]['close']
        if not distance>0:continue
        entries.append((pair,side,EMA,min(c.max_position,c.risk_per_trade/distance)))   # the stop loses risk_per_trade of equity
        taken.add(pair);held[EMA]+=1
    stretched=[]
    for pair in sorted(features):
        z=features[pair].get('z')
        if z is None or labels.get(pair)!='CHOP' or not free(pair):continue
        if z<=-c.mr_entry_z:stretched.append((-abs(z),pair,1))
        elif z>=c.mr_entry_z and c.allow_short:stretched.append((-abs(z),pair,-1))
    for _,pair,side in sorted(stretched):                                        # furthest from the mean first
        if held[MR]>=c.mr_slots:break
        entries.append((pair,side,MR,c.mr_fraction));taken.add(pair);held[MR]+=1
    return exits,entries


def moving(c,side,pair,drift,quick=None):
    """True while the price is still moving `side`'s way, False once that move has stalled, None while the runner's
    price record is too short to say. A steep move (`ride_steep` over fast_minutes) is judged over fast_minutes and
    must keep `ride`; anything gentler is judged over ride_short_minutes, with `ride` scaled to that window."""
    wave=side*drift[pair] if pair in drift else None;need=c.ride
    if c.ride_short_minutes and not (wave is not None and wave>=c.ride_steep):
        wave=side*quick[pair] if quick and pair in quick else None;need=c.ride*c.ride_short_minutes/c.fast_minutes
    return None if wave is None else wave>=need


def watch(book,quotes,c,now,drift,quick=None):
    """Exit rules checked every minute on live quotes. Returns [(pair, reason)] for the positions to close now.

    quotes: pair -> {'bid','ask'}. A long is valued at the bid and a short at the ask, the prices it would close at.
    drift:  pair -> price change over the last c.fast_minutes minutes (absent while that history is still short).
    quick:  pair -> price change over the last c.ride_short_minutes minutes, likewise.
    Each position's `best` price since entry is updated in place. Profit is counted after the fees of both orders.

    Momentum decides when a profit is taken: while the price is still moving the position's way (`ride`) a winner is
    held; once that move stalls, a mean-reversion position at its target and a trend position past `profit_arm` are
    closed (see `moving`). The profit lock stays underneath as the limit on what a real profit may give back.
    """
    cost=2*c.fee_bps/10000;out=[]
    for pair,p in book.items():
        q=quotes.get(pair)
        if not q or not q.get('tradable',True):continue                           # a wide quote is not a price to act on
        side=p['side'];entry=p['entry'];price=q['bid'] if side>0 else q['ask']
        best=p['best']=max(p.get('best',entry),price) if side>0 else min(p.get('best',entry),price)
        move=side*(price/entry-1);peak=side*(best/entry-1);back=side*(best-price)/best
        settled=now-p.get('opened',0)>=(c.fast_wait_minutes or c.fast_minutes)*60000   # a position this young is left to its stop-loss
        still=moving(c,side,pair,drift,quick) if c.ride else None                # is the price still going the position's way
        riding=still is True
        surge=bool(c.crash_ride) and bool(quick) and pair in quick and side*quick[pair]>=c.crash_ride   # very strong momentum
        if c.stop_loss and move<=-c.stop_loss:reason='stop loss'
        elif peak-cost>c.profit_arm and ((c.profit_trail and back>=c.profit_trail) or (c.profit_giveback and move<=peak*(1-c.profit_giveback))):reason='profit lock'
        elif c.mr_take_profit and p['leg']==MR and move-cost>=c.mr_take_profit and not riding:reason='profit target'
        elif c.crash_take_profit and p['leg']==CRASH and move-cost>=c.crash_take_profit and not surge:reason='profit target'
        elif c.crash_guard and p['leg']==CRASH and peak>=c.crash_guard and move<=0:reason='back to entry'
        elif p['leg']==EMA and still is False and move-cost>=c.profit_arm:reason='momentum faded'
        elif c.fast_cut and move<0 and settled and side*drift.get(pair,0.)<=-c.fast_cut:reason='fast fall'
        else:continue
        out.append((pair,reason))
    return out
