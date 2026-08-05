from market_sim.core.models import Side
from market_sim.events import Event
from market_sim.portfolio.pnl import PnLTracker
from market_sim.portfolio.positions import Position
from market_sim.portfolio.risk import RiskState


class Portfolio:
    """
    Per-strategy account: cash, position, realized/unrealized PnL, equity
    curve, and live risk state, all derived purely from fills and prices
    (never from a Strategy's own internal state — see ARCHITECTURE.md's
    portfolio/ rule). Fill attribution works the same way
    Strategy._apply_fill does: `track_order` is told which order_ids belong
    to this Portfolio at submit time, and on_fill only applies fills whose
    buy/sell order_id is in that set.
    """

    def __init__(self, strategy_id: str, initial_cash: float) -> None:
        self.strategy_id = strategy_id
        self.cash = initial_cash
        self._position = Position()
        self._pnl = PnLTracker(initial_cash=initial_cash)
        self._risk = RiskState(peak_equity=initial_cash)
        self._own_order_ids: set[str] = set()
        self._last_price: float | None = None

    def track_order(self, order_id: str) -> None:
        self._own_order_ids.add(order_id)

    def on_market_update(self, event: Event) -> None:
        self._last_price = event.data["price"]
        self._record_equity(event.timestamp)

    def on_fill(self, event: Event) -> None:
        if FillProcessor.process(self, event):
            self._record_equity(event.timestamp)

    @property
    def position_quantity(self) -> float:
        return self._position.quantity

    @property
    def realized_pnl(self) -> float:
        return self._pnl.realized_pnl

    @property
    def unrealized_pnl(self) -> float:
        if self._last_price is None or self._position.quantity == 0:
            return 0.0
        return self._position.quantity * (self._last_price - self._position.avg_price)

    @property
    def equity(self) -> float:
        if self._last_price is None:
            return self.cash
        return self.cash + self._position.quantity * self._last_price

    @property
    def equity_curve(self) -> list[tuple[float, float]]:
        return self._pnl.equity_curve

    @property
    def exposure(self) -> float:
        if self._last_price is None:
            return 0.0
        return self._risk.exposure(self._position.quantity, self._last_price)

    @property
    def drawdown(self) -> float:
        return self._risk.current_drawdown

    @property
    def max_drawdown(self) -> float:
        return self._risk.max_drawdown

    def _record_equity(self, timestamp: float) -> None:
        equity = self.equity
        self._pnl.record_equity(timestamp, equity)
        self._risk.update(equity)


class FillProcessor:
    """
    Applies a TRADE_EXECUTION event to a Portfolio's Position/PnLTracker/cash
    as one consistent unit, mirroring the MatchingEngine/OrderBook split
    (stateless algorithm vs. state container) already used in exchange/.
    """

    @staticmethod
    def process(portfolio: Portfolio, event: Event) -> bool:
        data = event.data
        if data["buy_order_id"] in portfolio._own_order_ids:
            side = Side.BUY
        elif data["sell_order_id"] in portfolio._own_order_ids:
            side = Side.SELL
        else:
            return False

        price = data["price"]
        quantity = data["quantity"]

        realized = portfolio._position.apply_fill(side, price, quantity)
        portfolio._pnl.add_realized(realized)
        portfolio.cash += -price * quantity if side == Side.BUY else price * quantity
        portfolio._last_price = price
        return True
