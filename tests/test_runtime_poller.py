"""Self-check for src/runtime/poller.py -- the shared polling/runtime
foundation described in ROADMAP.md Sec.1 and LIVE_SYSTEM_DESIGN.md's
"Runtime Model" section.

Written before poller.py's implementation. This module is domain-blind by
design (no draft/rune/live analysis logic), so every fixture here is a
generic fake data source, never a real LCU/Live Client shape.

Every test terminates in bounded time -- no unbounded loops. The threaded
start()/stop() tests use small, fixed real sleeps (tens of milliseconds)
plus a timeout on stop()'s join, so a bug in the loop fails the test
instead of hanging it. Run with: python -m tests.test_runtime_poller
"""

import time

from src.runtime.poller import SessionPoller


def test_poll_once_runs_synchronously_without_a_thread():
    calls = []
    poller = SessionPoller(data_source=lambda: calls.append(1) or {"phase": "champ_select"})

    result = poller.poll_once()

    assert result == {"phase": "champ_select"}
    assert poller.poll_count == 1
    assert poller.last_result == {"phase": "champ_select"}
    assert len(calls) == 1
    assert not poller.is_running  # poll_once() never touches the background loop


def test_idle_state_when_no_session_exists():
    poller = SessionPoller(data_source=lambda: None)

    poller.poll_once()

    assert poller.state == "idle"
    assert poller.last_result is None


def test_active_state_when_session_data_present():
    poller = SessionPoller(data_source=lambda: {"gameTime": 120.0})

    poller.poll_once()

    assert poller.state == "active"


def test_state_transitions_as_injected_source_changes_across_polls():
    # Simulates the real lifecycle this module exists to support: no
    # session -> champ select -> live game -> back to idle. The poller
    # itself never interprets *what* the session data means -- only
    # whether one is present.
    fake_states = [None, {"phase": "champ_select"}, {"gameTime": 5.0}, None]
    calls = iter(fake_states)
    poller = SessionPoller(data_source=lambda: next(calls))

    observed = []
    for _ in fake_states:
        poller.poll_once()
        observed.append(poller.state)

    assert observed == ["idle", "active", "active", "idle"]
    assert poller.poll_count == 4


def test_injected_fake_provider_is_the_only_data_source_used():
    # Proves the poller has no hidden dependency on a real LCU/Live Client
    # source -- any zero-arg callable works, which is what makes it usable
    # for both champ-select and live-game monitoring, and for tests.
    class FakeProvider:
        def __init__(self):
            self.calls = 0

        def __call__(self):
            self.calls += 1
            return {"call_number": self.calls}

    provider = FakeProvider()
    poller = SessionPoller(data_source=provider)

    poller.poll_once()
    poller.poll_once()

    assert provider.calls == 2
    assert poller.last_result == {"call_number": 2}


def test_on_result_callback_receives_every_poll_result():
    received = []
    poller = SessionPoller(data_source=lambda: {"tick": True}, on_result=received.append)

    poller.poll_once()
    poller.poll_once()

    assert received == [{"tick": True}, {"tick": True}]


def test_start_stop_lifecycle_polls_in_background_at_configured_interval():
    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)
        time.sleep(0.01)  # small, bounded real delay -- keeps the loop from busy-spinning

    poller = SessionPoller(data_source=lambda: {"ok": True}, interval_seconds=0.03, sleep_fn=fake_sleep)

    poller.start()
    time.sleep(0.1)  # let a handful of poll cycles happen
    poller.stop(timeout=2.0)

    assert poller.poll_count >= 2
    assert all(interval == 0.03 for interval in sleep_calls)
    assert not poller.is_running


def test_stop_is_clean_and_idempotent():
    poller = SessionPoller(data_source=lambda: {"ok": True}, interval_seconds=0.01, sleep_fn=lambda s: time.sleep(0.005))

    poller.start()
    assert poller.is_running
    poller.stop(timeout=2.0)

    assert not poller.is_running
    poll_count_after_first_stop = poller.poll_count

    poller.stop(timeout=2.0)  # calling stop() again must not raise or hang
    assert poller.poll_count == poll_count_after_first_stop  # no further polling happened


def test_start_is_idempotent_does_not_spawn_a_second_loop():
    poller = SessionPoller(data_source=lambda: {"ok": True}, interval_seconds=0.01, sleep_fn=lambda s: time.sleep(0.005))

    poller.start()
    first_thread = poller._thread
    poller.start()  # second call while already running must be a no-op
    second_thread = poller._thread

    assert first_thread is second_thread
    poller.stop(timeout=2.0)


def test_interval_must_be_positive():
    try:
        SessionPoller(data_source=lambda: None, interval_seconds=0)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for a non-positive interval_seconds")


if __name__ == "__main__":
    test_poll_once_runs_synchronously_without_a_thread()
    test_idle_state_when_no_session_exists()
    test_active_state_when_session_data_present()
    test_state_transitions_as_injected_source_changes_across_polls()
    test_injected_fake_provider_is_the_only_data_source_used()
    test_on_result_callback_receives_every_poll_result()
    test_start_stop_lifecycle_polls_in_background_at_configured_interval()
    test_stop_is_clean_and_idempotent()
    test_start_is_idempotent_does_not_spawn_a_second_loop()
    test_interval_must_be_positive()
    print("All checks passed.")
