class SimulationClock:
    def __init__(self, start_time: float = 0.0) -> None:
        self._current_time = start_time
        self._sequence_counter = 0

    def next_sequence(self) -> int:
        seq = self._sequence_counter
        self._sequence_counter += 1
        return seq

    def advance(self, timestamp: float) -> None:
        if timestamp < self._current_time:
            raise ValueError(
                f"cannot move clock backward: {timestamp} < {self._current_time}"
            )
        self._current_time = timestamp

    def now(self) -> float:
        return self._current_time