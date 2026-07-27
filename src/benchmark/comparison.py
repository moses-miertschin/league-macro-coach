"""Compares player metrics against a benchmark entry's metrics.

Pure function over two plain dicts -- no knowledge of Riot data, GameSnapshot,
or where the benchmark came from. This is the same "engine independent of
data source" principle already used for src/analysis/item_recommender.py.

No AI, no invented numbers: a metric with no known comparison direction, or
missing from the player's own data, is reported as "unavailable" rather than
silently scored.
"""

from src.benchmark.benchmark_schema import METRIC_DIRECTIONS

# ponytail: gap-ratio thresholds are a guess at "how big a gap matters",
# same caveat as macro_analyzer.py's BENCHMARKS -- tune once there's real
# benchmark data to check this against.
SEVERITY_THRESHOLDS = {"low": 0.05, "medium": 0.15}


def _gap_ratio(player_value: float, benchmark_value: float, direction: str) -> float:
    diff = player_value - benchmark_value
    # positive raw_gap always means "player is worse than benchmark",
    # regardless of the metric's direction.
    raw_gap = diff if direction == "lower_is_better" else -diff

    if benchmark_value == 0:
        # ponytail: no natural denominator at zero -- treat any
        # worse-than-zero deviation as maximal severity rather than
        # dividing by zero or guessing a scale.
        return 0.0 if raw_gap <= 0 else 1.0

    return raw_gap / abs(benchmark_value)


def _severity(gap_ratio: float) -> str:
    if gap_ratio <= 0:
        return "none"
    if gap_ratio < SEVERITY_THRESHOLDS["low"]:
        return "low"
    if gap_ratio < SEVERITY_THRESHOLDS["medium"]:
        return "medium"
    return "high"


def compare_metric(metric_name: str, player_value, benchmark_value) -> dict:
    direction = METRIC_DIRECTIONS.get(metric_name)
    difference = round(player_value - benchmark_value, 4)

    if direction is None:
        return {
            "metric": metric_name,
            "player_value": player_value,
            "benchmark_value": benchmark_value,
            "difference": difference,
            "severity": "unavailable",
            "detail": f"No known comparison direction for '{metric_name}' -- add it to METRIC_DIRECTIONS in benchmark_schema.py.",
        }

    gap_ratio = _gap_ratio(player_value, benchmark_value, direction)
    return {
        "metric": metric_name,
        "player_value": player_value,
        "benchmark_value": benchmark_value,
        "difference": difference,
        "severity": _severity(gap_ratio),
    }


def compare_to_benchmark(player_metrics: dict, benchmark_entry: dict) -> list:
    results = []
    for metric_name, benchmark_value in benchmark_entry.get("metrics", {}).items():
        if metric_name not in player_metrics or player_metrics[metric_name] is None:
            results.append({
                "metric": metric_name,
                "player_value": None,
                "benchmark_value": benchmark_value,
                "difference": None,
                "severity": "unavailable",
                "detail": f"Player data has no value for '{metric_name}'.",
            })
            continue
        results.append(compare_metric(metric_name, player_metrics[metric_name], benchmark_value))
    return results
