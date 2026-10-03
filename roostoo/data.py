"""OHLCV ingestion with explicit provenance and strict chronological validation."""
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
import random


@dataclass(frozen=True)
class Bar:
    timestamp: int  # candle OPEN, UTC milliseconds
    pair: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def validate(self):
        if not 1_000_000_000_000 <= self.timestamp < 10_000_000_000_000:
            raise ValueError('timestamp must be 13-digit UTC milliseconds')
        if not self.pair.endswith('/USD') or len(self.pair) > 24:
            raise ValueError(f'Expected BASE/USD pair: {self.pair}')
        if not all(math.isfinite(v) and v > 0 for v in (self.open, self.high, self.low, self.close)):
            raise ValueError('Prices must be finite and positive')
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close) or self.low > self.high:
            raise ValueError('Invalid OHLC range')
        if not math.isfinite(self.volume) or self.volume < 0:
            raise ValueError('Invalid volume')


def validate_bars(bars):
    if not bars:
        raise ValueError('Dataset is empty')
    times = {}
    previous = -1
    for bar in bars:
        bar.validate()
        if bar.timestamp < previous:
            raise ValueError('Input must be chronological; out-of-order row found')
        previous = bar.timestamp
        sequence = times.setdefault(bar.pair, [])
        if sequence and bar.timestamp <= sequence[-1]:
            raise ValueError(f'Duplicate/out-of-order timestamp for {bar.pair}')
        sequence.append(bar.timestamp)
    reference = next(iter(times.values()))
    if len(reference) < 3:
        raise ValueError('Need at least three candles per pair')
    interval = reference[1] - reference[0]
    if interval < 60_000:
        raise ValueError('Minimum candle interval is one minute')
    if any(b-a != interval for a,b in zip(reference, reference[1:])):
        raise ValueError('Data has gaps or irregular intervals; repair the source before replay')
    if any(seq != reference for seq in times.values()):
        raise ValueError('All pairs must have the same complete timeline; missing candles found')
    return interval


def read_csv(path):
    path = Path(path)
    with path.open(newline='') as f:
        bars = [Bar(int(r['timestamp']), r['pair'], *(float(r[k]) for k in ('open','high','low','close')), float(r.get('volume') or 0)) for r in csv.DictReader(f)]
    interval = validate_bars(bars)
    manifest_path = path.with_suffix('.manifest.json')
    supplied = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest = dict(supplied, file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    rows=len(bars), interval_ms=interval, start=bars[0].timestamp, end=bars[-1].timestamp)
    manifest.setdefault('source', 'User-imported OHLCV; origin not verified')
    manifest.setdefault('synthetic', False)
    return bars, manifest


def write_csv(path, bars, manifest):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(bars[0])))
        writer.writeheader()
        writer.writerows(asdict(b) for b in bars)
    path.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2))


def synthetic(days=90, seed=27):
    """Regime-changing fixture. Never use its returns as strategy evidence."""
    rng = random.Random(seed)
    start = int(datetime(2025,1,1,tzinfo=timezone.utc).timestamp()*1000)
    prices = {'BTC/USD': 95000., 'ETH/USD': 3300., 'SOL/USD': 190.}
    bars = []
    for i in range(days*24):
        common = rng.gauss(0, .004)
        phase = (i // 180) % 5
        drift = [.0012, -.001, .0001, .0015, -.0006][phase]
        for j, (pair, price) in enumerate(prices.items()):
            movement = drift + common + rng.gauss(0, .0025 + j*.0008)
            close = price * math.exp(movement)
            width = abs(rng.gauss(.002, .001))
            bars.append(Bar(start+i*3_600_000, pair, price, max(price,close)*(1+width), min(price,close)*(1-width),close,rng.uniform(100,10000)))
            prices[pair] = close
    return bars, {'source':'Deterministic synthetic development fixture', 'synthetic':True, 'seed':seed, 'interval_ms':3_600_000}
