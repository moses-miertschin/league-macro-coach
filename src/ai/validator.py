"""Grounding check for the AI coaching layer's output.

The model is instructed to only reference patterns present in
player_insights.json, but an instruction is not a guarantee. This module
mechanically verifies that guarantee: any priority_focus/strengths_acknowledged
entry whose "issue"/"pattern" doesn't match a pattern actually present in the
source insights is dropped rather than shown, per the pipeline's existing
"mark it unavailable, never fabricate" rule -- extended here to mean "if we
can't verify the model's claim, don't ship it."
"""

MAX_PRIORITY_FOCUS = 2


def validate_grounding(report: dict, insights: dict) -> dict:
    known_weaknesses = {w["pattern"] for w in insights.get("weaknesses", [])}
    known_strengths = {s["pattern"] for s in insights.get("strengths", [])}

    dropped = []

    cleaned_focus = []
    for item in report.get("priority_focus", []):
        if item.get("issue") in known_weaknesses:
            cleaned_focus.append(item)
        else:
            dropped.append({"section": "priority_focus", "issue": item.get("issue")})

    cleaned_strengths = []
    for item in report.get("strengths_acknowledged", []):
        if item.get("pattern") in known_strengths:
            cleaned_strengths.append(item)
        else:
            dropped.append({"section": "strengths_acknowledged", "pattern": item.get("pattern")})

    return {
        **report,
        "priority_focus": cleaned_focus[:MAX_PRIORITY_FOCUS],
        "strengths_acknowledged": cleaned_strengths,
        "grounding_dropped": dropped,
    }
