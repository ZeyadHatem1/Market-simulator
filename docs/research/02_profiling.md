# Profiling — Matching Engine (Python vs. Native) and Monte Carlo Runner

Full methodology and code: [`notebooks/03_profiling.ipynb`](../../notebooks/03_profiling.ipynb).
Measurement only — no source changes made as part of this pass, per CLAUDE.md's "no premature
optimization" rule. One real, verified inefficiency was found; see Interpretation below for what
it is and why it wasn't fixed inline.

## Setup

`docs/decisions/ADR-005-native-matching-engine-boundary.md` names `MatchingEngine`/`OrderBook`
as the only components ever targeted for a C++ port, on the stated assumption that they're the
performance-critical hot path. This pass checks that assumption empirically:

1. **Matching engine, Python vs. native**: 20,000 identical orders (same fuzz shape as
   `tests/exchange/test_native_differential.py`'s differential fuzz test — ~80% limit / 20%
   market, random side, price scattered around a mid of 100, seed=7) replayed through
   `(OrderBook, MatchingEngine())` and `(NativeOrderBook, NativeMatchingEngine())`, both with no
   `slippage_model` (matching `MonteCarloRunner`'s own default), timed best-of-3.
2. **`MonteCarloRunner`**: 100 runs of `MomentumStrategy` (lookback=5) against a 250-step GBM
   path (`SimConfig`: μ=0.05, σ=0.20, dt=1/252, seed=42, seeds 1000-1099), the runner's normal
   `build_exchange()` (pure Python) path, `cProfile`'d.

## Results

**Matching engine — Python vs. native**: best=0.0827s (Python) vs. best=0.0394s (native) over
20,000 orders — a **2.10x** speedup.

**Matching engine — where the Python time goes** (`cProfile`, same 20,000-order replay,
cumulative time, 0.300s total):

| function | ncalls | cumtime | % of total |
|---|---:|---:|---:|
| `MatchingEngine._match_market` | 4,042 | 0.278s | 92.7% |
| `builtins.sum` | 4,042 | 0.275s | 91.7% |
| `OrderBook.ask_liquidity` | 2,009 | 0.151s | 50.3% |
| `OrderBook.bid_liquidity` | 2,033 | 0.124s | 41.3% |

**`MonteCarloRunner.run()`** (100 runs × 250 steps): elapsed=0.672s, 6.72ms/run.
`cProfile` over the same batch (2.151s total under profiling overhead):

| function | ncalls | cumtime | % of total |
|---|---:|---:|---:|
| `MatchingEngine._match_market` | 24,500 | 1.205s | 56.0% |
| `builtins.sum` | 24,500 | 0.937s | 43.6% |
| `OrderBook.ask_liquidity` | 12,420 | 0.491s | 22.8% |
| `OrderBook.bid_liquidity` | 12,080 | 0.453s | 21.1% |
| `uuid.uuid4` (via `Event.event_id` default) | 74,000 | 0.237s | 11.0% |

## Interpretation and caveats

- **The headline finding: `MatchingEngine._match_market` unconditionally snapshots
  `available_liquidity` via `OrderBook.bid_liquidity()`/`ask_liquidity()` — an O(book depth) sum
  over every resting order on one side — even when `self._slippage_model is None`, in which case
  the value is never read.** `MonteCarloRunner` never passes a `slippage_model`, so every one of
  its runs pays this cost for nothing: it accounts for ~92% of matching-engine time in the
  isolated replay and ~44% of total `MonteCarloRunner.run()` wall time in the batch profile
  above. This isn't a guess from the profile alone —
  `exchange/native/adapter.py`'s `NativeMatchingEngine.match()` already guards the equivalent
  snapshot behind `needs_slippage = self._slippage_model is not None and incoming.order_type ==
  OrderType.MARKET`, so the fix already exists, proven safe, on the native side of this exact
  codebase; the pure-Python `_match_market` in `exchange/matching/matching_engine.py` just never
  picked it up. A correctness-neutral fix (mirror the native adapter's guard) is a one-line,
  test-covered change — flagged here rather than applied inline, since `MatchingEngine` is
  called out in its own docstring as "the most important correctness boundary in the system" and
  any change to it should go through the same review the rest of this project's matching-engine
  work has (see `tests/exchange/test_matching_engine.py` and the differential suite). Left as an
  explicit, actionable follow-up rather than silently patched.
- **The 2.10x native speedup is a floor, not a ceiling, for `MonteCarloRunner` specifically.**
  `_run_once` always calls `build_exchange()`, never `build_native_exchange()` — there's no
  option today to run a Monte Carlo batch on the native engine at all. Once the dead-liquidity-
  snapshot cost above is removed from the Python path, the *relative* native speedup for market
  orders would likely shrink (the snapshot cost is identical in both paths' Python-side callers,
  so removing it narrows the gap this benchmark measured); wiring native support into
  `MonteCarloRunner` is a separate, larger decision (a new optional code path through an
  already-tested entry point) and out of scope for a profiling pass.
- **Secondary, smaller cost: `uuid.uuid4()` runs once per constructed `Event`**
  (`events/event.py`'s `event_id` default factory), 11% of total time in the Monte Carlo batch.
  Real, but an order of magnitude smaller than the liquidity-snapshot cost — not investigated
  further here.
- **These numbers are one machine, one Python build, best-of-3/single-profile-run** — not a
  statistically rigorous benchmark suite (no `pytest-benchmark`, no warm/cold JIT
  considerations beyond a single warm-up call). Good enough to establish relative magnitude
  (which cost dominates), not precise enough to cite as a fixed percentage going forward.
