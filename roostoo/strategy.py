"""Causal regime filter: price efficiency, EMA trend, momentum and ATR risk."""
from collections import deque
from dataclasses import dataclass, asdict
import math
import statistics


@dataclass(frozen=True)
class Config:
    strategy: str = 'trend'
    initial_cash: float = 100000.0
    fast: int = 16
    slow: int = 64
    momentum: int = 24
    risk_per_trade: float = .005
    max_position: float = .30
    max_exposure: float = .80
    stop_atr: float = 3.0
    max_drawdown: float = .08
    fee_bps: float = 10.0
    spread_bps: float = 4.0
    slippage_bps: float = 3.0
    allow_short: bool = False
    cooldown_bars: int = 6
    max_hold_bars: int = 96
    rebalance_bars: int = 24
    top_n: int = 3
    target_volatility: float = .35
    rebalance_band: float = .02

    lstm_sequence: int = 24
    lstm_horizon: int = 12
    lstm_hidden: int = 16
    lstm_epochs: int = 6
    lstm_seed: int = 42
    lstm_min_edge: float = .003
    rank_model: str = 'boosted_72'
    rank_liquidity_top_n: int = 50
    # For the diversified trend ensemble, require this fraction of the
    # 72/168/336/720-hour trend votes before allocating capital.
    rank_min_trend_strength: float = 0.0
    regime_min_move: float = .03
    regime_hold_bars: int = 168
    take_profit_pct: float = .06
    take_profit_trail: float = .025
    take_profit_fraction: float = .50
    # Gradual, non-latching de-risking: exposure scales linearly to zero as
    # equity falls this far below its rolling peak. 0 keeps the latching halt.
    drawdown_brake: float = 0.0
    brake_window_bars: int = 168

    def validate(self):
        if self.strategy not in ('trend','hybrid','rotation','pullback','reversion','allocation','lstm_prediction','cross_asset','buy_hold','cash'):
            raise ValueError('Unknown strategy')
        if self.rank_model not in ('momentum','ridge_72','boosted_24','boosted_72','trend_budget','regime_adaptive'):
            raise ValueError('Unknown cross-asset ranking model')
        if type(self.rank_liquidity_top_n) is not int or not 1 <= self.rank_liquidity_top_n <= 500:
            raise ValueError('Invalid liquidity universe size')
        if not 0 <= self.rank_min_trend_strength <= 1:
            raise ValueError('Trend-strength gate must be between 0 and 1')
        if not .01 <= self.regime_min_move <= .5:
            raise ValueError('Invalid regime move hurdle')
        if type(self.regime_hold_bars) is not int or not 0 <= self.regime_hold_bars <= 720:
            raise ValueError('Invalid regime holding period')
        if not 0 < self.take_profit_pct <= 1 or not 0 < self.take_profit_trail < 1 or not 0 <= self.take_profit_fraction <= 1:
            raise ValueError('Invalid trailing profit-taking configuration')
        if not 0 <= self.drawdown_brake < 1 or type(self.brake_window_bars) is not int or not 1 <= self.brake_window_bars <= 1000:
            raise ValueError('Invalid drawdown brake configuration')
        if not 2 <= self.fast < self.slow <= 1000 or not 2 <= self.momentum <= 1000:
            raise ValueError('Require 2 <= fast < slow <= 1000 and a valid momentum window')
        if any(not math.isfinite(v) for v in asdict(self).values() if isinstance(v, (float,int))):
            raise ValueError('Configuration must be finite')
        if any(type(v) is not int for v in (self.lstm_sequence,self.lstm_horizon,self.lstm_hidden,self.lstm_epochs,self.lstm_seed)) or self.lstm_seed < 0:
            raise ValueError('LSTM window sizes, epochs, and seed must be integers; seed must be nonnegative')
        if not 4 <= self.lstm_sequence <= 168 or not 1 <= self.lstm_horizon <= 168 or not 4 <= self.lstm_hidden <= 128 or not 1 <= self.lstm_epochs <= 50 or not 0 <= self.lstm_min_edge <= .1:
            raise ValueError('Invalid LSTM configuration')
        if self.initial_cash <= 0 or not 0 < self.risk_per_trade <= .05:
            raise ValueError('Initial cash must be positive; risk per trade must be in (0, 5%]')
        if not 0 < self.max_position <= self.max_exposure <= 1:
            raise ValueError('Position/exposure caps must satisfy 0 < position <= exposure <= 1')
        if not 0 < self.max_drawdown < 1 or self.stop_atr <= 0:
            raise ValueError('Invalid drawdown or ATR stop')
        if any(not 0 <= x <= 200 for x in (self.fee_bps,self.spread_bps,self.slippage_bps)):
            raise ValueError('Costs must be between 0 and 200 bps')
        if not 0 < self.target_volatility <= 2 or not 0 < self.rebalance_band < 1:
            raise ValueError('Invalid volatility target or rebalance band')
        if self.top_n < 1 or self.rebalance_bars < 1:
            raise ValueError('Rotation count and rebalance interval must be positive')
        if self.cooldown_bars < 0 or self.max_hold_bars < 1:
            raise ValueError('Invalid holding/cooldown period')


class Indicators:
    def __init__(self, config):
        self.c = config
        self.closes = deque(maxlen=max(config.slow,config.momentum,72)+2)
        self.ranges = deque(maxlen=14)
        self.fast = self.slow = None
        self.count = 0

    def update(self, bar):
        prev = self.closes[-1] if self.closes else bar.open
        self.ranges.append(max(bar.high-bar.low,abs(bar.high-prev),abs(bar.low-prev)))
        self.closes.append(bar.close)
        self.fast = bar.close if self.fast is None else self.fast + 2/(self.c.fast+1)*(bar.close-self.fast)
        self.slow = bar.close if self.slow is None else self.slow + 2/(self.c.slow+1)*(bar.close-self.slow)
        self.count += 1
        p = list(self.closes)
        atr = statistics.mean(self.ranges)
        changes = [b-a for a,b in zip(p[-21:],p[-20:])] if len(p)>=21 else [0]
        path = sum(abs(x) for x in changes)
        efficiency = abs(p[-1]-p[-21])/path if len(p)>=21 and path else 0
        recent = p[-20:]
        sigma = statistics.pstdev(recent)
        gains = sum(max(0,x) for x in changes[-14:])
        losses = sum(max(0,-x) for x in changes[-14:])
        rsi = 100*gains/(gains+losses) if gains+losses else 50
        momentum = p[-1]/p[-self.c.momentum-1]-1 if len(p)>self.c.momentum else 0
        return {'ready':self.count>=max(self.c.slow,self.c.momentum+1), 'fast':self.fast,'slow':self.slow,
                'atr':atr,'efficiency':efficiency,'rsi':rsi,'momentum':momentum,
                'zscore':(p[-1]-statistics.mean(recent))/sigma if sigma else 0,
                'mean':statistics.mean(recent), 'close':bar.close,
                'volatility':statistics.pstdev([math.log(b/a) for a,b in zip(p[-73:],p[-72:])]) if len(p)>=73 else atr/bar.close}


def entry(features, config):
    f = features
    if not f['ready'] or config.strategy == 'cash':
        return None
    if config.strategy == 'buy_hold':
        return ('LONG', 'Buy and hold baseline', 1.)
    friction = (2*config.fee_bps+config.spread_bps+2*config.slippage_bps)/10000
    if f['atr']/f['close'] > .06:
        return None
    if config.strategy == 'lstm_prediction':
        forecast=f.get('predicted_return')
        if forecast is None: return None
        threshold=f.get('forecast_entry_hurdle',friction+config.lstm_min_edge)
        reason=f'LSTM Prediction: {forecast:+.2%} forecast over {config.lstm_horizon}h; target ${f["predicted_price"]:,.2f}; entry hurdle {threshold:.2%}'
        if forecast > threshold: return ('LONG',reason,forecast/max(f['atr']/f['close'],.001))
        if config.allow_short and forecast < -threshold: return ('SHORT',reason,-forecast/max(f['atr']/f['close'],.001))
        return None
    strength = abs(f['fast']-f['slow'])/max(f['atr'],1e-12)
    if config.strategy == 'reversion':
        rebound=abs(f['mean']/f['close']-1)
        if rebound>friction*3 and f['efficiency']<.6:
            if f['zscore'] < -2 and f['rsi'] < 30:
                return ('LONG','Range: extreme oversold excursion with a cost-adjusted reversion target',abs(f['zscore']))
            if config.allow_short and f['zscore'] > 2 and f['rsi'] > 70:
                return ('SHORT','Range: extreme overbought excursion with a cost-adjusted reversion target',abs(f['zscore']))
        return None
    if config.strategy == 'pullback':
        if f['fast'] > f['slow'] and f['momentum'] > 0 and f['zscore'] < -1.5 and f['rsi'] < 40:
            return ('LONG','Range: oversold pullback within an established uptrend',abs(f['zscore']))
        return None
    if f['efficiency'] >= .25 and abs(f['momentum']) > friction*2 and strength > .5:
        if f['fast'] > f['slow'] and f['momentum'] > 0:
            return ('LONG','Trend: positive momentum, rising EMA, efficient price path',strength)
        if config.allow_short and f['fast'] < f['slow'] and f['momentum'] < 0:
            return ('SHORT','Trend: negative momentum, falling EMA, efficient price path',strength)
    if config.strategy == 'hybrid' and f['efficiency'] < .20 and f['zscore'] < -2 and f['rsi'] < 35:
        return ('LONG','Range: oversold below two-sigma band',abs(f['zscore']))
    return None


def exit_reason(position, f, bar, config, index):
    if config.strategy == 'buy_hold':
        return None
    long = position['side']=='LONG'
    # Close-observed synthetic stop. No claims about unobserved intrabar execution.
    if (long and bar.close <= position['stop']) or (not long and bar.close >= position['stop']):
        return 'Trailing ATR stop observed at candle close'
    if config.strategy == 'lstm_prediction':
        # This candle is already completed; the exit fills at the next open.
        if index-position['entry_index']+1 >= config.lstm_horizon:
            return 'LSTM Prediction: forecast holding horizon reached'
        forecast=f.get('predicted_return')
        if forecast is not None and ((long and forecast < -config.lstm_min_edge) or (not long and forecast > config.lstm_min_edge)):
            return 'LSTM Prediction: forecast changed direction'
        return None
    if config.strategy == 'rotation':
        return None  # Cross-sectional rank exits are handled by the portfolio engine.
    if index-position['entry_index'] >= config.max_hold_bars:
        return 'Maximum holding period'
    if position['regime']=='Range':
        if (long and bar.close >= f['mean']) or (not long and bar.close <= f['mean']) or f['efficiency'] > .65:
            return 'Mean reversion target or regime invalidation'
    elif (long and f['fast']<f['slow']) or (not long and f['fast']>f['slow']):
        return 'EMA trend reversal'
    return None


def rotation_targets(features, config):
    """Daily relative momentum, scaled by trailing volatility, with absolute trend filter."""
    candidates=[]
    for pair,f in features.items():
        if not f['ready']: continue
        friction=(2*config.fee_bps+config.spread_bps+2*config.slippage_bps)/10000
        score=f['momentum']/max(f['volatility'],.001)
        if f['momentum']>friction*2 and f['close']>f['slow']:
            candidates.append((pair,'LONG',score))
        elif config.allow_short and f['momentum']<-friction*2 and f['close']<f['slow']:
            candidates.append((pair,'SHORT',-score))
    candidates.sort(key=lambda x:(-x[2],x[0]))
    return {pair:(side,score) for pair,side,score in candidates[:config.top_n]}
