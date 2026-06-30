import uuid
from dataclasses import dataclass, field

from market_sim.core.models import EventType


@dataclass
class Event:
    event_type: EventType
    timestamp: float
    sequence: int
    data: dict
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.timestamp < 0:
            raise ValueError(f"timestamp must be >= 0, got {self.timestamp}")
        if self.sequence < 0:
            raise ValueError(f"sequence must be >= 0, got {self.sequence}")
        if not isinstance(self.data, dict):
            raise TypeError(f"data must be a dict, got {type(self.data)}")