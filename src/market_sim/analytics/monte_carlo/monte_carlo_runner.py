from dataclasses import dataclass
from typing import Callable, Protocol

import numpy as np

from market_sim.core.clock import SimulationClock
from market_sim.core.config import ShockConfig
from market_sim.core.engine.runtime_engine import RuntimeEngine
from market_sim.core.models import EventType
from market_sim.events import Event
from market_sim.exchange import build_exchange
from market_sim.market.liquidity import SyntheticLiquidityProvider
from market_sim.market.microstructure import SlippageModel
from market_sim.market.shocks import ShockModel
from market_sim.portfolio import Portfolio
from market_sim.strategies import Strategy


class PriceGeneratorLike(Protocol):
    def generate(self) -> list[Event]: ...


StrategyFactory = Callable[[SimulationClock, Callable[[], str]], Strategy]
PriceGeneratorFactory = Callable[[int, SimulationClock], PriceGeneratorLike]
ShockConfigFactory = Callable[[int], ShockConfig]


@dataclass
class MonteCarloResult:
    final_pnl: np.ndarray
    equity_curves: list[list[tuple[float, float]]]
    mean: float
    median: float
    std: float
    percentiles: dict[int, float]
    prob_of_loss: float


class MonteCarloRunner:
    """
    Runs one strategy through `n_runs` independent full exchange simulations
    (seeds `base_seed, base_seed + 1, ..., base_seed + n_runs - 1`) and
    summarizes the resulting final-PnL distribution, per ARCHITECTURE.md's
    analytics/monte_carlo spec. Each run wires build_exchange() + a fresh
    SyntheticLiquidityProvider + one strategy instance + one Portfolio,
    matching the same shape notebooks/02_strategy_comparison.ipynb already
    exercises for a single seed, just repeated and aggregated.

    price_generator_factory(seed, clock) -> object with .generate() is how
    normal vs. stress runs are selected: pass a factory that builds
    PriceGenerator(replace(sim_config, seed=seed), clock) for plain GBM runs,
    or one that builds VolatilityRegimeModel(replace(regime_config,
    seed=seed), clock) for regime-switching stress runs — both already share
    this generate() -> list[Event] shape, so MonteCarloRunner doesn't need to
    know which one it's driving.

    shock_config_factory(seed), if given, builds a ShockConfig per run; its
    ShockModel.liquidity_multiplier_path() is passed to that run's
    SyntheticLiquidityProvider (see docs/decisions/ADR-007). Leave it None
    for a normal (non-stress) Monte Carlo batch.

    strategy_factory(clock, order_id_factory) -> Strategy mirrors how
    Strategy subclasses are actually constructed elsewhere (clock and
    order_id_factory are only available once a run's RuntimeEngine exists) —
    e.g. `lambda clock, oid: MomentumStrategy(strategy_id="mc", initial_cash=...,
    clock=clock, order_id_factory=oid, lookback=5, trade_size=10.0)`.

    final_pnl in the result is realized_pnl + unrealized_pnl (i.e. Portfolio
    state minus the strategy's initial_cash contribution already netted out
    by Portfolio itself — see Portfolio.realized_pnl/unrealized_pnl), one
    entry per run. equity_curves retains each run's full curve so
    visualization (MonteCarloFanChart, next in the Phase 3 roadmap) can plot
    percentile bands without re-running simulations.
    """

    def __init__(
        self,
        price_generator_factory: PriceGeneratorFactory,
        strategy_factory: StrategyFactory,
        n_runs: int,
        base_seed: int,
        initial_cash: float,
        liquidity_spread_bps: float = 20.0,
        liquidity_quantity: float = 1_000_000.0,
        shock_config_factory: ShockConfigFactory | None = None,
        slippage_model: SlippageModel | None = None,
        percentiles: tuple[int, ...] = (5, 25, 50, 75, 95),
    ) -> None:
        if n_runs <= 0:
            raise ValueError(f"n_runs must be > 0, got {n_runs}")
        self._price_generator_factory = price_generator_factory
        self._strategy_factory = strategy_factory
        self._n_runs = n_runs
        self._base_seed = base_seed
        self._initial_cash = initial_cash
        self._liquidity_spread_bps = liquidity_spread_bps
        self._liquidity_quantity = liquidity_quantity
        self._shock_config_factory = shock_config_factory
        self._slippage_model = slippage_model
        self._percentiles = percentiles

    def run(self) -> MonteCarloResult:
        final_pnl = np.empty(self._n_runs)
        equity_curves: list[list[tuple[float, float]]] = []

        for i in range(self._n_runs):
            portfolio = self._run_once(seed=self._base_seed + i)
            final_pnl[i] = portfolio.realized_pnl + portfolio.unrealized_pnl
            equity_curves.append(portfolio.equity_curve)

        return MonteCarloResult(
            final_pnl=final_pnl,
            equity_curves=equity_curves,
            mean=float(np.mean(final_pnl)),
            median=float(np.median(final_pnl)),
            std=float(np.std(final_pnl, ddof=1)) if self._n_runs > 1 else 0.0,
            percentiles={
                p: float(np.percentile(final_pnl, p)) for p in self._percentiles
            },
            prob_of_loss=float(np.mean(final_pnl < 0)),
        )

    def _run_once(self, seed: int) -> Portfolio:
        runtime = RuntimeEngine()
        book, _trade_log, _gateway = build_exchange(
            runtime, slippage_model=self._slippage_model
        )

        price_generator = self._price_generator_factory(seed, runtime.clock)
        for event in price_generator.generate():
            runtime.queue.push(event)

        multiplier_path = None
        if self._shock_config_factory is not None:
            shock_config = self._shock_config_factory(seed)
            multiplier_path = ShockModel(shock_config).liquidity_multiplier_path()

        liquidity_provider = SyntheticLiquidityProvider(
            book,
            spread_bps=self._liquidity_spread_bps,
            quantity=self._liquidity_quantity,
            liquidity_multiplier_path=multiplier_path,
        )
        runtime.loop.register_handler(
            EventType.MARKET_UPDATE, liquidity_provider.on_market_update
        )

        strategy = self._strategy_factory(runtime.clock, runtime.next_order_id)
        portfolio = Portfolio(
            strategy_id="monte_carlo", initial_cash=self._initial_cash
        )

        def on_market_update(event: Event) -> None:
            portfolio.on_market_update(event)
            for order_event in strategy.on_market_update(event):
                runtime.queue.push(order_event)
                portfolio.track_order(order_event.data["order_id"])

        runtime.loop.register_handler(EventType.MARKET_UPDATE, on_market_update)
        runtime.loop.register_handler(EventType.TRADE_EXECUTION, strategy.on_fill)
        runtime.loop.register_handler(EventType.TRADE_EXECUTION, portfolio.on_fill)

        runtime.start()
        return portfolio
