"""Self-check for the AI coaching layer's grounding behavior.

Uses a fake generate_fn -- no network, no API key, no live Anthropic API.
Run with: python -m tests.test_ai_report_generator
"""

import json

from src.ai.report_generator import generate_report
from src.ai.validator import validate_grounding

INSIGHTS = {
    "player_summary": {"games_analyzed": 20, "main_champion": "Akali", "main_role": "MIDDLE"},
    "strengths": [
        {"pattern": "damage_to_objectives", "evidence": "Observed in 13 of 20 games", "confidence": "high"},
    ],
    "weaknesses": [
        {"pattern": "kill_participation", "evidence": "Observed in 19 of 20 games", "confidence": "high"},
        {"pattern": "objective_fight_presence", "evidence": "Observed in 19 of 20 games", "confidence": "high"},
    ],
    "priority_improvements": [
        {"issue": "kill_participation", "reason": "Observed in 19 of 20 games", "impact": "high"},
    ],
}

PROFILE_SUMMARY = {"weakness_patterns": [], "strength_patterns": [], "recent_trends": []}


def test_validator_drops_ungrounded_entries():
    report = {
        "summary": "test",
        "priority_focus": [
            {
                "issue": "kill_participation",  # real pattern -- kept
                "coaching_explanation": "x",
                "evidence": "Observed in 19 of 20 games",
                "suggested_practice": "y",
            },
            {
                "issue": "made_up_pattern",  # not in insights -- dropped
                "coaching_explanation": "x",
                "evidence": "fabricated",
                "suggested_practice": "y",
            },
        ],
        "strengths_acknowledged": [
            {"pattern": "damage_to_objectives", "note": "good"},  # real -- kept
            {"pattern": "invented_strength", "note": "bad"},  # not in insights -- dropped
        ],
        "confidence_caveats": [],
    }

    cleaned = validate_grounding(report, INSIGHTS)

    assert [p["issue"] for p in cleaned["priority_focus"]] == ["kill_participation"]
    assert [s["pattern"] for s in cleaned["strengths_acknowledged"]] == ["damage_to_objectives"]
    assert len(cleaned["grounding_dropped"]) == 2


def test_validator_caps_priority_focus_at_two():
    report = {
        "summary": "test",
        "priority_focus": [
            {"issue": "kill_participation", "coaching_explanation": "a", "evidence": "e", "suggested_practice": "p"},
            {"issue": "objective_fight_presence", "coaching_explanation": "a", "evidence": "e", "suggested_practice": "p"},
        ],
        "strengths_acknowledged": [],
        "confidence_caveats": [],
    }
    # both real patterns -- neither should be dropped for being ungrounded
    cleaned = validate_grounding(report, INSIGHTS)
    assert len(cleaned["priority_focus"]) == 2
    assert cleaned["grounding_dropped"] == []


def test_generate_report_insufficient_data_skips_api_call():
    calls = []

    def fake_generate(prompt, schema=None):
        calls.append(prompt)
        raise AssertionError("should not be called when games_analyzed is 0")

    empty_insights = {"player_summary": {"games_analyzed": 0}}
    report = generate_report(empty_insights, PROFILE_SUMMARY, generate_fn=fake_generate)

    assert calls == []
    assert report["summary"] == "insufficient_data"
    assert report["priority_focus"] == []


def test_generate_report_calls_model_and_grounds_output():
    fake_response = {
        "summary": "Solid CS, but you're missing objective fights.",
        "priority_focus": [
            {
                "issue": "objective_fight_presence",
                "coaching_explanation": "You're often not credited on dragon/baron takedowns.",
                "evidence": "Observed in 19 of 20 games",
                "suggested_practice": "Roam timing and shot-calling",
            },
            {
                "issue": "hallucinated_pattern_not_in_insights",
                "coaching_explanation": "x",
                "evidence": "fabricated stat",
                "suggested_practice": "y",
            },
        ],
        "strengths_acknowledged": [
            {"pattern": "damage_to_objectives", "note": "Consistently strong."},
        ],
        "confidence_caveats": [],
    }

    captured_prompts = []

    def fake_generate(prompt, schema=None):
        captured_prompts.append(prompt)
        assert schema is not None  # structured-output schema must be passed
        return json.dumps(fake_response)

    report = generate_report(INSIGHTS, PROFILE_SUMMARY, generate_fn=fake_generate)

    # the hallucinated pattern must not survive grounding
    assert [p["issue"] for p in report["priority_focus"]] == ["objective_fight_presence"]
    assert len(report["grounding_dropped"]) == 1
    assert report["grounding_dropped"][0]["issue"] == "hallucinated_pattern_not_in_insights"

    # prompt must carry the champion/role/philosophy context, not just raw insights
    prompt = captured_prompts[0]
    assert "Akali" in prompt
    assert "Macro over mechanics" in prompt  # from coaching_philosophy.md


if __name__ == "__main__":
    test_validator_drops_ungrounded_entries()
    test_validator_caps_priority_focus_at_two()
    test_generate_report_insufficient_data_skips_api_call()
    test_generate_report_calls_model_and_grounds_output()
    print("All checks passed.")
