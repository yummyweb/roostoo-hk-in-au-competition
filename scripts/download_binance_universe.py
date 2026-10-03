#!/usr/bin/env python3
"""Discover Binance/Roostoo overlap, save every pair's real history and coverage.

No fabricated pre-listing candles. Each asset is saved individually; a synchronized
CSV for the existing portfolio simulator uses the common real-data intersection
of all pairs with >=1,000 complete consecutive hourly candles.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import ssl
import sys
import time
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roostoo.data import Bar,read_csv,write_csv,validate_bars

HOST='https://data-api.binance.vision'
HOUR=3600000


def get_json(url):
    for attempt in range(4):
        try:
            with urlopen(url,timeout=30) as response:return json.load(response)
        except HTTPError as e:
            if e.code not in (429,500,502,503,504) or attempt==3:raise
            delay=min(30,int(e.headers.get('Retry-After','2')))
        except (URLError,TimeoutError):
            if attempt==3:raise
            delay=2**attempt
        time.sleep(delay)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',default='2024-10-01');parser.add_argument('--end',default='2026-10-01')
    parser.add_argument('--output',default='data/binance-all');parser.add_argument('--reuse',default='data/universe-1h.csv')
    args=parser.parse_args();folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True)
    start=int(datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc).timestamp()*1000)
    end=min(int(datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc).timestamp()*1000),int(time.time()*1000)//HOUR*HOUR)
    exchange=get_json(HOST+'/api/v3/exchangeInfo')
    roostoo=get_json('https://mock-api.roostoo.com/v3/exchangeInfo')
    (folder/'binance-exchange.json').write_text(json.dumps(exchange,indent=2))
    (folder/'roostoo-exchange.json').write_text(json.dumps(roostoo,indent=2))
    binance={s['baseAsset']:s['symbol'] for s in exchange['symbols'] if s['quoteAsset']=='USDT' and s['status']=='TRADING' and s.get('isSpotTradingAllowed',True)}
    requested=sorted(p for p,r in roostoo['TradePairs'].items() if r['CanTrade'] and p.endswith('/USD'))
    overlap=[p for p in requested if p.split('/')[0] in binance]
    unavailable=[{'pair':p,'reason':'No current Binance TRADING USDT spot pair with the same base asset'} for p in requested if p not in overlap]
    cache={}
    if Path(args.reuse).exists():
        for b in read_csv(args.reuse)[0]:cache.setdefault(b.pair,[]).append(b)
    print(f'Discovered {len(overlap)} exact Binance/Roostoo pairs; {len(unavailable)} unavailable on Binance USDT spot.',flush=True)
    def fetch(pair):
        asset=pair.split('/')[0];file=folder/(asset+'USDT.csv')
        rows=[]
        if file.exists():
            try:rows=read_csv(file)[0]
            except ValueError:pass
        if not rows:rows=cache.get(pair,[])
        rows=[b for b in rows if start<=b.timestamp<end]
        # A cached pre-listing-truncated series is valid only when its own manifest
        # records the requested range; existing long-history cache starts at start.
        if rows and rows[0].timestamp>start and not file.exists():rows=[]
        cursor=rows[-1].timestamp+HOUR if rows else start
        while cursor<end:
            query=urlencode({'symbol':binance[asset],'interval':'1h','startTime':cursor,'endTime':end-1,'limit':1000})
            batch=get_json(HOST+'/api/v3/klines?'+query)
            if not batch:break
            for r in batch:
                if int(r[0])+HOUR<=end:
                    bar=Bar(int(r[0]),pair,*(float(r[i]) for i in (1,2,3,4,5)));bar.validate();rows.append(bar)
            next_cursor=int(batch[-1][0])+HOUR
            if next_cursor<=cursor:raise ValueError('Pagination did not advance')
            cursor=next_cursor;time.sleep(.1)
        rows.sort(key=lambda b:b.timestamp)
        if not rows:return pair,rows,{'pair':pair,'rows':0,'eligible':False,'reason':'No completed candles in requested range'}
        gaps=sum(b.timestamp-a.timestamp!=HOUR for a,b in zip(rows,rows[1:]))
        manifest={'source':'Binance public spot OHLCV','endpoint':HOST+'/api/v3/klines','binance_symbol':binance[asset],
                  'synthetic':False,'requested_start_ms':start,'requested_end_exclusive_ms':end,
                  'first_available_ms':rows[0].timestamp,'last_available_ms':rows[-1].timestamp,
                  'quote_mapping':'Binance USDT is a proxy for Roostoo USD; no historical Roostoo fill/depth claim',
                  'downloaded_at':datetime.now(timezone.utc).isoformat()}
        write_csv(file,rows,manifest)
        eligible=len(rows)>=1000 and gaps==0 and rows[-1].timestamp+HOUR==end
        return pair,rows,{'pair':pair,'binance_symbol':binance[asset],'rows':len(rows),'gaps':gaps,
                         'first_available_ms':rows[0].timestamp,'last_available_ms':rows[-1].timestamp,
                         'file':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'eligible':eligible,
                         'reason':None if eligible else 'Insufficient history (<1000 candles), gaps, or missing end of requested period'}
    all_rows={};coverage=[];failures=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(fetch,p):p for p in overlap}
        for job in as_completed(jobs):
            pair=jobs[job]
            try:
                pair,rows,record=job.result();all_rows[pair]=rows;coverage.append(record)
                print(f'{pair}: {record["rows"]} candles'+('' if record['eligible'] else ' (coverage exception)'),flush=True)
            except Exception as exc:
                failures.append({'pair':pair,'error':str(exc)});print(f'{pair}: FAILED {exc}',file=sys.stderr,flush=True)
    report={'source':HOST+'/api/v3/klines','requested_roostoo_pairs':len(requested),'binance_overlap':len(overlap),
            'unavailable':unavailable,'coverage':sorted(coverage,key=lambda r:r['pair']),'failures':failures,
            'requested_start_ms':start,'requested_end_exclusive_ms':end,
            'selection':'Exact active Binance USDT / tradable Roostoo USD overlap, with explicit coverage checks; no top-N asset cap',
            'survivorship_note':'Universe is discovered today, not a historical point-in-time membership reconstruction.'}
    eligible=[r['pair'] for r in coverage if r['eligible']]
    if eligible:
        common_start=max(all_rows[p][0].timestamp for p in eligible)
        joined=[b for p in eligible for b in all_rows[p] if b.timestamp>=common_start]
        joined.sort(key=lambda b:(b.timestamp,b.pair));validate_bars(joined)
        report.update(model_pairs=sorted(eligible),common_start_ms=common_start,common_candles_per_pair=(end-common_start)//HOUR)
        write_csv(folder/'market.csv',joined,{'source':'Binance public spot OHLCV — full eligible Roostoo overlap',
                  'endpoint':HOST+'/api/v3/klines','synthetic':False,'universe':sorted(eligible),
                  'quote_mapping':'USDT mapped to USD; historical Roostoo basis, spreads and impact unavailable',
                  'common_start_ms':common_start,'requested_start_ms':start,'requested_end_exclusive_ms':end,
                  'coverage_file':'coverage.json','selection':report['selection'],'survivorship_note':report['survivorship_note']})
        print(f'Portfolio CSV: {len(eligible)} assets × {(end-common_start)//HOUR} shared hourly candles.',flush=True)
    (folder/'coverage.json').write_text(json.dumps(report,indent=2))
    if failures:raise SystemExit('Some pairs failed. Per-pair files and coverage were saved; rerun to resume.')
    if not eligible:raise SystemExit('No eligible shared history; inspect coverage.json')

if __name__=='__main__':main()
