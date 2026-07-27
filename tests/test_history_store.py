"""Self-check for src/history/store.py — combining and persisting game records.

Uses a temp file so it never touches the real data/database/game_history.json.
Run with: python -m tests.test_history_store
"""

import tempfile
from pathlib import Path

from src.history.store import build_game_record, load_history, record_game

ANALYSIS = {
    "match_id": "NA1_TEST",
    "game_start_timestamp": 1700000000000,
    "champion": "Syndra",
    "role": "MIDDLE",
    "win": True,
    "kda": {"kills": 6, "deaths": 2, "assists": 8},
    "cs_per_minute": 7.5,
    "gold_earned": 12000,
    "damage_to_champions": 20000,
    "damage_share": 0.667,
    "objectives_participation": {"kill_participation": 0.65, "damage_to_objectives": 3000},
    "vision_score": 25,
    "game_duration_seconds": 1800,
}

MACRO_RESULT = {
    "match_id": "NA1_TEST",
    "champion_context_loaded": True,
    "role_context_loaded": True,
    "detected_patterns": [
        {
            "category": "farming",
            "pattern": "gold_per_minute",
            "value": 400.0,
            "confidence": "high",
            "detail": "adequate",
            "concern": False,
        },
        {
            "category": "deaths",
            "pattern": "death_count",
            "value": 2,
            "confidence": "high",
            "detail": "2 deaths",
            "concern": False,
        },
    ],
    "possible_improvement_areas": [],
    "confidence_level": "partial",
}


def test_build_game_record_extracts_tracked_fields():
    record = build_game_record(ANALYSIS, MACRO_RESULT)
    assert record["match_id"] == "NA1_TEST"
    assert record["champion"] == "Syndra"
    assert record["role"] == "MIDDLE"
    assert record["win"] is True
    assert record["kda"] == {"kills": 6, "deaths": 2, "assists": 8}
    assert record["deaths"] == 2
    assert record["cs_per_minute"] == 7.5
    assert record["gold_per_minute"] == 400.0  # pulled from macro_result patterns
    assert record["kill_participation"] == 0.65
    assert record["damage"] == 20000
    assert record["damage_share"] == 0.667
    assert record["vision_score"] == 25
    assert record["detected_patterns"] == MACRO_RESULT["detected_patterns"]


def test_record_game_upserts_instead_of_duplicating():
    with tempfile.TemporaryDirectory() as tmp:
        history_path = Path(tmp) / "game_history.json"

        record_game(ANALYSIS, MACRO_RESULT, path=history_path)
        assert len(load_history(history_path)) == 1

        updated_analysis = dict(ANALYSIS)
        updated_analysis["kda"] = {"kills": 10, "deaths": 1, "assists": 9}
        record_game(updated_analysis, MACRO_RESULT, path=history_path)

        history = load_history(history_path)
        assert len(history) == 1
        assert history[0]["kda"]["kills"] == 10


def test_load_history_missing_file_returns_empty_list():
    missing_path = Path(tempfile.gettempdir()) / "definitely_missing_game_history.json"
    assert load_history(missing_path) == []


if __name__ == "__main__":
    test_build_game_record_extracts_tracked_fields()
    test_record_game_upserts_instead_of_duplicating()
    test_load_history_missing_file_returns_empty_list()
    print("All checks passed.")
