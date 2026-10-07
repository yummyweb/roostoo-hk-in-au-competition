#!/usr/bin/env python3
"""Build the research panels from the repository's hourly candles.

Inputs: data/binance-50-1h.csv (scripts/assemble_universe.py), the six later days kept in
research/lab/data/candles-2026-10-01-to-06.csv, data/universe-1h.csv for the older 12-pair set, and each pair's
half-spread measured from one Roostoo ticker snapshot (research/lab/data/half_spreads.json).
Outputs research/lab/data/panel_{design,select,full,early12}.pkl: (timestamps, pairs, array[T, N, OHLCV], half_spreads).
The first 60% of rows is the design period, the next 20% the selection period, the last 20% the holdout.
"""
import csv
import json
import pickle
from pathlib import Path
import numpy as np

LAB = Path(__file__).resolve().parent; ROOT = LAB.parents[1]; HOUR = 3_600_000


def read(path, rows):
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.setdefault(r['pair'], {})[int(r['timestamp'])] = [float(r[k]) for k in ('open', 'high', 'low', 'close', 'volume')]
    return rows


def assemble(rows, before=None):
    pairs = sorted(rows); ts = sorted(set.intersection(*(set(rows[p]) for p in pairs)))
    if before is not None: ts = [t for t in ts if t < before]
    a = np.array([[rows[p][t] for p in pairs] for t in ts]); ts = np.array(ts)
    assert (np.diff(ts) == HOUR).all() and np.isfinite(a).all(), 'candles must be gap-free'
    return ts, pairs, a


def main():
    spreads = json.loads((LAB / 'data/half_spreads.json').read_text())
    rows = read(LAB / 'data/candles-2026-10-01-to-06.csv', read(ROOT / 'data/binance-50-1h.csv', {}))
    ts, pairs, a = assemble(rows); hs = np.array([spreads[p] for p in pairs]); T = len(ts)
    for name, end in (('design', int(T * .6)), ('select', int(T * .8)), ('full', T)):
        with open(LAB / f'data/panel_{name}.pkl', 'wb') as f: pickle.dump((ts[:end], pairs, a[:end], hs), f)
        print(f'{name}: rows 0..{end - 1}, {len(pairs)} pairs')
    ets, epairs, ea = assemble(read(ROOT / 'data/universe-1h.csv', {}), before=int(ts[0]))
    with open(LAB / 'data/panel_early12.pkl', 'wb') as f: pickle.dump((ets, epairs, ea, np.array([spreads[p] for p in epairs])), f)
    print(f'early12: {len(ets)} rows, {len(epairs)} pairs')


if __name__ == '__main__': main()
