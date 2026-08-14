# SynTradeX — Architecture

## 1. System Goal

Build a fully event-driven quantitative trading simulation engine.

The core of this project is the **exchange engine** and the **event-driven simulation pipeline**.
A synthetic market generator produces price ticks. Strategies consume those ticks and submit orders.
The exchange processes orders deterministically. Analytics measure how each strategy performed.

**This is a backtesting and forward simulation engine. It is not a multi-agent market.**
Strategies are measurable components, not autonomous actors. The goal is to produce
research-grade outputs: equity curves, Sharpe ratios, drawdown, Monte Carlo distributions, and
strategy comparisons — all driven by a clean, testable, deterministic core.

AI is an optional research layer added in Phase 3, after the exchange and analytics are solid.

---

## 2. System Pipeline

```
SimConfig
    |
    v
MarketGenerator (GBM / OU / Jump-Diffusion / Regime-Switching, seeded)
    |
    v  MARKET_UPDATE events
EventQueue (heapq, timestamp + sequence priority)
    |
    v
EventLoop (handler registry, simulated clock)
    |
    +--> StrategyEngine
    |        |-- on_market_update(event) -> ORDER_SUBMIT
    |        |-- on_fill(event)          -> position/cash/pnl update
    |        |-- strategies: Momentum, MeanReversion, RandomBaseline
    |
    +--> OrderBook
    |        |-- heap-based bid/ask (price-time priority), lazy-delete cancellation
    |        |-- O(log n) insert, cancel, match
    |        |-- fill -> TRADE_EXECUTION event
    |
    +--> TradeLog
    |
    v
ResearchEngine
    |-- Sharpe ratio
    |-- Max drawdown / Calmar ratio
    |-- Win rate, rolling volatility, VaR 95%
    |-- Correlation matrix across strategies
    |
    v
Monte Carlo Runner (N=1000 simulations, different seeds)
    |-- PnL distribution: mean, median, std, percentiles, prob of loss
    |-- Stress regimes: high volatility, trending, mean-reverting
    |
    v
Visualization
    |-- Equity curves (all strategies)
    |-- Monte Carlo fan chart
    |-- Order book snapshot bar chart
    |-- Strategy comparison dashboard
    |-- All saveable as PNG
```

---

## 3. Module Map

### `src/market_sim/core`

The runtime foundation.

- `core/engine`: `RuntimeEngine` — simulation lifecycle, start/stop, coordination.
- `core/clock`: `SimulationClock` — logical timestamps and sequence numbering.
- `core/queue`: `EventQueue` — heapq-based priority queue, deterministic ordering.
- `core/models`: `SimConfig`, `Instrument`, `Side`, `OrderType`, `EventType`.
- `core/config`: config loading and defaults.

**Rule:** `core/` owns simulation mechanics only. No strategy logic, no exchange rules.

---

### `src/market_sim/events`

The event schema layer. Defines what moves through the pipeline.

Events:
- `Event` — base: `event_id`, `event_type`, `timestamp`, `sequence`, `data`
- `MarketUpdate` — new price tick from the generator
- `OrderSubmit` — strategy requests an order
- `OrderCancel` — strategy cancels an order
- `TradeExecution` — a fill produced by the matching engine
- `PortfolioUpdate` — position/cash/pnl state after a fill
- `SimulationComplete` — end-of-run signal

**Rule:** events carry data, not logic. No methods beyond `__post_init__` validation.

---

### `src/market_sim/market`

Synthetic price generation.

- `market/generators`: `PriceGenerator` — Geometric Brownian Motion, configurable μ/σ/N/seed.
  `OrnsteinUhlenbeckProcess` — mean-reverting process (θ/μ/σ/N/seed), exact discrete-time
  solution. `JumpDiffusionProcess` — Merton jump-diffusion (GBM + compound Poisson jumps,
  λ/jump_mean/jump_std), reduces exactly to `PriceGenerator`'s GBM when λ=0. All three wrap
  their output into `MarketUpdate` events. See `docs/decisions/ADR-001-jump-diffusion-placement.md`
  for why jump events live here rather than in `market/shocks`.
- `market/arrivals`: `PoissonArrivalProcess` — the *timing* of incoming order arrivals, same
  family as the generators above (a stochastic process, not an exchange concern). Decides when
  orders occur; `exchange/gateway` still owns what happens once one arrives. See
  `docs/decisions/ADR-003-poisson-arrivals-placement.md`.
- `market/regimes`: `VolatilityRegimeModel` — regime-switching GBM: a discrete-time Markov
  chain over named regimes (e.g. `low_vol`/`high_vol`), each with its own (mu, sigma), sampled
  once per step via `RegimeConfig.transition_matrix` and driving the same GBM update
  `PriceGenerator` uses. With a transition matrix that always self-loops on one regime, this
  reduces exactly to `PriceGenerator`'s plain GBM for that regime's (mu, sigma). Same
  `generate()`/`price_path()` shape as the other generators, plus `regime_path()` (raw regime
  label array, one entry per step) for notebooks/Monte Carlo consumption.
- `market/shocks`: `ShockModel` — liquidity shocks: a Poisson-triggered process producing a
  per-step liquidity-multiplier array (`liquidity_multiplier_path()`), 1.0 = normal, lower
  during a shock window. Same standalone-process shape as `PoissonArrivalProcess` — owns only
  shock timing/magnitude, no `Event` wrapping, no clock dependency, and deliberately does not
  touch `MatchingEngine`/`OrderBook` itself; a consumer (Monte Carlo stress tests, notebooks)
  applies the multiplier. (Jump events are handled by `JumpDiffusionProcess` in
  `market/generators`, not here — a full standalone price process is a different concept from a
  shock layered onto an already-running simulation.) See
  `docs/decisions/ADR-006-shock-model-placement.md`.
- `market/microstructure`: `SlippageModel` — linear price-impact model
  (`bps = coefficient * order_quantity / available_liquidity`), applied only to market orders.
  The model is a pure function; the *application* at match time lives in
  `exchange/matching.MatchingEngine`, which reads `OrderBook.bid_liquidity()`/`ask_liquidity()`
  to build its input. Spread dynamics and queue dynamics are not started — out of scope for the
  current pass. See `docs/decisions/ADR-004-microstructure-slippage-split.md`.
- `MarketState`, `SimConfig` dataclass.

**Determinism rule:** all randomness is seeded through `SimConfig`. Same seed = identical run.

---

### `src/market_sim/exchange`

The deterministic exchange core. The most important correctness boundary in the system.

- `exchange/gateway`: order intake, validation, routing. See
  `docs/decisions/ADR-002-gateway-error-boundary.md` for why malformed-order handling lives here.
- `exchange/orderbook`: `OrderBook` — heap-based bid/ask levels, price-time priority,
  lazy-delete cancellation. Pure book storage; does not compute fill prices.
- `exchange/matching`: `MatchingEngine` — deterministic crossing logic, fill generation. Applies
  `market/microstructure.SlippageModel` to market-order fills when one is configured (optional,
  defaults to none — see `docs/decisions/ADR-004-microstructure-slippage-split.md`).
- `exchange/execution`: `Trade`, `ExecutionReport`, trade tape.
- `exchange/validation`: order validation, cancel checks.

**Rule:** the matching engine is pure and deterministic. It produces fills from orders.
It has no knowledge of strategies, portfolios, or analytics.

**Future optimization boundary:** `MatchingEngine` and `OrderBook` are the only components ever
targeted for a C++/pybind11 port (see README.md's stack table). Strategies, research, analytics,
and visualization stay pure Python permanently — this boundary does not move.

- `exchange/native`: the implemented native port — `NativeOrderBook`/`NativeMatchingEngine`,
  drop-in replacements for `OrderBook`/`MatchingEngine` with identical public method
  signatures, backed by a pybind11 extension (`exchange/native/cpp/`, built via setuptools, not
  CMake). Only primitives cross the pybind11 boundary; the native engine is slippage-agnostic
  (raw crossing only) with `SlippageModel` application staying entirely in the Python adapter.
  **Opt-in only**: `build_exchange()` is unchanged and still defaults to the pure-Python engine;
  `build_native_exchange()` is a separate, additive entry point. The extension is fully
  optional at import time — `market_sim.exchange.native.NATIVE_AVAILABLE` reflects whether it
  was built, and nothing breaks if it wasn't. Correctness is enforced by differential testing
  against the Python implementation as the oracle
  (`tests/exchange/test_native_differential.py`), not by manual inspection. Full rationale in
  `docs/decisions/ADR-005-native-matching-engine-boundary.md`.

---

### `src/market_sim/strategies`

Measurable trading strategies. These are components, not autonomous agents.

- `strategies/base`: `Strategy` abstract base — `on_market_update`, `on_fill`, position/cash/pnl state.
- `strategies/momentum`: `MomentumStrategy`.
- `strategies/mean_reversion`: `MeanReversionStrategy`.
- `strategies/random`: `RandomBaseline` — random buy/sell, used for benchmarking.

**Rule:** strategies react to events and submit orders via the event queue.
They never mutate the order book or portfolio directly.

---

### `src/market_sim/portfolio`

Position, cash, and PnL accounting.

- `portfolio/positions`: `Position`, position ledger.
- `portfolio/pnl`: realized PnL, unrealized PnL, equity curve.
- `portfolio/risk`: exposure, drawdown state, limits.
- `Portfolio`, `PortfolioManager`, `FillProcessor`.

**Rule:** portfolio accounting depends only on fills and prices.
No strategy internals are visible here.

---

### `src/market_sim/analytics`

Research metrics. Generic — works on any strategy's output. All functions are pure: they take
an equity curve (`list[tuple[timestamp, equity]]`, the shape `Portfolio.equity_curve` already
produces) or a `PortfolioManager`, and return a number/DataFrame — no side effects, no mutation
of simulation state.

- `analytics/metrics`: `sharpe`, `max_drawdown`, `calmar`, `win_rate`, `rolling_volatility`,
  `var_95`. `sharpe`/`calmar` take an explicit `periods_per_year` argument rather than assuming
  252, since `SimConfig.dt` is configurable. `win_rate` reads `Portfolio.realized_pnl_history`
  (added alongside this module — `PnLTracker` previously only kept a running total, not a
  per-fill history, so win/loss couldn't be counted).
- `analytics/statistics`: `correlation_matrix` — pairwise return correlation across strategies'
  equity curves, aligned by timestamp (not position: two strategies that fill a different
  number of times end up with differently-sized curves).
- `analytics/performance`: `PerformanceReport` (one strategy's metrics) + `compare()` (one row
  per strategy in a `PortfolioManager`, as a DataFrame).
- `analytics/monte_carlo`: `MonteCarloRunner` — N=1000 simulations, PnL distribution,
  stress test regimes. Phase 3, not started.

First write-up using this layer: `docs/research/01_strategy_comparison.md` (backing notebook:
`notebooks/02_strategy_comparison.ipynb`).

**Rule:** analytics is purely downstream. It reads simulation output. It never alters execution.

---

### `src/market_sim/visualization`

Charts and dashboards. All outputs saveable as PNG.

- `EquityCurvePlot` — all strategies on one chart.
- `MonteCarloFanChart` — percentile bands from Monte Carlo run.
- `OrderBookSnapshot` — bar chart of bid/ask depth at a point in time.
- `StrategyDashboard` — comparison view: returns, Sharpe, drawdown, win rate.

---

### `src/market_sim/ai`

Optional research layer. Added in Phase 3, after the exchange and analytics are complete.
Consumes historical simulation output. Does not replace the exchange core.

Choose exactly one in Phase 3:
- **(A)** `ai/forecasting` — ARIMA forecasting → forecast-driven strategy.
- **(B)** `ai/anomaly` — z-score anomaly detection → defensive strategy.
- **(C)** `ai/rl` — Q-learning agent (state = price changes + position, actions = BUY/SELL/HOLD).

---

## 4. Event Flow

```
MarketGenerator
    |
    | MarketUpdate (timestamp t, price p)
    v
EventQueue
    |
    | dispatch by priority (timestamp, then sequence)
    v
EventLoop
    |
    +--> StrategyEngine.on_market_update(event)
    |        |
    |        | OrderSubmit event
    |        v
    |    EventQueue (re-enqueued)
    |        |
    |        v
    |    Exchange.handle_order(event)
    |        |
    |        v
    |    OrderBook + MatchingEngine
    |        |
    |        | TradeExecution event
    |        v
    |    EventQueue (re-enqueued)
    |        |
    |        +--> StrategyEngine.on_fill(event)  -> updates position/cash/pnl
    |        +--> TradeLog.record(event)
    |
    v
[end of simulation]
ResearchEngine.compute(trade_log, equity_curves)
MonteCarloRunner.run(N=1000)
Visualization.render()
```

---

## 5. Data Flow

```
1.  SimConfig sets μ, σ, N ticks, seed, and initial capital.
2.  MarketGenerator produces N price ticks via GBM, wraps each as a MarketUpdate event.
3.  EventQueue receives all events with (timestamp, sequence) priority.
4.  EventLoop dispatches events in deterministic order.
5.  Each strategy receives MarketUpdate, decides to BUY/SELL/HOLD, emits OrderSubmit.
6.  Exchange validates the order.
7.  OrderBook stores passive limit orders. MatchingEngine crosses aggressive orders.
8.  Fills produce TradeExecution events. Strategies update position/cash/pnl via on_fill.
9.  TradeLog stores all executions.
10. After simulation ends, ResearchEngine computes metrics for each strategy.
11. MonteCarloRunner re-runs the simulation N=1000 times with different seeds.
12. Visualization renders equity curves, fan charts, and the comparison dashboard.
```

---

## 6. Core Class Boundaries

### Event

```python
@dataclass
class Event:
    event_id: str        # UUID
    event_type: EventType
    timestamp: float     # simulation time
    sequence: int        # tiebreaker for equal timestamps
    data: dict
```

### OrderBook

```python
class OrderBook:
    _bids: list[tuple[float, int, Order]]  # max-heap (negated price), price-time priority
    _asks: list[tuple[float, int, Order]]  # min-heap, price-time priority
    def insert(order: Order) -> None
    def cancel(order_id: str) -> None       # lazy delete via _cancelled set
    def best_bid() -> Order | None
    def best_ask() -> Order | None
    def bid_liquidity() -> float
    def ask_liquidity() -> float
    def spread() -> float | None
```

### MatchingEngine

```python
class MatchingEngine:
    def match(order: Order, book: OrderBook) -> list[Trade]
```

Pure function-style. No state beyond what it needs to match.
Deterministic. Heavily unit tested.

### Strategy (abstract base)

```python
class Strategy(ABC):
    position: int
    cash: float
    pnl: float

    @abstractmethod
    def on_market_update(self, event: Event) -> list[Event]: ...

    @abstractmethod
    def on_fill(self, event: Event) -> None: ...
```

### ResearchEngine

```python
class ResearchEngine:
    def sharpe(equity_curve: list[float]) -> float
    def max_drawdown(equity_curve: list[float]) -> float
    def calmar(equity_curve: list[float]) -> float
    def win_rate(trades: list[Trade]) -> float
    def rolling_volatility(equity_curve: list[float], window: int) -> list[float]
    def var_95(equity_curve: list[float]) -> float
    def correlation_matrix(curves: dict[str, list[float]]) -> pd.DataFrame
```

---

## 7. Determinism Rules

- Every event has a `timestamp` and a `sequence` number.
- Equal timestamps are broken by `sequence`. No random ordering.
- All RNG seeded through `SimConfig.seed`.
- `MatchingEngine` is a pure, stateless function. Same inputs → same outputs.
- Order IDs and trade IDs generated centrally via a counter in `RuntimeEngine`.
- Tests assert exact fill prices, fill quantities, and event order.

---

## 8. Repo Structure

```
market-sim/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── config/
├── docs/
│   ├── architecture/
│   │   └── ARCHITECTURE.md
│   ├── diagrams/
│   ├── research/
│   └── decisions/
├── examples/
├── notebooks/
├── src/
│   └── market_sim/
│       ├── core/
│       │   ├── clock/
│       │   ├── engine/
│       │   ├── queue/
│       │   ├── models/
│       │   └── config/
│       ├── events/
│       ├── market/
│       │   ├── generators/
│       │   ├── arrivals/
│       │   ├── regimes/
│       │   ├── shocks/
│       │   └── microstructure/
│       ├── exchange/
│       │   ├── gateway/
│       │   ├── orderbook/
│       │   ├── matching/
│       │   ├── execution/
│       │   ├── validation/
│       │   └── native/       # opt-in C++/pybind11 port, see ADR-005
│       │       └── cpp/
│       ├── strategies/
│       │   ├── base/
│       │   ├── momentum/
│       │   ├── mean_reversion/
│       │   └── random/
│       ├── portfolio/
│       │   ├── positions/
│       │   ├── pnl/
│       │   └── risk/
│       ├── analytics/
│       │   ├── metrics/
│       │   ├── statistics/
│       │   ├── performance/
│       │   └── monte_carlo/
│       ├── visualization/
│       └── ai/
│           ├── forecasting/
│           ├── anomaly/
│           └── rl/
└── tests/
    ├── core/
    ├── exchange/
    ├── market/
    ├── strategies/
    ├── portfolio/
    ├── analytics/
    └── integration/
```

Flat, not nested under `tests/unit/` — this reflects the actual repo layout, which was never
nested despite earlier drafts of this doc implying otherwise. Deliberately left flat rather than
restructured to match; this is a documentation-accuracy fix, not a planned code change.

---

## 9. Diagrams

Generated from the actual current code (not this document's aspirational module map), so they
stay accurate as implementation catches up to spec:

- [`docs/diagrams/event_lifecycle.md`](../diagrams/event_lifecycle.md) — sequence diagram of one
  order-submit-to-fill cycle through the currently wired pipeline.
- [`docs/diagrams/module_dependency_graph.md`](../diagrams/module_dependency_graph.md) — import
  graph across `src/market_sim`, distinguishing compile-time imports from runtime handler wiring.

---
