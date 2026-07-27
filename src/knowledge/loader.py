"""Loads champion and role knowledge markdown files into structured dicts.

Parses the fixed section template used by knowledge/champions/*.md and
knowledge/roles/*.md (Expected Role, Important Metrics, Metrics That
Matter Less, Common Mistakes to Detect, General Improvement Categories)
into a plain dict. No AI, no coaching text — this only makes the existing
markdown content queryable by section.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHAMPIONS_DIR = PROJECT_ROOT / "knowledge" / "champions"
ROLES_DIR = PROJECT_ROOT / "knowledge" / "roles"

SECTION_KEYS = {
    "Expected Role": "expected_role",
    "Important Metrics": "important_metrics",
    "Metrics That Matter Less": "metrics_that_matter_less",
    "Common Mistakes to Detect": "common_mistakes",
    "General Improvement Categories": "improvement_categories",
}
BULLET_SECTIONS = (
    "important_metrics",
    "metrics_that_matter_less",
    "common_mistakes",
    "improvement_categories",
)

# ponytail: Riot's teamPosition values don't match the knowledge filenames
# 1:1. Only the two roles with knowledge files today are mapped; add more
# entries here as knowledge/roles/ grows.
ROLE_FILENAME_MAP = {
    "middle": "mid",
    "utility": "support",
}


def _bullets(block: str) -> list:
    return [line.strip("- ").strip() for line in block.splitlines() if line.strip().startswith("-")]


def _parse_markdown(text: str) -> dict:
    sections = {}
    current_key = None
    lines_for_key = []

    def flush():
        if current_key:
            sections[current_key] = "\n".join(lines_for_key).strip()

    for line in text.splitlines():
        heading = line.strip()
        if heading.startswith("## "):
            flush()
            current_key = SECTION_KEYS.get(heading[3:].strip())
            lines_for_key = []
        elif current_key:
            lines_for_key.append(line)
    flush()

    for key in BULLET_SECTIONS:
        if key in sections:
            sections[key] = _bullets(sections[key])

    return sections


def load_champion(champion: str) -> dict | None:
    path = CHAMPIONS_DIR / f"{champion.lower()}.md"
    if not path.exists():
        return None
    return _parse_markdown(path.read_text(encoding="utf-8"))


def load_role(role: str) -> dict | None:
    normalized = ROLE_FILENAME_MAP.get(role.lower(), role.lower())
    path = ROLES_DIR / f"{normalized}.md"
    if not path.exists():
        return None
    return _parse_markdown(path.read_text(encoding="utf-8"))
