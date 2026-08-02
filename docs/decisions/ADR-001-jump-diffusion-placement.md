# ADR-001: JumpDiffusionProcess lives in `market/generators/`, not `market/shocks/`

## Context

ARCHITECTURE.md originally assigned "jump events" to `market/shocks/ShockModel`. When Merton
jump-diffusion was implemented, that raised the question of whether it belongs there, or as its
own generator alongside `PriceGenerator` (GBM) and `OrnsteinUhlenbeckProcess`.

## Decision

`JumpDiffusionProcess` lives in `market/generators/`. It is a complete, self-contained price
process — same `generate()` / `price_path()` interface as `PriceGenerator` and
`OrnsteinUhlenbeckProcess`, same determinism guarantee (seeded RNG, identical config = identical
path), same test structure. It is not a shock layered onto an already-running simulation; it
produces its own full price path from scratch.

`market/shocks/ShockModel` remains reserved for liquidity and regime shocks applied to a
simulation that's already running — a different concept from a standalone price process.

## Consequences

- `market/generators/` is now the single home for all stochastic price processes (GBM, OU, Jump
  Diffusion), with a consistent interface and test pattern (see `tests/market/test_jump_diffusion.py`,
  which mirrors `tests/market/test_price_generator.py`).
- ARCHITECTURE.md's `market/shocks` bullet no longer mentions jump events — only liquidity shocks.
- Any future price process (e.g. a stochastic-volatility model) should default to
  `market/generators/` unless it's explicitly a shock applied externally to an existing path.
