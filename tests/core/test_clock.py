from market_sim.core.clock import SimulationClock


def test_next_sequence_strictly_increasing():
    clock = SimulationClock()
    sequences = [clock.next_sequence() for _ in range(5)]
    assert sequences == [0, 1, 2, 3, 4]


def test_advance_and_now():
    clock = SimulationClock()
    assert clock.now() == 0.0

    clock.advance(5.0)
    assert clock.now() == 5.0


def test_advance_backward_raises():
    clock = SimulationClock(start_time=10.0)
    try:
        clock.advance(5.0)
        assert False, "expected ValueError"
    except ValueError:
        pass
