from dataclasses import dataclass

from market_sim.core.models import Side


@dataclass
class Position:
    """
    Net position in a single instrument, tracked via weighted-average cost
    basis (not FIFO/LIFO lot tracking — that's more precision than a
    backtesting engine needs, and Order/TRADE_EXECUTION don't carry an
    instrument field yet, so there is only ever one instrument to track per
    Portfolio today).
    """

    quantity: float = 0.0
    avg_price: float = 0.0

    def apply_fill(self, side: Side, price: float, quantity: float) -> float:
        """
        Apply a fill, updating quantity/avg_price. Returns the realized PnL
        produced by this fill: 0 if it only adds to or opens a position,
        nonzero for the portion that closes or flips an existing one.
        """
        signed_qty = quantity if side == Side.BUY else -quantity
        original_quantity = self.quantity

        same_direction = original_quantity == 0 or (original_quantity > 0) == (
            signed_qty > 0
        )
        if same_direction:
            new_quantity = original_quantity + signed_qty
            self.avg_price = (
                price
                if original_quantity == 0
                else (self.avg_price * abs(original_quantity) + price * abs(signed_qty))
                / abs(new_quantity)
            )
            self.quantity = new_quantity
            return 0.0

        closing_qty = min(abs(signed_qty), abs(original_quantity))
        direction = 1 if original_quantity > 0 else -1
        realized = closing_qty * (price - self.avg_price) * direction

        self.quantity = original_quantity + signed_qty
        if abs(signed_qty) > abs(original_quantity):
            self.avg_price = price  # flipped through flat into the opposite direction
        elif self.quantity == 0:
            self.avg_price = 0.0

        return realized
