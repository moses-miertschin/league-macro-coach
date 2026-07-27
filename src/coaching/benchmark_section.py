"""Builds coaching_session.json's "benchmark" section from existing stored
benchmark data (src/benchmark/storage.py) and the current match's
already-computed analysis + macro pattern output.

Informational only, by design: this module never turns a benchmark gap
into a coaching priority or a recommendation. src/coaching/priorities.py
(main_lessons/next_game_focus) never imports this module and never reads
its output -- a benchmark comparison is a fact for the player to read, not
a new decision the system makes.

Every value in the output traces back to something that already exists:
player metric values come verbatim from analysis.json/macro_patterns.json
(no new derivation), benchmark values come verbatim from a stored
src/benchmark entry, and all comparison math is src/benchmark/comparison.py's
already-tested logic, untouched here.

Metric-name limitation, stated plainly rather than worked around: only
whole-game metrics that already exist are supplied here (cs_per_minute,
gold_per_minute, kill_participation, damage_to_objectives, vision_score,
death_count). Minute-10-specific metrics like "cs_10" would require parsing
raw timeline participantFrames, which src/analysis/timeline_analyzer.py does
not currently do and is not modified here. A benchmark entry keyed that way
will honestly report "unavailable" through comparison.py's existing
missing-metric path -- not a bug, the correct behavior for a metric that
genuinely isn't computable yet.
"""

from pathlib import Path

from src.benchmark.comparison import compare_to_benchmark
from src.benchmark.storage import BENCHMARK_DATA_PATH, find_benchmarks


def _player_metrics(analysis: dict, macro_patterns: dict | None) -> dict:
    metrics = {
        "cs_per_minute": analysis.get("cs_per_minute"),
        "vision_score": analysis.get("vision_score"),
        "kill_participation": analysis.get("objectives_participation", {}).get("kill_participation"),
        "damage_to_objectives": analysis.get("objectives_participation", {}).get("damage_to_objectives"),
        "death_count": analysis.get("kda", {}).get("deaths"),
    }
    if macro_patterns:
        for p in macro_patterns.get("detected_patterns", []):
            if p["pattern"] == "gold_per_minute":
                metrics["gold_per_minute"] = p["value"]
    return {k: v for k, v in metrics.items() if v is not None}


def _evidence(comparison: dict, benchmark_entry: dict) -> str:
    rank = benchmark_entry.get("rank", "unknown")
    patch = benchmark_entry.get("patch", "unknown")
    return f"You: {comparison['player_value']} vs {rank} benchmark (patch {patch}): {comparison['benchmark_value']}"


def build_benchmark_section(
    analysis: dict,
    macro_patterns: dict | None,
    benchmark_path: Path = BENCHMARK_DATA_PATH,
) -> dict:
    champion = analysis.get("champion")
    role = analysis.get("role")
    if not champion or not role:
        return {
            "status": "unavailable",
            "detail": "Champion or role missing from match analysis.",
            "comparisons": [],
        }

    matches = find_benchmarks(champion, role, path=benchmark_path)
    if not matches:
        return {
            "status": "unavailable",
            "detail": f"No benchmark data has been added yet for {champion} ({role}).",
            "comparisons": [],
        }

    # ponytail: takes the first stored match when several exist (e.g. more
    # than one rank/source for the same champion+role) -- no patch tracking
    # exists on the player's side yet to disambiguate further. Revisit once
    # a real second source actually creates this ambiguity.
    benchmark_entry = matches[0]
    player_metrics = _player_metrics(analysis, macro_patterns)
    comparisons = compare_to_benchmark(player_metrics, benchmark_entry)

    for c in comparisons:
        if c["severity"] != "unavailable":
            c["evidence"] = _evidence(c, benchmark_entry)
        else:
            c["evidence"] = c.get("detail", "No comparison data available for this metric.")

    return {
        "status": "available",
        "benchmark_source": {"rank": benchmark_entry.get("rank"), "patch": benchmark_entry.get("patch")},
        "comparisons": comparisons,
    }
