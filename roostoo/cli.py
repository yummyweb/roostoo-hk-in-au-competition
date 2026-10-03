import argparse
from dataclasses import fields
import json
import os
from pathlib import Path
import sys
import time
from .data import synthetic,read_csv,write_csv
from .engine import run
from .strategy import Config
from .rules import load_rules
from .report import save_run

ROOT=Path(__file__).resolve().parents[1]


def get_rules(bars):
    return load_rules(json.loads((ROOT/'config/exchange_info.json').read_text()),sorted({b.pair for b in bars}))


def main():
    parser=argparse.ArgumentParser(description='Roostoo Flight Deck research tools')
    sub=parser.add_subparsers(dest='command',required=True)
    d=sub.add_parser('demo'); d.add_argument('--output',default=str(ROOT/'runs/demo')); d.add_argument('--seed',type=int,default=27)
    b=sub.add_parser('backtest'); b.add_argument('--data',required=True); b.add_argument('--output',required=True); b.add_argument('--config')
    l=sub.add_parser('lstm'); l.add_argument('--data',required=True); l.add_argument('--output',required=True); l.add_argument('--config'); l.add_argument('--epochs',type=int)
    r=sub.add_parser('research'); r.add_argument('--data',required=True); r.add_argument('--output',required=True)
    sub.add_parser('bridge')
    collect=sub.add_parser('collect'); collect.add_argument('--output',required=True); collect.add_argument('--samples',type=int,default=60); collect.add_argument('--interval',type=int,default=60)
    sub.add_parser('check-account')
    args=parser.parse_args()
    if args.command=='bridge':
        payload=json.load(sys.stdin)
        settings=payload.get('config',{})
        if settings.get('strategy')=='cross_asset':
            preset=json.loads((ROOT/'config/ranking_candidate.json').read_text())
            settings=dict(preset,**settings)
        c=Config(**settings); c.validate()
        if payload.get('data_path'):
            bars,manifest=read_csv(payload['data_path'])
        else:
            bars,manifest=synthetic(seed=int(payload.get('seed',27)))
        result=run(bars,c,manifest,get_rules(bars))
        if payload.get('output'):
            save_run(result,payload['output'])
        print(json.dumps(result,allow_nan=False,separators=(',',':')))
    elif args.command in ('demo','backtest','research','lstm'):
        if args.command=='demo':
            bars,manifest=synthetic(seed=args.seed)
            write_csv(ROOT/'data/demo.csv',bars,manifest)
            config=Config(allow_short=True)
        else:
            bars,manifest=read_csv(args.data)
            config=Config(**json.loads(Path(args.config).read_text())) if getattr(args,'config',None) else Config()
        rules=get_rules(bars)
        if args.command=='lstm':
            from dataclasses import replace
            from .lstm import run_lstm
            config=replace(config,strategy='lstm_prediction',lstm_epochs=args.epochs or config.lstm_epochs)
            result=run_lstm(bars,config,manifest,rules,args.output)
        elif args.command=='research':
            from .research import evaluate
            summary,result=evaluate(bars,manifest,rules)
            Path(args.output).mkdir(parents=True,exist_ok=True)
            (Path(args.output)/'research.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
        else:
            result=run(bars,config,manifest,rules)
        path=save_run(result,args.output)
        print(json.dumps({'path':str(path),'metrics':result['metrics']},indent=2))
    else:
        from .api import Client
        client=Client(os.environ.get('ROOSTOO_API_KEY',''),os.environ.get('ROOSTOO_API_SECRET',''))
        client.sync_clock()
        if args.command=='check-account':
            balance=client.balance()
            print(json.dumps({'success':True,'wallet_assets':list(balance.get('SpotWallet',balance.get('Wallet',{}))),'short_positions':len(client.short_positions()['Positions'])}))
        else:
            if args.interval<60 or args.samples<1:
                raise ValueError('Collection interval must be >= 60 seconds, samples >= 1')
            path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True)
            path.with_suffix('.exchange.json').write_text(json.dumps(client.exchange_info(),indent=2))
            with path.open('a') as f:
                for i in range(args.samples):
                    record={'received_at_ms':int(time.time()*1000)}
                    try:
                        record['server_clock']=client.sync_clock()
                        record['raw_response']=client.ticker()
                    except Exception as e:
                        record['error']=str(e)
                    f.write(json.dumps(record)+'\n'); f.flush()
                    if i<args.samples-1: time.sleep(args.interval)


if __name__=='__main__':
    try:
        main()
    except (ValueError,KeyError,OSError,RuntimeError) as exc:
        print(f'Error: {exc}',file=sys.stderr)
        raise SystemExit(1)
