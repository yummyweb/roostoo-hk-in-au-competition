from pathlib import Path
import csv
import hashlib
import json
import platform


def save_run(result, directory):
    path=Path(directory)
    path.mkdir(parents=True,exist_ok=True)
    result['runtime']={'python':platform.python_version(),'engine':'0.1.0'}
    sources=sorted(Path(__file__).parent.glob('*.py'))
    result['runtime']['source_sha256']=hashlib.sha256(b''.join(p.read_bytes() for p in sources)).hexdigest()
    (path/'run.json').write_text(json.dumps(result,allow_nan=False,separators=(',',':')))
    for name,key in [('config','config'),('metrics','metrics'),('data_manifest','manifest'),('exchange_rules','exchange_rules')]:
        (path/f'{name}.json').write_text(json.dumps(result[key],indent=2,allow_nan=False))
    for name in ('trades','orders','signals'):
        (path/f'{name}.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in result[name]))
    with (path/'equity_curve.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=result['equity_curve'][0].keys()); w.writeheader(); w.writerows(result['equity_curve'])
    m=result['metrics']
    text=f"# {result['name']}\n\nSource: {result['manifest'].get('source','Unknown')}\n\n"
    text+='| Metric | Value |\n| --- | --- |\n'+''.join(f'| {k} | {v} |\n' for k,v in m.items())
    text+='\n## Execution assumptions\n\n'+''.join(f'- {w}\n' for w in result['warnings'])
    text+='\n## Configuration\n\n```json\n'+json.dumps(result['config'],indent=2)+'\n```\n'
    if 'model' in result:
        text+='\n## LSTM forecast evaluation\n\n'+json.dumps(result['model']['forecast_metrics'],indent=2)+'\n'
        text+='\nCost-stress return: '+str(result['model']['cost_stress_metrics']['total_return'])+'\n'
    if 'ranking_model' in result:
        model=result['ranking_model']
        text+='\n## Portfolio architecture\n\n'+model['architecture']+'\n\n'+model['target']+'\n\n'+model['method']+'\n'
        text+='\nCost-stress return: '+str(model['cost_stress_metrics']['total_return'])+'\n'
    (path/'report.md').write_text(text)
    return path/'run.json'
