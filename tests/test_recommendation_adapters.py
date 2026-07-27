"""Self-check for src/recommendations/adapters.py.

Written before adapters.py's implementation. Fixtures match the *actual*
current output shapes of item_recommender.recommend_items() and
coaching/priorities.select_priorities() -- neither module is imported or
touched here; these are hand-built dicts mirroring their real shapes, so
this test suite has no dependency on those modules' internals.
Run with: python -m tests.test_recommendation_adapters
"""

import copy

from src.recommendations.adapters import adapt_item_recommendation, adapt_macro_lesson
from src.recommendations.schema import validate_recommendation

# Matches item_recommender.py's real per-recommendation shape (a "complete_item" entry).
ITEM_ENTRY = {
    "item": "Zhonya's Hourglass",
    "triggered_rules": ["enemy_has_fed_carry", "game_state_behind"],
    "evidence": [{"fact": "enemy_has_fed_carry", "champions": ["Caitlyn"]}],
    "confidence_score": 45,
    "confidence_tier": "medium",
    "confidence_breakdown": [
        {"factor": "trigger_matched", "points": 40},
        {"factor": "additional_trigger_matched", "points": 20},
        {"factor": "champion_specific_knowledge", "points": 15},
        {"factor": "conflicting_signal", "points": -30},
    ],
    "conflicting_signal": True,
    "reason": "Zhonya's Hourglass: Valuable when behind, or facing a fed enemy carry that threatens burst kills.",
    "source": "champion_knowledge",
    "cost": 2600,
    "builds_toward": None,
    "purchasable_now": None,
    "priority": 1,
    "recommendation_type": "complete_item",
}

# Matches item_recommender.py's save_gold entry -- no item, no cost, no trigger.
SAVE_GOLD_ENTRY = {
    "item": None,
    "triggered_rules": [],
    "evidence": [{"fact": "available_gold", "value": 100}],
    "confidence_score": 100,
    "confidence_tier": "high",
    "confidence_breakdown": [{"factor": "gold_insufficient_for_all_candidates", "points": 100}],
    "conflicting_signal": False,
    "reason": "Available gold (100) isn't enough for any recommended item or component right now -- hold gold for your next back.",
    "source": "computed",
    "cost": None,
    "builds_toward": None,
    "purchasable_now": None,
    "priority": 4,
    "recommendation_type": "save_gold",
}

# Matches coaching/priorities.py's real lesson shape -- a recurring, cross-game lesson.
RECURRING_LESSON = {
    "issue": "kill_participation",
    "evidence": ["Observed in 19 of 20 games"],
    "why_it_matters": (
        "This is a recurring pattern (Observed in 19 of 20 games), tracked across your full game "
        "history -- repeated patterns are the most reliable signal for what to prioritize."
    ),
    "practice_goal": "Before the next objective spawns, check whether you're positioned to contribute to the fight.",
    "scope": "recurring",
    "confidence": "high",
    "priority": 1,
}

# A this-game-only lesson (thin history, no recurring pattern confirmed yet).
THIS_GAME_LESSON = {
    "issue": "death_count",
    "evidence": ["This game: 9 deaths this game (value: 9)"],
    "why_it_matters": "Flagged as a concern in this game (9 deaths this game) -- not yet confirmed as a repeated pattern across multiple games.",
    "practice_goal": "Review each death this game and identify one point where retreating or repositioning earlier was possible.",
    "scope": "this_game",
    "confidence": "high",
    "priority": 2,
}


def test_adapt_item_recommendation_converts_correctly():
    result = adapt_item_recommendation(ITEM_ENTRY)

    assert result["system"] == "item"
    assert result["category"] == "enemy_has_fed_carry"  # first triggered rule
    assert result["subject"] == "Zhonya's Hourglass"
    assert result["recommendation"] == "Zhonya's Hourglass"
    assert result["reason"] == ITEM_ENTRY["reason"]
    assert result["evidence"] == ITEM_ENTRY["evidence"]
    assert result["confidence"] == "medium"
    assert result["confidence_score"] == 45
    assert result["severity"] == "medium"
    assert result["priority"] == 1
    assert result["source"] == "champion_knowledge"
    assert result["details"]["cost"] == 2600
    assert result["details"]["recommendation_type"] == "complete_item"
    assert result["details"]["conflicting_signal"] is True
    assert result["details"]["triggered_rules"] == ITEM_ENTRY["triggered_rules"]


def test_adapt_item_recommendation_handles_save_gold_entry():
    result = adapt_item_recommendation(SAVE_GOLD_ENTRY)

    assert result["subject"] == "save_gold"  # fallback label -- no item name to use
    assert result["recommendation"] is None  # genuinely nothing to buy, not fabricated
    assert result["confidence"] == "high"
    assert result["category"] == "uncategorized"  # no triggered_rules on this entry type
    assert result["details"]["recommendation_type"] == "save_gold"


def test_adapt_macro_lesson_converts_correctly():
    result = adapt_macro_lesson(RECURRING_LESSON)

    assert result["system"] == "macro"
    assert result["category"] == "recurring"
    assert result["subject"] == "kill_participation"
    assert result["recommendation"] == RECURRING_LESSON["practice_goal"]
    assert result["reason"] == RECURRING_LESSON["why_it_matters"]
    assert result["evidence"] == ["Observed in 19 of 20 games"]
    assert result["confidence"] == "high"
    assert result["confidence_score"] is None  # priorities.py never produces a numeric score
    assert result["severity"] == "high"
    assert result["priority"] == 1
    assert result["source"] == "macro_analysis"


def test_adapt_macro_lesson_this_game_scope():
    result = adapt_macro_lesson(THIS_GAME_LESSON)
    assert result["category"] == "this_game"
    assert result["subject"] == "death_count"


def test_adapted_item_recommendation_passes_validate_recommendation():
    assert validate_recommendation(adapt_item_recommendation(ITEM_ENTRY)) == []
    assert validate_recommendation(adapt_item_recommendation(SAVE_GOLD_ENTRY)) == []


def test_adapted_macro_lesson_passes_validate_recommendation():
    assert validate_recommendation(adapt_macro_lesson(RECURRING_LESSON)) == []
    assert validate_recommendation(adapt_macro_lesson(THIS_GAME_LESSON)) == []


def test_invalid_adapted_output_is_still_caught_by_validator():
    # proves validate_recommendation() is a real safety net, not just
    # something the adapters happen to satisfy -- corrupt a field the way a
    # future adapter bug plausibly could, and confirm it's caught.
    broken = adapt_item_recommendation(ITEM_ENTRY)
    broken["confidence"] = "extremely-sure"  # not a valid enum value
    errors = validate_recommendation(broken)
    assert any("confidence" in e for e in errors)

    broken2 = adapt_macro_lesson(RECURRING_LESSON)
    del broken2["severity"]
    errors2 = validate_recommendation(broken2)
    assert any("severity" in e for e in errors2)


def test_adapt_item_recommendation_does_not_mutate_input():
    original = copy.deepcopy(ITEM_ENTRY)
    adapt_item_recommendation(ITEM_ENTRY)
    assert ITEM_ENTRY == original


def test_adapt_macro_lesson_does_not_mutate_input():
    original = copy.deepcopy(RECURRING_LESSON)
    adapt_macro_lesson(RECURRING_LESSON)
    assert RECURRING_LESSON == original


if __name__ == "__main__":
    test_adapt_item_recommendation_converts_correctly()
    test_adapt_item_recommendation_handles_save_gold_entry()
    test_adapt_macro_lesson_converts_correctly()
    test_adapt_macro_lesson_this_game_scope()
    test_adapted_item_recommendation_passes_validate_recommendation()
    test_adapted_macro_lesson_passes_validate_recommendation()
    test_invalid_adapted_output_is_still_caught_by_validator()
    test_adapt_item_recommendation_does_not_mutate_input()
    test_adapt_macro_lesson_does_not_mutate_input()
    print("All checks passed.")
