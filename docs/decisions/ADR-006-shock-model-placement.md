# ADR-006: ShockModel stays a standalone, unwired liquidity-multiplier process

## Context

ARCHITECTURE.md scopes `market/shocks/ShockModel` to liquidity shocks only — price jumps
already live in `JumpDiffusionProcess` (`market/generators/`, see ADR-001). Before
implementation, three integration depths were possible: (a) a standalone stochastic process
producing a liquidity-multiplier path, with no wiring into the matching path; (b) the same
process, but with `MatchingEngine` gaining an optional `shock_model` constructor arg (mirroring
`slippage_model`) that scales `OrderBook.bid_liquidity()`/`ask_liquidity()` at match time; (c)
`ShockModel` actively cancelling resting orders from `OrderBook` during a shock window, modeling
liquidity providers pulling quotes. Resolved with the user up front (AskUserQuestion) rather
than guessed, the same way ADR-004's slippage-application split was.

## Decision

`ShockModel` is a standalone stochastic process, matching the `PoissonArrivalProcess`
precedent (ADR-003): it owns only the shock *timing/magnitude* (a Poisson-triggered process
producing a per-step liquidity-multiplier array), not the application of that multiplier to
the matching engine or order book. `MatchingEngine`/`OrderBook` are untouched by this module.
Consumers (Monte Carlo stress tests, notebooks) apply the multiplier themselves — e.g. scaling
the liquidity value passed into `SlippageModel.apply()` — when they need a shock's effect on
fill prices.

Chosen over (b) because it avoids touching the matching engine's correctness-critical path
again immediately after the native C++ port (ADR-005) was differential-tested against it — a
new optional constructor arg there would need matching updates and re-verification in both the
Python and C++ implementations. Chosen over (c) because order-book mutation policy (which
resting orders get pulled, by side or by distance from mid) is a materially bigger scope than
a price-impact multiplier and isn't needed yet by any current consumer.

## Consequences

- `ShockModel.liquidity_multiplier_path()` is a pure function of `ShockConfig`, same shape as
  `PoissonArrivalProcess.arrival_times()` — fresh seeded RNG per call, no clock dependency, no
  `Event` wrapping.
- `analytics/monte_carlo.MonteCarloRunner` (next in the Phase 3 roadmap) is the first intended
  consumer — it will need to decide, when it's built, exactly how a multiplier path feeds into
  a stress-test run. That decision is deferred to when `MonteCarloRunner` exists, not made here.
- If a future need arises for shocks to actually move fill prices within a single simulation run
  (not just a Monte Carlo distribution), this ADR's option (b) is the natural next step and
  should be revisited then — not built speculatively now.
