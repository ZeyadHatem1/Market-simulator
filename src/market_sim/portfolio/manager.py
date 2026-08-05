from market_sim.events import Event
from market_sim.portfolio.portfolio import Portfolio


class PortfolioManager:
    """
    Owns one Portfolio per strategy_id, so multiple strategies' equity curves
    can be compared side by side (the point of the "strategy comparison"
    goal in ARCHITECTURE.md/README.md). on_market_update/on_fill fan out to
    every registered Portfolio; each Portfolio self-filters fills via its own
    tracked order_ids, same as Strategy does.
    """

    def __init__(self) -> None:
        self._portfolios: dict[str, Portfolio] = {}

    def register_strategy(self, strategy_id: str, initial_cash: float) -> Portfolio:
        if strategy_id in self._portfolios:
            raise ValueError(f"strategy_id already registered: {strategy_id}")
        portfolio = Portfolio(strategy_id, initial_cash)
        self._portfolios[strategy_id] = portfolio
        return portfolio

    def portfolio(self, strategy_id: str) -> Portfolio:
        return self._portfolios[strategy_id]

    def on_market_update(self, event: Event) -> None:
        for portfolio in self._portfolios.values():
            portfolio.on_market_update(event)

    def on_fill(self, event: Event) -> None:
        for portfolio in self._portfolios.values():
            portfolio.on_fill(event)

    def equity_curves(self) -> dict[str, list[tuple[float, float]]]:
        return {
            strategy_id: portfolio.equity_curve
            for strategy_id, portfolio in self._portfolios.items()
        }
