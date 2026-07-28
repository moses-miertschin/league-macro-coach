"""The desktop application's entry point. build_application()/
build_main_window()/build_arg_parser()/resolve_state_path()/
build_demo_publisher() are the non-blocking building blocks the
automated test suite exercises directly; main() is the thin,
untested-by-design wrapper that parses argv and enters Qt's blocking
event loop, matching src/draft/cli.py's existing "thin main(), tested
helpers underneath" convention.

Two run modes, both wired through the exact same LiveStateSource (Stage
6) -> MainWindow.update_from_state_result() path -- --demo never bypasses
that pipeline for a second, demo-only rendering path:

  Real mode (default): watches reports/runtime/draft_state.json (or
  --state-file), the file src/draft/cli.py --once/--watch publishes.

  Demo mode (--demo / --demo-state NAME): a DemoStatePublisher (Stage 7)
  writes demo/states/ fixtures (Stage 4) through the real publish_state()
  into a separate demo-only path, while an ordinary LiveStateSource
  watches that same path -- demo mode differs only in *what's being
  published*, never in how it's delivered to the window.

Run with: python -m src.ui.app [--state-file PATH | --demo | --demo-state NAME] [--demo-interval SECONDS] [--verbose]
"""

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.ui.demo_fixtures import load_demo_state_by_name, load_demo_states
from src.ui.demo_publisher import DemoStatePublisher
from src.ui.live_state_source import LiveStateSource
from src.ui.main_window import MainWindow
from src.ui.state_reader import DEFAULT_STATE_PATH

DEFAULT_DEMO_STATE_PATH = DEFAULT_STATE_PATH.parent / "demo_draft_state.json"


def build_application(argv: list | None = None) -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication(argv if argv is not None else [])


def build_main_window(app_state: dict | None = None, name_lookup=None) -> MainWindow:
    window = MainWindow()
    if app_state is not None:
        window.update_from_app_state(app_state, name_lookup=name_lookup)
    return window


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LeagueMacroCoach desktop draft assistant.")
    parser.add_argument(
        "--state-file", type=Path, default=None,
        help="Path to the runtime state JSON file to watch (default: reports/runtime/draft_state.json).",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run in demo mode, cycling through demo/states/ fixtures instead of watching real data.",
    )
    parser.add_argument(
        "--demo-state", default=None,
        help="Show one named demo/states/ fixture (e.g. 03_champ_select_prelock_recommendations). Implies --demo, no cycling.",
    )
    parser.add_argument(
        "--demo-interval", type=float, default=5.0,
        help="Seconds between demo fixture changes in cycling --demo mode (default: 5.0).",
    )
    parser.add_argument("--verbose", action="store_true", help="Print each received state update to the console.")
    return parser


def _is_demo_mode(args: argparse.Namespace) -> bool:
    return args.demo or args.demo_state is not None


def resolve_state_path(args: argparse.Namespace) -> Path:
    if args.state_file is not None:
        return args.state_file
    if _is_demo_mode(args):
        return DEFAULT_DEMO_STATE_PATH
    return DEFAULT_STATE_PATH


def build_demo_publisher(args: argparse.Namespace, output_path: Path, publish_fn=None):
    if not _is_demo_mode(args):
        return None
    if args.demo_state is not None:
        states = [load_demo_state_by_name(args.demo_state)]
    else:
        states = load_demo_states()
    kwargs = {"interval_seconds": args.demo_interval}
    if publish_fn is not None:
        kwargs["publish_fn"] = publish_fn
    return DemoStatePublisher(states, output_path=output_path, **kwargs)


def _print_state_result(result) -> None:
    suffix = f": {result.error}" if result.error else ""
    print(f"[state] {result.status}{suffix}")


def main(argv: list | None = None) -> int:
    args = build_arg_parser().parse_args(argv if argv is not None else sys.argv[1:])

    app = build_application([])
    window = build_main_window()

    watch_path = resolve_state_path(args)
    demo_publisher = build_demo_publisher(args, watch_path)

    source = LiveStateSource(path=watch_path)
    source.state_changed.connect(window.update_from_state_result)
    if args.verbose:
        source.state_changed.connect(_print_state_result)

    def _shutdown():
        source.stop()
        if demo_publisher is not None:
            demo_publisher.stop()

    app.aboutToQuit.connect(_shutdown)

    if demo_publisher is not None:
        demo_publisher.start()
    source.start()

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
