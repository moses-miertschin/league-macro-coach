"""Loads item knowledge markdown files into structured dicts.

Sibling to src/knowledge/loader.py rather than an extension of it --
champion/role knowledge uses a fixed section-name template
(loader.py's SECTION_KEYS); item knowledge uses item *names* as headings
with a fixed five-field record per item, a different enough shape that
sharing the parser would mean threading a section-key map through
loader.py's existing callers for no benefit.

Each knowledge/items/{champion}.md has three kinds of section:
  ## Core Build          -- plain item-name bullets, always relevant
  ## Avoid: Item Name     -- hard-excluded regardless of any trigger
  ## Item Name            -- everything else: a five-field qualitative
                             record (Valuable when / Bad when / Champion
                             fit / Priority / Game state), still prose,
                             not numeric thresholds.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ITEMS_DIR = PROJECT_ROOT / "knowledge" / "items"

FIELD_KEYS = {
    "valuable when": "valuable_when",
    "bad when": "bad_when",
    "champion fit": "champion_fit",
    "priority": "priority",
    "game state": "game_state",
}


def _parse_field_bullets(lines: list) -> dict:
    fields = {}
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("-") or ":" not in stripped:
            continue
        content = stripped.lstrip("- ").strip()
        key, _, value = content.partition(":")
        field_key = FIELD_KEYS.get(key.strip().lower())
        if field_key:
            fields[field_key] = value.strip()
    return fields


def _parse_core_build(lines: list) -> list:
    names = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        name = stripped.lstrip("- ").strip()
        name = name.split(" -- ")[0].split(" — ")[0].strip()
        if name:
            names.append(name)
    return names


def load_item_knowledge(path: Path) -> dict:
    if not path.exists():
        return {"core_build": [], "items": {}, "avoid": {}}

    core_build = []
    items = {}
    avoid = {}

    current_section = None  # "core_build" | "item" | "avoid"
    current_name = None
    current_lines = []

    def flush():
        if current_section == "core_build":
            core_build.extend(_parse_core_build(current_lines))
        elif current_section == "item" and current_name:
            items[current_name] = _parse_field_bullets(current_lines)
        elif current_section == "avoid" and current_name:
            avoid[current_name] = _parse_field_bullets(current_lines)

    for line in path.read_text(encoding="utf-8").splitlines():
        heading = line.strip()
        if heading.startswith("## "):
            flush()
            current_lines = []
            title = heading[3:].strip()
            if title.lower() == "core build":
                current_section, current_name = "core_build", None
            elif title.lower().startswith("avoid:"):
                current_section, current_name = "avoid", title.split(":", 1)[1].strip()
            else:
                current_section, current_name = "item", title
        else:
            current_lines.append(line)
    flush()

    return {"core_build": core_build, "items": items, "avoid": avoid}


def load_champion_items(champion: str, items_dir: Path = ITEMS_DIR) -> dict:
    return load_item_knowledge(items_dir / f"{champion.lower()}.md")


def load_general_items(items_dir: Path = ITEMS_DIR) -> dict:
    return load_item_knowledge(items_dir / "general.md")
