#!/usr/bin/env python3
"""Assemble a fixed, real Binance/Roostoo crypto universe from cached per-asset files."""
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roostoo.data import read_csv, write_csv, validate_bars

DEFAULT_ASSETS='AAVE,ADA,APT,ARB,AVAX,BNB,BONK,BTC,CAKE,CFX,CRV,DOGE,DOT,ENA,ETH,FET,FIL,FLOKI,HBAR,ICP,LINK,LISTA,LTC,NEAR,PAXG,PENDLE,PEPE,POL,SEI,SHIB,SOL,SUI,TAO,TRX,UNI,WIF,WLD,XLM,XRP,ZEC,ZEN,1000CHEEMS,EIGEN,PENGU,TRUMP,S,STO,TUT,ONDO,VIRTUAL'

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',default=DEFAULT_ASSETS);p.add_argument('--source',default='data/binance-all');p.add_argument('--output',default='data/binance-50-1h.csv');p.add_argument('--min-rows',type=int,default=10000);p.add_argument('--end',default='2026-10-01');a=p.parse_args()
 assets=list(dict.fromkeys(x.strip().upper() for x in a.assets.split(',') if x.strip()))
 if len(assets)!=50: raise ValueError(f'Expected exactly 50 assets, got {len(assets)}')
 source=Path(a.source);series={};records=[]
 for asset in assets:
  file=source/(asset+'USDT.csv')
  if not file.exists(): raise FileNotFoundError(file)
  bars,meta=read_csv(file)
  if meta.get('synthetic') or not meta.get('source','').startswith('Binance'):
   raise ValueError(f'{asset}: source is not identified Binance data')
  bars=[b for b in bars if b.pair==asset+'/USD']
  if len(bars)<a.min_rows:raise ValueError(f'{asset}: only {len(bars)} rows, below --min-rows')
  series[asset]=bars;records.append(dict(asset=asset,rows=len(bars),first_timestamp=bars[0].timestamp,last_timestamp=bars[-1].timestamp,source_file=file.name,source_sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
 common_start=max(v[0].timestamp for v in series.values()); common_end=min(v[-1].timestamp for v in series.values())+3600000
 joined=[]
 for asset in assets:
  rows=[b for b in series[asset] if common_start<=b.timestamp<common_end]
  if len(rows)*3600000 != common_end-common_start:raise ValueError(f'{asset}: gaps or incomplete common window')
  joined.extend(rows)
 joined.sort(key=lambda b:(b.timestamp,b.pair));validate_bars(joined)
 manifest={'source':'Binance public spot OHLCV via data-api.binance.vision','endpoint':'https://data-api.binance.vision/api/v3/klines','synthetic':False,'universe':[x+'/USD' for x in assets],'asset_count':50,'selection':'Fixed 50 tradable Roostoo crypto pairs selected before replay from cached Binance histories; all have >=10,000 completed hourly candles and the common synchronized window is used.','requested_assets':assets,'common_start_ms':common_start,'requested_end_exclusive_ms':common_end,'common_candles_per_asset':(common_end-common_start)//3600000,'quote_mapping':'Binance USDT mapped to Roostoo USD; historical Roostoo spreads/depth unavailable','source_files':records,'assembled_at':datetime.now(timezone.utc).isoformat(),'survivorship_note':'Current overlap membership and available history are used; this is not point-in-time historical membership.'}
 write_csv(a.output,joined,manifest);print(json.dumps(dict(output=a.output,assets=len(assets),rows=len(joined),common_start_ms=common_start,common_end_exclusive_ms=common_end,sha256=hashlib.sha256(Path(a.output).read_bytes()).hexdigest()),indent=2))
if __name__=='__main__':main()
