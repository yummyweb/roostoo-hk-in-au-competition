#!/usr/bin/env python3
"""Assemble complete per-symbol broad-universe downloads into one CSV."""
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roostoo.data import read_csv, validate_bars, write_csv


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', default='data/binance-broad-all')
    p.add_argument('--output', default='data/binance-broad-1h.csv')
    p.add_argument('--min-assets', type=int, default=100)
    a = p.parse_args()
    source = Path(a.source); report = json.loads((source / 'download.json').read_text())
    complete = [x['symbol'] for x in report['results'] if x.get('complete')]
    if len(complete) < a.min_assets: raise SystemExit(f'Only {len(complete)} complete assets; need {a.min_assets}')
    series = {}; records = []
    for symbol in sorted(complete):
        path = source / (symbol + '.csv')
        bars, _ = read_csv(path)
        series[symbol] = bars
        records.append({'symbol': symbol, 'rows': len(bars), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    start = max(v[0].timestamp for v in series.values())
    end = min(v[-1].timestamp for v in series.values()) + 3_600_000
    joined = []
    for symbol, bars in series.items():
        rows = [b for b in bars if start <= b.timestamp < end]
        if len(rows) * 3_600_000 != end - start: raise SystemExit(f'{symbol}: incomplete common window')
        joined.extend(rows)
    joined.sort(key=lambda b: (b.timestamp, b.pair)); interval = validate_bars(joined)
    manifest = {'source': 'Binance public spot OHLCV via data-api.binance.vision',
        'endpoint': 'https://data-api.binance.vision/api/v3/klines', 'synthetic': False,
        'universe': [x + '/USD' for x in sorted(complete)], 'asset_count': len(complete),
        'selection': 'Top current Binance USDT spot pairs by 24-hour quote volume, excluding stablecoins, leveraged tokens and tokenized stocks; complete one-year hourly coverage required.',
        'common_start_ms': start, 'common_end_exclusive_ms': end, 'common_candles_per_asset': (end-start)//interval,
        'quote_mapping': 'Binance USDT mapped to USD; historical Roostoo spreads/depth unavailable',
        'source_files': records, 'screen_file': 'screen.json', 'download_file': 'download.json',
        'assembled_at': datetime.now(timezone.utc).isoformat(),
        'survivorship_note': 'Current listing and volume screen creates survivorship and selection bias; this is a research universe.'}
    write_csv(a.output, joined, manifest)
    print(json.dumps({'output': a.output, 'assets': len(complete), 'rows': len(joined),
                      'start': start, 'end_exclusive': end}, indent=2))


if __name__ == '__main__': main()
