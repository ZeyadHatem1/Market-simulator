# Profiling — Matching Engine (Python vs. Native) and Monte Carlo Runner

Full methodology and code: [`notebooks/03_profiling.ipynb`](../../notebooks/03_profiling.ipynb).
This pass found a real inefficiency and fixed it in the same pass (a one-line, test-covered
change mirroring an existing guard already proven safe on the native side of this codebase —
not a speculative optimization). All numbers below reflect the fixed code unless labeled
"before."

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

## The bug found, and the fix

`MatchingEngine._match_market` (`exchange/matching/matching_engine.py`) unconditionally
snapshotted `available_liquidity` via `OrderBook.bid_liquidity()`/`ask_liquidity()` — an
O(book depth) sum over every resting order on one side — even when `self._slippage_model is
None`, in which case the value was never read (it's only used inside the `if
self._slippage_model is not None` branch below). `MonteCarloRunner` never passes a
`slippage_model`, so every one of its runs paid this cost for nothing.

This wasn't a guess from the profile alone: `exchange/native/adapter.py`'s
`NativeMatchingEngine.match()` already guarded the equivalent snapshot behind `needs_slippage =
self._slippage_model is not None and incoming.order_type == OrderType.MARKET` — the fix already
existed, proven safe, on the native side of this exact codebase; the pure-Python path just never
picked it up. **Fixed** by mirroring that guard in `_match_market` — `available_liquidity` is
now only computed when `self._slippage_model is not None`. Behavior is unchanged (verified by
the full 342-test suite, including the native differential suite, all still passing); only the
dead computation was removed.

## Results

**Matching engine — Python, before vs. after the fix** (best-of-3, 20,000-order replay):

| | before | after | change |
|---|---:|---:|---:|
| Python matching engine | 0.0827s | 0.0061s | **13.6x faster** |
| Native matching engine | 0.0393s | 0.0393s | unchanged (never affected) |

**Matching engine — where the Python time goes now** (`cProfile`, same replay, 0.021s total —
down from 0.300s before the fix):

| function | ncalls | cumtime | % of total |
|---|---:|---:|---:|
| `MatchingEngine.match` | 20,000 | 0.016s | 76% |
| `MatchingEngine._match_limit` | 15,958 | 0.011s | 52% |
| `Order.is_filled` | 35,958 | 0.007s | 33% |
| `Order.remaining_quantity` | 35,958 | 0.003s | 14% |
| `MatchingEngine._match_market` | 4,042 | 0.001s | 5% |

The remaining time is now dominated by real matching logic, not dead computation.

**`MonteCarloRunner.run()`, before vs. after** (100 runs × 250 steps):

| | before | after | change |
|---|---:|---:|---:|
| elapsed | 0.672s | 0.413s | **1.6x faster** |
| per run | 6.72ms | 4.13ms | |

## The surprising second finding: native is now *slower* than Python on this workload

With the dead computation removed, **pure Python outperforms the native engine by ~6.4x** on
the same 20,000-order replay (0.0061s vs. 0.0393s) — the opposite of what the pre-fix numbers
suggested (a 2.10x native lead, which turned out to be entirely an artifact of Python paying an
unnecessary O(depth) cost the native adapter's `needs_slippage` guard already avoided).

This is workload-shape-dependent, not a blanket "the native port isn't worth it" conclusion:

- **Every order in this benchmark is one independent `match()` call**, i.e. one Python↔C++
  boundary crossing via pybind11 per order, for orders that mostly rest or cross only 1-2
  price levels. Once Python's own per-order cost is this small, the fixed per-call marshalling
  overhead of crossing into C++ and back dominates the native side's runtime.
- A workload with **fewer orders but deeper multi-level sweeps per `match()` call** (many fills
  concentrated inside a single boundary crossing, e.g. a large market order sweeping 20+ price
  levels) would amortize that crossing cost over more work per call, and should favor native —
  this benchmark's random fuzz mix (mean fill count well under 1 per order, per the `ncalls`
  columns above) doesn't exercise that case. Not measured here; a natural next step if this
  matters for a specific workload, not pursued in this pass.
- Native correctness is unaffected either way — `tests/exchange/test_native_differential.py`'s
  19 tests, unrelated to this profiling pass, continue to enforce byte-identical fills/book
  state against the same 5,000-operation seeded fuzz suite.

## Other findings, not pursued

- **`MonteCarloRunner` has no option to use the native engine at all** — `_run_once` always
  calls `build_exchange()`, never `build_native_exchange()`. A real architectural gap, and per
  the reversal above, not obviously worth closing for this workload shape without first
  measuring a deeper-sweep scenario. Left as a documented gap, not a fix.
- **`uuid.uuid4()` runs once per constructed `Event`** (`events/event.py`'s `event_id` default
  factory) — now ~20% of remaining `MonteCarloRunner` wall time (it was proportionally smaller
  before, hidden behind the much larger liquidity-snapshot cost). Real, an order of magnitude
  smaller than what was fixed, not investigated further here.

## Caveats

- **These numbers are one machine, one Python build, best-of-3/single-profile-run** — not a
  statistically rigorous benchmark suite (no `pytest-benchmark`, no warm/cold JIT
  considerations beyond a single warm-up call). Good enough to establish relative magnitude and
  direction (which cost dominates, which engine wins), not precise enough to cite as fixed
  percentages going forward.
- **The native-vs-Python reversal is specific to this order mix.** Treat "native is 2.10x
  faster" (the pre-fix, since-corrected headline) as retracted, and "Python is 6.4x faster"
  (this pass's number) as equally workload-specific — neither is a general claim about the two
  engines.
