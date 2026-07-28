"""Self-check for src/ui/state_watcher.py -- the UI-independent runtime
state file watcher (Stage 2 of the desktop-app session). Written before
state_watcher.py's implementation.

Uses real (bounded) threading and real temporary files, following the
same precedent already established in tests/test_runtime_poller.py --
every test uses a small real polling interval (tens of milliseconds) and
a generous real settle-wait to let a handful of poll cycles happen, then
stop()s with a timeout, so a loop bug fails the test instead of hanging
it. Run with: python -m tests.test_state_watcher
"""

import json
import tempfile
import time
from pathlib import Path

from src.ui.state_reader import FILE_MISSING, INVALID_JSON, VALID_STATE
from src.ui.state_watcher import StateWatcher

POLL_INTERVAL = 0.02  # seconds -- fast enough for quick tests, slow enough not to busy-spin
SETTLE = 0.15  # generous real-wait margin: several poll cycles at POLL_INTERVAL

VALID_STATE_DICT = {
    "state_schema_version": 1,
    "state": "idle_no_champ_select",
    "draft_snapshot": None,
    "recommendations": [],
    "champion_catalog_version": None,
    "warnings": [],
    "error": None,
}


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_initial_state_delivered_on_first_poll():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        _write(path, VALID_STATE_DICT)
        received = []
        watcher = StateWatcher(path=path, interval_seconds=POLL_INTERVAL, on_change=received.append)

        watcher.poll_once()  # synchronous -- no thread needed for this one

        assert len(received) == 1
        assert received[0].status == VALID_STATE


def test_no_callback_when_file_missing_and_still_missing():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "never_created.json"
        received = []
        watcher = StateWatcher(path=path, interval_seconds=POLL_INTERVAL, on_change=received.append)

        watcher.poll_once()
        watcher.poll_once()
        watcher.poll_once()

        assert len(received) == 1  # only the first file_missing delivery -- not repeated
        assert received[0].status == FILE_MISSING


def test_file_creation_after_startup_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        received = []
        watcher = StateWatcher(path=path, interval_seconds=POLL_INTERVAL, on_change=received.append)

        watcher.start()
        time.sleep(SETTLE)
        _write(path, VALID_STATE_DICT)
        time.sleep(SETTLE)
        watcher.stop(timeout=2.0)

        statuses = [r.status for r in received]
        assert statuses[0] == FILE_MISSING
        assert statuses[-1] == VALID_STATE


def test_atomic_replacement_with_new_content_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        _write(path, VALID_STATE_DICT)
        received = []
        watcher = StateWatcher(path=path, interval_seconds=POLL_INTERVAL, on_change=received.append)

        watcher.start()
        time.sleep(SETTLE)

        new_state = dict(VALID_STATE_DICT, state="champ_select_active")
        # Emulates publish_state()'s own atomic write: temp file + replace.
        tmp_path = path.with_suffix(".tmp")
        _write(tmp_path, new_state)
        tmp_path.replace(path)

        time.sleep(SETTLE)
        watcher.stop(timeout=2.0)

        received_states = [r.state["state"] for r in received if r.state is not None]
        assert received_states[0] == "idle_no_champ_select"
        assert received_states[-1] == "champ_select_active"


def test_unchanged_file_does_not_repeat_the_callback():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        _write(path, VALID_STATE_DICT)
        received = []
        watcher = StateWatcher(path=path, interval_seconds=POLL_INTERVAL, on_change=received.append)

        watcher.start()
        time.sleep(SETTLE * 2)  # several poll cycles; file never changes
        watcher.stop(timeout=2.0)

        assert len(received) == 1  # only the initial delivery


def test_deletion_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        _write(path, VALID_STATE_DICT)
        received = []
        watcher = StateWatcher(path=path, interval_seconds=POLL_INTERVAL, on_change=received.append)

        watcher.start()
        time.sleep(SETTLE)
        path.unlink()
        time.sleep(SETTLE)
        watcher.stop(timeout=2.0)

        statuses = [r.status for r in received]
        assert statuses[0] == VALID_STATE
        assert statuses[-1] == FILE_MISSING


def test_invalid_to_valid_transition_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text("{not valid json", encoding="utf-8")
        received = []
        watcher = StateWatcher(path=path, interval_seconds=POLL_INTERVAL, on_change=received.append)

        watcher.start()
        time.sleep(SETTLE)
        _write(path, VALID_STATE_DICT)
        time.sleep(SETTLE)
        watcher.stop(timeout=2.0)

        statuses = [r.status for r in received]
        assert statuses[0] == INVALID_JSON
        assert statuses[-1] == VALID_STATE


def test_valid_to_invalid_transition_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        _write(path, VALID_STATE_DICT)
        received = []
        watcher = StateWatcher(path=path, interval_seconds=POLL_INTERVAL, on_change=received.append)

        watcher.start()
        time.sleep(SETTLE)
        path.write_text("not json {{{", encoding="utf-8")
        time.sleep(SETTLE)
        watcher.stop(timeout=2.0)

        statuses = [r.status for r in received]
        assert statuses[0] == VALID_STATE
        assert statuses[-1] == INVALID_JSON


def test_callback_exception_does_not_kill_the_watcher():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        _write(path, VALID_STATE_DICT)
        calls = {"count": 0}
        errors = []

        def flaky_on_change(result):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("boom")

        watcher = StateWatcher(
            path=path, interval_seconds=POLL_INTERVAL, on_change=flaky_on_change, on_error=errors.append,
        )

        watcher.start()
        time.sleep(SETTLE)
        new_state = dict(VALID_STATE_DICT, state="champ_select_active")
        _write(path, new_state)
        time.sleep(SETTLE)
        watcher.stop(timeout=2.0)

        assert calls["count"] == 2  # first call raised; second (after the real change) still happened
        assert len(errors) == 1
        assert isinstance(errors[0], RuntimeError)


def test_clean_stop_and_repeated_start_stop_leaves_no_thread_alive():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        _write(path, VALID_STATE_DICT)
        watcher = StateWatcher(path=path, interval_seconds=POLL_INTERVAL, on_change=lambda r: None)

        watcher.start()
        time.sleep(SETTLE)
        watcher.stop(timeout=2.0)
        assert not watcher.is_running

        # repeated start/stop must be safe
        watcher.start()
        time.sleep(SETTLE)
        watcher.stop(timeout=2.0)
        assert not watcher.is_running

        watcher.stop(timeout=2.0)  # stopping an already-stopped watcher must not raise
        assert not watcher.is_running


def test_configured_interval_is_used():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        _write(path, VALID_STATE_DICT)
        sleep_calls = []

        def fake_sleep(seconds):
            sleep_calls.append(seconds)
            time.sleep(0.01)  # small real delay so the loop doesn't spin instantly

        watcher = StateWatcher(path=path, interval_seconds=0.3, on_change=lambda r: None, sleep_fn=fake_sleep)

        watcher.start()
        time.sleep(SETTLE)
        watcher.stop(timeout=2.0)

        assert len(sleep_calls) >= 1
        assert all(s == 0.3 for s in sleep_calls)


if __name__ == "__main__":
    test_initial_state_delivered_on_first_poll()
    test_no_callback_when_file_missing_and_still_missing()
    test_file_creation_after_startup_is_detected()
    test_atomic_replacement_with_new_content_is_detected()
    test_unchanged_file_does_not_repeat_the_callback()
    test_deletion_is_detected()
    test_invalid_to_valid_transition_is_detected()
    test_valid_to_invalid_transition_is_detected()
    test_callback_exception_does_not_kill_the_watcher()
    test_clean_stop_and_repeated_start_stop_leaves_no_thread_alive()
    test_configured_interval_is_used()
    print("All checks passed.")
