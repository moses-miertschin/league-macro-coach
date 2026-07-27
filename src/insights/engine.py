"""Converts stored player profile data into structured insights.

Reads reports/generated_reports/profile_summary.json (produced by
src/profile/generator.py) and reshapes its already-computed strength and
weakness patterns into the player_insights.json schema. No LLM calls, no
AI-generated coaching text, no generic League advice — every field here is
either copied from profile_summary.json or a deterministic function of its
numbers (games_flagged, games_played).

The "insufficient_data" case only covers a genuinely empty profile (zero
games recorded) — the "not enough games to trust a pattern" case is
already handled upstream: src/history/aggregate.py's repeated_strengths()/
repeated_weaknesses() only surface a pattern once it has been observed in
at least 2 games, so with too little history those lists simply arrive
empty and this module has nothing invented to add.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "generated_reports"
PROFILE_SUMMARY_PATH = REPORTS_DIR / "profile_summary.json"
INSIGHTS_PATH = REPORTS_DIR / "player_insights.json"

# ponytail: confidence is a simple step function of raw game count, not a
# statistical measure. Revisit if/when there's enough history to justify
# something more rigorous (e.g. a confidence interval on the rate).
HIGH_CONFIDENCE_GAMES = 5
MEDIUM_CONFIDENCE_GAMES = 3


def _confidence(games_flagged: int) -> str:
    if games_flagged >= HIGH_CONFIDENCE_GAMES:
        return "high"
    if games_flagged >= MEDIUM_CONFIDENCE_GAMES:
        return "medium"
    return "low"


def _evidence(games_flagged: int, games_played: int) -> str:
    return f"Observed in {games_flagged} of {games_played} games"


def _pattern_insight(pattern_entry: dict, games_played: int) -> dict:
    games_flagged = pattern_entry["games_flagged"]
    return {
        "pattern": pattern_entry["pattern"],
        "evidence": _evidence(games_flagged, games_played),
        "confidence": _confidence(games_flagged),
    }


def _priority_improvement(pattern_entry: dict, games_played: int) -> dict:
    games_flagged = pattern_entry["games_flagged"]
    return {
        "issue": pattern_entry["pattern"],
        "reason": _evidence(games_flagged, games_played),
        "impact": _confidence(games_flagged),
    }


def _empty_insights() -> dict:
    return {
        "player_summary": {
            "games_analyzed": 0,
            "main_champion": "insufficient_data",
            "main_role": "insufficient_data",
        },
        "strengths": [],
        "weaknesses": [],
        "priority_improvements": [],
    }


def generate_insights(profile_summary: dict) -> dict:
    games_played = profile_summary.get("games_played", 0)
    if not games_played:
        return _empty_insights()

    most_played = profile_summary.get("most_played_champions", [])
    main_champion = most_played[0]["champion"] if most_played else "insufficient_data"

    role_distribution = profile_summary.get("role_distribution", {})
    main_role = (
        max(role_distribution.items(), key=lambda item: item[1]["games"])[0]
        if role_distribution
        else "insufficient_data"
    )

    weaknesses_ranked = sorted(
        profile_summary.get("weakness_patterns", []),
        key=lambda p: p["games_flagged"],
        reverse=True,
    )

    return {
        "player_summary": {
            "games_analyzed": games_played,
            "main_champion": main_champion,
            "main_role": main_role,
        },
        "strengths": [
            _pattern_insight(p, games_played) for p in profile_summary.get("strength_patterns", [])
        ],
        "weaknesses": [_pattern_insight(p, games_played) for p in weaknesses_ranked],
        "priority_improvements": [
            _priority_improvement(p, games_played) for p in weaknesses_ranked
        ],
    }


def load_profile_summary(path: Path = PROFILE_SUMMARY_PATH) -> dict:
    if not path.exists():
        return {"games_played": 0}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    profile_summary = load_profile_summary()
    insights = generate_insights(profile_summary)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(INSIGHTS_PATH, "w", encoding="utf-8") as f:
        json.dump(insights, f, indent=2)

    print(f"Saved player insights to {INSIGHTS_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
