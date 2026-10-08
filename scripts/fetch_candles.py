#!/usr/bin/env python3
"""Download recent candle closes for the execution universe from Binance's public data API.

    scripts/fetch_candles.py [days] [candle minutes]     (default 20 days of 5-minute candles)

Writes data/candles_<minutes>m/<COIN>.json as [[open time in ms, close], ...]. Used to fit the regime model of a bar
length (scripts/fit_bar_regime.py) and to replay the runner (scripts/replay_bars.py). No key is needed.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import json
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
MINUTE=60000


def closes(pair,end,count,minutes):
    """The last `count` completed candles before `end`, oldest first; [] if Binance does not list the coin."""
    rows=[]
    try:
        while len(rows)<count:
            query=urlencode({'symbol':pair.split('/')[0]+'USDT','interval':f'{minutes}m','endTime':end-1,'limit':min(1000,count-len(rows))})
            with urlopen('https://data-api.binance.vision/api/v3/klines?'+query,timeout=20) as response:batch=json.load(response)
            if not batch:break
            rows=[[int(r[0]),float(r[4])] for r in batch]+rows;end=int(batch[0][0])
    except Exception as error:
        print(f'{pair}: {error}',file=sys.stderr)
    return rows


def main():
    days=float(sys.argv[1]) if len(sys.argv)>1 else 20.;minutes=int(sys.argv[2]) if len(sys.argv)>2 else 5
    doc=json.loads((ROOT/'config/universe-crypto.json').read_text());pairs=doc['pairs'];span=minutes*MINUTE
    end=int(time.time()*1000)//span*span;out=ROOT/f'data/candles_{minutes}m';out.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(8) as pool:
        for pair,rows in zip(pairs,pool.map(lambda p:closes(p,end,int(days*1440/minutes),minutes),pairs)):
            (out/(pair.split('/')[0]+'.json')).write_text(json.dumps(rows))
            print(f'{pair}: {len(rows)} candles',flush=True)


if __name__=='__main__':main()
