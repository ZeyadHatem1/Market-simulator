# ADR-005: Native matching engine crosses the pybind11 boundary as primitives only; Python remains the correctness oracle

## Context

CLAUDE.md step 11 / `ARCHITECTURE.md`'s "Future optimization boundary" name `MatchingEngine` +
`OrderBook` as the only components ever targeted for a C++ port; everything else (strategies,
portfolio, analytics, visualization) stays pure Python permanently. This is the last roadmap
step, explicitly gated on every earlier phase being correctness-verified in pure Python first,
and the roadmap note itself specifies the bar: "differential-test against Python as oracle" —
the deliverable is a native engine *proven identical* to the existing Python one, not a
replacement of it.

`cmake` was not installed on the development machine and this project has no other native-build
needs that would justify adding it, so the build-backend choice (setuptools vs.
CMake/scikit-build-core) was itself a real decision worth recording, not just the C++ design.

## Decision

1. **Primitives-only boundary.** `NativeOrderBook`/`NativeMatchingEngine` (bound via pybind11 as
   `market_sim.exchange.native._core`) take/return plain `str`/`int`/`double`/
   `std::optional<double>` — never Python `Order`/`Event` objects. A pure-Python adapter
   (`exchange/native/adapter.py`) presents the exact same public method signatures as
   `OrderBook`/`MatchingEngine`, converting at the boundary. `Order.__post_init__` already
   validates every order before it can reach the boundary, so no validation or exception
   translation is duplicated on the C++ side.
2. **Build backend: setuptools + `pybind11.setup_helpers.Pybind11Extension`, not CMake /
   scikit-build-core.** `cmake` isn't installed and one extension module with two source files
   doesn't justify introducing a new system-level build tool. `pybind11` itself is a
   build-time-only dependency (header-only; the compiled `.so` is self-contained) and is
   declared only in `pyproject.toml`'s `[build-system] requires`, never in
   `[project] dependencies`.
3. **Slippage arithmetic stays exclusively in `market/microstructure/SlippageModel`
   (unchanged).** The native engine does raw crossing only — it always fills at the resting
   order's exact price, i.e. the equivalent of `MatchingEngine(slippage_model=None)`. The
   Python adapter takes a liquidity snapshot (`book.ask_liquidity()`/`bid_liquidity()`) once
   before calling into C++ (one boundary crossing per market order, not per fill), then applies
   the existing, unmodified `SlippageModel.apply()` to each returned fill — identical semantics
   to `_match_market` today. This preserves ADR-004's split rather than re-litigating it, keeps
   the trivial bps arithmetic in exactly one place in the codebase (zero drift risk), and keeps
   the C++ engine's crossing logic free of any liquidity-dependent branching.
4. **Rollout is strictly opt-in.** `build_exchange()` is untouched; `build_native_exchange()` is
   a new, separate, additive entry point in `exchange/native/gateway.py`, reusing the existing
   `ExchangeGateway` unmodified (it's already duck-typed on `book`/`matching_engine`). The
   native module's import never fails: `NATIVE_AVAILABLE` is a flag checked at package-import
   time, and `NativeOrderBook`/`NativeMatchingEngine` additionally attempt the `_core` import
   lazily inside their own `__init__`, raising a clear `ImportError` there — not at
   `import market_sim` time — if the extension hasn't been built.
5. **Correctness gate: Python remains the oracle.** Every change to the native engine must pass
   `tests/exchange/test_native_differential.py` — scripted replay of the highest-value existing
   `OrderBook`/`MatchingEngine` scenarios (multi-level sweep, time priority, cancellation
   mid-sweep, partial-fill-preserves-seq-on-requeue, slippage direction and pre-trade-snapshot
   behavior) plus `np.random.default_rng`-seeded fuzzing (same pattern already used by
   `RandomBaseline`/`PoissonArrivalProcess` — no `hypothesis`, no new test dependency),
   asserting identical fills and full book state (including resting orders' `seq`, which is
   what actually catches a time-priority bug a price-only comparison would miss) after every
   step.

## Consequences

- `MatchingEngine`/`OrderBook`/`SlippageModel` in the pure-Python path: zero changes. All 208
  pre-existing tests are unaffected regardless of whether the native extension is built.
- Anyone without a C++ toolchain, without `pybind11` installed, or on a platform where the
  extension fails to build can still `pip install -e .` and use the whole simulator — the
  native path degrades to "unavailable" (differential tests auto-skip via
  `NATIVE_AVAILABLE`), never to a broken import. Verified directly: renaming the built `.so`
  aside and re-running `import market_sim` + the full test suite reproduces the pre-extension
  baseline exactly (208 passed, 0 errors).
- Adopting the native engine in a real simulation run is a manual opt-in
  (`build_native_exchange()` instead of `build_exchange()`) — no default behavior anywhere
  changes as a result of this ADR.
- No benchmarking/profiling was performed as part of this pass — that's Phase 4's job per
  CLAUDE.md's later-phases section. This ADR records a *correct* native engine, not a
  *measured-faster* one.
- Status: **implemented.** `src/market_sim/exchange/native/` (Python adapter + `cpp/` sources),
  `setup.py`, `pyproject.toml`'s `[build-system]` table, and
  `tests/exchange/test_native_differential.py` (19 tests: 9 scripted scenarios + 10 fuzz runs
  across 2 slippage configurations × 5 seeds × 500 steps each, all passing).
