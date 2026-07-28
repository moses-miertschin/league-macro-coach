"""The desktop application's entry point. This stage only builds the
QApplication/MainWindow shell -- no data source is wired in yet (that's
Stage 6's live file-watcher integration), and there's no CLI argument
parsing yet (Stage 7). build_application()/build_main_window() are the
non-blocking factories the automated test suite exercises directly;
main() is the thin, untested-by-design wrapper that enters Qt's blocking
event loop, matching src/draft/cli.py's existing "thin main(), tested
building blocks underneath" convention.

Run with: python -m src.ui.app
"""

import sys

from PySide6.QtWidgets import QApplication

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
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
