from market_sim.core.models import EventType, Side, OrderType
from .event import Event


def market_update(
    timestamp: float, sequence: int, price: float, instrument: str
) -> Event:
    return Event(
        event_type=EventType.MARKET_UPDATE,
        timestamp=timestamp,
        sequence=sequence,
        data={"price": price, "instrument": instrument},
    )


def order_submit(
    timestamp: float,
    sequence: int,
    order_id: str,
    side: Side,
    order_type: OrderType,
    quantity: float,
    price: float | None = None,
) -> Event:
    return Event(
        event_type=EventType.ORDER_SUBMIT,
        timestamp=timestamp,
        sequence=sequence,
        data={
            "order_id": order_id,
            "side": side,
            "order_type": order_type,
            "price": price,
            "quantity": quantity,
        },
    )


def order_cancel(timestamp: float, sequence: int, order_id: str) -> Event:
    return Event(
        event_type=EventType.ORDER_CANCEL,
        timestamp=timestamp,
        sequence=sequence,
        data={"order_id": order_id},
    )


def trade_execution(
    timestamp: float,
    sequence: int,
    trade_id: str,
    price: float,
    quantity: float,
    buy_order_id: str,
    sell_order_id: str,
) -> Event:
    return Event(
        event_type=EventType.TRADE_EXECUTION,
        timestamp=timestamp,
        sequence=sequence,
        data={
            "trade_id": trade_id,
            "price": price,
            "quantity": quantity,
            "buy_order_id": buy_order_id,
            "sell_order_id": sell_order_id,
        },
    )


def portfolio_update(
    timestamp: float,
    sequence: int,
    strategy_id: str,
    position: float,
    cash: float,
    pnl: float,
) -> Event:
    return Event(
        event_type=EventType.PORTFOLIO_UPDATE,
        timestamp=timestamp,
        sequence=sequence,
        data={
            "strategy_id": strategy_id,
            "position": position,
            "cash": cash,
            "pnl": pnl,
        },
    )


def simulation_complete(
    timestamp: float, sequence: int, final_timestamp: float
) -> Event:
    return Event(
        event_type=EventType.SIMULATION_COMPLETE,
        timestamp=timestamp,
        sequence=sequence,
        data={"final_timestamp": final_timestamp},
    )
