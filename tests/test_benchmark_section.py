"""Self-check for src/coaching/benchmark_section.py.

Written before the module's implementation, per instruction to add tests
before modifying production behavior. Uses only synthetic fixtures and a
temp benchmark-storage path -- no network, no real benchmark data.
Run with: python -m tests.test_benchmark_section
"""

import tempfile
from pathlib import Path

from src.benchmark.storage import add_benchmark_entry
from src.coaching.benchmark_section import build_benchmark_section

ANALYSIS = {
    "champion": "Akali",
    "role": "MID",
    "cs_per_minute": 6.2,
    "vision_score": 22,
    "kda": {"kills": 3, "deaths": 5, "assists": 4},
    "objectives_participation": {"kill_participation": 0.45, "damage_to_objectives": 1200},
}
MACRO_PATTERNS = {
    "detected_patterns": [
        {"category": "farming", "pattern": "gold_per_minute", "value": 320, "confidence": "high", "detail": "low", "concern": True, "tier": "low"},
    ],
}
BENCHMARK_ENTRY = {
    "champion": "Akali",
    "role": "MID",
    "patch": "16.14",
    "rank": "challenger",
    "metrics": {"cs_per_minute": 8.5, "vision_score": 15, "gold_per_minute": 420},
}


def test_benchmark_section_available_when_data_exists():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "benchmarks.json"
        add_benchmark_entry(BENCHMARK_ENTRY, path=path)

        section = build_benchmark_section(ANALYSIS, MACRO_PATTERNS, benchmark_path=path)

        assert section["status"] == "available"
        assert section["benchmark_source"] == {"rank": "challenger", "patch": "16.14"}
        by_metric = {c["metric"]: c for c in section["comparisons"]}

        # cs_per_minute: player below a higher-is-better benchmark
        assert by_metric["cs_per_minute"]["severity"] == "high"
        assert by_metric["cs_per_minute"]["player_value"] == 6.2
        assert by_metric["cs_per_minute"]["benchmark_value"] == 8.5

        # vision_score: player exceeds a higher-is-better benchmark -> no gap
        assert by_metric["vision_score"]["severity"] == "none"

        # gold_per_minute: sourced from macro_patterns, not analysis directly
        assert by_metric["gold_per_minute"]["player_value"] == 320
        assert by_metric["gold_per_minute"]["severity"] == "high"

        # every non-unavailable comparison must carry evidence
        assert all("evidence" in c for c in section["comparisons"])


def test_missing_benchmark_data_stays_unavailable():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "benchmarks.json"  # never written to -- no data added

        section = build_benchmark_section(ANALYSIS, MACRO_PATTERNS, benchmark_path=path)

        assert section["status"] == "unavailable"
        assert section["comparisons"] == []
        assert "Akali" in section["detail"]


def test_champion_or_role_missing_from_analysis_stays_unavailable():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "benchmarks.json"
        add_benchmark_entry(BENCHMARK_ENTRY, path=path)

        incomplete_analysis = {"champion": "Akali"}  # no role
        section = build_benchmark_section(incomplete_analysis, None, benchmark_path=path)

        assert section["status"] == "unavailable"
        assert section["comparisons"] == []


def test_no_fabricated_comparisons_every_value_traces_to_source():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "benchmarks.json"
        add_benchmark_entry(BENCHMARK_ENTRY, path=path)

        section = build_benchmark_section(ANALYSIS, MACRO_PATTERNS, benchmark_path=path)
        by_metric = {c["metric"]: c for c in section["comparisons"]}

        cs = by_metric["cs_per_minute"]
        # player_value must equal the literal analysis field, never derived/rounded/guessed
        assert cs["player_value"] == ANALYSIS["cs_per_minute"]
        assert cs["benchmark_value"] == BENCHMARK_ENTRY["metrics"]["cs_per_minute"]
        # evidence must literally contain both real numbers, not a paraphrase
        assert str(cs["player_value"]) in cs["evidence"]
        assert str(cs["benchmark_value"]) in cs["evidence"]
        assert "challenger" in cs["evidence"]


def test_metric_not_computable_from_existing_data_is_unavailable_not_guessed():
    # a benchmark entry keyed by a minute-10-specific metric this pass
    # cannot supply -- must degrade honestly, never invent a player value.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "benchmarks.json"
        entry = {**BENCHMARK_ENTRY, "metrics": {"cs_10": 78}}
        add_benchmark_entry(entry, path=path)

        section = build_benchmark_section(ANALYSIS, MACRO_PATTERNS, benchmark_path=path)

        assert section["status"] == "available"  # a benchmark exists, even if this metric can't be judged
        cs_10 = section["comparisons"][0]
        assert cs_10["metric"] == "cs_10"
        assert cs_10["severity"] == "unavailable"
        assert cs_10["player_value"] is None


if __name__ == "__main__":
    test_benchmark_section_available_when_data_exists()
    test_missing_benchmark_data_stays_unavailable()
    test_champion_or_role_missing_from_analysis_stays_unavailable()
    test_no_fabricated_comparisons_every_value_traces_to_source()
    test_metric_not_computable_from_existing_data_is_unavailable_not_guessed()
    print("All checks passed.")
