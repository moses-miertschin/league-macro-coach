"""Persists analyzed games so they can be compared across matches.

Combines a match's structured analysis (analyzer.py) and macro pattern
result (macro_analyzer.py) into one flat game record, and stores all
records as a JSON list in data/database/game_history.json. Upserts by
match_id, so re-running analysis on the same match updates its record
instead of duplicating it. No AI, no advice text — storage only.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "generated_reports"
HISTORY_PATH = PROJECT_ROOT / "data" / "database" / "game_history.json"


def _pattern_value(patterns: list, pattern_name: str):
    for p in patterns:
        if p["pattern"] == pattern_name:
            return p["value"]
    return None


def build_game_record(analysis: dict, macro_result: dict) -> dict:
    patterns = macro_result["detected_patterns"]
    return {
        "match_id": analysis["match_id"],
        "game_start_timestamp": analysis.get("game_start_timestamp"),
        "champion": analysis["champion"],
        "role": analysis["role"],
        "win": analysis["win"],
        "kda": analysis["kda"],
        "deaths": analysis["kda"]["deaths"],
        "cs_per_minute": analysis["cs_per_minute"],
        "gold_per_minute": _pattern_value(patterns, "gold_per_minute"),
        "kill_participation": analysis["objectives_participation"]["kill_participation"],
        "damage": analysis["damage_to_champions"],
        "damage_share": analysis.get("damage_share"),
        "vision_score": analysis["vision_score"],
        "detected_patterns": patterns,
    }


def load_history(path: Path = HISTORY_PATH) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_history(history: list, path: Path = HISTORY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def record_game(analysis: dict, macro_result: dict, path: Path = HISTORY_PATH) -> dict:
    record = build_game_record(analysis, macro_result)
    history = load_history(path)
    history = [g for g in history if g["match_id"] != record["match_id"]]
    history.append(record)
    save_history(history, path)
    return record


def sync_all() -> list:
    """Build/update a history record for every analyzed match found on disk."""
    recorded = []
    for analysis_path in sorted(REPORTS_DIR.glob("*_analysis.json")):
        match_id = analysis_path.stem.removesuffix("_analysis")
        macro_path = REPORTS_DIR / f"{match_id}_macro_patterns.json"
        if not macro_path.exists():
            continue
        with open(analysis_path, encoding="utf-8") as f:
            analysis = json.load(f)
        with open(macro_path, encoding="utf-8") as f:
            macro_result = json.load(f)
        recorded.append(record_game(analysis, macro_result))
    return recorded


def main() -> None:
    recorded = sync_all()
    print(f"Synced {len(recorded)} game(s) into {HISTORY_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
