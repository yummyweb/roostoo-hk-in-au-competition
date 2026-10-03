#!/usr/bin/env python3
"""Download a liquid, broad Binance USDT/spot universe for causal research.

The exchange has hundreds of currently trading symbols. This script screens the
current exchange list by 24-hour quote volume, removes stablecoins, leveraged
tokens and tokenized-stock symbols, and downloads one synchronized hourly year.
It writes one identified Binance CSV per symbol; assembly is a separate step so
the screening and common-window decisions remain auditable.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API = 'https://data-api.binance.vision/api/v3/'
INTERVAL_MS = 3_600_000
STABLES = {'USDT', 'USDC', 'FDUSD', 'TUSD', 'USDP', 'DAI', 'BUSD', 'USD1', 'EUR', 'TRY', 'BRL'}
LEVERAGED_SUFFIXES = ('UP', 'DOWN', 'BULL', 'BEAR')


def get_json(path, params=None):
    query = urlencode(params or {})
    with urlopen(Request(API + path + ('?' + query if query else ''), headers={'User-Agent': 'quant-research'}), timeout=45) as response:
        return json.load(response)


def select_symbols(exchange, tickers, count):
    allowed = {
        s['symbol']: s for s in exchange['symbols']
        if s.get('status') == 'TRADING' and s.get('quoteAsset') == 'USDT'
        and s.get('isSpotTradingAllowed') and s.get('baseAsset') not in STABLES
        and not s.get('baseAsset', '').endswith(LEVERAGED_SUFFIXES)
        and not s.get('baseAsset', '').endswith('B')
    }
    ranked = []
    for row in tickers:
        symbol = row.get('symbol')
        if symbol in allowed:
            ranked.append((float(row.get('quoteVolume', 0.0)), symbol, allowed[symbol]['baseAsset']))
    ranked.sort(reverse=True)
    return ranked[:count]


def download_one(symbol, start, end, output):
    destination = output / (symbol + '.csv')
    expected = (end - start) // INTERVAL_MS
    cursor = start
    rows = []
    while cursor < end:
        data = get_json('klines', {'symbol': symbol, 'interval': '1h', 'startTime': cursor, 'endTime': end - 1, 'limit': 1000})
        if not data:
            break
        rows.extend(row for row in data if int(row[0]) + INTERVAL_MS <= end)
        next_cursor = int(data[-1][0]) + INTERVAL_MS
        if next_cursor <= cursor:
            raise RuntimeError('pagination did not advance')
        cursor = next_cursor
    rows = [r for r in rows if start <= int(r[0]) < end]
    complete = len(rows) == expected and rows and int(rows[0][0]) == start and int(rows[-1][0]) == end - INTERVAL_MS
    if complete:
        lines = ['timestamp,pair,open,high,low,close,volume']
        lines.extend(','.join(map(str, (int(r[0]), symbol[:-4] + '/USD', *[float(r[i]) for i in (1, 2, 3, 4, 5)]))) for r in rows)
        destination.write_text('\n'.join(lines) + '\n')
    return dict(symbol=symbol, rows=len(rows), complete=bool(complete), first=int(rows[0][0]) if rows else None, last=int(rows[-1][0]) if rows else None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default='2025-10-01')
    parser.add_argument('--end', default='2026-10-01')
    parser.add_argument('--count', type=int, default=250)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--output', default='data/binance-broad-all')
    args = parser.parse_args()
    start = int(datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc).timestamp() * 1000)
    end = int(datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc).timestamp() * 1000)
    if end <= start or (end - start) % INTERVAL_MS:
        raise SystemExit('start/end must define complete hourly candles')
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    exchange = get_json('exchangeInfo')
    tickers = get_json('ticker/24hr')
    selected = select_symbols(exchange, tickers, args.count)
    (output / 'screen.json').write_text(json.dumps({'source': API, 'start': args.start, 'end': args.end,
        'requested_count': args.count, 'selected': [{'symbol': s, 'base_asset': a, 'quote_volume_24h': v} for v, s, a in selected]}, indent=2))
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download_one, symbol, start, end, output): symbol for _, symbol, _ in selected}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = dict(symbol=symbol, rows=0, complete=False, error=str(exc))
            results.append(result)
            print(json.dumps(result), flush=True)
    results.sort(key=lambda x: x['symbol'])
    (output / 'download.json').write_text(json.dumps({'source': API, 'downloaded_at': datetime.now(timezone.utc).isoformat(),
        'start': args.start, 'end': args.end, 'results': results}, indent=2))
    print(json.dumps({'requested': len(selected), 'complete': sum(x['complete'] for x in results), 'output': str(output)}))


if __name__ == '__main__':
    main()
