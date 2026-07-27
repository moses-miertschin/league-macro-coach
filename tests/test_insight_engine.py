"""Self-check for src/insights/engine.py — reshaping profile_summary.json
into player_insights.json, deterministically, with no invented content.

No file I/O, no API calls. Run with: python -m tests.test_insight_engine
"""

from src.insights.engine import generate_insights


def test_empty_profile():
    result = generate_insights({"games_played": 0})
    assert result["player_summary"] == {
        "games_analyzed": 0,
        "main_champion": "insufficient_data",
        "main_role": "insufficient_data",
    }
    assert result["strengths"] == []
    assert result["weaknesses"] == []
    assert result["priority_improvements"] == []


def test_empty_profile_missing_key_defaults_to_zero():
    # a profile_summary.json that somehow has no games_played key at all
    # should be treated the same as zero games, not crash.
    result = generate_insights({})
    assert result["player_summary"]["games_analyzed"] == 0


def test_insufficient_games():
    # a single recorded game: identity (champion/role) is knowable, but
    # src/history/aggregate.py never surfaces a pattern below 2
    # occurrences, so strength/weakness patterns arrive empty upstream.
    profile_summary = {
        "games_played": 1,
        "most_played_champions": [{"champion": "Pyke", "games": 1, "win_rate": 1.0}],
        "role_distribution": {"UTILITY": {"games": 1, "percentage": 100.0}},
        "strength_patterns": [],
        "weakness_patterns": [],
    }
    result = generate_insights(profile_summary)
    assert result["player_summary"] == {
        "games_analyzed": 1,
        "main_champion": "Pyke",
        "main_role": "UTILITY",
    }
    assert result["strengths"] == []
    assert result["weaknesses"] == []
    assert result["priority_improvements"] == []


def test_repeated_weakness_detection():
    profile_summary = {
        "games_played": 5,
        "most_played_champions": [{"champion": "Syndra", "games": 5, "win_rate": 0.4}],
        "role_distribution": {"MIDDLE": {"games": 5, "percentage": 100.0}},
        "strength_patterns": [],
        "weakness_patterns": [
            {"pattern": "death_count", "category": "deaths", "games_flagged": 4, "rate": 0.8},
        ],
    }
    result = generate_insights(profile_summary)
    assert result["weaknesses"] == [
        {
            "pattern": "death_count",
            "evidence": "Observed in 4 of 5 games",
            "confidence": "medium",  # 4 >= MEDIUM_CONFIDENCE_GAMES(3), < HIGH(5)
        }
    ]


def test_repeated_strength_detection():
    profile_summary = {
        "games_played": 7,
        "most_played_champions": [{"champion": "Syndra", "games": 7, "win_rate": 0.7}],
        "role_distribution": {"MIDDLE": {"games": 7, "percentage": 100.0}},
        "strength_patterns": [
            {"pattern": "kill_participation", "category": "objectives", "games_flagged": 6, "rate": 0.86},
        ],
        "weakness_patterns": [],
    }
    result = generate_insights(profile_summary)
    assert result["strengths"] == [
        {
            "pattern": "kill_participation",
            "evidence": "Observed in 6 of 7 games",
            "confidence": "high",  # 6 >= HIGH_CONFIDENCE_GAMES(5)
        }
    ]


def test_priority_improvement_ordering():
    # deliberately unsorted input — the engine must rank by games_flagged
    # itself rather than trusting the input order.
    profile_summary = {
        "games_played": 10,
        "most_played_champions": [{"champion": "Syndra", "games": 10, "win_rate": 0.5}],
        "role_distribution": {"MIDDLE": {"games": 10, "percentage": 100.0}},
        "strength_patterns": [],
        "weakness_patterns": [
            {"pattern": "gold_per_minute", "category": "farming", "games_flagged": 3, "rate": 0.3},
            {"pattern": "death_count", "category": "deaths", "games_flagged": 6, "rate": 0.6},
            {"pattern": "vision_score_per_minute", "category": "vision", "games_flagged": 4, "rate": 0.4},
        ],
    }
    result = generate_insights(profile_summary)
    issues_in_order = [p["issue"] for p in result["priority_improvements"]]
    assert issues_in_order == ["death_count", "vision_score_per_minute", "gold_per_minute"]


if __name__ == "__main__":
    test_empty_profile()
    test_empty_profile_missing_key_defaults_to_zero()
    test_insufficient_games()
    test_repeated_weakness_detection()
    test_repeated_strength_detection()
    test_priority_improvement_ordering()
    print("All checks passed.")
