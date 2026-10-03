import importlib.util
import unittest
from dataclasses import replace
from roostoo.data import synthetic,Bar
from roostoo.lstm import splits,market_arrays,fit_predict,run_lstm
from roostoo.strategy import Config,entry,exit_reason

HAS_ML=bool(importlib.util.find_spec('numpy') and importlib.util.find_spec('torch'))


class LSTMStrategyTests(unittest.TestCase):
    def test_horizon_labels_cannot_cross_training_or_validation_boundaries(self):
        train,val,test,cut,end=splits(2000,24,12)
        self.assertLess(max(train)+12,cut)
        self.assertGreaterEqual(min(val),cut)
        self.assertLess(max(val)+12,end)
        self.assertEqual(min(test),end)
        self.assertGreaterEqual(min(train)-24+1,24)

    def test_entry_needs_forecast_above_costs_and_buffer(self):
        c=Config(strategy='lstm_prediction')
        f=dict(ready=True,atr=1,close=100,predicted_price=101,predicted_return=.004)
        self.assertIsNone(entry(f,c))
        f['predicted_return']=.01
        idea=entry(f,c);self.assertEqual(idea[0],'LONG');self.assertIn('LSTM Prediction',idea[1])
        f['predicted_return']=-.01
        self.assertIsNone(entry(f,c));self.assertEqual(entry(f,replace(c,allow_short=True))[0],'SHORT')
        del f['predicted_return'];self.assertIsNone(entry(f,c))

    def test_exit_uses_forecast_and_horizon_not_ema(self):
        c=Config(strategy='lstm_prediction')
        p=dict(side='LONG',stop=90,entry_index=1)
        b=Bar(1735689600000,'BTC/USD',100,100,100,100)
        f=dict(predicted_return=.02,fast=90,slow=110)
        self.assertIsNone(exit_reason(p,f,b,c,2))
        self.assertIsNone(exit_reason(p,f,b,c,11))
        self.assertIn('horizon',exit_reason(p,f,b,c,12))
        f['predicted_return']=-.02;self.assertIn('direction',exit_reason(p,f,b,c,2))

    def test_horizon_exit_fills_at_forecast_target_time(self):
        from roostoo.engine import run
        bars=[Bar(1735689600000+i*3600000,'BTC/USD',100,101,99,100,100) for i in range(30)]
        features=[{'BTC/USD':dict(ready=True,atr=1,close=100,predicted_price=101,
                                 predicted_return=.01 if i==5 else .002)} for i in range(30)]
        result=run(bars,Config(strategy='lstm_prediction',lstm_horizon=3),precomputed=features,start_index=5)
        self.assertEqual(len(result['trades']),1)
        trade=result['trades'][0]
        self.assertEqual(trade['holding_hours'],3)
        self.assertEqual(trade['exit_time'],trade['entry_signal_time']+1+3*3600000)

    def test_historical_data_and_hourly_interval_required(self):
        bars,m=synthetic(days=45)
        with self.assertRaisesRegex(ValueError,'historical'):
            run_lstm(bars,Config(strategy='lstm_prediction'),m,None)
        with self.assertRaises(ValueError):splits(999,24,12)
        with self.assertRaises(ValueError):Config(lstm_sequence=24.5).validate()


@unittest.skipUnless(HAS_ML,'Install requirements-lstm.txt to exercise training')
class LSTMTrainingTests(unittest.TestCase):
    def test_future_mutation_cannot_change_features_scaler_weights_or_earlier_predictions(self):
        import numpy as np
        bars,_=synthetic(days=50,seed=81)
        bars=[b for b in bars if b.pair=='BTC/USD']
        cutoff=bars[1100].timestamp
        changed=[replace(b,open=b.open*1.5,high=b.high*1.5,low=b.low*1.5,close=b.close*1.5,volume=b.volume*3) if b.timestamp>=cutoff else b for b in bars]
        _,a=market_arrays(bars);_,b=market_arrays(changed)
        np.testing.assert_array_equal(a['BTC/USD']['x'][:1100],b['BTC/USD']['x'][:1100])
        c=Config(strategy='lstm_prediction',lstm_epochs=1,lstm_hidden=4,lstm_sequence=8)
        pred1,m1,_,start=fit_predict(bars,c)
        pred2,m2,_,_=fit_predict(changed,c)
        self.assertEqual(m1['scaler_mean'],m2['scaler_mean'])
        self.assertEqual(m1['scaler_scale'],m2['scaler_scale'])
        self.assertEqual(m1['weight_sha256'],m2['weight_sha256'])
        for i in range(start,1100):self.assertEqual(pred1['BTC/USD'][i],pred2['BTC/USD'][i])
        self.assertLess(m1['last_train_label_timestamp'],m1['train_end_exclusive'])
        self.assertLess(m1['last_validation_label_timestamp'],m1['test_start'])

    def test_scaler_statistics_are_training_only(self):
        import numpy as np
        bars,_=synthetic(days=45);bars=[b for b in bars if b.pair=='BTC/USD']
        c=Config(strategy='lstm_prediction',lstm_epochs=1,lstm_hidden=4,lstm_sequence=8)
        _,arrays=market_arrays(bars)
        _,metadata,_,_=fit_predict(bars,c)
        cut=int(len(bars)*.6)
        expected=arrays['BTC/USD']['x'][24:cut].mean(axis=0)
        np.testing.assert_allclose(metadata['scaler_mean'],expected,rtol=1e-6)
