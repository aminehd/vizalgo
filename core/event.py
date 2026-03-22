from dataclasses import dataclass, field
from typing import Any


@dataclass
class Snapshot:
    description: str = ""
    line: int = 0
    duration: float = 0.8      # seconds this frame shows
    data: dict = field(default_factory=dict)   # problem-specific state: grid, queue, count, etc.
