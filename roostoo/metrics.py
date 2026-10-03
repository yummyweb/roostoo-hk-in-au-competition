"""Ratios use UTC daily sampled returns; undefined ratios are null, never infinity."""
import math
import statistics

DAY = 86_400_000
YEAR = 365 * DAY


def summarize(curve, trades, orders, initial):
    equity = [x['equity'] for x in curve]
    daily = {}
    for row in curve:
        daily[row['timestamp']//DAY] = row['equity']
    daily_values = [initial] + list(daily.values())
    returns = [b/a-1 for a,b in zip(daily_values,daily_values[1:]) if a>0]
    mean = statistics.mean(returns) if returns else 0
    vol = statistics.stdev(returns) if len(returns)>1 else 0
    downside = math.sqrt(sum(min(0,r)**2 for r in returns)/len(returns)) if returns else 0
    duration = curve[-1]['timestamp']-curve[0]['timestamp'] if len(curve)>1 else 0
    total = equity[-1]/initial-1
    # At least 7 days required for annualized ratios; short samples remain unstable.
    annual = math.expm1(math.log1p(total)*YEAR/duration) if duration>=7*DAY and total>-1 and math.log1p(total)*YEAR/duration<700 else None
    sharpe = mean/vol*math.sqrt(365) if len(returns)>=7 and vol>1e-12 else None
    sortino = mean/downside*math.sqrt(365) if len(returns)>=7 and downside>1e-12 else None
    mdd = max(x['drawdown'] for x in curve)
    calmar = annual/mdd if annual is not None and mdd>1e-12 else None
    closed = [t for t in trades if t['status']=='CLOSED']
    wins = [t['net_pnl'] for t in closed if t['net_pnl']>0]
    losses = [t['net_pnl'] for t in closed if t['net_pnl']<0]
    fills = [o for o in orders if o['status']=='FILLED']
    fees = sum(o['fee'] for o in fills)
    return {'initial_equity':initial,'final_equity':equity[-1],'net_pnl':equity[-1]-initial,
            'total_return':total,'annualized_return':annual,'max_drawdown':mdd,
            'sharpe':sharpe,'sortino':sortino,'calmar':calmar,
            'composite_score':.4*sortino+.3*sharpe+.3*calmar if all(x is not None for x in (sharpe,sortino,calmar)) else None,
            'volatility':vol*math.sqrt(365),'downside_deviation':downside*math.sqrt(365),
            'closed_trades':len(closed),'open_trades':len(trades)-len(closed),'fills':len(fills),
            'win_rate':len(wins)/len(closed) if closed else None,
            'profit_factor':sum(wins)/abs(sum(losses)) if losses else None,
            'fees':fees,'slippage_cost':sum(o['slippage_cost'] for o in fills),
            'turnover':sum(o['quantity']*o['price'] for o in fills)/initial,
            'active_days':len(set(o['timestamp']//DAY for o in fills)),
            'average_exposure':statistics.mean(x['exposure'] for x in curve),
            'metric_basis':'UTC daily returns, 365 days/year, zero risk-free/target rate; partial first/last days included',
            'sample_days':len(returns)}
