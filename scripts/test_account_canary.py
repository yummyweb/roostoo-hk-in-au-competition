#!/usr/bin/env python3
"""Finite execution check on a GENERAL TEST account only, never competition keys.

Persists intent before each POST. An interrupted/ambiguous canary is not retried.
The small buy and sell are separated by >60 seconds, with no order retry.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roostoo.api import Client
from roostoo.rules import load_rules


def wallet(balance):
    result=balance.get('SpotWallet',balance.get('Wallet'))
    if not isinstance(result,dict):raise ValueError('Unknown balance schema')
    return result


def canary(client,output,budget=10.):
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('Canary journal already exists. Reconcile it; do not blindly retry orders.')
    journal={'account_type':'GENERAL TEST','budget':budget,'phase':'created','events':[]}
    def save(phase,event=None):
        journal['phase']=phase
        if event:journal['events'].append(event)
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(journal,indent=2));tmp.replace(path)
    client.sync_clock();info=client.exchange_info();rule=load_rules(info,['BTC/USD'])['BTC/USD']
    initial=wallet(client.balance());initial_qty=float(initial.get('BTC',{}).get('Free',0))
    if initial_qty>0:raise ValueError('Use an empty general test wallet to make this canary unambiguous')
    ask=float(client.ticker()['Data']['BTC/USD']['MinAsk']);quantity=rule.quantity(budget/ask)
    if not rule.valid(quantity,ask):raise ValueError('Canary budget below minimum')
    if float(initial.get('USD',{}).get('Free',0))<budget*1.01:raise ValueError('Insufficient general-test cash')
    save('buy_submitting',{'intent':{'pair':'BTC/USD','side':'BUY','type':'MARKET','quantity':quantity},'timestamp':int(time.time()*1000)})
    buy=client.request('POST','/v3/place_order',{'pair':'BTC/USD','side':'BUY','type':'MARKET','quantity':format(quantity,'.8f')},signed=True)
    if buy.get('OrderDetail',{}).get('Status')!='FILLED':
        save('buy_needs_reconciliation',{'response':buy});raise ValueError('Buy did not confirm FILLED; inspect journal')
    save('buy_filled',{'response':buy})
    print('General-test BUY confirmed. Waiting 61 seconds before the closing SELL.',flush=True)
    time.sleep(30)
    time.sleep(31)
    client.sync_clock();after_buy=wallet(client.balance())
    available=float(after_buy.get('BTC',{}).get('Free',0))
    quantity=rule.quantity(available-initial_qty)
    bid=float(client.ticker()['Data']['BTC/USD']['MaxBid'])
    if not rule.valid(quantity,bid):raise ValueError('Remaining quantity below minimum; reconcile the test wallet')
    save('sell_submitting',{'intent':{'pair':'BTC/USD','side':'SELL','type':'MARKET','quantity':quantity},'timestamp':int(time.time()*1000)})
    sell=client.request('POST','/v3/place_order',{'pair':'BTC/USD','side':'SELL','type':'MARKET','quantity':format(quantity,'.8f')},signed=True)
    save('sell_response',{'response':sell})
    if sell.get('OrderDetail',{}).get('Status')!='FILLED':raise ValueError('Sell did not confirm FILLED; reconcile journal')
    final=wallet(client.balance())
    save('complete',{'initial_wallet':initial,'final_wallet':final})
    print(json.dumps({'phase':'complete','buy_commission_coin':buy['OrderDetail'].get('CommissionCoin'),
                      'sell_commission_coin':sell['OrderDetail'].get('CommissionCoin'),
                      'buy_fee_rate':buy['OrderDetail'].get('CommissionPercent'),
                      'sell_fee_rate':sell['OrderDetail'].get('CommissionPercent'),
                      'residual_BTC':final.get('BTC',{}).get('Free',0)}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute-general-canary',action='store_true',required=True);p.add_argument('--output',default='runs/canary/journal.json');args=p.parse_args()
    canary(Client(os.environ.get('ROOSTOO_TEST_API_KEY',''),os.environ.get('ROOSTOO_TEST_API_SECRET','')),args.output)
