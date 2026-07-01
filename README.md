# Synthetic Market Simulator

An event driven quantitative trading simulation engine. A synthetic market generator
produces price ticks. Strategies consume ticks, submit orders, and get filled by a
deterministic exchange engine. Analytics measure every strategy across 1000+ Monte Carlo
simulations.

> **Demo video:** *soon*

---

## What This Is

SynTradeX is a **backtesting and forward simulation engine**, not a multi-agent market.

The core is the exchange: a deterministic order book with price-time priority matching.
Strategies are measurable components that react to price events and submit orders.
The research layer computes Sharpe, drawdown, VaR, and Monte Carlo distributions.
The output is a quantitative comparison of strategies under different market regimes.

```
SimConfig
    |
    v
MarketGenerator (GBM, configurable μ/σ/N/seed)
    |
    v  MARKET_UPDATE events
EventQueue (heapq, timestamp + sequence priority)
    |
    v
EventLoop
    |
    +--> StrategyEngine   ->  OrderBook + MatchingEngine  ->  TradeLog
    |         on_fill()                                            |
    |         position / cash / pnl                               v
    |                                                      ResearchEngine
    v                                                             |
Visualization  <-----------  MonteCarloRunner (N=1000)  ---------+
```

---

## Stack

| Layer | Tools |
|-------|-------|
| Simulation core | Python 3.11, dataclasses, asyncio |
| Event queue | heapq (stdlib) |
| Order book | sortedcontainers (SortedDict) |
| Market generation | numpy (GBM) |
| Analytics | pandas, scipy |
| Visualization | matplotlib, plotly |
| Optional AI layer | One of: ARIMA, z-score anomaly, Q-learning RL |

---

## Repo Structure

```
market-sim/
├── src/market_sim/
│   ├── core/          # EventQueue, EventLoop, SimulationClock, SimConfig
│   ├── events/        # Event schemas: MarketUpdate, OrderSubmit, TradeExecution, ...
│   ├── market/        # PriceGenerator (GBM), VolatilityRegimeModel, ShockModel
│   ├── exchange/      # OrderBook (SortedDict), MatchingEngine, TradeLog
│   ├── strategies/    # Strategy base, MomentumStrategy, MeanReversionStrategy, RandomBaseline
│   ├── portfolio/     # Position, PnL, equity curve, drawdown state
│   ├── analytics/     # ResearchEngine: Sharpe, drawdown, VaR, Monte Carlo runner
│   ├── visualization/ # Equity curves, fan chart, order book snapshot, comparison dashboard
│   └── ai/            # Optional: forecasting / anomaly detection / RL (Phase 3, pick one)
├── tests/
│   ├── unit/          # Exchange, market, strategies, analytics
│   └── integration/   # End-to-end pipeline tests
├── docs/architecture/
│   └── ARCHITECTURE.md
├── notebooks/
├── examples/
├── config/
├── pyproject.toml
└── requirements.txt
```

---

## Phase 1 Deliverables (in progress)

- `Event` dataclass with `event_id`, `event_type`, `timestamp`, `sequence`, `data`
- `EventQueue` — heapq ordered by `(timestamp, sequence)`
- `EventLoop` — handler registry, deterministic dispatch
- `PriceGenerator` — GBM with configurable μ, σ, N, seed; emits `MarketUpdate` events
- `SimConfig` dataclass
- `OrderBook` — basic bid/ask lists, insert, cancel
- `MatchingEngine` — deterministic fills, emits `TradeExecution`
- `TradeLog`
- Unit tests asserting exact fill prices and event order

---

## Determinism Guarantee

Every event carries a `timestamp` and a `sequence` number. Equal timestamps are broken
by sequence. All randomness is seeded through `SimConfig`. The matching engine is a pure
function: same inputs always produce the same outputs. Tests assert exact execution order.

---

## Architecture

Full module map, event flow, data flow, class boundaries, and build phases:
[`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md)
