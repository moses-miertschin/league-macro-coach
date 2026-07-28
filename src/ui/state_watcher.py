"""UI-independent watcher for the runtime state file src/ui/state_reader.py
reads. No UI code, no League API logic -- this module only detects when a
new StateReadResult is meaningfully different from the last one delivered
and hands it to an injected callback.

Built on top of src/runtime/poller.py's SessionPoller by composition, not
duplication: SessionPoller already provides the proven, tested threading
lifecycle (start()/stop(), idempotent, bounded thread shutdown, injectable
sleep_fn, no busy-loop) this watcher needs, and reusing it means this
module never has to re-solve that problem. What SessionPoller does *not*
provide -- deciding whether a new poll result is worth telling anyone
about -- is exactly this module's own, separate job, so it isn't forced
into SessionPoller (which stays deliberately domain-blind).

A result counts as "meaningfully new" when its (status, state, error)
triple differs from the last one delivered -- not when its modification
timestamp merely changes. This matters in practice: --watch republishes
the runtime state file on every poll even when nothing about the draft
actually changed, and a watcher that fired on every mtime bump would spam
callbacks for no real change.

Callback exceptions never kill the watcher: on_change is called from
inside a try/except, so a bug in the caller's own callback degrades to
(optionally) reporting it via on_error, never to silently stopping future
updates -- the next poll always tries again from a clean slate.
"""

import time
from pathlib import Path

from src.runtime.poller import SessionPoller
from src.ui.state_reader import DEFAULT_STATE_PATH, StateReadResult, read_runtime_state


class StateWatcher:
    def __init__(
        self,
        path: Path = DEFAULT_STATE_PATH,
        interval_seconds: float = 1.0,
        on_change=None,
        reader_fn=read_runtime_state,
        sleep_fn=time.sleep,
        on_error=None,
    ):
        self._path = Path(path)
        self._reader_fn = reader_fn
        self._on_change = on_change
        self._on_error = on_error
        self._last_result: StateReadResult | None = None
        self._poller = SessionPoller(
            data_source=self._read,
            interval_seconds=interval_seconds,
            on_result=self._handle_result,
            sleep_fn=sleep_fn,
        )

    @property
    def is_running(self) -> bool:
        return self._poller.is_running

    @property
    def last_result(self) -> StateReadResult | None:
        return self._last_result

    def poll_once(self) -> StateReadResult:
        """Synchronous single tick -- the same unit both start()/stop() and
        an external caller (e.g. a future desktop app's own timer) use."""
        return self._poller.poll_once()

    def start(self) -> None:
        self._poller.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._poller.stop(timeout=timeout)

    def _read(self) -> StateReadResult:
        return self._reader_fn(self._path)

    def _handle_result(self, result: StateReadResult) -> None:
        if not self._is_meaningfully_new(result):
            return
        self._last_result = result
        if self._on_change is None:
            return
        try:
            self._on_change(result)
        except Exception as exc:
            if self._on_error is not None:
                try:
                    self._on_error(exc)
                except Exception:
                    pass  # a failing error-handler must not kill the watcher either

    def _is_meaningfully_new(self, result: StateReadResult) -> bool:
        if self._last_result is None:
            return True
        return (
            result.status != self._last_result.status
            or result.state != self._last_result.state
            or result.error != self._last_result.error
        )
