"""Self-check for src/ui/app.py -- the QApplication/MainWindow factory
(Stage 5 of the desktop-app session). Written before app.py's
implementation. Only tests the non-blocking factory functions
(build_application, build_main_window) -- never main(), which enters
Qt's blocking event loop and is exercised manually/by a future desktop
CLI (Stage 7), not by this automated, non-interactive suite.
Run with: python -m tests.test_app
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.draft.service import IDLE_NO_CHAMP_SELECT
from src.ui.app import build_application, build_main_window
from src.ui.main_window import MainWindow


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


if __name__ == "__main__":
    test_build_application_returns_a_qapplication()
    test_build_application_reuses_the_existing_instance()
    test_build_main_window_with_no_initial_state_is_still_constructed()
    test_build_main_window_applies_an_initial_app_state()
    print("All checks passed.")
