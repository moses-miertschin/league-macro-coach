"""Stage-1 adapters: pure, additive translations of existing recommendation
outputs into src/recommendations/schema.py's shared shape.

Per RECOMMENDATION_SYSTEM_DESIGN.md's two-stage migration plan, these are
translation-only. Neither src/analysis/item_recommender.py nor
src/coaching/priorities.py is imported, called, or modified here -- these
functions accept plain dicts matching those modules' existing output shapes
and return a new dict, never touching the input. Nothing in the existing
pipeline calls these yet; that wiring is a later, separate phase.

Both adapters read every input field with .get()/[] and only ever construct
a brand-new return dict -- they never assign into the input, so they cannot
mutate it.

Two fields both source systems conflate that the shared schema deliberately
keeps separate (confidence vs. severity -- see schema.py's docstring): since
neither item_recommender.py nor priorities.py currently computes an
independent impact/urgency score, both adapters reuse the same confidence
value for `severity` rather than inventing a new derivation. This is an
honestly-flagged simplification, not a hidden decision -- revisit only if
either source system starts computing severity independently.
"""


def adapt_item_recommendation(entry: dict) -> dict:
    """Converts one entry from item_recommender.recommend_items()'s
    "recommendations" list into the shared schema. Call once per entry, not
    on the whole recommend_items() result dict.
    """
    triggered_rules = entry.get("triggered_rules") or []
    category = triggered_rules[0] if triggered_rules else "uncategorized"

    return {
        "system": "item",
        "category": category,
        "subject": entry.get("item") or "save_gold",
        "recommendation": entry.get("item"),
        "reason": entry["reason"],
        "evidence": entry.get("evidence", []),
        "confidence": entry["confidence_tier"],
        "confidence_score": entry.get("confidence_score"),
        "severity": entry["confidence_tier"],
        "priority": entry["priority"],
        "source": entry["source"],
        "details": {
            "cost": entry.get("cost"),
            "builds_toward": entry.get("builds_toward"),
            "purchasable_now": entry.get("purchasable_now"),
            "recommendation_type": entry.get("recommendation_type"),
            "conflicting_signal": entry.get("conflicting_signal"),
            "confidence_breakdown": entry.get("confidence_breakdown", []),
            "triggered_rules": triggered_rules,
        },
    }


def adapt_macro_lesson(lesson: dict) -> dict:
    """Converts one lesson from coaching/priorities.select_priorities()'s
    output list into the shared schema. Call once per lesson.
    """
    return {
        "system": "macro",
        "category": lesson["scope"],
        "subject": lesson["issue"],
        "recommendation": lesson.get("practice_goal"),
        "reason": lesson["why_it_matters"],
        "evidence": lesson.get("evidence", []),
        "confidence": lesson["confidence"],
        "confidence_score": None,  # priorities.py never produces a numeric score
        "severity": lesson["confidence"],
        "priority": lesson["priority"],
        "source": "macro_analysis",
        "details": {},  # every field on a lesson already has a clean home above
    }
