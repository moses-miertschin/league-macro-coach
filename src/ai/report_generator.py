"""Turns rule-based player_insights.json + profile_summary.json into a
structured AI coaching report.

The AI layer only phrases already-computed findings -- see prompt_builder.py
for what context it's given and validator.py for how grounding is enforced.
No new facts are computed here; if there isn't enough game history yet, no
API call is made at all (see _empty_report below).
"""

import json
from pathlib import Path

from dotenv import load_dotenv

from src.ai import client
from src.ai.prompt_builder import build_prompt
from src.ai.validator import validate_grounding
from src.knowledge.loader import load_champion, load_role

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "generated_reports"
INSIGHTS_PATH = REPORTS_DIR / "player_insights.json"
PROFILE_SUMMARY_PATH = REPORTS_DIR / "profile_summary.json"
COACHING_REPORT_PATH = REPORTS_DIR / "coaching_report.json"
PHILOSOPHY_PATH = PROJECT_ROOT / "knowledge" / "coaching_philosophy.md"

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "priority_focus": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue": {"type": "string"},
                    "coaching_explanation": {"type": "string"},
                    "evidence": {"type": "string"},
                    "suggested_practice": {"type": "string"},
                },
                "required": ["issue", "coaching_explanation", "evidence", "suggested_practice"],
                "additionalProperties": False,
            },
        },
        "strengths_acknowledged": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["pattern", "note"],
                "additionalProperties": False,
            },
        },
        "confidence_caveats": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "priority_focus", "strengths_acknowledged", "confidence_caveats"],
    "additionalProperties": False,
}


def _empty_report() -> dict:
    return {
        "summary": "insufficient_data",
        "priority_focus": [],
        "strengths_acknowledged": [],
        "confidence_caveats": ["Not enough games recorded yet to generate coaching guidance."],
        "grounding_dropped": [],
    }


def generate_report(insights: dict, profile_summary: dict, generate_fn=client.generate) -> dict:
    if not insights.get("player_summary", {}).get("games_analyzed"):
        return _empty_report()

    champion_knowledge = load_champion(insights["player_summary"]["main_champion"])
    role_knowledge = load_role(insights["player_summary"]["main_role"])
    philosophy_text = PHILOSOPHY_PATH.read_text(encoding="utf-8")

    prompt = build_prompt(insights, profile_summary, champion_knowledge, role_knowledge, philosophy_text)
    raw = generate_fn(prompt, schema=REPORT_SCHEMA)
    report = json.loads(raw)
    return validate_grounding(report, insights)


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    with open(INSIGHTS_PATH, encoding="utf-8") as f:
        insights = json.load(f)
    with open(PROFILE_SUMMARY_PATH, encoding="utf-8") as f:
        profile_summary = json.load(f)

    report = generate_report(insights, profile_summary)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(COACHING_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Saved coaching report to {COACHING_REPORT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
