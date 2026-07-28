"""Orchestrates the first complete user-facing coaching report.

Combines player_insights.json, profile_summary.json, one match's macro
patterns (which already carry timeline-derived evidence -- see
src/analysis/timeline_analyzer.py and macro_analyzer.py's integration of
it), that match's item recommendations, and (if any exist) stored benchmark
comparisons into one coaching_session.json.

This is pure combination, not analysis: every field here already exists in
one of those files. Nothing is computed, thresholded, or decided here --
that already happened upstream. No AI, no Anthropic dependency, no network
call -- this module works from disk alone and always will.

The benchmark section is informational only -- see
src/coaching/benchmark_section.py's docstring. It is never read by
select_priorities() and never influences main_lessons/next_game_focus.
"""

import json
from pathlib import Path

from src.analysis.macro_analyzer import latest_structured_analysis
from src.benchmark.storage import BENCHMARK_DATA_PATH
from src.coaching.benchmark_section import build_benchmark_section
from src.coaching.formatter import print_session
from src.coaching.priorities import select_priorities
from src.recommendations.adapters import adapt_item_recommendation, adapt_macro_lesson

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "generated_reports"
PROFILE_PATH = PROJECT_ROOT / "data" / "player_profile.json"
COACHING_SESSION_PATH = REPORTS_DIR / "coaching_session.json"


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _game_result(analysis: dict) -> str:
    return "Win" if analysis.get("win") else "Loss"


def _item_review(item_recommendations: dict | None) -> dict:
    if item_recommendations is None:
        return {
            "status": "unavailable",
            "detail": "Item recommendations were not generated for this match.",
        }
    return {
        "status": "available",
        "player_state": item_recommendations.get("player_state", {}),
        "top_recommendations": item_recommendations.get("recommendations", [])[:3],
        "unrecognized_items_flagged": item_recommendations.get("unrecognized_items_flagged", []),
    }


def _shared_recommendations(item_recommendations: dict | None, main_lessons: list) -> list:
    """Additive shared-schema view of this session's recommendations, per
    RECOMMENDATION_SYSTEM_DESIGN.md's Stage-1 adapters. Pure coordination --
    translation logic lives in src/recommendations/adapters.py, not here.
    """
    entries = []
    if item_recommendations is not None:
        entries.extend(adapt_item_recommendation(r) for r in item_recommendations.get("recommendations", []))
    entries.extend(adapt_macro_lesson(lesson) for lesson in main_lessons)
    return entries


def build_coaching_session(
    match_id: str,
    reports_dir: Path = REPORTS_DIR,
    profile_path: Path = PROFILE_PATH,
    benchmark_path: Path = BENCHMARK_DATA_PATH,
) -> dict:
    analysis = _load_json(reports_dir / f"{match_id}_analysis.json")
    if analysis is None:
        raise RuntimeError(f"No structured analysis found for match {match_id} in {reports_dir}")

    macro_patterns = _load_json(reports_dir / f"{match_id}_macro_patterns.json")
    item_recommendations = _load_json(reports_dir / f"{match_id}_item_recommendations.json")
    insights = _load_json(reports_dir / "player_insights.json")
    profile = _load_json(profile_path) or {}

    main_lessons = select_priorities(insights, macro_patterns)

    return {
        "player": profile.get("riot_id", "unknown"),
        "champion": analysis.get("champion", "unknown"),
        "game_result": _game_result(analysis),
        "main_lessons": main_lessons,
        "item_review": _item_review(item_recommendations),
        "benchmark": build_benchmark_section(analysis, macro_patterns, benchmark_path=benchmark_path),
        "strengths": (insights or {}).get("strengths", []),
        "next_game_focus": [lesson["issue"] for lesson in main_lessons],
        "shared_recommendations": _shared_recommendations(item_recommendations, main_lessons),
    }


def main() -> None:
    analysis_path = latest_structured_analysis()
    match_id = analysis_path.stem.removesuffix("_analysis")

    session = build_coaching_session(match_id)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(COACHING_SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2)

    print(f"Saved coaching session to {COACHING_SESSION_PATH.relative_to(PROJECT_ROOT)}\n")
    print_session(session)


if __name__ == "__main__":
    main()
