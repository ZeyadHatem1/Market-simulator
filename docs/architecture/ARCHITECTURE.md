# Market Simulator — Architecture

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
- `market/liquidity`: `SyntheticLiquidityProvider` — rests a two-sided quote around the current
  price into `OrderBook` on every `MarketUpdate`, giving strategies' MARKET orders a counterparty
  to fill against. Inserts directly into `OrderBook` rather than through
  `ExchangeGateway`/`ORDER_SUBMIT` (same shortcut test fixtures already use). Deliberately
  non-adversarial (tight, symmetric quotes tracking fair price) — see
  `docs/research/01_strategy_comparison.md`'s `win_rate` caveat. Accepts an optional
  `liquidity_multiplier_path` (from `ShockModel`) that scales quoted quantity per step, the
  mechanism `analytics/monte_carlo.MonteCarloRunner` uses for stress runs. See
  `docs/decisions/ADR-007-liquidity-provider-placement.md`.
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

**Profiling**: `docs/research/02_profiling.md` profiled `_match_market` and found it
unconditionally computed an O(book-depth) liquidity snapshot even when no `slippage_model` was
set — a real bug, confirmed (not guessed) by comparing against `exchange/native/adapter.py`'s
already-correct `needs_slippage` guard, and fixed in the same pass (13.6x faster on the
benchmark replay; `MonteCarloRunner.run()` 1.6x faster on a 100-run batch). The fix also
surfaced a genuinely surprising second result: with the dead computation gone, pure Python now
outperforms the native engine on that order mix — see the doc for why (per-`match()`-call
pybind11 boundary-crossing overhead, not a general "native is slower" claim).

---

### `src/market_sim/strategies`

Measurable trading strategies. These are components, not autonomous agents.

- `strategies/base`: `Strategy` abstract base — `on_market_update`, `on_fill`, position/cash/pnl state.
- `strategies/momentum`: `MomentumStrategy`.
- `strategies/mean_reversion`: `MeanReversionStrategy`.
- `strategies/random`: `RandomBaseline` — random buy/sell, used for benchmarking.
- `strategies/anomaly_defense`: `AnomalyDefenseStrategy` — holds a static target position under
  normal conditions, flattens to cash whenever `ai/anomaly.AnomalyDetector` flags the latest
  return as anomalous, re-enters once the flag clears. Risk-off only, no directional signal of
  its own. The one place `strategies/` imports outside `core`/`events` — see `ai/anomaly` below.

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
- `analytics/statistics`: `align_equity_curves` — turns a `dict[key, equity_curve]` into one
  timestamp-aligned `DataFrame` (union of timestamps, forward-filled; later samples win ties at
  an identical timestamp). `correlation_matrix` — pairwise return correlation across strategies'
  equity curves, built on `align_equity_curves` (curves can't be zipped by position: two
  strategies, or two Monte Carlo runs, that fill a different number of times end up with
  differently-sized curves). `align_equity_curves` is also reused by
  `visualization.plot_monte_carlo_fan_chart`.
- `analytics/performance`: `PerformanceReport` (one strategy's metrics) + `compare()` (one row
  per strategy in a `PortfolioManager`, as a DataFrame).
- `analytics/monte_carlo`: `MonteCarloRunner` — runs one strategy through N independent full
  exchange simulations (seeds `base_seed .. base_seed + N - 1`), each wiring
  `build_exchange()` + a fresh `market/liquidity.SyntheticLiquidityProvider` + the strategy +
  one `Portfolio`, and summarizes the resulting final-PnL distribution (mean, median, std,
  percentiles, prob of loss) plus every run's full equity curve. `price_generator_factory`
  selects normal (plain GBM via `PriceGenerator`) vs. stress (regime-switching via
  `VolatilityRegimeModel`) runs — both share the same `generate() -> list[Event]` shape, so the
  runner doesn't special-case which one it's driving. An optional `shock_config_factory` builds
  a `ShockConfig` per run whose `ShockModel.liquidity_multiplier_path()` feeds the run's
  liquidity provider, thinning resting depth during shock windows (which `SlippageModel` and
  partial fills already react to — no `MatchingEngine`/`OrderBook` changes needed). See
  `docs/decisions/ADR-007-liquidity-provider-placement.md`.

First write-up using this layer: `docs/research/01_strategy_comparison.md` (backing notebook:
`notebooks/02_strategy_comparison.ipynb`). `MonteCarloRunner.run()`'s own wall-clock profile
(where its time actually goes at a 100-run batch size) is in
`docs/research/02_profiling.md` (backing notebook: `notebooks/03_profiling.ipynb`).

**Rule:** analytics is purely downstream. It reads simulation output. It never alters execution.

---

### `src/market_sim/visualization`

Charts and dashboards. Plain functions, not classes — no per-instance state a chart needs to
hold beyond its inputs, consistent with `analytics/`'s pure-function style. `plot_equity_curves`
and `plot_monte_carlo_fan_chart` return a matplotlib `Figure` rather than saving it, the caller
deciding whether/how to persist it (`fig.savefig(path)`); `plot_vol_surface` returns a plotly
`Figure` instead (`fig.write_image(path)` for a static image, `fig.show()`/`fig.write_html(path)`
for the interactive version) — 2D static charts stay matplotlib, but a 3D vol surface is
specifically what the stack table earmarks plotly for.

- `plot_equity_curves` — all strategies on one chart. Takes `dict[strategy_id, equity_curve]`,
  the same shape `PortfolioManager.equity_curves()` and `analytics.statistics.correlation_matrix`
  already use.
- `plot_monte_carlo_fan_chart` — median equity path plus a shaded percentile band (default
  5th-95th) across every run in a `MonteCarloResult`. Reuses
  `analytics.statistics.align_equity_curves` to align runs onto one timestamp axis first, for
  the same reason `correlation_matrix` needs it: runs that trade a different number of times
  produce differently-sized equity curves even when every run shares the same underlying tick
  timestamps.
- `plot_vol_surface` — 3D surface plot (`plotly.graph_objects.Surface`) of
  `derivatives.vol_surface.VolSurface.implied_vols` over (strike, maturity). The first
  `visualization` function to depend on `derivatives` rather than `analytics`. Raises if either
  axis of the surface is empty; otherwise a thin wrapper — the grid shape is already exactly
  what `go.Surface(x=strikes, y=maturities, z=implied_vols)` expects, no reshaping needed.
- `OrderBookSnapshot` (bar chart of bid/ask depth) and `StrategyDashboard` (comparison view:
  returns, Sharpe, drawdown, win rate) — still not started; no simulation-time consumer needs
  them yet, unlike `plot_vol_surface` which had a concrete data contract (`VolSurface`) waiting
  on it.

---

### `src/market_sim/derivatives`

Standalone options-pricing library — Black-Scholes-Merton pricing, Greeks, implied volatility,
and vol surfaces. Pure math: takes plain floats/arrays (spot, strike, maturity, rate, vol), not
`SimConfig`/`Event`/`Order`. Not wired into the exchange, strategies, or portfolio in any way —
there is no options `OrderType`, no options position in `Portfolio`. Adding that would be a
different, much larger feature (contract specs, expiry handling, options-specific order types)
than what this step scopes; this module prices options as a research/analysis capability
alongside `analytics/`, not as tradeable instruments in the simulation. See
`docs/decisions/ADR-008-derivatives-isolation-boundary.md` for the full placement rationale.

- `derivatives/black_scholes`: `black_scholes_price(S, K, T, r, sigma, option_type, q=0.0)` —
  the Black-Scholes-Merton European call/put formula under a continuous dividend yield
  (`q=0.0` reduces to the plain Black-Scholes formula). `black_scholes_greeks(...)` — closed-form
  delta/gamma/vega/theta/rho for the same contract, sharing `_d1_d2` with the pricing formula
  rather than recomputing it. `OptionType` (CALL/PUT) is defined here and re-exported by the
  other two submodules — a real Enum (not a type alias), so it's imported once, not duplicated
  per file the way plain type aliases like `EquityCurve` are elsewhere in this codebase.
- `derivatives/implied_volatility`: `implied_volatility(market_price, S, K, T, r, option_type,
  q=0.0, sigma_bounds=(1e-6, 5.0))` — solves for sigma via Brent's method (`scipy.optimize.
  brentq`) rather than Newton-Raphson, since Brent's bracketed search stays robust for deep
  in/out-of-the-money contracts where vega (and therefore a Newton step) is near zero. Raises
  `ValueError` if `market_price` isn't attainable for any sigma in `sigma_bounds` (e.g. a
  no-arbitrage violation).
- `derivatives/vol_surface`: `build_vol_surface(market_prices, strikes, maturities, S, r,
  option_type, q=0.0)` — inverts a `(len(maturities), len(strikes))` grid of market option
  prices into a matching grid of implied vols, one `implied_volatility` solve per cell. Takes
  `market_prices` as plain input rather than generating them from an assumed smile/skew shape:
  this simulator has no real options market data, but a caller can synthesize an example price
  grid via `black_scholes_price` with a hand-picked vol smile and feed it back in as a
  round-trip demonstration — keeping the function equally usable for synthetic and real data,
  rather than baking in an invented smile parameterization.

3D vol-surface plotting is `visualization.plot_vol_surface` (see `visualization/` above) — this
module itself stays rendering-free, `build_vol_surface` only ever returns the grid.

---

### `src/market_sim/ai`

Optional research layer. Added in Phase 3, after the exchange and analytics are complete.
Does not replace the exchange core.

Phase 3 named three candidates and required choosing exactly one — chose **(B)**:
- **(B)** `ai/anomaly` — z-score anomaly detection → defensive strategy. **Implemented.**
- (A) `ai/forecasting` (ARIMA forecasting → forecast-driven strategy) and (C) `ai/rl`
  (Q-learning agent) were not built — out of scope once (B) was chosen, per this section's
  "exactly one."

- `ai/anomaly`: `AnomalyDetector` — rolling z-score over price *returns* (not raw price, which
  carries trend/drift that would make an ordinary rally or selloff look anomalous against a
  rolling price window). `update(price) -> bool` flags a step anomalous when the latest return's
  z-score against the population mean/std of the trailing `window` returns exceeds `threshold`
  in magnitude; `is_ready` reports whether enough returns have accumulated yet (`window + 1`
  price updates, since the first update only seeds the running last-price with no return to
  score). Pure, stdlib-only (`statistics`/`collections`), zero `market_sim` imports — no config
  dataclass, matching `strategies/`'s own convention of taking constructor args directly rather
  than `market/generators`' one-config-per-whole-path shape (this is called incrementally,
  tick-by-tick, not once per run).
- Consumer: `strategies/anomaly_defense.AnomalyDefenseStrategy` (see `strategies/` above).

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
├── .pylintrc
├── .github/
│   └── workflows/
│       └── ci.yml
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
│       │   ├── microstructure/
│       │   └── liquidity/
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
│       │   ├── random/
│       │   └── anomaly_defense/
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
│       ├── derivatives/
│       │   ├── black_scholes/
│       │   ├── implied_volatility/
│       │   └── vol_surface/
│       └── ai/
│           ├── forecasting/    # not started, see §3
│           ├── anomaly/
│           └── rl/             # not started, see §3
└── tests/
    ├── core/
    ├── exchange/
    ├── market/
    ├── strategies/
    ├── portfolio/
    ├── analytics/
    ├── visualization/
    ├── derivatives/
    ├── ai/
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
