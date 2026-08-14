import numpy as np
import pytest

from market_sim.core.config import ShockConfig
from market_sim.market import ShockModel


def make_config(**overrides) -> ShockConfig:
    base = dict(
        shock_intensity=2.0,
        magnitude_range=(0.1, 0.4),
        duration_range=(3, 15),
        n_steps=252,
        dt=1 / 252,
        seed=42,
    )
    base.update(overrides)
    return ShockConfig(**base)


def make_model(config: ShockConfig) -> ShockModel:
    return ShockModel(config=config)


# --- liquidity_multiplier_path() shape/determinism tests ---

def test_length_matches_n_steps():
    model = make_model(make_config(n_steps=100))
    path = model.liquidity_multiplier_path()
    assert len(path) == 100


def test_values_are_in_valid_range():
    model = make_model(make_config(n_steps=2000, shock_intensity=10.0))
    path = model.liquidity_multiplier_path()
    assert np.all(path > 0)
    assert np.all(path <= 1.0)


def test_same_seed_reproducible():
    config = make_config(seed=7)
    path_a = make_model(config).liquidity_multiplier_path()
    path_b = make_model(config).liquidity_multiplier_path()
    np.testing.assert_array_equal(path_a, path_b)


def test_different_seeds_produce_different_paths():
    path_a = make_model(make_config(seed=1)).liquidity_multiplier_path()
    path_b = make_model(make_config(seed=2)).liquidity_multiplier_path()
    assert not np.array_equal(path_a, path_b)


def test_negligible_intensity_produces_no_shocks():
    # Expected shock count here is ~4e-8 — effectively zero for a fixed seed.
    config = make_config(shock_intensity=1e-6, n_steps=10, seed=42)
    path = make_model(config).liquidity_multiplier_path()
    np.testing.assert_array_equal(path, np.ones(10))


# --- shocked values stay within the configured magnitude range ---

def test_shocked_values_within_magnitude_range():
    config = make_config(
        n_steps=2000, shock_intensity=10.0, magnitude_range=(0.2, 0.6)
    )
    path = make_model(config).liquidity_multiplier_path()
    shocked = path[path < 1.0]
    assert shocked.size > 0  # sanity: this config must actually produce shocks
    assert np.all(shocked >= 0.2)
    assert np.all(shocked <= 0.6)


# --- duration_range and magnitude_range affect the path in the expected direction ---

def test_longer_duration_produces_at_least_as_many_shocked_steps():
    # With the same seed, shock start positions/counts/magnitudes are drawn
    # identically regardless of duration_range (duration is a separate draw
    # that only extends each window's end) — so every shocked step in the
    # short-duration run is also shocked in the long-duration run.
    common = dict(shock_intensity=5.0, n_steps=1000, seed=42)
    short_path = make_model(make_config(duration_range=(1, 1), **common)).liquidity_multiplier_path()
    long_path = make_model(make_config(duration_range=(20, 20), **common)).liquidity_multiplier_path()
    assert (long_path < 1.0).sum() >= (short_path < 1.0).sum()


def test_milder_magnitude_range_produces_higher_multipliers():
    # Same reasoning: shock positions/durations are identical across the two
    # configs (magnitude is drawn after start/duration, doesn't change how
    # many draws happen), so this compares the same shocked windows directly.
    common = dict(shock_intensity=5.0, n_steps=1000, seed=42, duration_range=(3, 15))
    harsh_path = make_model(make_config(magnitude_range=(0.05, 0.05), **common)).liquidity_multiplier_path()
    mild_path = make_model(make_config(magnitude_range=(0.9, 0.9), **common)).liquidity_multiplier_path()
    assert np.all(mild_path >= harsh_path)
    assert mild_path.mean() > harsh_path.mean()


# --- ShockConfig validation tests ---

def test_zero_shock_intensity_raises():
    with pytest.raises(ValueError):
        make_config(shock_intensity=0.0)


def test_negative_shock_intensity_raises():
    with pytest.raises(ValueError):
        make_config(shock_intensity=-1.0)


def test_magnitude_range_lo_not_positive_raises():
    with pytest.raises(ValueError):
        make_config(magnitude_range=(0.0, 0.4))


def test_magnitude_range_lo_greater_than_hi_raises():
    with pytest.raises(ValueError):
        make_config(magnitude_range=(0.5, 0.4))


def test_magnitude_range_hi_above_one_raises():
    with pytest.raises(ValueError):
        make_config(magnitude_range=(0.1, 1.5))


def test_duration_range_lo_below_one_raises():
    with pytest.raises(ValueError):
        make_config(duration_range=(0, 5))


def test_duration_range_lo_greater_than_hi_raises():
    with pytest.raises(ValueError):
        make_config(duration_range=(10, 5))


def test_invalid_n_steps_raises():
    with pytest.raises(ValueError):
        make_config(n_steps=0)


def test_invalid_dt_raises():
    with pytest.raises(ValueError):
        make_config(dt=0.0)
