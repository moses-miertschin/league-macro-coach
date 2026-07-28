"""The desktop application's entry point. build_application()/
build_main_window() are the non-blocking factories the automated test
suite exercises directly; main() is the thin, untested-by-design wrapper
that enters Qt's blocking event loop, matching src/draft/cli.py's
existing "thin main(), tested building blocks underneath" convention.

main() wires a real LiveStateSource (Stage 6) against the default
runtime state path, so `python -m src.ui.app` already live-updates
against whatever src/draft/cli.py --watch is publishing -- with no CLI
argument parsing yet (--state-file/--demo/etc. are Stage 7). The watcher
is stopped via QApplication.aboutToQuit so its background thread never
outlives the window.

Run with: python -m src.ui.app
"""

import sys

from PySide6.QtWidgets import QApplication

from src.ui.live_state_source import LiveStateSource
from src.ui.main_window import MainWindow


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


def main(argv: list | None = None) -> int:
    app = build_application(argv if argv is not None else sys.argv)
    window = build_main_window()

    source = LiveStateSource()
    source.state_changed.connect(window.update_from_state_result)
    app.aboutToQuit.connect(lambda: source.stop())
    source.start()

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
