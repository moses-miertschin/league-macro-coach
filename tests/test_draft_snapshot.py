"""Self-check for src/draft/snapshot.py -- DraftSnapshot, the source-agnostic
draft state built from a raw LCU /lol-champ-select/v1/session dict.

Written before snapshot.py's implementation. The fixture below is shaped
like a real captured LCU champ-select response (myTeam/theirTeam rosters,
bans, timer) -- not fetched from a real client, per this project's "no real
League installation in tests" rule already established in
tests/test_draft_client.py. Run with: python -m tests.test_draft_snapshot
"""

import copy

from src.draft.snapshot import build_draft_snapshot

# Yasuo=157 (local player's pick), Lee Sin=64 (one enemy pick already locked),
# Poppy=78 and Twisted Fate=45 (ally-team bans), Zed=238 (enemy-team ban).
REAL_CHAMP_SELECT_SESSION = {
    "localPlayerCellId": 2,
    "myTeam": [
        {"cellId": 0, "championId": 0, "assignedPosition": "top", "summonerId": 111},
        {"cellId": 1, "championId": 0, "assignedPosition": "jungle", "summonerId": 112},
        {"cellId": 2, "championId": 157, "assignedPosition": "middle", "summonerId": 113},
        {"cellId": 3, "championId": 0, "assignedPosition": "bottom", "summonerId": 114},
        {"cellId": 4, "championId": 0, "assignedPosition": "utility", "summonerId": 115},
    ],
    "theirTeam": [
        {"cellId": 5, "championId": 64, "assignedPosition": "", "summonerId": 0},
        {"cellId": 6, "championId": 0, "assignedPosition": "", "summonerId": 0},
        {"cellId": 7, "championId": 0, "assignedPosition": "", "summonerId": 0},
        {"cellId": 8, "championId": 0, "assignedPosition": "", "summonerId": 0},
        {"cellId": 9, "championId": 0, "assignedPosition": "", "summonerId": 0},
    ],
    "bans": {
        "myTeamBans": [78, 45],
        "theirTeamBans": [238],
        "numBans": 3,
    },
    "timer": {
        "phase": "BAN_PICK",
        "adjustedTimeLeftInPhase": 27500,
        "totalTimeInPhase": 30000,
        "isInfinite": False,
    },
    "actions": [[{"actorCellId": 5, "championId": 238, "type": "ban", "completed": True}]],
}


def test_normal_draft_parsing_extracts_picks_bans_and_phase():
    snapshot = build_draft_snapshot(REAL_CHAMP_SELECT_SESSION)

    assert snapshot["ally_picks"] == [157]
    assert snapshot["enemy_picks"] == [64]
    assert snapshot["ally_bans"] == [78, 45]
    assert snapshot["enemy_bans"] == [238]
    assert snapshot["phase"] == {"name": "BAN_PICK", "time_left_ms": 27500, "is_infinite": False}


def test_ally_and_enemy_rosters_stay_separate():
    snapshot = build_draft_snapshot(REAL_CHAMP_SELECT_SESSION)

    assert len(snapshot["ally_team"]) == 5
    assert len(snapshot["enemy_team"]) == 5
    assert {m["cell_id"] for m in snapshot["ally_team"]} == {0, 1, 2, 3, 4}
    assert {m["cell_id"] for m in snapshot["enemy_team"]} == {5, 6, 7, 8, 9}


def test_unpicked_slots_stay_honestly_none_not_fabricated():
    snapshot = build_draft_snapshot(REAL_CHAMP_SELECT_SESSION)

    unpicked_ally = [m for m in snapshot["ally_team"] if m["cell_id"] != 2]
    assert all(m["champion_id"] is None for m in unpicked_ally)
    unpicked_enemy = [m for m in snapshot["enemy_team"] if m["cell_id"] != 5]
    assert all(m["champion_id"] is None for m in unpicked_enemy)


def test_blank_assigned_position_normalizes_to_none():
    # theirTeam entries carry "" for assignedPosition (privacy/blind pick) --
    # that's functionally "no known position," same as a missing field.
    snapshot = build_draft_snapshot(REAL_CHAMP_SELECT_SESSION)
    enemy = next(m for m in snapshot["enemy_team"] if m["cell_id"] == 5)
    assert enemy["assigned_position"] is None


def test_current_player_identified_by_local_player_cell_id():
    snapshot = build_draft_snapshot(REAL_CHAMP_SELECT_SESSION)

    assert snapshot["current_player"] == {"cell_id": 2, "champion_id": 157, "assigned_position": "middle"}


def test_current_player_before_locking_a_pick_has_no_champion_yet():
    session = copy.deepcopy(REAL_CHAMP_SELECT_SESSION)
    session["myTeam"][2]["championId"] = 0  # local player hasn't picked yet

    snapshot = build_draft_snapshot(session)

    assert snapshot["current_player"]["champion_id"] is None
    assert snapshot["ally_picks"] == []  # honest: nobody on the ally team has picked


def test_current_player_none_when_local_cell_id_matches_nobody():
    session = copy.deepcopy(REAL_CHAMP_SELECT_SESSION)
    session["localPlayerCellId"] = 999  # doesn't match any myTeam entry

    snapshot = build_draft_snapshot(session)

    assert snapshot["current_player"] is None


def test_missing_bans_and_timer_default_to_honest_empty_values():
    session = copy.deepcopy(REAL_CHAMP_SELECT_SESSION)
    del session["bans"]
    del session["timer"]

    snapshot = build_draft_snapshot(session)

    assert snapshot["ally_bans"] == []
    assert snapshot["enemy_bans"] == []
    assert snapshot["phase"] == {"name": None, "time_left_ms": None, "is_infinite": None}


def test_missing_team_rosters_default_to_empty_with_no_current_player():
    snapshot = build_draft_snapshot({"localPlayerCellId": 2})

    assert snapshot["ally_team"] == []
    assert snapshot["enemy_team"] == []
    assert snapshot["ally_picks"] == []
    assert snapshot["enemy_picks"] == []
    assert snapshot["current_player"] is None


def test_no_session_returns_none_not_a_fabricated_empty_snapshot():
    # Mirrors SessionPoller's own idle convention (src/runtime/poller.py) --
    # "no session" is None, never an empty-but-present snapshot.
    assert build_draft_snapshot(None) is None
    assert build_draft_snapshot({}) is None


if __name__ == "__main__":
    test_normal_draft_parsing_extracts_picks_bans_and_phase()
    test_ally_and_enemy_rosters_stay_separate()
    test_unpicked_slots_stay_honestly_none_not_fabricated()
    test_blank_assigned_position_normalizes_to_none()
    test_current_player_identified_by_local_player_cell_id()
    test_current_player_before_locking_a_pick_has_no_champion_yet()
    test_current_player_none_when_local_cell_id_matches_nobody()
    test_missing_bans_and_timer_default_to_honest_empty_values()
    test_missing_team_rosters_default_to_empty_with_no_current_player()
    test_no_session_returns_none_not_a_fabricated_empty_snapshot()
    print("All checks passed.")
