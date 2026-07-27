"""Self-check for src/recommendations/schema.py.

No file I/O, no dependency on any recommendation-producing system -- these
are hand-built fixtures matching the shape each future/existing system is
expected to produce, per RECOMMENDATION_SYSTEM_DESIGN.md. Written before
schema.py's implementation. Run with: python -m tests.test_recommendation_schema
"""

from src.recommendations.schema import validate_recommendation

REQUIRED_FIELDS = (
    "system", "category", "subject", "recommendation", "reason", "evidence",
    "confidence", "confidence_score", "severity", "priority", "source", "details",
)


def _make_entry(**overrides) -> dict:
    entry = {
        "system": "item",
        "category": "core_build",
        "subject": "Zhonya's Hourglass",
        "recommendation": "Zhonya's Hourglass",
        "reason": "Zhonya's Hourglass: Valuable when behind.",
        "evidence": [{"fact": "enemy_has_fed_carry", "champions": ["Caitlyn"]}],
        "confidence": "high",
        "confidence_score": 75,
        "severity": "high",
        "priority": 1,
        "source": "champion_knowledge",
        "details": {"cost": 3250},
    }
    entry.update(overrides)
    return entry


def test_valid_entry_has_no_errors():
    assert validate_recommendation(_make_entry()) == []


def test_valid_entry_for_each_system():
    # proves the schema genuinely generalizes across all five systems named
    # in RECOMMENDATION_SYSTEM_DESIGN.md, not just the item system it was
    # first drafted against.
    fixtures = {
        "item": _make_entry(system="item", category="core_build", subject="Zhonya's Hourglass"),
        "draft": _make_entry(system="draft", category="ban", subject="Yasuo", recommendation="Ban", source="matchup_knowledge"),
        "rune": _make_entry(system="rune", category="keystone", subject="Electrocute", source="champion_knowledge"),
        "live": _make_entry(system="live", category="objective_timer", subject="dragon_spawn", recommendation="2:15", source="live_client_data"),
        "macro": _make_entry(system="macro", category="deaths", subject="death_count", recommendation=None, confidence_score=None, source="recurring_pattern"),
    }
    for system, entry in fixtures.items():
        errors = validate_recommendation(entry)
        assert errors == [], f"{system} fixture failed validation: {errors}"


def test_missing_required_fields_are_each_flagged():
    for field in REQUIRED_FIELDS:
        entry = _make_entry()
        del entry[field]
        errors = validate_recommendation(entry)
        assert any(field in e for e in errors), f"missing '{field}' was not flagged: {errors}"


def test_invalid_enum_values_are_flagged():
    assert any("system" in e for e in validate_recommendation(_make_entry(system="nonsense")))
    assert any("confidence" in e for e in validate_recommendation(_make_entry(confidence="super-sure")))
    assert any("severity" in e for e in validate_recommendation(_make_entry(severity="critical")))


def test_null_recommendation_with_unavailable_confidence_and_severity_is_valid():
    # explicitly allowed per RECOMMENDATION_SYSTEM_DESIGN.md: "unavailable" is
    # an accepted, expected state, never rejected as incomplete.
    entry = _make_entry(
        recommendation=None,
        confidence="unavailable",
        confidence_score=None,
        severity="unavailable",
    )
    assert validate_recommendation(entry) == []


def test_confidence_score_out_of_range_is_flagged():
    assert any("confidence_score" in e for e in validate_recommendation(_make_entry(confidence_score=150)))
    assert any("confidence_score" in e for e in validate_recommendation(_make_entry(confidence_score=-5)))


def test_confidence_score_null_is_valid_even_without_unavailable_confidence():
    # a system may simply not produce a numeric score (macro today doesn't) --
    # null is allowed regardless of the confidence tier.
    assert validate_recommendation(_make_entry(confidence_score=None)) == []


def test_priority_must_be_an_integer():
    assert any("priority" in e for e in validate_recommendation(_make_entry(priority="first")))


def test_evidence_must_be_a_list():
    assert any("evidence" in e for e in validate_recommendation(_make_entry(evidence="none")))


def test_details_bucket_is_open_to_arbitrary_domain_specific_keys():
    assert validate_recommendation(_make_entry(details={})) == []
    entry = _make_entry(details={"anything_goes": True, "cost": 100, "nested": {"a": 1}})
    assert validate_recommendation(entry) == []


def test_details_must_be_a_dict():
    assert any("details" in e for e in validate_recommendation(_make_entry(details="none")))


if __name__ == "__main__":
    test_valid_entry_has_no_errors()
    test_valid_entry_for_each_system()
    test_missing_required_fields_are_each_flagged()
    test_invalid_enum_values_are_flagged()
    test_null_recommendation_with_unavailable_confidence_and_severity_is_valid()
    test_confidence_score_out_of_range_is_flagged()
    test_confidence_score_null_is_valid_even_without_unavailable_confidence()
    test_priority_must_be_an_integer()
    test_evidence_must_be_a_list()
    test_details_bucket_is_open_to_arbitrary_domain_specific_keys()
    test_details_must_be_a_dict()
    print("All checks passed.")
