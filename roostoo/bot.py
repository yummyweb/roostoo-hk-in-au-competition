"""Persistent autonomous allocation runner. Default execution is local paper trading.

Live activation is explicit; it is not enabled by opening the desktop app.
No POST is retried. Ambiguous outcomes latch a reconciliation halt across restarts.
"""
import argparse
from dataclasses import asdict,replace
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from .api import Client,APIError
from .allocation import allocation_targets,brake_scale,breakout_targets
from .data import Bar
from .legs import decide,watch
from .ranking import LOOKBACK,trend_frame
from .regime_hmm import RegimeFilter
from .rules import load_rules
from .strategy import Config,Indicators

HOUR=3600000
COIN_REGIME=Path(__file__).resolve().parents[1]/'config/coin_regime.json'
SHORT_KINDS=('SHORT','COVER');CLOSING=('SELL','COVER')   # an interrupted short request is reconciled from the exchange's position list


def save_state(path,state):
    temp=path.with_suffix('.tmp')
    with temp.open('w') as f:
        json.dump(state,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def plan_order(state,wallet,quotes,targets,rules,c,now):
    """Pure portfolio reconciliation; sells take precedence over new exposure."""
    cash=float(wallet.get('USD',{}).get('Free',0))
    quantities={p:float(wallet.get(p.split('/')[0],{}).get('Free',0)) for p in rules}
    equity=cash+sum(quantities[p]*quotes[p]['bid'] for p in rules)
    peak=max(state.get('peak',equity),equity)
    if c.drawdown_brake>0:
        # Gradual and non-latching: exposure recovers as the rolling peak ages out.
        scale=brake_scale(equity,max([equity]+[m[1] for m in state.get('equity_marks',[])]),c);halted=equity<=0
    else:
        scale=1.;halted=state.get('halted',False) or equity<=0 or 1-equity/peak>=c.max_drawdown
    if halted:targets={}
    orders=[]
    profit_lock=state.get('profit_lock',{})
    for pair in sorted(rules):
        q=quantities[pair];price=quotes[pair]['bid'];held=q*price;desired=targets.get(pair,0)*scale*equity;delta=desired-held
        if not quotes[pair].get('tradable',True):continue
        if c.rank_model=='breakout' and desired>0 and held>rules[pair].minimum:continue  # slots are not rebalanced
        threshold=max(rules[pair].minimum,equity*c.rebalance_band)
        if abs(delta)<=threshold and not(desired==0 and held>rules[pair].minimum):continue
        side='BUY' if delta>0 else 'SELL'
        if side=='BUY' and float(profit_lock.get(pair,0))>now:
            continue
        fill=quotes[pair]['ask'] if side=='BUY' else price
        # Leave a modest quote-movement buffer before live acceptance.
        budget=min(delta,cash/(1+c.fee_bps/10000)*.995,max(0,c.max_exposure*equity-(equity-cash)),max(0,c.max_position*equity-held)) if side=='BUY' else min(-delta,held)
        if c.rank_model=='breakout' and side=='BUY' and budget<desired/2:continue  # under half a slot would be released as a leftover
        amount=rules[pair].quantity(max(0,budget)/fill)
        if side=='SELL':amount=min(amount,q)
        if rules[pair].valid(amount,fill):
            orders.append({'pair':pair,'side':side,'quantity':amount,'reference_price':fill,'signal_time':now,
                           'priority':abs(delta)+(equity if side=='SELL' else 0),
                           'reason':'Drawdown halt: reduce exposure' if halted else
                                   ('Regime-adaptive rotation: rebalance confirmed trend leaders' if c.rank_model=='regime_adaptive'
                                    else 'Diversified trend ensemble: rebalance toward trend-vote targets' if c.rank_model=='trend_budget'
                                    else (f'Breakout slot: {c.momentum}h move at a {c.breakout_high_bars}h high' if side=='BUY' else 'Breakout slot: trailing stop or leftover exit') if c.rank_model=='breakout'
                                    else 'Daily volatility allocation: rebalance toward target'),
                           'target_weight':targets.get(pair,0)})
    # A trailing profit trim takes priority over a new allocation entry.
    for pair in sorted(rules) if c.take_profit_fraction>0 else ():
        q=quantities[pair];meta=state.get('position_meta',{}).get(pair,{})
        if not quotes[pair].get('tradable',True):continue
        avg=float(meta.get('avg_entry',0));high=max(float(meta.get('high',0)),quotes[pair]['bid'])
        if q<=0 or avg<=0 or high<=0:
            continue
        gain=quotes[pair]['bid']/avg-1
        pullback=1-quotes[pair]['bid']/high
        if gain < c.take_profit_pct or pullback < c.take_profit_trail:
            continue
        amount=rules[pair].quantity(q*c.take_profit_fraction)
        if not rules[pair].valid(amount,quotes[pair]['bid']):
            continue
        return {'pair':pair,'side':'SELL','quantity':amount,'reference_price':quotes[pair]['bid'],
                'signal_time':now,'priority':abs(amount*quotes[pair]['bid'])+equity,
                'reason':f'Trailing profit take: gain {gain:.1%}, pullback {pullback:.1%}',
                'target_weight':targets.get(pair,0)} , {'equity':equity,'cash':cash,'peak':peak,'halted':halted,'brake':scale}
    chosen=sorted(orders,key=lambda o:(-o['priority'],o['pair']))[0] if orders else None
    return chosen,{'equity':equity,'cash':cash,'peak':peak,'halted':halted,'brake':scale}


class Runner:
    def __init__(self,config,path,client=None,live=False):
        config.validate()
        self.legs=config.rank_model=='regime_legs'
        if config.strategy not in ('allocation','cross_asset') or (config.allow_short and not self.legs) or (self.legs and config.strategy!='allocation'):
            raise ValueError('The autonomous runner supports long-only allocation modes, and shorts only in the regime-legs mode')
        self.c=config;self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.client=client or Client();self.live=live
        digest=hashlib.sha256(json.dumps(asdict(config),sort_keys=True).encode()).hexdigest()
        requested_mode='live' if live else 'paper'
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {
            'mode':'live' if live else 'paper','config_hash':digest,'cash':config.initial_cash,'inventory':{},'peak':config.initial_cash,
            'halted':False,'last_submit':0,'inflight':None,'pending':None,'targets':{},'target_day':None,
            'fills':0,'position_meta':{},'profit_lock':{}}
        self.state.setdefault('position_meta',{});self.state.setdefault('profit_lock',{})
        for key,empty in (('book',{}),('locks',{}),('queue',[]),('shorts',{})):self.state.setdefault(key,empty)
        self.migrated_state=False
        if self.state['mode']!=requested_mode or self.state['config_hash']!=digest:
            # A config-only change can be adopted without discarding history
            # when this ledger has never traded. Active ledgers still require
            # explicit reconciliation and remain blocked.
            inventory=self.state.get('inventory',{})
            inactive=(not self.state.get('halted') and not self.state.get('inflight')
                      and not self.state.get('pending') and not self.state.get('fills')
                      and not any(abs(float(q))>1e-12 for q in inventory.values()))
            if not inactive:
                raise ValueError('State belongs to a different mode/config; reconcile the active ledger before changing it')
            self.state.update(mode=requested_mode,config_hash=digest,targets={},target_day=None,
                              target_regime=None,market_regime=None,regime_age=0)
            self.migrated_state=True
        if self.state.get('inflight') and self.state['inflight'].get('kind') not in SHORT_KINDS:
            raise RuntimeError('Unresolved submitted order. Reconcile the saved intent with query_order and balances before restarting.')
        self.rules=None;self.features=None;self.feature_hour=None;self.info=None;self.labels={}
        self.regime=json.loads(COIN_REGIME.read_text()) if self.legs else None
        self.no_shorts=False   # set when the exchange says this account cannot short; the short side is then skipped
        self.tape={}           # pair -> [(time, mid price)] of the last fast_minutes, from the quotes read each cycle

    def log(self,event):
        with self.path.with_suffix('.jsonl').open('a') as f:
            f.write(json.dumps(event,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

    def bootstrap(self):
        self.client.sync_clock();self.info=self.client.exchange_info()
        universe_path = Path(os.environ.get('ROOSTOO_UNIVERSE_CONFIG',
                                           str(Path(__file__).resolve().parents[1]/'config/universe.json')))
        pairs_doc=json.loads(universe_path.read_text())
        # Accept the legacy plain list and the richer {pairs: [...]} manifest.
        pairs=pairs_doc if isinstance(pairs_doc,list) else pairs_doc.get('pairs', [])
        if not pairs:
            raise ValueError(f'No pairs in universe config: {universe_path}')
        self.rules=load_rules(self.info,pairs)
        if self.live:
            if not self.state.get('position_meta'):
                self.state['position_meta']=self.reconstruct_position_meta()
            b=self.wallet()
            if abs(float(b.get('USD',{}).get('Free',0))-self.c.initial_cash)>.05 and (not self.path.exists() or self.migrated_state):
                raise ValueError('A new live session needs a flat wallet matching initial_cash; do not silently adopt an unknown portfolio')
            if not self.legs and self.client.short_positions().get('Positions'):raise ValueError('Existing short positions are outside the allocation strategy')
            try:
                pending=self.client.request('GET','/v3/pending_count',signed=True)
                if pending.get('TotalPending',0):raise ValueError('Existing pending exchange orders require reconciliation')
            except APIError as e:
                if 'no pending order' not in str(e).lower():raise
        self.log({'event':'start','mode':self.state['mode'],'config':asdict(self.c),'state_migrated':self.migrated_state,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'timestamp':int(time.time()*1000)})
        save_state(self.path,self.state)

    def reconstruct_position_meta(self):
        """Recover average entry and high water marks from matched spot orders."""
        lots={}
        for order in sorted(self.client.orders().get('OrderMatched',[]),key=lambda x:x.get('CreateTimestamp',0)):
            pair=order.get('Pair','');asset=pair.split('/')[0]
            if pair not in self.rules or order.get('Status')!='FILLED':
                continue
            quantity=float(order.get('FilledQuantity',0));price=float(order.get('FilledAverPrice',0))
            if quantity<=0 or price<=0:continue
            if order.get('Side')=='BUY':
                lots.setdefault(asset,[]).append([quantity,price])
            elif order.get('Side')=='SELL':
                left=quantity
                while left>1e-10 and lots.get(asset):
                    take=min(left,lots[asset][0][0]);lots[asset][0][0]-=take;left-=take
                    if lots[asset][0][0]<=1e-10:lots[asset].pop(0)
        meta={}
        for asset,entries in lots.items():
            quantity=sum(x[0] for x in entries)
            if quantity<=1e-10:continue
            pair=asset+'/USD';avg=sum(q*p for q,p in entries)/quantity
            meta[pair]={'quantity':quantity,'avg_entry':avg,'high':max(p for _,p in entries)}
        return meta

    def update_position_meta(self,pair,side,quantity,price):
        meta=self.state.setdefault('position_meta',{});old=meta.get(pair)
        if side=='BUY':
            if old and old.get('quantity',0)>quantity*.01:   # dust from an earlier position starts a fresh record
                oq=float(old['quantity']);nq=oq+quantity
                old['avg_entry']=(oq*float(old['avg_entry'])+quantity*price)/nq
                old['quantity']=nq;old['high']=max(float(old.get('high',price)),price)
            else:
                meta[pair]={'quantity':quantity,'avg_entry':price,'high':price}
        elif old:
            remaining=max(0,float(old.get('quantity',0))-quantity)
            # Rounding dust ends the position, so a later entry starts a fresh high-water mark.
            if remaining<=max(1e-10,float(old.get('quantity',0))*.01):meta.pop(pair,None)
            else:old['quantity']=remaining

    def wallet(self):
        if not self.live:
            return dict({'USD':{'Free':self.state['cash']}},**{p.split('/')[0]:{'Free':q} for p,q in self.state['inventory'].items()})
        b=self.client.balance();wallet=b.get('SpotWallet',b.get('Wallet'))
        if not isinstance(wallet,dict):raise ValueError('Unknown wallet response schema')
        expected={'USD'}|{p.split('/')[0] for p in self.rules}
        if any(float(v.get('Free',0))>0 and asset not in expected for asset,v in wallet.items()):
            raise ValueError('Unmanaged assets present in the live wallet')
        # Short collateral may be reported as locked USD; a locked coin can only be an order this bot never places.
        if any(float(v.get('Lock',0))>0 and not (asset=='USD' and self.legs) for asset,v in wallet.items()):raise ValueError('Locked balances require order reconciliation')
        return wallet

    def refresh_features(self,now):
        hour=now//HOUR
        if self.feature_hour==hour:return
        features={};labels={};trend=self.c.rank_model=='trend_budget'
        count=max(self.c.slow*3,self.c.momentum+2,self.c.breakout_high_bars+2,LOOKBACK+1 if trend else 0,1000 if self.legs else 0)
        for pair in self.rules:
            rows=[];end=hour*HOUR-1
            while len(rows)<count:
                query=urlencode({'symbol':pair.split('/')[0]+'USDT','interval':'1h','endTime':end,'limit':min(1000,count-len(rows))})
                with urlopen('https://data-api.binance.vision/api/v3/klines?'+query,timeout=20) as response:batch=json.load(response)
                if not batch:raise ValueError(f'Missing warmup candles: {pair}')
                rows=batch+rows;end=int(batch[0][0])-1
            indicator=Indicators(self.c);previous=None; closes=[]; dollar_volumes=[]
            for row in rows:
                bar=Bar(int(row[0]),pair,*(float(row[i]) for i in (1,2,3,4,5)));bar.validate()
                if previous is not None and bar.timestamp-previous!=HOUR:raise ValueError(f'Historical data gap: {pair}')
                if bar.timestamp+HOUR>now:raise ValueError('Incomplete candle rejected')
                features[pair]=indicator.update(bar); closes.append(bar.close)
                dollar_volumes.append(bar.close*bar.volume); previous=bar.timestamp
            if previous!=(hour-1)*HOUR:raise ValueError(f'Stale history: {pair}')
            if self.legs:
                regime=RegimeFilter(self.regime)
                for close in closes:regime.update(close)
                labels[pair]=regime.label;continue
            if trend:
                # Same trend votes, volatility and liquidity as the research replay.
                features[pair]=trend_frame(closes,dollar_volumes);continue
            f=features[pair]
            def trailing_return(window):
                return closes[-1]/closes[-window-1]-1 if len(closes)>window else 0.
            f.update(momentum_short=trailing_return(self.c.momentum),
                     momentum_12=trailing_return(12), momentum_24=trailing_return(24),
                     momentum_48=trailing_return(48), momentum_72=trailing_return(72),
                     momentum_168=trailing_return(168),
                     dollar_volume=sum(dollar_volumes[-168:])/min(168,len(dollar_volumes)))
            f['trend_strength']=sum(f[k]>0 for k in ('momentum_short','momentum_24','momentum_72','momentum_168'))/4
        if self.c.rank_model=='regime_adaptive':
            all_features=list(features.values())
            breadth_short=sum(f['momentum_short']>0 for f in all_features)/len(all_features)
            breadth_48=sum(f['momentum_48']>0 for f in all_features)/len(all_features)
            breadth_168=sum(f['momentum_168']>0 for f in all_features)/len(all_features)
            basket_short=sum(f['momentum_short'] for f in all_features)/len(all_features)
            basket_48=sum(f['momentum_48'] for f in all_features)/len(all_features)
            if breadth_48>=.60 and breadth_168>=.55 and basket_48>0:
                regime='BULL'
            elif breadth_short>=.52 and basket_short>0 and basket_48<0:
                regime='RECOVERY'
            elif breadth_short<=.38 and breadth_48<=.45 and basket_48<0:
                regime='BEAR'
            else:
                regime='CHOP'
            previous_regime=self.state.get('market_regime')
            age=int(self.state.get('regime_age',0))+1 if previous_regime==regime else 1
            self.state.update(market_regime=regime,regime_age=age)
            for f in features.values():
                f.update(market_regime=regime,regime_age=age,
                         market_breadth_short=breadth_short,market_breadth_48=breadth_48,
                         market_breadth_168=breadth_168,market_return_short=basket_short,
                         market_return_48=basket_48)
        self.features=features;self.labels=labels;self.feature_hour=hour

    def breakout(self,wallet,quotes,now):
        """Hourly slot decision from completed candles; a stopped pair is locked out for the cooldown."""
        value={p:float(wallet.get(p.split('/')[0],{}).get('Free',0))*quotes[p]['bid'] for p in self.rules}
        equity=float(wallet.get('USD',{}).get('Free',0))+sum(value.values())
        held={p:v/equity for p,v in value.items() if v>self.rules[p].minimum}
        meta=self.state['position_meta']
        for pair in [p for p in meta if p not in held]:del meta[pair]  # a record left by an earlier position must not seed a new one
        for pair in held:  # an untracked holding starts its high-water mark now
            meta.setdefault(pair,{'quantity':value[pair]/quotes[pair]['bid'],'avg_entry':quotes[pair]['bid'],'high':quotes[pair]['bid']})
        locked={p for p,until in self.state['profit_lock'].items() if until>now}
        targets=breakout_targets(self.features,self.c,held,{p:float(meta[p]['high']) for p in held},locked,
                                 self.state.setdefault('stop_levels',{}))
        for pair in held:
            if pair not in targets:self.state['profit_lock'][pair]=(now//HOUR+self.c.cooldown_bars)*HOUR  # whole hourly decisions
        return targets

    def submit(self,intent,quotes,now):
        if self.state.get('inflight'):raise RuntimeError('Ambiguous earlier order; submission blocked')
        if now-self.state['last_submit']<60000:raise RuntimeError('Global 60-second order throttle')
        # Reconcile the intent against current capacity and target immediately before execution.
        fresh,marks=plan_order(self.state,self.wallet(),quotes,self.state['targets'],self.rules,self.c,now)
        self.state.update(marks)
        if not fresh or fresh['pair']!=intent['pair'] or fresh['side']!=intent['side']:
            self.state['pending']=None;save_state(self.path,self.state);return
        intent=dict(fresh,quantity=min(fresh['quantity'],intent['quantity']))
        self.state.update(inflight=intent,last_submit=now,pending=None);save_state(self.path,self.state)
        self.log({'event':'intent','mode':self.state['mode'],**intent})
        if self.live:
            # Deliberately no automatic retry here, even after a network timeout.
            response=self.client.request('POST','/v3/place_order',{'pair':intent['pair'],'side':intent['side'],'type':'MARKET','quantity':format(intent['quantity'],'.12f')},signed=True)
            detail=response.get('OrderDetail',{})
            self.log({'event':'exchange_response','timestamp':now,'response':response})
            if detail.get('Status')!='FILLED':raise RuntimeError('Order not confirmed FILLED; reconciliation required')
            fill_price=float(detail.get('FilledAverPrice',intent['reference_price']))
        else:
            price=quotes[intent['pair']]['ask' if intent['side']=='BUY' else 'bid']
            price*=1+self.c.slippage_bps/10000 if intent['side']=='BUY' else 1-self.c.slippage_bps/10000
            q=intent['quantity'];cost=q*price;fee=cost*self.c.fee_bps/10000
            fill_price=price
            if intent['side']=='BUY':
                if cost+fee>self.state['cash']:raise RuntimeError('Paper fill exceeded reserved cash')
                self.state['cash']-=cost+fee
                self.state['inventory'][intent['pair']]=self.state['inventory'].get(intent['pair'],0)+q
            else:
                self.state['cash']+=cost-fee;self.state['inventory'][intent['pair']]-=q
            self.log({'event':'paper_fill','timestamp':now,**intent,'price':price,'fee':fee})
        self.update_position_meta(intent['pair'],intent['side'],intent['quantity'],fill_price)
        if intent['reason'].startswith('Trailing profit take'):
            self.state['profit_lock'][intent['pair']]=now+self.c.rebalance_bars*HOUR
        self.state['fills']+=1;self.state['inflight']=None;save_state(self.path,self.state)

    def read_quotes(self):
        ticker=self.client.ticker();now=int(time.time()*1000+self.client.offset)
        server=int(ticker.get('ServerTime',0))
        if abs(now-server)>15000:raise ValueError('Stale ticker: execution blocked')
        quotes={}
        for pair in self.rules:
            raw=ticker['Data'][pair];bid=float(raw['MaxBid']);ask=float(raw['MinAsk'])
            if not all(math.isfinite(x) and x>0 for x in (bid,ask)) or bid>ask:raise ValueError('Invalid quote')
            quotes[pair]={'bid':bid,'ask':ask}
            # A wide quote pauses trading in that pair only; it is still marked at the bid.
            if (ask/bid-1)>.01:quotes[pair]['tradable']=False
        return quotes,now

    # ---- regime-legs mode: tagged long and short positions, decided hourly by legs.decide -------------------------
    def account(self,quotes):
        """Cash, long quantities, short positions and equity as the exchange (or the paper ledger) reports them."""
        wallet=self.wallet();cash=float(wallet.get('USD',{}).get('Free',0))
        longs={p:float(wallet.get(p.split('/')[0],{}).get('Free',0)) for p in self.rules}
        if self.live:
            shorts={}
            try:rows=self.client.short_positions().get('Positions')
            except APIError as error:
                # Only an explicit refusal with no short on the book means "this account cannot short". Any other
                # failed read blocks this cycle: counting open shorts as gone would drop their collateral from equity.
                refused=any(word in str(error).lower() for word in ('not allow','permission'))
                if not refused or any(p['side']<0 for p in self.state['book'].values()):raise
                if not self.no_shorts:self.log({'event':'shorts_unavailable','error':str(error)})
                self.no_shorts=True;rows=[]
            if rows is None and not any(p['side']<0 for p in self.state['book'].values()):rows=[]
            if not isinstance(rows,list):raise ValueError('Unknown short position response schema')
            rows=[row for row in rows if row.get('Pair') in self.rules]   # a short outside the universe is not this bot's
            for row in rows:   # a zero field is left out by the exchange
                collateral=float(row.get('Collateral',0))
                shorts[row['Pair']]={'qty':float(row.get('ShortQty',0)),'entry':float(row.get('EntryPrice',0)),'collateral':collateral,
                                     'value':float(row.get('PositionValue',collateral+float(row.get('UnrealizedPNL',0))))}
        else:
            shorts={p:dict(s,value=max(0.,s['collateral']+s['qty']*(s['entry']-quotes[p]['ask']))) for p,s in self.state['shorts'].items()}
        equity=cash+sum(q*quotes[p]['bid'] for p,q in longs.items())+sum(s['value'] for s in shorts.values())
        return {'cash':cash,'longs':longs,'shorts':shorts,'equity':equity}

    def spot(self,pair,side,quantity,quotes,reason,now):
        """One market spot order under the same no-retry rule as submit(). Returns the fill price."""
        reference=quotes[pair]['ask' if side=='BUY' else 'bid']
        intent={'pair':pair,'side':side,'quantity':quantity,'reference_price':reference,'signal_time':now,'reason':reason}
        self.state.update(inflight=intent,last_submit=now);save_state(self.path,self.state)
        self.log({'event':'intent','mode':self.state['mode'],**intent})
        if self.live:
            response=self.client.request('POST','/v3/place_order',{'pair':pair,'side':side,'type':'MARKET','quantity':format(quantity,'.12f')},signed=True)
            detail=response.get('OrderDetail',{})
            self.log({'event':'exchange_response','timestamp':now,'response':response})
            if detail.get('Status')!='FILLED':raise RuntimeError('Order not confirmed FILLED; reconciliation required')
            price=float(detail.get('FilledAverPrice',reference))
        else:
            price=reference*(1+self.c.slippage_bps/10000 if side=='BUY' else 1-self.c.slippage_bps/10000)
            cost=quantity*price;fee=cost*self.c.fee_bps/10000
            if side=='BUY':
                if cost+fee>self.state['cash']:raise RuntimeError('Paper fill exceeded reserved cash')
                self.state['cash']-=cost+fee;self.state['inventory'][pair]=self.state['inventory'].get(pair,0)+quantity
            else:
                self.state['cash']+=cost-fee;self.state['inventory'][pair]=self.state['inventory'].get(pair,0)-quantity
            self.log({'event':'paper_fill','timestamp':now,**intent,'price':price,'fee':fee})
        self.state['fills']+=1;self.state['inflight']=None;save_state(self.path,self.state)
        return price

    def short(self,pair,kind,collateral,quotes,reason,now,leg=None):
        """Open (collateral in USD) or fully close a 1x short. Returns the entry or close price, or None if refused."""
        intent={'pair':pair,'kind':kind,'leg':leg,'collateral':collateral,'signal_time':now,'reason':reason}
        self.state.update(inflight=intent,last_submit=now);save_state(self.path,self.state)
        self.log({'event':'intent','mode':self.state['mode'],**intent})
        if self.live:
            try:
                # Only the documented parameters may be signed: pair and collateral to open, pair alone to close.
                if kind=='SHORT':response=self.client.request('POST','/v6/short_open',{'pair':pair,'collateral':format(collateral,'.2f')},signed=True)
                else:response=self.client.request('POST','/v6/short_close',{'pair':pair},signed=True)
            except APIError as error:
                # The exchange answered and refused, so nothing changed. Anything else stays in flight and is reconciled.
                self.log({'event':'short_refused','timestamp':now,'pair':pair,'kind':kind,'error':str(error)})
                if kind=='SHORT' and any(word in str(error).lower() for word in ('not allow','permission')):self.no_shorts=True
                self.state['inflight']=None;save_state(self.path,self.state);return None
            self.log({'event':'exchange_response','timestamp':now,'response':response})
            price=float(response.get('EntryPrice' if kind=='SHORT' else 'ClosePrice',0)) or quotes[pair]['bid' if kind=='SHORT' else 'ask']
        else:
            slip=self.c.slippage_bps/10000;rate=self.c.fee_bps/10000
            if kind=='SHORT':
                price=quotes[pair]['bid']*(1-slip);self.state['cash']-=collateral*(1+rate)
                self.state['shorts'][pair]={'qty':collateral/price,'entry':price,'collateral':collateral}
            else:
                held=self.state['shorts'].pop(pair);price=quotes[pair]['ask']*(1+slip)
                profit=max(-held['collateral'],held['qty']*(held['entry']-price))      # a short loses at most its collateral
                self.state['cash']+=held['collateral']+profit-held['qty']*price*rate
            self.log({'event':'paper_fill','timestamp':now,**intent,'price':price})
        self.state['fills']+=1;self.state['inflight']=None;save_state(self.path,self.state)
        return price

    def act(self,action,account,quotes,now):
        """Carry out one queued action against the current account. Sizes come from equity at this moment."""
        pair,kind=action['pair'],action['action'];book=self.state['book'];rule=self.rules[pair]
        opened={'leg':action.get('leg'),'bar':now//HOUR,'level':None,'opened':now}
        budget=min(action.get('weight',0)*account['equity'],account['cash']/(1+self.c.fee_bps/10000)*.995)
        if kind in ('BUY','SHORT') and budget<action['weight']*account['equity']/2:return False   # not enough cash for half the size
        if kind=='SELL':
            quantity=rule.quantity(account['longs'].get(pair,0))
            if not rule.valid(quantity,quotes[pair]['bid']):book.pop(pair,None);return False
            self.spot(pair,'SELL',quantity,quotes,action['reason'],now);book.pop(pair,None)
        elif kind=='COVER':
            if pair not in account['shorts']:book.pop(pair,None);return False
            if self.short(pair,'COVER',0.,quotes,action['reason'],now) is None:
                self.state['queue'].append(action);return False                  # refused: nothing changed, try again after the other actions
            book.pop(pair,None)
        elif kind=='BUY':
            quantity=rule.quantity(budget/quotes[pair]['ask'])
            if not rule.valid(quantity,quotes[pair]['ask']):return False
            price=self.spot(pair,'BUY',quantity,quotes,action['reason'],now)
            book[pair]=dict(opened,side=1,entry=price,high=price,low=price)
        else:
            collateral=math.floor(budget*100)/100
            if collateral<1:return False
            price=self.short(pair,'SHORT',collateral,quotes,action['reason'],now,action.get('leg'))
            if price is None:
                self.state['locks'][pair]=now//HOUR+24;return False              # refused: leave this pair alone for a day
            book[pair]=dict(opened,side=-1,entry=price,high=price,low=price)
        save_state(self.path,self.state);return True

    def drift(self,quotes,now):
        """Price change of each pair over the last fast_minutes, from the bot's own minute-by-minute record of mid prices."""
        span=self.c.fast_minutes*60000;out={}
        for pair,q in quotes.items():
            mid=(q['bid']+q['ask'])/2;tape=self.tape.setdefault(pair,[]);tape.append((now,mid))
            while tape[0][0]<now-span:tape.pop(0)
            if now-tape[0][0]>=span*.8:out[pair]=mid/tape[0][1]-1
        return out

    def cycle_legs(self):
        self.client.sync_clock();now=int(time.time()*1000+self.client.offset);candle_error=None;started=time.time()
        try:self.refresh_features(now)
        except Exception as e:   # without candles there is no new decision, but queued exits still run
            candle_error=str(e);self.log({'event':'feature_error','timestamp':now,'error':candle_error})
        refresh_seconds=round(time.time()-started,1)
        quotes,now=self.read_quotes();state=self.state;book=state['book'];bar=now//HOUR-1
        account=self.account(quotes)
        pending=state.get('inflight')
        if pending and pending.get('kind') in SHORT_KINDS:                       # an interrupted short request: trust the position list
            pair=pending['pair'];held=account['shorts'].get(pair)
            if pending['kind']=='SHORT' and held:
                book[pair]={'leg':pending.get('leg'),'side':-1,'entry':held['entry'],'bar':now//HOUR,'high':held['entry'],'low':held['entry'],'level':None}
            elif pending['kind']=='COVER' and not held:book.pop(pair,None)
            elif pending['kind']=='COVER' and pair in book:state['queue'].append({'pair':pair,'action':'COVER','reason':pending['reason']})   # it did not close: try again
            self.log({'event':'short_reconciled','timestamp':now,'pair':pair,'kind':pending['kind'],'open':bool(held)})
            state['inflight']=None
        for pair,p in list(book.items()):                                         # positions that no longer exist leave the book
            gone=pair not in account['shorts'] if p['side']<0 else account['longs'].get(pair,0)*quotes[pair]['bid']<=self.rules[pair].minimum
            if gone:del book[pair]
        state['peak']=max(state.get('peak',account['equity']),account['equity'])
        if account['equity']<=0 or 1-account['equity']/state['peak']>=self.c.max_drawdown:state['halted']=True
        hour=now//HOUR;marks=[m for m in state.get('equity_marks',[]) if m[0]>hour-self.c.brake_window_bars]
        if marks and marks[-1][0]==hour:marks[-1][1]=max(marks[-1][1],account['equity'])
        else:marks.append([hour,account['equity']])
        state['equity_marks']=marks                                               # the loss brake: nothing new is opened this far below the recent high
        braked=self.c.drawdown_brake>0 and account['equity']<=max(m[1] for m in marks)*(1-self.c.drawdown_brake)
        if self.feature_hour==now//HOUR and state.get('legs_bar')!=bar:
            exits,entries=decide(self.features,self.labels,book,state['locks'],replace(self.c,allow_short=False) if self.no_shorts else self.c,bar)
            carried=[a for a in state['queue'] if a['action'] in CLOSING and a['pair'] in book and a['pair'] not in exits]   # an exit not yet sent still stands
            state['queue']=carried+[{'pair':p,'action':'SELL' if book[p]['side']>0 else 'COVER','reason':f"{book[p]['leg']} exit"} for p in exits]
            state['queue']+=[{'pair':p,'action':'BUY' if side>0 else 'SHORT','leg':leg,'weight':weight,
                              'reason':f"{leg} {'long' if side>0 else 'short'} in {self.labels.get(p)}"} for p,side,leg,weight in entries]
            state['legs_bar']=bar
            self.log({'event':'decision','timestamp':now,'bar':bar,'refresh_seconds':refresh_seconds,'labels':self.labels,'queue':state['queue']})
        for pair,reason in watch(book,quotes,self.c,now,self.drift(quotes,now)):  # every minute: stop-loss, profit lock, profit target, fast fall
            if any(a['pair']==pair and a['action'] in CLOSING for a in state['queue']):continue
            p=book[pair];state['queue']=[a for a in state['queue'] if a['pair']!=pair]
            state['queue'].insert(0,{'pair':pair,'action':'SELL' if p['side']>0 else 'COVER','reason':reason})
            state['locks'][pair]=now//HOUR+(self.c.cooldown_bars if p['leg']=='ema' else self.c.mr_cooldown_bars)
            self.log({'event':'exit_signal','timestamp':now,'pair':pair,'reason':reason,'leg':p['leg'],'side':p['side'],'entry':p['entry'],'best':p['best'],'quote':quotes[pair]})
        if state.get('legs_bar')!=bar or state['halted'] or braked:               # an entry is good only in the hour after its candle, never after a halt or under the brake
            state['queue']=[a for a in state['queue'] if a['action'] in CLOSING]
        if state['halted']:                                                       # a halt closes everything, with or without candles
            waiting={a['pair'] for a in state['queue']}
            state['queue']+=[{'pair':p,'action':'SELL' if v['side']>0 else 'COVER','reason':'drawdown halt'} for p,v in book.items() if p not in waiting]
        # Anything held but not in the book is not ours to keep: it is closed first and nothing is opened on top of it.
        foreign=[(pair,'SELL','untracked holding') for pair,quantity in account['longs'].items()
                 if pair not in book and quantity*quotes[pair]['bid']>self.rules[pair].minimum]
        foreign+=[(pair,'COVER','untracked short') for pair in account['shorts'] if pair not in book]
        for pair,kind,reason in foreign:
            state['queue']=[a for a in state['queue'] if a['pair']!=pair]
            state['queue'].insert(0,{'pair':pair,'action':kind,'reason':reason})
        done=None
        if now-state['last_submit']>=60000:                                       # one order per minute for the whole account
            for action in list(state['queue']):
                if not quotes[action['pair']].get('tradable',True):continue
                state['queue'].remove(action);done=dict(action,filled=self.act(action,account,quotes,now));break
        counts={k:sum(1 for v in self.labels.values() if v==k) for k in ('BULL','BEAR','CHOP')}
        held={f"{leg}_{'long' if side>0 else 'short'}":sum(1 for p in book.values() if p['leg']==leg and p['side']==side) for leg in ('ema','mr') for side in (1,-1)}
        invested=(sum(q*quotes[p]['bid'] for p,q in account['longs'].items())+sum(s['value'] for s in account['shorts'].values()))/account['equity'] if account['equity']>0 else 0.
        self.log({'event':'snapshot','timestamp':now,'equity':account['equity'],'cash':account['cash'],'halted':state['halted'],'brake':braked,
                  'invested':invested,'regimes':counts,'book':book,'queue':state['queue'],'done':done,'candle_error':candle_error})
        save_state(self.path,state)
        # No candles for this hour means no hourly decision (the minute exits above still ran): say so until they arrive.
        if candle_error and self.feature_hour!=now//HOUR:raise ValueError('No candles for this hour, no decision made: '+candle_error)
        return {'mode':state['mode'],'equity':account['equity'],'fills':state['fills'],'halted':state['halted'],'brake':braked,
                'invested':round(invested,3),'regimes':counts,'positions':held,'queued':len(state['queue']),
                'done':f"{done['action']} {done['pair']}" if done and done['filled'] else None,'why':done['reason'] if done and done['filled'] else None}

    def cycle(self):
        if self.legs:return self.cycle_legs()
        self.client.sync_clock();now=int(time.time()*1000+self.client.offset)
        try:self.refresh_features(now)
        except Exception as e:
            # Without candles, keep the last targets so exits and the brake still run.
            if self.state.get('target_day') is None:raise
            self.log({'event':'feature_error','timestamp':now,'error':str(e)})
        # Obtain execution quotes AFTER potentially slow historical reads.
        quotes,now=self.read_quotes()
        for pair,meta in list(self.state.get('position_meta',{}).items()):
            if pair in quotes:
                meta['high']=max(float(meta.get('high',quotes[pair]['bid'])),quotes[pair]['bid'])
        if self.state.get('pending') and now-self.state['pending']['signal_time']>=60000:
            self.submit(self.state['pending'],quotes,now)
        day=now//(self.c.rebalance_bars*HOUR)
        target_due=self.state['target_day']!=day
        if self.c.rank_model=='regime_adaptive':
            target_due = target_due or self.state.get('target_regime')!=self.state.get('market_regime')
            target_due = target_due or self.state.get('regime_age',0)==self.c.regime_hold_bars
        wallet=self.wallet()
        if target_due and self.feature_hour==now//HOUR:
            if self.c.rank_model=='breakout':
                self.state['targets']=self.breakout(wallet,quotes,now)
            else:
                self.state['targets']=allocation_targets(self.features,self.c)
            self.state['target_day']=day
            if self.c.rank_model=='regime_adaptive':
                self.state['target_regime']=self.state.get('market_regime')
        # Empty targets before the first decision of a new ledger or config would read as "sell everything".
        if self.state['target_day'] is None:raise ValueError('No target decision yet; holdings left untouched')
        intent,marks=plan_order(self.state,wallet,quotes,self.state['targets'],self.rules,self.c,now)
        self.state.update(marks)
        if marks['halted']:self.state['targets']={}
        if self.c.drawdown_brake>0:
            hour=now//HOUR;history=[m for m in self.state.get('equity_marks',[]) if m[0]>hour-self.c.brake_window_bars]
            if history and history[-1][0]==hour:history[-1][1]=max(history[-1][1],marks['equity'])
            else:history.append([hour,marks['equity']])
            self.state['equity_marks']=history
        self.state['pending']=intent
        self.log({'event':'snapshot','timestamp':now,**marks,'market_regime':self.state.get('market_regime'),
                  'regime_age':self.state.get('regime_age',0),'targets':self.state['targets'],
                  'pending':intent,'quotes':quotes})
        save_state(self.path,self.state)
        return {'mode':self.state['mode'],'equity':marks['equity'],'fills':self.state['fills'],
                'halted':marks['halted'],'brake':marks['brake'],'market_regime':self.state.get('market_regime'),
                'regime_age':self.state.get('regime_age',0),
                'pending':intent['pair'] if intent else None}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--state',default='runs/paper/state.json');p.add_argument('--live',action='store_true');p.add_argument('--cycles',type=int,default=0)
    a=p.parse_args();c=Config(**json.loads(Path(a.config).read_text()))
    lock_path=Path(a.state).with_suffix('.lock');lock_path.parent.mkdir(parents=True,exist_ok=True)
    with lock_path.open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('Another bot owns this state; refusing duplicate execution')
        client=Client(os.environ.get('ROOSTOO_API_KEY',''),os.environ.get('ROOSTOO_API_SECRET',''))
        live=a.live or os.environ.get('ROOSTOO_LIVE','0')=='1'
        runner=Runner(c,a.state,client,live);runner.bootstrap();cycles=0
        while a.cycles==0 or cycles<a.cycles:
            try:print(json.dumps(runner.cycle()),flush=True)
            except Exception as e:
                runner.log({'event':'error','timestamp':int(time.time()*1000),'error':str(e)})
                if runner.state.get('inflight') and runner.state['inflight'].get('kind') not in SHORT_KINDS:raise
                print(f'Cycle blocked: {e}',flush=True)
            cycles+=1
            if a.cycles==0 or cycles<a.cycles:time.sleep(60)

if __name__=='__main__':main()
