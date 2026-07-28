"""Self-check for src/draft/recommender.py -- the first deterministic draft
recommendation engine.

Written before recommender.py's implementation. Uses a hand-built fake
champion catalog and a fake profile_loader_fn for most tests (no network,
no real Data Dragon fetch) -- except one explicit integration test that
uses the real default profile_loader_fn against the real
knowledge/champions/yone_profile.md authored in an earlier checkpoint, to
prove the whole chain works end to end, not just against fakes.
Run with: python -m tests.test_draft_recommender
"""

import inspect

from src.draft.recommender import recommend_draft
from src.knowledge.champion_loader import load_champion_profile
from src.recommendations.schema import validate_recommendation

FAKE_CATALOG = {
    "champions_by_id": {
        157: {"id": 157, "name": "Yone"},
        54: {"id": 54, "name": "Malphite"},
        238: {"id": 238, "name": "Zed"},
        111: {"id": 111, "name": "Nautilus"},
        99: {"id": 99, "name": "Lux"},
    },
    "champions_by_name": {
        "yone": {"id": 157, "name": "Yone"},
        "malphite": {"id": 54, "name": "Malphite"},
        "zed": {"id": 238, "name": "Zed"},
        "nautilus": {"id": 111, "name": "Nautilus"},
        "lux": {"id": 99, "name": "Lux"},
    },
}

FAKE_YONE_PROFILE = {
    "champion": "Yone",
    "roles": ["middle"],
    "damage_type": "hybrid",
    "scaling_profile": "scales_throughout",
    "strengths": [],
    "weaknesses": [],
    "preferred_playstyle": None,
    "common_counters": ["Malphite"],
    "favorable_matchups": ["Zed"],
    "synergy_champions": ["Nautilus"],
}


def _fake_profile_loader(champion_name):
    return {"Yone": FAKE_YONE_PROFILE}.get(champion_name)


def _snapshot(current_champion_id=157, enemy_picks=None, ally_picks=None, assigned_position="middle"):
    return {
        "ally_team": [],
        "enemy_team": [],
        "ally_picks": ally_picks or [],
        "enemy_picks": enemy_picks or [],
        "ally_bans": [],
        "enemy_bans": [],
        "current_player": {"cell_id": 2, "champion_id": current_champion_id, "assigned_position": assigned_position},
        "phase": {"name": "BAN_PICK", "time_left_ms": 30000, "is_infinite": False},
    }


def test_flags_enemy_counter_pick():
    snapshot = _snapshot(enemy_picks=[54])  # Malphite counters Yone

    result = recommend_draft(snapshot, FAKE_CATALOG, profile_loader_fn=_fake_profile_loader)

    assert len(result) == 1
    entry = result[0]
    assert entry["system"] == "draft"
    assert entry["category"] == "counter_warning"
    assert entry["subject"] == "Malphite"
    assert entry["severity"] == "high"
    assert entry["priority"] == 1
    assert entry["source"] == "champion_knowledge"
    assert validate_recommendation(entry) == []


def test_flags_favorable_matchup():
    snapshot = _snapshot(enemy_picks=[238])  # Zed is favorable for Yone

    result = recommend_draft(snapshot, FAKE_CATALOG, profile_loader_fn=_fake_profile_loader)

    assert len(result) == 1
    assert result[0]["category"] == "favorable_matchup"
    assert result[0]["subject"] == "Zed"
    assert result[0]["severity"] == "low"


def test_flags_ally_synergy():
    snapshot = _snapshot(ally_picks=[111])  # Nautilus synergizes with Yone

    result = recommend_draft(snapshot, FAKE_CATALOG, profile_loader_fn=_fake_profile_loader)

    assert len(result) == 1
    assert result[0]["category"] == "ally_synergy"
    assert result[0]["subject"] == "Nautilus"
    assert result[0]["severity"] == "medium"


def test_unrelated_pick_produces_no_entry():
    snapshot = _snapshot(enemy_picks=[99])  # Lux has no relationship to Yone in the fixture

    result = recommend_draft(snapshot, FAKE_CATALOG, profile_loader_fn=_fake_profile_loader)

    assert result == []


def test_multiple_signals_sorted_by_severity_and_prioritized():
    snapshot = _snapshot(enemy_picks=[54, 238], ally_picks=[111])

    result = recommend_draft(snapshot, FAKE_CATALOG, profile_loader_fn=_fake_profile_loader)

    assert [e["category"] for e in result] == ["counter_warning", "ally_synergy", "favorable_matchup"]
    assert [e["priority"] for e in result] == [1, 2, 3]
    for entry in result:
        assert validate_recommendation(entry) == []


def test_no_snapshot_returns_empty_list():
    assert recommend_draft(None, FAKE_CATALOG, profile_loader_fn=_fake_profile_loader) == []


def test_no_current_player_champion_picked_yet_returns_empty_list():
    snapshot = _snapshot(current_champion_id=None)
    assert recommend_draft(snapshot, FAKE_CATALOG, profile_loader_fn=_fake_profile_loader) == []


def test_unresolvable_current_player_champion_id_returns_empty_list_never_guesses():
    snapshot = _snapshot(current_champion_id=999999)  # not in the catalog
    assert recommend_draft(snapshot, FAKE_CATALOG, profile_loader_fn=_fake_profile_loader) == []


def test_missing_profile_for_current_player_champion_returns_empty_list():
    snapshot = _snapshot(enemy_picks=[54])
    assert recommend_draft(snapshot, FAKE_CATALOG, profile_loader_fn=lambda _name: None) == []


def test_unresolvable_enemy_or_ally_ids_are_skipped_not_fabricated():
    snapshot = _snapshot(enemy_picks=[54, 424242], ally_picks=[111, 555555])

    result = recommend_draft(snapshot, FAKE_CATALOG, profile_loader_fn=_fake_profile_loader)

    assert {e["subject"] for e in result} == {"Malphite", "Nautilus"}


def test_player_role_included_in_details_when_available():
    snapshot = _snapshot(enemy_picks=[54], assigned_position="middle")

    result = recommend_draft(snapshot, FAKE_CATALOG, profile_loader_fn=_fake_profile_loader)

    assert result[0]["details"]["player_role"] == "middle"


def test_default_profile_loader_is_the_real_champion_loader():
    sig = inspect.signature(recommend_draft)
    assert sig.parameters["profile_loader_fn"].default is load_champion_profile


def test_integration_with_real_yone_profile_file_on_disk():
    # No fake profile_loader_fn here -- uses the real default, which reads
    # the real knowledge/champions/yone_profile.md authored in an earlier
    # checkpoint. Proves catalog -> profile loader -> recommender works as
    # a whole, not just against hand-built fakes.
    snapshot = _snapshot(current_champion_id=157, enemy_picks=[54])  # Yone vs. Malphite

    result = recommend_draft(snapshot, FAKE_CATALOG)

    assert len(result) == 1
    assert result[0]["subject"] == "Malphite"
    assert result[0]["category"] == "counter_warning"
    assert validate_recommendation(result[0]) == []


if __name__ == "__main__":
    test_flags_enemy_counter_pick()
    test_flags_favorable_matchup()
    test_flags_ally_synergy()
    test_unrelated_pick_produces_no_entry()
    test_multiple_signals_sorted_by_severity_and_prioritized()
    test_no_snapshot_returns_empty_list()
    test_no_current_player_champion_picked_yet_returns_empty_list()
    test_unresolvable_current_player_champion_id_returns_empty_list_never_guesses()
    test_missing_profile_for_current_player_champion_returns_empty_list()
    test_unresolvable_enemy_or_ally_ids_are_skipped_not_fabricated()
    test_player_role_included_in_details_when_available()
    test_default_profile_loader_is_the_real_champion_loader()
    test_integration_with_real_yone_profile_file_on_disk()
    print("All checks passed.")
