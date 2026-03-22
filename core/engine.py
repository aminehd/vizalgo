import functools
import inspect
import sys
import textwrap
from collections.abc import Mapping
from .event import Snapshot
from .state import VizGrid, VizQueue


class VizEngine:
    def __init__(self, problem: str, title: str):
        self.problem         = problem
        self.title           = title
        self.snapshots: list = []
        self.source_lines: list[str] = []
        self._fn_start_line: int = 0
        self._trace_line:    int = 0

        # Global speed controls — set these instead of per-call duration
        self.line_speed: float = 0.6   # seconds per code line (pointer movement)
        self.snap_speed: float = 1.2   # seconds for state-change snaps

        self.config = None

    # ── Internal ────────────────────────────────────────────────────────────

    def _record(self, description: str, data: dict):
        """Append a snapshot, or replace the last micro-snap if on the same line."""
        line     = self._trace_line
        duration = self.snap_speed
        if (self.snapshots
                and self.snapshots[-1].line == line
                and self.snapshots[-1].duration <= self.line_speed):
            self.snapshots[-1] = Snapshot(
                description=description, duration=duration, line=line, data=data
            )
        else:
            self.snapshots.append(Snapshot(
                description=description, duration=duration, line=line, data=data
            ))

    def _serialize(self, val, ann: dict):
        """
        Type-dispatch: turn a Python value + annotation into snapshot-safe data.
        Returns None for types we can't meaningfully display (skipped).

        ann keys per type:
          list/tuple  → cursor (int), window ([l, r])
          dict        → highlight (key)
          VizGrid     → cursor (r,c), neighbors [(r,c),...]
        """
        if isinstance(val, VizGrid):
            if "cursor"    in ann: val.cursor    = ann["cursor"]
            if "neighbors" in ann: val.neighbors = ann["neighbors"]
            return val.snapshot()

        if isinstance(val, VizQueue):
            return val.snapshot()

        if isinstance(val, (list, tuple)):
            try:
                return {
                    "type":   "array",
                    "values": list(val),
                    "cursor": ann.get("cursor"),
                    "window": list(ann["window"]) if "window" in ann else None,
                }
            except Exception:
                return None

        if isinstance(val, Mapping):
            try:
                return {
                    "type":      "hashmap",
                    "entries":   {str(k): v for k, v in val.items()},
                    "highlight": ann.get("highlight"),
                }
            except Exception:
                return None

        if isinstance(val, (int, float, bool)):
            return val

        if isinstance(val, str) and len(val) < 80:
            return val

        return None  # skip everything else

    # ── Public API ───────────────────────────────────────────────────────────

    def snap(self, description="", **explicit_data):
        """
        Record a frame with state data.
        If config is set, auto-captures state from the call stack.
        If the auto-tracer already added a micro-snap for this line, replace it.
        """
        # Auto-capture from call stack if config is set
        if self.config is not None:
            frame = inspect.currentframe().f_back
            all_locals = {}
            f = frame
            while f is not None:
                for k, v in f.f_locals.items():
                    if k not in all_locals:
                        all_locals[k] = v
                f = f.f_back
            data = self.config.extract(all_locals)
        else:
            data = explicit_data

        self._record(description, data)

    def _serialize_locals(self, locs: dict, mark_dict: dict) -> dict:
        """Serialize a locals dict using type-dispatch, applying mark annotations."""
        data = {}
        for key, val in locs.items():
            if key.startswith("_") or key == "self" or callable(val):
                continue
            serialized = self._serialize(val, mark_dict.get(key, {}))
            if serialized is not None:
                data[key] = serialized
        return data

    def step(self, locals_dict: dict, mark: dict = None, label: str = ""):
        """
        Explicit snapshot from locals() — kept for backwards compatibility.
        Prefer @engine.show(mark=...) for clean zero-intrusion tracing.
        """
        data = self._serialize_locals(locals_dict, mark or {})
        self._record(label, data)

    def show(self, fn=None, *, mark=None):
        """
        Decorator: pins source + installs tracer that auto-snapshots every line.

        Two usage patterns:

          @engine.show                           # auto-capture, no annotations
          @engine.show(mark=lambda locs: {...})  # auto-capture + cursor/highlight

        mark: callable(locals_dict) → mark_dict
              locs is frame.f_locals at that line — use .get() for safety:

              mark=lambda locs: {
                  "nums": {"cursor": locs.get("i")},
                  "acc":  {"highlight": locs.get("prefix_sum", 0) - locs.get("k", 0)},
              }

        Algorithm code stays completely pure — no engine calls needed inside.
        """
        # @engine.show(mark=...) — called with args, return the real decorator
        if fn is None:
            return lambda f: self.show(f, mark=mark)

        try:
            src = inspect.getsource(fn)
            self.source_lines   = textwrap.dedent(src).splitlines()
            self._fn_start_line = inspect.getsourcelines(fn)[1]
        except Exception:
            pass

        fn_code     = fn.__code__
        fn_qualname = fn.__qualname__
        engine      = self

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            def local_tracer(frame, event, arg):
                if event == 'line':
                    engine._trace_line = frame.f_lineno - engine._fn_start_line
                    locs      = dict(frame.f_locals)
                    mark_dict = {}
                    if mark:
                        try:
                            mark_dict = mark(locs)
                        except Exception:
                            pass
                    data = engine._serialize_locals(locs, mark_dict)
                    engine._record("", data)
                return local_tracer

            def global_tracer(frame, event, arg):
                if event == 'call':
                    if frame.f_code is fn_code:
                        return local_tracer
                    fq = getattr(frame.f_code, 'co_qualname', '')
                    if fq.startswith(fn_qualname + '.<locals>.'):
                        return local_tracer
                return None

            old = sys.gettrace()
            sys.settrace(global_tracer)
            try:
                result = fn(*args, **kwargs)
            finally:
                sys.settrace(old)
            return result

        return wrapper

    def solution(self, fn):
        """Decorator — resets snapshots on each call."""
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            self.snapshots   = []
            self._trace_line = 0
            return fn(*args, **kwargs)
        return wrapper

    def run(self, fn, *args):
        return fn(*args)

    def render(self, renderer, output: str = None):
        renderer.render(
            self.snapshots, output,
            problem=self.problem,
            title=self.title,
            source_lines=self.source_lines,
        )
