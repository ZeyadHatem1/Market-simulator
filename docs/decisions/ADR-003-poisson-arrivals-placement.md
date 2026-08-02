# ADR-003: Poisson order arrivals live in `market/arrivals/`, not `exchange/gateway`

## Context

CLAUDE.md's Phase 2 roadmap names "Poisson order arrivals" as an upcoming step, but no module in
ARCHITECTURE.md's module map had a natural home for it. It could plausibly sit in
`exchange/gateway` (it produces orders) or as its own market-side stochastic process.

## Decision

Poisson order arrivals live in a new `market/arrivals/` module (`PoissonArrivalProcess`), a
sibling of `market/generators/`, `market/regimes/`, and `market/shocks/`. It is a market-side
arrival process — it generates the *timing* of incoming orders, the same family as GBM/OU/Jump
Diffusion. `exchange/gateway` continues to own what happens once an order arrives (validation,
routing to the book) — it does not decide *when* orders occur.

## Consequences

- `market/` becomes the single place responsible for all timing and price stochastics feeding
  the simulation; `exchange/` stays purely reactive and deterministic given whatever it's handed.
- Status: **planned, not yet implemented.** This ADR records the placement decision ahead of
  implementation so it doesn't need to be re-derived in a future session.
