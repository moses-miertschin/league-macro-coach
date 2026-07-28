"""Atomic local JSON state publisher -- the local output layer a future
desktop UI (not built yet) will read. Accepts the application-state dict
DraftRuntimeService.poll_once() (src/draft/service.py) produces, validates
its basic shape, and writes it to disk atomically so a reader can never
observe a partially-written file.

No recommendation logic, no League API calls -- this module only ever
takes an already-computed dict and writes it to disk. Validation here is
shape-only (the seven required top-level keys the app-state contract in
src/draft/service.py already documents), not a re-derivation of anything.

Atomicity: the JSON is serialized to a string first (so a serialization
failure never touches the filesystem at all), written to a temp file in
the *same directory* as the target (so the final os.replace() is a same-
filesystem rename, atomic on both POSIX and Windows since Python 3.3), and
only then swapped into place. If anything fails before the swap, the temp
file is removed and the real output path is left completely untouched.
"""

import json
import os
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "reports" / "runtime" / "draft_state.json"

REQUIRED_STATE_KEYS = (
    "state_schema_version",
    "state",
    "draft_snapshot",
    "recommendations",
    "champion_catalog_version",
    "warnings",
    "error",
)


class InvalidStateError(ValueError):
    """Raised when the given state dict doesn't match the basic documented
    shape -- a real bug upstream, not an honestly-expected absence."""


def validate_state_shape(state) -> list:
    """Returns a list of validation error strings; empty means valid. Same
    "returns errors, doesn't raise" convention as
    src/recommendations/schema.py's validate_recommendation()."""
    if not isinstance(state, dict):
        return [f"state must be a dict, got {type(state).__name__}"]
    return [f"missing required key: '{key}'" for key in REQUIRED_STATE_KEYS if key not in state]


def publish_state(state: dict, output_path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    """Atomically writes state as deterministically-formatted JSON to
    output_path. Never mutates state. Raises InvalidStateError if state
    doesn't match the basic documented shape, or TypeError if it contains
    something json.dumps() can't serialize -- both are real bugs upstream,
    not something this module should silently paper over.
    """
    errors = validate_state_shape(state)
    if errors:
        raise InvalidStateError(f"Invalid application state: {errors}")

    serialized = json.dumps(state, indent=2, sort_keys=True)  # deterministic formatting; raises TypeError if unserializable

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(serialized)
        os.replace(tmp_path, output_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    return output_path
