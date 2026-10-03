#!/usr/bin/env python3
"""Compare causal portfolio rules on the broad synchronized Binance universe."""
import argparse, json, math, sys
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roostoo.data import read_csv
from roostoo.ranking import execution_features, fit_scores, market_features, replay
from roostoo.rules import PairRule
from roostoo.strategy import Config


def rules_for(bars):
    # Binance breadth is deliberately research-only: current Roostoo rules do
    # not cover every Binance symbol. Use conservative generic spot rules for
    # symbols absent from the imported Roostoo snapshot and record that fact.
    import json
    info = json.loads(Path('config/exchange_info.json').read_text()).get('TradePairs', {})
    return {p: PairRule(int(info[p]['AmountPrecision']), int(info[p]['PricePrecision']), float(info[p]['MiniOrder']), bool(info[p]['CanTrade']))
            if p in info else PairRule(amount_precision=8, price_precision=8, minimum=1.0, can_trade=True)
            for p in sorted({b.pair for b in bars})}


def metrics(m):
    return {k: m[k] for k in ('total_return', 'max_drawdown', 'sharpe', 'sortino', 'calmar',
                               'closed_trades', 'fills', 'average_exposure', 'active_days', 'fees', 'turnover')}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--data', default='data/binance-broad-1h.csv'); p.add_argument('--output', default='runs/broad-universe-study')
    a = p.parse_args(); bars, manifest = read_csv(a.data); rules = rules_for(bars)
    market = market_features(bars); n = len(market['timestamps']); pairs = len(market['pairs']); features = execution_features(market, fit_scores(market, 'trend_budget', int(n*.6))[0])
    # Five contiguous fresh-wallet blocks: 60-day blocks after the causal
    # warmup, plus a 65-day tail. The last block is never used to select rules.
    blocks = [('b1', 720, 2160), ('b2', 2160, 3600), ('b3', 3600, 5040), ('b4', 5040, 6480), ('tail', 6480, n)]
    candidates = {
        'trend_budget_v15_liq100': Config(strategy='cross_asset', rank_model='trend_budget', target_volatility=.15, max_position=.2, max_exposure=.8, rank_liquidity_top_n=100, rank_min_trend_strength=0., rebalance_band=.02, rebalance_bars=24),
        'strength_gate_v20_liq100': Config(strategy='cross_asset', rank_model='trend_budget', target_volatility=.20, max_position=.2, max_exposure=.8, rank_liquidity_top_n=100, rank_min_trend_strength=.5, rebalance_band=.01, rebalance_bars=24),
        'strong_gate_v20_liq100': Config(strategy='cross_asset', rank_model='trend_budget', target_volatility=.20, max_position=.2, max_exposure=.8, rank_liquidity_top_n=100, rank_min_trend_strength=.75, rebalance_band=.01, rebalance_bars=24),
        'momentum_top20_v20': Config(strategy='cross_asset', rank_model='momentum', target_volatility=.20, max_position=.2, max_exposure=.8, top_n=20, rank_liquidity_top_n=100, rebalance_band=.01, rebalance_bars=24),
        'strength_gate_v20_liq50': Config(strategy='cross_asset', rank_model='trend_budget', target_volatility=.20, max_position=.2, max_exposure=.8, rank_liquidity_top_n=50, rank_min_trend_strength=.5, rebalance_band=.01, rebalance_bars=24),
        'strength_gate_v15_liq25': Config(strategy='cross_asset', rank_model='trend_budget', target_volatility=.15, max_position=.2, max_exposure=.8, rank_liquidity_top_n=25, rank_min_trend_strength=.5, rebalance_band=.01, rebalance_bars=24),
        'momentum_top5_v15': Config(strategy='cross_asset', rank_model='momentum', target_volatility=.15, max_position=.2, max_exposure=.8, top_n=5, rank_liquidity_top_n=50, rebalance_band=.02, rebalance_bars=24),
    }
    results = []
    for name, c in candidates.items():
        c.validate(); record = {'name': name, 'config': c.__dict__, 'blocks': {}}
        for block, start, end in blocks:
            if end - start < 100: continue
            base = replay(bars, c, manifest, rules, features, start, end)['metrics']
            stress = replay(bars, replace(c, fee_bps=20, spread_bps=10, slippage_bps=10), manifest, rules, features, start, end)['metrics']
            record['blocks'][block] = {'base': metrics(base), 'stress': metrics(stress)}
            print(json.dumps({'candidate': name, 'block': block, 'return': base['total_return'], 'stress': stress['total_return']}), flush=True)
        vals = [x['base']['total_return'] for x in record['blocks'].values()]; dds = [x['base']['max_drawdown'] for x in record['blocks'].values()]; sharpes = [x['base']['sharpe'] for x in record['blocks'].values()]
        stress_vals = [x['stress']['total_return'] for x in record['blocks'].values()]
        record['summary'] = {'mean_return': sum(vals)/len(vals), 'median_return': sorted(vals)[len(vals)//2], 'mean_stress_return': sum(stress_vals)/len(stress_vals), 'worst_return': min(vals), 'mean_max_drawdown': sum(dds)/len(dds), 'mean_sharpe': sum(sharpes)/len(sharpes), 'mean_sortino': sum(x['base']['sortino'] for x in record['blocks'].values())/len(vals), 'mean_calmar': sum(x['base']['calmar'] for x in record['blocks'].values())/len(vals), 'mean_stress_sortino': sum(x['stress']['sortino'] for x in record['blocks'].values())/len(vals), 'mean_stress_calmar': sum(x['stress']['calmar'] for x in record['blocks'].values())/len(vals), 'positive_blocks': sum(v > 0 for v in vals), 'blocks': len(vals)}
        results.append(record)
    out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
    (out/'results.json').write_text(json.dumps({'data': a.data, 'manifest': manifest, 'asset_count': pairs, 'timestamp_count': n, 'blocks': blocks, 'results': results,
        'selection_rule': 'Choose on b1-b4 stability and stress; tail is reported separately and excluded from selection.',
        'warnings': ['Binance USDT is mapped to USD and does not represent historical Roostoo execution.', 'Current volume/listing screen has survivorship bias.', 'Generic rules are used for Binance symbols missing from the Roostoo exchange snapshot.', 'No candidate is a guarantee of future return.']}, indent=2, allow_nan=False))
    print(json.dumps({'output': str(out/'results.json'), 'assets': pairs, 'timestamps': n}, indent=2))


if __name__ == '__main__': main()
