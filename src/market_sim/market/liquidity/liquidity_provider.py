import itertools

import numpy as np

from market_sim.core.models import OrderType, Side
from market_sim.events import Event
from market_sim.exchange.orderbook import Order, OrderBook


class SyntheticLiquidityProvider:
    """
    Rests a two-sided quote (bid and ask, both `quantity` deep) around the
    current price into `book` on every MARKET_UPDATE, giving strategies'
    MARKET orders a counterparty to fill against. Promoted from
    notebooks/02_strategy_comparison.ipynb's inline glue so MonteCarloRunner
    can reuse the same behavior across N repeated runs. Inserts directly into
    OrderBook rather than through ExchangeGateway/ORDER_SUBMIT — same
    shortcut the notebook and test fixtures already use for seeding
    liquidity. See docs/decisions/ADR-007-liquidity-provider-placement.md.

    Deliberately non-adversarial: quotes a tight, symmetric spread tracking
    the fair price rather than reacting to order flow. See
    docs/research/01_strategy_comparison.md for the known win_rate-inflation
    consequence of this.

    liquidity_multiplier_path, if given, scales `quantity` on the i-th
    MARKET_UPDATE this instance has seen by path[i] (clamped to the path's
    last value once i exceeds its length) — the wiring
    ShockModel.liquidity_multiplier_path() feeds into for stress runs.
    """

    def __init__(
        self,
        book: OrderBook,
        spread_bps: float = 20.0,
        quantity: float = 1_000_000.0,
        liquidity_multiplier_path: np.ndarray | None = None,
    ) -> None:
        self._book = book
        self._spread_bps = spread_bps
        self._quantity = quantity
        self._liquidity_multiplier_path = liquidity_multiplier_path
        self._order_ids = itertools.count()
        self._step = 0

    def on_market_update(self, event: Event) -> None:
        price = event.data["price"]
        offset = price * self._spread_bps / 10_000
        quantity = self._quantity * self._current_multiplier()

        self._book.insert(
            Order(
                order_id=f"lp-bid-{next(self._order_ids)}",
                side=Side.BUY,
                order_type=OrderType.LIMIT,
                price=price - offset,
                quantity=quantity,
                timestamp=event.timestamp,
            )
        )
        self._book.insert(
            Order(
                order_id=f"lp-ask-{next(self._order_ids)}",
                side=Side.SELL,
                order_type=OrderType.LIMIT,
                price=price + offset,
                quantity=quantity,
                timestamp=event.timestamp,
            )
        )
        self._step += 1

    def _current_multiplier(self) -> float:
        if self._liquidity_multiplier_path is None:
            return 1.0
        idx = min(self._step, len(self._liquidity_multiplier_path) - 1)
        return float(self._liquidity_multiplier_path[idx])
