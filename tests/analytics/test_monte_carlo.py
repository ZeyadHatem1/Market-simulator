import dataclasses

import numpy as np
import pytest

from market_sim.analytics.monte_carlo import MonteCarloRunner
from market_sim.core.config import RegimeConfig, ShockConfig, SimConfig
from market_sim.market.generators import PriceGenerator
from market_sim.market.regimes import VolatilityRegimeModel
from market_sim.strategies import MomentumStrategy, RandomBaseline

BASE_SIM_CONFIG = SimConfig(
    instrument="SIM",
    initial_price=100.0,
    mu=0.05,
    sigma=0.20,
    n_steps=20,
    dt=1 / 252,
    seed=42,
    initial_capital=100_000.0,
)


def _gbm_factory(config=BASE_SIM_CONFIG):
    def factory(seed, clock):
        return PriceGenerator(dataclasses.replace(config, seed=seed), clock)

    return factory


def _momentum_factory():
    return lambda clock, order_id_factory: MomentumStrategy(
        strategy_id="mc",
        initial_cash=100_000.0,
        clock=clock,
        order_id_factory=order_id_factory,
        lookback=3,
        trade_size=10.0,
    )


def _random_baseline_factory():
    return lambda clock, order_id_factory: RandomBaseline(
        strategy_id="mc",
        initial_cash=100_000.0,
        clock=clock,
        order_id_factory=order_id_factory,
        trade_size=10.0,
        seed=7,
    )


def test_run_produces_one_pnl_and_curve_per_run():
    runner = MonteCarloRunner(
        price_generator_factory=_gbm_factory(),
        strategy_factory=_momentum_factory(),
        n_runs=5,
        base_seed=100,
        initial_cash=100_000.0,
    )

    result = runner.run()

    assert result.final_pnl.shape == (5,)
    assert len(result.equity_curves) == 5


def test_run_is_deterministic():
    def build():
        return MonteCarloRunner(
            price_generator_factory=_gbm_factory(),
            strategy_factory=_momentum_factory(),
            n_runs=5,
            base_seed=100,
            initial_cash=100_000.0,
        )

    result_a = build().run()
    result_b = build().run()

    np.testing.assert_allclose(result_a.final_pnl, result_b.final_pnl)


def test_different_seeds_produce_different_pnl():
    result_a = MonteCarloRunner(
        price_generator_factory=_gbm_factory(),
        strategy_factory=_random_baseline_factory(),
        n_runs=5,
        base_seed=100,
        initial_cash=100_000.0,
    ).run()
    result_b = MonteCarloRunner(
        price_generator_factory=_gbm_factory(),
        strategy_factory=_random_baseline_factory(),
        n_runs=5,
        base_seed=999,
        initial_cash=100_000.0,
    ).run()

    assert not np.allclose(result_a.final_pnl, result_b.final_pnl)


def test_summary_statistics_match_hand_computed_numpy():
    runner = MonteCarloRunner(
        price_generator_factory=_gbm_factory(),
        strategy_factory=_momentum_factory(),
        n_runs=10,
        base_seed=1,
        initial_cash=100_000.0,
        percentiles=(5, 50, 95),
    )

    result = runner.run()
    pnl = result.final_pnl

    assert result.mean == pytest.approx(float(np.mean(pnl)))
    assert result.median == pytest.approx(float(np.median(pnl)))
    assert result.std == pytest.approx(float(np.std(pnl, ddof=1)))
    assert set(result.percentiles.keys()) == {5, 50, 95}
    for p, value in result.percentiles.items():
        assert value == pytest.approx(float(np.percentile(pnl, p)))
    assert result.prob_of_loss == pytest.approx(float(np.mean(pnl < 0)))


def test_prob_of_loss_within_unit_interval():
    result = MonteCarloRunner(
        price_generator_factory=_gbm_factory(),
        strategy_factory=_random_baseline_factory(),
        n_runs=20,
        base_seed=1,
        initial_cash=100_000.0,
    ).run()

    assert 0.0 <= result.prob_of_loss <= 1.0


def test_single_run_std_is_zero():
    result = MonteCarloRunner(
        price_generator_factory=_gbm_factory(),
        strategy_factory=_momentum_factory(),
        n_runs=1,
        base_seed=1,
        initial_cash=100_000.0,
    ).run()

    assert result.std == 0.0


def test_n_runs_must_be_positive():
    with pytest.raises(ValueError):
        MonteCarloRunner(
            price_generator_factory=_gbm_factory(),
            strategy_factory=_momentum_factory(),
            n_runs=0,
            base_seed=1,
            initial_cash=100_000.0,
        )


def test_stress_run_with_regime_price_generator_and_shocks():
    regime_config = RegimeConfig(
        instrument="SIM",
        initial_price=100.0,
        regimes={"low_vol": (0.05, 0.15), "high_vol": (0.0, 0.5)},
        transition_matrix=[[0.9, 0.1], [0.1, 0.9]],
        initial_regime="low_vol",
        n_steps=20,
        dt=1 / 252,
        seed=42,
    )

    def regime_factory(seed, clock):
        return VolatilityRegimeModel(
            dataclasses.replace(regime_config, seed=seed), clock
        )

    def shock_config_factory(seed):
        return ShockConfig(
            shock_intensity=5.0,
            magnitude_range=(0.1, 0.4),
            duration_range=(2, 5),
            n_steps=20,
            dt=1 / 252,
            seed=seed,
        )

    runner = MonteCarloRunner(
        price_generator_factory=regime_factory,
        strategy_factory=_random_baseline_factory(),
        n_runs=3,
        base_seed=1,
        initial_cash=100_000.0,
        shock_config_factory=shock_config_factory,
    )

    result = runner.run()

    assert result.final_pnl.shape == (3,)
    assert len(result.equity_curves) == 3
