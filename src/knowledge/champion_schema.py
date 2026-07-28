"""Defines the shared champion knowledge shape that src/knowledge/champion_loader.py
produces and validates -- the structured record future draft recommendation,
matchup analysis, rune recommendation, and item recommendation systems will
all read from (see ROADMAP.md Sec.3-4, RECOMMENDATION_SYSTEM_DESIGN.md).
This phase only creates the shape and its validator -- no recommendation
logic reads this yet.

Same "returns error strings instead of raising" convention already
established by src/benchmark/benchmark_schema.py's validate_benchmark_entry()
and src/recommendations/schema.py's validate_recommendation().

"unknown" is the honest-absence value for damage_type/scaling_profile --
the same convention data/static/champion_damage_types.json already uses,
never guessed at, only filled in from real, hand-verified knowledge. Empty
lists are the honest-absence value for every list field. None is the
honest-absence value for preferred_playstyle, since it's prose, not a
category or a collection.
"""

REQUIRED_FIELDS = (
    "champion",
    "roles",
    "damage_type",
    "scaling_profile",
    "strengths",
    "weaknesses",
    "preferred_playstyle",
    "common_counters",
    "favorable_matchups",
    "synergy_champions",
)

# Matches Riot's own teamPosition vocabulary, the same one already used by
# game_state.py/loader.py -- avoids introducing a second role-naming scheme.
VALID_ROLES = {"top", "jungle", "middle", "bottom", "utility"}

# Matches data/static/champion_damage_types.json's existing vocabulary.
VALID_DAMAGE_TYPES = {"physical", "magic", "hybrid", "unknown"}

VALID_SCALING_PROFILES = {"early_game", "mid_game", "late_game", "scales_throughout", "unknown"}

_PLAIN_LIST_FIELDS = ("strengths", "weaknesses", "common_counters", "favorable_matchups", "synergy_champions")


def validate_champion_profile(entry: dict) -> list:
    """Returns a list of validation error strings; empty means valid."""
    errors = []

    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append(f"missing required field: '{field}'")

    if "champion" in entry and (not isinstance(entry["champion"], str) or not entry["champion"]):
        errors.append("'champion' must be a non-empty string")

    if "damage_type" in entry and entry["damage_type"] not in VALID_DAMAGE_TYPES:
        errors.append(f"invalid damage_type: '{entry['damage_type']}' (must be one of {sorted(VALID_DAMAGE_TYPES)})")

    if "scaling_profile" in entry and entry["scaling_profile"] not in VALID_SCALING_PROFILES:
        errors.append(
            f"invalid scaling_profile: '{entry['scaling_profile']}' (must be one of {sorted(VALID_SCALING_PROFILES)})"
        )

    if "roles" in entry:
        if not isinstance(entry["roles"], list):
            errors.append("'roles' must be a list")
        else:
            invalid_roles = [r for r in entry["roles"] if r not in VALID_ROLES]
            if invalid_roles:
                errors.append(f"invalid roles: {invalid_roles} (must be a subset of {sorted(VALID_ROLES)})")

    for field in _PLAIN_LIST_FIELDS:
        if field in entry and not isinstance(entry[field], list):
            errors.append(f"'{field}' must be a list")

    if "preferred_playstyle" in entry:
        playstyle = entry["preferred_playstyle"]
        if playstyle is not None and not isinstance(playstyle, str):
            errors.append("'preferred_playstyle' must be null or a string")

    return errors
