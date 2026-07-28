"""Shared polling/runtime foundation for future champion-select and
live-game monitoring -- see ROADMAP.md Sec.1 ("shared polling/runtime
model... build this once, shared by both phases") and
LIVE_SYSTEM_DESIGN.md's "Runtime Model" section.

This module is deliberately domain-blind: it knows nothing about draft
picks, runes, or live game analysis. It only knows how to call an injected
data source, track idle-vs-active state, and hand each result to a
callback. Every real decision system (a future src/draft/, src/live/, or a
desktop app) builds on top of this without this module knowing anything
about them -- the same "source-agnostic shape" precedent GameSnapshot
(src/analysis/game_state.py) already established for post-game data.

A data source is any zero-argument callable returning a dict when a
session exists (champ select in progress, game in progress) or None when
it doesn't -- the same "endpoint simply isn't reachable" idle condition
LIVE_SYSTEM_DESIGN.md describes for the Live Client Data API. This module
never inspects or interprets the dict's contents.

Two ways to drive it, both supported without extra code:
  - Background thread: start()/stop() -- for a headless/CLI-style caller.
  - Manual polling: call poll_once() directly from an external event loop
    (e.g. a Qt/Tk timer callback in a future desktop app) -- avoids
    updating UI state from a background thread entirely.
"""

import threading
import time


class SessionPoller:
    def __init__(self, data_source, interval_seconds=5.0, on_result=None, sleep_fn=time.sleep):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

        self._data_source = data_source
        self.interval_seconds = interval_seconds
        self._on_result = on_result
        self._sleep_fn = sleep_fn

        self._thread = None
        self._running = threading.Event()
        self.poll_count = 0
        self.last_result = None

    @property
    def state(self) -> str:
        return "idle" if self.last_result is None else "active"

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def poll_once(self):
        """Runs a single poll cycle synchronously and returns the result.

        This is the unit the rest of this class is built around -- both
        the background loop and any external caller (a desktop app's own
        timer) go through this same path, so there is only one place that
        ever calls the data source or dispatches on_result.
        """
        result = self._data_source()
        self.poll_count += 1
        self.last_result = result
        if self._on_result is not None:
            self._on_result(result)
        return result

    def start(self) -> None:
        if self.is_running:
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        while self.is_running:
            self.poll_once()
            self._sleep_fn(self.interval_seconds)

    def stop(self, timeout: float = 2.0) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._thread = None
