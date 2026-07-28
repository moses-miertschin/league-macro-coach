"""Self-check for src/ui/demo_fixtures.py -- the deterministic demo
application-state fixtures (Stage 4 of the desktop-app session). Written
before demo_fixtures.py's implementation. No PySide6, no network, no real
League installation -- every fixture is a hand-authored JSON file under
demo/states/. Run with: python -m tests.test_demo_fixtures
"""

import json
import tempfile
from pathlib import Path

from src.draft.service import CHAMP_SELECT_ACTIVE, IDLE_NO_CHAMP_SELECT, LEAGUE_CLIENT_UNAVAILABLE, PROCESSING_ERROR
from src.recommendations.schema import validate_recommendation
from src.runtime.state_publisher import validate_state_shape
from src.ui.demo_fixtures import DEMO_STATES_DIR, list_demo_state_files, load_demo_states


def test_demo_states_dir_exists_and_has_fixtures():
    assert DEMO_STATES_DIR.is_dir()
    files = list_demo_state_files()
    assert len(files) >= 4


def test_list_demo_state_files_is_sorted_for_deterministic_cycling():
    files = list_demo_state_files()
    assert files == sorted(files)


def test_every_fixture_file_is_valid_json_matching_the_state_shape():
    for path in list_demo_state_files():
        state = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_state_shape(state)
        assert errors == [], f"{path.name}: {errors}"


def test_every_recommendation_entry_in_every_fixture_is_a_valid_schema_entry():
    for state in load_demo_states():
        for entry in state["recommendations"]:
            errors = validate_recommendation(entry)
            assert errors == [], f"{entry.get('subject')}: {errors}"


def test_load_demo_states_covers_every_runtime_state():
    states = {s["state"] for s in load_demo_states()}
    assert states == {LEAGUE_CLIENT_UNAVAILABLE, IDLE_NO_CHAMP_SELECT, CHAMP_SELECT_ACTIVE, PROCESSING_ERROR}


def test_load_demo_states_includes_a_prelock_pick_recommendation_example():
    states = load_demo_states()
    categories = {entry["category"] for s in states for entry in s["recommendations"]}
    assert "pick_recommendation" in categories


def test_load_demo_states_includes_a_locked_champion_callout_example():
    states = load_demo_states()
    categories = {entry["category"] for s in states for entry in s["recommendations"]}
    assert {"counter_warning", "favorable_matchup", "ally_synergy"} & categories


def test_load_demo_states_is_deterministic_and_independently_parsed():
    first = load_demo_states()
    second = load_demo_states()

    assert first == second
    assert first[0] is not second[0]


def test_load_demo_states_raises_with_filename_on_a_malformed_fixture():
    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "01_broken.json"
        bad_path.write_text(json.dumps({"state": "champ_select_active"}), encoding="utf-8")  # missing required keys

        try:
            load_demo_states(directory=Path(tmp))
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "01_broken.json" in str(exc)


def test_custom_directory_is_honored():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "01_custom.json"
        path.write_text(json.dumps({
            "state_schema_version": 1,
            "state": IDLE_NO_CHAMP_SELECT,
            "draft_snapshot": None,
            "recommendations": [],
            "champion_catalog_version": None,
            "warnings": [],
            "error": None,
        }), encoding="utf-8")

        states = load_demo_states(directory=Path(tmp))

        assert len(states) == 1
        assert states[0]["state"] == IDLE_NO_CHAMP_SELECT


if __name__ == "__main__":
    test_demo_states_dir_exists_and_has_fixtures()
    test_list_demo_state_files_is_sorted_for_deterministic_cycling()
    test_every_fixture_file_is_valid_json_matching_the_state_shape()
    test_every_recommendation_entry_in_every_fixture_is_a_valid_schema_entry()
    test_load_demo_states_covers_every_runtime_state()
    test_load_demo_states_includes_a_prelock_pick_recommendation_example()
    test_load_demo_states_includes_a_locked_champion_callout_example()
    test_load_demo_states_is_deterministic_and_independently_parsed()
    test_load_demo_states_raises_with_filename_on_a_malformed_fixture()
    test_custom_directory_is_honored()
    print("All checks passed.")
