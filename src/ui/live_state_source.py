"""Bridges src/ui/state_watcher.py's background-thread polling into Qt's
main-thread event loop. StateWatcher's on_change callback fires from
SessionPoller's background thread; Qt widgets may only be touched from
the thread that owns them (the GUI thread). Signal.emit() is the
standard, thread-safe way to hand a value back across that boundary --
Qt compares the emitting thread against the receiving QObject's own
thread affinity and automatically queues the connected slot's invocation
onto the receiver's thread when they differ, so a slot connected to
state_changed always actually runs on the GUI thread, even though
emit() itself is called from StateWatcher's polling thread.

No UI code, no League API logic, no filesystem parsing -- this module
only relays a StateReadResult (src/ui/state_reader.py) that
StateWatcher already built; the reader/watcher stack under it never
imports PySide6.
"""

from PySide6.QtCore import QObject, Signal

from src.ui.state_reader import DEFAULT_STATE_PATH, StateReadResult
from src.ui.state_watcher import StateWatcher


class LiveStateSource(QObject):
    state_changed = Signal(object)  # emits a StateReadResult

    def __init__(
        self,
        path=DEFAULT_STATE_PATH,
        interval_seconds: float = 1.0,
        watcher_factory=StateWatcher,
        parent=None,
    ):
        super().__init__(parent)
        self._watcher = watcher_factory(path=path, interval_seconds=interval_seconds, on_change=self._emit_change)

    def _emit_change(self, result: StateReadResult) -> None:
        self.state_changed.emit(result)

    @property
    def is_running(self) -> bool:
        return self._watcher.is_running

    def start(self) -> None:
        self._watcher.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._watcher.stop(timeout=timeout)
