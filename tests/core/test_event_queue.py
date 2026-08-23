from market_sim.core.queue import EventQueue
from market_sim.events import market_update


def make_event(timestamp, sequence):
    return market_update(
        timestamp=timestamp, sequence=sequence, price=100.0, instrument="SIM"
    )


def test_pops_in_timestamp_order():
    q = EventQueue()
    q.push(make_event(2.0, 0))
    q.push(make_event(1.0, 1))
    q.push(make_event(3.0, 2))

    first = q.pop()
    second = q.pop()
    third = q.pop()

    assert [first.timestamp, second.timestamp, third.timestamp] == [1.0, 2.0, 3.0]


def test_equal_timestamps_break_by_sequence():
    q = EventQueue()
    q.push(make_event(5.0, 2))
    q.push(make_event(5.0, 0))
    q.push(make_event(5.0, 1))

    sequences = [q.pop().sequence for _ in range(3)]

    assert sequences == [0, 1, 2]


def test_is_empty_and_len():
    q = EventQueue()
    assert q.is_empty()
    assert len(q) == 0

    q.push(make_event(1.0, 0))
    assert not q.is_empty()
    assert len(q) == 1

    q.pop()
    assert q.is_empty()
    assert len(q) == 0


def test_pop_from_empty_raises():
    q = EventQueue()
    try:
        q.pop()
        assert False, "expected IndexError"
    except IndexError:
        pass
