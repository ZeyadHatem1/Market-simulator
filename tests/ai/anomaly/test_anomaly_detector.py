import pytest

from market_sim.ai.anomaly import AnomalyDetector


def test_no_flag_before_window_is_full():
    detector = AnomalyDetector(window=4, threshold=1.5)
    results = [detector.update(p) for p in [100.0, 100.0, 100.0, 100.0]]
    assert results == [False, False, False, False]


def test_constant_price_never_flags_regardless_of_threshold():
    detector = AnomalyDetector(window=4, threshold=0.001)
    results = [detector.update(100.0) for _ in range(20)]
    assert not any(results)


def test_hand_computed_z_score_spike_crosses_threshold():
    # Prices [100, 100, 100, 100, 110] -> returns [0, 0, 0, 0.10] once the
    # window=4 fills on the 5th update. mean=0.025, population std =
    # sqrt(0.0075/4) = sqrt(0.001875); z = 0.075 / sqrt(0.001875) = sqrt(3)
    # ~= 1.7320508, computed independently by hand rather than re-deriving
    # the implementation's own formula.
    prices = [100.0, 100.0, 100.0, 100.0, 110.0]

    below_threshold = AnomalyDetector(window=4, threshold=2.0)
    results_below = [below_threshold.update(p) for p in prices]
    assert results_below == [False, False, False, False, False]

    above_threshold = AnomalyDetector(window=4, threshold=1.5)
    results_above = [above_threshold.update(p) for p in prices]
    assert results_above == [False, False, False, False, True]


def test_flag_clears_on_the_next_tick_once_the_spike_is_no_longer_latest():
    detector = AnomalyDetector(window=4, threshold=1.5)
    for p in [100.0, 100.0, 100.0, 100.0, 110.0]:
        flagged = detector.update(p)
    assert flagged is True

    # A z-score detector flags the *latest* return, not the price level —
    # once the next return (flat, since price holds at 110) becomes the
    # newest entry, the prior spike return is no longer what's being scored.
    assert detector.update(110.0) is False


def test_invalid_window_raises():
    with pytest.raises(ValueError):
        AnomalyDetector(window=1, threshold=1.5)


def test_invalid_threshold_raises():
    with pytest.raises(ValueError):
        AnomalyDetector(window=4, threshold=0.0)
