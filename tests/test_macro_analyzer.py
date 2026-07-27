"""Self-check for macro_analyzer.py's rule-based logic.

No file I/O, no API calls. Run with: python -m tests.test_macro_analyzer
"""

from src.analysis.macro_analyzer import macro_analyze

WEAK_GAME = {
    "match_id": "NA1_TEST",
    "champion": "Syndra",
    "role": "MIDDLE",
    "win": False,
    "kda": {"kills": 2, "deaths": 9, "assists": 3},
    "cs_per_minute": 4.5,
    "gold_earned": 8000,
    "damage_to_champions": 15000,
    "objectives_participation": {"kill_participation": 0.3, "damage_to_objectives": 500},
    "vision_score": 10,
    "game_duration_seconds": 1800,
}


def test_flags_weak_game():
    result = macro_analyze(WEAK_GAME)
    assert result["match_id"] == "NA1_TEST"
    assert len(result["detected_patterns"]) == 10
    assert result["champion_context_loaded"] is True  # knowledge/champions/syndra.md
    assert result["role_context_loaded"] is True  # knowledge/roles/mid.md

    concerns = {p["pattern"] for p in result["detected_patterns"] if p["concern"] is True}
    # vision_score_per_minute is excluded: both syndra.md and mid.md list
    # vision score under "Metrics That Matter Less", so it's de-prioritized
    # even though the raw number is below the low-vision benchmark.
    assert concerns == {
        "death_count",
        "cs_per_minute",
        "gold_per_minute",
        "kill_participation",
        "damage_to_objectives",
    }
    assert set(result["possible_improvement_areas"]) == concerns

    vision_pattern = next(
        p for p in result["detected_patterns"] if p["pattern"] == "vision_score_per_minute"
    )
    assert vision_pattern["concern"] is False
    assert "deprioritized" in vision_pattern["detail"]

    unavailable = {
        p["pattern"] for p in result["detected_patterns"] if p["confidence"] == "unavailable"
    }
    assert unavailable == {
        "deaths_before_objectives",
        "deaths_after_extended_no_recall",
        "objective_fight_presence",
        "vision_score_vs_enemy_laner",
    }
    assert result["confidence_level"] == "partial"


def test_deprioritized_metric_not_flagged_for_pyke():
    pyke_low_cs_game = dict(WEAK_GAME)
    pyke_low_cs_game["champion"] = "Pyke"
    pyke_low_cs_game["role"] = "UTILITY"
    pyke_low_cs_game["cs_per_minute"] = 0.5  # expected for Pyke, per knowledge/champions/pyke.md

    result = macro_analyze(pyke_low_cs_game)
    assert result["champion_context_loaded"] is True
    assert result["role_context_loaded"] is True

    cs_pattern = next(p for p in result["detected_patterns"] if p["pattern"] == "cs_per_minute")
    assert cs_pattern["concern"] is False
    assert "deprioritized" in cs_pattern["detail"]
    assert "cs_per_minute" not in result["possible_improvement_areas"]


def test_missing_champion_knowledge_does_not_crash():
    unknown_champion_game = dict(WEAK_GAME)
    unknown_champion_game["champion"] = "SomeFutureChampion"

    result = macro_analyze(unknown_champion_game)
    assert result["champion_context_loaded"] is False
    assert result["role_context_loaded"] is True


def test_missing_role_does_not_crash():
    # regression test: TEST_AUDIT.md's first draft mis-flagged this as a
    # crash risk (load_role(None).lower() failing). Re-checking the source
    # showed macro_analyze() already guards this — `if analysis.get("role")`
    # — so this test locks in the existing safe behavior, not a fix.
    no_role_game = dict(WEAK_GAME)
    no_role_game["champion"] = "SomeFutureChampion"
    no_role_game["role"] = None

    result = macro_analyze(no_role_game)
    assert result["champion_context_loaded"] is False
    assert result["role_context_loaded"] is False


def test_timeline_enrichment_fills_previously_unavailable_patterns():
    timeline_result = {
        "death_timestamps_ms": [100000, 200000],
        "deaths_before_objectives": 2,
        "objective_participation": {
            "dragons": {"total": 2, "participated": 0},
            "barons": {"total": 1, "participated": 0},
            "towers": {"total": 1, "participated": 0},
        },
        "recall_patterns": {"status": "unavailable", "detail": "no recall event exists"},
        "fight_participation": {"fights_detected": 3, "fights_participated": 0, "participation_rate": 0.0},
    }

    result = macro_analyze(WEAK_GAME, timeline_result)

    deaths_before = next(
        p for p in result["detected_patterns"] if p["pattern"] == "deaths_before_objectives"
    )
    assert deaths_before["confidence"] == "high"
    assert deaths_before["value"] == 2
    assert deaths_before["concern"] is True  # 2 >= DEATHS_BEFORE_OBJECTIVES_CONCERN

    objective_presence = next(
        p for p in result["detected_patterns"] if p["pattern"] == "objective_fight_presence"
    )
    assert objective_presence["confidence"] == "high"
    assert objective_presence["value"] == 0.0  # 0 participated of 4 total takedowns
    assert objective_presence["concern"] is True  # low participation

    # recall timing stays unavailable even with a timeline — Riot's
    # timeline has no recall event at all, this isn't a missing-data gap
    recall_pattern = next(
        p for p in result["detected_patterns"] if p["pattern"] == "deaths_after_extended_no_recall"
    )
    assert recall_pattern["confidence"] == "unavailable"

    # only 2 of 4 originally-unavailable patterns can ever be filled by a timeline
    unavailable = {p["pattern"] for p in result["detected_patterns"] if p["confidence"] == "unavailable"}
    assert unavailable == {"deaths_after_extended_no_recall", "vision_score_vs_enemy_laner"}


def test_without_timeline_result_still_marks_unavailable():
    # default parameter must reproduce the pre-timeline behavior exactly
    result = macro_analyze(WEAK_GAME)
    deaths_before = next(
        p for p in result["detected_patterns"] if p["pattern"] == "deaths_before_objectives"
    )
    assert deaths_before["confidence"] == "unavailable"
    objective_presence = next(
        p for p in result["detected_patterns"] if p["pattern"] == "objective_fight_presence"
    )
    assert objective_presence["confidence"] == "unavailable"


def test_strong_game_has_no_concerns():
    strong_game = dict(WEAK_GAME)
    strong_game["kda"] = {"kills": 8, "deaths": 2, "assists": 6}
    strong_game["cs_per_minute"] = 9.0
    strong_game["gold_earned"] = 15000
    strong_game["objectives_participation"] = {
        "kill_participation": 0.7,
        "damage_to_objectives": 6000,
    }
    strong_game["vision_score"] = 40

    result = macro_analyze(strong_game)
    assert result["possible_improvement_areas"] == []


if __name__ == "__main__":
    test_flags_weak_game()
    test_strong_game_has_no_concerns()
    test_deprioritized_metric_not_flagged_for_pyke()
    test_missing_champion_knowledge_does_not_crash()
    test_missing_role_does_not_crash()
    test_timeline_enrichment_fills_previously_unavailable_patterns()
    test_without_timeline_result_still_marks_unavailable()
    print("All checks passed.")
