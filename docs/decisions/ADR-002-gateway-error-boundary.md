# ADR-002: Malformed-order rejection happens in ExchangeGateway, not EventLoop

## Context

`EventLoop.dispatch()` (`core/engine/event_loop.py`) has no exception handling at all, and
`RuntimeEngine.start()` doesn't add any either — any handler exception propagates and kills the
entire simulation run. Once `ExchangeGateway` started handling real `ORDER_SUBMIT`/`ORDER_CANCEL`
events, a single malformed order (e.g. from a future strategy bug) would otherwise abort an
entire multi-day backtest over one bad input.

## Decision

`ExchangeGateway.handle_order_submit` / `handle_order_cancel` catch `OrderValidationError` and
`ValueError` (the latter from `Order.__post_init__`'s domain checks — quantity/price validity)
before any book mutation. The rejected event is recorded to `gateway.rejected_orders` and logged
as a warning; the handler returns instead of raising. Rejection happens strictly before any book
mutation, so it cannot corrupt matching state or determinism for any other order.

This is currently the **only** place in the system hardened this way. A bug inside
`MatchingEngine` itself is still left to crash loudly — that represents a real invariant
violation (a correctness bug in trusted code), not recoverable bad input from upstream.

## Consequences

- A malformed order never crashes the run and never touches book state.
- If `strategies/` later registers its own `EventLoop` handlers (e.g. `on_fill`), they need
  equivalent treatment, or `EventLoop` needs a documented dispatch-level exception policy.
  Currently undecided — revisit when Strategy engine v1 lands.
