from abc import ABC, abstractmethod
from ..core.event import Snapshot


class BaseRenderer(ABC):
    @abstractmethod
    def render(self, snapshots: list, output: str, **meta):
        """Render list of snapshots to output path (e.g. MP4)."""
        ...
