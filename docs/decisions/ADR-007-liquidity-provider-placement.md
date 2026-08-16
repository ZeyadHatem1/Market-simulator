# ADR-007: SyntheticLiquidityProvider lives in market/, inserts directly into OrderBook

## Context

`MonteCarloRunner` (ARCHITECTURE.md's analytics/monte_carlo) needs to run N full exchange
simulations per Monte Carlo batch. Strategies only ever submit MARKET orders (per
ARCHITECTURE.md's strategies/ rule), which need a resting counterparty to fill against. Nothing
in `src/` provided one — `notebooks/02_strategy_comparison.ipynb` worked around this with inline
glue: a MARKET_UPDATE handler resting a large two-sided quote around the current price directly
into the OrderBook, explicitly documented there as "notebook glue for a research demo, not new
production code." `MonteCarloRunner` needs the same behavior across N repeated runs, not once per
notebook, so the glue has to become real, reusable code.

Two questions, resolved with the user up front (AskUserQuestion) rather than guessed: (1) should
this synthetic LP be promoted into `src/` now, or should `MonteCarloRunner` take a
liquidity-provider factory as an injected callable and leave the gap unaddressed; (2) where
should it live, and should it keep the notebook's direct-`OrderBook.insert()` shortcut or route
through `ExchangeGateway`/`ORDER_SUBMIT` like a real order source.

## Decision

Promote it as `market.liquidity.SyntheticLiquidityProvider`, in `market/` rather than
`exchange/` or `strategies/`:

- Not `exchange/`: everything in `exchange/` (gateway/orderbook/matching/execution/validation) is
  pure mechanism — it never originates orders on its own. A liquidity provider is a market
  participant, not a matching-engine concern.
- Not `strategies/`: `strategies/` per ARCHITECTURE.md are "measurable components" — compared via
  `Portfolio`/`analytics.compare()`. The LP is not a strategy under test; it has no `Portfolio`,
  is never a row in a comparison table, and always exists as scaffolding around whatever
  strategies are actually being measured. Grouping it with `market/regimes`, `market/shocks`,
  `market/microstructure` fits better — it's synthetic market structure, the same category as
  those.

Kept the notebook's direct-insertion shortcut (`OrderBook.insert()`, bypassing
`ExchangeGateway`/`ORDER_SUBMIT`) rather than routing through the gateway like a real strategy
order. The notebook version already documented this as "same pattern unit test fixtures use" —
promoting it faithfully rather than redesigning it keeps this ADR scoped to "make it reusable,"
not "also change its wire-level behavior." Going through `ORDER_SUBMIT` would add
`order_id`/validation machinery this component doesn't need (it isn't malformed, isn't a fill
subject to rejection accounting) purely for architectural symmetry with strategies — the kind of
overengineering CLAUDE.md's hard rules warn against.

`ShockModel.liquidity_multiplier_path()` (ADR-006) feeds in as an optional
`liquidity_multiplier_path` constructor arg: on the i-th `MARKET_UPDATE` the LP has seen, it
scales its quoted quantity by `path[i]` (clamped to the path's last value beyond its length) —
this is the "how a multiplier path feeds into a stress-test run" decision ADR-006 deferred to
whenever `MonteCarloRunner` was built. A shock step means thinner resting depth, which
`SlippageModel` already reacts to via `OrderBook.bid_liquidity()`/`ask_liquidity()`, and can
produce partial fills if depth is thin enough — no `MatchingEngine`/`OrderBook` changes needed,
consistent with ADR-006's choice not to touch the matching path.

## Consequences

- `SyntheticLiquidityProvider` remains non-adversarial (tight, symmetric quotes tracking fair
  price) — the same limitation flagged in `docs/research/01_strategy_comparison.md` for
  `win_rate`. Promoting it to `src/` does not fix that; it makes the *existing* limitation
  reusable instead of copy-pasted. A real adversarial market-maker component is still a possible
  future addition, not built here.
- `MonteCarloRunner` and any future notebook can both depend on one implementation instead of
  drifting copies.
- If a future consumer needs the LP to route through validation/gateway (e.g. to appear in
  `TradeLog`/rejection accounting on equal footing with strategy orders), that is a materially
  different design and should get its own ADR, not a silent change to this one.
