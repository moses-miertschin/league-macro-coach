"""Self-check for src/ui/dev_launcher.py -- the optional development
convenience that launches src/draft/cli.py --watch and src/ui/app.py
together (Stage 8 of the desktop-app session). Written before
dev_launcher.py's implementation.

Only tests pure command-building functions -- never main(), which spawns
two real subprocesses (one of them a real Qt window) and blocks. That
matches this project's established "thin main(), tested functions
underneath" convention and keeps this suite finite, non-interactive, and
free of real subprocess/window creation.
Run with: python -m tests.test_dev_launcher
"""

from src.ui.dev_launcher import build_app_command, build_arg_parser, build_watch_command, resolve_app_args


def test_build_watch_command_uses_the_given_python_executable():
    command = build_watch_command(python_executable="C:/fake/python.exe")

    assert command[0] == "C:/fake/python.exe"
    assert command[1:4] == ["-m", "src.draft.cli", "--watch"]


def test_build_watch_command_omits_interval_by_default():
    command = build_watch_command(python_executable="python")

    assert "--interval" not in command


def test_build_watch_command_includes_interval_when_given():
    command = build_watch_command(python_executable="python", interval=2.5)

    assert "--interval" in command
    assert command[command.index("--interval") + 1] == "2.5"


def test_build_app_command_with_no_extra_args():
    command = build_app_command(python_executable="python")

    assert command == ["python", "-m", "src.ui.app"]


def test_build_app_command_forwards_extra_args():
    command = build_app_command(python_executable="python", extra_args=["--demo", "--verbose"])

    assert command == ["python", "-m", "src.ui.app", "--demo", "--verbose"]


def test_arg_parser_default_has_no_interval_and_no_app_args():
    args = build_arg_parser().parse_args([])

    assert args.interval is None
    assert args.app_args == []


def test_arg_parser_parses_interval():
    args = build_arg_parser().parse_args(["--interval", "3.0"])

    assert args.interval == 3.0


def test_arg_parser_forwards_remaining_args_to_the_app():
    args = build_arg_parser().parse_args(["--", "--demo", "--verbose"])

    assert resolve_app_args(args) == ["--demo", "--verbose"]


def test_resolve_app_args_with_no_forwarded_args():
    args = build_arg_parser().parse_args([])

    assert resolve_app_args(args) == []


def test_resolve_app_args_strips_only_a_leading_separator():
    args = build_arg_parser().parse_args(["--", "--demo"])

    assert resolve_app_args(args) == ["--demo"]


if __name__ == "__main__":
    test_build_watch_command_uses_the_given_python_executable()
    test_build_watch_command_omits_interval_by_default()
    test_build_watch_command_includes_interval_when_given()
    test_build_app_command_with_no_extra_args()
    test_build_app_command_forwards_extra_args()
    test_arg_parser_default_has_no_interval_and_no_app_args()
    test_arg_parser_parses_interval()
    test_arg_parser_forwards_remaining_args_to_the_app()
    test_resolve_app_args_with_no_forwarded_args()
    test_resolve_app_args_strips_only_a_leading_separator()
    print("All checks passed.")
