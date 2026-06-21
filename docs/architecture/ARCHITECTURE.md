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
MarketGenerator (GBM, μ/σ/seed)
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
    |        |-- SortedDict bid/ask (price-time priority)
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
  Wraps ticks into `MarketUpdate` events.
- `market/regimes`: `VolatilityRegimeModel` — regime transitions (high vol, trending, mean-reverting).
- `market/shocks`: `ShockModel` — jump events, liquidity shocks.
- `MarketState`, `SimConfig` dataclass.

**Determinism rule:** all randomness is seeded through `SimConfig`. Same seed = identical run.

---

### `src/market_sim/exchange`

The deterministic exchange core. The most important correctness boundary in the system.

- `exchange/gateway`: order intake, validation, routing.
- `exchange/orderbook`: `OrderBook` — `SortedDict` bid/ask levels, price-time priority,
  O(log n) insert/cancel, market orders with slippage model.
- `exchange/matching`: `MatchingEngine` — deterministic crossing logic, fill generation.
- `exchange/execution`: `Trade`, `ExecutionReport`, trade tape.
- `exchange/validation`: order validation, cancel checks.

**Rule:** the matching engine is pure and deterministic. It produces fills from orders.
It has no knowledge of strategies, portfolios, or analytics.

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

Research metrics. Generic — works on any strategy's output.

- `analytics/metrics`: Sharpe ratio, max drawdown, Calmar ratio, win rate,
  rolling volatility, VaR 95%.
- `analytics/statistics`: distributions, correlations, regime statistics.
- `analytics/performance`: `PerformanceReport`, strategy comparison, equity analysis.
- `analytics/monte_carlo`: `MonteCarloRunner` — N=1000 simulations, PnL distribution,
  stress test regimes.

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
    bids: SortedDict     # price -> deque[Order], descending
    asks: SortedDict     # price -> deque[Order], ascending
    def insert(order: Order) -> None
    def cancel(order_id: str) -> None
    def best_bid() -> float
    def best_ask() -> float
    def snapshot() -> OrderBookSnapshot
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
│       │   ├── regimes/
│       │   └── shocks/
│       ├── exchange/
│       │   ├── gateway/
│       │   ├── orderbook/
│       │   ├── matching/
│       │   ├── execution/
│       │   └── validation/
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
    ├── unit/
    │   ├── exchange/
    │   ├── market/
    │   ├── strategies/
    │   └── analytics/
    └── integration/
```

---
