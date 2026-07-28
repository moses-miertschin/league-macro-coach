"""Sanitized champ-select capture tool -- an explicitly-invoked diagnostic
mode (see src/draft/cli.py's --capture-once), never run automatically and
never part of the regular --once/--watch poll flow.

Exists because every LCU/DraftSnapshot fixture in this codebase's tests is
hand-built from Riot's public documentation, never verified against a
real running client (a gap CHECKPOINT.md has flagged repeatedly). This
tool closes that gap without guessing at the real shape in advance: it
recursively redacts a small, named set of sensitive key names wherever
they appear, at any nesting depth, rather than assuming an exact field
path -- the whole point is that the real response shape isn't confirmed
yet, so a path-specific sanitizer could miss a sensitive field sitting
somewhere unexpected. Every other field name and structure is kept
intact, so the captured sample can be diffed by hand against this
project's REAL_CHAMP_SELECT_SESSION-style test fixtures.

Never captures the lockfile password, auth headers, or any of the
sensitive fields below -- redacted to a fixed placeholder, never silently
dropped (dropping a key would hide whether it existed at all, defeating
the point of a structural comparison).
"""

import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CAPTURE_DIR = PROJECT_ROOT / "reports" / "captures"

# Case-insensitive key-name matches, redacted wherever they appear at any
# nesting depth. Deliberately name-based, not path-based.
SENSITIVE_KEY_NAMES = {
    "password",
    "chatroompassword",
    "puuid",
    "summonerid",
    "accountid",
    "displayname",
    "gamename",
    "internalname",
    "riotid",
    "tagline",
    "authorization",
    "token",
    "secret",
}

REDACTED_PLACEHOLDER = "[REDACTED]"

CAPTURE_FILE_WARNING = (
    "This is a sanitized capture of a real League Client (LCU) champ-select "
    "response, made for comparing this project's hand-built test fixtures "
    "against the real API shape. Known sensitive fields (password, puuid, "
    "summonerId, etc.) are redacted, but this sanitizer is best-effort, not "
    "a guarantee -- review this file yourself before sharing or committing it."
)


def sanitize(value):
    """Recursively redacts known-sensitive key names anywhere in value.
    Never mutates the input -- always returns a new structure."""
    if isinstance(value, dict):
        return {
            key: (REDACTED_PLACEHOLDER if key.lower() in SENSITIVE_KEY_NAMES else sanitize(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def capture_champ_select(
    raw_session: dict,
    snapshot: dict | None,
    capture_dir: Path = DEFAULT_CAPTURE_DIR,
    clock_fn=lambda: time.strftime("%Y%m%dT%H%M%S"),
) -> dict:
    """Writes a sanitized raw-session sample and the normalized snapshot to
    capture_dir, timestamped via clock_fn (injectable for deterministic
    filenames in tests). Returns {"raw_path": Path, "snapshot_path": Path}.
    """
    capture_dir = Path(capture_dir)
    capture_dir.mkdir(parents=True, exist_ok=True)
    timestamp = clock_fn()

    raw_path = capture_dir / f"{timestamp}_raw_session.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(
            {"_warning": CAPTURE_FILE_WARNING, "captured_at": timestamp, "session": sanitize(raw_session)},
            f, indent=2, sort_keys=True,
        )

    snapshot_path = capture_dir / f"{timestamp}_snapshot.json"
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(
            {"_warning": CAPTURE_FILE_WARNING, "captured_at": timestamp, "snapshot": sanitize(snapshot)},
            f, indent=2, sort_keys=True,
        )

    return {"raw_path": raw_path, "snapshot_path": snapshot_path}
