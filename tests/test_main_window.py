"""Self-check for src/ui/main_window.py -- the QMainWindow that assembles
the four src/ui/widgets/ into one window and drives them from a
presentation dict (Stage 5), plus update_from_state_result() which
bridges a raw src/ui/state_reader.py StateReadResult -- as delivered by
Stage 6's LiveStateSource -- into the window without going through
build_presentation() for the four reader-level statuses it doesn't know
about. Offscreen, non-interactive: no show(), no exec().
Run with: python -m tests.test_main_window
"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QScrollArea

from src.draft.service import CHAMP_SELECT_ACTIVE, LEAGUE_CLIENT_UNAVAILABLE
from src.ui.main_window import MainWindow
from src.ui.state_reader import FILE_MISSING, INVALID_JSON, INVALID_STATE_SHAPE, READ_ERROR, VALID_STATE, StateReadResult

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


def test_update_from_state_result_with_valid_state_behaves_like_update_from_app_state():
    window = MainWindow()
    result = StateReadResult(VALID_STATE, _base_state(LEAGUE_CLIENT_UNAVAILABLE), Path("state.json"), 123.0, None)

    window.update_from_state_result(result)

    assert window.status_header.title_text == "League Client Not Running"


def test_update_from_state_result_file_missing_is_low_severity_and_honest():
    window = MainWindow()
    result = StateReadResult(FILE_MISSING, None, Path("state.json"), None, None)

    window.update_from_state_result(result)

    assert window.status_header.severity == "low"
    assert window.draft_summary.isHidden() is True
    assert window.recommendations.card_count == 0


def test_update_from_state_result_invalid_json_surfaces_the_reader_error():
    window = MainWindow()
    result = StateReadResult(INVALID_JSON, None, Path("state.json"), 123.0, "Invalid JSON: Expecting value (line 1)")

    window.update_from_state_result(result)

    assert window.status_header.severity == "high"
    assert "Invalid JSON" in window.status_header.message_text


def test_update_from_state_result_invalid_shape_surfaces_the_reader_error():
    window = MainWindow()
    result = StateReadResult(INVALID_STATE_SHAPE, None, Path("state.json"), 123.0, "Runtime state does not match the expected shape: missing required key: 'state'")

    window.update_from_state_result(result)

    assert window.status_header.severity == "high"
    assert "missing required key" in window.status_header.message_text


def test_update_from_state_result_read_error_is_handled_honestly():
    window = MainWindow()
    result = StateReadResult(READ_ERROR, None, Path("state.json"), None, "IsADirectoryError while reading state.json")

    window.update_from_state_result(result)

    assert window.status_header.severity == "high"
    assert "IsADirectoryError" in window.status_header.message_text


def test_recommendations_are_wrapped_in_a_scroll_area_so_long_lists_dont_grow_the_window():
    window = MainWindow()
    scroll_areas = window.centralWidget().findChildren(QScrollArea)

    assert len(scroll_areas) == 1
    assert scroll_areas[0].widget() is window.recommendations
    assert scroll_areas[0].widgetResizable() is True


def test_scrolled_recommendations_still_update_normally():
    window = MainWindow()

    window.update_presentation({
        "status_header": {"title": "Champ Select Active", "message": "Live.", "severity": "low", "show_content": True},
        "draft_summary": None,
        "recommendation_cards": [{
            "priority": 1, "category": "pick_recommendation", "subject": "Ashe", "recommendation": "Ashe",
            "reason": "Ashe plays bottom.", "evidence": [], "severity": "medium", "confidence": "high",
            "confidence_score": None, "score_breakdown": {"total": 1}, "source": "champion_knowledge", "details": {},
        }],
        "diagnostics": {"warnings": [], "error": None, "state_schema_version": 1, "champion_catalog_version": None,
                        "unresolved_ally_ids": [], "unresolved_enemy_ids": [], "missing_ally_profiles": []},
    })

    assert window.recommendations.card_count == 1


def test_main_window_has_a_reasonable_default_size():
    window = MainWindow()

    assert window.minimumSize().width() >= 400
    assert window.minimumSize().height() >= 400


def test_update_from_state_result_clears_stale_content_from_a_previous_valid_state():
    snapshot = {
        "current_player": {"cell_id": 0, "champion_id": None, "assigned_position": "bottom"},
        "phase": {"name": "BAN_PICK", "time_left_ms": 1000, "is_infinite": False},
    }
    window = MainWindow()
    window.update_from_state_result(StateReadResult(VALID_STATE, _base_state(CHAMP_SELECT_ACTIVE, draft_snapshot=snapshot), Path("state.json"), 1.0, None))
    assert window.draft_summary.isHidden() is False

    window.update_from_state_result(StateReadResult(FILE_MISSING, None, Path("state.json"), None, None))

    assert window.draft_summary.isHidden() is True


if __name__ == "__main__":
    test_main_window_constructs_with_all_four_sections()
    test_update_presentation_drives_all_four_widgets()
    test_update_from_app_state_builds_the_presentation_internally()
    test_update_from_app_state_resolves_champion_names_via_lookup()
    test_update_from_state_result_with_valid_state_behaves_like_update_from_app_state()
    test_update_from_state_result_file_missing_is_low_severity_and_honest()
    test_update_from_state_result_invalid_json_surfaces_the_reader_error()
    test_update_from_state_result_invalid_shape_surfaces_the_reader_error()
    test_update_from_state_result_read_error_is_handled_honestly()
    test_recommendations_are_wrapped_in_a_scroll_area_so_long_lists_dont_grow_the_window()
    test_scrolled_recommendations_still_update_normally()
    test_main_window_has_a_reasonable_default_size()
    test_update_from_state_result_clears_stale_content_from_a_previous_valid_state()
    print("All checks passed.")
