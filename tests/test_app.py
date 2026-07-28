"""Self-check for src/ui/app.py -- the QApplication/MainWindow factory
(Stage 5), plus the Stage 7 CLI argument-parsing and configuration
helpers (build_arg_parser, resolve_state_path, build_demo_publisher).
Written before each stage's implementation. Only tests the non-blocking
building blocks -- never main() itself, which enters Qt's blocking event
loop and is exercised manually, not by this automated, non-interactive
suite (matching src/draft/cli.py's established "thin main(), tested
helpers underneath" precedent).
Run with: python -m tests.test_app
"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.draft.service import IDLE_NO_CHAMP_SELECT
from src.ui.app import build_application, build_arg_parser, build_demo_publisher, build_main_window, resolve_state_path
from src.ui.demo_publisher import DemoStatePublisher
from src.ui.main_window import MainWindow
from src.ui.state_reader import DEFAULT_STATE_PATH


def test_build_application_returns_a_qapplication():
    app = build_application([])

    assert isinstance(app, QApplication)


def test_build_application_reuses_the_existing_instance():
    first = build_application([])
    second = build_application([])

    assert first is second


def test_build_main_window_with_no_initial_state_is_still_constructed():
    build_application([])
    window = build_main_window()

    assert isinstance(window, MainWindow)


def test_build_main_window_applies_an_initial_app_state():
    build_application([])
    state = {
        "state_schema_version": 1, "state": IDLE_NO_CHAMP_SELECT, "draft_snapshot": None, "recommendations": [],
        "champion_catalog_version": None, "warnings": [], "error": None,
    }

    window = build_main_window(app_state=state)

    assert window.status_header.title_text == "Waiting for Champ Select"


# ---------------------------------------------------------------------------
# build_arg_parser (Stage 7)
# ---------------------------------------------------------------------------


def test_default_args_watch_the_default_state_path_no_demo():
    args = build_arg_parser().parse_args([])

    assert args.state_file is None
    assert args.demo is False
    assert args.demo_state is None
    assert args.demo_interval == 5.0
    assert args.verbose is False


def test_state_file_flag_is_parsed_as_a_path():
    args = build_arg_parser().parse_args(["--state-file", "custom/state.json"])

    assert args.state_file == Path("custom/state.json")


def test_demo_flags_are_parsed():
    args = build_arg_parser().parse_args(["--demo", "--demo-interval", "2.5"])

    assert args.demo is True
    assert args.demo_interval == 2.5


def test_demo_state_flag_is_parsed():
    args = build_arg_parser().parse_args(["--demo-state", "03_champ_select_prelock_recommendations"])

    assert args.demo_state == "03_champ_select_prelock_recommendations"


# ---------------------------------------------------------------------------
# resolve_state_path (Stage 7)
# ---------------------------------------------------------------------------


def test_resolve_state_path_defaults_to_the_real_runtime_path():
    args = build_arg_parser().parse_args([])

    assert resolve_state_path(args) == DEFAULT_STATE_PATH


def test_resolve_state_path_honors_an_explicit_state_file():
    args = build_arg_parser().parse_args(["--state-file", "custom/state.json"])

    assert resolve_state_path(args) == Path("custom/state.json")


def test_resolve_state_path_uses_a_separate_path_in_demo_mode():
    args = build_arg_parser().parse_args(["--demo"])

    demo_path = resolve_state_path(args)

    assert demo_path != DEFAULT_STATE_PATH
    assert "demo" in demo_path.name


def test_resolve_state_path_demo_state_flag_alone_implies_demo_mode():
    args = build_arg_parser().parse_args(["--demo-state", "01_league_client_unavailable"])

    assert resolve_state_path(args) != DEFAULT_STATE_PATH


def test_resolve_state_path_explicit_state_file_wins_even_in_demo_mode():
    args = build_arg_parser().parse_args(["--demo", "--state-file", "custom/state.json"])

    assert resolve_state_path(args) == Path("custom/state.json")


# ---------------------------------------------------------------------------
# build_demo_publisher (Stage 7)
# ---------------------------------------------------------------------------


def test_build_demo_publisher_returns_none_outside_demo_mode():
    args = build_arg_parser().parse_args([])

    assert build_demo_publisher(args, Path("out.json")) is None


def test_build_demo_publisher_cycles_all_fixtures_in_plain_demo_mode():
    calls = []
    args = build_arg_parser().parse_args(["--demo"])

    publisher = build_demo_publisher(args, Path("out.json"), publish_fn=lambda state, output_path: calls.append(state))

    assert isinstance(publisher, DemoStatePublisher)
    publisher.start()
    assert len(calls) == 1  # first fixture published immediately
    publisher.stop()


def test_build_demo_publisher_pins_a_single_named_fixture():
    calls = []
    args = build_arg_parser().parse_args(["--demo-state", "01_league_client_unavailable"])

    publisher = build_demo_publisher(args, Path("out.json"), publish_fn=lambda state, output_path: calls.append(state))
    publisher.start()

    assert calls[0]["state"] == "league_client_unavailable"
    assert publisher.is_cycling is False
    publisher.stop()


def test_build_demo_publisher_raises_for_an_unknown_demo_state_name():
    args = build_arg_parser().parse_args(["--demo-state", "not_a_real_fixture"])

    try:
        build_demo_publisher(args, Path("out.json"))
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "not_a_real_fixture" in str(exc)


if __name__ == "__main__":
    test_build_application_returns_a_qapplication()
    test_build_application_reuses_the_existing_instance()
    test_build_main_window_with_no_initial_state_is_still_constructed()
    test_build_main_window_applies_an_initial_app_state()
    test_default_args_watch_the_default_state_path_no_demo()
    test_state_file_flag_is_parsed_as_a_path()
    test_demo_flags_are_parsed()
    test_demo_state_flag_is_parsed()
    test_resolve_state_path_defaults_to_the_real_runtime_path()
    test_resolve_state_path_honors_an_explicit_state_file()
    test_resolve_state_path_uses_a_separate_path_in_demo_mode()
    test_resolve_state_path_demo_state_flag_alone_implies_demo_mode()
    test_resolve_state_path_explicit_state_file_wins_even_in_demo_mode()
    test_build_demo_publisher_returns_none_outside_demo_mode()
    test_build_demo_publisher_cycles_all_fixtures_in_plain_demo_mode()
    test_build_demo_publisher_pins_a_single_named_fixture()
    test_build_demo_publisher_raises_for_an_unknown_demo_state_name()
    print("All checks passed.")
