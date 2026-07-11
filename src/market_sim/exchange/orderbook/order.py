from dataclasses import dataclass
from market_sim.core.models import Side, OrderType


@dataclass
class Order:
    order_id: str
    side: Side
    order_type: OrderType
    quantity: float
    timestamp: float
    price: float | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(f"quantity must be > 0, got {self.quantity}")
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("limit order requires a price")
        if self.price is not None and self.price <= 0:
            raise ValueError(f"price must be > 0, got {self.price}")