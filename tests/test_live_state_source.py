"""Self-check for src/ui/live_state_source.py -- the Qt thread-safe bridge
between src/ui/state_watcher.py's background-thread polling and the GUI
thread (Stage 6 of the desktop-app session). Written before
live_state_source.py's implementation.

Two kinds of test here, matching this project's established precedent
(a fast direct-wiring test plus a real-threading integration test):
a fake watcher_factory proves the signal-emission wiring itself without
any real thread, and a real StateWatcher against a real temp file proves
the actual cross-thread delivery works when a Qt event loop is pumping
(QCoreApplication.processEvents(), bounded, matching the real-but-bounded
threading pattern test_state_watcher.py already established).

Offscreen, non-interactive: QT_QPA_PLATFORM is forced before any PySide6
import; no window is ever shown. Run with: python -m tests.test_live_state_source
"""

import json
import os
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from src.ui.live_state_source import LiveStateSource
from src.ui.state_reader import VALID_STATE, StateReadResult

_app = QApplication.instance() or QApplication([])

POLL_INTERVAL = 0.02
TIMEOUT = 2.0

VALID_STATE_DICT = {
    "state_schema_version": 1,
    "state": "idle_no_champ_select",
    "draft_snapshot": None,
    "recommendations": [],
    "champion_catalog_version": None,
    "warnings": [],
    "error": None,
}


class _FakeWatcher:
    """Stands in for StateWatcher -- captures the on_change callback
    LiveStateSource wires up so a test can invoke it directly, without a
    real background thread."""

    def __init__(self, path=None, interval_seconds=None, on_change=None):
        self.on_change = on_change
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self, timeout=2.0):
        self.stopped = True

    @property
    def is_running(self):
        return self.started and not self.stopped


def _process_events_until(condition_fn, timeout=TIMEOUT, interval=POLL_INTERVAL):
    deadline = time.time() + timeout
    while time.time() < deadline:
        QCoreApplication.processEvents()
        if condition_fn():
            return True
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# Direct wiring (no real thread)
# ---------------------------------------------------------------------------


def test_live_state_source_emits_signal_when_watcher_reports_a_change():
    received = []
    source = LiveStateSource(watcher_factory=_FakeWatcher)
    source.state_changed.connect(received.append)

    fake_result = StateReadResult(VALID_STATE, dict(VALID_STATE_DICT), Path("fake.json"), None, None)
    source._watcher.on_change(fake_result)

    assert received == [fake_result]


def test_live_state_source_start_stop_delegate_to_the_watcher():
    source = LiveStateSource(watcher_factory=_FakeWatcher)

    source.start()
    assert source.is_running is True

    source.stop()
    assert source.is_running is False


def test_live_state_source_uses_configured_path_and_interval():
    captured = {}

    def factory(path=None, interval_seconds=None, on_change=None):
        captured["path"] = path
        captured["interval_seconds"] = interval_seconds
        return _FakeWatcher(path=path, interval_seconds=interval_seconds, on_change=on_change)

    custom_path = Path("custom_state.json")
    LiveStateSource(path=custom_path, interval_seconds=0.5, watcher_factory=factory)

    assert captured["path"] == custom_path
    assert captured["interval_seconds"] == 0.5


# ---------------------------------------------------------------------------
# Real threading + real Qt cross-thread signal delivery
# ---------------------------------------------------------------------------


def test_live_state_source_delivers_real_background_thread_updates_to_the_gui_thread():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(VALID_STATE_DICT), encoding="utf-8")

        received = []
        source = LiveStateSource(path=path, interval_seconds=POLL_INTERVAL)
        source.state_changed.connect(received.append)

        source.start()
        try:
            delivered = _process_events_until(lambda: len(received) >= 1)
            assert delivered, "expected the initial state to be delivered"
            assert received[0].status == VALID_STATE

            new_state = dict(VALID_STATE_DICT, state="champ_select_active")
            path.write_text(json.dumps(new_state), encoding="utf-8")

            delivered = _process_events_until(lambda: len(received) >= 2)
            assert delivered, "expected the changed state to be delivered"
            assert received[1].state["state"] == "champ_select_active"
        finally:
            source.stop(timeout=2.0)


if __name__ == "__main__":
    test_live_state_source_emits_signal_when_watcher_reports_a_change()
    test_live_state_source_start_stop_delegate_to_the_watcher()
    test_live_state_source_uses_configured_path_and_interval()
    test_live_state_source_delivers_real_background_thread_updates_to_the_gui_thread()
    print("All checks passed.")
