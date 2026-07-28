"""Self-check for src/draft/capture.py -- the sanitized champ-select
capture tool (Stage 5 of this session's staged implementation plan).
Written before capture.py's implementation. Every test uses fake session
payloads only -- no real LCU client, no real League installation.
Run with: python -m tests.test_draft_capture
"""

import copy
import json
import tempfile
from pathlib import Path

from src.draft.capture import (
    CAPTURE_FILE_WARNING,
    REDACTED_PLACEHOLDER,
    capture_champ_select,
    sanitize,
)

# Shaped like a real LCU champ-select session, deliberately including
# player-identifying fields (summonerId, puuid) and a chat password --
# exactly the kind of real-looking payload this tool exists to sanitize.
FAKE_RAW_SESSION = {
    "localPlayerCellId": 2,
    "myTeam": [
        {"cellId": 2, "championId": 157, "assignedPosition": "middle", "summonerId": 123456, "puuid": "real-puuid-abc"},
    ],
    "theirTeam": [
        {"cellId": 5, "championId": 64, "assignedPosition": "", "summonerId": 0, "puuid": ""},
    ],
    "chatDetails": {"chatRoomName": "champ-select-lobby-1", "chatRoomPassword": "supersecret"},
    "bans": {"myTeamBans": [78], "theirTeamBans": [238], "numBans": 2},
    "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 27500, "isInfinite": False},
    "actions": [[{"actorCellId": 5, "championId": 238, "type": "ban", "completed": True}]],
}

FAKE_SNAPSHOT = {
    "ally_team": [{"cell_id": 2, "champion_id": 157, "assigned_position": "middle"}],
    "enemy_team": [{"cell_id": 5, "champion_id": 64, "assigned_position": None}],
    "ally_picks": [157], "enemy_picks": [64],
    "ally_bans": [78], "enemy_bans": [238],
    "current_player": {"cell_id": 2, "champion_id": 157, "assigned_position": "middle"},
    "phase": {"name": "BAN_PICK", "time_left_ms": 27500, "is_infinite": False},
}


def test_sanitize_redacts_known_sensitive_keys():
    result = sanitize(FAKE_RAW_SESSION)

    assert result["myTeam"][0]["summonerId"] == REDACTED_PLACEHOLDER
    assert result["myTeam"][0]["puuid"] == REDACTED_PLACEHOLDER
    assert result["chatDetails"]["chatRoomPassword"] == REDACTED_PLACEHOLDER


def test_sanitize_redacts_nested_structures_at_any_depth():
    nested = {"a": {"b": {"c": [{"puuid": "deep-secret"}]}}}

    result = sanitize(nested)

    assert result["a"]["b"]["c"][0]["puuid"] == REDACTED_PLACEHOLDER


def test_sanitize_preserves_non_sensitive_field_names_and_structure():
    result = sanitize(FAKE_RAW_SESSION)

    assert result["localPlayerCellId"] == 2
    assert result["myTeam"][0]["cellId"] == 2
    assert result["myTeam"][0]["championId"] == 157
    assert result["myTeam"][0]["assignedPosition"] == "middle"
    assert result["bans"] == FAKE_RAW_SESSION["bans"]
    assert result["chatDetails"]["chatRoomName"] == "champ-select-lobby-1"  # not itself a sensitive key name


def test_sanitize_never_mutates_the_input():
    original = copy.deepcopy(FAKE_RAW_SESSION)

    sanitize(FAKE_RAW_SESSION)

    assert FAKE_RAW_SESSION == original


def test_sanitize_matches_sensitive_keys_case_insensitively():
    result = sanitize({"PUUID": "x", "SummonerID": "y", "Password": "z"})

    assert result["PUUID"] == REDACTED_PLACEHOLDER
    assert result["SummonerID"] == REDACTED_PLACEHOLDER
    assert result["Password"] == REDACTED_PLACEHOLDER


def test_capture_writes_sanitized_raw_and_normalized_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        paths = capture_champ_select(
            FAKE_RAW_SESSION, FAKE_SNAPSHOT, capture_dir=Path(tmp), clock_fn=lambda: "20260101T000000"
        )

        with open(paths["raw_path"], encoding="utf-8") as f:
            raw_contents = json.load(f)
        with open(paths["snapshot_path"], encoding="utf-8") as f:
            snapshot_contents = json.load(f)

        assert raw_contents["session"]["myTeam"][0]["summonerId"] == REDACTED_PLACEHOLDER
        assert raw_contents["session"]["myTeam"][0]["championId"] == 157
        assert snapshot_contents["snapshot"] == FAKE_SNAPSHOT
        assert raw_contents["_warning"] == CAPTURE_FILE_WARNING
        assert snapshot_contents["_warning"] == CAPTURE_FILE_WARNING


def test_capture_filenames_are_deterministic_given_an_injected_clock():
    with tempfile.TemporaryDirectory() as tmp:
        paths = capture_champ_select(
            FAKE_RAW_SESSION, FAKE_SNAPSHOT, capture_dir=Path(tmp), clock_fn=lambda: "20260101T000000"
        )

        assert paths["raw_path"].name == "20260101T000000_raw_session.json"
        assert paths["snapshot_path"].name == "20260101T000000_snapshot.json"


def test_capture_creates_the_capture_directory_when_missing():
    with tempfile.TemporaryDirectory() as tmp:
        capture_dir = Path(tmp) / "nested" / "captures"

        paths = capture_champ_select(FAKE_RAW_SESSION, FAKE_SNAPSHOT, capture_dir=capture_dir, clock_fn=lambda: "t")

        assert paths["raw_path"].exists()
        assert paths["snapshot_path"].exists()


def test_capture_never_stores_the_lockfile_password_or_player_credentials():
    with tempfile.TemporaryDirectory() as tmp:
        paths = capture_champ_select(FAKE_RAW_SESSION, FAKE_SNAPSHOT, capture_dir=Path(tmp), clock_fn=lambda: "t")

        raw_text = paths["raw_path"].read_text(encoding="utf-8")
        assert "supersecret" not in raw_text
        assert "real-puuid-abc" not in raw_text
        assert "123456" not in raw_text  # the redacted summonerId value


if __name__ == "__main__":
    test_sanitize_redacts_known_sensitive_keys()
    test_sanitize_redacts_nested_structures_at_any_depth()
    test_sanitize_preserves_non_sensitive_field_names_and_structure()
    test_sanitize_never_mutates_the_input()
    test_sanitize_matches_sensitive_keys_case_insensitively()
    test_capture_writes_sanitized_raw_and_normalized_snapshot()
    test_capture_filenames_are_deterministic_given_an_injected_clock()
    test_capture_creates_the_capture_directory_when_missing()
    test_capture_never_stores_the_lockfile_password_or_player_credentials()
    print("All checks passed.")
