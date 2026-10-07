import contextlib
import hashlib
import hmac
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from roostoo.api import APIError,Client

# The script lives in scripts/ (not a package) and shares this file's name, so load it by path.
spec=importlib.util.spec_from_file_location('short_canary_script',Path(__file__).resolve().parents[1]/'scripts'/'test_short_canary.py')
script=importlib.util.module_from_spec(spec);spec.loader.exec_module(script)

OPENED={'Success':True,'ID':412,'Pair':'BTC/USD','OrderType':'MARKET','EntryPrice':50000,'ShortQty':0.0002,'Collateral':10,'OpenFee':0.01,'Status':'OPEN','CreateTimestamp':1757980800000}
CLOSED={'Success':True,'ClosePrice':50000,'RealizedPNL':0,'CloseFee':0.01,'ReturnAmount':9.99,'ClosedQty':0.0002,'FullyClosed':True}
POSITION={'ID':412,'Pair':'BTC/USD','EntryPrice':50000,'ShortQty':0.0002,'Collateral':10,'CurrentPrice':50010,'UnrealizedPNL':-0.002,'UnrealizedPNLPct':-0.0002,'PositionValue':9.998,'CreateTimestamp':1757980800000,'PositionStatus':'OPEN'}
NONE_OPEN={'Success':True,'Positions':[]}
ONE_OPEN={'Success':True,'Positions':[POSITION]}
GET_POSITIONS=('GET','/v6/short_positions',None,True)
POST_OPEN=('POST','/v6/short_open',{'pair':'BTC/USD','collateral':'10'},True)
POST_CLOSE=('POST','/v6/short_close',{'pair':'BTC/USD'},True)


def balance(free,lock=0.,key='Wallet'):
    return {'Success':True,'ErrMsg':'',key:{'BTC':{'Free':0,'Lock':0},'USD':{'Free':free,'Lock':lock}}}


LOCK_SCHEMA=[balance(50000),balance(49989.99,10),balance(49999.98)]      # collateral moves Free -> Lock
REMOVED_SCHEMA=[balance(50000),balance(49989.99),balance(49999.98)]      # collateral just leaves Free


class FakeClient:
    """Stands in for roostoo.api.Client: records every call in order and never touches the network."""
    def __init__(self,balances=LOCK_SCHEMA,positions=(NONE_OPEN,ONE_OPEN,NONE_OPEN),opened=OPENED,closed=CLOSED,journal=None):
        self.log=[];self.balances=iter(balances);self.positions=iter(positions)
        self.answers={'/v6/short_open':opened,'/v6/short_close':closed};self.journal=journal;self.on_disk={}

    def answer(self,value):
        if isinstance(value,Exception):raise value
        return value

    def sync_clock(self):
        self.log.append('sync_clock');return {'Success':True,'ServerTime':1757980800000}

    def balance(self):
        self.log.append('balance');return self.answer(next(self.balances))

    def request(self,method,endpoint,params=None,signed=False):
        self.log.append((method,endpoint,params,signed))
        if method=='POST' and self.journal:self.on_disk[endpoint]=json.loads(Path(self.journal).read_text())
        if endpoint=='/v6/short_positions':return self.answer(next(self.positions))
        return self.answer(self.answers[endpoint])


class ShortCanaryTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.path=Path(folder.name)/'canary'/'short-journal.json'
        sleeper=patch.object(script.time,'sleep');self.sleep=sleeper.start();self.addCleanup(sleeper.stop)

    def run_canary(self,client):
        self.sleep.side_effect=lambda seconds:client.log.append(('sleep',seconds))
        self.out=io.StringIO()
        with contextlib.redirect_stdout(self.out):journal=script.canary(client,self.path)
        self.assertEqual(json.loads(self.path.read_text()),journal)  # what is on disk is what was returned
        return journal

    def run_main(self,argv,environ):
        self.out=io.StringIO()
        with patch.object(script,'Client') as factory,patch.object(script,'canary') as canary,contextlib.redirect_stdout(self.out):
            canary.return_value={'phase':'complete','stop':None,'events':[]}
            code=script.main(argv,environ)
        return code,factory,canary

    # --- refusals -------------------------------------------------------------------------------
    def test_refuses_without_the_execute_flag(self):
        code,factory,canary=self.run_main(['--output',str(self.path)],{'ROOSTOO_TEST_API_KEY':'k','ROOSTOO_TEST_API_SECRET':'s'})
        self.assertEqual(code,2);self.assertFalse(factory.called);self.assertFalse(canary.called)
        self.assertIn('Refusing',self.out.getvalue());self.assertFalse(self.path.exists())

    def test_an_abbreviated_flag_is_not_accepted(self):
        with self.assertRaises(SystemExit),contextlib.redirect_stderr(io.StringIO()):
            self.run_main(['--exec','--output',str(self.path)],{'ROOSTOO_TEST_API_KEY':'k','ROOSTOO_TEST_API_SECRET':'s'})
        self.assertFalse(self.path.exists())

    def test_refuses_without_test_keys_and_ignores_competition_keys(self):
        live={'ROOSTOO_API_KEY':'live-key','ROOSTOO_API_SECRET':'live-secret'}
        for environ in (live,dict(live,ROOSTOO_TEST_API_KEY='k'),dict(live,ROOSTOO_TEST_API_SECRET='s')):
            code,factory,canary=self.run_main([script.FLAG,'--output',str(self.path)],environ)
            self.assertEqual(code,2);self.assertFalse(factory.called);self.assertFalse(canary.called)
            self.assertIn('ROOSTOO_TEST_API_KEY',self.out.getvalue());self.assertNotIn('live-',self.out.getvalue())

    def test_main_builds_the_client_from_the_test_keys_only(self):
        environ={'ROOSTOO_API_KEY':'live-key','ROOSTOO_API_SECRET':'live-secret','ROOSTOO_TEST_API_KEY':'test-key','ROOSTOO_TEST_API_SECRET':'test-secret'}
        code,factory,canary=self.run_main([script.FLAG,'--output',str(self.path)],environ)
        self.assertEqual(code,0);factory.assert_called_once_with('test-key','test-secret')
        canary.assert_called_once_with(factory.return_value,str(self.path))
        self.assertNotIn('test-key',self.out.getvalue());self.assertNotIn('test-secret',self.out.getvalue())

    def test_refuses_when_the_journal_already_exists(self):
        self.path.parent.mkdir(parents=True);self.path.write_text('{"phase": "open_needs_reconciliation"}')
        client=Mock()
        with self.assertRaisesRegex(FileExistsError,'already exists'):script.canary(client,self.path)
        self.assertEqual(client.mock_calls,[])
        self.assertEqual(self.path.read_text(),'{"phase": "open_needs_reconciliation"}')
        with patch.object(script,'Client'),contextlib.redirect_stdout(io.StringIO()) as out:
            code=script.main([script.FLAG,'--output',str(self.path)],{'ROOSTOO_TEST_API_KEY':'k','ROOSTOO_TEST_API_SECRET':'s'})
        self.assertEqual(code,2);self.assertIn('Refusing',out.getvalue())

    # --- the sequence ---------------------------------------------------------------------------
    def test_sends_exactly_the_documented_parameters_in_the_documented_order(self):
        client=FakeClient()
        journal=self.run_canary(client)
        self.assertEqual(client.log,['sync_clock','balance',GET_POSITIONS,POST_OPEN,'balance',GET_POSITIONS,('sleep',61),POST_CLOSE,'balance',GET_POSITIONS])
        self.assertEqual(journal['phase'],'complete');self.assertIsNone(journal['stop'])
        self.assertEqual([e['step'] for e in journal['events']],['sync_clock','balance_before','positions_before','open','open','balance_after_open','positions_after_open','close','close','balance_final','positions_final'])
        for raw in (OPENED,CLOSED,ONE_OPEN,LOCK_SCHEMA[1]):self.assertIn(json.dumps(raw),self.out.getvalue())  # raw JSON is printed

    def test_real_client_signs_and_sends_only_the_documented_parameters(self):
        # The real Client over a fake transport: proves what goes on the wire without any network.
        sent=[]
        answers={'/v3/serverTime':{'ServerTime':1757980800000},'/v3/balance':balance(50000),'/v6/short_positions':NONE_OPEN,'/v6/short_open':OPENED,'/v6/short_close':CLOSED}
        def transport(request,timeout=None):
            sent.append(request)
            return contextlib.closing(io.BytesIO(json.dumps(answers[request.full_url.split('?')[0].split('roostoo.com')[1]]).encode()))
        with patch('roostoo.api.urlopen',transport),patch('urllib.request.urlopen',transport),contextlib.redirect_stdout(io.StringIO()) as out:
            journal=script.canary(Client('test-key-value','test-secret-value'),self.path)
        self.assertEqual(journal['phase'],'complete')
        posts={r.full_url.split('roostoo.com')[1]:r for r in sent if r.get_method()=='POST'}
        self.assertEqual(list(posts),['/v6/short_open','/v6/short_close'])
        for endpoint,names in (('/v6/short_open',['collateral','pair','timestamp']),('/v6/short_close',['pair','timestamp'])):
            body=posts[endpoint].data.decode();pairs=dict(part.split('=') for part in body.split('&'))
            self.assertEqual(list(pairs),names)  # sorted, and nothing extra to break the server-side signature
            self.assertEqual(pairs['pair'],'BTC/USD');self.assertRegex(pairs['timestamp'],r'^\d{13}$')
            headers={k.lower():v for k,v in posts[endpoint].header_items()}
            self.assertEqual(headers['msg-signature'],hmac.new(b'test-secret-value',body.encode(),hashlib.sha256).hexdigest())
            self.assertEqual(headers['content-type'],'application/x-www-form-urlencoded')
        self.assertEqual(dict(p.split('=') for p in posts['/v6/short_open'].data.decode().split('&'))['collateral'],'10')
        listing=[r for r in sent if '/v6/short_positions' in r.full_url]
        self.assertEqual(len(listing),3)
        for r in listing:self.assertRegex(r.full_url,r'/v6/short_positions\?timestamp=\d{13}$')
        for text in (out.getvalue(),self.path.read_text(),'\n'.join(script.summary(journal))):
            self.assertNotIn('test-key-value',text);self.assertNotIn('test-secret-value',text)

    def test_journals_the_intent_before_each_post(self):
        client=FakeClient(journal=self.path)
        self.run_canary(client)
        at_open,at_close=client.on_disk['/v6/short_open'],client.on_disk['/v6/short_close']
        self.assertEqual(at_open['phase'],'open_submitting')
        self.assertEqual(at_open['events'][-1]['intent'],{'method':'POST','endpoint':'/v6/short_open','params':{'pair':'BTC/USD','collateral':'10'}})
        self.assertEqual(at_close['phase'],'close_submitting')
        self.assertEqual(at_close['events'][-1]['intent'],{'method':'POST','endpoint':'/v6/short_close','params':{'pair':'BTC/USD'}})
        self.assertEqual([e['response'] for e in at_close['events'] if e['step']=='open' and 'response' in e],[OPENED])  # raw answer saved after

    # --- failures -------------------------------------------------------------------------------
    def test_does_not_retry_after_an_exception_from_the_open(self):
        client=FakeClient(opened=TimeoutError('unknown outcome'))
        journal=self.run_canary(client)
        self.assertEqual(client.log,['sync_clock','balance',GET_POSITIONS,POST_OPEN])  # one POST, then nothing at all
        self.assertFalse(self.sleep.called)
        self.assertEqual(journal['phase'],'open_needs_reconciliation');self.assertIn('NOT retried',journal['stop'])
        self.assertEqual(journal['events'][-1]['error'],'TimeoutError: unknown outcome')
        text='\n'.join(script.summary(journal))
        self.assertIn('OPEN accepted: UNKNOWN',text);self.assertIn('STOPPED',text)
        with self.assertRaises(FileExistsError):script.canary(client,self.path)  # a second run is blocked
        self.assertEqual(len(client.log),4)

    def test_pending_or_unknown_open_status_is_not_followed_by_a_close(self):
        client=FakeClient(opened=dict(OPENED,Status='PENDING'))
        journal=self.run_canary(client)
        self.assertEqual(client.log[-1],POST_OPEN);self.assertEqual(journal['phase'],'open_needs_reconciliation')

    def test_stops_cleanly_when_the_exchange_answers_success_false(self):
        for message in ('this competition does not allow short positions','insufficient balance'):
            with self.subTest(message):
                self.path=self.path.with_name(message.replace(' ','-')+'.json')
                client=FakeClient(opened=APIError(message))
                journal=self.run_canary(client)
                self.assertEqual(client.log,['sync_clock','balance',GET_POSITIONS,POST_OPEN])
                self.assertEqual(journal['phase'],'open_rejected');self.assertIn(message,journal['stop'])
                self.assertEqual(journal['events'][-1]['rejected'],message)
                text='\n'.join(script.summary(journal))
                self.assertIn('OPEN accepted: NO',text);self.assertIn(f'ErrMsg="{message}"',text);self.assertIn(f'open: "{message}"',text)
                with patch.object(script,'Client'),patch.object(script,'canary',return_value=journal),contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(script.main([script.FLAG],{'ROOSTOO_TEST_API_KEY':'k','ROOSTOO_TEST_API_SECRET':'s'}),1)

    def test_rejected_close_is_journaled_and_not_retried(self):
        client=FakeClient(closed=APIError('no open short position for this pair'))
        journal=self.run_canary(client)
        self.assertEqual(client.log[-1],POST_CLOSE);self.assertEqual(client.log.count(POST_CLOSE),1)
        self.assertEqual(journal['phase'],'close_rejected');self.assertIn('no open short position for this pair',journal['stop'])

    def test_no_order_is_sent_when_the_account_is_not_clean_or_short_of_cash(self):
        cases={'already-short':FakeClient(positions=iter([ONE_OPEN])),'no-cash':FakeClient(balances=[balance(10.05)]),
               'shorts-disabled':FakeClient(positions=iter([APIError('this competition does not allow short positions')]))}
        for name,client in cases.items():
            with self.subTest(name):
                self.path=self.path.with_name(name+'.json')
                journal=self.run_canary(client)
                self.assertEqual(client.log,['sync_clock','balance',GET_POSITIONS])
                self.assertEqual(journal['phase'],'stopped_before_open');self.assertIn('No order was sent',journal['stop'])

    def test_a_failed_read_after_the_open_does_not_leave_the_short_open(self):
        client=FakeClient(balances=[balance(50000),TimeoutError('slow'),balance(49999.98)])
        journal=self.run_canary(client)
        self.assertEqual(client.log.count(POST_CLOSE),1);self.assertEqual(journal['phase'],'complete')
        self.assertIn('not available (TimeoutError: slow)','\n'.join(script.summary(journal)))

    # --- the summary ----------------------------------------------------------------------------
    def test_summary_when_collateral_moves_to_lock(self):
        text='\n'.join(script.summary(self.run_canary(FakeClient(balances=LOCK_SCHEMA))))
        self.assertEqual(script.collateral_location(LOCK_SCHEMA[0],LOCK_SCHEMA[1],10)[0],'lock')
        self.assertIn('Wallet.USD.Free: 50000.000000 -> 49989.990000 (-10.010000)',text)
        self.assertIn('Wallet.USD.Lock: 0.000000 -> 10.000000 (+10.000000)',text)
        self.assertIn('IS shown as held in Wallet.USD.Lock +10.000000',text)
        self.assertIn('OPEN accepted: yes. Status=OPEN, EntryPrice=50000, ShortQty=0.0002, Collateral=10, OpenFee=0.01',text)
        self.assertIn('key fields: CurrentPrice=50010, UnrealizedPNL=-0.002, PositionValue=9.998',text)
        self.assertIn('ClosePrice=50000, RealizedPNL=0, CloseFee=0.01, ReturnAmount=9.99, FullyClosed=True',text)
        self.assertIn('Wallet.USD.Free: 50000.000000 -> 49999.980000 (-0.020000)',text)
        self.assertIn('= -0.020000; actual Wallet.USD.Free change = -0.020000; unexplained = +0.000000',text)
        self.assertIn('ErrMsg from the exchange: none',text);self.assertIn('Open shorts left at the end: 0',text)

    def test_summary_when_collateral_is_simply_removed_from_free(self):
        text='\n'.join(script.summary(self.run_canary(FakeClient(balances=REMOVED_SCHEMA))))
        self.assertEqual(script.collateral_location(REMOVED_SCHEMA[0],REMOVED_SCHEMA[1],10)[0],'removed')
        self.assertIn('Wallet.USD.Free: 50000.000000 -> 49989.990000 (-10.010000)',text)
        self.assertIn('Wallet.USD.Lock: 0.000000 -> 0.000000 (+0.000000)',text)
        self.assertIn('is NOT shown as Lock anywhere in /v3/balance',text)

    def test_summary_names_the_wallet_key_and_reports_neither(self):
        other=[balance(50000,key='SpotWallet'),dict(balance(49989.99,key='SpotWallet'),ShortWallet={'USD':{'Free':0,'Lock':10}}),balance(50000.5,key='SpotWallet')]
        code,sentence=script.collateral_location(other[0],other[1],10)
        self.assertEqual(code,'lock');self.assertIn('ShortWallet.USD.Lock +10.000000',sentence);self.assertIn('SpotWallet.USD.Free -10.010000',sentence)
        self.assertEqual(script.collateral_location(balance(50000),balance(49999.99),10)[0],'neither')  # only the fee left
        self.assertEqual(script.collateral_location(balance(50000),balance(50000,10),10)[0],'lock_only')
        text='\n'.join(script.summary(self.run_canary(FakeClient(balances=other,closed=dict(CLOSED,RealizedPNL=0.52,ReturnAmount=10.51)))))
        self.assertIn('= +0.500000; actual SpotWallet.USD.Free change = +0.500000; unexplained = +0.000000',text)

    def test_missing_zero_fields_are_reported_as_absent_not_as_a_crash(self):
        opened={k:v for k,v in OPENED.items() if k!='OpenFee'};closed={k:v for k,v in CLOSED.items() if k!='RealizedPNL'}
        text='\n'.join(script.summary(self.run_canary(FakeClient(opened=opened,closed=closed))))
        self.assertIn('OpenFee=absent (guide: read as 0)',text);self.assertIn('RealizedPNL=absent (guide: read as 0)',text)

    def test_partial_close_is_flagged(self):
        journal=self.run_canary(FakeClient(closed={k:v for k,v in CLOSED.items() if k!='FullyClosed'},positions=(NONE_OPEN,ONE_OPEN,ONE_OPEN)))
        self.assertEqual(journal['phase'],'close_not_full')
        self.assertIn('Open shorts left at the end: 1','\n'.join(script.summary(journal)))


if __name__=='__main__':
    unittest.main()
