"""Defines the shape of benchmark data -- not any actual benchmark numbers.

No scraping, no AI, no fabricated statistics live here or anywhere in
src/benchmark/. This module only defines what a valid benchmark entry looks
like and how to validate one, so that whatever future data source produces
real numbers (see the source sketches below) has one common contract to
satisfy before src/benchmark/storage.py will accept it.

A benchmark entry is a plain dict:

    {
        "champion": "Akali",
        "role": "MID",
        "patch": "16.14",
        "rank": "challenger",
        "metrics": {"cs_10": 78, "gold_10": 4200, "deaths_before_10": 0.5},
    }

Required keys: champion, role, patch, rank, metrics. Anything else
(e.g. a future "matchup" or "sample_size" key) is allowed but not required
-- the schema stays permissive of new descriptor fields so a future data
source doesn't need this file changed just to add one, only to add a new
metric (see METRIC_DIRECTIONS below).

Future data sources this is designed to support, none of them built yet:

- Challenger ranked games  -- rank="challenger", one entry per champion/role/patch
- Pro games                -- rank="pro" (or a league identifier), same shape
- Patch-specific data      -- distinguished by "patch", nothing else needed
- Matchup-specific data    -- an additional descriptor key (e.g. "matchup":
  "Akali_vs_Zed") on top of the required fields; storage.py's query
  function accepts arbitrary extra filters for exactly this reason
"""

REQUIRED_FIELDS = ("champion", "role", "patch", "rank", "metrics")

# ponytail: seeded with the three metrics this phase was asked to support.
# Adding a new metric means adding one entry here -- the same kind of
# code-level scaling ceiling already documented for item_recommender.py's
# TRIGGER_KEYWORDS in ARCHITECTURE_AUDIT.md Finding E. Direction determines
# how comparison.py interprets a gap: "higher_is_better" metrics are bad
# when the player is below benchmark, "lower_is_better" metrics are bad
# when the player is above it.
METRIC_DIRECTIONS = {
    "cs_10": "higher_is_better",
    "gold_10": "higher_is_better",
    "deaths_before_10": "lower_is_better",
    # whole-game metrics -- the only ones src/coaching/benchmark_section.py
    # can actually supply today (see that module's docstring for why
    # minute-10-specific metrics above aren't computable yet).
    "cs_per_minute": "higher_is_better",
    "gold_per_minute": "higher_is_better",
    "kill_participation": "higher_is_better",
    "damage_to_objectives": "higher_is_better",
    "vision_score": "higher_is_better",
    "death_count": "lower_is_better",
}


def validate_benchmark_entry(entry: dict) -> list:
    """Returns a list of validation error strings; empty means valid.

    Deliberately returns errors rather than raising, so a future importer
    can validate a batch of scraped/entered records and report every
    problem at once instead of stopping at the first one.
    """
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append(f"missing required field: '{field}'")

    metrics = entry.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, dict) or not metrics:
            errors.append("'metrics' must be a non-empty dict")
        else:
            for name, value in metrics.items():
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(f"metric '{name}' must be numeric, got {type(value).__name__}")

    return errors
