"""Self-check for src/ui/presentation.py -- the toolkit-independent
transform of a DraftRuntimeService-shaped app-state dict into stable
render structures (Stage 3 of the desktop-app session). Written before
presentation.py's implementation. No PySide6, no filesystem, no network.
Run with: python -m tests.test_presentation
"""

import copy

from src.draft.service import (
    CHAMP_SELECT_ACTIVE,
    IDLE_NO_CHAMP_SELECT,
    LEAGUE_CLIENT_UNAVAILABLE,
    PROCESSING_ERROR,
)
from src.ui.presentation import (
    build_diagnostics,
    build_draft_summary,
    build_presentation,
    build_recommendation_cards,
    build_status_header,
)


def _base_state(state, **overrides):
    base = {
        "state_schema_version": 1,
        "state": state,
        "draft_snapshot": None,
        "recommendations": [],
        "champion_catalog_version": None,
        "warnings": [],
        "error": None,
    }
    base.update(overrides)
    return base


def _pick_recommendation_entry(**overrides):
    entry = {
        "system": "draft",
        "category": "pick_recommendation",
        "subject": "Ashe",
        "recommendation": "Ashe",
        "reason": "Ashe plays bottom.",
        "evidence": [{"fact": "role_fit", "champion": "Ashe", "role": "bottom"}],
        "confidence": "high",
        "confidence_score": None,
        "severity": "medium",
        "priority": 1,
        "source": "champion_knowledge",
        "details": {
            "player_role": "bottom",
            "score_breakdown": {"role_fit": "required", "damage_balance": 2, "direct_synergy": 0, "total": 2},
            "unresolved_ally_ids": [123],
            "unresolved_enemy_ids": [456],
            "missing_ally_profiles": ["SomeAlly"],
        },
    }
    entry.update(overrides)
    return entry


# ---------------------------------------------------------------------------
# build_status_header
# ---------------------------------------------------------------------------


def test_status_header_for_each_non_error_state():
    for state in (LEAGUE_CLIENT_UNAVAILABLE, IDLE_NO_CHAMP_SELECT, CHAMP_SELECT_ACTIVE):
        header = build_status_header(_base_state(state))
        assert header["title"]
        assert header["message"]
        assert header["severity"] in ("low", "medium", "high")
        assert isinstance(header["show_content"], bool)


def test_status_header_shows_content_only_for_champ_select_active():
    assert build_status_header(_base_state(CHAMP_SELECT_ACTIVE))["show_content"] is True
    assert build_status_header(_base_state(LEAGUE_CLIENT_UNAVAILABLE))["show_content"] is False
    assert build_status_header(_base_state(IDLE_NO_CHAMP_SELECT))["show_content"] is False


def test_status_header_for_processing_error_surfaces_the_real_error_message():
    header = build_status_header(_base_state(PROCESSING_ERROR, error="recommender raised: ValueError('boom')"))

    assert header["severity"] == "high"
    assert header["show_content"] is False
    assert "boom" in header["message"]


def test_status_header_processing_error_without_message_has_honest_fallback():
    header = build_status_header(_base_state(PROCESSING_ERROR, error=None))

    assert header["message"]  # never blank


def test_status_header_unknown_state_is_handled_honestly_not_a_crash():
    header = build_status_header(_base_state("some_future_state"))

    assert header["severity"] == "high"
    assert "some_future_state" in header["message"]
    assert header["show_content"] is False


# ---------------------------------------------------------------------------
# build_draft_summary
# ---------------------------------------------------------------------------


def test_draft_summary_is_none_when_no_snapshot():
    assert build_draft_summary(_base_state(IDLE_NO_CHAMP_SELECT)) is None


def test_draft_summary_reports_phase_and_role():
    snapshot = {
        "current_player": {"cell_id": 0, "champion_id": None, "assigned_position": "bottom"},
        "phase": {"name": "BAN_PICK", "time_left_ms": 30000, "is_infinite": False},
    }
    summary = build_draft_summary(_base_state(CHAMP_SELECT_ACTIVE, draft_snapshot=snapshot))

    assert summary["phase_name"] == "BAN_PICK"
    assert summary["time_left_ms"] == 30000
    assert summary["is_infinite"] is False
    assert summary["role"] == "bottom"


def test_draft_summary_no_champion_selected_yet_has_no_display_name():
    snapshot = {
        "current_player": {"cell_id": 0, "champion_id": None, "assigned_position": "bottom"},
        "phase": {},
    }
    summary = build_draft_summary(_base_state(CHAMP_SELECT_ACTIVE, draft_snapshot=snapshot))

    assert summary["champion_id"] is None
    assert summary["champion_display_name"] is None


def test_draft_summary_champion_id_without_a_lookup_falls_back_to_honest_id_label():
    snapshot = {
        "current_player": {"cell_id": 0, "champion_id": 22, "assigned_position": "bottom"},
        "phase": {},
    }
    summary = build_draft_summary(_base_state(CHAMP_SELECT_ACTIVE, draft_snapshot=snapshot), name_lookup=None)

    assert summary["champion_display_name"] == "Champion ID 22"


def test_draft_summary_champion_id_resolved_via_lookup():
    snapshot = {
        "current_player": {"cell_id": 0, "champion_id": 22, "assigned_position": "bottom"},
        "phase": {},
    }
    summary = build_draft_summary(
        _base_state(CHAMP_SELECT_ACTIVE, draft_snapshot=snapshot), name_lookup=lambda cid: "Ashe" if cid == 22 else None,
    )

    assert summary["champion_display_name"] == "Ashe"


def test_draft_summary_champion_id_unresolved_by_lookup_never_fabricates_a_name():
    snapshot = {
        "current_player": {"cell_id": 0, "champion_id": 9999, "assigned_position": "bottom"},
        "phase": {},
    }
    summary = build_draft_summary(
        _base_state(CHAMP_SELECT_ACTIVE, draft_snapshot=snapshot), name_lookup=lambda cid: None,
    )

    assert "9999" in summary["champion_display_name"]
    assert summary["champion_display_name"] != "Ashe"


# ---------------------------------------------------------------------------
# build_recommendation_cards
# ---------------------------------------------------------------------------


def test_recommendation_cards_empty_when_no_recommendations():
    assert build_recommendation_cards(_base_state(CHAMP_SELECT_ACTIVE, recommendations=[])) == []


def test_recommendation_cards_preserve_ordering_and_fields():
    entries = [_pick_recommendation_entry(priority=1, subject="Ashe"), _pick_recommendation_entry(priority=2, subject="Jinx")]
    cards = build_recommendation_cards(_base_state(CHAMP_SELECT_ACTIVE, recommendations=entries))

    assert [c["subject"] for c in cards] == ["Ashe", "Jinx"]
    assert cards[0]["recommendation"] == "Ashe"
    assert cards[0]["reason"] == "Ashe plays bottom."
    assert cards[0]["category"] == "pick_recommendation"
    assert cards[0]["confidence"] == "high"
    assert cards[0]["severity"] == "medium"
    assert cards[0]["source"] == "champion_knowledge"


def test_recommendation_cards_preserve_score_breakdown_exactly_without_recomputing():
    entry = _pick_recommendation_entry()
    cards = build_recommendation_cards(_base_state(CHAMP_SELECT_ACTIVE, recommendations=[entry]))

    assert cards[0]["score_breakdown"] == entry["details"]["score_breakdown"]


def test_recommendation_cards_unavailable_entry_is_preserved_not_dropped():
    entry = _pick_recommendation_entry(
        recommendation=None, confidence="unavailable", severity="unavailable", subject="role_unavailable",
    )
    cards = build_recommendation_cards(_base_state(CHAMP_SELECT_ACTIVE, recommendations=[entry]))

    assert len(cards) == 1
    assert cards[0]["recommendation"] is None
    assert cards[0]["confidence"] == "unavailable"


def test_recommendation_cards_skip_malformed_entries_missing_required_fields():
    good = _pick_recommendation_entry(subject="Ashe")
    malformed = {"subject": "Broken"}  # missing category/recommendation/reason/severity/confidence/priority
    cards = build_recommendation_cards(_base_state(CHAMP_SELECT_ACTIVE, recommendations=[good, malformed]))

    assert len(cards) == 1
    assert cards[0]["subject"] == "Ashe"


def test_recommendation_cards_skip_non_dict_entries():
    cards = build_recommendation_cards(_base_state(CHAMP_SELECT_ACTIVE, recommendations=["not a dict", None, 42]))

    assert cards == []


# ---------------------------------------------------------------------------
# build_diagnostics
# ---------------------------------------------------------------------------


def test_diagnostics_defaults_when_no_recommendations():
    diagnostics = build_diagnostics(_base_state(IDLE_NO_CHAMP_SELECT))

    assert diagnostics["warnings"] == []
    assert diagnostics["error"] is None
    assert diagnostics["unresolved_ally_ids"] == []
    assert diagnostics["unresolved_enemy_ids"] == []
    assert diagnostics["missing_ally_profiles"] == []


def test_diagnostics_pulls_unresolved_ids_and_missing_profiles_from_recommendations():
    entry = _pick_recommendation_entry()
    diagnostics = build_diagnostics(_base_state(CHAMP_SELECT_ACTIVE, recommendations=[entry]))

    assert diagnostics["unresolved_ally_ids"] == [123]
    assert diagnostics["unresolved_enemy_ids"] == [456]
    assert diagnostics["missing_ally_profiles"] == ["SomeAlly"]


def test_diagnostics_reports_schema_and_catalog_version():
    diagnostics = build_diagnostics(_base_state(CHAMP_SELECT_ACTIVE, champion_catalog_version="14.1.1"))

    assert diagnostics["state_schema_version"] == 1
    assert diagnostics["champion_catalog_version"] == "14.1.1"


# ---------------------------------------------------------------------------
# build_presentation (top-level combinator) + no-mutation guarantee
# ---------------------------------------------------------------------------


def test_build_presentation_combines_all_sections():
    snapshot = {
        "current_player": {"cell_id": 0, "champion_id": None, "assigned_position": "bottom"},
        "phase": {"name": "BAN_PICK", "time_left_ms": 1000, "is_infinite": False},
    }
    state = _base_state(CHAMP_SELECT_ACTIVE, draft_snapshot=snapshot, recommendations=[_pick_recommendation_entry()])

    presentation = build_presentation(state)

    assert presentation["status_header"]["show_content"] is True
    assert presentation["draft_summary"]["role"] == "bottom"
    assert len(presentation["recommendation_cards"]) == 1
    assert presentation["diagnostics"]["unresolved_ally_ids"] == [123]


def test_build_presentation_never_mutates_the_input_state():
    snapshot = {
        "current_player": {"cell_id": 0, "champion_id": 22, "assigned_position": "bottom"},
        "phase": {"name": "BAN_PICK", "time_left_ms": 1000, "is_infinite": False},
    }
    state = _base_state(CHAMP_SELECT_ACTIVE, draft_snapshot=snapshot, recommendations=[_pick_recommendation_entry()])
    before = copy.deepcopy(state)

    build_presentation(state, name_lookup=lambda cid: "Ashe")

    assert state == before


if __name__ == "__main__":
    test_status_header_for_each_non_error_state()
    test_status_header_shows_content_only_for_champ_select_active()
    test_status_header_for_processing_error_surfaces_the_real_error_message()
    test_status_header_processing_error_without_message_has_honest_fallback()
    test_status_header_unknown_state_is_handled_honestly_not_a_crash()
    test_draft_summary_is_none_when_no_snapshot()
    test_draft_summary_reports_phase_and_role()
    test_draft_summary_no_champion_selected_yet_has_no_display_name()
    test_draft_summary_champion_id_without_a_lookup_falls_back_to_honest_id_label()
    test_draft_summary_champion_id_resolved_via_lookup()
    test_draft_summary_champion_id_unresolved_by_lookup_never_fabricates_a_name()
    test_recommendation_cards_empty_when_no_recommendations()
    test_recommendation_cards_preserve_ordering_and_fields()
    test_recommendation_cards_preserve_score_breakdown_exactly_without_recomputing()
    test_recommendation_cards_unavailable_entry_is_preserved_not_dropped()
    test_recommendation_cards_skip_malformed_entries_missing_required_fields()
    test_recommendation_cards_skip_non_dict_entries()
    test_diagnostics_defaults_when_no_recommendations()
    test_diagnostics_pulls_unresolved_ids_and_missing_profiles_from_recommendations()
    test_diagnostics_reports_schema_and_catalog_version()
    test_build_presentation_combines_all_sections()
    test_build_presentation_never_mutates_the_input_state()
    print("All checks passed.")
