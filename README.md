# Synthetic Market Simulator

An event driven quantitative trading simulation engine. Synthetic market generators produce
price ticks — GBM, mean-reverting, jump-diffusion, and regime-switching processes, plus a
liquidity-shock overlay. Strategies consume ticks, submit orders, and get filled by a
deterministic exchange engine. A research/analytics layer measures strategy performance
(Sharpe, drawdown, Calmar, correlation) across those runs.

> **Demo video:** *soon*

---

## What This Is

SynTradeX is a **backtesting and forward simulation engine**, not a multi-agent market.

The core is the exchange: a deterministic, price-time-priority order book and matching engine
(pure Python, with an opt-in C++/pybind11 port for the hot path). Strategies are measurable
components that react to price events and submit orders — they never touch the book or a
portfolio directly. A portfolio layer tracks position/cash/PnL per strategy, and the research
layer computes Sharpe, drawdown, Calmar, win rate, and cross-strategy correlation from that.

```
SimConfig
    |
    v
MarketGenerator (GBM / OU / Jump-Diffusion / Regime-Switching, configurable per process)
    |
    v  MARKET_UPDATE events
EventQueue (heapq, timestamp + sequence priority)
    |
    v
EventLoop
    |
    +--> Strategy   ->  ExchangeGateway  ->  OrderBook + MatchingEngine  ->  TradeLog
    |       on_fill()                                                          |
    |       position / cash / pnl                                             v
    |                                                                  Portfolio(s)
    v                                                                         |
Visualization  <-----------  MonteCarloRunner (planned)  <---------  Analytics (Sharpe, etc.)
```

---

## Stack

| Layer | Tools |
|-------|-------|
| Simulation core | Python 3.11, dataclasses |
| Event queue | heapq (stdlib) |
| Order book / matching | heapq-based, price-time priority; opt-in C++/pybind11 port |
| Market generation | numpy (GBM, OU, Jump-Diffusion, Regime-Switching, Poisson arrivals) |
| Analytics | pandas, numpy, scipy |
| Visualization | matplotlib, plotly (planned) |
| Optional AI layer | one of: ARIMA forecasting, z-score anomaly detection, Q-learning RL (not yet started) |

---

## Repo Structure

```
market-sim/
├── src/market_sim/
│   ├── core/          # EventQueue, EventLoop, RuntimeEngine, SimulationClock, config/*
│   ├── events/         # Event schemas: MarketUpdate, OrderSubmit, TradeExecution, ...
│   ├── market/         # PriceGenerator (GBM), OU, JumpDiffusion, VolatilityRegimeModel,
│   │                    # ShockModel, PoissonArrivalProcess, SlippageModel
│   ├── exchange/        # OrderBook, MatchingEngine, ExchangeGateway, TradeLog,
│   │                     # native/ (opt-in C++ port, identical Python-facing API)
│   ├── strategies/      # Strategy base, MomentumStrategy, MeanReversionStrategy, RandomBaseline
│   ├── portfolio/       # Position, PnLTracker, RiskState, Portfolio, PortfolioManager
│   ├── analytics/       # sharpe/drawdown/calmar/win_rate, correlation_matrix, PerformanceReport
│   │                     # (monte_carlo not yet started)
│   ├── visualization/   # not yet started
│   └── ai/              # not yet started — exactly one of forecasting/anomaly/rl, per ARCHITECTURE.md
├── tests/                # core, exchange, market, strategies, portfolio, analytics, integration
├── docs/
│   ├── architecture/ARCHITECTURE.md   # full module map, event flow, class boundaries
│   ├── decisions/                     # ADRs — durable rationale for placement/boundary choices
│   ├── diagrams/                      # Mermaid: event lifecycle, module dependency graph
│   └── research/                      # notebook write-ups
├── notebooks/
├── examples/
├── config/
├── pyproject.toml
└── requirements.txt
```

---

## Current Capabilities

- **Exchange**: price-time-priority order book, deterministic matching (limit + market orders,
  partial fills, cancellation), linear slippage on market-order fills, opt-in C++ port
  differential-tested against the Python implementation as the correctness oracle.
- **Market generation**: GBM, Ornstein-Uhlenbeck (mean-reverting), Merton jump-diffusion,
  Markov regime-switching GBM, Poisson order-arrival timing, and a liquidity-shock process.
- **Strategies**: momentum, mean-reversion, and a random baseline, all pluggable into the
  exchange with zero extra wiring code.
- **Portfolio**: per-strategy position/cash/PnL tracking (weighted-average cost basis),
  drawdown and exposure state, isolated across strategies via `PortfolioManager`.
- **Analytics**: Sharpe, max drawdown, Calmar, win rate, rolling volatility, VaR 95%,
  cross-strategy correlation, and a strategy-comparison report — see
  [`docs/research/01_strategy_comparison.md`](docs/research/01_strategy_comparison.md) for a
  worked example.

Monte Carlo stress testing, visualization, derivatives pricing, and the AI layer are planned
next — see [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) for the
full module map of what's implemented versus planned.

---

## Determinism Guarantee

Every event carries a `timestamp` and a `sequence` number. Equal timestamps are broken
by sequence. All randomness is seeded through config objects (`SimConfig`, `OUConfig`,
`RegimeConfig`, `ShockConfig`, ...). The matching engine is a pure function: same inputs always
produce the same outputs. Tests assert exact execution order and, where a closed-form oracle
exists (e.g. a regime model that never switches regimes), exact numerical agreement with the
simpler process it should reduce to.

---

## Architecture

Full module map, event flow, data flow, class boundaries, and diagrams:
[`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md)
