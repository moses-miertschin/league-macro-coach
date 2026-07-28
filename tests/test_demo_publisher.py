"""Self-check for src/ui/demo_publisher.py -- the QTimer-driven cycler
that publishes demo/states/ fixtures (Stage 4) through the real
publish_state() writer (Stage 7 of the desktop-app session). Written
before demo_publisher.py's implementation.

DemoStatePublisher deliberately writes through the exact same
publish_state() function real data goes through, and does not itself
know about LiveStateSource/StateWatcher/the window at all -- a
LiveStateSource pointed at the same output path is what actually
delivers each write, exactly like a real --watch run would. This test
file only proves DemoStatePublisher writes the right content at the
right cadence; tests/test_live_state_source.py already proves delivery
from a changing file works.

Offscreen, non-interactive: QT_QPA_PLATFORM forced before any PySide6
import. Run with: python -m tests.test_demo_publisher
"""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication

from src.ui.demo_publisher import DemoStatePublisher

_app = QApplication.instance() or QApplication([])

STATE_A = {"state_schema_version": 1, "state": "idle_no_champ_select", "draft_snapshot": None, "recommendations": [], "champion_catalog_version": None, "warnings": [], "error": None}
STATE_B = {"state_schema_version": 1, "state": "champ_select_active", "draft_snapshot": None, "recommendations": [], "champion_catalog_version": None, "warnings": [], "error": None}


def _process_events_until(condition_fn, timeout=2.0, interval=0.02):
    deadline = time.time() + timeout
    while time.time() < deadline:
        QCoreApplication.processEvents()
        if condition_fn():
            return True
        time.sleep(interval)
    return False


def test_start_publishes_the_first_state_immediately():
    calls = []
    publisher = DemoStatePublisher(
        [STATE_A, STATE_B], output_path="fake/path.json", interval_seconds=100,
        publish_fn=lambda state, output_path: calls.append((state, output_path)),
    )

    publisher.start()

    assert len(calls) == 1
    assert calls[0] == (STATE_A, "fake/path.json")
    publisher.stop()


def test_single_state_never_starts_a_repeating_timer():
    calls = []
    publisher = DemoStatePublisher(
        [STATE_A], output_path="fake/path.json", interval_seconds=100,
        publish_fn=lambda state, output_path: calls.append(state), timer_factory=QTimer,
    )

    publisher.start()

    assert len(calls) == 1
    assert publisher.is_cycling is False
    publisher.stop()


def test_multiple_states_cycle_on_the_configured_interval():
    calls = []
    publisher = DemoStatePublisher(
        [STATE_A, STATE_B], output_path="fake/path.json", interval_seconds=0.05,
        publish_fn=lambda state, output_path: calls.append(state), timer_factory=QTimer,
    )

    publisher.start()
    try:
        delivered = _process_events_until(lambda: len(calls) >= 3, timeout=2.0)
        assert delivered, f"expected at least 3 publishes, got {len(calls)}"
        assert calls[0] == STATE_A
        assert calls[1] == STATE_B
        assert calls[2] == STATE_A
    finally:
        publisher.stop()


def test_stop_halts_further_publishes():
    calls = []
    publisher = DemoStatePublisher(
        [STATE_A, STATE_B], output_path="fake/path.json", interval_seconds=0.05,
        publish_fn=lambda state, output_path: calls.append(state), timer_factory=QTimer,
    )

    publisher.start()
    _process_events_until(lambda: len(calls) >= 1)
    publisher.stop()
    count_after_stop = len(calls)
    _process_events_until(lambda: len(calls) > count_after_stop, timeout=0.3)

    assert len(calls) == count_after_stop


def test_empty_state_list_raises_at_construction():
    try:
        DemoStatePublisher([], output_path="fake/path.json")
        assert False, "expected ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    test_start_publishes_the_first_state_immediately()
    test_single_state_never_starts_a_repeating_timer()
    test_multiple_states_cycle_on_the_configured_interval()
    test_stop_halts_further_publishes()
    test_empty_state_list_raises_at_construction()
    print("All checks passed.")
