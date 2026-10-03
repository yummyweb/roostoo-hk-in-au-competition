#!/usr/bin/env python3
"""Four predefined architectures; selection only on two chronological validation blocks."""
from dataclasses import asdict,replace
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roostoo.data import read_csv
from roostoo.strategy import Config
from roostoo.cli import get_rules
from roostoo.report import save_run
from roostoo.ranking import MODEL_NAMES,market_features,fit_scores,execution_features,replay,validate_input


def episode_summary(rows):
    return dict(episodes=len(rows),mean_return=statistics.mean(r['total_return'] for r in rows),
        median_return=statistics.median(r['total_return'] for r in rows),worst_return=min(r['total_return'] for r in rows),
        profitable_fraction=sum(r['total_return']>0 for r in rows)/len(rows),
        eight_active_days_fraction=sum(r['active_days']>=8 for r in rows)/len(rows))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',default='data/binance-20-1h.csv')
    parser.add_argument('--output',default='runs/ranking-study')
    parser.add_argument('--risk-followup',action='store_true',help='Predefined lower-risk ridge/trend follow-up; exploratory after initial comparison')
    args=parser.parse_args();folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True)
    bars,manifest=read_csv(args.data);rules=get_rules(bars)
    base=Config(strategy='cross_asset',max_position=.2,top_n=5,target_volatility=.35,rebalance_bars=24,rebalance_band=.02)
    validate_input(bars,base,manifest)
    market=market_features(bars);n=len(market['timestamps']);a,b,z=int(n*.6),int(n*.7),int(n*.8)
    configs=[replace(base,rank_model=model) for model in ('momentum','ridge_72','boosted_24','boosted_72')]
    if args.risk_followup:
        configs=[replace(base,rank_model=model,target_volatility=vol,rank_liquidity_top_n=liq) for model in ('ridge_72','trend_budget') for vol in (.15,.25) for liq in ([50] if model=='ridge_72' else [15,25,50])]
    plan=dict(configs=[asdict(c) for c in configs],base_config=asdict(base),fit_end=a,validation_blocks=[[a,b],[b,z]],evaluation=[z,n],
        selection='Mean(validation return - 1.5 * validation max drawdown), across two fresh-wallet blocks; fixed list, no later-period selection',
        history='Exploratory; these later historical markets were already inspected during earlier research.',manifest=manifest)
    (folder/'experiment-plan.json').write_text(json.dumps(plan,indent=2))
    candidates=[]
    for c in configs:
        model=c.rank_model
        candidate_id=model+('_vol'+str(round(c.target_volatility*100))+'_liq'+str(c.rank_liquidity_top_n) if args.risk_followup else '')
        scores,metadata,fitted=fit_scores(market,model,a)
        features=execution_features(market,scores)
        metrics=[replay(bars,c,manifest,rules,features,left,right)['metrics'] for left,right in ((a,b),(b,z))]
        score=statistics.mean(m['total_return']-1.5*m['max_drawdown'] for m in metrics)
        record=dict(model=model,candidate_id=candidate_id,config=asdict(c),validation=metrics,selection_score=score,metadata=metadata)
        candidates.append(record)
        print('Validation',candidate_id,json.dumps(dict(score=score,returns=[m['total_return'] for m in metrics],drawdowns=[m['max_drawdown'] for m in metrics])),flush=True)
    selected=max(candidates,key=lambda r:r['selection_score'])
    # Persist choice before evaluating any candidate on the last 20%.
    selection=dict(plan=plan,candidates=candidates,selected_model=selected['model'],selected_id=selected['candidate_id'],selected_config=selected['config'])
    (folder/'selection.json').write_text(json.dumps(selection,indent=2))
    Path('config/ranking_candidate.json').write_text(json.dumps(selected['config'],indent=2))
    print('Frozen selection:',selected['candidate_id'],flush=True)
    later=[]
    for record in candidates:
        c=Config(**record['config']);candidate_id=record['candidate_id'];scores,metadata,fitted=fit_scores(market,c.rank_model,a)
        features=execution_features(market,scores)
        r=replay(bars,c,manifest,rules,features,z,metadata=metadata)
        stress=replay(bars,replace(c,fee_bps=20,spread_bps=10,slippage_bps=10),manifest,rules,features,z)
        r['ranking_model']['cost_stress_metrics']=stress['metrics']
        r['ranking_model']['selection_role']='Validation-selected candidate' if candidate_id==selected['candidate_id'] else 'Diagnostic comparator; not selected on later performance'
        save_run(r,folder/candidate_id)
        evaluation=dict(model=c.rank_model,candidate_id=candidate_id,metrics=r['metrics'],stress=stress['metrics'])
        later.append(evaluation)
        if candidate_id==selected['candidate_id']:
            # Fresh-wallet 14-day episodes, with the same frozen model/features/caps.
            episodes=[];stressed=[]
            for start in range(z,n-336+1,336):
                normal=replay(bars,c,manifest,rules,features,start,start+336)
                cost=replay(bars,replace(c,fee_bps=20,spread_bps=10,slippage_bps=10),manifest,rules,features,start,start+336)
                episodes.append(dict(start=normal['evaluation_start'],end=normal['evaluation_end'],metrics=normal['metrics']))
                stressed.append(cost['metrics'])
            evaluation['episodes']=episodes
            evaluation['episode_summary']=episode_summary([r['metrics'] for r in episodes])
            evaluation['stress_episode_summary']=episode_summary(stressed)
            metadata['config']=asdict(c)
            (folder/candidate_id/'ranking-model.json').write_text(json.dumps(metadata,indent=2))
            if fitted is not None:
                import joblib
                joblib.dump(fitted,folder/candidate_id/'ranking-model.joblib')
        print('Evaluation',candidate_id,json.dumps(dict(return_pct=r['metrics']['total_return']*100,drawdown_pct=r['metrics']['max_drawdown']*100,stress_pct=stress['metrics']['total_return']*100,exposure=r['metrics']['average_exposure'])),flush=True)
    selection.update(evaluation=later)
    original=Path('runs/lstm-prediction-20/run.json')
    if original.exists():
        lstm=json.loads(original.read_text())
        if lstm['manifest']['sha256']==manifest['sha256'] and lstm['evaluation_start']==int(market['timestamps'][z]):
            selection['lstm_reference']=dict(metrics=lstm['metrics'],stress=lstm['model']['cost_stress_metrics'],source_sha256=lstm['runtime']['source_sha256'])
    selection['cash_return']=0
    selection['source_sha256']=hashlib.sha256(b''.join(p.read_bytes() for p in sorted(Path('roostoo').glob('*.py')))).hexdigest()
    (folder/'study.json').write_text(json.dumps(selection,indent=2,allow_nan=False))
    print('Study saved:',folder/'study.json',flush=True)

if __name__=='__main__':main()
