import json
import math
import statistics
import tempfile
import unittest
from dataclasses import asdict,replace
from pathlib import Path
from unittest.mock import patch

from roostoo import bot
from roostoo.api import APIError
from roostoo.bot import Runner,save_state
from roostoo.data import synthetic
from roostoo.legs import decide
from roostoo.regime_hmm import RegimeFilter
from roostoo.rules import PairRule
from roostoo.strategy import Config,Indicators

HOUR=3600000
C=Config(strategy='allocation',rank_model='regime_legs',fast=48,slow=200,stop_atr=6.,risk_per_trade=.01,top_n=2,
         max_position=.2475,max_exposure=.99,cooldown_bars=6,allow_short=True,max_drawdown=.3)
IDENTITY=[[1.,0.],[0.,1.]]
REGIME=dict(return_bars=24,vol_bars=24,feature_mean=[0.,.01],feature_std=[.05,.01],means=[[-1.,0.],[0.,0.],[1.,0.]],
            covariances=[IDENTITY]*3,transition=[[.9,.05,.05],[.05,.9,.05],[.05,.05,.9]],start=[1/3]*3,
            bear_state=0,chop_state=1,bull_state=2)


def row(**changes):
    """A flat, uninteresting coin: fast EMA above slow for a long time, price at its mean."""
    return dict(dict(ready=True,close=100.,bar_high=100.5,bar_low=99.5,atr_24=1.,ema_fast=101.,ema_slow=100.,
                     age_up=500,age_down=10**6,z=0.),**changes)


class DecideTests(unittest.TestCase):
    def test_label_picks_the_leg_and_the_side(self):
        features={'A/USD':row(age_up=3),                                     # fresh up-cross
                  'B/USD':row(ema_fast=99.,age_up=10**6,age_down=2),          # fresh down-cross
                  'C/USD':row(age_up=13),                                    # up-cross too old
                  'D/USD':row(z=-3.2),'E/USD':row(z=3.5),'F/USD':row(z=-3.1),
                  'G/USD':row(ema_fast=99.,age_up=10**6,age_down=2)}
        labels={'A/USD':'BULL','B/USD':'BEAR','C/USD':'BULL','D/USD':'CHOP','E/USD':'CHOP','F/USD':'BULL','G/USD':'BULL'}
        exits,entries=decide(features,labels,{},{},C,1000)
        self.assertEqual(exits,[])
        # Trend entries first (the stop is 6 ATR = 6% away, so 1% of equity at risk is a 16.7% position), then the
        # mean-reversion entries, furthest from the mean first. F is stretched but not in CHOP; G crossed down but is not in BEAR.
        self.assertEqual([(p,side,leg) for p,side,leg,_ in entries],
                         [('A/USD',1,'ema'),('B/USD',-1,'ema'),('E/USD',-1,'mr'),('D/USD',1,'mr')])
        self.assertAlmostEqual(entries[0][3],.01/.06);self.assertEqual(entries[2][3],C.mr_fraction)
        long_only=decide(features,labels,{},{},replace(C,allow_short=False),1000)[1]
        self.assertEqual([(p,side) for p,side,_,_ in long_only],[('A/USD',1),('D/USD',1)])
        calm=decide(dict(features,**{'A/USD':row(age_up=3,atr_24=.1)}),labels,{},{},C,1000)[1]
        self.assertEqual(calm[0][3],C.max_position)                          # a tight stop cannot buy more than one slot

    def test_slots_locks_and_readiness_limit_entries(self):
        features={p:row(age_up=1,ema_fast=101.+i) for i,p in enumerate(('A/USD','B/USD','C/USD'))}
        labels=dict.fromkeys(features,'BULL')
        entries=decide(features,labels,{},{},C,10)[1]
        self.assertEqual([p for p,*_ in entries],['C/USD','B/USD'])           # two slots, widest gap first
        self.assertEqual([p for p,*_ in decide(features,labels,{},{'C/USD':11},C,10)[1]],['B/USD','A/USD'])
        self.assertEqual([p for p,*_ in decide(features,labels,{},{'C/USD':10},C,10)[1]],['C/USD','B/USD'])
        features['C/USD']['ready']=False
        self.assertEqual([p for p,*_ in decide(features,labels,{},{},C,10)[1]],['B/USD','A/USD'])
        book={'A/USD':dict(leg='ema',side=1,entry=100.,bar=5,high=100.,low=100.,level=None)}
        self.assertEqual([p for p,*_ in decide(features,labels,book,{},C,10)[1]],['B/USD'])   # one slot already used

    def test_trend_exits_on_the_opposite_cross_or_a_ratcheting_stop(self):
        long=dict(leg='ema',side=1,entry=100.,bar=5,high=100.,low=100.,level=None)
        short=dict(leg='ema',side=-1,entry=100.,bar=5,high=100.,low=100.,level=None)
        book={'A/USD':dict(long),'B/USD':dict(short)};locks={}
        calm={'A/USD':row(close=105.,bar_high=110.),'B/USD':row(close=95.,bar_low=90.,ema_fast=99.,age_down=40)}
        self.assertEqual(decide(calm,{},book,locks,C,10)[0],[])
        self.assertEqual((book['A/USD']['level'],book['B/USD']['level']),(104.,96.))   # 110 - 6 ATR and 90 + 6 ATR
        wide={'A/USD':row(close=104.5,atr_24=3.),'B/USD':row(close=95.5,atr_24=3.,ema_fast=99.)}
        self.assertEqual(decide(wide,{},book,locks,C,11)[0],[])
        self.assertEqual((book['A/USD']['level'],book['B/USD']['level']),(104.,96.))   # a wider range never loosens them
        hit={'A/USD':row(close=104.),'B/USD':row(close=96.,ema_fast=99.)}
        self.assertEqual(decide(hit,{},book,locks,C,12)[0],['A/USD','B/USD']);self.assertEqual(locks,{})
        book={'A/USD':dict(long),'B/USD':dict(short)}
        crossed={'A/USD':row(ema_fast=99.),'B/USD':row(ema_fast=101.)}
        self.assertEqual(decide(crossed,{},book,locks,C,12)[0],['A/USD','B/USD'])
        self.assertEqual(locks,{'A/USD':18,'B/USD':18})                              # six-bar pause after a cross-back

    def test_mean_reversion_exits_at_the_mean_on_time_or_on_a_large_adverse_move(self):
        def held(side):return {'X/USD':dict(leg='mr',side=side,entry=100.,bar=10,high=100.,low=100.,level=None)}
        for side,stay,back,against in ((1,-1.,0.,79.),(-1,1.,0.,121.)):
            self.assertEqual(decide({'X/USD':row(z=stay)},{},held(side),{},C,20)[0],[])
            self.assertEqual(decide({'X/USD':row(z=stay)},{},held(side),{},C,58)[0],['X/USD'])    # 48 bars after entry
            self.assertEqual(decide({'X/USD':row(z=back)},{},held(side),{},C,20)[0],['X/USD'])
            locks={};self.assertEqual(decide({'X/USD':row(z=stay,close=against)},{},held(side),locks,C,20)[0],['X/USD'])
            self.assertEqual(locks,{'X/USD':33})                                     # exit fills in bar 21, then 12 bars out
        self.assertEqual(decide({'X/USD':row(z=None)},{},held(1),{},C,20)[0],[])


class FeatureTests(unittest.TestCase):
    def test_indicator_rows_match_slow_references(self):
        bars,_=synthetic(days=30);btc=[b for b in bars if b.pair=='BTC/USD'];closes=[b.close for b in btc]
        c=replace(C,fast=12,slow=48,mr_window=30);state=Indicators(c);age=[10**6,10**6];on=[False,False]
        def ema(n,i):
            value=sum(closes[:n])/n
            for x in closes[n:i+1]:value+=2/(n+1)*(x-value)
            return value
        for i,bar in enumerate(btc):
            f=state.update(bar)
            fast=ema(12,i) if i>=11 else None;slow=ema(48,i) if i>=47 else None
            for k,now in enumerate((slow is not None and fast>slow,slow is not None and fast<slow)):
                age[k]=(age[k]+1 if on[k] else 0) if now else 10**6;on[k]=now
            self.assertEqual((f['age_up'],f['age_down']),tuple(age))
            self.assertEqual(f['ready'],i+1>=max(3*48,2*30))
            self.assertEqual((f['bar_high'],f['bar_low']),(bar.high,bar.low))
            if i%37==0 and i>=47:
                self.assertAlmostEqual(f['ema_fast'],fast,places=9);self.assertAlmostEqual(f['ema_slow'],slow,places=9)
            if i>=29:
                window=closes[i-29:i+1];self.assertAlmostEqual(f['z'],(bar.close-statistics.mean(window))/statistics.pstdev(window),places=6)
            else:self.assertIsNone(f['z'])

    def test_regime_filter_labels_rising_falling_and_flat_coins(self):
        def label(step):
            f=RegimeFilter(REGIME);price=100.
            for i in range(80):
                price*=math.exp(step+(.0001 if i%2 else -.0001));out=f.update(price)
                if i<23:self.assertIsNone(out)
            return f.label
        self.assertEqual((label(.002),label(-.002),label(0.)),('BULL','BEAR','CHOP'))
        self.assertIsNone(RegimeFilter(REGIME).label)


class FakeClient:
    """Exchange stand-in: a USD wallet, a list of open shorts, and scripted answers to short requests."""
    def __init__(self):
        self.offset=0;self.usd=100000.;self.positions=[];self.calls=[];self.fail=None
    def sync_clock(self):return {}
    def balance(self):return {'SpotWallet':{'USD':{'Free':self.usd,'Lock':sum(p['Collateral'] for p in self.positions)}}}
    def short_positions(self):return {'Success':True,'Positions':list(self.positions)}
    def request(self,method,endpoint,params=None,signed=False):
        self.calls.append((endpoint,dict(params or {})))
        if self.fail:raise self.fail
        if endpoint=='/v6/short_open':
            collateral=float(params['collateral']);self.usd-=collateral*1.001
            self.positions.append({'Pair':params['pair'],'EntryPrice':100.,'ShortQty':collateral/100,'Collateral':collateral,'PositionValue':collateral})
            return {'Success':True,'EntryPrice':100.,'ShortQty':collateral/100,'Collateral':collateral,'Status':'OPEN'}
        if endpoint=='/v6/short_close':
            held=next(p for p in self.positions if p['Pair']==params['pair']);self.positions.remove(held);self.usd+=held['Collateral']
            return {'Success':True,'ClosePrice':100.,'FullyClosed':True}
        raise AssertionError(endpoint)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.regime=Path(self.folder.name)/'coin_regime.json';self.regime.write_text(json.dumps(REGIME))
        patcher=patch.object(bot,'COIN_REGIME',self.regime);patcher.start();self.addCleanup(patcher.stop)
        self.path=Path(self.folder.name)/'state.json';self.pairs=('A/USD','B/USD','D/USD')
        self.quotes={p:{'bid':100.,'ask':100.} for p in self.pairs};self.now=1000*HOUR+5000

    def runner(self,live=False,client=None):
        r=Runner(C,self.path,client or FakeClient(),live);r.rules={p:PairRule() for p in self.pairs}
        r.read_quotes=lambda:(self.quotes,self.now);r.refresh_features=lambda now:None
        return r

    def decide_hour(self,r,features,labels):
        r.features=features;r.labels=labels;r.feature_hour=self.now//HOUR

    def step(self,r,minutes=1):
        self.now+=minutes*60000
        with patch.object(bot.time,'time',return_value=self.now/1000):return r.cycle()

    def test_paper_cycle_opens_holds_and_closes_long_and_short_positions(self):
        r=self.runner()
        self.decide_hour(r,{'A/USD':row(age_up=3),'B/USD':row(ema_fast=99.,age_up=10**6,age_down=2),'D/USD':row(z=-3.2)},
                         {'A/USD':'BULL','B/USD':'BEAR','D/USD':'CHOP'})
        done=[self.step(r)['done'] for _ in range(4)]
        self.assertEqual(done,['BUY A/USD','SHORT B/USD','BUY D/USD',None])           # one order a minute, then nothing left
        book=r.state['book'];self.assertEqual({p:(v['leg'],v['side'],v['bar']) for p,v in book.items()},
                                              {'A/USD':('ema',1,1000),'B/USD':('ema',-1,1000),'D/USD':('mr',1,1000)})
        status=self.step(r);self.assertEqual(status['positions'],{'ema_long':1,'ema_short':1,'mr_long':1,'mr_short':0})
        self.assertAlmostEqual(status['equity'],100000.,delta=60)                      # only fees and slippage were paid
        self.assertAlmostEqual(r.state['shorts']['B/USD']['collateral'],100000*.01/.06,delta=30)
        # A restart keeps the book; the next hour's candles close every position.
        save_state(self.path,r.state);r=self.runner();self.now=1001*HOUR
        self.decide_hour(r,{'A/USD':row(ema_fast=99.),'B/USD':row(ema_fast=101.),'D/USD':row(z=.1)},{})
        self.assertEqual([self.step(r)['done'] for _ in range(4)],['SELL A/USD','COVER B/USD','SELL D/USD',None])
        self.assertEqual((r.state['book'],r.state['shorts']),({},{}));self.assertEqual(r.state['fills'],6)
        self.assertEqual(r.state['locks'],{'A/USD':1006,'B/USD':1006,'D/USD':1013})
        self.assertAlmostEqual(self.step(r)['equity'],100000.,delta=120)

    def test_holdings_the_book_does_not_know_are_released_and_a_deep_drawdown_closes_everything(self):
        r=self.runner();r.state['inventory']={'D/USD':30.};r.state['cash']=97000.
        self.decide_hour(r,{p:row() for p in self.pairs},{})
        self.assertEqual(self.step(r)['done'],'SELL D/USD')
        self.now=1001*HOUR;self.decide_hour(r,{'A/USD':row(age_up=3),'B/USD':row(),'D/USD':row()},{'A/USD':'BULL'})
        self.assertEqual(self.step(r)['done'],'BUY A/USD')
        r.state['peak']=200000.;self.now=1002*HOUR;self.decide_hour(r,{p:row(age_up=1) for p in self.pairs},dict.fromkeys(self.pairs,'BULL'))
        status=self.step(r);self.assertTrue(status['halted']);self.assertEqual(status['done'],'SELL A/USD')
        self.assertEqual(self.step(r)['done'],None)

    def test_live_short_requests_use_the_documented_parameters_and_survive_refusals_and_timeouts(self):
        client=FakeClient();save_state(self.path,dict(Runner(C,self.path,client,True).state,fills=1))
        r=self.runner(True,client)
        self.decide_hour(r,{'A/USD':row(),'B/USD':row(ema_fast=99.,age_up=10**6,age_down=2),'D/USD':row()},{'B/USD':'BEAR'})
        self.assertEqual(self.step(r)['done'],'SHORT B/USD')
        endpoint,params=client.calls[-1];self.assertEqual((endpoint,sorted(params)),('/v6/short_open',['collateral','pair']))
        self.assertEqual(params['collateral'],'16666.66')
        self.assertEqual(self.step(r)['positions']['ema_short'],1)                     # locked USD does not block the cycle
        # The exchange refuses the close: nothing changes, nothing latches, the next hour tries again.
        self.now=1001*HOUR;self.decide_hour(r,{'A/USD':row(),'B/USD':row(ema_fast=101.),'D/USD':row()},{})
        client.fail=APIError('server busy');self.assertIsNone(self.step(r)['done'])
        self.assertIsNone(r.state['inflight']);self.assertIn('B/USD',r.state['book']);self.assertFalse(r.no_shorts)
        # A timeout leaves the request in flight; the position list settles it without stopping the bot.
        self.now=1002*HOUR;self.decide_hour(r,{'A/USD':row(),'B/USD':row(ema_fast=101.),'D/USD':row()},{})
        client.fail=TimeoutError('no answer')
        with self.assertRaises(TimeoutError):self.step(r)
        self.assertEqual(r.state['inflight']['kind'],'COVER')
        client.fail=None;client.positions.clear();r=self.runner(True,client)           # it did close; restart is allowed
        self.step(r);self.assertIsNone(r.state['inflight']);self.assertEqual(r.state['book'],{})

    def test_a_breakout_ledger_migrates_to_the_regime_legs_config(self):
        from roostoo.migrate_state import digest,migrate
        from unittest.mock import Mock
        root=Path(__file__).resolve().parents[1]
        old=Config(strategy='allocation',rank_model='breakout',momentum=12,top_n=4,max_position=.25,max_exposure=.99,take_profit_fraction=0.,
                   cooldown_bars=12,rebalance_bars=1,breakout_high_bars=120,trail_atr=4.)
        legs=Config(**json.loads((root/'config/live_candidate.json').read_text()))
        self.assertEqual((legs.rank_model,legs.allow_short),('regime_legs',True))
        logged={k:v for k,v in asdict(old).items() if not k.startswith(('mr_','ema_fresh'))}     # written before the legs fields existed
        state={'mode':'paper','config_hash':digest(old,1),'cash':100000.,'inventory':{},'peak':100000.,'halted':False,'last_submit':5,
               'inflight':None,'pending':None,'targets':{},'target_day':7,'fills':54,'stop_levels':{'X/USD':1.}}
        save_state(self.path,state);self.path.with_suffix('.jsonl').write_text(json.dumps({'event':'start','config':logged})+'\n')
        client=Mock();client.exchange_info.return_value=json.loads((root/'config/exchange_info.json').read_text())
        migrate(self.path,legs,root/'config/universe-50.json',False,client)
        moved=json.loads(self.path.read_text())
        self.assertEqual((moved['config_hash'],moved['book'],moved['queue'],moved['fills']),(digest(legs),{},[],54))
        Runner(legs,self.path,FakeClient())


    def test_an_account_that_cannot_short_keeps_trading_the_long_side(self):
        client=FakeClient();save_state(self.path,dict(Runner(C,self.path,client,True).state,fills=1))
        r=self.runner(True,client);client.fail=APIError('this competition does not allow short positions')
        both={'A/USD':row(),'B/USD':row(ema_fast=99.,age_up=10**6,age_down=2),'D/USD':row()}
        self.decide_hour(r,both,{'B/USD':'BEAR'})
        self.assertIsNone(self.step(r)['done']);self.assertTrue(r.no_shorts);self.assertEqual(r.state['locks']['B/USD'],1024)
        self.now=1001*HOUR;self.decide_hour(r,dict(both,**{'D/USD':row(ema_fast=99.,age_up=10**6,age_down=1)}),{'B/USD':'BEAR','D/USD':'BEAR'})
        calls=len(client.calls);self.assertIsNone(self.step(r)['done']);self.assertEqual(len(client.calls),calls)   # no further short requests


if __name__=='__main__':unittest.main()
