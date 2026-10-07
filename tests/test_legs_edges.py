"""Boundary and failure-path tests for the regime-legs strategy, found by mutating roostoo/legs.py and the short handling."""
import contextlib,io,json,sys,unittest
from dataclasses import asdict,replace
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))   # the tests folder, for test_legs helpers
import test_legs as T
from test_legs import C,row,FakeClient,HOUR
from roostoo import bot
from roostoo.api import APIError
from roostoo.bot import Runner,save_state
from roostoo.legs import decide

UP=dict(age_up=1);DOWN=dict(ema_fast=99.,age_up=10**6,age_down=1)
def held(leg,side,bar=5):return dict(leg=leg,side=side,entry=100.,bar=bar,high=100.,low=100.,level=None)
def names(entries):return [(p,side,leg) for p,side,leg,_ in entries]


class DecideKillers(unittest.TestCase):
    def test_L46_a_close_at_the_trailing_level_exits_despite_float_noise(self):
        # 0.7 - 6 x 0.05 is 0.3999999999999999 in floating point and 0.1 + 6 x 0.1 is 0.7000000000000001: both closes are AT the level
        book={'A/USD':dict(held('ema',1),entry=.6,high=.6,low=.6),'B/USD':dict(held('ema',-1),entry=.2,high=.2,low=.2)}
        at={'A/USD':row(close=.4,bar_high=.7,bar_low=.4,atr_24=.05),'B/USD':row(close=.7,bar_high=.7,bar_low=.1,atr_24=.1,ema_fast=99.)}
        self.assertEqual(decide(at,{},book,{},C,10)[0],['A/USD','B/USD'])
        book={'A/USD':dict(held('ema',1),entry=.6,high=.6,low=.6),'B/USD':dict(held('ema',-1),entry=.2,high=.2,low=.2)}
        near={'A/USD':dict(at['A/USD'],close=.40001),'B/USD':dict(at['B/USD'],close=.69999)}
        self.assertEqual(decide(near,{},book,{},C,10)[0],[])                                          # one tick inside is not a hit
    def test_L12_mr_stop_fires_at_exactly_twenty_percent(self):
        self.assertEqual(decide({'X/USD':row(z=-1.,close=80.)},{},{'X/USD':held('mr',1,10)},{},C,20)[0],['X/USD'])
        self.assertEqual(decide({'X/USD':row(z=1.,close=120.)},{},{'X/USD':held('mr',-1,10)},{},C,20)[0],['X/USD'])
        self.assertEqual(decide({'X/USD':row(z=-1.,close=80.01)},{},{'X/USD':held('mr',1,10)},{},C,20)[0],[])
        self.assertEqual(decide({'X/USD':row(z=1.,close=119.99)},{},{'X/USD':held('mr',-1,10)},{},C,20)[0],[])
    def test_L13_mr_time_limit_is_not_one_bar_early(self):
        self.assertEqual(decide({'X/USD':row(z=-1.)},{},{'X/USD':held('mr',1,10)},{},C,57)[0],[])        # 47 bars after entry
        self.assertEqual(decide({'X/USD':row(z=-1.)},{},{'X/USD':held('mr',1,10)},{},C,58)[0],['X/USD'])
    def test_L17_L20_held_positions_use_slots_and_are_not_entered_again(self):
        features={'A/USD':row(**UP),'B/USD':row(ema_fast=102.,**UP),'C/USD':row(ema_fast=103.,**UP)};labels=dict.fromkeys(features,'BULL')
        self.assertEqual(names(decide(features,labels,{'A/USD':held('ema',1)},{},C,10)[1]),[('C/USD',1,'ema')])   # top_n=2, one used
        # a coin held by the other leg is never entered again, whatever its signal (it stays: z is still below 0)
        stuck={'A/USD':row(z=-1.,**UP)}
        self.assertEqual(decide(stuck,{'A/USD':'BULL'},{'A/USD':held('mr',1)},{},C,10),([],[]))
        self.assertEqual(decide({'A/USD':row(z=-3.5)},{'A/USD':'CHOP'},{'A/USD':held('ema',1)},{},C,10),([],[]))
    def test_L21_L22_cross_is_fresh_through_bar_twelve(self):
        for age,expected in ((12,1),(13,0)):
            self.assertEqual(len(decide({'A/USD':row(age_up=age)},{'A/USD':'BULL'},{},{},C,10)[1]),expected)
            self.assertEqual(len(decide({'A/USD':row(ema_fast=99.,age_up=10**6,age_down=age)},{'A/USD':'BEAR'},{},{},C,10)[1]),expected)
    def test_L23_L24_ema_entries_need_the_matching_label(self):
        for label in ('CHOP','BEAR',None):self.assertEqual(decide({'A/USD':row(**UP)},{'A/USD':label},{},{},C,10)[1],[])
        for label in ('CHOP','BULL',None):self.assertEqual(decide({'A/USD':row(**DOWN)},{'A/USD':label},{},{},C,10)[1],[])
        self.assertEqual(decide({'A/USD':row(**UP)},{},{},{},C,10)[1],[])
    def test_L27_shorts_are_ranked_widest_gap_first_and_share_the_slots_with_longs(self):
        features={'A/USD':row(**DOWN),'B/USD':row(**dict(DOWN,ema_fast=97.)),'C/USD':row(ema_fast=102.,**UP)}
        labels={'A/USD':'BEAR','B/USD':'BEAR','C/USD':'BULL'}
        self.assertEqual(names(decide(features,labels,{},{},replace(C,top_n=1),10)[1]),[('B/USD',-1,'ema')])
        self.assertEqual(names(decide(features,labels,{},{},C,10)[1]),[('B/USD',-1,'ema'),('C/USD',1,'ema')])
    def test_L32_L33_mr_enters_at_exactly_three_sigma(self):
        got=decide({'A/USD':row(z=-3.),'B/USD':row(z=3.),'D/USD':row(z=-2.999),'E/USD':row(z=2.999)},dict.fromkeys('ABDE','CHOP') and {p+'/USD':'CHOP' for p in 'ABDE'},{},{},C,10)[1]
        self.assertEqual(names(got),[('A/USD',1,'mr'),('B/USD',-1,'mr')])
    def test_L36_mr_longs_are_ranked_most_stretched_first(self):
        got=decide({'A/USD':row(z=-3.2),'B/USD':row(z=-4.),'D/USD':row(z=3.6)},{p+'/USD':'CHOP' for p in 'ABD'},{},{},C,10)[1]
        self.assertEqual([p for p,*_ in got],['B/USD','D/USD','A/USD'])
    def test_L37_L38_mr_slots_cap_new_plus_held_positions(self):
        features={p+'/USD':row(z=-3.-i/10) for i,p in enumerate('ABDE')};labels=dict.fromkeys(features,'CHOP')
        self.assertEqual(len(decide(features,labels,{},{},C,10)[1]),4)                                  # mr_slots=10, top_n=2
        self.assertEqual([p for p,*_ in decide(features,labels,{},{},replace(C,mr_slots=3),10)[1]],['E/USD','D/USD','B/USD'])
        book={'X/USD':held('mr',1,9),'Y/USD':held('mr',-1,9)};features.update({'X/USD':row(z=-1.),'Y/USD':row(z=1.)})
        self.assertEqual([p for p,*_ in decide(features,labels,book,{},replace(C,mr_slots=3),10)[1]],['E/USD'])
    def test_L42_a_coin_with_no_range_is_skipped_not_divided_by_zero(self):
        self.assertEqual(decide({'A/USD':row(atr_24=0.,**UP)},{'A/USD':'BULL'},{},{},C,10)[1],[])


class Exchange(FakeClient):
    """FakeClient plus spot fills at 100 and coin balances."""
    def __init__(self):super().__init__();self.coins={};self.locked={}
    def balance(self):
        wallet=super().balance()
        wallet['SpotWallet'].update({a:{'Free':q,'Lock':self.locked.get(a,0)} for a,q in self.coins.items()});return wallet
    def request(self,method,endpoint,params=None,signed=False):
        if endpoint!='/v3/place_order':return super().request(method,endpoint,params,signed)
        self.calls.append((endpoint,dict(params)))
        if self.fail:raise self.fail
        sign=1 if params['side']=='BUY' else -1;quantity=float(params['quantity']);asset=params['pair'].split('/')[0]
        self.coins[asset]=self.coins.get(asset,0)+sign*quantity;self.usd-=sign*quantity*100
        return {'Success':True,'OrderDetail':{'Status':'FILLED','FilledAverPrice':100.}}


class RunnerKillers(unittest.TestCase):
    setUp=T.RunnerTests.setUp;runner=T.RunnerTests.runner;decide_hour=T.RunnerTests.decide_hour;step=T.RunnerTests.step
    FLAT={'A/USD':row(),'B/USD':row(),'D/USD':row()}
    def live(self,client,**state):
        save_state(self.path,dict(Runner(C,self.path,client,True).state,fills=1,**state));return self.runner(True,client)
    def tick(self,r,ms):
        self.now+=ms
        with patch.object(bot.time,'time',return_value=self.now/1000):return r.cycle()
    def posts(self,client):return [c for c in client.calls if c[0] in ('/v6/short_open','/v6/short_close','/v3/place_order')]

    def test_B21_one_order_per_minute_for_the_whole_account(self):
        r=self.runner();self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(age_up=3),'B/USD':row(**DOWN)}),{'A/USD':'BULL','B/USD':'BEAR'})
        self.assertEqual(self.tick(r,60000)['done'],'BUY A/USD')
        self.assertIsNone(self.tick(r,30000)['done']);self.assertIsNone(self.tick(r,29999)['done'])   # 59.999 s after the buy
        self.assertEqual(self.tick(r,1)['done'],'SHORT B/USD')

    def test_B32_one_decision_per_completed_candle(self):
        r=self.runner();self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(age_up=3)}),{'A/USD':'BULL'})
        with patch.object(bot,'decide',wraps=bot.decide) as decided:
            for _ in range(4):self.step(r)
            self.assertEqual(decided.call_count,1)
            self.now=1001*HOUR;r.feature_hour=1001;self.step(r);self.step(r);self.assertEqual(decided.call_count,2)

    def test_B33_an_untradable_quote_holds_the_action_in_the_queue(self):
        r=self.runner();self.quotes['A/USD']={'bid':100.,'ask':102.,'tradable':False}
        self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(age_up=3)}),{'A/USD':'BULL'})
        status=self.step(r);self.assertEqual((status['done'],status['queued'],r.state['fills']),(None,1,0))
        self.quotes['A/USD']={'bid':100.,'ask':100.};self.assertEqual(self.step(r)['done'],'BUY A/USD')

    def test_B34_exits_run_before_entries(self):
        r=self.runner();self.decide_hour(r,dict(self.FLAT,**{'D/USD':row(z=-3.2)}),{'D/USD':'CHOP'})
        self.assertEqual(self.step(r)['done'],'BUY D/USD')
        self.now=1001*HOUR;self.decide_hour(r,dict(self.FLAT,**{'D/USD':row(z=.1),'A/USD':row(age_up=3)}),{'A/USD':'BULL'})
        self.assertEqual([self.step(r)['done'] for _ in range(2)],['SELL D/USD','BUY A/USD'])

    def test_B26_an_entry_needs_cash_for_at_least_half_its_size(self):
        r=self.runner();r.state.update(cash=5000.,inventory={'D/USD':950.},book={'D/USD':held('mr',1,999)})
        self.decide_hour(r,dict(self.FLAT,**{'D/USD':row(z=-1.),'A/USD':row(age_up=3)}),{'A/USD':'BULL'})
        self.assertIsNone(self.step(r)['done']);self.assertNotIn('A/USD',r.state['book']);self.assertEqual(r.state['fills'],0)

    def test_B27_no_short_request_under_one_dollar_of_collateral(self):
        client=Exchange();client.usd=5.;r=self.live(client,peak=5.)
        self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(**DOWN)}),{'B/USD':'BEAR'})
        self.assertIsNone(self.step(r)['done']);self.assertEqual(self.posts(client),[])

    def test_B28_B16_B18_paper_short_accounting_follows_the_price(self):
        r=self.runner();self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(**DOWN)}),{'B/USD':'BEAR'})
        self.assertEqual(self.step(r)['done'],'SHORT B/USD');short=dict(r.state['shorts']['B/USD']);k=short['collateral']
        self.assertAlmostEqual(r.state['cash'],100000-k*1.001,places=6)                                 # 0.10% open fee
        self.assertAlmostEqual(short['entry'],99.97);self.assertAlmostEqual(short['qty'],k/99.97)
        self.quotes['B/USD']={'bid':90.,'ask':90.}
        self.assertAlmostEqual(self.step(r)['equity'],100000-k*.001+short['qty']*(99.97-90),places=6)   # a fall is a gain
        self.now=1001*HOUR;self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(close=90.,ema_fast=101.)}),{})
        self.assertEqual(self.step(r)['done'],'COVER B/USD');price=90*1.0003
        self.assertAlmostEqual(r.state['cash'],100000-k*.001+short['qty']*(99.97-price)-short['qty']*price*.001,places=6)

    def test_B17_a_paper_short_loses_at_most_its_collateral(self):
        r=self.runner();self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(**DOWN)}),{'B/USD':'BEAR'})
        self.step(r);short=dict(r.state['shorts']['B/USD']);k=short['collateral'];self.quotes['B/USD']={'bid':250.,'ask':250.}
        self.assertAlmostEqual(self.step(r)['equity'],100000-k*1.001,places=6)                           # worth nothing, not negative
        self.now=1001*HOUR;self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(close=250.,ema_fast=101.)}),{})
        self.assertEqual(self.step(r)['done'],'COVER B/USD')
        self.assertAlmostEqual(r.state['cash'],100000-k*1.001-short['qty']*250*1.0003*.001,places=6)

    def test_B19_live_equity_counts_a_short_at_its_position_value(self):
        client=Exchange();client.usd=99000.;r=self.live(client);r.state['book']={'B/USD':held('ema',-1,999)}
        self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(ema_fast=99.,age_down=40)}),{})
        position={'Pair':'B/USD','EntryPrice':100.,'ShortQty':10.,'Collateral':1000.}
        for extra,equity in (({'PositionValue':1100.,'UnrealizedPNL':100.},100100.),({'UnrealizedPNL':-50.},99950.),({},100000.)):
            client.positions[:]=[dict(position,**extra)];self.assertAlmostEqual(self.step(r)['equity'],equity)

    def test_B22_B02_an_untracked_short_is_covered_with_the_pair_alone(self):
        client=Exchange();client.usd=99000.;client.positions.append({'Pair':'B/USD','EntryPrice':100.,'ShortQty':10.,'Collateral':1000.,'PositionValue':1000.})
        r=self.live(client);self.decide_hour(r,self.FLAT,{})
        self.assertEqual(self.step(r)['done'],'COVER B/USD');self.assertEqual(self.posts(client),[('/v6/short_close',{'pair':'B/USD'})])

    def test_B23_a_short_the_exchange_no_longer_lists_leaves_the_book_without_an_order(self):
        client=Exchange();r=self.live(client);r.state['book']={'B/USD':held('ema',-1,999)}
        self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(ema_fast=99.,age_down=40)}),{})                  # no exit signal: only the position list says it is gone
        status=self.step(r);self.assertIsNone(status['done']);self.assertEqual(status['positions']['ema_short'],0)
        self.assertEqual((r.state['book'],self.posts(client)),({},[]))

    def test_B15_a_locked_coin_still_blocks_the_cycle(self):
        client=Exchange();client.coins={'A':5.};client.locked={'A':1.};r=self.live(client);self.decide_hour(r,self.FLAT,{})
        with self.assertRaisesRegex(ValueError,'Locked'):self.step(r)

    def test_B29_a_refused_position_list_switches_to_long_only_instead_of_stopping(self):
        client=Exchange();r=self.live(client)
        client.short_positions=lambda:(_ for _ in ()).throw(APIError('this competition does not allow short positions'))
        self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(age_up=3),'B/USD':row(**DOWN)}),{'A/USD':'BULL','B/USD':'BEAR'})
        self.assertEqual(self.step(r)['done'],'BUY A/USD');self.assertTrue(r.no_shorts)
        self.step(r);self.assertEqual([c[0] for c in self.posts(client)],['/v3/place_order'])

    def test_B05_an_ordinary_refusal_does_not_switch_the_short_side_off(self):
        client=Exchange();r=self.live(client);client.fail=APIError('insufficient balance')
        self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(**DOWN)}),{'B/USD':'BEAR'})
        self.assertIsNone(self.step(r)['done']);self.assertFalse(r.no_shorts);self.assertEqual(r.state['locks'],{'B/USD':1024})

    def test_B09_a_short_open_that_timed_out_but_filled_is_adopted_not_covered(self):
        client=Exchange();r=self.live(client);client.fail=TimeoutError('no answer')
        self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(**DOWN)}),{'B/USD':'BEAR'})
        with self.assertRaises(TimeoutError):self.step(r)
        self.assertEqual(r.state['inflight']['kind'],'SHORT')
        client.fail=None;client.usd-=16666.66*1.001
        client.positions.append({'Pair':'B/USD','EntryPrice':99.5,'ShortQty':167.5,'Collateral':16666.66,'PositionValue':16666.66})
        r=self.runner(True,client);self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(**DOWN)}),{'B/USD':'BEAR'});r.state['legs_bar']=999
        self.assertIsNone(self.step(r)['done']);self.assertIsNone(r.state['inflight'])
        self.assertEqual({k:r.state['book']['B/USD'][k] for k in ('leg','side','entry')},{'leg':'ema','side':-1,'entry':99.5})
        self.assertEqual([c[0] for c in self.posts(client)],['/v6/short_open'])                           # sent once, never repeated, not covered

    def test_B31_main_keeps_cycling_after_a_short_is_left_in_flight_but_stops_for_a_spot_order(self):
        config=Path(self.folder.name)/'config.json';config.write_text(json.dumps(asdict(C)))
        for intent,expected in (({'pair':'B/USD','kind':'COVER'},3),({'pair':'A/USD','side':'BUY'},1)):
            calls=[]
            def cycle(runner):
                calls.append(1)
                if len(calls)==1:runner.state['inflight']=intent;raise TimeoutError('no answer')
                runner.state['inflight']=None;return {'ok':True}
            argv=['bot','--config',str(config),'--state',str(Path(self.folder.name)/f'main{expected}.json'),'--cycles','3']
            with patch.object(sys,'argv',argv),patch.object(Runner,'bootstrap',lambda s:None),patch.object(Runner,'cycle',cycle),\
                 patch.object(bot.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
                if expected==1:
                    with self.assertRaises(TimeoutError):bot.main()
                else:bot.main()
            self.assertEqual(len(calls),expected)


    def test_a_failed_read_of_the_short_list_blocks_the_cycle_and_changes_nothing(self):
        client=Exchange();client.usd=99000.;client.positions.append({'Pair':'B/USD','EntryPrice':100.,'ShortQty':10.,'Collateral':1000.,'PositionValue':1000.})
        r=self.live(client);r.state['book']={'B/USD':held('ema',-1,999)}
        self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(ema_fast=99.,age_down=40)}),{});self.step(r)
        for message in ('system busy, try again','short positions are not allowed'):   # even a refusal is not believed with a short open
            client.short_positions=lambda:(_ for _ in ()).throw(APIError(message))
            with self.assertRaises(APIError):self.step(r)
            self.assertEqual((list(r.state['book']),r.state['halted'],r.no_shorts,self.posts(client)),(['B/USD'],False,False,[]))

    def test_an_old_holding_is_sold_before_anything_is_opened_on_that_coin(self):
        r=self.runner();r.state.update(cash=50000.,inventory={'A/USD':250.,'B/USD':250.})      # left by another strategy
        self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(age_up=3),'B/USD':row(**DOWN)}),{'A/USD':'BULL','B/USD':'BEAR'})
        self.assertEqual(sorted(self.step(r)['done'] for _ in range(2)),['SELL A/USD','SELL B/USD'])
        self.assertIsNone(self.step(r)['done']);self.assertEqual((r.state['book'],r.state['shorts']),({},{}))
        self.now=1001*HOUR;self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(age_up=4)}),{'A/USD':'BULL'})
        self.assertEqual(self.step(r)['done'],'BUY A/USD')                                 # entered afresh at the next decision

    def test_missing_candles_are_reported_as_a_blocked_cycle_until_they_arrive(self):
        r=self.runner();self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(age_up=3)}),{'A/USD':'BULL'})
        self.assertEqual(self.step(r)['done'],'BUY A/USD')
        def down(now):raise OSError('Network is unreachable')
        r.refresh_features=down;self.now=1001*HOUR
        with self.assertRaisesRegex(ValueError,'No candles for this hour'):self.step(r)
        self.assertIn('A/USD',r.state['book'])
        r.refresh_features=lambda now:None;self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(ema_fast=99.)}),{})
        self.assertEqual(self.step(r)['done'],'SELL A/USD')

    def test_a_refused_cover_is_tried_again_and_an_unsent_exit_survives_the_next_decision(self):
        client=Exchange();r=self.live(client);self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(**DOWN)}),{'B/USD':'BEAR'})
        self.assertEqual(self.step(r)['done'],'SHORT B/USD')
        self.now=1001*HOUR;self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(ema_fast=101.)}),{});client.fail=APIError('system busy')
        status=self.step(r);self.assertEqual((status['done'],status['queued'],list(r.state['book'])),(None,1,['B/USD']))
        self.now=1002*HOUR;self.decide_hour(r,dict(self.FLAT,**{'B/USD':row(ema_fast=99.,age_down=40)}),{})   # the exit signal is gone, the queued cover is not
        client.fail=None;self.assertEqual(self.step(r)['done'],'COVER B/USD');self.assertEqual((r.state['book'],client.positions),({},[]))

    def test_a_halt_between_decisions_drops_queued_entries_and_closes_every_position(self):
        r=self.runner();self.decide_hour(r,dict(self.FLAT,**{'A/USD':row(age_up=3),'B/USD':row(**DOWN),'D/USD':row(z=-3.2)}),{'A/USD':'BULL','B/USD':'BEAR','D/USD':'CHOP'})
        self.assertEqual(self.step(r)['done'],'BUY A/USD');r.state['peak']=200000.
        self.assertEqual([self.step(r)['done'] for _ in range(2)],['SELL A/USD',None]);self.assertEqual((r.state['book'],r.state['queue']),({},[]))

    def test_the_regime_strategy_runs_only_as_an_allocation_config_with_real_booleans(self):
        with self.assertRaises(ValueError):Runner(replace(C,strategy='cross_asset'),self.path,FakeClient(),False)
        for bad in (dict(allow_short='false'),dict(top_n=2.5),dict(cooldown_bars=6.5)):
            with self.assertRaises(ValueError):replace(C,**bad).validate()


if __name__=='__main__':unittest.main()
