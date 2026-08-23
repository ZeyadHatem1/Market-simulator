import numpy as np
import pytest

from market_sim.core.config import SimConfig
from market_sim.core.clock import SimulationClock
from market_sim.core.models import EventType
from market_sim.market import PriceGenerator


def make_config(**overrides) -> SimConfig:
    base = dict(
        instrument="SIM",
        initial_price=100.0,
        mu=0.05,
        sigma=0.20,
        n_steps=252,
        dt=1 / 252,
        seed=42,
        initial_capital=100_000.0,
    )
    base.update(overrides)
    return SimConfig(**base)


def make_generator(config: SimConfig) -> PriceGenerator:
    return PriceGenerator(config=config, clock=SimulationClock())


# --- generate() tests ---


def test_output_length_matches_n_steps():
    config = make_config(n_steps=100)
    gen = make_generator(config)
    events = gen.generate()
    assert len(events) == 100


def test_all_events_are_market_updates():
    gen = make_generator(make_config())
    events = gen.generate()
    assert all(e.event_type == EventType.MARKET_UPDATE for e in events)


def test_all_events_have_correct_instrument():
    gen = make_generator(make_config(instrument="TEST"))
    events = gen.generate()
    assert all(e.data["instrument"] == "TEST" for e in events)


def test_all_prices_are_positive():
    # GBM via exp() can never produce zero or negative prices
    gen = make_generator(make_config())
    events = gen.generate()
    assert all(e.data["price"] > 0 for e in events)


def test_same_seed_produces_identical_events():
    config = make_config(seed=7)
    events_a = make_generator(config).generate()
    events_b = make_generator(config).generate()
    prices_a = [e.data["price"] for e in events_a]
    prices_b = [e.data["price"] for e in events_b]
    assert prices_a == prices_b


def test_different_seeds_produce_different_paths():
    events_a = make_generator(make_config(seed=1)).generate()
    events_b = make_generator(make_config(seed=2)).generate()
    prices_a = [e.data["price"] for e in events_a]
    prices_b = [e.data["price"] for e in events_b]
    assert prices_a != prices_b


def test_timestamps_advance_monotonically():
    gen = make_generator(make_config(n_steps=50))
    events = gen.generate()
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)
    assert all(t > 0 for t in timestamps)


def test_sequences_are_unique_and_increasing():
    gen = make_generator(make_config(n_steps=50))
    events = gen.generate()
    sequences = [e.sequence for e in events]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))


# --- price_path() tests ---


def test_price_path_length():
    config = make_config(n_steps=100)
    gen = make_generator(config)
    path = gen.price_path()
    # n_steps + 1 because index 0 is the initial price
    assert len(path) == 101


def test_price_path_starts_at_initial_price():
    config = make_config(initial_price=200.0)
    gen = make_generator(config)
    path = gen.price_path()
    assert path[0] == 200.0


def test_price_path_all_positive():
    gen = make_generator(make_config())
    path = gen.price_path()
    assert np.all(path > 0)


def test_price_path_same_seed_reproducible():
    config = make_config(seed=99)
    path_a = make_generator(config).price_path()
    path_b = make_generator(config).price_path()
    np.testing.assert_array_equal(path_a, path_b)


# --- SimConfig validation tests ---


def test_invalid_initial_price_raises():
    with pytest.raises(ValueError):
        make_config(initial_price=0.0)


def test_invalid_sigma_raises():
    with pytest.raises(ValueError):
        make_config(sigma=-0.1)


def test_invalid_n_steps_raises():
    with pytest.raises(ValueError):
        make_config(n_steps=0)
