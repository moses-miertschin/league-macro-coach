"""Self-check for src/profile/generator.py — shaping game history into the
requested profile_summary.json schema.

No file I/O, no API calls. Run with: python -m tests.test_profile_generator
"""

from src.profile.generator import generate_profile_summary


def _game(match_id, ts, champion, role, win, kills, deaths, assists, cs_pm, gold_pm, damage_share, vision, patterns=None):
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
        "kill_participation": 0.5,
        "damage": 15000,
        "damage_share": damage_share,
        "vision_score": vision,
        "detected_patterns": patterns or [],
    }


def test_empty_history_handling():
    summary = generate_profile_summary([])
    assert summary["games_played"] == 0
    assert summary["most_played_champions"] == []
    assert summary["role_distribution"] == {}
    assert all(v is None for v in summary["overall_average_stats"].values())
    assert summary["champion_profiles"] == []
    assert summary["strength_patterns"] == []
    assert summary["weakness_patterns"] == []
    assert summary["recent_trends"]["status"] == "insufficient_data"


def test_single_game_handling():
    history = [_game("G1", 1000, "Syndra", "MIDDLE", True, 6, 2, 8, 7.5, 400, 0.6, 30)]
    summary = generate_profile_summary(history)

    assert summary["games_played"] == 1
    assert summary["most_played_champions"] == [{"champion": "Syndra", "games": 1, "win_rate": 1.0}]
    assert summary["role_distribution"] == {"MIDDLE": {"games": 1, "percentage": 100.0}}
    assert summary["overall_average_stats"]["kills"] == 6
    assert summary["overall_average_stats"]["damage_share"] == 0.6
    assert len(summary["champion_profiles"]) == 1
    # a single game can't show a trend
    assert summary["recent_trends"]["status"] == "insufficient_data"


def test_multiple_games_aggregation():
    history = [
        _game("G1", 1000, "Syndra", "MIDDLE", False, 2, 9, 3, 4.0, 250, 0.4, 10),
        _game("G2", 2000, "Syndra", "MIDDLE", True, 6, 3, 8, 7.5, 400, 0.6, 30),
        _game("G3", 3000, "Pyke", "UTILITY", True, 4, 5, 12, 0.5, 300, 0.2, 60),
    ]
    summary = generate_profile_summary(history)

    assert summary["games_played"] == 3
    assert summary["overall_average_stats"]["kills"] == round((2 + 6 + 4) / 3, 2)
    assert summary["role_distribution"]["MIDDLE"]["games"] == 2
    assert summary["role_distribution"]["UTILITY"]["games"] == 1
    assert summary["role_distribution"]["MIDDLE"]["percentage"] == round(2 / 3 * 100, 1)

    champions_in_profiles = {p["champion"] for p in summary["champion_profiles"]}
    assert champions_in_profiles == {"Syndra", "Pyke"}
    # sorted by games played, descending
    assert summary["champion_profiles"][0]["champion"] == "Syndra"


def test_champion_frequency_calculation():
    history = [
        _game("G1", 1000, "Syndra", "MIDDLE", True, 6, 2, 8, 7.5, 400, 0.6, 30),
        _game("G2", 2000, "Syndra", "MIDDLE", True, 6, 2, 8, 7.5, 400, 0.6, 30),
        _game("G3", 3000, "Syndra", "MIDDLE", True, 6, 2, 8, 7.5, 400, 0.6, 30),
        _game("G4", 4000, "Pyke", "UTILITY", True, 4, 5, 12, 0.5, 300, 0.2, 60),
    ]
    summary = generate_profile_summary(history)

    assert summary["most_played_champions"][0]["champion"] == "Syndra"
    assert summary["most_played_champions"][0]["games"] == 3
    assert summary["most_played_champions"][1]["champion"] == "Pyke"
    assert summary["most_played_champions"][1]["games"] == 1


def test_win_rate_calculation():
    history = [
        _game("G1", 1000, "Syndra", "MIDDLE", True, 6, 2, 8, 7.5, 400, 0.6, 30),
        _game("G2", 2000, "Syndra", "MIDDLE", True, 6, 2, 8, 7.5, 400, 0.6, 30),
        _game("G3", 3000, "Syndra", "MIDDLE", False, 2, 9, 3, 4.0, 250, 0.4, 10),
    ]
    summary = generate_profile_summary(history)

    syndra_summary = next(c for c in summary["most_played_champions"] if c["champion"] == "Syndra")
    assert syndra_summary["win_rate"] == round(2 / 3, 2)

    syndra_profile = next(p for p in summary["champion_profiles"] if p["champion"] == "Syndra")
    assert syndra_profile["win_rate"] == round(2 / 3, 2)


if __name__ == "__main__":
    test_empty_history_handling()
    test_single_game_handling()
    test_multiple_games_aggregation()
    test_champion_frequency_calculation()
    test_win_rate_calculation()
    print("All checks passed.")
