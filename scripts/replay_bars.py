#!/usr/bin/env python3
"""Replay the regime runner on bars built from quotes over recorded candle closes (data/candles_<n>m).

    scripts/replay_bars.py [config] [days] [skip]   (default config/live_candidate.json, the last 6 days;
                                                     skip ends the window that many days before the newest candle)

This drives the real Runner in paper mode: one cycle per recorded candle (1-minute candles for a 1-minute preset,
5-minute candles otherwise), quotes built from that close and the config's spread, the same order throttle and
fees. Everything recorded before the window warms the indicators. It is a check of how often a preset trades and
what it pays in fees, not a forecast: fills are at the quoted price, exits are seen once per candle rather than
once a minute, and the regime model was fitted on these days.
"""
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch
import json
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from roostoo import bot
from roostoo.bot import Runner
from roostoo.regime_hmm import RegimeFilter
from roostoo.rules import load_rules
from roostoo.strategy import Config,Indicators

MINUTE=60000;WARM=1000


class Offline:
    offset=0
    def sync_clock(self):return {}


def replay(c,days=6.,skip=0.):
    """Run the runner over `days` of recorded candles ending `skip` days before the newest one.
    Returns (equity per cycle, closed trades, fees, orders, coins, positions still open, cycles per day)."""
    if c.bar_minutes==60:raise SystemExit('This replays presets whose bars are built from quotes')
    candle=1 if c.bar_minutes==1 else 5;step=candle*MINUTE;span=c.bar_minutes*MINUTE;per_day=1440//candle
    series={path.stem+'/USD':json.loads(path.read_text()) for path in sorted((ROOT/f'data/candles_{candle}m').glob('*.json'))}
    end=max(rows[-1][0] for rows in series.values() if rows);length=max(len(rows) for rows in series.values());drop=int(skip*per_day)
    series={pair:rows[:len(rows)-drop] for pair,rows in series.items() if len(rows)==length and rows[-1][0]==end}
    pairs=sorted(series);stamps=[row[0]+step for row in series[pairs[0]]];first=len(stamps)-int(days*per_day)   # close times
    rules=load_rules(json.loads((ROOT/'config/exchange_info.json').read_text()),pairs);half=c.spread_bps/20000
    events=[];trades=[];open_={};fees=0.;equity=[];orders=0
    with tempfile.TemporaryDirectory() as folder,patch.object(bot,'save_state',lambda path,state:None):
        r=Runner(c,Path(folder)/'state.json',Offline(),False);r.rules=rules;r.log=events.append
        r.series={pair:[Indicators(c),RegimeFilter(r.regime),None] for pair in pairs}
        for t in [t for t in range(first) if stamps[t]%span==0][-WARM:]:           # the bars that closed before the window
            for pair in pairs:r.feed(pair,stamps[t],series[pair][t][1])
            r.feature_hour=stamps[t]//span
        for t in range(first,len(stamps)):
            now=stamps[t];quotes={pair:{'bid':series[pair][t][1]*(1-half),'ask':series[pair][t][1]*(1+half)} for pair in pairs}
            r.read_quotes=lambda:(quotes,now);events.clear()
            with patch.object(bot.time,'time',return_value=now/1000):status=r.cycle()
            equity.append(status['equity'])
            intent=next((e for e in events if e['event']=='intent'),None);fill=next((e for e in events if e['event']=='paper_fill'),None)
            if not fill:continue
            pair=fill['pair'];price=fill['price'];kind=fill.get('side') or fill['kind'];orders+=1
            if kind in ('BUY','SHORT'):
                quantity=fill['quantity'] if kind=='BUY' else fill['collateral']/price
                open_[pair]=(1 if kind=='BUY' else -1,quantity,price,intent['reason'].split()[0],now);fees+=quantity*price*c.fee_bps/10000
            elif pair in open_:
                side,quantity,entry,leg,since=open_.pop(pair);cost=quantity*(entry+price)*c.fee_bps/10000;fees+=quantity*price*c.fee_bps/10000
                trades.append((leg,side,fill['reason'],side*quantity*(price-entry)-cost,quantity*entry,(now-since)/MINUTE))
    return equity,trades,fees,orders,len(pairs),len(open_),per_day


def main():
    c=Config(**json.loads(Path(sys.argv[1] if len(sys.argv)>1 else ROOT/'config/live_candidate.json').read_text()))
    days=float(sys.argv[2]) if len(sys.argv)>2 else 6.;skip=float(sys.argv[3]) if len(sys.argv)>3 else 0.
    equity,trades,fees,orders,coins,still,day=replay(c,days,skip)
    start=c.initial_cash;peak=start;drawdown=0.;span=len(equity)/day
    for value in equity:peak=max(peak,value);drawdown=max(drawdown,1-value/peak)
    print(f'{coins} coins, {span:.1f} days ending {skip:g} days before the newest candle: return {equity[-1]/start-1:+.2%}, worst drop {drawdown:.2%}, '
          f'fees {fees/start:.2%} of the account ({fees/start/span:.2%} a day), orders a day {orders/span:.0f}, '
          f'closed trades {len(trades)}, still open {still}')
    print('by day: '+'  '.join(f'{equity[min(len(equity)-1,(k+1)*day-1)]/(equity[k*day-1] if k else start)-1:+.2%}' for k in range((len(equity)+day-1)//day)))
    def table(title,key):
        print(title);groups=defaultdict(list)
        for trade in trades:groups[key(trade)].append(trade)
        for name,rows in sorted(groups.items(),key=lambda item:-len(item[1])):
            profit=[row[3] for row in rows]
            print(f"  {name:28} trades {len(rows):4}  won {sum(p>0 for p in profit)/len(rows):4.0%}  average {sum(profit)/len(rows):+8.2f} USD "
                  f"({sum(profit)/sum(row[4] for row in rows):+.2%} of the position)  total {sum(profit):+9.0f} USD  held {sum(row[5] for row in rows)/len(rows):5.0f} min")
    table('by exit reason:',lambda trade:trade[2])
    table('by leg and side:',lambda trade:f"{trade[0]} {'long' if trade[1]>0 else 'short'}")


if __name__=='__main__':main()
