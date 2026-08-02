# ADR-004: Slippage modeling lives in `market/microstructure/`, application stays in `exchange/orderbook`

## Context

`exchange/orderbook` previously carried a doc claim that market orders had a slippage model —
not true, and already walked back to "not yet implemented" in an earlier documentation pass.
Separately, ARCHITECTURE.md's module map had no dedicated slot for microstructure concerns
(spread dynamics, liquidity metrics, queue dynamics) at all.

## Decision

A new `market/microstructure/` module holds the spread/liquidity/queue models and the slippage
model/parameters. The actual **application** of slippage to a market order at match time stays
in `exchange/orderbook`, since that's where matching happens and where book state lives.
`market/microstructure` supplies the model that `exchange/orderbook` consumes — it does not
duplicate or replace the matching/fill logic.

## Consequences

- `exchange/orderbook` remains the single place that mutates book state and produces fills,
  preserving ARCHITECTURE.md's rule that the matching engine has no knowledge of strategies,
  portfolios, or analytics — microstructure models are data/parameters flowing in, not another
  mutation path.
- Status: **planned, not yet implemented.**
