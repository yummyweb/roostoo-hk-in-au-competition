#!/usr/bin/env python3
"""Finite SHORT check on a GENERAL TEST account only, never competition keys.

Opens one 10 USD BTC/USD short at market, waits 61 seconds, closes the whole
position, and records how the exchange reports it. Every step is journaled and
fsynced; the intent is on disk before each POST and no POST is ever retried.
An interrupted/ambiguous canary is not re-run: reconcile it from the journal.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roostoo.api import APIError,Client

PAIR='BTC/USD'
COLLATERAL='10'  # sent verbatim: the signed string is collateral=10&pair=BTC/USD&timestamp=...
FLAG='--execute-general-short-canary'


def flat(balance):
    """{(wallet key, asset, field): number} for every numeric leaf of a /v3/balance answer."""
    out={}
    for key,wallet in (balance or {}).items():
        if not isinstance(wallet,dict):continue
        for asset,entry in wallet.items():
            if not isinstance(entry,dict):continue
            for field,value in entry.items():
                if isinstance(value,(int,float)) and not isinstance(value,bool):out[(key,asset,field)]=float(value)
    return out


def moves(before,after):
    """Every balance leaf that differs between two /v3/balance answers: {leaf: (before, after)}."""
    a,b=flat(before),flat(after)
    return {k:(a.get(k,0.),b.get(k,0.)) for k in sorted(set(a)|set(b)) if abs(b.get(k,0.)-a.get(k,0.))>1e-9}


def wallet_key(balance):
    return 'SpotWallet' if isinstance(balance.get('SpotWallet'),dict) else 'Wallet'


def collateral_location(before,after,collateral):
    """Where did the collateral go after the open? Returns (code, sentence).

    code is 'lock' (left Free and shows up in another USD field, normally Lock), 'removed'
    (left Free, shown nowhere in /v3/balance), 'lock_only' (a USD field rose, Free did not
    fall) or 'neither'. A move counts when it is at least half the collateral.
    """
    usd={'.'.join(k):b-a for k,(a,b) in moves(before,after).items() if k[1]=='USD'}
    freed=[f'{k} {d:+.6f}' for k,d in usd.items() if k.endswith('.Free') and -d>=collateral/2]
    held=[f'{k} {d:+.6f}' for k,d in usd.items() if d>=collateral/2]
    if freed and held:return 'lock',f'Collateral LEFT Free ({"; ".join(freed)}) and IS shown as held in {"; ".join(held)}.'
    if freed:return 'removed',f'Collateral LEFT Free ({"; ".join(freed)}) and is NOT shown as Lock anywhere in /v3/balance; it is visible only in /v6/short_positions.'
    if held:return 'lock_only',f'{"; ".join(held)} rose but USD Free did NOT fall by the collateral. Unexpected.'
    return 'neither','NEITHER: USD Free did not fall and no USD Lock rose by the collateral; /v3/balance does not reflect the short.'


def canary(client,output):
    path=Path(output)
    if path.exists():raise FileExistsError('Short canary journal already exists. Reconcile it; do not blindly retry orders.')
    path.parent.mkdir(parents=True,exist_ok=True)
    journal={'account_type':'GENERAL TEST','pair':PAIR,'collateral':COLLATERAL,'phase':'created','stop':None,'events':[]}

    def save(phase,**event):
        journal['phase']=phase
        if event:journal['events'].append(dict(event,timestamp=int(time.time()*1000)))
        tmp=path.with_suffix('.tmp')
        with open(tmp,'w') as handle:
            handle.write(json.dumps(journal,indent=2));handle.flush();os.fsync(handle.fileno())
        os.replace(tmp,path)
        folder=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(folder)
        finally:os.close(folder)

    def call(step,phase,send):
        """One request, journaled. Returns ('ok', response), ('rejected', ErrMsg) or ('error', text)."""
        try:response=send()
        except APIError as error:  # HTTP 200 with Success false: a definite refusal, nothing happened
            save(phase,step=step,rejected=str(error))
            print(f'{step}: REFUSED by the exchange: {error}',flush=True)
            return 'rejected',str(error)
        except Exception as error:  # timeout, HTTP error, unreadable answer: outcome unknown
            text=f'{type(error).__name__}: {error}'
            save(phase,step=step,error=text)
            print(f'{step}: NO USABLE ANSWER: {text}',flush=True)
            return 'error',text
        save(phase,step=step,response=response)
        print(f'{step}: {json.dumps(response)}',flush=True)
        return 'ok',response

    def stop(phase,message):
        journal['stop']=message;save(phase)
        return journal

    def positions():
        return client.request('GET','/v6/short_positions',signed=True)

    save('created')
    seen={}
    for step,send in (('sync_clock',client.sync_clock),('balance_before',client.balance),('positions_before',positions)):
        status,seen[step]=call(step,'preparing',send)
        if status!='ok':return stop('stopped_before_open',f'{step} failed ({seen[step]}). No order was sent. Fix the cause, then run again with a new --output file.')
    if seen['positions_before'].get('Positions'):
        return stop('stopped_before_open','The test account already holds an open short. A new open would merge into it and the close would close all of it. No order was sent. Use a test account with no open shorts.')
    free=flat(seen['balance_before']).get((wallet_key(seen['balance_before']),'USD','Free'))
    if free is None:return stop('stopped_before_open','Unknown balance schema: no USD Free under Wallet/SpotWallet. No order was sent.')
    if free<float(COLLATERAL)*1.01:return stop('stopped_before_open',f'Insufficient general-test cash: USD Free is {free}, need {COLLATERAL} plus the fee. No order was sent.')

    params={'pair':PAIR,'collateral':COLLATERAL}  # Client.request adds timestamp; nothing else may be sent
    save('open_submitting',step='open',intent={'method':'POST','endpoint':'/v6/short_open','params':params})
    status,opened=call('open','open_answered',lambda:client.request('POST','/v6/short_open',dict(params),signed=True))
    if status=='rejected':return stop('open_rejected',f'The exchange refused the short open: "{opened}". Nothing was opened, nothing to close.')
    if status=='error' or opened.get('Status')!='OPEN':
        return stop('open_needs_reconciliation','The short open did not confirm Status OPEN, so its outcome is unknown. It was NOT retried and no close was sent. Do NOT run this again: check the test account for an open BTC/USD short and send the journal to the engineer.')

    # From here a short is open. Failed reads are journaled but do not stop the close.
    call('balance_after_open','open_confirmed',client.balance)
    call('positions_after_open','open_confirmed',positions)
    print('General-test SHORT open confirmed. Waiting 61 seconds before the close.',flush=True)
    time.sleep(61)
    params={'pair':PAIR}  # no close_qty / close_pct: the exchange closes the whole position
    save('close_submitting',step='close',intent={'method':'POST','endpoint':'/v6/short_close','params':params})
    status,closed=call('close','close_answered',lambda:client.request('POST','/v6/short_close',dict(params),signed=True))
    if status=='rejected':return stop('close_rejected',f'The exchange refused the close: "{closed}". The short is probably still OPEN on the test account. It was NOT retried. Do NOT run this again; send the journal to the engineer.')
    if status=='error':return stop('close_needs_reconciliation','The close got no usable answer, so the short may or may not still be open. It was NOT retried. Do NOT run this again; check the test account and send the journal to the engineer.')
    call('balance_final','close_answered',client.balance)
    call('positions_final','close_answered',positions)
    if closed.get('FullyClosed') is not True:return stop('close_not_full','The close was accepted but FullyClosed is not true: part of the short may still be open on the test account.')
    save('complete')
    return journal


def summary(journal):
    """Plain-language lines the operator can paste to the engineer."""
    def found(step,kind='response'):
        return next((e[kind] for e in journal['events'] if e.get('step')==step and kind in e),None)
    def fields(response,names):
        return ', '.join(f'{n}={response[n]}' if n in response else f'{n}=absent (guide: read as 0)' for n in names)
    def usd(before,after):
        a,b=flat(before),flat(after)
        rows=[f'   {".".join(k)}: {a.get(k,0.):.6f} -> {b.get(k,0.):.6f} ({signed(b.get(k,0.)-a.get(k,0.))})' for k in sorted(set(a)|set(b)) if k[1]=='USD']
        other=[f'{".".join(k)} {x:.8f} -> {y:.8f}' for k,(x,y) in moves(before,after).items() if k[1]!='USD']
        return rows+[f'   Non-USD balance fields that changed: {"; ".join(other) if other else "none"}']
    def signed(x):
        return f'{round(x,6)+0.:+.6f}'  # +0. turns a rounded -0.0 into 0.0
    def unread(step):
        return f'   not available ({found(step,"rejected") or found(step,"error") or "step not reached"})'

    lines=['','==== SHORT CANARY SUMMARY (general TEST account, BTC/USD, collateral 10) ====',f'Result: {journal["phase"]}']
    if journal['stop']:lines.append(f'STOPPED: {journal["stop"]}')
    opened,closed=found('open'),found('close')
    start,after,final=found('balance_before'),found('balance_after_open'),found('balance_final')

    if opened:lines.append(f'1. OPEN accepted: {"yes" if opened.get("Status")=="OPEN" else "NOT CONFIRMED"}. {fields(opened,("Status","EntryPrice","ShortQty","Collateral","OpenFee","ID","OrderType"))}')
    elif found('open','rejected') is not None:lines.append(f'1. OPEN accepted: NO. The exchange answered ErrMsg="{found("open","rejected")}"')
    elif found('open','error') is not None:lines.append(f'1. OPEN accepted: UNKNOWN. {found("open","error")}')
    else:lines.append('1. OPEN was never sent.')

    lines.append('2. USD balance, before the open -> after the open:')
    if opened and start and after:
        lines+=usd(start,after)
        lines.append('   => '+collateral_location(start,after,float(opened.get('Collateral',COLLATERAL)))[1])
    else:lines.append(unread('balance_after_open'))

    lines.append('3. /v6/short_positions after the open:')
    listed=found('positions_after_open')
    if listed is None:lines.append(unread('positions_after_open'))
    else:
        rows=listed.get('Positions') or []
        lines.append(f'   top-level keys: {", ".join(listed)}; open positions: {len(rows)}')
        for row in rows:
            lines.append('   '+', '.join(f'{k}={v}' for k,v in row.items()))
            lines.append('   key fields: '+fields(row,('CurrentPrice','UnrealizedPNL','PositionValue')))

    if closed:lines.append(f'4. CLOSE answered. {fields(closed,("ClosePrice","RealizedPNL","CloseFee","ReturnAmount","FullyClosed","ClosedQty"))}')
    elif found('close','rejected') is not None:lines.append(f'4. CLOSE refused. The exchange answered ErrMsg="{found("close","rejected")}"')
    elif found('close','error') is not None:lines.append(f'4. CLOSE outcome UNKNOWN. {found("close","error")}')
    else:lines.append('4. CLOSE was never sent.')

    lines.append('5. USD balance, start -> end of the run:')
    if opened and closed and start and final:
        lines+=usd(start,final)
        expected=float(closed.get('RealizedPNL',0))-float(opened.get('OpenFee',0))-float(closed.get('CloseFee',0))
        leaf=(wallet_key(start),'USD','Free')
        actual=flat(final).get(leaf,0.)-flat(start).get(leaf,0.)
        lines.append(f'   Expected change in Free = RealizedPNL - OpenFee - CloseFee = {signed(expected)}; actual {".".join(leaf)} change = {signed(actual)}; unexplained = {signed(actual-expected)}')
        left=found('positions_final')
        lines.append('   Open shorts left at the end: '+('not read' if left is None else str(len(left.get('Positions') or []))))
    else:lines.append(unread('balance_final'))

    errors=[f'{e["step"]}: "{e["rejected"]}"' for e in journal['events'] if 'rejected' in e]
    errors+=[f'{e["step"]}: "{e["response"]["ErrMsg"]}"' for e in journal['events'] if isinstance(e.get('response'),dict) and e['response'].get('ErrMsg')]
    lines.append(f'6. ErrMsg from the exchange: {"; ".join(errors) if errors else "none"}')
    lines.append('The raw JSON of every answer is printed above and saved in the journal file.')
    return lines


def main(argv=None,environ=os.environ):
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument(FLAG,action='store_true');p.add_argument('--output',default='runs/canary/short-journal.json');args=p.parse_args(argv)
    if not args.execute_general_short_canary:
        print(f'Refusing to run: pass {FLAG} to confirm these are GENERAL TEST account keys. No request was sent.');return 2
    key,secret=environ.get('ROOSTOO_TEST_API_KEY',''),environ.get('ROOSTOO_TEST_API_SECRET','')
    if not key or not secret:
        print('Refusing to run: set ROOSTOO_TEST_API_KEY and ROOSTOO_TEST_API_SECRET (general TEST account only). No request was sent.');return 2
    try:journal=canary(Client(key,secret),args.output)
    except FileExistsError as error:
        print(f'Refusing to run: {error} No request was sent.');return 2
    print('\n'.join(summary(journal)))
    return 0 if journal['phase']=='complete' else 1


if __name__=='__main__':
    sys.exit(main())
