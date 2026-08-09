import logging

from market_sim.core.clock import SimulationClock
from market_sim.core.engine.event_loop import EventLoop
from market_sim.core.engine.runtime_engine import RuntimeEngine
from market_sim.core.models import EventType
from market_sim.core.queue import EventQueue
from market_sim.events import Event
from market_sim.exchange.execution import TradeLog
from market_sim.exchange.matching import MatchingEngine
from market_sim.exchange.orderbook import Order, OrderBook
from market_sim.exchange.validation import (
    OrderValidationError,
    validate_order_cancel,
    validate_order_submit,
)
from market_sim.market.microstructure import SlippageModel

logger = logging.getLogger(__name__)


class ExchangeGateway:
    """
    Order intake and routing. Bridges ORDER_SUBMIT / ORDER_CANCEL events to the
    OrderBook + MatchingEngine, and re-enqueues resulting TRADE_EXECUTION events
    onto the EventQueue for downstream consumers (TradeLog, strategy on_fill).

    A malformed order (fails validation, or fails Order's own domain checks such
    as quantity <= 0) is rejected and dropped before it ever touches the book —
    it is recorded in `rejected_orders` and logged, not raised. This is
    intentional: one bad order from upstream (e.g. a strategy bug) must not
    crash an entire multi-day simulation run. Rejection happens strictly before
    any book mutation, so it cannot corrupt matching state or determinism for
    every other order. Everything past that boundary (MatchingEngine itself) is
    left to raise and crash loudly — those are real invariant violations, not
    recoverable bad input.
    """

    def __init__(
        self,
        book: OrderBook,
        matching_engine: MatchingEngine,
        queue: EventQueue,
        clock: SimulationClock,
        runtime: RuntimeEngine,
    ) -> None:
        self._book = book
        self._matching_engine = matching_engine
        self._queue = queue
        self._clock = clock
        self._runtime = runtime
        self.rejected_orders: list[Event] = []

    def register(self, loop: EventLoop) -> None:
        loop.register_handler(EventType.ORDER_SUBMIT, self.handle_order_submit)
        loop.register_handler(EventType.ORDER_CANCEL, self.handle_order_cancel)

    def handle_order_submit(self, event: Event) -> None:
        try:
            validate_order_submit(event)
            data = event.data
            order = Order(
                order_id=data["order_id"],
                side=data["side"],
                order_type=data["order_type"],
                quantity=data["quantity"],
                timestamp=event.timestamp,
                price=data.get("price"),
            )
        except (OrderValidationError, ValueError) as exc:
            self._reject(event, exc)
            return

        fills = self._matching_engine.match(
            incoming=order,
            book=self._book,
            timestamp=event.timestamp,
            sequence=self._clock.next_sequence(),
            trade_id=self._runtime.next_trade_id(),
        )

        for fill in fills:
            self._queue.push(fill)

    def handle_order_cancel(self, event: Event) -> None:
        try:
            validate_order_cancel(event)
        except OrderValidationError as exc:
            self._reject(event, exc)
            return

        self._book.cancel(event.data["order_id"])

    def _reject(self, event: Event, exc: Exception) -> None:
        self.rejected_orders.append(event)
        logger.warning(
            "rejected %s event %s: %s", event.event_type.name, event.event_id, exc
        )


def build_exchange(
    runtime: RuntimeEngine, slippage_model: SlippageModel | None = None
) -> tuple[OrderBook, TradeLog, ExchangeGateway]:
    """
    The single supported way to wire an exchange onto a RuntimeEngine: builds
    OrderBook + MatchingEngine + TradeLog + ExchangeGateway and registers all
    of their handlers (including TradeLog.record for TRADE_EXECUTION) on
    runtime.loop. Use this instead of wiring the pieces by hand so trades can
    never silently go unlogged.

    slippage_model is optional and defaults to None (no slippage applied,
    market orders fill at the resting order's exact price) so existing
    callers and tests are unaffected unless they opt in.
    """
    book = OrderBook()
    trade_log = TradeLog()
    gateway = ExchangeGateway(
        book=book,
        matching_engine=MatchingEngine(slippage_model=slippage_model),
        queue=runtime.queue,
        clock=runtime.clock,
        runtime=runtime,
    )
    gateway.register(runtime.loop)
    runtime.loop.register_handler(EventType.TRADE_EXECUTION, trade_log.record)

    return book, trade_log, gateway
