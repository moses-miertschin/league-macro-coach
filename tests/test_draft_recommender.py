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

import copy
import inspect

from src.draft.recommender import DAMAGE_BALANCE_BONUS, DIRECT_SYNERGY_BONUS, recommend_draft
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


def test_no_current_player_champion_picked_yet_triggers_pick_recommendations():
    # Previously this returned [] outright; now that recommend_draft()
    # supports pre-lock pick recommendations, "no champion locked" means
    # "dispatch to the pick-recommendation path," not "nothing to say."
    # candidate_names=[] keeps this specific test deterministic and
    # isolated from the real knowledge/champions/*_profile.md files on
    # disk -- with no candidates, the honest result is one "unavailable"
    # pick_recommendation entry, not a fabricated pick.
    snapshot = _snapshot(current_champion_id=None)
    result = recommend_draft(snapshot, FAKE_CATALOG, profile_loader_fn=_fake_profile_loader, candidate_names=[])

    assert len(result) == 1
    assert result[0]["category"] == "pick_recommendation"
    assert result[0]["confidence"] == "unavailable"
    assert validate_recommendation(result[0]) == []


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


# ============================================================================
# Pick-recommendation tests (current_player.champion_id is None) -- extends
# recommend_draft() to cover champion SELECTION, not just informational
# callouts about an already-locked champion. Every test above this line is
# untouched and must keep passing exactly as before.
# ============================================================================


def _make_catalog_and_profiles(champions: dict) -> tuple:
    """champions: {name: {"id": int, "roles": [...], "damage_type": ...,
    "synergy_champions": [...] (optional), "strengths": [...] (optional)}}

    Returns (catalog, profiles_by_name), with every champion_schema-required
    field filled in with an honest empty default for whatever a given test
    doesn't care about. profiles_by_name.get is itself a valid
    profile_loader_fn (name -> profile | None).
    """
    catalog = {"champions_by_id": {}, "champions_by_name": {}}
    profiles = {}
    for name, spec in champions.items():
        champion_id = spec["id"]
        catalog["champions_by_id"][champion_id] = {"id": champion_id, "name": name}
        catalog["champions_by_name"][name.lower()] = {"id": champion_id, "name": name}
        profiles[name] = {
            "champion": name,
            "roles": spec.get("roles", []),
            "damage_type": spec.get("damage_type", "unknown"),
            "scaling_profile": "unknown",
            "strengths": spec.get("strengths", []),
            "weaknesses": [],
            "preferred_playstyle": spec.get("preferred_playstyle"),
            "common_counters": [],
            "favorable_matchups": [],
            "synergy_champions": spec.get("synergy_champions", []),
        }
    return catalog, profiles


def _pick_snapshot(assigned_position="middle", ally_picks=None, enemy_picks=None, ally_bans=None, enemy_bans=None):
    return {
        "ally_team": [],
        "enemy_team": [],
        "ally_picks": ally_picks or [],
        "enemy_picks": enemy_picks or [],
        "ally_bans": ally_bans or [],
        "enemy_bans": enemy_bans or [],
        "current_player": {"cell_id": 2, "champion_id": None, "assigned_position": assigned_position},
        "phase": {"name": "BAN_PICK", "time_left_ms": 30000, "is_infinite": False},
    }


def test_filters_candidates_by_middle_role():
    catalog, profiles = _make_catalog_and_profiles({
        "Annie": {"id": 1, "roles": ["middle"], "damage_type": "magic"},
        "Garen": {"id": 2, "roles": ["top"], "damage_type": "physical"},
    })
    snapshot = _pick_snapshot(assigned_position="middle")

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Annie", "Garen"])

    assert [e["subject"] for e in result] == ["Annie"]
    assert result[0]["category"] == "pick_recommendation"
    assert result[0]["recommendation"] == "Annie"
    assert result[0]["system"] == "draft"


def test_filters_candidates_by_support_utility_role():
    catalog, profiles = _make_catalog_and_profiles({
        "Soraka": {"id": 1, "roles": ["utility"], "damage_type": "magic"},
        "Annie": {"id": 2, "roles": ["middle"], "damage_type": "magic"},
    })
    snapshot = _pick_snapshot(assigned_position="utility")

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Soraka", "Annie"])

    assert [e["subject"] for e in result] == ["Soraka"]


def test_excludes_champions_already_picked_by_either_team():
    catalog, profiles = _make_catalog_and_profiles({
        "Annie": {"id": 1, "roles": ["middle"], "damage_type": "magic"},
        "Ahri": {"id": 2, "roles": ["middle"], "damage_type": "magic"},
    })
    snapshot = _pick_snapshot(assigned_position="middle", ally_picks=[], enemy_picks=[1])

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Annie", "Ahri"])

    assert [e["subject"] for e in result] == ["Ahri"]


def test_excludes_champions_banned_by_ally_team():
    catalog, profiles = _make_catalog_and_profiles({
        "Annie": {"id": 1, "roles": ["middle"], "damage_type": "magic"},
        "Ahri": {"id": 2, "roles": ["middle"], "damage_type": "magic"},
    })
    snapshot = _pick_snapshot(assigned_position="middle", ally_bans=[1])

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Annie", "Ahri"])

    assert [e["subject"] for e in result] == ["Ahri"]


def test_excludes_champions_banned_by_enemy_team():
    catalog, profiles = _make_catalog_and_profiles({
        "Annie": {"id": 1, "roles": ["middle"], "damage_type": "magic"},
        "Ahri": {"id": 2, "roles": ["middle"], "damage_type": "magic"},
    })
    snapshot = _pick_snapshot(assigned_position="middle", enemy_bans=[2])

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Annie", "Ahri"])

    assert [e["subject"] for e in result] == ["Annie"]


def test_physical_heavy_allies_favor_a_magic_candidate():
    catalog, profiles = _make_catalog_and_profiles({
        "Garen": {"id": 1, "roles": ["top"], "damage_type": "physical"},
        "Darius": {"id": 2, "roles": ["top"], "damage_type": "physical"},
        "Annie": {"id": 3, "roles": ["middle"], "damage_type": "magic"},
        "Yasuo": {"id": 4, "roles": ["middle"], "damage_type": "physical"},
    })
    snapshot = _pick_snapshot(assigned_position="middle", ally_picks=[1, 2])

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Annie", "Yasuo"])

    assert [e["subject"] for e in result] == ["Annie", "Yasuo"]
    assert result[0]["details"]["score_breakdown"]["damage_balance"] == DAMAGE_BALANCE_BONUS
    assert result[1]["details"]["score_breakdown"]["damage_balance"] == 0
    assert "damage_balance" in {ev["fact"] for ev in result[0]["evidence"]}


def test_magic_heavy_allies_favor_physical_or_hybrid_candidate():
    catalog, profiles = _make_catalog_and_profiles({
        "Annie": {"id": 1, "roles": ["middle"], "damage_type": "magic"},
        "Ahri": {"id": 2, "roles": ["middle"], "damage_type": "magic"},
        "Yasuo": {"id": 3, "roles": ["top"], "damage_type": "physical"},
        "Nautilus": {"id": 4, "roles": ["top"], "damage_type": "hybrid"},
        "Viktor": {"id": 5, "roles": ["top"], "damage_type": "magic"},
    })
    snapshot = _pick_snapshot(assigned_position="top", ally_picks=[1, 2])

    result = recommend_draft(
        snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Yasuo", "Nautilus", "Viktor"]
    )

    scores = {e["subject"]: e["details"]["score_breakdown"]["damage_balance"] for e in result}
    assert scores["Yasuo"] == DAMAGE_BALANCE_BONUS
    assert scores["Nautilus"] == DAMAGE_BALANCE_BONUS
    assert scores["Viktor"] == 0


def test_balanced_composition_gives_no_damage_bonus():
    catalog, profiles = _make_catalog_and_profiles({
        "Garen": {"id": 1, "roles": ["top"], "damage_type": "physical"},
        "Annie": {"id": 2, "roles": ["middle"], "damage_type": "magic"},
        "Yasuo": {"id": 3, "roles": ["jungle"], "damage_type": "physical"},
        "Viktor": {"id": 4, "roles": ["jungle"], "damage_type": "magic"},
    })
    # one physical + one magic locked -- balanced, no clear lean
    snapshot = _pick_snapshot(assigned_position="jungle", ally_picks=[1, 2])

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Yasuo", "Viktor"])

    assert all(e["details"]["score_breakdown"]["damage_balance"] == 0 for e in result)


def test_insufficient_locked_allies_gives_no_damage_bonus():
    catalog, profiles = _make_catalog_and_profiles({
        "Garen": {"id": 1, "roles": ["top"], "damage_type": "physical"},  # only 1 locked ally
        "Annie": {"id": 2, "roles": ["middle"], "damage_type": "magic"},
    })
    snapshot = _pick_snapshot(assigned_position="middle", ally_picks=[1])

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Annie"])

    assert result[0]["details"]["score_breakdown"]["damage_balance"] == 0


def test_direct_authored_synergy_affects_ranking():
    catalog, profiles = _make_catalog_and_profiles({
        "Leona": {"id": 1, "roles": ["utility"], "damage_type": "physical"},
        "Yasuo": {"id": 2, "roles": ["middle"], "damage_type": "physical", "synergy_champions": ["Leona"]},
        "Annie": {"id": 3, "roles": ["middle"], "damage_type": "physical"},
    })
    snapshot = _pick_snapshot(assigned_position="middle", ally_picks=[1])

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Yasuo", "Annie"])

    assert [e["subject"] for e in result] == ["Yasuo", "Annie"]
    assert result[0]["details"]["score_breakdown"]["direct_synergy"] == DIRECT_SYNERGY_BONUS
    assert result[1]["details"]["score_breakdown"]["direct_synergy"] == 0
    assert {"fact": "direct_synergy", "synergizes_with": ["Leona"]} in result[0]["evidence"]


def test_combined_bonuses_sum_correctly_and_reach_high_severity():
    catalog, profiles = _make_catalog_and_profiles({
        "Garen": {"id": 1, "roles": ["top"], "damage_type": "physical"},
        "Darius": {"id": 2, "roles": ["top"], "damage_type": "physical"},
        "Leona": {"id": 3, "roles": ["utility"], "damage_type": "physical"},
        "Annie": {"id": 4, "roles": ["middle"], "damage_type": "magic", "synergy_champions": ["Leona"]},
    })
    snapshot = _pick_snapshot(assigned_position="middle", ally_picks=[1, 2, 3])

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Annie"])

    breakdown = result[0]["details"]["score_breakdown"]
    assert breakdown["role_fit"] == "required"
    assert breakdown["damage_balance"] == DAMAGE_BALANCE_BONUS
    assert breakdown["direct_synergy"] == DIRECT_SYNERGY_BONUS
    assert breakdown["total"] == DAMAGE_BALANCE_BONUS + DIRECT_SYNERGY_BONUS
    assert result[0]["severity"] == "high"


def test_deterministic_alphabetical_tie_break_when_scores_equal():
    catalog, profiles = _make_catalog_and_profiles({
        "Zed": {"id": 1, "roles": ["middle"], "damage_type": "physical"},
        "Annie": {"id": 2, "roles": ["middle"], "damage_type": "magic"},
        "Morgana": {"id": 3, "roles": ["middle"], "damage_type": "magic"},
    })
    snapshot = _pick_snapshot(assigned_position="middle")  # no allies locked -- everyone scores 0

    result = recommend_draft(
        snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Zed", "Annie", "Morgana"]
    )

    assert [e["subject"] for e in result] == ["Annie", "Morgana", "Zed"]
    assert [e["priority"] for e in result] == [1, 2, 3]


def test_limits_default_result_to_top_three_candidates():
    champions = {f"Mid{i}": {"id": i, "roles": ["middle"], "damage_type": "magic"} for i in range(1, 6)}
    catalog, profiles = _make_catalog_and_profiles(champions)
    snapshot = _pick_snapshot(assigned_position="middle")

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=list(champions.keys()))

    assert len(result) == 3
    assert [e["subject"] for e in result] == ["Mid1", "Mid2", "Mid3"]


def test_unknown_assigned_role_returns_unavailable_recommendation():
    catalog, profiles = _make_catalog_and_profiles({"Annie": {"id": 1, "roles": ["middle"], "damage_type": "magic"}})
    snapshot = _pick_snapshot(assigned_position=None)

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Annie"])

    assert len(result) == 1
    entry = result[0]
    assert entry["category"] == "pick_recommendation"
    assert entry["confidence"] == "unavailable"
    assert entry["severity"] == "unavailable"
    assert entry["recommendation"] is None
    assert validate_recommendation(entry) == []


def test_no_eligible_profiles_returns_unavailable_recommendation():
    catalog, profiles = _make_catalog_and_profiles({"Garen": {"id": 1, "roles": ["top"], "damage_type": "physical"}})
    snapshot = _pick_snapshot(assigned_position="middle")  # Garen doesn't fit middle

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Garen"])

    assert len(result) == 1
    assert result[0]["category"] == "pick_recommendation"
    assert result[0]["confidence"] == "unavailable"
    assert result[0]["severity"] == "unavailable"
    assert validate_recommendation(result[0]) == []


def test_unresolved_ally_ids_and_missing_profiles_are_recorded():
    catalog, profiles = _make_catalog_and_profiles({"Annie": {"id": 1, "roles": ["middle"], "damage_type": "magic"}})
    # a locked ally id the catalog can resolve to a name, but with no
    # authored profile for that name (a real, common gap per CHECKPOINT.md)
    catalog["champions_by_id"][2] = {"id": 2, "name": "GhostChampion"}
    catalog["champions_by_name"]["ghostchampion"] = {"id": 2, "name": "GhostChampion"}
    # id 999 has no catalog entry at all -- unresolvable

    snapshot = _pick_snapshot(assigned_position="middle", ally_picks=[2, 999])

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Annie"])

    assert result[0]["details"]["unresolved_ally_ids"] == [999]
    assert result[0]["details"]["missing_ally_profiles"] == ["GhostChampion"]


def test_pick_recommendation_details_include_strengths_and_playstyle_without_scoring_them():
    catalog, profiles = _make_catalog_and_profiles({
        "Annie": {
            "id": 1, "roles": ["middle"], "damage_type": "magic",
            "strengths": ["Strong early burst", "Reliable stun", "Good wave clear"],
            "preferred_playstyle": "Bully the lane early with burst combos.",
        },
        "Ahri": {
            "id": 2, "roles": ["middle"], "damage_type": "magic",
            "strengths": ["Only one strength listed"],
        },
    })
    snapshot = _pick_snapshot(assigned_position="middle")

    result = recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Annie", "Ahri"])

    annie = next(e for e in result if e["subject"] == "Annie")
    ahri = next(e for e in result if e["subject"] == "Ahri")
    assert annie["details"]["strengths"] == ["Strong early burst", "Reliable stun", "Good wave clear"]
    assert annie["details"]["preferred_playstyle"] == "Bully the lane early with burst combos."
    # a longer strengths list must not itself earn extra score
    assert annie["details"]["score_breakdown"]["total"] == ahri["details"]["score_breakdown"]["total"] == 0


def test_never_mutates_snapshot_catalog_or_profiles():
    catalog, profiles = _make_catalog_and_profiles({
        "Garen": {"id": 1, "roles": ["top"], "damage_type": "physical"},
        "Annie": {"id": 2, "roles": ["middle"], "damage_type": "magic"},
    })
    snapshot = _pick_snapshot(assigned_position="middle", ally_picks=[1])
    snapshot_copy = copy.deepcopy(snapshot)
    catalog_copy = copy.deepcopy(catalog)
    profiles_copy = copy.deepcopy(profiles)

    recommend_draft(snapshot, catalog, profile_loader_fn=profiles.get, candidate_names=["Annie"])

    assert snapshot == snapshot_copy
    assert catalog == catalog_copy
    assert profiles == profiles_copy


def test_default_candidate_discovery_uses_real_profile_files_on_disk():
    # No candidate_names, no profile_loader_fn override -- exercises the
    # real list_available_champion_profiles() default discovery against
    # the real knowledge/champions/*_profile.md files authored in an
    # earlier checkpoint.
    empty_catalog = {"champions_by_id": {}, "champions_by_name": {}}
    snapshot = _pick_snapshot(assigned_position="middle")

    result = recommend_draft(snapshot, empty_catalog)

    real_subjects = {e["subject"] for e in result if e["confidence"] != "unavailable"}
    assert real_subjects.issubset({"Yone", "Akali", "Fizz", "Syndra"})
    assert "Pyke" not in real_subjects  # Pyke's role is utility, not middle
    assert len(result) <= 3


if __name__ == "__main__":
    test_flags_enemy_counter_pick()
    test_flags_favorable_matchup()
    test_flags_ally_synergy()
    test_unrelated_pick_produces_no_entry()
    test_multiple_signals_sorted_by_severity_and_prioritized()
    test_no_snapshot_returns_empty_list()
    test_no_current_player_champion_picked_yet_triggers_pick_recommendations()
    test_unresolvable_current_player_champion_id_returns_empty_list_never_guesses()
    test_missing_profile_for_current_player_champion_returns_empty_list()
    test_unresolvable_enemy_or_ally_ids_are_skipped_not_fabricated()
    test_player_role_included_in_details_when_available()
    test_default_profile_loader_is_the_real_champion_loader()
    test_integration_with_real_yone_profile_file_on_disk()
    test_filters_candidates_by_middle_role()
    test_filters_candidates_by_support_utility_role()
    test_excludes_champions_already_picked_by_either_team()
    test_excludes_champions_banned_by_ally_team()
    test_excludes_champions_banned_by_enemy_team()
    test_physical_heavy_allies_favor_a_magic_candidate()
    test_magic_heavy_allies_favor_physical_or_hybrid_candidate()
    test_balanced_composition_gives_no_damage_bonus()
    test_insufficient_locked_allies_gives_no_damage_bonus()
    test_direct_authored_synergy_affects_ranking()
    test_combined_bonuses_sum_correctly_and_reach_high_severity()
    test_deterministic_alphabetical_tie_break_when_scores_equal()
    test_limits_default_result_to_top_three_candidates()
    test_unknown_assigned_role_returns_unavailable_recommendation()
    test_no_eligible_profiles_returns_unavailable_recommendation()
    test_unresolved_ally_ids_and_missing_profiles_are_recorded()
    test_pick_recommendation_details_include_strengths_and_playstyle_without_scoring_them()
    test_never_mutates_snapshot_catalog_or_profiles()
    test_default_candidate_discovery_uses_real_profile_files_on_disk()
    print("All checks passed.")
