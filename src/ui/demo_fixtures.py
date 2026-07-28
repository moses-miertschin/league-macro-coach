"""Deterministic, hand-authored demo application-state fixtures for the
desktop app's --demo mode (Stage 7) and for tests. Every fixture under
demo/states/ is a plain JSON file shaped exactly like
DraftRuntimeService.poll_once()'s real output (src/draft/service.py) --
validated here against the same validate_state_shape() the real runtime
publisher uses, so a future --demo mode can push these straight through
publish_state() and exercise the exact same reader/watcher/presentation
pipeline real data does, rather than a second, demo-only rendering path.

No real player data, no real match data, no real captured champ-select
session -- every name and id here is illustrative sample data, the same
role fixtures already play throughout this project's test suite.
"""

import json
from pathlib import Path

from src.runtime.state_publisher import validate_state_shape

DEMO_STATES_DIR = Path(__file__).resolve().parent.parent.parent / "demo" / "states"


def list_demo_state_files(directory: Path = DEMO_STATES_DIR) -> list:
    """Sorted by filename so demo cycling order is deterministic and
    reproducible across runs -- the fixtures are numbered accordingly."""
    return sorted(Path(directory).glob("*.json"))


def load_demo_states(directory: Path = DEMO_STATES_DIR) -> list:
    """Parses and validates every fixture in directory. Raises ValueError
    naming the offending file for a malformed fixture -- that's an
    authoring bug in this project's own demo data, not an
    honestly-expected runtime absence, so it should fail loudly rather
    than silently skip a broken fixture."""
    states = []
    for path in list_demo_state_files(directory):
        state = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_state_shape(state)
        if errors:
            raise ValueError(f"Demo fixture {path.name} does not match the expected state shape: {errors}")
        states.append(state)
    return states
