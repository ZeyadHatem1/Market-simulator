import numpy as np
import pytest

from market_sim.core.config import OUConfig
from market_sim.core.clock import SimulationClock
from market_sim.core.models import EventType
from market_sim.market import OrnsteinUhlenbeckProcess


def make_config(**overrides) -> OUConfig:
    base = dict(
        instrument="SIM",
        initial_value=100.0,
        theta=5.0,
        mu=100.0,
        sigma=2.0,
        n_steps=252,
        dt=1 / 252,
        seed=42,
    )
    base.update(overrides)
    return OUConfig(**base)


def make_process(config: OUConfig) -> OrnsteinUhlenbeckProcess:
    return OrnsteinUhlenbeckProcess(config=config, clock=SimulationClock())


# --- generate() tests ---


def test_output_length_matches_n_steps():
    config = make_config(n_steps=100)
    process = make_process(config)
    events = process.generate()
    assert len(events) == 100


def test_all_events_are_market_updates():
    process = make_process(make_config())
    events = process.generate()
    assert all(e.event_type == EventType.MARKET_UPDATE for e in events)


def test_all_events_have_correct_instrument():
    process = make_process(make_config(instrument="TEST"))
    events = process.generate()
    assert all(e.data["instrument"] == "TEST" for e in events)


def test_same_seed_produces_identical_events():
    config = make_config(seed=7)
    events_a = make_process(config).generate()
    events_b = make_process(config).generate()
    values_a = [e.data["price"] for e in events_a]
    values_b = [e.data["price"] for e in events_b]
    assert values_a == values_b


def test_different_seeds_produce_different_paths():
    events_a = make_process(make_config(seed=1)).generate()
    events_b = make_process(make_config(seed=2)).generate()
    values_a = [e.data["price"] for e in events_a]
    values_b = [e.data["price"] for e in events_b]
    assert values_a != values_b


def test_timestamps_advance_monotonically():
    process = make_process(make_config(n_steps=50))
    events = process.generate()
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)
    assert all(t > 0 for t in timestamps)


def test_sequences_are_unique_and_increasing():
    process = make_process(make_config(n_steps=50))
    events = process.generate()
    sequences = [e.sequence for e in events]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))


# --- value_path() tests ---


def test_value_path_length():
    config = make_config(n_steps=100)
    process = make_process(config)
    path = process.value_path()
    # n_steps + 1 because index 0 is the initial value
    assert len(path) == 101


def test_value_path_starts_at_initial_value():
    config = make_config(initial_value=50.0)
    process = make_process(config)
    path = process.value_path()
    assert path[0] == 50.0


def test_value_path_same_seed_reproducible():
    config = make_config(seed=99)
    path_a = make_process(config).value_path()
    path_b = make_process(config).value_path()
    np.testing.assert_array_equal(path_a, path_b)


# --- mean-reversion correctness ---


def test_zero_volatility_converges_deterministically_to_mu():
    # With sigma=0 the process is a deterministic ODE solution — this is the
    # property that distinguishes OU from GBM and must hold exactly, not
    # just "on average" over a stochastic sample.
    config = make_config(
        sigma=0.0, theta=5.0, initial_value=50.0, mu=10.0, n_steps=1000, dt=0.01
    )
    process = make_process(config)
    path = process.value_path()
    assert path[-1] == pytest.approx(10.0, abs=1e-6)


def test_process_pulls_toward_mean_over_time():
    config = make_config(
        sigma=0.0, theta=5.0, initial_value=200.0, mu=100.0, n_steps=100, dt=1 / 252
    )
    process = make_process(config)
    path = process.value_path()
    distances = np.abs(path - 100.0)
    assert np.all(np.diff(distances) <= 0)


# --- OUConfig validation tests ---


def test_invalid_theta_raises():
    with pytest.raises(ValueError):
        make_config(theta=0.0)


def test_invalid_sigma_raises():
    with pytest.raises(ValueError):
        make_config(sigma=-0.1)


def test_invalid_n_steps_raises():
    with pytest.raises(ValueError):
        make_config(n_steps=0)


def test_invalid_dt_raises():
    with pytest.raises(ValueError):
        make_config(dt=0.0)
