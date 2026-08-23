from market_sim.core.models import EventType, OrderType, Side
from market_sim.events import Event


class OrderValidationError(ValueError):
    pass


def validate_order_submit(event: Event) -> None:
    if event.event_type != EventType.ORDER_SUBMIT:
        raise OrderValidationError(f"expected ORDER_SUBMIT, got {event.event_type}")

    data = event.data
    missing = [
        key for key in ("order_id", "side", "order_type", "quantity") if key not in data
    ]
    if missing:
        raise OrderValidationError(f"order_submit event missing fields: {missing}")

    if not isinstance(data["side"], Side):
        raise OrderValidationError(f"side must be a Side enum, got {data['side']!r}")
    if not isinstance(data["order_type"], OrderType):
        raise OrderValidationError(
            f"order_type must be an OrderType enum, got {data['order_type']!r}"
        )
    if data["order_type"] == OrderType.LIMIT and data.get("price") is None:
        raise OrderValidationError("limit order requires a price")


def validate_order_cancel(event: Event) -> None:
    if event.event_type != EventType.ORDER_CANCEL:
        raise OrderValidationError(f"expected ORDER_CANCEL, got {event.event_type}")
    if "order_id" not in event.data:
        raise OrderValidationError("order_cancel event missing 'order_id'")
