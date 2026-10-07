"""Score frozen candidates on a named panel and row range. Usage: python exam.py <panel> <start> [end]"""
import importlib.util, sys, time
import numpy as np
import harness as h, evalkit, baselines

CANDIDATES = [
    ('cash', None),
    ('breakout v2 (8%/24h, 72h high, 6% trail)', 'BASE'),
    ('breakout LIVE: 8%/12h, 120h high, 4ATR', 'work/breakout_params/candidate_live.py'),
    ('breakout tuned: 10%/12h, 120h high, 4ATR', 'work/breakout_params/candidate_1.py'),
    ('breakout tuned, 6% trail kept', 'work/breakout_params/candidate_2.py'),
    ('breakout tuned, 6 slots', 'work/breakout_params/candidate_3.py'),
    ('breakout v2 + BTC>EMA480 gate', 'work/shorts_direction/candidate_1.py'),
    ('gated breakout + 33% BTC short hedge', 'work/shorts_direction/candidate_2.py'),
    ('gated breakout + EMA shorts in bad mkt', 'work/shorts_direction/candidate_3.py'),
    ('EMA 48/200 L+S, 6ATR, 1% risk sizing', 'work/ema_risk/candidate_1.py'),
    ('EMA 48/200 L+S, 6ATR, full slots', 'work/ema_risk/candidate_2.py'),
    ('EMA 48/200 short only, risk sized', 'work/ema_risk/candidate_3.py'),
    ('EMA 24/200 L+S, 6ATR', 'work/ema_windows/candidate_1.py'),
    ('EMA 24/200 short only, 6ATR', 'work/ema_windows/candidate_2.py'),
    ('EMA 24/200 long only, 4ATR', 'work/ema_windows/candidate_3.py'),
    ('KMeans trend gate + EMA 24/100 long', 'work/regime_trendchop/candidate_1.py'),
    ('gap threshold + EMA 24/100 long', 'work/regime_trendchop/candidate_2.py'),
    ('HMM low-vol gate + EMA 24/100 long', 'work/regime_paper/candidate_1.py'),
    ('z-score 168h z<=-2.5 long (least bad)', 'work/z_risk/candidate_1.py'),
    ('z-score 168h z<=-3.0 long, 10 slots', 'work/z_risk/candidate_2.py'),
    ('z-score 72h z<=-3 long, BTC-gated', 'work/z_windows/candidate_1.py'),
    ('z-score 240h z<=-3.5 long', 'work/z_windows/candidate_2.py'),
    ('MIX balanced: breakout + EMA L/S risk', 'work/integrate_competition_fit/candidate_1.py'),
    ('MIX aggressive: breakout + EMA L/S', 'work/integrate_competition_fit/candidate_2.py'),
    ('TEAM SPEC faithful: KMeans->EMA or z', 'work/integrate_team_spec/candidate_1.py'),
    ('TEAM SPEC B: EMA + z-score, no switch', 'work/integrate_team_spec/candidate_2.py'),
    ('MIX sleeves: gated brk 67 + EMA L/S 67', 'work/integrate_evidence_first/candidate_1.py'),
    ('tuned breakout + BTC gate (long only)', 'work/integrate_evidence_first/candidate_2.py'),
]


def load(path):
    if path == 'BASE': return lambda p: baselines.Breakout(p)
    folder = str((h.LAB / path).parent)
    if folder not in sys.path: sys.path.insert(0, folder)
    spec = importlib.util.spec_from_file_location('cand_' + path.replace('/', '_').replace('.', '_'), h.LAB / path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod.make


def score(make, P, start, end, fresh=True):
    r = h.backtest(P, make(P), start=start, end=end); s = r.summary(); w = r.windows(11)
    rs = h.backtest(P, make(P), evalkit.STRESS, start, end).summary()
    out = dict(total=s['total_return'], mdd=s['max_drawdown'], sharpe=s['sharpe'], sortino=s['sortino'], calmar=s['calmar'],
               w_mean=w.get('mean', float('nan')), w_med=w.get('median', float('nan')), w_win=w.get('win', float('nan')),
               stress=rs['total_return'], trades=s['trades'], active=s['active_day_share'])
    if fresh:
        f = h.fresh_windows(P, make, days=11, step_days=3, start=start, end=end)
        out.update(f_mean=f['mean'], f_med=f['median'], f_win=f['win'], f_worst=f['worst'], f_best=f['best'], f_mdd=f['mdd_mean'], f_ge10=f['p_ge_10'], f_lem5=f['p_le_m5'])
    return out


if __name__ == '__main__':
    name = sys.argv[1]; start = int(sys.argv[2]); P = h.load(name); end = int(sys.argv[3]) if len(sys.argv) > 3 else P.T
    only = sys.argv[4].split(',') if len(sys.argv) > 4 and sys.argv[4] else None
    skip = sys.argv[5].split(',') if len(sys.argv) > 5 else []
    print(f'panel {name}, rows {start}..{end} ({(end - start) / 24:.0f} days); equal-weight coin return {np.mean(P.C[end - 1] / P.C[start] - 1):+.1%}, BTC {P.C[end - 1, P.i("BTC/USD")] / P.C[start, P.i("BTC/USD")] - 1:+.1%}')
    print(f"{'candidate':42} {'total':>7} {'mdd':>6} {'stress':>7} | {'Shrp':>5} {'Sort':>5} {'Calm':>6} | fresh 11d: {'mean':>6} {'med':>6} {'win':>4} {'worst':>6} {'best':>6} {'>=10%':>5} {'<=-5%':>5} {'mdd':>5} | trades active")
    for label, path in CANDIDATES:
        if (only and not any(k in label for k in only)) or any(k in label for k in skip): continue
        if path is None:
            print(f"{label:42} {0:+7.1%} {0:6.1%} {0:+7.1%}"); continue
        t0 = time.time()
        try:
            o = score(load(path), P, start, end)
        except Exception as e:
            print(f'{label:42} FAILED {type(e).__name__}: {str(e)[:90]}'); continue
        print(f"{label:42} {o['total']:+7.1%} {o['mdd']:6.1%} {o['stress']:+7.1%} | {o['sharpe']:5.2f} {o['sortino']:5.2f} {o['calmar']:6.2f} | "
              f"           {o['f_mean']:+6.2%} {o['f_med']:+6.2%} {o['f_win']:4.0%} {o['f_worst']:+6.1%} {o['f_best']:+6.1%} {o['f_ge10']:5.0%} {o['f_lem5']:5.0%} {o['f_mdd']:5.1%} | {o['trades']:5d} {o['active']:5.0%}  ({time.time() - t0:.0f}s)", flush=True)
