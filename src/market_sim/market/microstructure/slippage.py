from dataclasses import dataclass

from market_sim.core.config import SlippageConfig
from market_sim.core.models import Side


@dataclass
class SlippageModel:
    """
    Linear price-impact model: slippage scales with the incoming order's size
    relative to the liquidity available on the side of the book it's crossing.
    An order equal in size to all resting liquidity moves the price by
    `coefficient` bps against the aggressor; smaller orders move it
    proportionally less, larger orders proportionally more (unbounded).
    """

    coefficient: float

    def bps(self, order_quantity: float, available_liquidity: float) -> float:
        if available_liquidity <= 0:
            return 0.0
        return self.coefficient * (order_quantity / available_liquidity)

    def apply(
        self,
        reference_price: float,
        order_quantity: float,
        available_liquidity: float,
        side: Side,
    ) -> float:
        adjustment = (
            reference_price * self.bps(order_quantity, available_liquidity) / 10_000.0
        )
        if side == Side.BUY:
            return reference_price + adjustment
        return reference_price - adjustment


def slippage_model_from_config(config: SlippageConfig) -> SlippageModel:
    return SlippageModel(coefficient=config.coefficient)
