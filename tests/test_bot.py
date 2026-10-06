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
        c=Config(**json.loads((Path(__file__).resolve().parents[1]/'config/live_candidate.json').read_text()))
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
        logged={k:v for k,v in asdict(old).items() if k not in LEGACY_FIELDS[0]}  # written before the brake fields existed
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

