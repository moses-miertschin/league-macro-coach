"""Self-check for src/runtime/state_publisher.py -- the atomic local
state-JSON publisher (Stage 3 of this session's staged implementation
plan). Written before state_publisher.py's implementation. Every test
uses a tempfile.TemporaryDirectory() -- never touches the real
reports/runtime/ directory. Run with: python -m tests.test_state_publisher
"""

import copy
import json
import tempfile
from pathlib import Path

from src.runtime.state_publisher import (
    DEFAULT_OUTPUT_PATH,
    InvalidStateError,
    publish_state,
    validate_state_shape,
)

VALID_STATE = {
    "state_schema_version": 1,
    "state": "champ_select_active",
    "draft_snapshot": {"ally_picks": [157]},
    "recommendations": [],
    "champion_catalog_version": "14.1.1",
    "warnings": [],
    "error": None,
}


def test_first_write_creates_the_file_with_exact_content():
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "draft_state.json"

        result_path = publish_state(VALID_STATE, output_path=output_path)

        assert result_path == output_path
        assert output_path.exists()
        with open(output_path, encoding="utf-8") as f:
            assert json.load(f) == VALID_STATE


def test_repeated_replacement_overwrites_with_latest_content_and_leaves_no_temp_files():
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "draft_state.json"

        publish_state(VALID_STATE, output_path=output_path)
        second_state = dict(VALID_STATE, state="idle_no_champ_select", draft_snapshot=None)
        publish_state(second_state, output_path=output_path)

        with open(output_path, encoding="utf-8") as f:
            assert json.load(f) == second_state
        leftovers = [p for p in Path(tmp).iterdir() if p != output_path]
        assert leftovers == []  # no stray .tmp files left behind


def test_parent_directory_is_created_when_missing():
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "nested" / "runtime" / "draft_state.json"

        publish_state(VALID_STATE, output_path=output_path)

        assert output_path.exists()
        with open(output_path, encoding="utf-8") as f:
            assert json.load(f) == VALID_STATE


def test_invalid_state_shape_raises_without_writing_anything():
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "draft_state.json"
        broken_state = dict(VALID_STATE)
        del broken_state["state"]

        try:
            publish_state(broken_state, output_path=output_path)
        except InvalidStateError:
            pass
        else:
            raise AssertionError("Expected InvalidStateError for a state dict missing a required key")

        assert not output_path.exists()


def test_validate_state_shape_reports_every_missing_key():
    errors = validate_state_shape({})
    assert len(errors) == 7  # every required top-level key


def test_validate_state_shape_rejects_a_non_dict():
    errors = validate_state_shape("not a dict")
    assert errors != []


def test_unserializable_data_raises_typeerror_without_writing_anything():
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "draft_state.json"
        bad_state = dict(VALID_STATE, error=object())  # not JSON serializable

        try:
            publish_state(bad_state, output_path=output_path)
        except TypeError:
            pass
        else:
            raise AssertionError("Expected TypeError for unserializable content")

        assert not output_path.exists()


def test_does_not_mutate_the_original_state_dict():
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "draft_state.json"
        original_copy = copy.deepcopy(VALID_STATE)

        publish_state(VALID_STATE, output_path=output_path)

        assert VALID_STATE == original_copy


def test_atomic_replace_failure_cleans_up_the_temp_file():
    with tempfile.TemporaryDirectory() as tmp:
        # output_path itself is a directory, not a file -- the final
        # os.replace() onto it must fail, proving the temp file created
        # along the way is cleaned up rather than left behind.
        output_dir_as_target = Path(tmp) / "draft_state.json"
        output_dir_as_target.mkdir()

        try:
            publish_state(VALID_STATE, output_path=output_dir_as_target)
        except OSError:
            pass
        else:
            raise AssertionError("Expected an OSError when the output path is itself a directory")

        leftovers = list(Path(tmp).iterdir())
        assert leftovers == [output_dir_as_target]  # only the pre-existing directory -- no stray temp file


def test_default_output_path_is_reports_runtime_draft_state_json():
    assert DEFAULT_OUTPUT_PATH.parts[-3:] == ("reports", "runtime", "draft_state.json")


if __name__ == "__main__":
    test_first_write_creates_the_file_with_exact_content()
    test_repeated_replacement_overwrites_with_latest_content_and_leaves_no_temp_files()
    test_parent_directory_is_created_when_missing()
    test_invalid_state_shape_raises_without_writing_anything()
    test_validate_state_shape_reports_every_missing_key()
    test_validate_state_shape_rejects_a_non_dict()
    test_unserializable_data_raises_typeerror_without_writing_anything()
    test_does_not_mutate_the_original_state_dict()
    test_atomic_replace_failure_cleans_up_the_temp_file()
    test_default_output_path_is_reports_runtime_draft_state_json()
    print("All checks passed.")
