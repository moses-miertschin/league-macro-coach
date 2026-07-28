"""Self-check for src/knowledge/champion_schema.py.

Run with: python -m tests.test_champion_schema
"""

from src.knowledge.champion_schema import REQUIRED_FIELDS, validate_champion_profile

VALID_PROFILE = {
    "champion": "Yone",
    "roles": ["middle", "top"],
    "damage_type": "hybrid",
    "scaling_profile": "scales_throughout",
    "strengths": ["Strong 1v1 duelist with a double-crit passive"],
    "weaknesses": ["Vulnerable to hard CC before he can use his ultimate"],
    "preferred_playstyle": "Aggressive skirmisher who looks for early trades and picks.",
    "common_counters": ["Malphite"],
    "favorable_matchups": ["Zed"],
    "synergy_champions": ["Nautilus"],
}


def test_valid_profile_passes():
    assert validate_champion_profile(VALID_PROFILE) == []


def test_each_required_field_missing_is_flagged():
    for field in REQUIRED_FIELDS:
        broken = dict(VALID_PROFILE)
        del broken[field]
        errors = validate_champion_profile(broken)
        assert any(field in e for e in errors), f"expected an error mentioning {field!r}, got {errors}"


def test_invalid_damage_type_is_flagged():
    broken = dict(VALID_PROFILE, damage_type="fire")
    errors = validate_champion_profile(broken)
    assert any("damage_type" in e for e in errors)


def test_invalid_scaling_profile_is_flagged():
    broken = dict(VALID_PROFILE, scaling_profile="instant")
    errors = validate_champion_profile(broken)
    assert any("scaling_profile" in e for e in errors)


def test_invalid_role_is_flagged():
    broken = dict(VALID_PROFILE, roles=["middle", "carry"])
    errors = validate_champion_profile(broken)
    assert any("roles" in e for e in errors)


def test_unknown_damage_type_and_scaling_profile_are_valid_not_rejected():
    # "unknown" is the honest-absence sentinel -- same convention
    # data/static/champion_damage_types.json already uses -- must be
    # accepted, never treated as an error.
    entry = dict(VALID_PROFILE, damage_type="unknown", scaling_profile="unknown")
    assert validate_champion_profile(entry) == []


def test_empty_lists_and_null_playstyle_are_valid_not_rejected():
    entry = dict(
        VALID_PROFILE,
        strengths=[], weaknesses=[], common_counters=[], favorable_matchups=[], synergy_champions=[],
        preferred_playstyle=None,
    )
    assert validate_champion_profile(entry) == []


def test_non_list_field_is_flagged():
    broken = dict(VALID_PROFILE, strengths="not a list")
    errors = validate_champion_profile(broken)
    assert any("strengths" in e for e in errors)


def test_empty_champion_name_is_flagged():
    broken = dict(VALID_PROFILE, champion="")
    errors = validate_champion_profile(broken)
    assert any("champion" in e for e in errors)


if __name__ == "__main__":
    test_valid_profile_passes()
    test_each_required_field_missing_is_flagged()
    test_invalid_damage_type_is_flagged()
    test_invalid_scaling_profile_is_flagged()
    test_invalid_role_is_flagged()
    test_unknown_damage_type_and_scaling_profile_are_valid_not_rejected()
    test_empty_lists_and_null_playstyle_are_valid_not_rejected()
    test_non_list_field_is_flagged()
    test_empty_champion_name_is_flagged()
    print("All checks passed.")
