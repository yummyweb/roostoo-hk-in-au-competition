#!/usr/bin/env python3
"""Download completed Binance public 1h candles; USD mapping is an explicit proxy."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
from urllib.request import urlopen
from urllib.parse import urlencode
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roostoo.data import Bar,write_csv,validate_bars,read_csv


def main():
    p=argparse.ArgumentParser(); p.add_argument('--start',default='2024-10-01'); p.add_argument('--end',default='2026-10-01'); p.add_argument('--output',default='data/binance-1h.csv'); p.add_argument('--assets',default='BTC,ETH,SOL'); p.add_argument('--reuse'); a=p.parse_args()
    start=int(datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc).timestamp()*1000)
    requested_end=int(datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc).timestamp()*1000)
    end=min(requested_end,int(time.time()*1000)//3_600_000*3_600_000)
    assets=list(dict.fromkeys(asset.strip().upper() for asset in a.assets.split(',') if asset.strip()))
    if not assets: p.error('--assets must contain at least one symbol')
    bars=[]; cached_sources=[]
    if a.reuse:
        reuse=Path(a.reuse)
        files=[reuse/(asset+'USDT.csv') for asset in assets] if reuse.is_dir() else [reuse]
        for file in files:
            if file.exists():
                cached,metadata=read_csv(file)
                if metadata.get('synthetic') or not metadata.get('source','').startswith('Binance'):
                    raise ValueError('Only identified Binance market data can be reused by this downloader')
                bars.extend(cached)
                cached_sources.append({'file':str(file),'sha256':metadata['sha256'],'source':metadata['source']})
    bars=[b for b in bars if b.pair.split('/')[0] in assets and start<=b.timestamp<end]
    existing=set()
    for asset in assets:
        cached=[b for b in bars if b.pair==asset+'/USD']
        if cached and cached[0].timestamp==start and cached[-1].timestamp+3_600_000==end and len(cached)==(end-start)//3_600_000:
            existing.add(asset)
    bars=[b for b in bars if b.pair.split('/')[0] in existing]
    for asset in assets:
        if asset in existing: continue
        cursor=start
        while cursor<end:
            query=urlencode({'symbol':asset+'USDT','interval':'1h','startTime':cursor,'endTime':end-1,'limit':1000})
            with urlopen('https://data-api.binance.vision/api/v3/klines?'+query,timeout=30) as response:
                rows=json.load(response)
            if not rows: break
            for r in rows:
                if int(r[0])+3_600_000<=end:
                    bars.append(Bar(int(r[0]),asset+'/USD',*(float(r[i]) for i in (1,2,3,4,5))))
            next_cursor=int(rows[-1][0])+3_600_000
            if next_cursor<=cursor: raise ValueError('Source pagination did not advance')
            cursor=next_cursor
            time.sleep(.15)
        print(asset,'downloaded',file=sys.stderr)
    bars.sort(key=lambda b:(b.timestamp,b.pair)); validate_bars(bars)
    if {b.pair for b in bars}!={asset+'/USD' for asset in assets}:
        raise ValueError('Binance returned no history for one or more requested assets')
    if bars[0].timestamp!=start or bars[-1].timestamp+3_600_000!=end:
        raise ValueError('Requested period is not fully covered; choose a period with real history for every asset')
    write_csv(a.output,bars,{'source':'Binance public spot klines via data-api.binance.vision','synthetic':False,
                            'quote_mapping':'USDT prices mapped to USD pairs; basis risk and historical Roostoo spreads unavailable',
                            'requested_start':a.start,'requested_end_exclusive':a.end,'downloaded_at':datetime.now(timezone.utc).isoformat(),
                            'endpoint':'https://data-api.binance.vision/api/v3/klines',
                            'universe':[asset+'/USD' for asset in assets],'cached_sources':cached_sources,
                            'selection':'Fixed requested asset list; not a point-in-time full-universe study'})
    print(f'Saved {len(bars)} rows to {a.output}')

if __name__=='__main__': main()
