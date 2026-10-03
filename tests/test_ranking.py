import importlib.util
from dataclasses import replace
import unittest
from roostoo.data import synthetic
from roostoo.strategy import Config
from roostoo.ranking import training_rows,ranking_targets,validate_input

HAS_ML=bool(importlib.util.find_spec('numpy') and importlib.util.find_spec('sklearn'))


class RankingTests(unittest.TestCase):
    def test_labels_end_before_fit_boundary(self):
        for horizon in (24,72):
            rows=training_rows(4000,2400,horizon)
            self.assertGreaterEqual(rows[0],720)
            self.assertLess(rows[-1]+1+horizon,2400)

    def test_rank_selection_trend_gate_and_risk_caps(self):
        c=Config(strategy='cross_asset',top_n=2,max_position=.2,target_volatility=.35)
        f=dict(ready=True,close=110,slow=100,momentum=.1,rank_score=.02,volatility=.02)
        features={'BTC/USD':f,'ETH/USD':dict(f,rank_score=.04),'SOL/USD':dict(f,rank_score=1,momentum=-.1),'ADA/USD':dict(f,rank_score=-.1)}
        targets=ranking_targets(features,c,3600000)
        self.assertEqual(set(targets),{'BTC/USD','ETH/USD'})
        self.assertLessEqual(sum(targets.values()),c.max_exposure)
        self.assertLessEqual(max(targets.values()),c.max_position)
        self.assertLessEqual(sum(targets.values())*.02*(365*24)**.5,c.target_volatility+1e-12)
        self.assertEqual(targets,ranking_targets(dict(reversed(list(features.items()))),c,3600000))
        self.assertEqual(ranking_targets({'BTC/USD':dict(f,momentum=-.1)},c,3600000),{})

    def test_input_rejects_synthetic_and_short_allocation(self):
        bars,m=synthetic(days=101)
        with self.assertRaisesRegex(ValueError,'historical'):validate_input(bars,Config(strategy='cross_asset'),m)
        with self.assertRaisesRegex(ValueError,'long-only'):validate_input(bars,Config(strategy='cross_asset',allow_short=True),{})

    def test_trend_budget_keeps_cash_for_inactive_assets(self):
        c=Config(strategy='cross_asset',rank_model='trend_budget',target_volatility=2,max_position=.3)
        f=dict(ready=True,volatility=.01,trend_strength=1.)
        targets=ranking_targets({'BTC/USD':f,'ETH/USD':dict(f,trend_strength=0.),'SOL/USD':f,'ADA/USD':f},c,3600000)
        self.assertNotIn('ETH/USD',targets)
        self.assertAlmostEqual(sum(targets.values()),.6)
        weaker=ranking_targets({'BTC/USD':dict(f,trend_strength=.5),'ETH/USD':dict(f,trend_strength=0.),'SOL/USD':f,'ADA/USD':f},c,3600000)
        self.assertLess(weaker['BTC/USD'],targets['BTC/USD'])

    def test_trend_budget_applies_liquidity_gate(self):
        c=Config(strategy='cross_asset',rank_model='trend_budget',rank_liquidity_top_n=2,target_volatility=2)
        f=dict(ready=True,volatility=.01,trend_strength=1.,dollar_volume=10.)
        features={'BTC/USD':f,'ETH/USD':dict(f,dollar_volume=9.),'SOL/USD':dict(f,dollar_volume=1.),'ADA/USD':dict(f,dollar_volume=0.)}
        self.assertEqual(set(ranking_targets(features,c,3600000)),{'BTC/USD','ETH/USD'})

    def test_trend_budget_applies_minimum_strength_gate(self):
        c=Config(strategy='cross_asset',rank_model='trend_budget',rank_min_trend_strength=.5,
                 target_volatility=2,max_position=.3)
        f=dict(ready=True,volatility=.01,trend_strength=.5,dollar_volume=10.)
        features={'BTC/USD':f,'ETH/USD':dict(f,trend_strength=.25),
                  'SOL/USD':dict(f,trend_strength=.5)}
        targets=ranking_targets(features,c,3600000)
        self.assertEqual(set(targets),{'BTC/USD','SOL/USD'})
        self.assertAlmostEqual(targets['BTC/USD'],targets['SOL/USD'])
        self.assertEqual(ranking_targets({'BTC/USD':dict(f,trend_strength=.49)},c,3600000),{})

    def test_regime_adaptive_requires_confirmed_bull_and_meaningful_move(self):
        c=Config(strategy='cross_asset',rank_model='regime_adaptive',top_n=2,
                 rank_liquidity_top_n=3,target_volatility=.5,regime_hold_bars=24)
        f=dict(ready=True,close=110,slow=100,volatility=.02,trend_strength=.75,
               dollar_volume=10.,momentum_72=.08,momentum_168=.12,setup_score=6.,
               market_regime='BULL',regime_age=24)
        targets=ranking_targets({'BTC/USD':f,'ETH/USD':dict(f,dollar_volume=9.)},c,3600000)
        self.assertEqual(set(targets),{'BTC/USD','ETH/USD'})
        self.assertEqual(ranking_targets({'BTC/USD':dict(f,market_regime='CHOP')},c,3600000),{})
        self.assertEqual(ranking_targets({'BTC/USD':dict(f,momentum_168=.01)},c,3600000),{})


@unittest.skipUnless(HAS_ML,'Install ML requirements for ranking tests')
class RankingCausalityTests(unittest.TestCase):
    def test_future_mutations_leave_prior_features_fit_and_orders_unchanged(self):
        import numpy as np
        from roostoo.ranking import market_features,fit_scores,execution_features,replay
        bars,m=synthetic(days=110)
        count=3;n=len(bars)//count;train_end=int(n*.6);start=int(n*.8);cutoff=start+120
        cuttime=bars[cutoff*count].timestamp
        changed=[replace(b,open=b.open*1.5,high=b.high*1.5,low=b.low*1.5,close=b.close*1.5,volume=b.volume*4) if b.timestamp>=cuttime else b for b in bars]
        a=market_features(bars);b=market_features(changed)
        np.testing.assert_array_equal(a['x'][:cutoff],b['x'][:cutoff])
        for model in ('ridge_72','boosted_72','trend_budget'):
            p,metadata,_=fit_scores(a,model,train_end)
            q,other,_=fit_scores(b,model,train_end)
            np.testing.assert_array_equal(p[:cutoff],q[:cutoff])
            self.assertEqual(metadata['last_train_label_timestamp'],other['last_train_label_timestamp'])
            if model!='trend_budget':self.assertLess(metadata['last_train_label_timestamp'],metadata['train_end_exclusive'])
            c=Config(strategy='cross_asset',rank_model=model,max_drawdown=.5)
            r=replay(bars,c,m,None,execution_features(a,p),start)
            s=replay(changed,c,m,None,execution_features(b,q),start)
            self.assertEqual([o for o in r['orders'] if o['timestamp']<cuttime],[o for o in s['orders'] if o['timestamp']<cuttime])
            self.assertGreater(r['metrics']['fills'],0)
            self.assertAlmostEqual(c.initial_cash+sum(t['net_pnl'] for t in r['trades']),r['metrics']['final_equity'],places=6)
            self.assertTrue(all(o['signal_timestamp']<o['timestamp'] for o in r['orders'] if o['status']=='FILLED'))

    def test_future_mutations_leave_prior_regime_features_unchanged(self):
        """The broad regime classifier must not read candles after the decision."""
        import numpy as np
        from roostoo.ranking import market_features,fit_scores
        from roostoo.regime import regime_features
        bars,m=synthetic(days=110)
        count=3; cutoff=1800
        cuttime=bars[cutoff*count].timestamp
        changed=[replace(b,open=b.open*1.5,high=b.high*1.5,low=b.low*1.5,
                         close=b.close*1.5,volume=b.volume*4)
                 if b.timestamp>=cuttime else b for b in bars]
        a=market_features(bars); b=market_features(changed)
        pa,_,_=fit_scores(a,'regime_adaptive',int(len(a['timestamps'])*.6))
        pb,_,_=fit_scores(b,'regime_adaptive',int(len(b['timestamps'])*.6))
        fa=regime_features(a,pa); fb=regime_features(b,pb)
        self.assertEqual(fa[:cutoff],fb[:cutoff])
        # Ensure this is a meaningful check and the mutation actually changes
        # the post-cutoff classifier input.
        self.assertFalse(np.array_equal(a['close'][cutoff:],b['close'][cutoff:]))
