import hashlib
import hmac
import math
import unittest
from dataclasses import replace
from unittest.mock import patch
from roostoo.data import Bar, synthetic, validate_bars
from roostoo.engine import run,short_settlement
from roostoo.strategy import Config
from roostoo.rules import PairRule
from roostoo.api import canonical,signature
from roostoo.metrics import summarize

BASE=1_735_689_600_000


def bars(prices, pair='BTC/USD', interval=3_600_000):
    return [Bar(BASE+i*interval,pair,p,p,p,p) for i,p in enumerate(prices)]


class ExecutionTests(unittest.TestCase):
    def config(self,**kw):
        return replace(Config(fast=2,slow=3,momentum=2,fee_bps=10,spread_bps=0,slippage_bps=0,cooldown_bars=999,max_drawdown=.9),**kw)

    def round_trip(self,side):
        source=bars([100,110,120,130])
        with patch('roostoo.engine.entry',return_value=(side,'Trend test',1)),patch('roostoo.engine.exit_reason',return_value='test close'):
            result=run(source,self.config(allow_short=True))
        return result

    def test_long_accounting_next_open_and_both_fees(self):
        r=self.round_trip('LONG');t=r['trades'][0]
        self.assertEqual(t['entry_price'],110)
        self.assertEqual(t['exit_price'],120)
        self.assertGreater(t['entry_time'],t['entry_signal_time'])
        expected=t['quantity']*10-t['quantity']*110*.001-t['quantity']*120*.001
        self.assertAlmostEqual(t['net_pnl'],expected,places=7)
        self.assertAlmostEqual(r['metrics']['final_equity'],100000+expected,places=7)
        self.assertTrue(all(p['cash']>=0 for p in r['equity_curve']))

    def test_short_collateral_and_fee_accounting(self):
        r=self.round_trip('SHORT');t=r['trades'][0]
        expected=-t['quantity']*10-t['quantity']*(110+120)*.001
        self.assertAlmostEqual(r['metrics']['final_equity'],100000+expected,places=7)
        self.assertAlmostEqual(t['net_pnl'],expected,places=7)
        self.assertAlmostEqual(r['equity_curve'][2]['cash'],100000-t['collateral']-t['entry_fee'])

    def test_short_loss_capped_at_collateral_before_fee(self):
        amount,gross,fee=short_settlement(1,100,1000,100)
        self.assertEqual(gross,-100);self.assertEqual(fee,1);self.assertEqual(amount,-1)

    def test_market_sides_and_slippage(self):
        with patch('roostoo.engine.entry',return_value=('LONG','test',1)),patch('roostoo.engine.exit_reason',return_value='close'):
            r=run(bars([100]*5),self.config(spread_bps=20,slippage_bps=10))
        t=r['trades'][0]
        self.assertAlmostEqual(t['entry_price'],100*1.001*1.001)
        self.assertAlmostEqual(t['exit_price'],100*.999*.999)
        self.assertLess(t['net_pnl'],0)

    def test_global_rate_limit_multiple_assets(self):
        source=sorted(bars([100]*8,interval=60000)+bars([100]*8,pair='ETH/USD',interval=60000),key=lambda b:b.timestamp)
        with patch('roostoo.engine.entry',return_value=('LONG','test',1)),patch('roostoo.engine.exit_reason',return_value=None):
            r=run(source,self.config())
        fills=[o for o in r['orders'] if o['status']=='FILLED']
        self.assertEqual(len(fills),2)
        self.assertTrue(all(b['timestamp']-a['timestamp']>=60000 for a,b in zip(fills,fills[1:])))

    def test_no_terminal_future_fill(self):
        with patch('roostoo.engine.entry',side_effect=[None,None,('LONG','late',1)]):
            r=run(bars([100]*3),self.config())
        self.assertEqual(r['metrics']['fills'],0)
        self.assertEqual(r['orders'][-1]['status'],'UNFILLED_END')

    def test_future_prices_cannot_change_past_decisions(self):
        source,manifest=synthetic(days=15)
        cutoff=BASE+10*24*3600000
        changed=[replace(b,open=b.open*2,high=b.high*2,low=b.low*2,close=b.close*2) if b.timestamp>=cutoff else b for b in source]
        a=run(source,Config(allow_short=True),manifest);b=run(changed,Config(allow_short=True),manifest)
        self.assertEqual([o for o in a['orders'] if o['timestamp']<cutoff],[o for o in b['orders'] if o['timestamp']<cutoff])
        self.assertEqual([s for s in a['signals'] if s['timestamp']<cutoff],[s for s in b['signals'] if s['timestamp']<cutoff])

    def test_circuit_breaker_exits_and_does_not_reenter(self):
        with patch('roostoo.engine.entry',return_value=('LONG','test',1)),patch('roostoo.engine.exit_reason',return_value=None):
            r=run(bars([100,100,50,50,100,100]),self.config(max_drawdown=.05,cooldown_bars=0))
        self.assertTrue(r['metrics']['circuit_breaker_triggered'])
        self.assertEqual(len(r['trades']),1)
        self.assertEqual(r['trades'][0]['status'],'CLOSED')
        self.assertIn('circuit breaker',r['trades'][0]['exit_reason'])

    def test_gapped_entry_cannot_spend_more_cash(self):
        with patch('roostoo.engine.entry',return_value=('LONG','test',1)),patch('roostoo.engine.exit_reason',return_value=None):
            r=run(bars([100,10000,10000]),self.config(max_position=1,max_exposure=1))
        self.assertTrue(all(x['cash']>=-1e-7 for x in r['equity_curve']))
        self.assertLessEqual(r['trades'][0]['collateral']+r['trades'][0]['entry_fee'],100000)

    def test_warmup_cannot_trade(self):
        r=run(bars([100+i for i in range(20)]),self.config(strategy='buy_hold'),start_index=10)
        self.assertEqual(r['equity_curve'][0]['equity'],100000)
        self.assertTrue(all(o['timestamp']>=BASE+11*3600000 for o in r['orders']))


class ValidationTests(unittest.TestCase):
    def test_reject_duplicate_gaps_and_invalid_prices(self):
        for source in [bars([100]*3)+bars([100]),bars([100]*4)[:2]+bars([100]*4)[3:],bars([100,float('nan'),100])]:
            with self.assertRaises(ValueError):validate_bars(source)

    def test_reject_unsynchronized_pairs(self):
        source=sorted(bars([100]*4)+bars([100]*3,'ETH/USD'),key=lambda b:b.timestamp)
        with self.assertRaises(ValueError):validate_bars(source)

    def test_precision_and_strict_minimum(self):
        rule=PairRule(amount_precision=2,minimum=1)
        self.assertEqual(rule.quantity(.01999),.01)
        self.assertFalse(rule.valid(.01,100));self.assertTrue(rule.valid(.02,100))

    def test_signature_sorted_and_literal_slash(self):
        params={'timestamp':1580774512000,'pair':'BNB/USD','quantity':'2000','side':'BUY','type':'MARKET'}
        expected='pair=BNB/USD&quantity=2000&side=BUY&timestamp=1580774512000&type=MARKET'
        self.assertEqual(canonical(params),expected)
        self.assertEqual(signature(params,'secret'),hmac.new(b'secret',expected.encode(),hashlib.sha256).hexdigest())

    def test_metrics_cash_does_not_get_infinite_score(self):
        r=run(bars([100]*240),Config(strategy='cash'))
        self.assertEqual(r['metrics']['total_return'],0)
        self.assertIsNone(r['metrics']['sharpe']);self.assertIsNone(r['metrics']['sortino']);self.assertIsNone(r['metrics']['composite_score'])

    def test_config_rejects_nonfinite_and_leverage(self):
        for c in [Config(initial_cash=float('nan')),Config(max_exposure=2),Config(fee_bps=-1)]:
            with self.assertRaises(ValueError):c.validate()


if __name__=='__main__':unittest.main()
