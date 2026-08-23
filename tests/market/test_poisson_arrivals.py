import numpy as np
import pytest

from market_sim.core.config import PoissonArrivalConfig
from market_sim.market import PoissonArrivalProcess


def make_config(**overrides) -> PoissonArrivalConfig:
    base = dict(rate=10.0, n_arrivals=252, seed=42)
    base.update(overrides)
    return PoissonArrivalConfig(**base)


def make_process(config: PoissonArrivalConfig) -> PoissonArrivalProcess:
    return PoissonArrivalProcess(config=config)


# --- inter_arrival_times() tests ---


def test_inter_arrival_times_length_matches_n_arrivals():
    process = make_process(make_config(n_arrivals=100))
    gaps = process.inter_arrival_times()
    assert len(gaps) == 100


def test_inter_arrival_times_are_positive():
    process = make_process(make_config(n_arrivals=100))
    gaps = process.inter_arrival_times()
    assert np.all(gaps > 0)


def test_inter_arrival_times_same_seed_reproducible():
    config = make_config(seed=7)
    gaps_a = make_process(config).inter_arrival_times()
    gaps_b = make_process(config).inter_arrival_times()
    np.testing.assert_array_equal(gaps_a, gaps_b)


def test_inter_arrival_times_different_seeds_produce_different_gaps():
    gaps_a = make_process(make_config(seed=1)).inter_arrival_times()
    gaps_b = make_process(make_config(seed=2)).inter_arrival_times()
    assert not np.array_equal(gaps_a, gaps_b)


def test_mean_inter_arrival_time_converges_to_expected():
    # Law of large numbers: with enough draws, the sample mean of iid
    # Exponential(rate) gaps converges to 1/rate.
    config = make_config(rate=10.0, n_arrivals=200_000, seed=42)
    process = make_process(config)
    gaps = process.inter_arrival_times()
    assert gaps.mean() == pytest.approx(1.0 / 10.0, rel=0.02)


# --- arrival_times() tests ---


def test_arrival_times_length_matches_n_arrivals():
    process = make_process(make_config(n_arrivals=100))
    arrivals = process.arrival_times()
    assert len(arrivals) == 100


def test_arrival_times_strictly_increasing():
    process = make_process(make_config(n_arrivals=100))
    arrivals = process.arrival_times()
    assert np.all(np.diff(arrivals) > 0)


def test_arrival_times_equals_cumsum_of_inter_arrival_times():
    process = make_process(make_config(n_arrivals=100))
    arrivals = process.arrival_times()
    gaps = process.inter_arrival_times()
    np.testing.assert_array_equal(arrivals, np.cumsum(gaps))


def test_arrival_times_same_seed_reproducible():
    config = make_config(seed=99)
    arrivals_a = make_process(config).arrival_times()
    arrivals_b = make_process(config).arrival_times()
    np.testing.assert_array_equal(arrivals_a, arrivals_b)


def test_arrival_times_different_seeds_produce_different_paths():
    arrivals_a = make_process(make_config(seed=1)).arrival_times()
    arrivals_b = make_process(make_config(seed=2)).arrival_times()
    assert not np.array_equal(arrivals_a, arrivals_b)


def test_higher_rate_produces_more_arrivals_per_unit_time():
    # Same n_arrivals, higher rate => shorter expected gaps => the whole
    # arrival sequence finishes sooner.
    slow = make_process(make_config(rate=1.0, n_arrivals=1000, seed=42)).arrival_times()
    fast = make_process(
        make_config(rate=50.0, n_arrivals=1000, seed=42)
    ).arrival_times()
    assert fast[-1] < slow[-1]


# --- PoissonArrivalConfig validation tests ---


def test_invalid_rate_raises():
    with pytest.raises(ValueError):
        make_config(rate=0.0)


def test_negative_rate_raises():
    with pytest.raises(ValueError):
        make_config(rate=-1.0)


def test_invalid_n_arrivals_raises():
    with pytest.raises(ValueError):
        make_config(n_arrivals=0)
