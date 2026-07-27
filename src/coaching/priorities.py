"""Selects the top 1-3 improvement priorities for a coaching session.

Prefers cross-game, evidence-backed priorities (player_insights.json's
priority_improvements, which only ever surface a pattern after 2+ games --
see src/history/aggregate.py's repeated-pattern threshold) over this-game
observations. Single-game patterns only fill remaining slots when cross-game
history doesn't yet have enough, and are explicitly labeled with a
different "scope" so a one-off is never presented with the same weight as
a proven repeat.

No AI, no invented statistics -- every evidence string is copied verbatim
from existing data. The one piece of authored text is a small, fixed,
category-level practice-goal template (not champion-specific tactical
advice, and not per-instance-generated), the same kind of hand-curated
prose the knowledge/ files already contain, just not requiring a new
knowledge file for this first pass.
"""

MAX_LESSONS = 3

IMPACT_WEIGHT = {"high": 3, "medium": 2, "low": 1}

# ponytail: generic, category-level practice framing, not champion-specific.
# Revisit once knowledge/ has per-category or per-champion practice content
# to draw from instead of this fixed fallback.
PRACTICE_GOALS_BY_CATEGORY = {
    "deaths": "Review each death this game and identify one point where retreating or repositioning earlier was possible.",
    "farming": "Track CS/min over your next few games and compare it against this session's number.",
    "objectives": "Before the next objective spawns, check whether you're positioned to contribute to the fight.",
    "vision": "Place one additional ward within two minutes of your next recall.",
}
DEFAULT_PRACTICE_GOAL = "Focus on this specific pattern in your next game."


def _category_for_pattern(pattern_name: str, macro_patterns: dict | None) -> str | None:
    if not macro_patterns:
        return None
    for p in macro_patterns.get("detected_patterns", []):
        if p["pattern"] == pattern_name:
            return p["category"]
    return None


def _practice_goal(category: str | None) -> str:
    return PRACTICE_GOALS_BY_CATEGORY.get(category, DEFAULT_PRACTICE_GOAL)


def _cross_game_lessons(insights: dict | None, macro_patterns: dict | None) -> list:
    if not insights:
        return []
    ranked = sorted(
        insights.get("priority_improvements", []),
        key=lambda p: IMPACT_WEIGHT.get(p.get("impact"), 0),
        reverse=True,
    )
    lessons = []
    for entry in ranked:
        category = _category_for_pattern(entry["issue"], macro_patterns)
        lessons.append({
            "issue": entry["issue"],
            "evidence": [entry["reason"]],
            "why_it_matters": (
                f"This is a recurring pattern ({entry['reason']}), tracked across your full game "
                "history -- repeated patterns are the most reliable signal for what to prioritize."
            ),
            "practice_goal": _practice_goal(category),
            "scope": "recurring",
            "confidence": entry.get("impact", "unknown"),
        })
    return lessons


def _single_game_lessons(macro_patterns: dict | None, exclude_patterns: set, remaining_slots: int) -> list:
    if not macro_patterns or remaining_slots <= 0:
        return []
    lessons = []
    for p in macro_patterns.get("detected_patterns", []):
        if len(lessons) >= remaining_slots:
            break
        if not p.get("concern") or p["pattern"] in exclude_patterns:
            continue
        lessons.append({
            "issue": p["pattern"],
            "evidence": [f"This game: {p['detail']} (value: {p['value']})"],
            "why_it_matters": (
                f"Flagged as a concern in this game ({p['detail']}) -- not yet confirmed as a "
                "repeated pattern across multiple games."
            ),
            "practice_goal": _practice_goal(p["category"]),
            "scope": "this_game",
            "confidence": p.get("confidence", "unknown"),
        })
    return lessons


def select_priorities(insights: dict | None, macro_patterns: dict | None) -> list:
    cross_game = _cross_game_lessons(insights, macro_patterns)[:MAX_LESSONS]
    remaining = MAX_LESSONS - len(cross_game)
    exclude = {lesson["issue"] for lesson in cross_game}
    single_game = _single_game_lessons(macro_patterns, exclude, remaining)

    combined = cross_game + single_game
    for i, lesson in enumerate(combined, start=1):
        lesson["priority"] = i
    return combined
