from dataclasses import dataclass


@dataclass
class GridPanel:
    var: str        # variable name in solution locals, e.g. "grid"
    key: str = "grid"


@dataclass
class QueuePanel:
    var: str
    key: str = "queue"


@dataclass
class Counter:
    var: str
    label: str = ""
    key: str = "count"


class RenderConfig:
    def __init__(self, panels: list):
        self.panels = panels

    def extract(self, all_locals: dict) -> dict:
        """Extract state from collected locals using panel definitions."""
        data = {}
        for panel in self.panels:
            if not hasattr(panel, 'var'):
                continue
            val = all_locals.get(panel.var)
            if val is None:
                continue
            if hasattr(val, 'snapshot'):
                data[panel.key] = val.snapshot()
            else:
                data[panel.key] = val
        return data
