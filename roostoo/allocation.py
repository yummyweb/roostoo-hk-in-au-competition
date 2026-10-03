"""Long-only volatility-budgeted allocation with partial, FIFO lot rebalancing.

The portfolio is re-targeted daily. One asset order may fill at each next candle
open. Small allocation drifts are ignored, avoiding full-position fee churn.
"""
from dataclasses import asdict
from itertools import groupby
import hashlib
import json
import math
from .data import validate_bars
from .metrics import summarize
from .rules import PairRule
from .strategy import Indicators


def run_allocation(bars,c,manifest,rules,start_index=0,precomputed=None):
    interval=validate_bars(bars)
    frames=[(t,{b.pair:b for b in rows}) for t,rows in groupby(bars,key=lambda b:b.timestamp)]
    pairs=sorted(frames[0][1]);rules=rules or {p:PairRule() for p in pairs}
    if precomputed is not None and len(precomputed)!=len(frames):
        raise ValueError('Precomputed features must match the replay timeline')
    if any(p not in rules or not rules[p].can_trade for p in pairs):
        raise ValueError('Missing/non-tradable exchange pair')
    if not 0<=start_index<len(frames)-1:raise ValueError('Invalid evaluation start')
    if c.allow_short:raise ValueError('Allocation strategy currently supports long-only portfolios')
    states={p:Indicators(c) for p in pairs}
    positions={p:[] for p in pairs};trades=[];orders=[];signals=[];cash=c.initial_cash
    pending=None;targets={};halted=False;peak=c.initial_cash;last_fill=-10**20
    half=c.spread_bps/20000;slip=c.slippage_bps/10000;fee_rate=c.fee_bps/10000
    start=frames[start_index][0]
    curve=[dict(timestamp=start,equity=cash,cash=cash,drawdown=0.,exposure=0.,benchmark=cash)]
    baseline={p:frames[start_index][1][p].open*(1+half)*(1+slip) for p in pairs}
    def qty(pair):return sum(p['quantity'] for p in positions[pair])
    for index,(timestamp,market) in enumerate(frames):
        if index>=start_index and pending and timestamp-last_fill>=60000:
            pair=pending['pair'];buy=pending['action']=='OPEN';rule=rules[pair]
            side_price=market[pair].open*(1+half if buy else 1-half)
            price=side_price*(1+slip if buy else 1-slip)
            quantity=pending['quantity']
            if buy:
                eq=cash+sum(qty(p)*market[p].open*(1-half) for p in pairs)
                gross=sum(qty(p)*market[p].open for p in pairs)
                capacity=min(cash/(1+fee_rate),max(0,eq*c.max_exposure-gross),max(0,eq*c.max_position-qty(pair)*market[pair].open))
                quantity=rule.quantity(min(quantity,capacity/price))
            else:quantity=rule.quantity(min(quantity,qty(pair)))
            order=dict(id=len(orders)+1,timestamp=timestamp,signal_timestamp=pending['timestamp'],pair=pair,
                       side='LONG',action=pending['action'],price=price,quantity=quantity,fee=0.,slippage_cost=0.,reason=pending['reason'],status='REJECTED')
            # Risk liquidation may leave exchange-minimum dust, which remains explicitly marked.
            if rule.valid(quantity,price):
                fee=quantity*price*fee_rate
                if buy:
                    cash-=quantity*price+fee
                    p=dict(id=len(trades)+1,pair=pair,side='LONG',status='OPEN',entry_time=timestamp,
                           entry_signal_time=pending['timestamp'],entry_price=price,quantity=quantity,collateral=quantity*price,
                           entry_fee=fee,exit_fee=0.,entry_reason=pending['reason'],exit_reason=None,exit_time=None,exit_price=None,
                           entry_index=index,regime='Cross-Asset Ranking' if c.strategy=='cross_asset' else 'Allocation',stop=None,initial_stop=None,features=pending['features'],gross_pnl=0.,net_pnl=-fee,
                           return_pct=-fee/(quantity*price),holding_hours=0.)
                    trades.append(p);positions[pair].append(p);order['trade_id']=p['id']
                else:
                    cash+=quantity*price-fee;remaining=quantity;closed_ids=[]
                    for p in list(positions[pair]):
                        if remaining<=1e-10:break
                        closing=min(remaining,p['quantity']);original=p['quantity'];fraction=closing/original
                        if fraction<1-1e-9:
                            rest=dict(p,id=len(trades)+1,quantity=original-closing,collateral=p['collateral']*(1-fraction),entry_fee=p['entry_fee']*(1-fraction))
                            trades.append(rest);positions[pair].insert(positions[pair].index(p),rest)
                        positions[pair].remove(p)
                        entry_fee=p['entry_fee']*fraction;exit_fee=fee*closing/quantity;gross=closing*(price-p['entry_price']);net=gross-entry_fee-exit_fee
                        p.update(quantity=closing,collateral=closing*p['entry_price'],entry_fee=entry_fee,exit_fee=exit_fee,status='CLOSED',
                                 exit_time=timestamp,exit_price=price,exit_reason=pending['reason'],gross_pnl=gross,net_pnl=net,
                                 return_pct=net/(closing*p['entry_price']),holding_hours=(timestamp-p['entry_time'])/3600000)
                        remaining-=closing;closed_ids.append(p['id'])
                    order['trade_ids']=closed_ids
                order.update(status='FILLED',fee=fee,slippage_cost=abs(price-side_price)*quantity);last_fill=timestamp
            else:order['rejection']='Order below exchange minimum or capacity limit'
            orders.append(order);pending=None
        features=precomputed[index] if precomputed is not None else {p:states[p].update(b) for p,b in market.items()}
        if index<start_index:continue
        gross=sum(qty(p)*market[p].close for p in pairs)
        equity=cash+gross*(1-half);peak=max(peak,equity);dd=1-equity/peak
        if dd>=c.max_drawdown or cash<-.000001:halted=True
        for pair,lots in positions.items():
            for p in lots:
                mark=market[pair].close*(1-half);gain=p['quantity']*(mark-p['entry_price'])
                p.update(mark_price=mark,gross_pnl=gain,net_pnl=gain-p['entry_fee'],return_pct=(gain-p['entry_fee'])/p['collateral'],holding_hours=(timestamp+interval-p['entry_time'])/3600000)
        benchmark=sum(c.initial_cash/len(pairs)/(1+fee_rate)/baseline[p]*market[p].close*(1-half) for p in pairs)
        curve.append(dict(timestamp=timestamp+interval,equity=equity,cash=cash,drawdown=dd,exposure=gross/equity if equity>0 else 0,benchmark=benchmark))
        if not targets or (timestamp//interval)%c.rebalance_bars==0:
            if c.strategy=='cross_asset':
                from .ranking import ranking_targets
                targets=ranking_targets(features,c,interval)
            else: targets=allocation_targets(features,c,interval)
        if halted:targets={}
        if pending:continue
        candidates=[]
        for pair in pairs:
            held=qty(pair)*market[pair].close;desired=targets.get(pair,0)*equity
            delta=desired-held
            threshold=max(rules[pair].minimum,equity*c.rebalance_band)
            if abs(delta)>threshold or (desired==0 and held>rules[pair].minimum):
                action='OPEN' if delta>0 else 'CLOSE'
                if action=='OPEN' and (cash<=threshold or halted):continue
                reason='Portfolio drawdown circuit breaker' if halted else ('Daily allocation: increase confirmed trend within volatility budget' if delta>0 else 'Daily allocation: trim drift or exit invalidated trend')
                if c.strategy=='cross_asset' and not halted:
                    reason='Cross-Asset Ranking: '+('increase a leading asset within volatility budget' if delta>0 else 'trim drift or exit a lower-ranked/invalidated trend')
                    if c.rank_model=='trend_budget':
                        reason='Diversified trend ensemble: '+('increase allocation supported by 3/7/14/30-day trend votes' if delta>0 else 'trim allocation after weaker trend votes or price drift')
                candidates.append(dict(pair=pair,action=action,side='LONG',quantity=rules[pair].quantity(abs(delta)/market[pair].close),
                                       priority=abs(delta)+(equity if action=='CLOSE' else 0),reason=reason,features=features[pair],timestamp=timestamp+interval-1))
        if candidates:
            pending=sorted(candidates,key=lambda x:(-x['priority'],x['pair']))[0];signals.append(dict(pending))
    if pending:orders.append(dict(id=len(orders)+1,status='UNFILLED_END',timestamp=pending['timestamp'],pair=pending['pair'],action=pending['action'],side='LONG',reason='No future candle'))
    m=summarize(curve,trades,orders,c.initial_cash);m['circuit_breaker_triggered']=halted
    digest=hashlib.sha256(json.dumps({'config':asdict(c),'manifest':manifest,'start':start},sort_keys=True).encode()).hexdigest()[:12]
    return {'schema_version':1,'id':digest,'name':'Volatility allocation / Long only','config':asdict(c),'manifest':manifest,
            'exchange_rules':{p:asdict(rules[p]) for p in pairs},'metrics':m,'equity_curve':curve,'trades':trades,'orders':orders,'signals':signals,
            'bars':[asdict(b) for b in bars],'pairs':pairs,'interval_ms':interval,'evaluation_start':start,'evaluation_end':curve[-1]['timestamp'],
            'warnings':['FIFO lots: a partial sale splits the entry lot. Closed-trade win rate is lot-based, not order-based.',
                        'Hourly close signals fill at the next open, one asset order per event. Spread and slippage are modeled.',
                        'Volatility sizing assumes perfect correlation; there are no intrabar stops or guaranteed drawdown bounds.',
                        'Fees are modeled in USD; open lots are marked at bid without exit commission. Tiny minimum-order dust can remain.',
                        'Annualized ratios on 14-day episodes are unstable; activity counts do not prove organizer eligibility.']}


def allocation_targets(features,c,interval=3600000):
    """Shared causal allocation rule used by replay and the autonomous runner."""
    ranked=[]
    for pair,f in features.items():
        if f['ready'] and f['momentum']>0 and f['close']>f['slow']:
            sigma=max(.2,f['volatility']*math.sqrt(365*86400000/interval))
            ranked.append((pair,f['momentum']/sigma,sigma))
    ranked.sort(key=lambda x:(-x[1],x[0]));ranked=ranked[:c.top_n]
    if not ranked:return {}
    inverses=sum(1/x[2] for x in ranked)
    raw={p:min(c.max_position,c.max_exposure/sigma/inverses) for p,score,sigma in ranked}
    risk=sum(raw[p]*sigma for p,score,sigma in ranked)
    scale=min(1,c.target_volatility/risk) if risk else 0
    return {p:w*scale for p,w in raw.items()}
