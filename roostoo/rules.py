from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass(frozen=True)
class PairRule:
    amount_precision: int = 6
    price_precision: int = 2
    minimum: float = 1.0
    can_trade: bool = True

    def quantity(self, value):
        if not self.can_trade:
            raise ValueError('Pair is not tradable')
        return float(Decimal(str(value)).quantize(Decimal(10) ** -self.amount_precision, rounding=ROUND_DOWN))

    def valid(self, quantity, price):
        return self.can_trade and quantity > 0 and Decimal(str(quantity))*Decimal(str(price)) > Decimal(str(self.minimum))


def load_rules(info, pairs):
    rules = {}
    for pair in pairs:
        if pair not in info.get('TradePairs', {}):
            raise ValueError(f'{pair} missing from exchange rules')
        r = info['TradePairs'][pair]
        rules[pair] = PairRule(int(r['AmountPrecision']),int(r['PricePrecision']),float(r['MiniOrder']),bool(r['CanTrade']))
        if not rules[pair].can_trade:
            raise ValueError(f'{pair} cannot trade')
    return rules
