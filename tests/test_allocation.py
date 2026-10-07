import unittest
from dataclasses import replace
from roostoo.data import synthetic
from roostoo.engine import run
from roostoo.strategy import Config,Indicators,rotation_targets
from roostoo.allocation import regime_adaptive_targets
from itertools import groupby


class AllocationTests(unittest.TestCase):
    def test_fifo_partial_sales_conserve_equity_and_fees(self):
        bars,manifest=synthetic(days=30)
        c=Config(strategy='allocation',fast=8,slow=24,momentum=12,max_position=.4,top_n=3,rebalance_band=.005,rebalance_bars=6)
        r=run(bars,c,manifest)
        closed=sum(t['net_pnl'] for t in r['trades'] if t['status']=='CLOSED')
        opened=sum(t['net_pnl'] for t in r['trades'] if t['status']=='OPEN')
        self.assertAlmostEqual(c.initial_cash+closed+opened,r['metrics']['final_equity'],places=6)
        lot_fees=sum(t['entry_fee']+t['exit_fee'] for t in r['trades'])
        self.assertAlmostEqual(lot_fees,r['metrics']['fees'],places=6)
        self.assertEqual(len(set(t['id'] for t in r['trades'])),len(r['trades']))
        self.assertTrue(all(x['cash']>=-1e-6 for x in r['equity_curve']))
        self.assertTrue(any(o['action']=='CLOSE' and o['status']=='FILLED' for o in r['orders']))
        # There should be multiple descendants of at least one original entry after trimming.
        self.assertLess(len(set((t['pair'],t['entry_time']) for t in r['trades'])),len(r['trades']))

    def test_precomputed_features_match_normal_replay(self):
        bars,manifest=synthetic(days=10);c=Config(strategy='allocation',fast=8,slow=24,momentum=12)
        states={p:Indicators(c) for p in {b.pair for b in bars}}
        features=[{b.pair:states[b.pair].update(b) for b in g} for _,g in groupby(bars,key=lambda b:b.timestamp)]
        a=run(bars,c,manifest);b=run(bars,c,manifest,precomputed=features)
        self.assertEqual(a['orders'],b['orders']);self.assertEqual(a['equity_curve'],b['equity_curve'])

    def test_future_mutation_does_not_change_allocation_past(self):
        bars,m=synthetic(days=15);cutoff=bars[len(bars)//2].timestamp
        changed=[replace(b,open=b.open*2,high=b.high*2,low=b.low*2,close=b.close*2) if b.timestamp>=cutoff else b for b in bars]
        c=Config(strategy='allocation',fast=8,slow=24,momentum=12)
        a=run(bars,c,m);b=run(changed,c,m)
        self.assertEqual([o for o in a['orders'] if o['timestamp']<cutoff],[o for o in b['orders'] if o['timestamp']<cutoff])

    def test_rotation_targets_use_risk_adjusted_trend_ranking(self):
        base=dict(ready=True,momentum=.1,volatility=.02,close=110,slow=100)
        f={'BTC/USD':base,'ETH/USD':dict(base,volatility=.01),'SOL/USD':dict(base,momentum=-.3,close=90)}
        self.assertEqual(list(rotation_targets(f,Config(top_n=1))),['ETH/USD'])
        targets=rotation_targets(f,Config(top_n=1,allow_short=True))
        self.assertEqual(targets['SOL/USD'][0],'SHORT')

    def test_regime_targets_require_persistent_bull_and_short_hurdle(self):
        c=Config(strategy='cross_asset',rank_model='regime_adaptive',top_n=2,
                 max_position=.3,target_volatility=.8,rank_min_trend_strength=.5,
                 regime_min_move=.02,regime_hold_bars=24)
        f=dict(ready=True,market_regime='BULL',regime_age=24,close=110,slow=100,
               volatility=.01,trend_strength=.75,momentum_short=.04,momentum_72=.08,
               dollar_volume=10.)
        targets=regime_adaptive_targets({'BTC/USD':f,'ETH/USD':dict(f,dollar_volume=9.)},c)
        self.assertEqual(set(targets),{'BTC/USD','ETH/USD'})
        self.assertEqual(regime_adaptive_targets({'BTC/USD':dict(f,market_regime='CHOP')},c),{})
        self.assertEqual(regime_adaptive_targets({'BTC/USD':dict(f,momentum_72=.01)},c),{})

    def test_volatility_uses_returns_when_slow_window_is_short(self):
        import math,statistics
        bars,_=synthetic(days=10);btc=[b for b in bars if b.pair==bars[0].pair]
        state=Indicators(Config(fast=16,slow=64,momentum=12))
        for b in btc[:100]:f=state.update(b)
        closes=[b.close for b in btc[:100]]
        self.assertAlmostEqual(f['volatility'],statistics.pstdev([math.log(b/a) for a,b in zip(closes[-73:],closes[-72:])]))

    def test_replay_brake_reduces_exposure_instead_of_halting(self):
        from roostoo.allocation import run_allocation
        bars,m=synthetic(days=30)
        c=Config(strategy='allocation',fast=8,slow=24,momentum=12,max_position=.4,max_drawdown=.005,rebalance_bars=6)
        halted=run_allocation(bars,c,m,None);braked=run_allocation(bars,replace(c,drawdown_brake=.005),m,None)
        self.assertTrue(halted['metrics']['circuit_breaker_triggered'])
        self.assertFalse(braked['metrics']['circuit_breaker_triggered'])
        self.assertGreater(braked['metrics']['fills'],halted['metrics']['fills'])

    def test_breakout_replay_fills_slots_without_rebalancing_them(self):
        from roostoo.allocation import run_allocation
        bars,m=synthetic(days=30)
        c=Config(strategy='allocation',rank_model='breakout',fast=8,slow=24,momentum=24,top_n=2,max_position=.5,max_exposure=.98,
                 regime_min_move=.02,take_profit_trail=.03,cooldown_bars=12,rebalance_bars=1,max_drawdown=.5)
        r=run_allocation(bars,c,m,None)
        filled=[o for o in r['orders'] if o['status']=='FILLED']
        self.assertTrue(any(o['action']=='OPEN' for o in filled));self.assertTrue(any(o['action']=='CLOSE' for o in filled))
        # Every sale closes the whole slot: no lot is ever split by a trim.
        self.assertEqual(len(set((t['pair'],t['entry_time']) for t in r['trades'])),len(r['trades']))
        self.assertAlmostEqual(c.initial_cash+sum(t['net_pnl'] for t in r['trades']),r['metrics']['final_equity'],places=6)

    def test_indicators_use_the_configured_high_window_and_a_24_bar_true_range(self):
        bars,_=synthetic(days=30);btc=[b for b in bars if b.pair=='BTC/USD']
        state=Indicators(Config(momentum=12,breakout_high_bars=120,trail_atr=4.))
        for i,bar in enumerate(btc):
            f=state.update(bar)
            if i<120:continue
            self.assertEqual(f['breakout_high'],max(b.close for b in btc[i-119:i+1]))
            ranges=[max(b.high-b.low,abs(b.high-a.close),abs(b.low-a.close)) for a,b in zip(btc[i-24:i],btc[i-23:i+1])]
            self.assertAlmostEqual(f['atr_24'],sum(ranges)/24,places=9)
            self.assertAlmostEqual(f['momentum'],bar.close/btc[i-12].close-1,places=12)

    def test_replay_stop_does_not_loosen_when_the_range_widens(self):
        from roostoo.allocation import run_allocation
        from roostoo.data import Bar
        c=Config(strategy='allocation',rank_model='breakout',fast=8,slow=24,momentum=12,top_n=2,max_position=.5,max_exposure=.98,
                 regime_min_move=.08,cooldown_bars=12,rebalance_bars=1,max_drawdown=.5,breakout_high_bars=24,trail_atr=4.)
        rows=[(100.,100.5,99.5,100.)]*30+[(100.,112.5,100.,112.),   # 12% in an hour at a new high: buy at the next open
              (112.,113.,111.5,112.5),                             # filled; high 113, ATR 1.5, stop 107
              (112.5,113.,95.,106.9),                              # wide bar closes under 107; a recomputed stop would be near 104
              (106.9,107.,106.5,106.9),(106.9,107.,106.5,106.9),(106.9,107.,106.5,106.9)]
        bars=[Bar(1735689600000+i*3600000,'BTC/USD',*row,1000.) for i,row in enumerate(rows)]
        r=run_allocation(bars,c,{},None)
        filled=[(o['action'],o['signal_timestamp']) for o in r['orders'] if o['status']=='FILLED']
        self.assertEqual(filled,[('OPEN',bars[31].timestamp-1),('CLOSE',bars[33].timestamp-1)])

