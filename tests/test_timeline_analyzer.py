"""Self-check for src/analysis/timeline_analyzer.py — mocked timeline data,
no network, no API calls. Run with: python -m tests.test_timeline_analyzer
"""

from src.analysis.timeline_analyzer import analyze_timeline

PARTICIPANT_ID = 1

# Frame boundaries don't matter to the analyzer (it flattens all frames'
# events), so this uses a small number of frames for readability.
TIMELINE = {
    "metadata": {"matchId": "NA1_TEST"},
    "info": {
        "frames": [
            {
                "timestamp": 0,
                "events": [
                    # player (1) dies at 100s
                    {"type": "CHAMPION_KILL", "timestamp": 100000, "killerId": 2, "victimId": 1, "assistingParticipantIds": []},
                    # dragon falls 30s later (within the 60s window) — player got the takedown
                    {"type": "ELITE_MONSTER_KILL", "timestamp": 130000, "killerId": 1, "monsterType": "DRAGON", "assistingParticipantIds": [3]},
                ],
            },
            {
                "timestamp": 300000,
                "events": [
                    # baron taken by the enemy team — player not involved
                    {"type": "ELITE_MONSTER_KILL", "timestamp": 500000, "killerId": 4, "monsterType": "BARON_NASHOR", "assistingParticipantIds": [5]},
                    # tower taken by the player
                    {"type": "BUILDING_KILL", "timestamp": 600000, "killerId": 1, "buildingType": "TOWER_BUILDING", "assistingParticipantIds": []},
                ],
            },
            {
                "timestamp": 600000,
                "events": [
                    # isolated solo kill — alone, doesn't form a "fight"
                    {"type": "CHAMPION_KILL", "timestamp": 700000, "killerId": 1, "victimId": 6, "assistingParticipantIds": []},
                    # two kills 15s apart form one fight; player assists the first
                    {"type": "CHAMPION_KILL", "timestamp": 800000, "killerId": 2, "victimId": 7, "assistingParticipantIds": [1]},
                    {"type": "CHAMPION_KILL", "timestamp": 815000, "killerId": 8, "victimId": 9, "assistingParticipantIds": []},
                    # isolated kill far from the others — not a fight, player uninvolved
                    {"type": "CHAMPION_KILL", "timestamp": 900000, "killerId": 10, "victimId": 2, "assistingParticipantIds": []},
                ],
            },
        ],
    },
}

EMPTY_TIMELINE = {"metadata": {"matchId": "NA1_EMPTY"}, "info": {"frames": [{"timestamp": 0, "events": []}]}}


def test_death_timing():
    result = analyze_timeline(TIMELINE, PARTICIPANT_ID)
    assert result["death_timestamps_ms"] == [100000]
    assert result["deaths_before_objectives"] == 1  # dragon fell 30s after the death


def test_objective_participation():
    result = analyze_timeline(TIMELINE, PARTICIPANT_ID)
    assert result["objective_participation"] == {
        "dragons": {"total": 1, "participated": 1},
        "barons": {"total": 1, "participated": 0},
        "towers": {"total": 1, "participated": 1},
    }


def test_recall_patterns_marked_unavailable():
    result = analyze_timeline(TIMELINE, PARTICIPANT_ID)
    assert result["recall_patterns"]["status"] == "unavailable"
    assert "recall" in result["recall_patterns"]["detail"].lower()


def test_fight_participation():
    result = analyze_timeline(TIMELINE, PARTICIPANT_ID)
    # only the 800000/815000 pair qualifies (2 kills within the window);
    # the two isolated kills at 700000 and 900000 don't form fights.
    assert result["fight_participation"] == {
        "fights_detected": 1,
        "fights_participated": 1,
        "participation_rate": 1.0,
    }


def test_empty_timeline_handles_gracefully():
    result = analyze_timeline(EMPTY_TIMELINE, PARTICIPANT_ID)
    assert result["death_timestamps_ms"] == []
    assert result["deaths_before_objectives"] == 0
    assert result["objective_participation"] == {
        "dragons": {"total": 0, "participated": 0},
        "barons": {"total": 0, "participated": 0},
        "towers": {"total": 0, "participated": 0},
    }
    assert result["fight_participation"] == {
        "fights_detected": 0,
        "fights_participated": 0,
        "participation_rate": None,
    }


if __name__ == "__main__":
    test_death_timing()
    test_objective_participation()
    test_recall_patterns_marked_unavailable()
    test_fight_participation()
    test_empty_timeline_handles_gracefully()
    print("All checks passed.")
