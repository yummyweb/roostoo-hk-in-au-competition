"""LSTM Prediction: pooled OHLCV forecasting with purged chronological splits.

All sequence inputs end at the signal candle. Labels are future log returns;
only labels wholly contained in their training/validation partition are used.
The final 20% is never used for fitting, scaling, epoch or threshold selection.
"""
from dataclasses import asdict, replace
import copy
import hashlib
from itertools import groupby
import json
from pathlib import Path
import sys

FEATURE_NAMES = ['log_return_1','log_return_6','log_return_24','range_fraction',
                 'body_return','relative_log_volume','volatility_24','mean_deviation_24']


def dependencies():
    try:
        import numpy as np
        import torch
    except ImportError as exc:
        raise RuntimeError('LSTM Prediction needs the ML environment. Run scripts/setup-lstm.sh, or set ROOSTOO_PYTHON to a Python with requirements-lstm.txt installed.') from exc
    return np, torch


def splits(length, sequence, horizon):
    if length < 1000:
        raise ValueError('LSTM Prediction requires at least 1,000 hourly candles per pair (about 42 days).')
    train_end=int(length*.6);test_start=int(length*.8)
    # 24 warmup bars precede a full sequence; labels cannot cross a partition.
    first=24+sequence-1
    train=list(range(first,train_end-horizon,3))
    validation=list(range(train_end,test_start-horizon,3))
    test=list(range(test_start,length))
    if len(train)<100 or len(validation)<30 or len(test)<horizon+10:
        raise ValueError('LSTM Prediction requires at least 1,000 hourly candles per pair (about 42 days).')
    return train,validation,test,train_end,test_start


def market_arrays(bars):
    np,_=dependencies()
    pairs=sorted({b.pair for b in bars})
    arrays={}
    for pair in pairs:
        rows=[b for b in bars if b.pair==pair]
        close=np.asarray([b.close for b in rows],dtype=np.float64)
        volume=np.log1p([b.volume for b in rows]);n=len(rows)
        x=np.zeros((n,len(FEATURE_NAMES)),dtype=np.float32)
        returns=np.zeros(n);returns[1:]=np.diff(np.log(close))
        for t,b in enumerate(rows):
            x[t,0]=returns[t]
            x[t,1]=np.log(close[t]/close[max(0,t-6)])
            x[t,2]=np.log(close[t]/close[max(0,t-24)])
            x[t,3]=(b.high-b.low)/b.close
            x[t,4]=np.log(b.close/b.open)
            x[t,5]=volume[t]-volume[max(0,t-23):t+1].mean()
            x[t,6]=returns[max(0,t-23):t+1].std()
            x[t,7]=np.log(close[t]/close[max(0,t-23):t+1].mean())
        if not np.isfinite(x).all():
            raise ValueError(f'Nonfinite derived LSTM features for {pair}')
        arrays[pair]={'x':x,'close':close,'timestamps':[b.timestamp for b in rows]}
    return pairs,arrays


def build_model(torch,features,hidden):
    class Forecaster(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm=torch.nn.LSTM(features,hidden,batch_first=True)
            self.head=torch.nn.Linear(hidden,1)
        def forward(self,x):
            values,_=self.lstm(x)
            return self.head(values[:,-1]).squeeze(-1)
    return Forecaster()


def fit_predict(bars,c,artifact_dir=None):
    np,torch=dependencies()
    torch.set_num_threads(4);torch.manual_seed(c.lstm_seed)
    torch.use_deterministic_algorithms(True)
    pairs,arrays=market_arrays(bars);n=len(arrays[pairs[0]]['close'])
    train_idx,val_idx,test_idx,train_end,test_start=splits(n,c.lstm_sequence,c.lstm_horizon)
    # Only features available before the training boundary fit the scaler.
    training_features=np.concatenate([arrays[p]['x'][24:train_end] for p in pairs])
    mean=training_features.mean(axis=0);scale=training_features.std(axis=0)
    scale=np.maximum(scale,1e-6)
    scaled={p:np.clip((arrays[p]['x']-mean)/scale,-10,10).astype(np.float32) for p in pairs}
    def examples(indices):
        sequences=[];labels=[]
        for p in pairs:
            close=arrays[p]['close']
            for i in indices:
                sequences.append(scaled[p][i-c.lstm_sequence+1:i+1])
                labels.append(np.log(close[i+c.lstm_horizon]/close[i])*100)
        return torch.from_numpy(np.stack(sequences)),torch.tensor(labels,dtype=torch.float32)
    train_x,train_y=examples(train_idx);val_x,val_y=examples(val_idx)
    model=build_model(torch,len(FEATURE_NAMES),c.lstm_hidden)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    # Huber loss reduces the influence of extreme crypto returns.
    loss_fn=torch.nn.HuberLoss(delta=1.)
    loader=torch.utils.data.DataLoader(torch.utils.data.TensorDataset(train_x,train_y),batch_size=256,shuffle=True,
                                     generator=torch.Generator().manual_seed(c.lstm_seed))
    best=None;best_loss=float('inf');best_epoch=0;history=[]
    for epoch in range(c.lstm_epochs):
        model.train();total=0
        for x,y in loader:
            optimizer.zero_grad();loss=loss_fn(model(x),y);loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
            optimizer.step();total+=float(loss.detach())*len(y)
        model.eval()
        with torch.no_grad():
            predicted=torch.cat([model(val_x[i:i+512]) for i in range(0,len(val_x),512)])
            vloss=float(loss_fn(predicted,val_y))
        history.append({'epoch':epoch+1,'training_huber':total/len(train_y),'validation_huber':vloss})
        print(f'LSTM epoch {epoch+1}/{c.lstm_epochs}: validation loss {vloss:.6f}',file=sys.stderr,flush=True)
        if vloss<best_loss:
            best_loss=vloss;best=copy.deepcopy(model.state_dict());best_epoch=epoch+1
    if best is None:
        raise ValueError('LSTM training did not produce a finite validation loss')
    model.load_state_dict(best);model.eval()
    # Inference sees only a past sequence, with a frozen model and scaler.
    forecasts={};actual=[];predicted=[];rows=[]
    with torch.no_grad():
        for p in pairs:
            sequences=np.stack([scaled[p][i-c.lstm_sequence+1:i+1] for i in test_idx])
            tx=torch.from_numpy(sequences)
            output=torch.cat([model(tx[i:i+512]) for i in range(0,len(tx),512)]).numpy()/100
            forecasts[p]={}
            for i,value in zip(test_idx,output):
                clipped=float(np.clip(value,-.5,.5));ret=float(np.expm1(clipped));price=float(arrays[p]['close'][i]*np.exp(clipped))
                forecasts[p][i]={'predicted_return':ret,'predicted_price':price,'forecast_horizon':c.lstm_horizon}
                outcome=float(arrays[p]['close'][i+c.lstm_horizon]/arrays[p]['close'][i]-1) if i+c.lstm_horizon<n else None
                rows.append({'pair':p,'timestamp':arrays[p]['timestamps'][i],'forecast_available_at':arrays[p]['timestamps'][i]+3600000,
                             'target_timestamp':arrays[p]['timestamps'][i]+(c.lstm_horizon+1)*3600000,
                             'close':float(arrays[p]['close'][i]),'predicted_price':price,'predicted_return':ret,'actual_return':outcome})
                if outcome is not None:actual.append(outcome);predicted.append(ret)
    actual=np.asarray(actual);predicted=np.asarray(predicted)
    directional=np.abs(actual)>1e-12
    metrics={'return_mae':float(np.abs(actual-predicted).mean()),'zero_return_mae':float(np.abs(actual).mean()),
             'return_rmse':float(np.sqrt(np.mean((actual-predicted)**2))),
             'zero_return_rmse':float(np.sqrt(np.mean(actual**2))),
             'directional_accuracy':float(np.mean((predicted[directional]>0)==(actual[directional]>0))) if directional.any() else None,
             'always_up_accuracy':float(np.mean(actual[directional]>0)) if directional.any() else None,
             'directional_samples':int(directional.sum()),'zero_return_samples':int((~directional).sum()),
             'correlation':float(np.corrcoef(actual,predicted)[0,1]) if actual.std()>1e-12 and predicted.std()>1e-12 else None,
             'labeled_predictions':len(actual)}
    weights_hash=hashlib.sha256(b''.join(v.detach().numpy().tobytes() for k,v in sorted(best.items()))).hexdigest()
    metadata={'strategy':'LSTM Prediction','architecture':f'1-layer LSTM, {c.lstm_hidden} hidden units, linear return head',
              'sequence_bars':c.lstm_sequence,'forecast_horizon_bars':c.lstm_horizon,'feature_names':FEATURE_NAMES,
              'target':'100 × log(close[t+horizon] / close[t]); converted back to a future price forecast',
              'train_end_exclusive':arrays[pairs[0]]['timestamps'][train_end],
              'test_start':arrays[pairs[0]]['timestamps'][test_start],
              'last_train_label_timestamp':arrays[pairs[0]]['timestamps'][train_idx[-1]+c.lstm_horizon],
              'last_validation_label_timestamp':arrays[pairs[0]]['timestamps'][val_idx[-1]+c.lstm_horizon],
              'train_samples':len(train_y),'validation_samples':len(val_y),'best_epoch':best_epoch,'history':history,
              'scaler_mean':mean.tolist(),'scaler_scale':scale.tolist(),'seed':c.lstm_seed,
              'weight_sha256':weights_hash,'torch_version':torch.__version__,'numpy_version':np.__version__,
              'forecast_metrics':metrics,'split_method':'60% fit / 20% epoch selection / 20% evaluation; horizon-purged labels; scaler fits training only',
              'history_reuse':'Model evaluation uses a reserved partition, but these historical markets were previously explored by other strategies.'}
    if artifact_dir:
        directory=Path(artifact_dir);directory.mkdir(parents=True,exist_ok=True)
        torch.save({'state_dict':best,'metadata':metadata,'config':asdict(c)},directory/'model.pt')
        (directory/'model.json').write_text(json.dumps(metadata,indent=2,allow_nan=False))
        (directory/'forecasts.jsonl').write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows))
    return forecasts,metadata,rows,test_start


def run_lstm(bars,c,manifest,rules,artifact_dir=None):
    from .data import validate_bars
    from .engine import run
    from .strategy import Indicators
    if validate_bars(bars)!=3600000:
        raise ValueError('LSTM Prediction currently requires hourly market candles')
    if (manifest or {}).get('synthetic'):
        raise ValueError('Choose a historical market CSV for LSTM Prediction; synthetic demo training is disabled.')
    forecasts,metadata,rows,start=fit_predict(bars,c,artifact_dir)
    states={p:Indicators(c) for p in forecasts};features=[]
    for i,(_,group) in enumerate(groupby(bars,key=lambda b:b.timestamp)):
        frame={}
        for b in group:
            f=states[b.pair].update(b);f.update(forecasts[b.pair].get(i,{}))
            f['forecast_entry_hurdle']=(2*c.fee_bps+c.spread_bps+2*c.slippage_bps)/10000+c.lstm_min_edge
            frame[b.pair]=f
        features.append(frame)
    result=run(bars,c,manifest,rules,start_index=start,precomputed=features)
    # Data and predictions retain warmup context, but equity and performance start at test boundary.
    result.update(name='LSTM Prediction',model=metadata,forecasts=rows)
    display_start=result['evaluation_start']-c.lstm_sequence*3600000
    result['bars']=[b for b in result['bars'] if b['timestamp']>=display_start]
    result['warnings'].insert(0,metadata['history_reuse'])
    result['warnings'].append('Future-price accuracy is measured against a no-change forecast. Profitable trading requires enough edge to cover costs.')
    stress=run(bars,replace(c,fee_bps=20,spread_bps=10,slippage_bps=10),manifest,rules,start_index=start,precomputed=features)
    result['model']['cost_stress_metrics']=stress['metrics']
    result['model']['cost_stress_method']='Same frozen forecasts and base entry hurdle; only execution fees, spread and slippage change.'
    return result
