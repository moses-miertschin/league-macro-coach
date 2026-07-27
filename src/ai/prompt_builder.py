"""Assembles the grounded context sent to the AI coaching layer.

Only already-computed rule-based findings (player_insights.json,
profile_summary.json) and qualitative knowledge-base text go into the
prompt -- no raw match data, and no instruction to draw on general League
knowledge beyond what's provided here. The model's job is to phrase
already-verified findings, never to decide what the findings are.
"""

import json

INSTRUCTIONS = """You are writing a League of Legends coaching report for one player.

Rules -- follow all of them:
1. Only reference weaknesses/strengths that appear in the "insights" data below, by their exact "pattern" name. Do not invent a weakness or strength that isn't listed.
2. Do not draw on general League of Legends knowledge beyond the "champion_knowledge", "role_knowledge", and "philosophy" sections below. If those sections don't mention something, don't invent guidance for it.
3. Surface at most 2 items in "priority_focus" -- the philosophy calls for a few goals, not a checklist.
4. Every "evidence" field must be copied from the matching insights entry's "evidence" string, not reworded or re-derived.
5. If a pattern's confidence is "low", say so in the coaching_explanation rather than sounding certain.
6. Do not mention games, patterns, or stats that aren't present in the data below.
"""


def build_prompt(
    insights: dict,
    profile_summary: dict,
    champion_knowledge: dict | None,
    role_knowledge: dict | None,
    philosophy_text: str,
) -> str:
    context = {
        "insights": insights,
        "profile_summary_evidence": {
            "weakness_patterns": profile_summary.get("weakness_patterns", []),
            "strength_patterns": profile_summary.get("strength_patterns", []),
            "recent_trends": profile_summary.get("recent_trends", []),
        },
        "champion_knowledge": champion_knowledge,
        "role_knowledge": role_knowledge,
    }
    return (
        INSTRUCTIONS
        + "\nphilosophy:\n"
        + philosophy_text
        + "\n\ndata:\n"
        + json.dumps(context, indent=2)
    )
