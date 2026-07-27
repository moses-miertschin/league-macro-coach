"""Self-check for src/knowledge/item_loader.py.

Writes a fixture markdown file to a temp dir -- no dependency on the real
knowledge/items/ content. Run with: python -m tests.test_item_loader
"""

import tempfile
from pathlib import Path

from src.knowledge.item_loader import load_item_knowledge

SAMPLE_MD = """# Test Champion — Item Guidance

## Core Build
- Kraken Slayer
- Berserker's Greaves -- standard boots choice

## Wit's End
- Valuable when: enemy has 2+ champions dealing primarily magic damage
- Bad when: enemy team is almost entirely physical damage
- Champion fit: attack-speed scaling synergizes well
- Priority: high vs AP-heavy comps
- Game state: situational regardless of ahead/behind

## Avoid: Guardian Angel
- Bad when: always for this champion
- Champion fit: poor -- no reliable disengage
"""


def test_parses_core_build_items_and_general():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.md"
        path.write_text(SAMPLE_MD, encoding="utf-8")

        result = load_item_knowledge(path)

        assert result["core_build"] == ["Kraken Slayer", "Berserker's Greaves"]


def test_parses_five_field_item_record():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.md"
        path.write_text(SAMPLE_MD, encoding="utf-8")

        result = load_item_knowledge(path)

        wits_end = result["items"]["Wit's End"]
        assert wits_end["valuable_when"] == "enemy has 2+ champions dealing primarily magic damage"
        assert wits_end["bad_when"] == "enemy team is almost entirely physical damage"
        assert wits_end["champion_fit"] == "attack-speed scaling synergizes well"
        assert wits_end["priority"] == "high vs AP-heavy comps"
        assert wits_end["game_state"] == "situational regardless of ahead/behind"


def test_parses_avoid_section():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.md"
        path.write_text(SAMPLE_MD, encoding="utf-8")

        result = load_item_knowledge(path)

        assert "Guardian Angel" in result["avoid"]
        assert result["avoid"]["Guardian Angel"]["bad_when"] == "always for this champion"


def test_missing_file_returns_empty_structure():
    result = load_item_knowledge(Path("does/not/exist.md"))
    assert result == {"core_build": [], "items": {}, "avoid": {}}


if __name__ == "__main__":
    test_parses_core_build_items_and_general()
    test_parses_five_field_item_record()
    test_parses_avoid_section()
    test_missing_file_returns_empty_structure()
    print("All checks passed.")
