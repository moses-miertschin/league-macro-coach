"""Defines the shared recommendation contract every decision system will
eventually produce -- item, draft, rune, live, and macro. See
RECOMMENDATION_SYSTEM_DESIGN.md for the full design rationale.

This phase only creates the shape and its validator. Nothing in this repo
produces this shape yet: item_recommender.py's recommend_items() and
coaching/priorities.py's lessons are untouched, and no adapter exists yet
either (that is a later, separate phase per the design doc).

A recommendation entry is a plain dict with two axes deliberately kept
separate, matching ARCHITECTURE_AUDIT.md Finding C's call to unify the
project's three previously-incompatible confidence vocabularies:

    confidence -- data-quality axis: how sure are we this claim is true
    severity   -- impact/urgency axis: how much should the player care

"unavailable" is a first-class, expected value for confidence/severity
(paired with recommendation: null) -- it must never be rejected as
incomplete, and a system must never fabricate a value to avoid it.

Required keys (REQUIRED_FIELDS): every one of these must be present, even
though `recommendation` and `confidence_score` are allowed to be null.
Everything domain-specific that doesn't generalize across all five systems
belongs in `details`, which stays permissive of arbitrary extra keys, the
same precedent already established for benchmark entries in
src/benchmark/benchmark_schema.py.
"""

REQUIRED_FIELDS = (
    "system",
    "category",
    "subject",
    "recommendation",
    "reason",
    "evidence",
    "confidence",
    "confidence_score",
    "severity",
    "priority",
    "source",
    "details",
)

VALID_SYSTEMS = {"item", "draft", "rune", "live", "macro"}
VALID_CONFIDENCE_LEVELS = {"high", "medium", "low", "unavailable"}
VALID_SEVERITY_LEVELS = {"high", "medium", "low", "unavailable"}


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_recommendation(entry: dict) -> list:
    """Returns a list of validation error strings; empty means valid.

    Returns errors rather than raising, so a future batch of entries from
    several systems can be validated all at once and reported together --
    same convention as src/benchmark/benchmark_schema.py's
    validate_benchmark_entry().
    """
    errors = []

    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append(f"missing required field: '{field}'")

    if "system" in entry and entry["system"] not in VALID_SYSTEMS:
        errors.append(f"invalid system: '{entry['system']}' (must be one of {sorted(VALID_SYSTEMS)})")

    if "confidence" in entry and entry["confidence"] not in VALID_CONFIDENCE_LEVELS:
        errors.append(f"invalid confidence: '{entry['confidence']}' (must be one of {sorted(VALID_CONFIDENCE_LEVELS)})")

    if "severity" in entry and entry["severity"] not in VALID_SEVERITY_LEVELS:
        errors.append(f"invalid severity: '{entry['severity']}' (must be one of {sorted(VALID_SEVERITY_LEVELS)})")

    if "category" in entry and not isinstance(entry["category"], str):
        errors.append("'category' must be a string")

    if "subject" in entry and not isinstance(entry["subject"], str):
        errors.append("'subject' must be a string")

    if "reason" in entry and not isinstance(entry["reason"], str):
        errors.append("'reason' must be a string")

    if "source" in entry and not isinstance(entry["source"], str):
        errors.append("'source' must be a string")

    if "recommendation" in entry and entry["recommendation"] is not None and not isinstance(entry["recommendation"], str):
        errors.append("'recommendation' must be null or a string")

    if "confidence_score" in entry:
        score = entry["confidence_score"]
        if score is not None and (not _is_number(score) or not (0 <= score <= 100)):
            errors.append("'confidence_score' must be null or a number between 0 and 100")

    if "priority" in entry and (not isinstance(entry["priority"], int) or isinstance(entry["priority"], bool)):
        errors.append("'priority' must be an integer")

    if "evidence" in entry and not isinstance(entry["evidence"], list):
        errors.append("'evidence' must be a list")

    if "details" in entry and not isinstance(entry["details"], dict):
        errors.append("'details' must be a dict")

    return errors
