"""Self-check for src/analysis/item_recommender.py.

Everything is fixture-driven (snapshot, knowledge, catalog, damage-type
table) -- no dependency on real match data, real knowledge files, or the
network. Run with: python -m tests.test_item_recommender
"""

from src.analysis.item_recommender import generate_item_recommendations, recommend_items

DAMAGE_TYPES = {
    "Syndra": {"damage_type": "magic"},
    "Lissandra": {"damage_type": "magic"},
    "Warwick": {"damage_type": "physical", "sustain": True},
}

CHAMPION_KNOWLEDGE = {
    "core_build": ["Kraken Slayer", "Berserker's Greaves"],
    "items": {
        "Wit's End": {
            "valuable_when": "enemy has 2+ champions dealing primarily magic damage",
            "bad_when": "enemy team is almost entirely physical damage",
        },
        "Death's Dance": {
            "valuable_when": "enemy has 2+ champions dealing primarily physical damage",
            "bad_when": "enemy damage is mostly burst/magic",
        },
        "Zhonya's Hourglass": {
            "valuable_when": "behind, or facing a fed enemy carry that threatens burst kills",
            "bad_when": "ahead with no real burst threat on the enemy team",
        },
        "Nonexistent Trinket": {
            "valuable_when": "enemy has healing or sustain in their kit",
            "bad_when": "",
        },
    },
    "avoid": {"Guardian Angel": {"bad_when": "always for this champion"}},
}
GENERAL_KNOWLEDGE = {"core_build": [], "items": {}, "avoid": {}}


def _catalog(entries: dict) -> dict:
    """entries: {item_id: (name, cost, from_ids)}"""
    by_id, by_name = {}, {}
    for item_id, (name, cost, from_ids) in entries.items():
        entry = {"id": item_id, "name": name, "cost": cost, "tags": [], "from": from_ids}
        by_id[item_id] = entry
        by_name[name.lower()] = entry
    return {"version": "test", "items_by_id": by_id, "items_by_name": by_name}


CATALOG = _catalog({
    "1": ("Wit's End", 2600, ["10", "11"]),
    "10": ("Recurve Bow", 1000, []),
    "11": ("Negatron Cloak", 900, []),
    "2": ("Death's Dance", 3200, []),
    "3": ("Zhonya's Hourglass", 2600, []),
    "4": ("Kraken Slayer", 3400, []),
    "5": ("Berserker's Greaves", 1100, []),
})


def _snapshot(current_gold=None, current_items=None):
    return {
        "champion": "Yone",
        "game_time_seconds": 900,
        "player": {"current_items": current_items or [], "current_gold": current_gold},
        "enemy_team": [
            {"champion": "Syndra", "is_fed": True},
            {"champion": "Lissandra", "is_fed": False},
            {"champion": "Warwick", "is_fed": False},
        ],
        "team_state": {"gold_diff": -3000, "kill_diff": -5},
        "game_state": "behind",
    }


def _find(result, item_or_builds_toward):
    for r in result["recommendations"]:
        if r["item"] == item_or_builds_toward or r.get("builds_toward") == item_or_builds_toward:
            return r
    return None


def test_trigger_matching_and_confidence_scoring():
    result = recommend_items(_snapshot(current_items=[4]), CHAMPION_KNOWLEDGE, GENERAL_KNOWLEDGE, CATALOG, DAMAGE_TYPES)

    wits_end = _find(result, "Wit's End")
    assert wits_end["triggered_rules"] == ["enemy_ap_heavy"]
    assert wits_end["confidence_score"] == 55  # 40 base + 15 champion-specific
    assert wits_end["confidence_tier"] == "medium"
    assert wits_end["conflicting_signal"] is False

    # Death's Dance requires enemy_ad_heavy (needs 2+ physical champs); only
    # Warwick is physical here, so the trigger never fires -- not a candidate.
    assert _find(result, "Death's Dance") is None


def test_stacked_triggers_and_self_conflict_are_both_scored():
    result = recommend_items(_snapshot(current_items=[4]), CHAMPION_KNOWLEDGE, GENERAL_KNOWLEDGE, CATALOG, DAMAGE_TYPES)

    zhonyas = _find(result, "Zhonya's Hourglass")
    # matches both enemy_has_fed_carry ("burst kills") and game_state_behind ("behind")
    assert sorted(zhonyas["triggered_rules"]) == ["enemy_has_fed_carry", "game_state_behind"]
    # its own "bad when" text also contains "burst threat", which overlaps the
    # active enemy_has_fed_carry trigger's keywords -- a genuine ambiguous
    # phrasing the engine must not silently ignore.
    assert zhonyas["conflicting_signal"] is True
    # 40 base + 20 additional trigger + 15 champion-specific - 30 conflict = 45
    assert zhonyas["confidence_score"] == 45


def test_owned_core_build_item_excluded_unowned_core_build_included():
    result = recommend_items(_snapshot(current_items=[4]), CHAMPION_KNOWLEDGE, GENERAL_KNOWLEDGE, CATALOG, DAMAGE_TYPES)

    assert _find(result, "Kraken Slayer") is None  # already owned (id 4)
    greaves = _find(result, "Berserker's Greaves")
    assert greaves is not None
    assert greaves["triggered_rules"] == ["core_build"]
    assert greaves["confidence_score"] == 40


def test_avoid_item_never_recommended():
    knowledge_with_matching_avoid = {
        **CHAMPION_KNOWLEDGE,
        "items": {
            **CHAMPION_KNOWLEDGE["items"],
            "Guardian Angel": {"valuable_when": "behind", "bad_when": ""},
        },
    }
    result = recommend_items(_snapshot(current_items=[4]), knowledge_with_matching_avoid, GENERAL_KNOWLEDGE, CATALOG, DAMAGE_TYPES)
    assert _find(result, "Guardian Angel") is None


def test_unrecognized_item_is_flagged_not_recommended():
    result = recommend_items(_snapshot(current_items=[4]), CHAMPION_KNOWLEDGE, GENERAL_KNOWLEDGE, CATALOG, DAMAGE_TYPES)

    assert "Nonexistent Trinket" in result["unrecognized_items_flagged"]
    assert _find(result, "Nonexistent Trinket") is None


def test_ranking_and_recommendation_type_assignment():
    result = recommend_items(_snapshot(current_items=[4]), CHAMPION_KNOWLEDGE, GENERAL_KNOWLEDGE, CATALOG, DAMAGE_TYPES)
    recs = result["recommendations"]

    scores = [r["confidence_score"] for r in recs]
    assert scores == sorted(scores, reverse=True)  # descending confidence
    assert recs[0]["priority"] == 1
    assert recs[0]["recommendation_type"] == "complete_item"
    assert all(r["recommendation_type"] == "alternative" for r in recs[1:])


def test_general_knowledge_fallback_for_uncovered_champion():
    # regression test: TEST_AUDIT.md flagged this as the single most
    # important gap in this module -- every prior test used an empty
    # GENERAL_KNOWLEDGE fixture, so the fallback path that fires for every
    # champion outside the current knowledge/items/*.md pool was completely
    # unverified.
    empty_champion_knowledge = {"core_build": [], "items": {}, "avoid": {}}
    general_knowledge = {
        "core_build": [],
        "items": {
            "Wit's End": {
                "valuable_when": "enemy has 2+ champions dealing primarily magic damage",
                "bad_when": "",
            },
        },
        "avoid": {},
    }

    result = recommend_items(_snapshot(current_items=[]), empty_champion_knowledge, general_knowledge, CATALOG, DAMAGE_TYPES)

    wits_end = _find(result, "Wit's End")
    assert wits_end is not None
    assert wits_end["source"] == "general_knowledge"
    assert wits_end["confidence_score"] == 45  # 40 base + 5 general-knowledge (not 15 -- not champion-specific)


def test_component_fallback_when_full_item_unaffordable():
    result = recommend_items(_snapshot(current_gold=950, current_items=[4]), CHAMPION_KNOWLEDGE, GENERAL_KNOWLEDGE, CATALOG, DAMAGE_TYPES)

    wits_end_progress = _find(result, "Wit's End")  # matched by builds_toward
    assert wits_end_progress["recommendation_type"] == "component"
    assert wits_end_progress["item"] == "Negatron Cloak"  # cheaper of the two components, only one affordable
    assert wits_end_progress["cost"] == 900
    assert wits_end_progress["purchasable_now"] is True

    # Berserker's Greaves (1100) has no build-path components and costs more
    # than available gold -- not purchasable, no component to fall back to.
    greaves = _find(result, "Berserker's Greaves")
    assert greaves["purchasable_now"] is False


def test_save_gold_when_nothing_is_affordable():
    result = recommend_items(_snapshot(current_gold=100, current_items=[4]), CHAMPION_KNOWLEDGE, GENERAL_KNOWLEDGE, CATALOG, DAMAGE_TYPES)

    save_gold_entries = [r for r in result["recommendations"] if r["recommendation_type"] == "save_gold"]
    assert len(save_gold_entries) == 1
    assert save_gold_entries[0]["item"] is None
    assert all(r["purchasable_now"] is not True for r in result["recommendations"])


def test_generate_item_recommendations_wires_real_pipeline_together():
    # generate_item_recommendations()'s whole job is composing
    # build_snapshot_from_match() + load_champion_items()/load_general_items()
    # + recommend_items() -- proving that wiring needs a real match dict and
    # the real knowledge/items/syndra.md file, not synthetic fixtures for
    # every dependency (recommend_items() itself is already covered above).
    match = {
        "metadata": {"matchId": "NA1_WIRING_TEST"},
        "info": {
            "gameDuration": 1500,
            "participants": [
                {"riotIdGameName": "HelloKittler", "riotIdTagline": "meow", "championName": "Syndra",
                 "teamPosition": "MIDDLE", "teamId": 100, "participantId": 1, "champLevel": 11,
                 "kills": 4, "deaths": 5, "assists": 3, "goldEarned": 8000,
                 "item0": 0, "item1": 0, "item2": 0, "item3": 0, "item4": 0, "item5": 0, "item6": 0},
                {"riotIdGameName": "Enemy", "riotIdTagline": "0000", "championName": "Zed",
                 "teamPosition": "MIDDLE", "teamId": 200, "participantId": 2, "champLevel": 12,
                 "kills": 8, "deaths": 1, "assists": 2, "goldEarned": 11000,
                 "item0": 0, "item1": 0, "item2": 0, "item3": 0, "item4": 0, "item5": 0, "item6": 0},
            ],
            "teams": [
                {"teamId": 100, "objectives": {"dragon": {"kills": 0}, "baron": {"kills": 0}, "tower": {"kills": 2}}},
                {"teamId": 200, "objectives": {"dragon": {"kills": 2}, "baron": {"kills": 0}, "tower": {"kills": 5}}},
            ],
        },
    }
    catalog = _catalog({
        "1": ("Liandry's Torment", 3000, []),
        "2": ("Sorcerer's Shoes", 1100, []),
    })

    result = generate_item_recommendations(match, "HelloKittler", "meow", catalog, {"Zed": {"damage_type": "physical"}})

    assert result["champion"] == "Syndra"
    item_names = {r["item"] for r in result["recommendations"]}
    assert "Liandry's Torment" in item_names  # Syndra's real core_build, from the real knowledge file


if __name__ == "__main__":
    test_trigger_matching_and_confidence_scoring()
    test_stacked_triggers_and_self_conflict_are_both_scored()
    test_owned_core_build_item_excluded_unowned_core_build_included()
    test_avoid_item_never_recommended()
    test_unrecognized_item_is_flagged_not_recommended()
    test_general_knowledge_fallback_for_uncovered_champion()
    test_ranking_and_recommendation_type_assignment()
    test_component_fallback_when_full_item_unaffordable()
    test_save_gold_when_nothing_is_affordable()
    test_generate_item_recommendations_wires_real_pipeline_together()
    print("All checks passed.")
