"""Self-check for analyzer.py's pure extraction logic.

No file I/O, no API calls. Run with: python -m tests.test_analyzer
"""

from src.analysis.analyzer import analyze_match

SAMPLE_MATCH = {
    "metadata": {"matchId": "NA1_TEST"},
    "info": {
        "gameDuration": 1800,
        "gameStartTimestamp": 1700000000000,
        "participants": [
            {
                "riotIdGameName": "HelloKittler",
                "riotIdTagline": "meow",
                "championName": "Syndra",
                "teamPosition": "MIDDLE",
                "teamId": 100,
                "participantId": 1,
                "win": True,
                "kills": 6,
                "deaths": 2,
                "assists": 8,
                "totalMinionsKilled": 150,
                "neutralMinionsKilled": 10,
                "goldEarned": 12000,
                "totalDamageDealtToChampions": 20000,
                "damageDealtToObjectives": 3000,
                "visionScore": 25,
                "challenges": {"killParticipation": 0.65},
            },
            {
                "riotIdGameName": "Teammate",
                "riotIdTagline": "0000",
                "championName": "Jinx",
                "teamPosition": "BOTTOM",
                "teamId": 100,
                "participantId": 2,
                "win": True,
                "kills": 4,
                "deaths": 3,
                "assists": 5,
                "totalMinionsKilled": 180,
                "neutralMinionsKilled": 0,
                "goldEarned": 11000,
                "totalDamageDealtToChampions": 10000,
                "damageDealtToObjectives": 1000,
                "visionScore": 15,
                "challenges": {"killParticipation": 0.5},
            },
            {
                "riotIdGameName": "Enemy",
                "riotIdTagline": "1111",
                "championName": "Ahri",
                "teamPosition": "MIDDLE",
                "teamId": 200,
                "participantId": 6,
                "win": False,
                "kills": 3,
                "deaths": 6,
                "assists": 2,
                "totalMinionsKilled": 140,
                "neutralMinionsKilled": 5,
                "goldEarned": 9000,
                "totalDamageDealtToChampions": 99999,
                "damageDealtToObjectives": 500,
                "visionScore": 18,
                "challenges": {"killParticipation": 0.4},
            },
        ],
    },
}


def test_analyze_match():
    result = analyze_match(SAMPLE_MATCH, "HelloKittler", "meow")
    assert result["match_id"] == "NA1_TEST"
    assert result["game_start_timestamp"] == 1700000000000
    assert result["participant_id"] == 1
    assert result["champion"] == "Syndra"
    assert result["role"] == "MIDDLE"
    assert result["win"] is True
    assert result["kda"] == {"kills": 6, "deaths": 2, "assists": 8}
    assert result["cs_per_minute"] == 5.33  # 160 cs / 30 min
    assert result["vision_score"] == 25
    assert result["damage_share"] == 0.667  # 20000 / (20000 + 10000) team damage, enemy excluded


def test_analyze_match_not_found():
    try:
        analyze_match(SAMPLE_MATCH, "Nobody", "0000")
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError for missing participant")


if __name__ == "__main__":
    test_analyze_match()
    test_analyze_match_not_found()
    print("All checks passed.")
