"""Persistent autonomous allocation runner. Default execution is local paper trading.

Live activation is explicit; it is not enabled by opening the desktop app.
No POST is retried. Ambiguous outcomes latch a reconciliation halt across restarts.
"""
import argparse
from dataclasses import asdict
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
from .allocation import allocation_targets,brake_scale
from .data import Bar
from .ranking import LOOKBACK,trend_frame
from .rules import load_rules
from .strategy import Config,Indicators

HOUR=3600000


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
        threshold=max(rules[pair].minimum,equity*c.rebalance_band)
        if abs(delta)<=threshold and not(desired==0 and held>rules[pair].minimum):continue
        side='BUY' if delta>0 else 'SELL'
        if side=='BUY' and float(profit_lock.get(pair,0))>now:
            continue
        fill=quotes[pair]['ask'] if side=='BUY' else price
        # Leave a modest quote-movement buffer before live acceptance.
        budget=min(delta,cash/(1+c.fee_bps/10000)*.995,max(0,c.max_exposure*equity-(equity-cash)),max(0,c.max_position*equity-held)) if side=='BUY' else min(-delta,held)
        amount=rules[pair].quantity(max(0,budget)/fill)
        if side=='SELL':amount=min(amount,q)
        if rules[pair].valid(amount,fill):
            orders.append({'pair':pair,'side':side,'quantity':amount,'reference_price':fill,'signal_time':now,
                           'priority':abs(delta)+(equity if side=='SELL' else 0),
                           'reason':'Drawdown halt: reduce exposure' if halted else
                                   ('Regime-adaptive rotation: rebalance confirmed trend leaders' if c.rank_model=='regime_adaptive'
                                    else 'Diversified trend ensemble: rebalance toward trend-vote targets' if c.rank_model=='trend_budget'
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
        if config.strategy not in ('allocation','cross_asset') or config.allow_short:
            raise ValueError('The autonomous runner currently supports long-only allocation and regime-adaptive cross-asset modes only')
        self.c=config;self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.client=client or Client();self.live=live
        digest=hashlib.sha256(json.dumps(asdict(config),sort_keys=True).encode()).hexdigest()
        requested_mode='live' if live else 'paper'
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {
            'mode':'live' if live else 'paper','config_hash':digest,'cash':config.initial_cash,'inventory':{},'peak':config.initial_cash,
            'halted':False,'last_submit':0,'inflight':None,'pending':None,'targets':{},'target_day':None,
            'fills':0,'position_meta':{},'profit_lock':{}}
        self.state.setdefault('position_meta',{});self.state.setdefault('profit_lock',{})
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
        if self.state.get('inflight'):
            raise RuntimeError('Unresolved submitted order. Reconcile the saved intent with query_order and balances before restarting.')
        self.rules=None;self.features=None;self.feature_hour=None;self.info=None

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
            if self.client.short_positions().get('Positions'):raise ValueError('Existing short positions are outside the allocation strategy')
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
            if old and old.get('quantity',0)>0:
                oq=float(old['quantity']);nq=oq+quantity
                old['avg_entry']=(oq*float(old['avg_entry'])+quantity*price)/nq
                old['quantity']=nq;old['high']=max(float(old.get('high',price)),price)
            else:
                meta[pair]={'quantity':quantity,'avg_entry':price,'high':price}
        elif old:
            remaining=max(0,float(old.get('quantity',0))-quantity)
            if remaining<=1e-10:meta.pop(pair,None)
            else:old['quantity']=remaining

    def wallet(self):
        if not self.live:
            return dict({'USD':{'Free':self.state['cash']}},**{p.split('/')[0]:{'Free':q} for p,q in self.state['inventory'].items()})
        b=self.client.balance();wallet=b.get('SpotWallet',b.get('Wallet'))
        if not isinstance(wallet,dict):raise ValueError('Unknown wallet response schema')
        expected={'USD'}|{p.split('/')[0] for p in self.rules}
        if any(float(v.get('Free',0))>0 and asset not in expected for asset,v in wallet.items()):
            raise ValueError('Unmanaged assets present in the live wallet')
        if any(float(v.get('Lock',0))>0 for v in wallet.values()):raise ValueError('Locked balances require order reconciliation')
        return wallet

    def refresh_features(self,now):
        hour=now//HOUR
        if self.feature_hour==hour:return
        features={};trend=self.c.rank_model=='trend_budget'
        count=max(self.c.slow*3,self.c.momentum+2,LOOKBACK+1 if trend else 0)
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
        self.features=features;self.feature_hour=hour

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

    def cycle(self):
        self.client.sync_clock();now=int(time.time()*1000+self.client.offset)
        try:self.refresh_features(now)
        except Exception as e:
            # Without candles, keep the last targets so exits and the brake still run.
            if self.state.get('target_day') is None:raise
            self.log({'event':'feature_error','timestamp':now,'error':str(e)})
        # Obtain execution quotes AFTER potentially slow historical reads.
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
        if target_due and self.feature_hour==now//HOUR:
            self.state['targets']=allocation_targets(self.features,self.c);self.state['target_day']=day
            if self.c.rank_model=='regime_adaptive':
                self.state['target_regime']=self.state.get('market_regime')
        intent,marks=plan_order(self.state,self.wallet(),quotes,self.state['targets'],self.rules,self.c,now)
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
                if runner.state.get('inflight'):raise
                print(f'Cycle blocked: {e}',flush=True)
            cycles+=1
            if a.cycles==0 or cycles<a.cycles:time.sleep(60)

if __name__=='__main__':main()
