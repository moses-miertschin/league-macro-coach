"""UI-independent reader for the runtime state JSON file
src/runtime/state_publisher.py's publish_state() writes.

No UI code, no League API logic, no recommendation logic -- this module
only ever reads a file from disk and classifies what it found. Reuses
state_publisher.py's own validate_state_shape() for the shape check
rather than re-deriving a second copy of the same required-fields list --
the reader and the writer must agree on exactly one definition of "valid
shape."

Never raises for an honestly-expected condition (missing file, malformed
JSON, wrong shape, or an unexpected OS-level read failure) -- every case
is reported as a StateReadResult instead, so a caller (a future watcher,
a UI) never needs to wrap a call to this module in its own try/except to
stay alive. Never mutates anything it reads; every read re-parses the
file into a fresh object.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from src.runtime.state_publisher import DEFAULT_OUTPUT_PATH, validate_state_shape

DEFAULT_STATE_PATH = DEFAULT_OUTPUT_PATH

FILE_MISSING = "file_missing"
VALID_STATE = "valid_state"
INVALID_JSON = "invalid_json"
INVALID_STATE_SHAPE = "invalid_state_shape"
READ_ERROR = "read_error"


@dataclass(frozen=True)
class StateReadResult:
    status: str
    state: dict | None
    source_path: Path
    modified_at: float | None
    error: str | None


def read_runtime_state(path: Path = DEFAULT_STATE_PATH) -> StateReadResult:
    path = Path(path)
    modified_at = None

    try:
        if not path.exists():
            return StateReadResult(FILE_MISSING, None, path, None, None)

        try:
            modified_at = path.stat().st_mtime
        except OSError:
            modified_at = None

        raw_text = path.read_text(encoding="utf-8")

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            return StateReadResult(INVALID_JSON, None, path, modified_at, f"Invalid JSON: {exc.msg} (line {exc.lineno})")

        shape_errors = validate_state_shape(parsed)
        if shape_errors:
            return StateReadResult(
                INVALID_STATE_SHAPE, None, path, modified_at,
                f"Runtime state does not match the expected shape: {', '.join(shape_errors)}",
            )

        return StateReadResult(VALID_STATE, parsed, path, modified_at, None)

    except Exception as exc:
        # Deliberately generic -- never surfaces a raw traceback or a
        # potentially sensitive exception message, just what kind of
        # failure occurred and where.
        return StateReadResult(READ_ERROR, None, path, modified_at, f"{exc.__class__.__name__} while reading {path.name}")
