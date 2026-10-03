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
