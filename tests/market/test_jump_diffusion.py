import numpy as np
import pytest

from market_sim.core.config import JumpDiffusionConfig, SimConfig
from market_sim.core.clock import SimulationClock
from market_sim.core.models import EventType
from market_sim.market import JumpDiffusionProcess, PriceGenerator


def make_config(**overrides) -> JumpDiffusionConfig:
    base = dict(
        instrument="SIM",
        initial_price=100.0,
        mu=0.05,
        sigma=0.20,
        jump_intensity=1.0,
        jump_mean=-0.02,
        jump_std=0.05,
        n_steps=252,
        dt=1 / 252,
        seed=42,
    )
    base.update(overrides)
    return JumpDiffusionConfig(**base)


def make_process(config: JumpDiffusionConfig) -> JumpDiffusionProcess:
    return JumpDiffusionProcess(config=config, clock=SimulationClock())


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


def test_all_prices_are_positive():
    # exp()-based update — jumps or not, price can never hit zero or go negative
    process = make_process(make_config(jump_intensity=50.0, jump_std=0.3))
    events = process.generate()
    assert all(e.data["price"] > 0 for e in events)


def test_same_seed_produces_identical_events():
    config = make_config(seed=7)
    events_a = make_process(config).generate()
    events_b = make_process(config).generate()
    prices_a = [e.data["price"] for e in events_a]
    prices_b = [e.data["price"] for e in events_b]
    assert prices_a == prices_b


def test_different_seeds_produce_different_paths():
    events_a = make_process(make_config(seed=1)).generate()
    events_b = make_process(make_config(seed=2)).generate()
    prices_a = [e.data["price"] for e in events_a]
    prices_b = [e.data["price"] for e in events_b]
    assert prices_a != prices_b


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


# --- price_path() tests ---

def test_price_path_length():
    config = make_config(n_steps=100)
    process = make_process(config)
    path = process.price_path()
    assert len(path) == 101


def test_price_path_starts_at_initial_price():
    config = make_config(initial_price=200.0)
    process = make_process(config)
    path = process.price_path()
    assert path[0] == 200.0


def test_price_path_all_positive():
    process = make_process(make_config(jump_intensity=50.0, jump_std=0.3))
    path = process.price_path()
    assert np.all(path > 0)


def test_price_path_same_seed_reproducible():
    config = make_config(seed=99)
    path_a = make_process(config).price_path()
    path_b = make_process(config).price_path()
    np.testing.assert_array_equal(path_a, path_b)


# --- jump-diffusion-specific correctness ---

def test_zero_jump_intensity_matches_pure_gbm():
    # With jump_intensity=0, Poisson(0) is always 0, so this must reduce to
    # exactly the same path as plain GBM for identical mu/sigma/seed — using
    # the already-tested PriceGenerator as the correctness oracle, rather
    # than re-deriving the formula by hand in the test.
    gbm_config = SimConfig(
        instrument="SIM",
        initial_price=100.0,
        mu=0.05,
        sigma=0.20,
        n_steps=100,
        dt=1 / 252,
        seed=42,
        initial_capital=100_000.0,
    )
    gbm_path = PriceGenerator(config=gbm_config, clock=SimulationClock()).price_path()

    jd_config = make_config(
        jump_intensity=0.0, mu=0.05, sigma=0.20, n_steps=100, dt=1 / 252, seed=42,
        initial_price=100.0,
    )
    jd_path = make_process(jd_config).price_path()

    np.testing.assert_allclose(gbm_path, jd_path)


def test_jumps_produce_a_different_path_than_no_jumps():
    no_jumps = make_config(jump_intensity=0.0)
    with_jumps = make_config(jump_intensity=50.0, jump_mean=0.0, jump_std=0.1)
    path_a = make_process(no_jumps).price_path()
    path_b = make_process(with_jumps).price_path()
    assert not np.allclose(path_a, path_b)


# --- JumpDiffusionConfig validation tests ---

def test_invalid_initial_price_raises():
    with pytest.raises(ValueError):
        make_config(initial_price=0.0)


def test_invalid_sigma_raises():
    with pytest.raises(ValueError):
        make_config(sigma=-0.1)


def test_invalid_jump_intensity_raises():
    with pytest.raises(ValueError):
        make_config(jump_intensity=-1.0)


def test_invalid_jump_std_raises():
    with pytest.raises(ValueError):
        make_config(jump_std=-0.1)


def test_invalid_n_steps_raises():
    with pytest.raises(ValueError):
        make_config(n_steps=0)
