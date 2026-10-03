"""Roostoo transport. No mutation retries: ambiguous outcomes require reconciliation."""
import hashlib
import hmac
import json
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode

BASE_URL = 'https://mock-api.roostoo.com'


class APIError(RuntimeError):
    pass


def canonical(params):
    # Reference signs decoded key=value strings, including the literal '/' in pairs.
    if any(any(c in str(v) for c in '&=\r\n') for v in params.values()):
        raise ValueError('Unsupported parameter characters')
    return '&'.join(f'{k}={params[k]}' for k in sorted(params))


def signature(params, secret):
    return hmac.new(secret.encode(),canonical(params).encode(),hashlib.sha256).hexdigest()


class Client:
    def __init__(self, key='', secret='', timeout=20):
        self.key,self.secret,self.timeout=key,secret,timeout
        self.offset=0

    def request(self, method, endpoint, params=None, signed=False):
        payload=dict(params or {})
        headers={'User-Agent':'RoostooFlightDeck/0.1'}
        if signed:
            if not self.key or not self.secret:
                raise APIError('Set ROOSTOO_API_KEY and ROOSTOO_API_SECRET')
            payload['timestamp']=int(time.time()*1000+self.offset)
            headers.update({'RST-API-KEY':self.key,'MSG-SIGNATURE':signature(payload,self.secret)})
        body=canonical(payload)
        url=BASE_URL+endpoint
        if method=='GET':
            url += ('?'+urlencode(payload)) if payload else ''
            data=None
        else:
            data=body.encode()
            headers['Content-Type']='application/x-www-form-urlencoded'
        with urlopen(Request(url,data=data,headers=headers,method=method),timeout=self.timeout) as response:
            result=json.load(response)
        if result.get('Success') is False:
            raise APIError(result.get('ErrMsg','Roostoo request failed'))
        return result

    def sync_clock(self):
        before=time.time()*1000
        response=self.request('GET','/v3/serverTime')
        after=time.time()*1000
        self.offset=int(response['ServerTime'])-(before+after)/2
        return response

    def exchange_info(self):
        return self.request('GET','/v3/exchangeInfo')

    def ticker(self):
        return self.request('GET','/v3/ticker',{'timestamp':int(time.time()*1000+self.offset)})

    def balance(self):
        return self.request('GET','/v3/balance',signed=True)

    def short_positions(self):
        return self.request('GET','/v6/short_positions',signed=True)

    def orders(self, **filters):
        if 'order_id' in filters and len(filters)>1:
            raise ValueError('order_id cannot be combined with other filters')
        return self.request('POST','/v3/query_order',filters,signed=True)
