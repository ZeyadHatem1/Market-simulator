# ADR-008: derivatives/ stays fully standalone, no wiring into exchange/portfolio

## Context

Phase 3's roadmap named "derivatives pricing (Black-Scholes, Greeks, vol surfaces)" as one
step, but ARCHITECTURE.md's §3 module map had no `derivatives/` entry at all before this step —
unlike every other Phase 2/3 addition, there was no prior placement/boundary spec to implement
against. Two integration depths were possible: (a) a fully standalone pricing library — plain
functions over floats/arrays (spot, strike, maturity, rate, vol), no dependency on
`SimConfig`/`Event`/`Order`/`Portfolio`, options never appear as tradeable instruments anywhere
in the simulation; (b) options as a new tradeable instrument type — a new `OrderType` variant,
options-specific fields on `Order` (strike, expiry, option type), and a way for `Portfolio` to
hold an options position and mark it to Black-Scholes fair value.

Unlike prior ADRs (jump-diffusion placement, shock-model placement, liquidity-provider
placement), this wasn't a case of picking which existing package a component belongs in — it
was deciding whether a new capability touches the exchange/portfolio boundary at all. Resolved
by direct analysis rather than AskUserQuestion, since option (b)'s scope was clear enough not to
need user input to rule out: CLAUDE.md's hard rules ("no overengineering", "no architecture
rewrites after Phase 1", "no new features in Phase 4") already settle it, and the roadmap line
that scoped this step ("Black-Scholes, Greeks, vol surfaces") never mentioned making options
tradeable.

## Decision

`derivatives/` is a fully standalone options-pricing math library: plain functions taking plain
floats/arrays in, plain floats/arrays out. No import of `core.models`, `events`, `exchange`,
`market`, `strategies`, `portfolio`, or `analytics` anywhere in the package — the only module in
`src/market_sim` with zero dependency on `core`/`events` at all (see
`docs/diagrams/module_dependency_graph.md`). There is no options `OrderType`, no options
position in `Portfolio`, and no options counterparty in `OrderBook`.

Also decided in the same pass: no config dataclass (no `BlackScholesConfig` alongside
`SimConfig`/`RegimeConfig`/etc.). Every other stochastic-process module in this codebase takes
one config object because it generates one whole path per call from one fixed set of
parameters. Black-Scholes pricing is the opposite shape — the same formula gets called with a
*different* `(S, K, T, r, sigma)` on every invocation, e.g. once per cell of a vol-surface grid
— so a config-object-per-call would be pure friction, not the consistency it provides
elsewhere.

Chosen over (b) because: options as tradeable instruments is a materially larger feature
(contract specs, expiry handling, an options-aware `MatchingEngine`/`Portfolio`) than one
roadmap line scopes, and would require touching `exchange`'s correctness-critical matching path
again, the same category of risk ADR-006 explicitly avoided for `ShockModel`. Pricing options
correctly does not require simulating a market in them.

## Consequences

- `derivatives/black_scholes` is the base module (`OptionType`, `black_scholes_price`,
  `black_scholes_greeks`); `implied_volatility` and `vol_surface` both depend on it (for
  `OptionType` and the pricing formula they invert), but nothing outside `derivatives` depends
  on any of the three, and nothing inside `derivatives` depends on anything outside it.
- `vol_surface.build_vol_surface` takes market prices as plain caller-supplied input rather than
  generating them from an invented smile/skew shape, for the same "don't guess at unbuilt
  scope" reasoning: this simulator has no real options market data, and inventing a synthetic
  smile parameterization inside `src/` would be exactly the kind of speculative feature CLAUDE.md
  warns against. A caller (notebook, future strategy) can synthesize an example price grid via
  `black_scholes_price` itself and round-trip it through the solver.
- If a future need arises to actually trade options within a simulation (e.g. an options-hedging
  strategy that needs live fills), that is option (b) from this ADR's Context and should get its
  own ADR when a concrete consumer exists — not built speculatively now.
