import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from roostoo.bot import Runner,plan_order,save_state
from roostoo.rules import PairRule
from roostoo.strategy import Config


class BotTests(unittest.TestCase):
    def setUp(self):
        self.c=Config(strategy='allocation')
        self.rules={'BTC/USD':PairRule()}
        self.quotes={'BTC/USD':{'bid':100.,'ask':100.1}}

    def test_planner_obeys_cash_position_cap_and_no_leverage(self):
        order,marks=plan_order({}, {'USD':{'Free':100000}},self.quotes,{'BTC/USD':1},self.rules,self.c,100000)
        self.assertEqual(order['side'],'BUY')
        self.assertLessEqual(order['quantity']*100.1,30000)
        self.assertEqual(marks['equity'],100000)

    def test_drawdown_halt_forces_exit(self):
        order,marks=plan_order({'peak':200000},{'USD':{'Free':90000},'BTC':{'Free':100}},self.quotes,{'BTC/USD':.3},self.rules,self.c,100000)
        self.assertTrue(marks['halted']);self.assertEqual(order['side'],'SELL');self.assertEqual(order['quantity'],100)

    def test_ambiguous_post_is_persisted_and_blocks_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json';client=Mock();client.request.side_effect=TimeoutError('unknown outcome')
            r=Runner(self.c,path,client,live=True);r.rules=self.rules
            r.wallet=lambda:{'USD':{'Free':100000}}
            r.state['targets']={'BTC/USD':.2}
            intent,_=plan_order(r.state,r.wallet(),self.quotes,r.state['targets'],self.rules,self.c,100000)
            with self.assertRaises(TimeoutError):r.submit(intent,self.quotes,100000)
            self.assertIsNotNone(json.loads(path.read_text())['inflight'])
            self.assertEqual(client.request.call_count,1)
            with self.assertRaisesRegex(RuntimeError,'Unresolved'):Runner(self.c,path,client,live=True)

    def test_throttle_applies_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json';r=Runner(self.c,path);r.state['last_submit']=100000;save_state(path,r.state)
            restored=Runner(self.c,path)
            with self.assertRaisesRegex(RuntimeError,'60-second'):restored.submit({},self.quotes,120000)

    def test_paper_roundtrip_changes_cash_without_http_order(self):
        with tempfile.TemporaryDirectory() as folder:
            client=Mock();r=Runner(self.c,Path(folder)/'state.json',client);r.rules=self.rules;r.state['targets']={'BTC/USD':.1}
            intent,_=plan_order(r.state,r.wallet(),self.quotes,r.state['targets'],self.rules,self.c,100000)
            r.submit(intent,self.quotes,100000)
            self.assertGreater(r.state['inventory']['BTC/USD'],0)
            r.state['targets']={}
            intent,_=plan_order(r.state,r.wallet(),self.quotes,{},self.rules,self.c,161000)
            r.submit(intent,self.quotes,161000)
            self.assertAlmostEqual(r.state['inventory']['BTC/USD'],0,places=5)
            self.assertLess(r.state['cash'],100000)
            self.assertFalse(client.request.called)

    def test_brake_scales_exposure_without_latching(self):
        c=Config(strategy='allocation',drawdown_brake=.04,rebalance_band=.001)
        state={'peak':100000,'equity_marks':[[1,100000]]}
        wallet={'USD':{'Free':68000},'BTC':{'Free':300}}  # equity 98,000: half way to the 4% brake
        order,marks=plan_order(state,wallet,self.quotes,{'BTC/USD':.3},self.rules,c,100000)
        self.assertAlmostEqual(marks['brake'],.5);self.assertFalse(marks['halted'])
        self.assertEqual(order['side'],'SELL');self.assertAlmostEqual(order['quantity']*100,30000-.15*98000,places=2)
        _,deep=plan_order(state,{'USD':{'Free':90000}},self.quotes,{'BTC/USD':.3},self.rules,c,100000)
        self.assertEqual(deep['brake'],0);self.assertFalse(deep['halted'])
        # Once the old peak leaves the window the brake releases; nothing stays latched.
        _,marks=plan_order({'peak':100000,'halted':True},wallet,self.quotes,{'BTC/USD':.3},self.rules,c,100000)
        self.assertEqual(marks['brake'],1);self.assertFalse(marks['halted'])

    def test_wide_quote_pauses_only_that_pair(self):
        rules=dict(self.rules,**{'ETH/USD':PairRule()})
        quotes={'BTC/USD':{'bid':100.,'ask':102.,'tradable':False},'ETH/USD':{'bid':10.,'ask':10.01}}
        order,marks=plan_order({},{'USD':{'Free':90000},'BTC':{'Free':100}},quotes,{'ETH/USD':.2},rules,self.c,100000)
        self.assertEqual(order['pair'],'ETH/USD');self.assertEqual(marks['equity'],100000)

    def test_take_profit_can_be_disabled(self):
        state={'position_meta':{'BTC/USD':{'quantity':100,'avg_entry':90.,'high':110.}}}
        wallet={'USD':{'Free':90000},'BTC':{'Free':100}}
        on,_=plan_order(state,wallet,self.quotes,{'BTC/USD':.1},self.rules,Config(strategy='allocation',take_profit_pct=.01,take_profit_trail=.01),100000)
        off,_=plan_order(state,wallet,self.quotes,{'BTC/USD':.1},self.rules,Config(strategy='allocation',take_profit_fraction=0.),100000)
        self.assertTrue(on['reason'].startswith('Trailing profit take'));self.assertIsNone(off)

    def test_live_ensemble_uses_research_targets_and_migrates(self):
        from dataclasses import asdict
        import hashlib
        from roostoo.allocation import allocation_targets
        from roostoo.ranking import ranking_targets
        from roostoo.migrate_state import digest,supported,LEGACY_FIELDS
        root=Path(__file__).resolve().parents[1]
        supported(Config(**json.loads((root/'config/live_candidate.json').read_text())))
        c=Config(**json.loads((root/'config/ranking_candidate_strength50.json').read_text()))
        supported(c)
        f=dict(ready=True,volatility=.01,trend_strength=.75,dollar_volume=10.)
        features={'BTC/USD':f,'ETH/USD':dict(f,trend_strength=.25),'SOL/USD':dict(f,ready=False)}
        self.assertEqual(allocation_targets(features,c),ranking_targets(features,c,3600000))
        self.assertEqual(set(allocation_targets(features,c)),{'BTC/USD'})
        # Ledgers hashed before each field group was added remain verifiable.
        values=asdict(c)
        for n,group in enumerate(LEGACY_FIELDS,1):
            for field in group:values.pop(field)
            self.assertEqual(digest(c,n),hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest())

    def test_active_ledger_from_previous_live_config_migrates_to_ensemble(self):
        from dataclasses import asdict
        from roostoo.migrate_state import digest,migrate,LEGACY_FIELDS
        root=Path(__file__).resolve().parents[1]
        new=Config(**json.loads((root/'config/live_candidate.json').read_text()))
        old=Config(strategy='cross_asset',rank_model='regime_adaptive',momentum=12,top_n=3,regime_min_move=.02,regime_hold_bars=0)
        logged={k:v for k,v in asdict(old).items() if k not in LEGACY_FIELDS[0]}  # written before the newest field group existed
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json'
            state={'mode':'paper','config_hash':digest(old,1),'cash':70000.,'inventory':{'BTC/USD':.3},'peak':100000.,
                   'halted':False,'last_submit':5,'inflight':None,'pending':{'pair':'BTC/USD'},'targets':{'BTC/USD':.3},'target_day':7,'fills':9}
            save_state(path,state);path.with_suffix('.jsonl').write_text(json.dumps({'event':'start','config':logged})+'\n')
            client=Mock();client.exchange_info.return_value=json.loads((root/'config/exchange_info.json').read_text())
            migrate(path,new,root/'config/universe-50.json',False,client)
            migrated=json.loads(path.read_text())
            self.assertEqual(migrated['config_hash'],digest(new));self.assertEqual(migrated['inventory'],{'BTC/USD':.3})
            self.assertEqual((migrated['fills'],migrated['targets'],migrated['target_day'],migrated['pending']),(9,{},None,None))
            Runner(new,path,client)  # the runner accepts the migrated ledger

    def test_breakout_slots_enter_hold_stop_and_lock(self):
        from roostoo.allocation import breakout_targets
        c=Config(strategy='allocation',rank_model='breakout',momentum=24,top_n=2,max_position=.5,max_exposure=.98,
                 regime_min_move=.08,take_profit_trail=.06,take_profit_fraction=0.,cooldown_bars=12,rebalance_bars=1)
        f=dict(ready=True,close=100.,momentum=.10,breakout_high=100.,atr_24=2.)
        features={'A/USD':f,'B/USD':dict(f,momentum=.20),'C/USD':dict(f,momentum=.30,close=95.),'D/USD':dict(f,momentum=.05),'E/USD':dict(f,momentum=.5)}
        # C is not at its 72h high, D moved too little, E is locked out: the two slots go to A and B.
        self.assertEqual(breakout_targets(features,c,{},{},{'E/USD'},{}),{'B/USD':.49,'A/USD':.49})
        held={'A/USD':.45,'B/USD':.45,'D/USD':.02}
        # A closed 6% under its high and D is a leftover: both are released and E takes the free slot.
        levels={}
        self.assertEqual(set(breakout_targets(features,c,held,{'A/USD':107.,'B/USD':105.,'D/USD':100.},set(),levels)),{'B/USD','E/USD'})
        self.assertEqual(levels,{'A/USD':107*.94,'B/USD':105*.94,'D/USD':100*.94})  # kept until the holding is gone
        # ATR trail: the stop sits trail_atr x ATR(24) under the high and only ratchets up.
        from dataclasses import replace
        k=replace(c,trail_atr=4.);levels={}
        self.assertIn('A/USD',breakout_targets(features,k,{'A/USD':.45},{'A/USD':107.},set(),levels));self.assertEqual(levels['A/USD'],99.)
        wide=dict(features,**{'A/USD':dict(f,atr_24=5.)})
        breakout_targets(wide,k,{'A/USD':.45},{'A/USD':107.},set(),levels);self.assertEqual(levels['A/USD'],99.)
        self.assertNotIn('A/USD',breakout_targets(dict(features,**{'A/USD':dict(f,close=99.)}),k,{'A/USD':.45},{'A/USD':107.},set(),levels))
        self.assertEqual(levels['A/USD'],99.)
        # Still held an hour later with a wider range: the fired stop is not loosened, so it stays released.
        self.assertNotIn('A/USD',breakout_targets(dict(features,**{'A/USD':dict(f,close=98.8,atr_24=9.)}),k,{'A/USD':.45},{'A/USD':107.},set(),levels))
        breakout_targets(features,k,{},{},set(),levels);self.assertEqual(levels,{})
        # A held slot is never rebalanced; a released one is sold in full.
        rules={p:PairRule() for p in ('A/USD','B/USD')};quotes={p:{'bid':100.,'ask':100.1} for p in rules}
        wallet={'USD':{'Free':10000},'A':{'Free':600},'B':{'Free':300}}
        order,_=plan_order({},wallet,quotes,{'A/USD':.49,'B/USD':.49},rules,c,0);self.assertIsNone(order)
        order,_=plan_order({},wallet,quotes,{'B/USD':.49},rules,c,0)
        self.assertEqual((order['pair'],order['side'],order['quantity']),('A/USD','SELL',600))

    def test_breakout_runner_tracks_untracked_holdings_and_locks_stops(self):
        c=Config(strategy='allocation',rank_model='breakout',momentum=24,top_n=2,max_position=.5,max_exposure=.98,
                 regime_min_move=.08,take_profit_trail=.06,take_profit_fraction=0.,cooldown_bars=12,rebalance_bars=1)
        with tempfile.TemporaryDirectory() as folder:
            r=Runner(c,Path(folder)/'state.json',Mock());r.rules={p:PairRule() for p in ('A/USD','B/USD')}
            f=dict(ready=True,close=100.,momentum=0.,breakout_high=120.,atr_24=2.)
            r.features={'A/USD':f,'B/USD':dict(f,close=90.)}
            r.state['position_meta']={'B/USD':{'quantity':500,'avg_entry':95.,'high':100.}}
            wallet={'USD':{'Free':10000},'A':{'Free':400},'B':{'Free':500}}
            quotes={'A/USD':{'bid':100.,'ask':100.1},'B/USD':{'bid':90.,'ask':90.1}}
            targets=r.breakout(wallet,quotes,1000)
            self.assertEqual(set(targets),{'A/USD'});self.assertEqual(r.state['position_meta']['A/USD']['high'],100.)
            self.assertEqual(r.state['profit_lock'],{'B/USD':12*3600000})
            r.update_position_meta('B/USD','SELL',499.999,90.);self.assertNotIn('B/USD',r.state['position_meta'])

    def test_runner_atr_stop_persists_ratchets_exits_and_is_reset_by_migration(self):
        from dataclasses import asdict
        from roostoo.migrate_state import digest,migrate
        root=Path(__file__).resolve().parents[1]
        c=Config(strategy='allocation',rank_model='breakout',momentum=12,top_n=2,max_position=.5,max_exposure=.98,
                 regime_min_move=.08,take_profit_fraction=0.,cooldown_bars=12,rebalance_bars=1,breakout_high_bars=120,trail_atr=4.)
        f=dict(ready=True,close=100.,momentum=0.,breakout_high=120.,atr_24=2.)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json';rules={'BTC/USD':PairRule()}
            r=Runner(c,path,Mock());r.rules=rules;r.features={'BTC/USD':f}
            r.state.update(cash=55000.,inventory={'BTC/USD':450.},fills=1,
                           position_meta={'BTC/USD':{'quantity':450.,'avg_entry':95.,'high':107.},'OLD/USD':{'quantity':.001,'avg_entry':1.,'high':9.}})
            quotes={'BTC/USD':{'bid':100.,'ask':100.1}}
            self.assertEqual(r.breakout(r.wallet(),quotes,1000),{'BTC/USD':.49})
            self.assertEqual(r.state['stop_levels'],{'BTC/USD':99.})  # 107 - 4 x ATR 2
            self.assertNotIn('OLD/USD',r.state['position_meta'])     # a record without a holding is dropped
            save_state(path,r.state)
            # After a restart a wider ATR must not loosen the saved stop.
            r=Runner(c,path,Mock());r.rules=rules;r.features={'BTC/USD':dict(f,atr_24=5.)}
            self.assertIn('BTC/USD',r.breakout(r.wallet(),quotes,2000));self.assertEqual(r.state['stop_levels'],{'BTC/USD':99.})
            # A new high moves it up.
            r.state['position_meta']['BTC/USD']['high']=130.;r.features={'BTC/USD':dict(f,close=125.)}
            r.breakout(r.wallet(),{'BTC/USD':{'bid':125.,'ask':125.1}},3000);self.assertEqual(r.state['stop_levels'],{'BTC/USD':122.})
            save_state(path,r.state)
            # Changing the config resets the levels but keeps the high-water mark.
            new=Config(**dict(asdict(c),trail_atr=3.))
            path.with_suffix('.jsonl').write_text(json.dumps({'event':'start','config':asdict(c)})+'\n')
            client=Mock();client.exchange_info.return_value=json.loads((root/'config/exchange_info.json').read_text())
            migrate(path,new,root/'config/universe-50.json',False,client)
            migrated=json.loads(path.read_text())
            self.assertEqual((migrated['stop_levels'],migrated['position_meta']['BTC/USD']['high'],migrated['config_hash']),({},130.,digest(new)))
            r=Runner(new,path,Mock());r.rules=rules;r.features={'BTC/USD':dict(f,close=125.)}
            r.breakout(r.wallet(),{'BTC/USD':{'bid':125.,'ask':125.1}},4000);self.assertEqual(r.state['stop_levels'],{'BTC/USD':124.})
            # An hourly close at the stop releases the slot, locks the pair for 12 hourly decisions and sells everything.
            low={'BTC/USD':{'bid':124.,'ask':124.1}};r.features={'BTC/USD':dict(f,close=124.)}
            targets=r.breakout(r.wallet(),low,5000)
            self.assertEqual((targets,r.state['stop_levels'],r.state['profit_lock']),({},{'BTC/USD':124.},{'BTC/USD':12*3600000}))
            order,_=plan_order(r.state,r.wallet(),low,targets,rules,new,5000)
            self.assertEqual((order['side'],order['quantity']),('SELL',450.))

    def test_breakout_skips_a_buy_that_would_be_under_half_a_slot_and_waits_for_a_first_decision(self):
        c=Config(strategy='allocation',rank_model='breakout',top_n=4,max_position=.25,max_exposure=.99,take_profit_fraction=0.,rebalance_bars=1)
        rules={p:PairRule() for p in ('A/USD','B/USD')};quotes={p:{'bid':100.,'ask':100.1} for p in rules}
        thin,_=plan_order({},{'USD':{'Free':10000},'A':{'Free':900}},quotes,{'A/USD':.2475,'B/USD':.2475},rules,c,0)
        self.assertIsNone(thin)                                    # 10% cash cannot fill half of a 24.75% slot
        full,_=plan_order({},{'USD':{'Free':40000},'A':{'Free':600}},quotes,{'A/USD':.2475,'B/USD':.2475},rules,c,0)
        self.assertEqual((full['pair'],full['side']),('B/USD','BUY'))
        with self.assertRaisesRegex(ValueError,'trail'):Config(strategy='allocation',rank_model='breakout',trail_atr=.06).validate()

    def test_ledgers_written_by_every_earlier_generation_still_verify(self):
        from roostoo.migrate_state import digest
        live=dict(strategy='allocation',rank_model='breakout',max_position=.25,max_exposure=.99,max_drawdown=.3,cooldown_bars=12,rebalance_bars=1,
                  top_n=4,target_volatility=.2,rebalance_band=.01,rank_min_trend_strength=.5,regime_min_move=.08,regime_hold_bars=0,
                  take_profit_pct=.01,take_profit_trail=.06,take_profit_fraction=0.)
        ensemble=dict(strategy='cross_asset',rank_model='trend_budget',max_position=.2,top_n=5,target_volatility=.2,rebalance_band=.01,
                      rank_min_trend_strength=.5,regime_min_move=.02,regime_hold_bars=0,take_profit_pct=.01,take_profit_trail=.01,
                      take_profit_fraction=0.,drawdown_brake=.04)
        regime=dict(strategy='cross_asset',rank_model='regime_adaptive',momentum=12,max_position=.35,max_exposure=.95,rebalance_bars=6,
                    target_volatility=.95,rebalance_band=.04,rank_min_trend_strength=.5,regime_min_move=.02,regime_hold_bars=0,
                    take_profit_pct=.01,take_profit_trail=.01,take_profit_fraction=1.)
        first=dict(strategy='cross_asset',rank_model='regime_adaptive',momentum=12,rebalance_bars=1,target_volatility=.8,rebalance_band=.01,
                   rank_min_trend_strength=.5,regime_min_move=.02,regime_hold_bars=0)
        # config_hash each commit's runner stored for its own config/live_candidate.json (recomputed from that commit's code).
        for fields,missing_groups,stored in ((dict(live,momentum=12,breakout_high_bars=120,trail_atr=4.),1,'1fbcc3bc9d5bf9c41f7a3711f78c45b39074731b3e59241380d5a61c4fd3381e'),  # c0f9374
                                             (live,2,'33d2d3f0a5545eff515ed9e2570f15aefbc01b644982f5336e8e72f3f3761e69'),      # fd1b585, 77905fc
                                             (ensemble,2,'57d9de1a75a22de474fa486c670d05e9ebd53cc0c23d99178c852ef906fe4e66'),  # 2fc7b16
                                             (regime,3,'6669631f8b3ef5c8e5eceaaf81221a25226f8ba9558a8099437e3818379d7abc'),    # b97285e (main)
                                             (first,4,'a934ee4110f3e3492f856a1203f8c5ce349a1a8a6dae6851166200d2b1134019')):    # 83fc82b
            self.assertEqual(digest(Config(**fields),missing_groups),stored)

