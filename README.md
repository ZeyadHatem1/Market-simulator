# Synthetic Market Simulator

[![CI](https://github.com/ZeyadHatem1/Market-simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/ZeyadHatem1/Market-simulator/actions/workflows/ci.yml)

An event driven quantitative trading simulation engine. Synthetic market generators produce
price ticks — GBM, mean-reverting, jump-diffusion, and regime-switching processes, plus a
liquidity-shock overlay. Strategies consume ticks, submit orders, and get filled by a
deterministic exchange engine. A research/analytics layer measures strategy performance
(Sharpe, drawdown, Calmar, correlation) across those runs.

> **Demo video:** *soon*

---

## What This Is

This project is a **backtesting and forward simulation engine**, not a multi-agent market.

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
Visualization  <-----------------  MonteCarloRunner  <---------------  Analytics (Sharpe, etc.)
```

Derivatives pricing (Black-Scholes, Greeks, implied vol, vol surfaces) is a separate, standalone
module — a pure options-pricing library, not part of this simulation pipeline.

---

## Stack

| Layer | Tools |
|-------|-------|
| Simulation core | Python 3.11, dataclasses |
| Event queue | heapq (stdlib) |
| Order book / matching | heapq-based, price-time priority; opt-in C++/pybind11 port |
| Market generation | numpy (GBM, OU, Jump-Diffusion, Regime-Switching, Poisson arrivals) |
| Analytics | pandas, numpy, scipy (metrics, correlation, Monte Carlo) |
| Visualization | matplotlib (equity curves, Monte Carlo fan charts); plotly (3D vol surfaces) |
| Derivatives | scipy (Black-Scholes, Greeks, implied volatility, vol surfaces) |
| Optional AI layer | z-score anomaly detection → defensive strategy (chosen of: ARIMA forecasting, anomaly detection, Q-learning RL) |

---

## Repo Structure

```
market-sim/
├── .github/workflows/ci.yml   # tests + black + pylint on every push/PR to main
├── .pylintrc
├── src/market_sim/
│   ├── core/          # EventQueue, EventLoop, RuntimeEngine, SimulationClock, config/*
│   ├── events/         # Event schemas: MarketUpdate, OrderSubmit, TradeExecution, ...
│   ├── market/         # PriceGenerator (GBM), OU, JumpDiffusion, VolatilityRegimeModel,
│   │                    # ShockModel, PoissonArrivalProcess, SlippageModel, SyntheticLiquidityProvider
│   ├── exchange/        # OrderBook, MatchingEngine, ExchangeGateway, TradeLog,
│   │                     # native/ (opt-in C++ port, identical Python-facing API)
│   ├── strategies/      # Strategy base, MomentumStrategy, MeanReversionStrategy, RandomBaseline,
│   │                     # AnomalyDefenseStrategy
│   ├── portfolio/       # Position, PnLTracker, RiskState, Portfolio, PortfolioManager
│   ├── analytics/       # sharpe/drawdown/calmar/win_rate, correlation_matrix, PerformanceReport,
│   │                     # MonteCarloRunner
│   ├── visualization/   # plot_equity_curves, plot_monte_carlo_fan_chart, plot_vol_surface
│   ├── derivatives/     # Black-Scholes pricing, Greeks, implied volatility, vol surfaces
│   └── ai/              # anomaly/ — AnomalyDetector (rolling z-score); forecasting/, rl/ not
│                         # started, per ARCHITECTURE.md's "choose exactly one"
├── tests/                # core, exchange, market, strategies, portfolio, analytics, visualization,
│                          # derivatives, ai, integration
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

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # or your preferred venv tool
pip install "pybind11>=2.11" setuptools wheel
pip install -e ".[dev]" --no-build-isolation
```

This builds the opt-in C++ matching-engine extension as part of the install (see
[`docs/decisions/ADR-005-native-matching-engine-boundary.md`](docs/decisions/ADR-005-native-matching-engine-boundary.md)),
so the native differential test suite runs too. The extension is fully optional — if the build
step is skipped (`pip install -e ".[dev]"` alone, no pybind11), everything still works;
`market_sim.exchange.native.NATIVE_AVAILABLE` reflects whether it's present, and
`build_exchange()` (the default, pure-Python path) is unaffected either way.

```bash
pytest                              # 342 tests (323 pure-Python + 19 native differential)
black --check .                     # formatting
pylint src/market_sim --fail-under=9.5   # linting, see .pylintrc for what's intentionally disabled and why
```

Same commands [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push/PR to
`main`.

---

## Current Capabilities

- **Exchange**: price-time-priority order book, deterministic matching (limit + market orders,
  partial fills, cancellation), linear slippage on market-order fills, opt-in C++ port
  differential-tested against the Python implementation as the correctness oracle. Profiling
  (see [`docs/research/02_profiling.md`](docs/research/02_profiling.md)) found and fixed a real
  inefficiency in the pure-Python matching engine (13.6x faster on the benchmark replay after
  the fix) — relative speed vs. the native port turned out to be workload-shape-dependent, not
  a fixed number; see the doc for details.
- **Market generation**: GBM, Ornstein-Uhlenbeck (mean-reverting), Merton jump-diffusion,
  Markov regime-switching GBM, Poisson order-arrival timing, and a liquidity-shock process.
- **Strategies**: momentum, mean-reversion, a random baseline, and an anomaly-defense strategy
  (flattens to cash on a detected volatility spike, re-enters once it clears), all pluggable into
  the exchange with zero extra wiring code.
- **Portfolio**: per-strategy position/cash/PnL tracking (weighted-average cost basis),
  drawdown and exposure state, isolated across strategies via `PortfolioManager`.
- **Analytics**: Sharpe, max drawdown, Calmar, win rate, rolling volatility, VaR 95%,
  cross-strategy correlation, and a strategy-comparison report — see
  [`docs/research/01_strategy_comparison.md`](docs/research/01_strategy_comparison.md) for a
  worked example.
- **Monte Carlo**: `MonteCarloRunner` replays a strategy through N full exchange simulations
  (varying seed), summarizing the final-PnL distribution (mean/median/std/percentiles/
  prob-of-loss) and retaining every run's equity curve; an optional stress mode swaps in
  regime-switching price generation and liquidity shocks.
- **Visualization**: equity curve charts across strategies, Monte Carlo fan charts
  (median + percentile band across runs), and an interactive 3D implied-volatility surface plot.
- **Derivatives**: Black-Scholes-Merton European option pricing, closed-form Greeks
  (delta/gamma/vega/theta/rho), an implied-volatility solver, and a vol-surface builder —
  a standalone pricing library, not wired into the exchange as tradeable instruments.
- **AI layer**: `AnomalyDetector` — rolling z-score over price returns, consumed by
  `AnomalyDefenseStrategy` (see Strategies above). Chosen of the three Phase 3 candidates
  (ARIMA forecasting, anomaly detection, Q-learning RL); the other two were not built, per
  ARCHITECTURE.md's "choose exactly one."

This closes out Phase 3 — see
[`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) for the full module map
of what's implemented.

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
