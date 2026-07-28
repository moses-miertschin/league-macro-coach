"""Self-check for src/ui/state_reader.py -- the UI-independent runtime
state file reader (Stage 1 of the desktop-app session). Written before
state_reader.py's implementation. Every test uses
tempfile.TemporaryDirectory() -- never touches the real reports/runtime/
directory, no League installation, no network.
Run with: python -m tests.test_state_reader
"""

import json
import tempfile
from pathlib import Path

from src.ui.state_reader import (
    DEFAULT_STATE_PATH,
    FILE_MISSING,
    INVALID_JSON,
    INVALID_STATE_SHAPE,
    READ_ERROR,
    VALID_STATE,
    read_runtime_state,
)

VALID_STATE_DICT = {
    "state_schema_version": 1,
    "state": "champ_select_active",
    "draft_snapshot": {"ally_picks": [157]},
    "recommendations": [],
    "champion_catalog_version": "14.1.1",
    "warnings": [],
    "error": None,
}


def test_missing_file_returns_file_missing():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "does_not_exist.json"

        result = read_runtime_state(path)

        assert result.status == FILE_MISSING
        assert result.state is None
        assert result.source_path == path
        assert result.modified_at is None
        assert result.error is None


def test_valid_idle_state_is_read_correctly():
    idle_state = dict(VALID_STATE_DICT, state="idle_no_champ_select", draft_snapshot=None)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(idle_state), encoding="utf-8")

        result = read_runtime_state(path)

        assert result.status == VALID_STATE
        assert result.state == idle_state
        assert result.modified_at is not None
        assert result.error is None


def test_valid_active_state_is_read_correctly():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(VALID_STATE_DICT), encoding="utf-8")

        result = read_runtime_state(path)

        assert result.status == VALID_STATE
        assert result.state == VALID_STATE_DICT


def test_invalid_json_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text("{not valid json", encoding="utf-8")

        result = read_runtime_state(path)

        assert result.status == INVALID_JSON
        assert result.state is None
        assert result.error is not None
        assert result.modified_at is not None  # file exists -- stat still succeeds


def test_wrong_top_level_type_is_invalid_state_shape():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")

        result = read_runtime_state(path)

        assert result.status == INVALID_STATE_SHAPE
        assert result.state is None


def test_missing_required_state_fields_is_invalid_state_shape():
    broken = dict(VALID_STATE_DICT)
    del broken["state"]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(broken), encoding="utf-8")

        result = read_runtime_state(path)

        assert result.status == INVALID_STATE_SHAPE
        assert "state" in result.error


def test_extra_forward_compatible_fields_are_preserved():
    extended = dict(VALID_STATE_DICT, some_future_field={"nested": "value"})
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(extended), encoding="utf-8")

        result = read_runtime_state(path)

        assert result.status == VALID_STATE
        assert result.state["some_future_field"] == {"nested": "value"}


def test_utf8_content_is_read_correctly():
    state_with_unicode = dict(VALID_STATE_DICT, error="Ünïcödé Chämpiön Návé — 日本語")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(state_with_unicode, ensure_ascii=False), encoding="utf-8")

        result = read_runtime_state(path)

        assert result.status == VALID_STATE
        assert result.state["error"] == "Ünïcödé Chämpiön Návé — 日本語"


def test_repeated_reads_return_independently_parsed_objects():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(VALID_STATE_DICT), encoding="utf-8")

        first = read_runtime_state(path)
        second = read_runtime_state(path)

        assert first.state == second.state
        assert first.state is not second.state  # independently parsed -- no shared mutable state


def test_configurable_path_is_honored():
    with tempfile.TemporaryDirectory() as tmp:
        custom_path = Path(tmp) / "custom_name.json"
        custom_path.write_text(json.dumps(VALID_STATE_DICT), encoding="utf-8")

        result = read_runtime_state(custom_path)

        assert result.source_path == custom_path
        assert result.status == VALID_STATE


def test_default_path_matches_state_publisher_default():
    from src.runtime.state_publisher import DEFAULT_OUTPUT_PATH

    assert DEFAULT_STATE_PATH == DEFAULT_OUTPUT_PATH


def test_read_exception_is_handled_as_read_error_not_a_crash():
    with tempfile.TemporaryDirectory() as tmp:
        # A directory where a file is expected -- reading it as text raises
        # a platform-specific OSError subclass.
        path = Path(tmp) / "state.json"
        path.mkdir()

        result = read_runtime_state(path)  # must not raise

        assert result.status == READ_ERROR
        assert result.error is not None


def test_error_messages_never_contain_a_raw_traceback():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text("not json at all {{{", encoding="utf-8")

        result = read_runtime_state(path)

        assert "Traceback" not in (result.error or "")
        assert 'File "' not in (result.error or "")


if __name__ == "__main__":
    test_missing_file_returns_file_missing()
    test_valid_idle_state_is_read_correctly()
    test_valid_active_state_is_read_correctly()
    test_invalid_json_is_detected()
    test_wrong_top_level_type_is_invalid_state_shape()
    test_missing_required_state_fields_is_invalid_state_shape()
    test_extra_forward_compatible_fields_are_preserved()
    test_utf8_content_is_read_correctly()
    test_repeated_reads_return_independently_parsed_objects()
    test_configurable_path_is_honored()
    test_default_path_matches_state_publisher_default()
    test_read_exception_is_handled_as_read_error_not_a_crash()
    test_error_messages_never_contain_a_raw_traceback()
    print("All checks passed.")
