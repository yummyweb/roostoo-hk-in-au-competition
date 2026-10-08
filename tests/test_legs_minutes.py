"""Minute bars: the regime-legs runner builds a bar every cycle from Roostoo's quotes and decides every minute."""
import io,json,sys,time,unittest
from dataclasses import asdict,replace
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parent))   # the tests folder, for test_legs helpers
import test_legs as T
from test_legs import C,row,FakeClient
from roostoo import bot
from roostoo.bot import Runner,save_state
from roostoo.legs import decide
from roostoo.rules import PairRule
from roostoo.strategy import Config

MINUTE=60000
M=replace(C,bar_minutes=1,fast=3,slow=6,mr_window=20,ema_fresh_bars=30,cooldown_bars=10,mr_cooldown_bars=10,mr_hold_bars=30,
          stop_loss=.02,profit_trail=.01,mr_take_profit=.01)


class MinuteTests(unittest.TestCase):
    FLAT={'A/USD':row(),'B/USD':row(),'D/USD':row()}
    def setUp(self):
        T.RunnerTests.setUp(self)
        patcher=patch.object(bot,'MINUTE_REGIME',str(self.regime));patcher.start();self.addCleanup(patcher.stop)
        self.now=30000000*MINUTE+5000
    def runner(self,config=M):
        r=Runner(config,self.path,FakeClient(),False);r.rules={p:PairRule() for p in self.pairs}
        r.read_quotes=lambda:(self.quotes,self.now);return r
    def stubbed(self,config=M):
        r=self.runner(config);r.refresh_minutes=lambda quotes,now:None;return r
    def decide_minute(self,r,features,labels):
        r.features=features;r.labels=labels;r.feature_hour=(self.now+MINUTE)//MINUTE          # the cycle about to run
    def step(self,r):
        self.now+=MINUTE
        with patch.object(bot.time,'time',return_value=self.now/1000):return r.cycle()
    def price(self,pair,value):self.quotes[pair]={'bid':value,'ask':value}

    def test_a_hairline_cross_is_not_entered_and_a_fixed_stop_replaces_the_atr_trail(self):
        gap=replace(C,ema_min_gap=.001)
        self.assertEqual(decide({'A/USD':row(ema_fast=100.05,age_up=1)},{'A/USD':'BULL'},{},{},gap,10)[1],[])
        self.assertEqual(len(decide({'A/USD':row(ema_fast=100.2,age_up=1)},{'A/USD':'BULL'},{},{},gap,10)[1]),1)
        self.assertEqual(len(decide({'A/USD':row(ema_fast=99.8,age_up=10**6,age_down=1)},{'A/USD':'BEAR'},{},{},gap,10)[1]),1)
        fallen=lambda:({'A/USD':row(close=90.,bar_low=90.)},{},{'A/USD':dict(leg='ema',side=1,entry=100.,bar=5,high=100.,low=100.,level=None)},{})
        self.assertEqual(decide(*fallen(),C,10)[0],['A/USD'])                                          # 6 x ATR below its high
        self.assertEqual(decide(*fallen(),replace(C,stop_loss=.02),10)[0],[])                          # left to the stop-loss checked every minute
        for bad in (dict(bar_minutes=7),dict(bar_minutes=1.),dict(ema_min_gap=-.1)):
            with self.assertRaises(ValueError):replace(C,**bad).validate()

    def test_bars_are_built_from_the_exchange_quotes_after_a_warm_up_from_public_minute_candles(self):
        asked=[]
        def candles(url,timeout):
            asked.append(url);start=(self.now+MINUTE)//MINUTE*MINUTE-50*MINUTE
            return io.StringIO(json.dumps([[start+k*MINUTE,'0','0','0',str(100+k/10),'0'] for k in range(50)]))
        r=self.runner();self.price('A/USD',106.)
        with patch.object(bot,'urlopen',candles):status=self.step(r)
        self.assertEqual(sorted(u.split('symbol=')[1].split('&')[0] for u in asked),['AUSDT','BUSDT','DUSDT'])
        self.assertTrue(all('interval=1m' in u for u in asked))
        self.assertEqual({p:s[0].count for p,s in r.series.items()},dict.fromkeys(self.pairs,51))      # 50 candles and this cycle's quote
        self.assertEqual((r.series['A/USD'][2],r.features['A/USD']['close'],r.features['A/USD']['bar_low']),(106.,106.,104.9))
        self.assertEqual((status['ready'],r.feature_hour),(3,self.now//MINUTE))                        # max(3 x slow, 2 x mr_window) = 40 bars
        with patch.object(bot,'urlopen',Mock(side_effect=AssertionError('warmed once'))):self.step(r)
        self.assertEqual(r.series['A/USD'][0].count,52)

    def test_without_the_public_history_the_cycle_is_reported_blocked_and_tried_again(self):
        r=self.runner()
        with patch.object(bot,'urlopen',Mock(side_effect=OSError('down'))):
            with self.assertRaisesRegex(ValueError,'Binance candle history unavailable'):self.step(r)
        self.assertIsNone(r.series)

    def test_decisions_holding_times_and_waits_are_counted_in_minutes(self):
        r=self.stubbed();self.decide_minute(r,dict(self.FLAT,**{'A/USD':row(age_up=3)}),{'A/USD':'BULL'})
        self.assertEqual(self.step(r)['done'],'BUY A/USD');bought=self.now//MINUTE
        self.assertEqual(r.state['book']['A/USD']['bar'],bought)
        with patch.object(bot,'decide',wraps=bot.decide) as decided:
            for _ in range(3):
                self.decide_minute(r,dict(self.FLAT,**{'A/USD':row(age_up=3)}),{'A/USD':'BULL'});self.assertIsNone(self.step(r)['done'])
            self.assertEqual(decided.call_count,3)                                                     # one decision every minute
        self.price('A/USD',103.);self.decide_minute(r,dict(self.FLAT,**{'A/USD':row(age_up=3)}),{'A/USD':'BULL'});self.step(r)
        self.price('A/USD',101.9);self.decide_minute(r,dict(self.FLAT,**{'A/USD':row(age_up=3)}),{'A/USD':'BULL'});status=self.step(r)
        self.assertEqual((status['done'],status['why'],r.state['locks']),('SELL A/USD','profit lock',{'A/USD':self.now//MINUTE+10}))
        for _ in range(10):                                                                             # the coin waits ten minutes
            self.decide_minute(r,dict(self.FLAT,**{'A/USD':row(age_up=3)}),{'A/USD':'BULL'});self.assertIsNone(self.step(r)['done'])
        self.decide_minute(r,dict(self.FLAT,**{'A/USD':row(age_up=3)}),{'A/USD':'BULL'});self.assertEqual(self.step(r)['done'],'BUY A/USD')

    def test_a_ledger_of_hourly_bars_moves_to_shorter_bars_with_its_positions_and_fresh_clocks(self):
        from roostoo.migrate_state import digest,migrate
        root=Path(__file__).resolve().parents[1]
        hourly=Config(**json.loads((root/'config/regime_hourly_exits_candidate.json').read_text()))
        live=Config(**json.loads((root/'config/live_candidate.json').read_text()))
        self.assertEqual((live.bar_minutes,live.rank_model,live.ride>0,live.profit_arm>0),(15,'regime_legs',True,True))
        logged={k:v for k,v in asdict(hourly).items() if k not in ('bar_minutes','ema_min_gap','profit_arm','ride')}       # written before those fields existed
        book={'SOL/USD':dict(leg='mr',side=1,entry=100.,bar=497630,high=101.,low=99.,level=95.,best=100.5,opened=5)}
        state=dict(Runner(hourly,self.path,FakeClient(),False).state,config_hash=digest(hourly,1),cash=95000.,inventory={'SOL/USD':50.},
                   book=book,locks={'ETH/USD':497640},fills=70)
        save_state(self.path,state);self.path.with_suffix('.jsonl').write_text(json.dumps({'event':'start','config':logged})+'\n')
        client=Mock();client.exchange_info.return_value=json.loads((root/'config/exchange_info.json').read_text())
        migrate(self.path,live,root/'config/universe-crypto.json',False,client)
        moved=json.loads(self.path.read_text());position=moved['book']['SOL/USD']
        self.assertEqual((moved['config_hash'],moved['locks'],moved['fills'],position['level']),(digest(live),{},70,None))
        self.assertAlmostEqual(position['bar'],time.time()*1000//(15*MINUTE),delta=1)
        self.assertEqual({k:position[k] for k in ('leg','side','entry','best')},{'leg':'mr','side':1,'entry':100.,'best':100.5})
        Runner(live,self.path,FakeClient())                                                            # the migrated ledger opens under the live preset


if __name__=='__main__':unittest.main()
