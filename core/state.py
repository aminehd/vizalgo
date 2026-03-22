import copy
from collections import deque


class VizGrid:
    """Wraps list[list], tracks cell states as integers."""

    def __init__(self, raw):
        """Accept list[list[str]] or list[list[int]], converts "1"->1, "0"->0."""
        self._grid = []
        for row in raw:
            new_row = []
            for cell in row:
                if isinstance(cell, str):
                    new_row.append(1 if cell == "1" else 0)
                else:
                    new_row.append(int(cell))
            self._grid.append(new_row)
        self.cursor    = None   # (r, c) — cell currently being processed
        self.neighbors = []     # [(r, c), ...] — cells being considered

    def __getitem__(self, r):
        return self._grid[r]

    def __setitem__(self, r, value):
        self._grid[r] = value

    def valid(self, r, c):
        """Bounds check."""
        return 0 <= r < self.rows and 0 <= c < self.cols

    @property
    def rows(self):
        return len(self._grid)

    @property
    def cols(self):
        return len(self._grid[0]) if self._grid else 0

    def snapshot(self):
        """Return dict with cells, cursor, and neighbors."""
        return {
            "cells":     copy.deepcopy(self._grid),
            "cursor":    list(self.cursor) if self.cursor is not None else None,
            "neighbors": [list(n) for n in self.neighbors],
        }


class VizQueue:
    """Wraps collections.deque with snapshot support."""

    def __init__(self):
        self._q = deque()

    def push(self, item):
        self._q.append(item)

    def pop(self):
        return self._q.popleft()

    def __bool__(self):
        return bool(self._q)

    def __len__(self):
        return len(self._q)

    def snapshot(self):
        """Return list copy of current queue contents."""
        return list(self._q)
