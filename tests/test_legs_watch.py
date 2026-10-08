"""The exits the regime-legs runner checks every minute on live quotes, and the loss brake on new entries."""
import json,sys,unittest
from dataclasses import asdict,replace
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parent))   # the tests folder, for test_legs helpers
import test_legs as T
from test_legs import C,row,FakeClient,HOUR
from roostoo.bot import Runner,save_state
from roostoo.legs import watch
from roostoo.rules import PairRule
from roostoo.strategy import Config

W=replace(C,stop_loss=.02,profit_trail=.01,mr_take_profit=.01,fast_cut=.01,fast_minutes=15)
NOW=10**9;DOWN=dict(ema_fast=99.,age_up=10**6,age_down=1)
def held(leg,side,**more):return dict(dict(leg=leg,side=side,entry=100.,bar=5,high=100.,low=100.,level=None),**more)
def at(price):return {'X/USD':{'bid':price,'ask':price}}
def seen(leg,side,*prices,config=W,drift=None,**more):
    """Show one position a run of prices; return what watch said at each and the position."""
    p=held(leg,side,**more);return [watch({'X/USD':p},at(price),config,NOW,drift or {}) for price in prices],p


class WatchTests(unittest.TestCase):
    HIT=lambda self,reason:[('X/USD',reason)]

    def test_the_stop_loss_closes_two_percent_against_the_entry(self):
        self.assertEqual(seen('ema',1,98.01,98.)[0],[[],self.HIT('stop loss')])
        self.assertEqual(seen('ema',-1,101.99,102.)[0],[[],self.HIT('stop loss')])
        self.assertEqual(seen('mr',1,97.)[0],[self.HIT('stop loss')])

    def test_the_profit_lock_waits_for_a_profit_after_fees_then_sells_one_percent_off_the_best_price(self):
        said,p=seen('ema',1,103.,102.5,101.9);self.assertEqual(said,[[],[],self.HIT('profit lock')]);self.assertEqual(p['best'],103.)
        said,p=seen('ema',-1,97.,97.5,98.);self.assertEqual(said,[[],[],self.HIT('profit lock')]);self.assertEqual(p['best'],97.)
        # 0.2% of fees: a best price of +0.15% was never a profit, so a 1% slip from it is left to the stop-loss
        self.assertEqual(seen('ema',1,100.15,99.)[0],[[],[]])
        self.assertEqual(seen('ema',1,100.3,99.2)[0],[[],self.HIT('profit lock')])
        self.assertEqual(seen('ema',1,110.,109.5,111.,110.)[0],[[],[],[],[]])                            # still within 1% of its best

    def test_a_mean_reversion_position_is_closed_at_its_small_profit_target(self):
        self.assertEqual(seen('mr',1,101.1,101.3)[0],[[],self.HIT('profit target')])
        self.assertEqual(seen('mr',-1,98.9,98.7)[0],[[],self.HIT('profit target')])
        self.assertEqual(seen('ema',1,101.3)[0],[[]])                                                    # a trend position runs on

    def test_a_losing_position_that_keeps_falling_fast_is_cut_before_its_stop(self):
        self.assertEqual(seen('ema',1,99.5,drift={'X/USD':-.012})[0],[self.HIT('fast fall')])
        self.assertEqual(seen('ema',-1,100.5,drift={'X/USD':.012})[0],[self.HIT('fast fall')])
        self.assertEqual(seen('ema',1,99.5,drift={'X/USD':-.005})[0],[[]])                               # falling, not fast
        self.assertEqual(seen('ema',1,100.1,drift={'X/USD':-.012})[0],[[]])                              # not losing
        self.assertEqual(seen('ema',1,99.5)[0],[[]])                                                     # no price history yet
        self.assertEqual(seen('ema',1,99.5,drift={'X/USD':-.012},opened=NOW-5*60000)[0],[[]])            # the fall before the entry is not held against it

    def test_rules_set_to_zero_are_off_and_a_wide_quote_is_not_acted_on(self):
        self.assertEqual(seen('mr',1,50.,150.,config=C,drift={'X/USD':-.5})[0],[[],[]])
        p=held('ema',1);self.assertEqual(watch({'X/USD':p},{'X/USD':{'bid':90.,'ask':100.,'tradable':False}},W,NOW,{}),[])
        self.assertNotIn('best',p);self.assertEqual(watch({'X/USD':p},{},W,NOW,{}),[])
        for bad in (dict(stop_loss=1.),dict(profit_trail=-.01),dict(fast_minutes=0),dict(fast_minutes=1.5)):
            with self.assertRaises(ValueError):replace(W,**bad).validate()


class RunnerWatchTests(unittest.TestCase):
    setUp=T.RunnerTests.setUp;decide_hour=T.RunnerTests.decide_hour;step=T.RunnerTests.step
    FLAT={'A/USD':row(),'B/USD':row(),'D/USD':row()}
    def runner(self,config=W):
        r=Runner(config,self.path,FakeClient(),False);r.rules={p:PairRule() for p in self.pairs}
        r.read_quotes=lambda:(self.quotes,self.now);r.refresh_features=lambda now:None
        return r
    def price(self,pair,value):self.quotes[pair]={'bid':value,'ask':value}

    def test_a_winner_is_sold_inside_the_hour_once_it_slips_one_percent_and_is_not_bought_straight_back(self):
        r=self.runner();self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(age_up=3)}),{'A/USD':'BULL'})
        self.assertEqual(self.step(r)['done'],'BUY A/USD')
        self.price('A/USD',103.);self.assertIsNone(self.step(r)['done'])
        self.price('A/USD',101.9);status=self.step(r)
        self.assertEqual((status['done'],status['why'],r.state['book'],r.state['locks']),('SELL A/USD','profit lock',{},{'A/USD':1006}))
        self.assertGreater(r.state['cash'],100000.)                                                     # the profit was kept
        self.now=1001*HOUR;self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(age_up=4)}),{'A/USD':'BULL'})
        self.assertIsNone(self.step(r)['done'])                                                         # the coin waits out its cooldown

    def test_a_short_is_covered_on_its_stop_and_a_dip_buy_is_sold_at_its_target_one_order_per_minute(self):
        r=self.runner();self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(**DOWN),'D/USD':row(z=-3.2)}),{'B/USD':'BEAR','D/USD':'CHOP'})
        self.assertEqual([self.step(r)['done'] for _ in range(2)],['SHORT B/USD','BUY D/USD'])
        self.assertAlmostEqual(r.state['shorts']['B/USD']['collateral']/100000,C.max_position,places=3)  # 1% risk over a 2% stop is capped at max_position
        self.price('B/USD',102.1);self.price('D/USD',101.5);first=self.step(r);second=self.step(r)
        self.assertEqual(sorted((s['done'],s['why']) for s in (first,second)),[('COVER B/USD','stop loss'),('SELL D/USD','profit target')])
        self.assertEqual((r.state['book'],r.state['shorts'],self.step(r)['done']),({},{},None))

    def test_a_fall_is_judged_fast_from_the_bots_own_minute_prices(self):
        r=self.runner();self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(age_up=3)}),{'A/USD':'BULL'})
        self.assertEqual(self.step(r)['done'],'BUY A/USD')
        self.price('A/USD',98.9);self.assertIsNone(self.step(r)['done'])                                 # one minute in: no history, and above the stop
        self.price('A/USD',100.)
        for _ in range(16):self.assertIsNone(self.step(r)['done'])
        self.price('A/USD',98.9);status=self.step(r);self.assertEqual((status['done'],status['why']),('SELL A/USD','fast fall'))

    def test_the_loss_brake_opens_nothing_while_the_account_is_two_percent_below_its_recent_high(self):
        r=self.runner(replace(W,drawdown_brake=.02,brake_window_bars=24));entry=dict(self.FLAT,**{'A/USD':row(age_up=3)})
        self.decide_hour(r,self.FLAT,{});self.assertEqual((self.step(r)['brake'],r.state['equity_marks']),(False,[[1000,100000.]]))
        r.state['cash']=97900.;self.now=1001*HOUR;self.decide_hour(r,entry,{'A/USD':'BULL'})
        status=self.step(r);self.assertEqual((status['brake'],status['done'],status['queued'],r.state['fills']),(True,None,0,0))
        r.state['cash']=99000.;self.now=1002*HOUR;self.decide_hour(r,entry,{'A/USD':'BULL'})
        status=self.step(r);self.assertEqual((status['brake'],status['done']),(False,'BUY A/USD'))
        self.assertAlmostEqual(self.step(r)['invested'],.2475,places=2)
        r.state['cash']-=3000.;self.price('A/USD',100.5);status=self.step(r)                             # braked again: the open position is kept
        self.assertEqual((status['brake'],status['done'],list(r.state['book'])),(True,None,['A/USD']))
        self.now=1030*HOUR;self.decide_hour(r,self.FLAT,{});self.assertFalse(self.step(r)['brake'])      # the old high has aged out of the window

    def test_positions_opened_under_the_hourly_rules_keep_their_book_and_come_under_the_new_exits(self):
        from roostoo.migrate_state import digest,migrate
        root=Path(__file__).resolve().parents[1]
        hourly=Config(**json.loads((root/'config/regime_hourly_candidate.json').read_text()))
        live=Config(**json.loads((root/'config/live_candidate.json').read_text()))
        self.assertEqual((live.profit_trail,live.stop_loss>0,live.mr_take_profit>0,live.drawdown_brake>0),(.01,True,True,True))
        logged={k:v for k,v in asdict(hourly).items() if k not in ('stop_loss','profit_trail','mr_take_profit','fast_cut','fast_minutes')}
        book={'SOL/USD':dict(leg='mr',side=1,entry=100.,bar=990,high=100.,low=100.,level=None)}          # as the deployed runner wrote it
        state=dict(Runner(hourly,self.path,FakeClient(),False).state,config_hash=digest(hourly,1),cash=95000.,inventory={'SOL/USD':50.},book=book,fills=62)
        save_state(self.path,state);self.path.with_suffix('.jsonl').write_text(json.dumps({'event':'start','config':logged})+'\n')
        client=Mock();client.exchange_info.return_value=json.loads((root/'config/exchange_info.json').read_text())
        migrate(self.path,live,root/'config/universe-50.json',False,client)
        moved=json.loads(self.path.read_text());self.assertEqual((moved['config_hash'],moved['book'],moved['fills']),(digest(live),book,62))
        self.pairs=('SOL/USD','B/USD','D/USD');self.quotes={p:{'bid':100.,'ask':100.} for p in self.pairs}
        r=self.runner(live);self.decide_hour(r,{'SOL/USD':row(z=-1.),'B/USD':row(),'D/USD':row()},{})
        self.price('SOL/USD',97.5);status=self.step(r);self.assertEqual((status['done'],status['why']),('SELL SOL/USD','stop loss'))

if __name__=='__main__':unittest.main()
