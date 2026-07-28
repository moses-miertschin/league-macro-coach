"""Self-check for src/ui/main_window.py -- the QMainWindow that assembles
the four src/ui/widgets/ into one window and drives them from a
presentation dict (Stage 5 of the desktop-app session). Written before
main_window.py's implementation. Offscreen, non-interactive: no show(),
no exec(). Run with: python -m tests.test_main_window
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.draft.service import CHAMP_SELECT_ACTIVE, LEAGUE_CLIENT_UNAVAILABLE
from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


def _base_state(state, **overrides):
    base = {
        "state_schema_version": 1, "state": state, "draft_snapshot": None, "recommendations": [],
        "champion_catalog_version": None, "warnings": [], "error": None,
    }
    base.update(overrides)
    return base


def test_main_window_constructs_with_all_four_sections():
    window = MainWindow()

    assert window.status_header is not None
    assert window.draft_summary is not None
    assert window.recommendations is not None
    assert window.diagnostics is not None


def test_update_presentation_drives_all_four_widgets():
    window = MainWindow()
    presentation = {
        "status_header": {"title": "Champ Select Active", "message": "Live.", "severity": "low", "show_content": True},
        "draft_summary": {"phase_name": "BAN_PICK", "time_left_ms": 1000, "is_infinite": False, "role": "bottom", "champion_id": None, "champion_display_name": None},
        "recommendation_cards": [{
            "priority": 1, "category": "pick_recommendation", "subject": "Ashe", "recommendation": "Ashe",
            "reason": "Ashe plays bottom.", "evidence": [], "severity": "medium", "confidence": "high",
            "confidence_score": None, "score_breakdown": {"total": 1}, "source": "champion_knowledge", "details": {},
        }],
        "diagnostics": {"warnings": [], "error": None, "state_schema_version": 1, "champion_catalog_version": "14.1.1",
                        "unresolved_ally_ids": [], "unresolved_enemy_ids": [], "missing_ally_profiles": []},
    }

    window.update_presentation(presentation)

    assert window.status_header.title_text == "Champ Select Active"
    assert window.draft_summary.isHidden() is False
    assert window.recommendations.card_count == 1
    assert "14.1.1" in window.diagnostics.text


def test_update_from_app_state_builds_the_presentation_internally():
    window = MainWindow()

    window.update_from_app_state(_base_state(LEAGUE_CLIENT_UNAVAILABLE))

    assert window.status_header.title_text == "League Client Not Running"
    assert window.draft_summary.isHidden() is True


def test_update_from_app_state_resolves_champion_names_via_lookup():
    snapshot = {
        "current_player": {"cell_id": 0, "champion_id": 22, "assigned_position": "bottom"},
        "phase": {"name": "BAN_PICK", "time_left_ms": 1000, "is_infinite": False},
    }
    window = MainWindow()

    window.update_from_app_state(
        _base_state(CHAMP_SELECT_ACTIVE, draft_snapshot=snapshot),
        name_lookup=lambda cid: "Ashe" if cid == 22 else None,
    )

    assert "Ashe" in window.draft_summary.champion_text


if __name__ == "__main__":
    test_main_window_constructs_with_all_four_sections()
    test_update_presentation_drives_all_four_widgets()
    test_update_from_app_state_builds_the_presentation_internally()
    test_update_from_app_state_resolves_champion_names_via_lookup()
    print("All checks passed.")
