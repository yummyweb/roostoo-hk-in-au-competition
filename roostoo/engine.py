"""One global fill per event, signals at close and fills at next candle OPEN.

Only market orders are simulated. Prices have modeled spread and adverse slippage;
there is no depth, queue, partial-fill or intrabar stop-fill claim.
"""
from dataclasses import asdict
from itertools import groupby
import hashlib
import json
from .data import validate_bars
from .strategy import Config, Indicators, entry, exit_reason, rotation_targets
from .rules import PairRule
from .metrics import summarize


def short_settlement(quantity, entry_price, close_price, collateral, fee_rate=.001):
    gross = max(-collateral, quantity*(entry_price-close_price))
    fee = quantity*close_price*fee_rate
    return collateral+gross-fee, gross, fee


def run(bars, config=None, manifest=None, rules=None, start_index=0, precomputed=None):
    c = config or Config()
    c.validate()
    if c.strategy=='cross_asset':
        from .ranking import run_ranking
        return run_ranking(bars,c,manifest or {},rules)
    if c.strategy=='lstm_prediction' and precomputed is None:
        from .lstm import run_lstm
        return run_lstm(bars,c,manifest or {},rules)
    if c.strategy=='allocation':
        from .allocation import run_allocation
        return run_allocation(bars,c,manifest or {},rules,start_index,precomputed)
    interval = validate_bars(bars)
    frames = [(t,{b.pair:b for b in rows}) for t,rows in groupby(bars,key=lambda b:b.timestamp)]
    if precomputed is not None and len(precomputed)!=len(frames):
        raise ValueError('Precomputed features must match the replay timeline')
    if not 0 <= start_index < len(frames)-1:
        raise ValueError('Evaluation start must leave at least two candles')
    pairs = sorted(frames[0][1])
    rules = rules or {p:PairRule() for p in pairs}
    if any(p not in rules or not rules[p].can_trade for p in pairs):
        raise ValueError('Missing/non-tradable exchange pair')
    state = {p:Indicators(c) for p in pairs}
    cash = c.initial_cash
    positions, cooldown, traded_once = {}, {}, set()
    trades, orders, signals, curve = [], [], [], []
    pending = None
    targets = {}
    last_fill = -10**20
    peak = c.initial_cash
    halted = False
    fee_rate = c.fee_bps/10000
    slip = c.slippage_bps/10000
    half_spread = c.spread_bps/20000
    evaluation_start = frames[start_index][0]
    curve.append({'timestamp':evaluation_start,'equity':cash,'cash':cash,'drawdown':0,'exposure':0,'benchmark':cash})
    benchmark_entries = {p:frames[start_index][1][p].open*(1+half_spread)*(1+slip) for p in pairs}

    def valuation(market, opening=False):
        value = cash
        gross = 0.
        for pair,p in positions.items():
            price = market[pair].open if opening else market[pair].close
            gross += p['quantity']*price
            if p['side']=='LONG':
                value += p['quantity']*price*(1-half_spread)
            else:
                value += p['collateral']+max(-p['collateral'],p['quantity']*(p['entry_price']-price*(1+half_spread)))
        return value,gross

    for index,(timestamp, market) in enumerate(frames):
        # Execute only previously observed signals, before accessing this candle's HLC.
        if index>=start_index and pending and timestamp-last_fill>=60_000:
            intent = pending
            pending = None
            pair = intent['pair']
            opening = intent['action']=='OPEN'
            is_buy = intent['side']=='LONG' if opening else intent['side']=='SHORT'
            side_price = market[pair].open*(1+half_spread if is_buy else 1-half_spread)
            price = side_price*(1+slip if is_buy else 1-slip)
            rule = rules[pair]
            order = {'id':len(orders)+1,'timestamp':timestamp,'signal_timestamp':intent['timestamp'],
                     'pair':pair,'action':intent['action'],'side':intent['side'],'price':price,
                     'reason':intent['reason'],'status':'REJECTED','fee':0.,'slippage_cost':0.,'quantity':0.}
            if opening:
                current_equity,gross = valuation(market,opening=True)
                budget = min(intent['budget'],cash/(1+fee_rate),max(0,current_equity*c.max_exposure-gross),current_equity*c.max_position)
                qty = rule.quantity(max(0,budget)/price)
                if rule.valid(qty,price) and pair not in positions and not halted:
                    collateral = qty*price
                    fee = collateral*fee_rate
                    cash -= collateral+fee
                    p = {'id':len(trades)+1,'pair':pair,'side':intent['side'],'status':'OPEN',
                         'entry_time':timestamp,'entry_signal_time':intent['timestamp'],'entry_price':price,
                         'quantity':qty,'collateral':collateral,'entry_fee':fee,'exit_fee':0.,
                         'entry_reason':intent['reason'],'exit_reason':None,'exit_time':None,'exit_price':None,
                         'entry_index':index,'regime':'LSTM Prediction' if c.strategy=='lstm_prediction' else ('Range' if intent['reason'].startswith('Range') else 'Trend'),
                         'stop':price-intent['stop_distance'] if is_buy else price+intent['stop_distance'],
                         'initial_stop':price-intent['stop_distance'] if is_buy else price+intent['stop_distance'],
                         'features':intent['features'],'gross_pnl':0.,'net_pnl':-fee,'return_pct':-fee/collateral}
                    positions[pair]=p
                    trades.append(p)
                    traded_once.add(pair)
                    order.update(status='FILLED',quantity=qty,fee=fee,trade_id=p['id'])
            elif pair in positions:
                p=positions[pair]
                qty=p['quantity']
                if p['side']=='LONG':
                    fee=qty*price*fee_rate
                    gross=qty*(price-p['entry_price'])
                    cash+=qty*price-fee
                else:
                    amount,gross,fee=short_settlement(qty,p['entry_price'],price,p['collateral'],fee_rate)
                    cash+=amount
                net=gross-p['entry_fee']-fee
                p.update(status='CLOSED',exit_time=timestamp,exit_price=price,exit_fee=fee,
                         exit_reason=intent['reason'],gross_pnl=gross,net_pnl=net,return_pct=net/p['collateral'],
                         holding_hours=(timestamp-p['entry_time'])/3_600_000)
                del positions[pair]
                cooldown[pair]=index+c.cooldown_bars
                order.update(status='FILLED',quantity=qty,fee=fee,trade_id=p['id'])
            if order['status']=='FILLED':
                order['slippage_cost']=abs(price-side_price)*order['quantity']
                last_fill=timestamp
            else:
                order['rejection']='Insufficient capacity, minimum order, or risk halt'
            orders.append(order)
        features=precomputed[index] if precomputed is not None else {p:state[p].update(b) for p,b in market.items()}
        if index<start_index:
            continue
        equity,gross = valuation(market)
        peak=max(peak,equity)
        drawdown=1-equity/peak
        if drawdown>=c.max_drawdown or cash<-.000001 or equity<=0:
            halted=True  # latched; flatten progressively, never reset peak to hide losses
        for p in positions.values():
            mark=market[p['pair']].close*(1-half_spread if p['side']=='LONG' else 1+half_spread)
            unreal=p['quantity']*(mark-p['entry_price']) if p['side']=='LONG' else max(-p['collateral'],p['quantity']*(p['entry_price']-mark))
            p.update(gross_pnl=unreal,net_pnl=unreal-p['entry_fee'],return_pct=(unreal-p['entry_fee'])/p['collateral'],mark_price=mark,
                     holding_hours=(timestamp+interval-p['entry_time'])/3_600_000)
        benchmark=sum(c.initial_cash/len(pairs)/(1+fee_rate)/benchmark_entries[p]*market[p].close*(1-half_spread) for p in pairs)
        curve.append({'timestamp':timestamp+interval,'equity':equity,'cash':cash,'drawdown':drawdown,
                      'exposure':gross/equity if equity>0 else 0.,'benchmark':benchmark})
        if pending:
            continue
        # Targets refresh on a fixed UTC cadence, not relative to arbitrary test-window starts.
        if c.strategy=='rotation' and (not targets or (timestamp//interval)%c.rebalance_bars==0):
            targets=rotation_targets(features,c)
        # Prioritize risk exits over entries; deterministic pair tie-breaking.
        candidates=[]
        for pair,p in positions.items():
            f=features[pair]
            reason='Portfolio drawdown circuit breaker' if halted else exit_reason(p,f,market[pair],c,index)
            if c.strategy=='rotation' and not reason and index-p['entry_index']>=c.rebalance_bars:
                if pair not in targets or targets[pair][0]!=p['side']:
                    reason='Daily rotation: asset left the strongest risk-adjusted trends'
            if reason:
                candidates.append({'pair':pair,'side':p['side'],'action':'CLOSE','reason':reason,'priority':1000+(1 if 'stop' in reason.lower() else 0)})
            else:
                distance=c.stop_atr*f['atr']
                p['stop']=max(p['stop'],market[pair].close-distance) if p['side']=='LONG' else min(p['stop'],market[pair].close+distance)
        if not halted:
            for pair in pairs:
                if pair in positions or index<cooldown.get(pair,0) or (c.strategy=='buy_hold' and pair in traded_once):
                    continue
                f=features[pair]
                idea=(targets[pair][0],'Rotation: top relative momentum with absolute trend confirmation',targets[pair][1]) if c.strategy=='rotation' and pair in targets else (None if c.strategy=='rotation' else entry(f,c))
                if idea:
                    side,reason,priority=idea
                    distance=max(c.stop_atr*f['atr'],f['close']*.005)
                    budget=min(equity*c.risk_per_trade/(distance/f['close']),equity*c.max_position,
                               max(0,equity*c.max_exposure-gross),cash/(1+fee_rate))
                    if c.strategy=='buy_hold':
                        budget=min(equity*c.max_position,max(0,equity*c.max_exposure-gross),cash/(1+fee_rate))
                    if budget>rules[pair].minimum:
                        candidates.append({'pair':pair,'side':side,'action':'OPEN','reason':reason,'priority':priority,
                                           'budget':budget,'stop_distance':distance,'features':f})
        if candidates:
            pending=sorted(candidates,key=lambda x:(-x['priority'],x['pair']))[0]
            pending['timestamp']=timestamp+interval-1
            signals.append(dict(pending))
    if pending:
        orders.append({'id':len(orders)+1,'status':'UNFILLED_END','timestamp':pending['timestamp'],
                       'pair':pending['pair'],'action':pending['action'],'side':pending['side'],'reason':'No future candle to execute signal'})
    m=summarize(curve,trades,orders,c.initial_cash)
    m['circuit_breaker_triggered']=halted
    config_dict=asdict(c)
    digest=hashlib.sha256(json.dumps({'config':config_dict,'manifest':manifest,'start':start_index},sort_keys=True).encode()).hexdigest()[:12]
    warnings=['Spot fees are modeled in USD. The passive basket is an analytical equal-weight, fully invested reference without order throttling.',
              'OHLCV fills use modeled spread and slippage; no order-book depth or intrabar stop simulation.',
              'Open positions are marked at bid/ask without hypothetical exit commission; no forced end liquidation.',
              'Annualized daily ratios on short samples are unstable; official metric sampling is not specified.',
              'Active days count any fill, not the organizer’s undefined requirement for enough strategy trades per day.']
    if (manifest or {}).get('synthetic'):
        warnings.insert(0,'SYNTHETIC DEMO: these results are not evidence of historical or future profitability.')
    return {'schema_version':1,'id':digest,'name':f'{c.strategy.title()} / {"Long + short" if c.allow_short else "Long only"}',
            'config':config_dict,'manifest':manifest or {},'exchange_rules':{p:asdict(rules[p]) for p in pairs},
            'metrics':m,'equity_curve':curve,'trades':trades,'orders':orders,'signals':signals,
            'bars':[asdict(b) for b in bars], 'pairs':pairs,'interval_ms':interval,'warnings':warnings,
            'evaluation_start':evaluation_start,'evaluation_end':curve[-1]['timestamp']}
