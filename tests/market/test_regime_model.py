import numpy as np
import pytest

from market_sim.core.config import RegimeConfig, SimConfig
from market_sim.core.clock import SimulationClock
from market_sim.core.models import EventType
from market_sim.market import PriceGenerator, VolatilityRegimeModel


def make_config(**overrides) -> RegimeConfig:
    base = dict(
        instrument="SIM",
        initial_price=100.0,
        regimes={
            "low_vol": (0.05, 0.15),
            "high_vol": (0.0, 0.50),
        },
        transition_matrix=[
            [0.95, 0.05],
            [0.05, 0.95],
        ],
        initial_regime="low_vol",
        n_steps=252,
        dt=1 / 252,
        seed=42,
    )
    base.update(overrides)
    return RegimeConfig(**base)


def make_model(config: RegimeConfig) -> VolatilityRegimeModel:
    return VolatilityRegimeModel(config=config, clock=SimulationClock())


# --- generate() tests ---

def test_output_length_matches_n_steps():
    config = make_config(n_steps=100)
    model = make_model(config)
    events = model.generate()
    assert len(events) == 100


def test_all_events_are_market_updates():
    model = make_model(make_config())
    events = model.generate()
    assert all(e.event_type == EventType.MARKET_UPDATE for e in events)


def test_all_events_have_correct_instrument():
    model = make_model(make_config(instrument="TEST"))
    events = model.generate()
    assert all(e.data["instrument"] == "TEST" for e in events)


def test_same_seed_produces_identical_events():
    config = make_config(seed=7)
    events_a = make_model(config).generate()
    events_b = make_model(config).generate()
    prices_a = [e.data["price"] for e in events_a]
    prices_b = [e.data["price"] for e in events_b]
    assert prices_a == prices_b


def test_different_seeds_produce_different_paths():
    events_a = make_model(make_config(seed=1)).generate()
    events_b = make_model(make_config(seed=2)).generate()
    prices_a = [e.data["price"] for e in events_a]
    prices_b = [e.data["price"] for e in events_b]
    assert prices_a != prices_b


def test_timestamps_advance_monotonically():
    model = make_model(make_config(n_steps=50))
    events = model.generate()
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)
    assert all(t > 0 for t in timestamps)


def test_sequences_are_unique_and_increasing():
    model = make_model(make_config(n_steps=50))
    events = model.generate()
    sequences = [e.sequence for e in events]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))


# --- price_path() tests ---

def test_price_path_length():
    config = make_config(n_steps=100)
    model = make_model(config)
    path = model.price_path()
    assert len(path) == 101


def test_price_path_starts_at_initial_price():
    config = make_config(initial_price=50.0)
    model = make_model(config)
    path = model.price_path()
    assert path[0] == 50.0


def test_price_path_same_seed_reproducible():
    config = make_config(seed=99)
    path_a = make_model(config).price_path()
    path_b = make_model(config).price_path()
    np.testing.assert_array_equal(path_a, path_b)


# --- regime_path() tests ---

def test_regime_path_length():
    config = make_config(n_steps=100)
    model = make_model(config)
    path = model.regime_path()
    assert len(path) == 100


def test_regime_path_starts_at_initial_regime():
    config = make_config(initial_regime="high_vol")
    model = make_model(config)
    path = model.regime_path()
    assert path[0] == "high_vol"


def test_regime_path_values_are_all_known_regimes():
    config = make_config()
    model = make_model(config)
    path = model.regime_path()
    assert set(path) <= {"low_vol", "high_vol"}


def test_regime_path_same_seed_reproducible():
    config = make_config(seed=99)
    path_a = make_model(config).regime_path()
    path_b = make_model(config).regime_path()
    assert list(path_a) == list(path_b)


def test_regime_path_consistent_with_price_path():
    # regime_path() and price_path() are independently re-derived from the
    # same seeded simulation routine, so calling them separately on the same
    # config must agree with each other: steps labeled high_vol should show
    # visibly larger moves than steps labeled low_vol on that same path.
    config = make_config(
        regimes={"low_vol": (0.0, 0.01), "high_vol": (0.0, 5.0)},
        transition_matrix=[[0.9, 0.1], [0.1, 0.9]],
        initial_regime="low_vol",
        n_steps=500,
        seed=13,
    )
    model = make_model(config)
    regimes = model.regime_path()
    prices = model.price_path()
    log_returns = np.diff(np.log(prices))

    low_vol_moves = np.abs(log_returns[regimes == "low_vol"])
    high_vol_moves = np.abs(log_returns[regimes == "high_vol"])
    assert high_vol_moves.mean() > low_vol_moves.mean()


# --- correctness: sticky single-regime reduces to plain GBM ---

def test_always_self_looping_regime_matches_plain_gbm():
    mu, sigma, seed, n_steps, dt = 0.08, 0.25, 5, 200, 1 / 252
    config = make_config(
        regimes={"only": (mu, sigma)},
        transition_matrix=[[1.0]],
        initial_regime="only",
        n_steps=n_steps,
        dt=dt,
        seed=seed,
        initial_price=100.0,
    )
    regime_path = make_model(config).price_path()

    gbm_config = SimConfig(
        instrument="SIM",
        initial_price=100.0,
        mu=mu,
        sigma=sigma,
        n_steps=n_steps,
        dt=dt,
        seed=seed,
        initial_capital=100_000.0,
    )
    gbm_path = PriceGenerator(config=gbm_config, clock=SimulationClock()).price_path()

    np.testing.assert_allclose(regime_path, gbm_path)


def test_zero_self_transition_alternates_every_step():
    config = make_config(
        regimes={"low_vol": (0.05, 0.15), "high_vol": (0.0, 0.50)},
        transition_matrix=[[0.0, 1.0], [1.0, 0.0]],
        initial_regime="low_vol",
        n_steps=20,
    )
    path = make_model(config).regime_path()
    expected = ["low_vol" if i % 2 == 0 else "high_vol" for i in range(20)]
    assert list(path) == expected


def test_high_vol_regime_produces_larger_moves_than_low_vol():
    # Not a statistical fluke check on a single draw: compare realized
    # variance across many steps for two runs that only differ in which
    # regime is forced to be active for the entire path.
    low_config = make_config(
        regimes={"low_vol": (0.0, 0.05), "high_vol": (0.0, 0.05)},
        transition_matrix=[[1.0, 0.0], [0.0, 1.0]],
        initial_regime="low_vol",
        n_steps=2000,
        seed=1,
    )
    high_config = make_config(
        regimes={"low_vol": (0.0, 0.05), "high_vol": (0.0, 2.0)},
        transition_matrix=[[1.0, 0.0], [0.0, 1.0]],
        initial_regime="high_vol",
        n_steps=2000,
        seed=1,
    )
    low_path = make_model(low_config).price_path()
    high_path = make_model(high_config).price_path()

    low_log_returns = np.diff(np.log(low_path))
    high_log_returns = np.diff(np.log(high_path))
    assert np.std(high_log_returns) > np.std(low_log_returns)


# --- RegimeConfig validation tests ---

def test_empty_regimes_raises():
    with pytest.raises(ValueError):
        make_config(regimes={}, transition_matrix=[], initial_regime="low_vol")


def test_negative_sigma_raises():
    with pytest.raises(ValueError):
        make_config(regimes={"low_vol": (0.05, -0.1), "high_vol": (0.0, 0.5)})


def test_unknown_initial_regime_raises():
    with pytest.raises(ValueError):
        make_config(initial_regime="does_not_exist")


def test_transition_matrix_wrong_row_count_raises():
    with pytest.raises(ValueError):
        make_config(transition_matrix=[[0.95, 0.05]])


def test_transition_matrix_wrong_column_count_raises():
    with pytest.raises(ValueError):
        make_config(transition_matrix=[[0.95, 0.05, 0.0], [0.05, 0.95, 0.0]])


def test_transition_matrix_negative_probability_raises():
    with pytest.raises(ValueError):
        make_config(transition_matrix=[[1.05, -0.05], [0.05, 0.95]])


def test_transition_matrix_row_not_summing_to_one_raises():
    with pytest.raises(ValueError):
        make_config(transition_matrix=[[0.5, 0.5], [0.5, 0.4]])


def test_invalid_n_steps_raises():
    with pytest.raises(ValueError):
        make_config(n_steps=0)


def test_invalid_dt_raises():
    with pytest.raises(ValueError):
        make_config(dt=0.0)
