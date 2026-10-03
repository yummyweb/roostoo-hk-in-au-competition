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
from .allocation import allocation_targets
from .data import Bar
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
    halted=state.get('halted',False) or equity<=0 or 1-equity/peak>=c.max_drawdown
    if halted:targets={}
    orders=[]
    for pair in sorted(rules):
        q=quantities[pair];price=quotes[pair]['bid'];held=q*price;desired=targets.get(pair,0)*equity;delta=desired-held
        threshold=max(rules[pair].minimum,equity*c.rebalance_band)
        if abs(delta)<=threshold and not(desired==0 and held>rules[pair].minimum):continue
        side='BUY' if delta>0 else 'SELL'
        fill=quotes[pair]['ask'] if side=='BUY' else price
        # Leave a modest quote-movement buffer before live acceptance.
        budget=min(delta,cash/(1+c.fee_bps/10000)*.995,max(0,c.max_exposure*equity-(equity-cash)),max(0,c.max_position*equity-held)) if side=='BUY' else min(-delta,held)
        amount=rules[pair].quantity(max(0,budget)/fill)
        if side=='SELL':amount=min(amount,q)
        if rules[pair].valid(amount,fill):
            orders.append({'pair':pair,'side':side,'quantity':amount,'reference_price':fill,'signal_time':now,
                           'priority':abs(delta)+(equity if side=='SELL' else 0),
                           'reason':'Drawdown halt: reduce exposure' if halted else 'Daily volatility allocation: rebalance toward target',
                           'target_weight':targets.get(pair,0)})
    chosen=sorted(orders,key=lambda o:(-o['priority'],o['pair']))[0] if orders else None
    return chosen,{'equity':equity,'cash':cash,'peak':peak,'halted':halted}


class Runner:
    def __init__(self,config,path,client=None,live=False):
        config.validate()
        if config.strategy!='allocation' or config.allow_short:
            raise ValueError('The autonomous runner currently supports long-only allocation only')
        self.c=config;self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.client=client or Client();self.live=live
        digest=hashlib.sha256(json.dumps(asdict(config),sort_keys=True).encode()).hexdigest()
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {
            'mode':'live' if live else 'paper','config_hash':digest,'cash':config.initial_cash,'inventory':{},'peak':config.initial_cash,
            'halted':False,'last_submit':0,'inflight':None,'pending':None,'targets':{},'target_day':None,'fills':0}
        if self.state['mode']!=('live' if live else 'paper') or self.state['config_hash']!=digest:
            raise ValueError('State belongs to a different mode/config; do not silently reset its ledger')
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
            b=self.wallet()
            if abs(float(b.get('USD',{}).get('Free',0))-self.c.initial_cash)>.05 and not self.path.exists():
                raise ValueError('A new live session needs a flat wallet matching initial_cash; do not silently adopt an unknown portfolio')
            if self.client.short_positions().get('Positions'):raise ValueError('Existing short positions are outside the allocation strategy')
            try:
                pending=self.client.request('GET','/v3/pending_count',signed=True)
                if pending.get('TotalPending',0):raise ValueError('Existing pending exchange orders require reconciliation')
            except APIError as e:
                if 'no pending order' not in str(e).lower():raise
        self.log({'event':'start','mode':self.state['mode'],'config':asdict(self.c),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'timestamp':int(time.time()*1000)})
        save_state(self.path,self.state)

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
        features={}
        count=max(self.c.slow*3,self.c.momentum+2)
        for pair in self.rules:
            rows=[];end=hour*HOUR-1
            while len(rows)<count:
                query=urlencode({'symbol':pair.split('/')[0]+'USDT','interval':'1h','endTime':end,'limit':min(1000,count-len(rows))})
                with urlopen('https://data-api.binance.vision/api/v3/klines?'+query,timeout=20) as response:batch=json.load(response)
                if not batch:raise ValueError(f'Missing warmup candles: {pair}')
                rows=batch+rows;end=int(batch[0][0])-1
            indicator=Indicators(self.c);previous=None
            for row in rows:
                bar=Bar(int(row[0]),pair,*(float(row[i]) for i in (1,2,3,4,5)));bar.validate()
                if previous is not None and bar.timestamp-previous!=HOUR:raise ValueError(f'Historical data gap: {pair}')
                if bar.timestamp+HOUR>now:raise ValueError('Incomplete candle rejected')
                features[pair]=indicator.update(bar);previous=bar.timestamp
            if previous!=(hour-1)*HOUR:raise ValueError(f'Stale history: {pair}')
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
        else:
            price=quotes[intent['pair']]['ask' if intent['side']=='BUY' else 'bid']
            price*=1+self.c.slippage_bps/10000 if intent['side']=='BUY' else 1-self.c.slippage_bps/10000
            q=intent['quantity'];cost=q*price;fee=cost*self.c.fee_bps/10000
            if intent['side']=='BUY':
                if cost+fee>self.state['cash']:raise RuntimeError('Paper fill exceeded reserved cash')
                self.state['cash']-=cost+fee
                self.state['inventory'][intent['pair']]=self.state['inventory'].get(intent['pair'],0)+q
            else:
                self.state['cash']+=cost-fee;self.state['inventory'][intent['pair']]-=q
            self.log({'event':'paper_fill','timestamp':now,**intent,'price':price,'fee':fee})
        self.state['fills']+=1;self.state['inflight']=None;save_state(self.path,self.state)

    def cycle(self):
        self.client.sync_clock();now=int(time.time()*1000+self.client.offset)
        self.refresh_features(now)
        # Obtain execution quotes AFTER potentially slow historical reads.
        ticker=self.client.ticker();now=int(time.time()*1000+self.client.offset)
        server=int(ticker.get('ServerTime',0))
        if abs(now-server)>15000:raise ValueError('Stale ticker: execution blocked')
        quotes={}
        for pair in self.rules:
            raw=ticker['Data'][pair];bid=float(raw['MaxBid']);ask=float(raw['MinAsk'])
            if not all(math.isfinite(x) and x>0 for x in (bid,ask)) or bid>ask:raise ValueError('Invalid quote')
            if (ask/bid-1)>.01:raise ValueError(f'Spread over 1%: {pair}; cycle blocked')
            quotes[pair]={'bid':bid,'ask':ask}
        if self.state.get('pending') and now-self.state['pending']['signal_time']>=60000:
            self.submit(self.state['pending'],quotes,now)
        day=now//(self.c.rebalance_bars*HOUR)
        if self.state['target_day']!=day:
            self.state['targets']=allocation_targets(self.features,self.c);self.state['target_day']=day
        intent,marks=plan_order(self.state,self.wallet(),quotes,self.state['targets'],self.rules,self.c,now)
        self.state.update(marks)
        if marks['halted']:self.state['targets']={}
        self.state['pending']=intent
        self.log({'event':'snapshot','timestamp':now,**marks,'targets':self.state['targets'],'pending':intent,'quotes':quotes})
        save_state(self.path,self.state)
        return {'mode':self.state['mode'],'equity':marks['equity'],'fills':self.state['fills'],'halted':marks['halted'],'pending':intent['pair'] if intent else None}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--state',default='runs/paper/state.json');p.add_argument('--live',action='store_true');p.add_argument('--cycles',type=int,default=0)
    a=p.parse_args();c=Config(**json.loads(Path(a.config).read_text()))
    lock_path=Path(a.state).with_suffix('.lock');lock_path.parent.mkdir(parents=True,exist_ok=True)
    with lock_path.open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('Another bot owns this state; refusing duplicate execution')
        client=Client(os.environ.get('ROOSTOO_API_KEY',''),os.environ.get('ROOSTOO_API_SECRET',''))
        runner=Runner(c,a.state,client,a.live);runner.bootstrap();cycles=0
        while a.cycles==0 or cycles<a.cycles:
            try:print(json.dumps(runner.cycle()),flush=True)
            except Exception as e:
                runner.log({'event':'error','timestamp':int(time.time()*1000),'error':str(e)})
                if runner.state.get('inflight'):raise
                print(f'Cycle blocked: {e}',flush=True)
            cycles+=1
            if a.cycles==0 or cycles<a.cycles:time.sleep(60)

if __name__=='__main__':main()
