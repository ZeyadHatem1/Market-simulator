# Strategy Comparison — Momentum vs Mean-Reversion vs Random Baseline

First write-up produced with the `analytics/` layer (CLAUDE.md step 10). Full methodology and
code: [`notebooks/02_strategy_comparison.ipynb`](../../notebooks/02_strategy_comparison.ipynb).

## Setup

One GBM price path (`default_config()`: μ=0.05, σ=0.20, 252 steps, dt=1/252, seed=42) drives
three strategies simultaneously, each with an isolated `Portfolio` under one `PortfolioManager`:

- `MomentumStrategy` (lookback=5, trade_size=10)
- `MeanReversionStrategy` (lookback=10, threshold=1.0, trade_size=10)
- `RandomBaseline` (trade_size=10, seed=7) — noise benchmark

All three submit `MARKET` orders only, which need a resting counterparty. No
market-maker/liquidity-provider component exists in `src/` yet, so the notebook seeds one
directly: a `MARKET_UPDATE` handler that rests a large two-sided quote around the current price
every tick, inserted straight into the `OrderBook`. This is notebook glue for the demo, not a
new production component — see the caveat below on what it does to the numbers.

252 ticks processed, 567 trades executed, 0 orders rejected.

## Results

`periods_per_year = 1 / config.dt = 252` for Sharpe/Calmar annualization — an explicit argument
in `analytics/metrics`, not a hardcoded assumption, since `SimConfig.dt` is configurable.

| strategy       |     equity | realized_pnl | unrealized_pnl | sharpe | max_drawdown | calmar | win_rate |
|----------------|-----------:|-------------:|----------------:|-------:|-------------:|-------:|---------:|
| momentum       | 118,272.42 |     18,272.42 |            0.00 |  0.649 |        0.025 |  3.568 |     1.00 |
| mean_reversion | 111,735.94 |      8,680.72 |        3,055.22 |  0.614 |        0.032 |  2.312 |     1.00 |
| random         | 112,594.63 |     12,507.49 |           87.13 |  0.633 |        0.022 |  3.249 |     1.00 |

Return correlation across strategies:

| strategy       | momentum | mean_reversion | random |
|----------------|---------:|---------------:|-------:|
| momentum       |    1.000 |          -0.066 | -0.006 |
| mean_reversion |   -0.066 |           1.000 |  0.056 |
| random         |   -0.006 |           0.056 |  1.000 |

## Interpretation and caveats

- **`win_rate == 1.0` for all three strategies is a testing-environment artifact, not a result
  worth trusting.** The synthetic liquidity provider quotes a tight spread that tracks the
  current fair price rather than acting as an adversarial counterparty with its own information
  or latency — so in this setup, closing a position is close to always profitable regardless of
  strategy quality. A real backtest needs either organic multi-participant order flow or a
  liquidity provider with its own edge; neither exists yet. Treat `win_rate` here as evidence
  the metric computes correctly (see `tests/analytics/test_metrics.py`), not as a strategy
  result.
- **One seeded path, not a distribution.** `random` posting a positive Sharpe here says nothing
  about its expected performance — Monte Carlo re-runs (N=1000 seeded draws) are Phase 3, not
  built yet. These numbers would look different under a different seed.
- **All three strategies key off the same price series**, so near-zero correlation between them
  is closer to "different reactions to the same signal" than "genuinely independent return
  streams." A cross-instrument or cross-regime comparison would be more informative once
  `market/regimes` (Phase 3) exists.
