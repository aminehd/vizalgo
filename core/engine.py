import functools
import inspect
import sys
import textwrap
from .event import Snapshot


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

    def snap(self, description="", **explicit_data):
        """
        Record a frame with state data.
        If config is set, auto-captures state from the call stack.
        If the auto-tracer already added a micro-snap for this line, replace it.
        """
        line = self._trace_line

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

        duration = self.snap_speed
        if (self.snapshots
                and self.snapshots[-1].line == line
                and self.snapshots[-1].duration <= self.line_speed):
            # Replace micro-snap with the full snap
            self.snapshots[-1] = Snapshot(
                description=description, duration=duration, line=line, data=data
            )
        else:
            self.snapshots.append(Snapshot(
                description=description, duration=duration, line=line, data=data
            ))

    def show(self, fn):
        """
        Decorator: pins which function's source shows in the code panel AND
        installs sys.settrace so every line gets a micro-snapshot (0.15 s),
        making the pointer animate line-by-line.
        """
        try:
            src = inspect.getsource(fn)
            self.source_lines   = textwrap.dedent(src).splitlines()
            self._fn_start_line = inspect.getsourcelines(fn)[1]
        except Exception:
            pass

        fn_code      = fn.__code__
        fn_qualname  = fn.__qualname__   # e.g. "numIslands"
        engine       = self

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            def local_tracer(frame, event, arg):
                if event == 'line':
                    engine._trace_line = frame.f_lineno - engine._fn_start_line
                    prev = engine.snapshots[-1] if engine.snapshots else None
                    # Add micro-snap only when moving to a new line
                    if not prev or prev.line != engine._trace_line:
                        engine.snapshots.append(Snapshot(
                            description=prev.description if prev else "",
                            duration=engine.line_speed,
                            line=engine._trace_line,
                            data=dict(prev.data) if prev else {},
                        ))
                return local_tracer

            def global_tracer(frame, event, arg):
                if event == 'call':
                    if frame.f_code is fn_code:
                        return local_tracer
                    # Also trace nested functions defined inside fn (e.g. bfs inside numIslands)
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
