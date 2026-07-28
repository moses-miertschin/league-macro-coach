"""Self-check for src/ui/widgets/ -- the individual PySide6 widgets that
render one section each of src/ui/presentation.py's output (Stage 5 of
the desktop-app session). Written before the widget implementations.

Runs in offscreen mode (QT_QPA_PLATFORM set before any PySide6 import) so
it's non-interactive and CI-safe -- no window is ever shown, no event
loop is ever entered; every widget is just constructed and inspected.
Run with: python -m tests.test_ui_widgets
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.ui.widgets.diagnostics import DiagnosticsWidget
from src.ui.widgets.draft_summary import DraftSummaryWidget
from src.ui.widgets.recommendations import RecommendationListWidget
from src.ui.widgets.status_header import StatusHeaderWidget

_app = QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# StatusHeaderWidget
# ---------------------------------------------------------------------------


def test_status_header_widget_displays_title_and_message():
    widget = StatusHeaderWidget()
    widget.update_header({"title": "Champ Select Active", "message": "Live draft recommendations below.", "severity": "low", "show_content": True})

    assert widget.title_text == "Champ Select Active"
    assert widget.message_text == "Live draft recommendations below."
    assert widget.severity == "low"


def test_status_header_widget_updates_on_repeated_calls():
    widget = StatusHeaderWidget()
    widget.update_header({"title": "A", "message": "a", "severity": "low", "show_content": True})
    widget.update_header({"title": "B", "message": "b", "severity": "high", "show_content": False})

    assert widget.title_text == "B"
    assert widget.message_text == "b"
    assert widget.severity == "high"


# ---------------------------------------------------------------------------
# DraftSummaryWidget
# ---------------------------------------------------------------------------


def test_draft_summary_widget_hides_when_summary_is_none():
    widget = DraftSummaryWidget()
    widget.update_summary(None)

    assert widget.isHidden() is True


def test_draft_summary_widget_shows_phase_role_and_champion():
    widget = DraftSummaryWidget()
    widget.update_summary({
        "phase_name": "BAN_PICK", "time_left_ms": 30000, "is_infinite": False,
        "role": "bottom", "champion_id": 22, "champion_display_name": "Champion ID 22",
    })

    assert "BAN_PICK" in widget.phase_text
    assert "bottom" in widget.role_text
    assert "Champion ID 22" in widget.champion_text


def test_draft_summary_widget_no_champion_selected_shows_honest_placeholder():
    widget = DraftSummaryWidget()
    widget.update_summary({
        "phase_name": "PLANNING", "time_left_ms": None, "is_infinite": None,
        "role": "bottom", "champion_id": None, "champion_display_name": None,
    })

    assert "No champion" in widget.champion_text


# ---------------------------------------------------------------------------
# RecommendationListWidget
# ---------------------------------------------------------------------------


def _card(**overrides):
    card = {
        "priority": 1, "category": "pick_recommendation", "subject": "Ashe", "recommendation": "Ashe",
        "reason": "Ashe plays bottom.", "evidence": [], "severity": "medium", "confidence": "high",
        "confidence_score": None, "score_breakdown": {"total": 1}, "source": "champion_knowledge", "details": {},
    }
    card.update(overrides)
    return card


def test_recommendation_list_widget_empty_shows_no_cards():
    widget = RecommendationListWidget()
    widget.update_cards([])

    assert widget.card_count == 0


def test_recommendation_list_widget_renders_one_card_per_entry_in_order():
    widget = RecommendationListWidget()
    widget.update_cards([_card(subject="Ashe", priority=1), _card(subject="Jinx", priority=2)])

    assert widget.card_count == 2
    texts = widget.card_texts
    assert "Ashe" in texts[0]
    assert "Jinx" in texts[1]


def test_recommendation_list_widget_shows_reason_and_severity():
    widget = RecommendationListWidget()
    widget.update_cards([_card(reason="Test reason string.", severity="high")])

    assert "Test reason string." in widget.card_texts[0]
    assert "high" in widget.card_texts[0]


def test_recommendation_list_widget_handles_null_recommendation_callouts():
    widget = RecommendationListWidget()
    widget.update_cards([_card(recommendation=None, subject="Malphite", category="counter_warning")])

    assert widget.card_count == 1
    assert "Malphite" in widget.card_texts[0]


def test_recommendation_list_widget_clears_old_cards_on_update():
    widget = RecommendationListWidget()
    widget.update_cards([_card(subject="Ashe"), _card(subject="Jinx")])
    widget.update_cards([_card(subject="Malphite")])

    assert widget.card_count == 1
    assert "Malphite" in widget.card_texts[0]


# ---------------------------------------------------------------------------
# DiagnosticsWidget
# ---------------------------------------------------------------------------


def test_diagnostics_widget_shows_error_when_present():
    widget = DiagnosticsWidget()
    widget.update_diagnostics({
        "warnings": [], "error": "recommender raised: ValueError('boom')", "state_schema_version": 1,
        "champion_catalog_version": None, "unresolved_ally_ids": [], "unresolved_enemy_ids": [], "missing_ally_profiles": [],
    })

    assert "boom" in widget.text


def test_diagnostics_widget_shows_unresolved_ids_and_missing_profiles():
    widget = DiagnosticsWidget()
    widget.update_diagnostics({
        "warnings": [], "error": None, "state_schema_version": 1, "champion_catalog_version": "14.1.1",
        "unresolved_ally_ids": [123], "unresolved_enemy_ids": [456], "missing_ally_profiles": ["SomeAlly"],
    })

    assert "123" in widget.text
    assert "456" in widget.text
    assert "SomeAlly" in widget.text
    assert "14.1.1" in widget.text


def test_diagnostics_widget_clean_state_has_no_error_text():
    widget = DiagnosticsWidget()
    widget.update_diagnostics({
        "warnings": [], "error": None, "state_schema_version": 1, "champion_catalog_version": None,
        "unresolved_ally_ids": [], "unresolved_enemy_ids": [], "missing_ally_profiles": [],
    })

    assert "Error:" not in widget.text


if __name__ == "__main__":
    test_status_header_widget_displays_title_and_message()
    test_status_header_widget_updates_on_repeated_calls()
    test_draft_summary_widget_hides_when_summary_is_none()
    test_draft_summary_widget_shows_phase_role_and_champion()
    test_draft_summary_widget_no_champion_selected_shows_honest_placeholder()
    test_recommendation_list_widget_empty_shows_no_cards()
    test_recommendation_list_widget_renders_one_card_per_entry_in_order()
    test_recommendation_list_widget_shows_reason_and_severity()
    test_recommendation_list_widget_handles_null_recommendation_callouts()
    test_recommendation_list_widget_clears_old_cards_on_update()
    test_diagnostics_widget_shows_error_when_present()
    test_diagnostics_widget_shows_unresolved_ids_and_missing_profiles()
    test_diagnostics_widget_clean_state_has_no_error_text()
    print("All checks passed.")
