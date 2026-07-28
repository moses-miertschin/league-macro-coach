"""Loads knowledge/champions/{champion}_profile.md into a validated,
structured champion knowledge dict -- the future data source for draft
recommendation, matchup analysis, rune recommendation, and item
recommendation systems (see ROADMAP.md Sec.3-4,
RECOMMENDATION_SYSTEM_DESIGN.md). No recommendation, synergy, counter, or
rune logic lives here -- structured extraction and validation only.

Sibling to src/knowledge/loader.py and src/knowledge/item_loader.py rather
than an extension of either: this is a third, genuinely different record
shape (a draft profile, not macro-coaching notes or item guidance), the
same "different shape, own loader" precedent item_loader.py already
established relative to loader.py. The existing
knowledge/champions/{champion}.md coaching files (loaded by loader.py's
load_champion()) are completely untouched -- this reads a
differently-named sibling file per champion, so both record types can
coexist in the same directory with zero collision.

Every returned dict has already passed
src/knowledge/champion_schema.py's validate_champion_profile(). A missing
file returns None (honest absence, matching load_champion()'s existing
convention); a malformed *existing* file raises ValueError instead, since
a hand-authored knowledge file failing validation is a real authoring
bug, not an expected absence -- the same "missing vs malformed" split
src/draft/client.py already draws for LCU lockfiles.
"""

from pathlib import Path

from src.knowledge.champion_schema import validate_champion_profile

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHAMPIONS_DIR = PROJECT_ROOT / "knowledge" / "champions"

_BULLET_SECTIONS = {
    "Roles": "roles",
    "Strengths": "strengths",
    "Weaknesses": "weaknesses",
    "Common Counters": "common_counters",
    "Favorable Matchups": "favorable_matchups",
    "Synergy Champions": "synergy_champions",
}
_SINGLE_LINE_SECTIONS = {
    "Damage Type": "damage_type",
    "Scaling Profile": "scaling_profile",
}
_PROSE_SECTIONS = {
    "Preferred Playstyle": "preferred_playstyle",
}
_TITLE_SEPARATORS = (" — ", " -- ", " - ")


def _bullets(block: str) -> list:
    return [line.strip("- ").strip() for line in block.splitlines() if line.strip().startswith("-")]


def _first_line(block: str) -> str:
    for line in block.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _extract_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            for sep in _TITLE_SEPARATORS:
                if sep in title:
                    title = title.split(sep, 1)[0].strip()
            return title or None
    return None


def _parse_profile_markdown(text: str, fallback_champion: str) -> dict:
    profile = {
        "champion": _extract_title(text) or fallback_champion,
        "roles": [],
        "damage_type": "unknown",
        "scaling_profile": "unknown",
        "strengths": [],
        "weaknesses": [],
        "preferred_playstyle": None,
        "common_counters": [],
        "favorable_matchups": [],
        "synergy_champions": [],
    }

    current_field = None
    current_kind = None  # "bullets" | "single_line" | "prose"
    lines_for_field = []

    def flush():
        if current_field is None:
            return
        block = "\n".join(lines_for_field)
        if current_kind == "bullets":
            profile[current_field] = _bullets(block)
        elif current_kind == "single_line":
            value = _first_line(block).lower().replace(" ", "_")
            profile[current_field] = value or "unknown"
        elif current_kind == "prose":
            profile[current_field] = block.strip() or None

    for line in text.splitlines():
        heading = line.strip()
        if heading.startswith("## "):
            flush()
            lines_for_field = []
            title = heading[3:].strip()
            if title in _BULLET_SECTIONS:
                current_field, current_kind = _BULLET_SECTIONS[title], "bullets"
            elif title in _SINGLE_LINE_SECTIONS:
                current_field, current_kind = _SINGLE_LINE_SECTIONS[title], "single_line"
            elif title in _PROSE_SECTIONS:
                current_field, current_kind = _PROSE_SECTIONS[title], "prose"
            else:
                current_field, current_kind = None, None
        elif current_field:
            lines_for_field.append(line)
    flush()

    profile["roles"] = [r.lower() for r in profile["roles"]]

    return profile


def load_champion_profile(champion: str, champions_dir: Path = CHAMPIONS_DIR) -> dict | None:
    path = champions_dir / f"{champion.lower()}_profile.md"
    if not path.exists():
        return None

    profile = _parse_profile_markdown(path.read_text(encoding="utf-8"), fallback_champion=champion)

    errors = validate_champion_profile(profile)
    if errors:
        raise ValueError(f"Invalid champion profile for {champion!r} at {path}: {errors}")

    return profile


def list_available_champion_profiles(champions_dir: Path = CHAMPIONS_DIR) -> list:
    """Discovers every authored {champion}_profile.md in champions_dir and
    returns their canonical champion names -- never a hardcoded roster, so
    coverage grows automatically as new profile files are authored. Each
    name comes from load_champion_profile() itself (the file's own
    # Heading), the same source of truth used everywhere else in this
    module. Sorted by filename for a deterministic order; a malformed file
    still raises (via load_champion_profile()), consistent with this
    module's existing "malformed data is a bug" discipline.
    """
    if not champions_dir.exists():
        return []

    names = []
    for path in sorted(champions_dir.glob("*_profile.md")):
        champion_arg = path.stem.removesuffix("_profile")
        profile = load_champion_profile(champion_arg, champions_dir=champions_dir)
        if profile is not None:
            names.append(profile["champion"])
    return names
