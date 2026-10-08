"""Entry timing of the regime legs: trend entries on a pullback, and the steep-drop buy with its own exits."""
import sys,unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))   # the tests folder, for the helpers of the other legs tests
import test_legs as T
from test_legs import C,row,FakeClient,HOUR
from test_legs_watch import W,seen
from roostoo.bot import Runner
from roostoo.legs import decide
from roostoo.rules import PairRule

FALLING=dict(ema_fast=99.,ema_slow=100.,age_up=10**6,age_down=300)    # fast EMA below slow for a long time: no fresh cross
P=replace(C,pullback=.01,momentum=6)
K=replace(C,crash_drop=.02,crash_take_profit=.01,crash_ride=.005,crash_guard=.005)
KW=replace(W,profit_arm=.01,crash_drop=.02,crash_take_profit=.01,crash_ride=.005,crash_guard=.005)   # the lock waits for a real profit, as live
def names(entries):return [(pair,side,leg) for pair,side,leg,_ in entries]
def crashed(close=97.9):return row(close=close,bar_high=100.,bar_low=close)


class PullbackTests(unittest.TestCase):
    def test_a_downtrend_is_shorted_on_a_bounce_and_an_uptrend_bought_on_a_dip(self):
        short=lambda move,label='BEAR',**f:names(decide({'A/USD':row(momentum=move,**dict(FALLING,**f))},{'A/USD':label},{},{},P,10)[1])
        self.assertEqual(short(.012),[('A/USD',-1,'ema')])                      # bounced 1.2% inside a downtrend: the cross is 300 bars old
        self.assertEqual((short(.005),short(-.02),short(0.)),([],[],[]))        # not enough of a bounce, or still falling
        self.assertEqual((short(.012,'CHOP'),short(.012,'BULL'),short(.012,None)),([],[],[]))
        self.assertEqual(short(.012,ema_fast=101.),[])                          # a bounce in a coin whose averages point up is not a downtrend
        long=lambda move,label='BULL':names(decide({'A/USD':row(momentum=move)},{'A/USD':label},{},{},P,10)[1])
        self.assertEqual(long(-.012),[('A/USD',1,'ema')])
        self.assertEqual((long(-.005),long(.02),long(-.012,'BEAR')),([],[],[]))
        self.assertEqual(names(decide({'A/USD':row(momentum=.012,**FALLING)},{'A/USD':'BEAR'},{},{},replace(P,allow_short=False),10)[1]),[])

    def test_the_largest_move_against_the_trend_goes_first_and_the_fresh_cross_rule_is_untouched_without_it(self):
        features={'A/USD':row(momentum=.012,**FALLING),'B/USD':row(momentum=.03,**FALLING),'D/USD':row(momentum=-.02)}
        labels={'A/USD':'BEAR','B/USD':'BEAR','D/USD':'BULL'}
        self.assertEqual(names(decide(features,labels,{},{},replace(P,top_n=1),10)[1]),[('B/USD',-1,'ema')])
        self.assertEqual(names(decide(features,labels,{},{},replace(P,top_n=3),10)[1]),[('B/USD',-1,'ema'),('D/USD',1,'ema'),('A/USD',-1,'ema')])
        self.assertEqual(decide(features,labels,{},{},C,10)[1],[])              # without pullback these old crosses are not entries
        # a pullback position is not closed when the averages cross back; it has a time limit instead
        held=lambda:{'A/USD':dict(leg='ema',side=-1,entry=100.,bar=10,high=100.,low=100.,level=None)}
        crossed={'A/USD':row(ema_fast=101.)};limit=replace(P,max_hold_bars=48,stop_loss=.02)
        self.assertEqual(decide(crossed,{},held(),{},replace(C,stop_loss=.02),20)[0],['A/USD'])        # the fresh-cross rule closes it
        self.assertEqual((decide(crossed,{},held(),{},limit,20)[0],decide(crossed,{},held(),{},limit,57)[0]),([],[]))
        locks={};self.assertEqual(decide(crossed,{},held(),locks,limit,58)[0],['A/USD']);self.assertEqual(locks,{'A/USD':58+C.cooldown_bars})
        for bad in (dict(pullback=1.),dict(pullback=-.01),dict(crash_drop=1.),dict(crash_ride=-.1)):
            with self.assertRaises(ValueError):replace(C,**bad).validate()


class SteepDropTests(unittest.TestCase):
    HIT=lambda self,reason:[('X/USD',reason)]
    def test_a_bear_coin_that_drops_two_percent_in_one_bar_is_bought(self):
        buy=lambda f,label='BEAR',config=K,book=None:decide({'A/USD':f},{'A/USD':label},book or {},{},config,10)[1]
        self.assertEqual(buy(crashed()),[('A/USD',1,'crash',C.mr_fraction)])
        self.assertEqual((buy(crashed(98.1)),buy(crashed(),'CHOP'),buy(crashed(),'BULL'),buy(crashed(),config=C)),([],[],[],[]))
        self.assertEqual(buy(dict(crashed(),ready=False)),[])
        full={'M/USD':dict(leg='mr',side=1,entry=100.,bar=9,high=100.,low=100.,level=None)}
        got=decide({'A/USD':crashed(),'M/USD':row(z=-1.)},{'A/USD':'BEAR'},full,{},replace(K,mr_slots=1),10)
        self.assertEqual(got,([],[]))                                           # it uses a mean-reversion slot
        both=decide({'A/USD':crashed(96.),'B/USD':crashed()},{'A/USD':'BEAR','B/USD':'BEAR'},{},{},replace(K,mr_slots=1),10)[1]
        self.assertEqual(names(both),[('A/USD',1,'crash')])                     # the steeper drop first

    def test_at_the_bar_close_only_its_time_limit_ends_it(self):
        book=lambda:{'A/USD':dict(leg='crash',side=1,entry=100.,bar=10,high=100.,low=100.,level=None)}
        flat={'A/USD':row(z=1.,ema_fast=99.)}                                  # back above its mean, averages pointing down: neither is its rule
        self.assertEqual(decide(flat,{},book(),{},K,57)[0],[])
        locks={};self.assertEqual(decide(flat,{},book(),locks,K,58)[0],['A/USD']);self.assertEqual(locks,{'A/USD':58+1+C.mr_cooldown_bars})

    def test_it_is_sold_at_one_percent_after_fees_unless_the_price_is_surging_and_at_its_entry_once_it_has_been_up(self):
        self.assertEqual(seen('crash',1,101.1,101.3,config=KW)[0],[[],self.HIT('profit target')])   # 0.9% then 1.1% after 0.2% of fees
        self.assertEqual(seen('crash',1,101.3,config=KW,quick={'X/USD':.006})[0],[[]])            # up 0.6% in the last minutes: held
        self.assertEqual(seen('crash',1,101.3,config=KW,quick={'X/USD':.002})[0],[self.HIT('profit target')])
        self.assertEqual(seen('crash',1,100.6,100.,config=KW)[0],[[],self.HIT('back to entry')])
        self.assertEqual(seen('crash',1,100.3,100.,99.,config=KW)[0],[[],[],[]])                  # never 0.5% up: left to the stop-loss
        self.assertEqual(seen('crash',1,97.9,config=KW)[0],[self.HIT('stop loss')])
        self.assertEqual(seen('mr',1,100.6,100.,config=KW)[0],[[],[]])                            # the other legs keep their own rules
        self.assertEqual(seen('ema',1,101.3,config=KW)[0],[[]])


class RunnerEntryTests(unittest.TestCase):
    setUp=T.RunnerTests.setUp;decide_hour=T.RunnerTests.decide_hour;step=T.RunnerTests.step
    FLAT={'A/USD':row(),'B/USD':row(),'D/USD':row()}
    def runner(self,config):
        r=Runner(config,self.path,FakeClient(),False);r.rules={p:PairRule() for p in self.pairs}
        r.read_quotes=lambda:(self.quotes,self.now);r.refresh_features=lambda now:None
        return r
    def price(self,pair,value):self.quotes[pair]={'bid':value,'ask':value}

    def test_a_pullback_entry_is_sent_at_once_and_a_steep_drop_buy_runs_to_its_target(self):
        config=replace(KW,pullback=.01,momentum=6,profit_arm=.006,ride=.003,fast_minutes=30,ride_short_minutes=10,ride_steep=.01)
        r=self.runner(config)
        self.decide_hour(r,dict(self.FLAT,**{'A/USD':crashed(),'B/USD':row(momentum=.012,**FALLING)}),{'A/USD':'BEAR','B/USD':'BEAR'})
        first=self.step(r);second=self.step(r)                                 # no waiting for the price to run the trade's way
        self.assertEqual([(s['done'],s['why']) for s in (first,second)],[('BUY A/USD','crash long in BEAR'),('SHORT B/USD','ema short in BEAR')])
        self.assertEqual(second['positions'],{'ema_long':0,'ema_short':1,'mr_long':0,'mr_short':0,'crash_long':1})
        self.price('A/USD',101.3);sold=self.step(r)
        self.assertEqual((sold['done'],sold['why'],sold['positions']['crash_long']),('SELL A/USD','profit target',0))
        self.assertEqual(r.state['locks']['A/USD'],1000+C.mr_cooldown_bars)


    def test_sharpe_and_sortino_come_from_utc_daily_equity_and_are_kept_in_the_state_and_the_log(self):
        import json,math,statistics
        from roostoo.metrics import ratios
        values=[100000.,101000.,99990.,100989.9];returns=[.01,-.01,.01]
        got=ratios(values);mean=statistics.mean(returns)
        self.assertAlmostEqual(got['sharpe'],mean/statistics.stdev(returns)*math.sqrt(365))
        self.assertAlmostEqual(got['sortino'],mean/math.sqrt(.01**2/3)*math.sqrt(365));self.assertEqual(got['days'],3)
        self.assertEqual((ratios([100000.,101000.]),ratios([100000.,101000.,102010.])['sortino']),({'sharpe':None,'sortino':None,'days':1},None))
        day=lambda k:(1000*HOUR//86400000+k)*86400000                                              # the test clock's day and the days before
        journal=[{'event':'snapshot','timestamp':day(-2)+5,'equity':99000.,'quotes':{}},{'event':'snapshot','timestamp':day(-2)+9,'equity':101000.},
                 {'event':'start','timestamp':day(-1)},{'event':'snapshot','timestamp':day(-1)+7,'equity':99990.,'book':{}}]
        self.path.with_suffix('.jsonl').write_text(''.join(json.dumps(event)+'\n' for event in journal))
        r=self.runner(KW);self.assertEqual(r.state['daily'],{str(day(-2)//86400000):101000.,str(day(-1)//86400000):99990.})   # the last value of each day
        self.decide_hour(r,self.FLAT,{});r.state['cash']=100989.9;status=self.step(r)
        self.assertEqual((status['sharpe'],status['sortino']),(round(got['sharpe'],2),round(got['sortino'],2)))
        saved=[json.loads(line) for line in self.path.with_suffix('.jsonl').read_text().splitlines()][-1]
        self.assertEqual((saved['event'],saved['sharpe'],saved['days'],r.state['daily'][str(day(0)//86400000)]),('snapshot',status['sharpe'],3,100989.9))


if __name__=='__main__':unittest.main()
