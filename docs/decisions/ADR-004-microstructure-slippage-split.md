# ADR-004: Slippage modeling lives in `market/microstructure/`, application stays in `exchange/matching`

## Context

`exchange/orderbook` previously carried a doc claim that market orders had a slippage model —
not true, and already walked back to "not yet implemented" in an earlier documentation pass.
Separately, ARCHITECTURE.md's module map had no dedicated slot for microstructure concerns
(spread dynamics, liquidity metrics, queue dynamics) at all.

This ADR originally said application would stay in `exchange/orderbook`, on the assumption that
matching happened there. By implementation time that assumption was stale: matching logic had
already moved into its own `exchange/matching/MatchingEngine` (see the matching-engine rebuild
predating this ADR), and `exchange/orderbook.OrderBook` had narrowed to pure book storage — it
computes the fill price for nothing. Updated below to match reality; this is a documentation
correction, not a design change to what was actually built.

## Decision

A new `market/microstructure/slippage.py` module holds `SlippageModel`: a linear price-impact
model, `slippage_bps = coefficient * (order_quantity / available_liquidity)`, applied against the
liquidity resting on the side a market order is crossing. The model is a pure function with no
book access of its own — it takes a reference price, an order quantity, and an available-liquidity
figure, and returns an adjusted price.

The **application** lives in `exchange/matching/MatchingEngine._match_market`, since that's where
the fill price is actually computed (same stateless-algorithm/state-container split already
established between `MatchingEngine` and `OrderBook`, and between `FillProcessor` and `Portfolio`).
`OrderBook` gained `bid_liquidity()`/`ask_liquidity()` (sum of remaining quantity resting on a
side) alongside its existing `bid_depth()`/`ask_depth()` (order counts) — `MatchingEngine` reads
these to build the `available_liquidity` argument, but does not mutate anything new.

Only market orders are affected. Limit orders execute at the resting order's exact price, as
before — a limit order is a price commitment the aggressor already made; there's nothing for an
impact model to adjust. The liquidity figure is snapshotted once, before the incoming order's
walk across price levels begins, so the model stays a pure function of (incoming order, pre-trade
book) — it does not compound slippage across an order's own fills as it eats through levels.
`MatchingEngine(slippage_model=None)` (the default) reproduces the old exact-price behavior
exactly, so `build_exchange(runtime)` with no `slippage_model` argument is unaffected.

## Consequences

- `exchange/orderbook.OrderBook` remains the single place that mutates book state; it gained two
  read-only query methods but no new mutation path.
- `exchange/matching.MatchingEngine` remains a pure, deterministic function of (order, book state,
  slippage model) — same inputs, same outputs — preserving ARCHITECTURE.md's rule that the
  matching engine has no knowledge of strategies, portfolios, or analytics. The slippage model is
  itself just another deterministic input, not a source of hidden randomness.
- Status: **implemented.** `market/microstructure/slippage.py` + `SlippageConfig` +
  `default_slippage_config()`, wired optionally through `MatchingEngine.__init__` and
  `build_exchange(runtime, slippage_model=...)`. Spread dynamics, liquidity metrics beyond
  `bid_liquidity`/`ask_liquidity`, and queue dynamics remain **not started** — out of scope for
  this pass per CLAUDE.md's no-overengineering rule; `OrderBook.spread()` already existed and
  needed no changes.
