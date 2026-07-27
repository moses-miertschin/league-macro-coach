"""Self-check for src/history/aggregate.py — pure arithmetic over game records.

No file I/O, no API calls. Run with: python -m tests.test_history_aggregate
"""

from src.history.aggregate import (
    average_stats_by_champion,
    average_stats_by_role,
    improvement_trends,
    most_played_champions,
    repeated_strengths,
    repeated_weaknesses,
)


def _pattern(pattern, category, concern):
    return {
        "category": category,
        "pattern": pattern,
        "value": 0,
        "confidence": "high",
        "detail": "low" if concern else "good",
        "concern": concern,
        "tier": "low" if concern else "good",
    }


def _game(match_id, ts, champion, role, win, kills, deaths, assists, cs_pm, gold_pm, kp, damage, vision, patterns):
    return {
        "match_id": match_id,
        "game_start_timestamp": ts,
        "champion": champion,
        "role": role,
        "win": win,
        "kda": {"kills": kills, "deaths": deaths, "assists": assists},
        "deaths": deaths,
        "cs_per_minute": cs_pm,
        "gold_per_minute": gold_pm,
        "kill_participation": kp,
        "damage": damage,
        "vision_score": vision,
        "detected_patterns": patterns,
    }


HISTORY = [
    _game(
        "G1", 1000, "Syndra", "MIDDLE", False, 2, 9, 3, 4.0, 250, 0.3, 12000, 10,
        [_pattern("death_count", "deaths", True), _pattern("cs_per_minute", "farming", True)],
    ),
    _game(
        "G2", 2000, "Syndra", "MIDDLE", True, 6, 3, 8, 7.5, 400, 0.6, 20000, 30,
        [_pattern("death_count", "deaths", False), _pattern("cs_per_minute", "farming", False)],
    ),
    _game(
        "G3", 3000, "Pyke", "UTILITY", True, 4, 5, 12, 0.5, 300, 0.7, 8000, 60,
        [_pattern("death_count", "deaths", False), _pattern("vision_score_per_minute", "vision", True)],
    ),
    _game(
        "G4", 4000, "Syndra", "MIDDLE", True, 8, 2, 6, 8.5, 450, 0.7, 22000, 35,
        [_pattern("death_count", "deaths", False), _pattern("cs_per_minute", "farming", True)],
    ),
]


def test_most_played_champions():
    result = most_played_champions(HISTORY)
    assert result[0] == {"champion": "Syndra", "games_played": 3}
    assert {"champion": "Pyke", "games_played": 1} in result


def test_average_stats_by_champion():
    result = average_stats_by_champion(HISTORY)
    syndra = result["Syndra"]
    assert syndra["games_played"] == 3
    assert syndra["win_rate"] == round(2 / 3, 2)
    assert syndra["avg_deaths"] == round((9 + 3 + 2) / 3, 2)


def test_average_stats_by_role():
    result = average_stats_by_role(HISTORY)
    assert result["MIDDLE"]["games_played"] == 3
    assert result["UTILITY"]["games_played"] == 1


def test_repeated_weaknesses_needs_min_occurrences():
    result = repeated_weaknesses(HISTORY, min_occurrences=2)
    patterns = {w["pattern"] for w in result}
    assert "cs_per_minute" in patterns  # flagged in G1 and G4
    assert "vision_score_per_minute" not in patterns  # only flagged once

    cs_weakness = next(w for w in result if w["pattern"] == "cs_per_minute")
    assert cs_weakness["games_flagged"] == 2


def test_repeated_strengths_needs_min_occurrences():
    result = repeated_strengths(HISTORY, min_occurrences=2)
    patterns = {s["pattern"] for s in result}
    assert "death_count" in patterns  # good (not concerning) in G2, G3, G4
    assert "cs_per_minute" not in patterns  # only good once (G2)

    death_strength = next(s for s in result if s["pattern"] == "death_count")
    assert death_strength["games_flagged"] == 3


def test_improvement_trends_needs_two_games():
    assert improvement_trends(HISTORY[:1])["status"] == "insufficient_data"

    trend = improvement_trends(HISTORY)
    assert trend["status"] == "ok"
    assert trend["change"]["avg_deaths"] < 0  # deaths trending down, earlier half vs later half


if __name__ == "__main__":
    test_most_played_champions()
    test_average_stats_by_champion()
    test_average_stats_by_role()
    test_repeated_weaknesses_needs_min_occurrences()
    test_repeated_strengths_needs_min_occurrences()
    test_improvement_trends_needs_two_games()
    print("All checks passed.")
