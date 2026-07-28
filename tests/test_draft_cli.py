"""Self-check for src/draft/cli.py -- the runnable draft command (Stage 4
of this session's staged implementation plan). Written before cli.py's
implementation.

No real League installation, no network, no infinite loops: --watch mode
is tested with an injected sleep_fn that raises KeyboardInterrupt after a
small bounded number of calls, simulating Ctrl+C arriving during the sleep
between polls -- exactly where a real interrupt would land.
Run with: python -m tests.test_draft_cli
"""

import tempfile
from pathlib import Path

from src.draft.cli import _build_service, build_arg_parser, run_capture_once, run_once, run_watch
from src.draft.client import LCUClient
from src.draft.service import DraftRuntimeService
from src.runtime.state_publisher import DEFAULT_OUTPUT_PATH

FAKE_STATE = {
    "state_schema_version": 1,
    "state": "champ_select_active",
    "draft_snapshot": {"ally_picks": [157]},
    "recommendations": [{
        "system": "draft", "category": "pick_recommendation", "subject": "Annie",
        "recommendation": "Annie", "reason": "Annie plays middle.", "evidence": [],
        "confidence": "high", "confidence_score": None, "severity": "low", "priority": 1,
        "source": "champion_knowledge", "details": {},
    }],
    "champion_catalog_version": "14.1.1",
    "warnings": [],
    "error": None,
}


class _FakeService:
    def __init__(self, states):
        self._states = list(states)
        self.poll_count = 0

    def poll_once(self):
        self.poll_count += 1
        return self._states[min(self.poll_count, len(self._states)) - 1]


# ---- argument parsing ----


def test_once_watch_and_capture_once_are_mutually_exclusive_and_one_is_required():
    parser = build_arg_parser()

    args = parser.parse_args(["--once"])
    assert args.once is True
    assert args.watch is False
    assert args.capture_once is False

    args = parser.parse_args(["--capture-once"])
    assert args.capture_once is True

    try:
        parser.parse_args(["--once", "--watch"])
    except SystemExit:
        pass
    else:
        raise AssertionError("Expected --once and --watch to be mutually exclusive")

    try:
        parser.parse_args(["--once", "--capture-once"])
    except SystemExit:
        pass
    else:
        raise AssertionError("Expected --once and --capture-once to be mutually exclusive")

    try:
        parser.parse_args([])
    except SystemExit:
        pass
    else:
        raise AssertionError("Expected an error when none of --once/--watch/--capture-once is given")


def test_parser_defaults():
    parser = build_arg_parser()
    args = parser.parse_args(["--once"])

    assert args.output == DEFAULT_OUTPUT_PATH
    assert args.interval == 5.0
    assert args.lockfile is None
    assert args.verbose is False


def test_parser_accepts_all_options():
    parser = build_arg_parser()
    args = parser.parse_args([
        "--watch", "--output", "custom/state.json", "--interval", "2.5",
        "--lockfile", "custom/lockfile", "--verbose",
    ])

    assert args.watch is True
    assert args.output == Path("custom/state.json")
    assert args.interval == 2.5
    assert args.lockfile == Path("custom/lockfile")
    assert args.verbose is True


# ---- --once ----


def test_run_once_polls_publishes_and_prints_status():
    service = _FakeService([FAKE_STATE])
    published = []
    printed = []

    result = run_once(
        service,
        output_path=Path("fake/state.json"),
        publisher_fn=lambda state, output_path: published.append((state, output_path)),
        print_fn=printed.append,
    )

    assert result == FAKE_STATE
    assert service.poll_count == 1
    assert published == [(FAKE_STATE, Path("fake/state.json"))]
    assert any("champ_select_active" in line for line in printed)


def test_run_once_verbose_includes_full_state_in_output():
    service = _FakeService([FAKE_STATE])
    printed = []

    run_once(
        service, output_path=Path("fake/state.json"),
        publisher_fn=lambda state, output_path: None, print_fn=printed.append, verbose=True,
    )

    assert any("state_schema_version" in line for line in printed)


# ---- --watch ----


def test_run_watch_publishes_after_every_poll_and_uses_configured_interval():
    service = _FakeService([FAKE_STATE])
    published = []
    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 2:
            raise KeyboardInterrupt

    run_watch(
        service,
        output_path=Path("fake/state.json"),
        interval_seconds=3.0,
        publisher_fn=lambda state, output_path: published.append((state, output_path)),
        print_fn=lambda *_: None,
        sleep_fn=fake_sleep,
    )

    assert service.poll_count == 2  # polled twice before the interrupt landed during the 2nd sleep
    assert len(published) == 2
    assert all(p[1] == Path("fake/state.json") for p in published)
    assert sleep_calls == [3.0, 3.0]  # the configured interval, every time


def test_run_watch_stops_cleanly_on_keyboard_interrupt_and_prints_a_message():
    service = _FakeService([FAKE_STATE])
    printed = []

    def fake_sleep(seconds):
        raise KeyboardInterrupt

    run_watch(  # must not raise -- KeyboardInterrupt is caught internally
        service, output_path=Path("fake/state.json"), interval_seconds=1.0,
        publisher_fn=lambda state, output_path: None, print_fn=printed.append, sleep_fn=fake_sleep,
    )

    assert any("stop" in line.lower() for line in printed)


def test_run_watch_reflects_state_changes_across_polls():
    idle_state = dict(FAKE_STATE, state="idle_no_champ_select", draft_snapshot=None, recommendations=[])
    service = _FakeService([FAKE_STATE, idle_state])
    published = []
    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 2:
            raise KeyboardInterrupt

    run_watch(
        service, output_path=Path("fake/state.json"), interval_seconds=1.0,
        publisher_fn=lambda state, output_path: published.append(state), print_fn=lambda *_: None,
        sleep_fn=fake_sleep,
    )

    assert [s["state"] for s in published] == ["champ_select_active", "idle_no_champ_select"]


# ---- --capture-once ----


def test_run_capture_once_writes_nothing_when_no_active_session():
    printed = []

    result = run_capture_once(session_source=lambda: None, print_fn=printed.append)

    assert result is None
    assert any("no active" in line.lower() for line in printed)


def test_run_capture_once_captures_when_a_session_is_active():
    fake_raw_session = {"myTeam": [], "theirTeam": [], "localPlayerCellId": 0, "bans": {}, "timer": {}}
    fake_snapshot = {"ally_picks": [], "enemy_picks": []}
    captured = {}

    def fake_capture_fn(raw_session, snapshot, capture_dir=None):
        captured["raw_session"] = raw_session
        captured["snapshot"] = snapshot
        captured["capture_dir"] = capture_dir
        return {"raw_path": Path("fake_raw.json"), "snapshot_path": Path("fake_snapshot.json")}

    printed = []
    result = run_capture_once(
        session_source=lambda: fake_raw_session,
        snapshot_builder=lambda raw: fake_snapshot,
        capture_fn=fake_capture_fn,
        print_fn=printed.append,
    )

    assert result == {"raw_path": Path("fake_raw.json"), "snapshot_path": Path("fake_snapshot.json")}
    assert captured["raw_session"] == fake_raw_session
    assert captured["snapshot"] == fake_snapshot
    assert any("fake_raw.json" in line for line in printed)
    assert any("fake_snapshot.json" in line for line in printed)


def test_run_capture_once_prints_the_review_warning():
    printed = []

    run_capture_once(
        session_source=lambda: {"myTeam": [], "theirTeam": [], "localPlayerCellId": 0, "bans": {}, "timer": {}},
        snapshot_builder=lambda raw: {},
        capture_fn=lambda raw_session, snapshot: {"raw_path": Path("a"), "snapshot_path": Path("b")},
        print_fn=printed.append,
    )

    assert any("review" in line.lower() for line in printed)


# ---- service construction (real LCUClient wiring, no network) ----


def test_build_service_wires_a_real_lcuclient_with_no_lockfile_present():
    with tempfile.TemporaryDirectory() as tmp:
        lockfile_path = Path(tmp) / "lockfile"  # deliberately never written

        service = _build_service(lockfile_path)

        assert isinstance(service, DraftRuntimeService)
        state = service.poll_once()  # no lockfile -- must resolve to league_client_unavailable, no network call
        assert state["state"] == "league_client_unavailable"


def test_build_service_defaults_to_standard_lockfile_path_when_unspecified():
    service = _build_service(None)

    assert isinstance(service, DraftRuntimeService)
    assert isinstance(service._session_source, LCUClient)
    assert service._session_source.lockfile_path == LCUClient().lockfile_path


if __name__ == "__main__":
    test_once_watch_and_capture_once_are_mutually_exclusive_and_one_is_required()
    test_parser_defaults()
    test_parser_accepts_all_options()
    test_run_once_polls_publishes_and_prints_status()
    test_run_once_verbose_includes_full_state_in_output()
    test_run_watch_publishes_after_every_poll_and_uses_configured_interval()
    test_run_watch_stops_cleanly_on_keyboard_interrupt_and_prints_a_message()
    test_run_watch_reflects_state_changes_across_polls()
    test_run_capture_once_writes_nothing_when_no_active_session()
    test_run_capture_once_captures_when_a_session_is_active()
    test_run_capture_once_prints_the_review_warning()
    test_build_service_wires_a_real_lcuclient_with_no_lockfile_present()
    test_build_service_defaults_to_standard_lockfile_path_when_unspecified()
    print("All checks passed.")
