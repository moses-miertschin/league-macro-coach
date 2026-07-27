"""Self-check for src/benchmark/ -- schema, comparison, storage.

No network, no scraping, no real benchmark data -- every number here is a
synthetic fixture. Run with: python -m tests.test_benchmark
"""

import tempfile
from pathlib import Path

from src.benchmark.benchmark_schema import validate_benchmark_entry
from src.benchmark.comparison import compare_metric, compare_to_benchmark
from src.benchmark.storage import add_benchmark_entry, find_benchmarks, load_benchmarks

VALID_ENTRY = {
    "champion": "Akali",
    "role": "MID",
    "patch": "16.14",
    "rank": "challenger",
    "metrics": {"cs_10": 78, "gold_10": 4200, "deaths_before_10": 0.5},
}


# ---- benchmark_schema.py ----

def test_valid_entry_has_no_errors():
    assert validate_benchmark_entry(VALID_ENTRY) == []


def test_missing_required_field_is_flagged():
    entry = {k: v for k, v in VALID_ENTRY.items() if k != "patch"}
    errors = validate_benchmark_entry(entry)
    assert any("patch" in e for e in errors)


def test_non_numeric_metric_is_flagged():
    entry = {**VALID_ENTRY, "metrics": {"cs_10": "seventy-eight"}}
    errors = validate_benchmark_entry(entry)
    assert any("cs_10" in e and "numeric" in e for e in errors)


def test_empty_metrics_is_flagged():
    entry = {**VALID_ENTRY, "metrics": {}}
    errors = validate_benchmark_entry(entry)
    assert any("metrics" in e for e in errors)


# ---- comparison.py ----

def test_prompt_example_reproduces_exact_numbers():
    # the exact numbers from the task's own example
    result = compare_metric("cs_10", 62, 78)
    assert result["difference"] == -16
    assert result["severity"] == "high"


def test_lower_is_better_metric_direction():
    # deaths_before_10: player worse (more deaths) than benchmark
    result = compare_metric("deaths_before_10", 2, 0.5)
    assert result["difference"] == 1.5
    assert result["severity"] == "high"  # gap_ratio = 1.5 / 0.5 = 3.0


def test_player_meeting_or_exceeding_benchmark_is_severity_none():
    assert compare_metric("cs_10", 78, 78)["severity"] == "none"
    assert compare_metric("cs_10", 85, 78)["severity"] == "none"  # exceeds a higher-is-better metric
    assert compare_metric("deaths_before_10", 0.2, 0.5)["severity"] == "none"  # fewer deaths than benchmark


def test_severity_tiers_scale_with_gap_size():
    assert compare_metric("cs_10", 97, 100)["severity"] == "low"     # gap_ratio 0.03
    assert compare_metric("cs_10", 90, 100)["severity"] == "medium"  # gap_ratio 0.10
    assert compare_metric("cs_10", 70, 100)["severity"] == "high"    # gap_ratio 0.30


def test_unknown_metric_direction_is_unavailable_not_guessed():
    result = compare_metric("wards_placed_10", 3, 5)
    assert result["severity"] == "unavailable"
    assert "METRIC_DIRECTIONS" in result["detail"]
    assert result["difference"] == -2  # still an honest arithmetic fact, just not judged


def test_zero_benchmark_edge_case_does_not_crash():
    assert compare_metric("deaths_before_10", 0, 0)["severity"] == "none"
    assert compare_metric("deaths_before_10", 1, 0)["severity"] == "high"


def test_compare_to_benchmark_full_example():
    player_metrics = {"cs_10": 62, "gold_10": 3500, "deaths_before_10": 2}
    results = compare_to_benchmark(player_metrics, VALID_ENTRY)
    by_metric = {r["metric"]: r for r in results}

    assert by_metric["cs_10"]["difference"] == -16
    assert by_metric["cs_10"]["severity"] == "high"
    assert by_metric["gold_10"]["difference"] == -700
    assert by_metric["gold_10"]["severity"] == "high"
    assert by_metric["deaths_before_10"]["difference"] == 1.5
    assert by_metric["deaths_before_10"]["severity"] == "high"


def test_missing_player_metric_stays_unavailable_not_fabricated():
    player_metrics = {"cs_10": 62}  # gold_10 and deaths_before_10 not recorded
    results = compare_to_benchmark(player_metrics, VALID_ENTRY)
    by_metric = {r["metric"]: r for r in results}

    assert by_metric["gold_10"]["severity"] == "unavailable"
    assert by_metric["gold_10"]["player_value"] is None
    assert by_metric["deaths_before_10"]["severity"] == "unavailable"


# ---- storage.py ----

def test_load_benchmarks_missing_file_returns_empty_list():
    assert load_benchmarks(Path("does/not/exist.json")) == []


def test_add_benchmark_entry_rejects_invalid_entry():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "benchmarks.json"
        try:
            add_benchmark_entry({"champion": "Akali"}, path=path)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError for an invalid benchmark entry")
        assert not path.exists()  # nothing written on a rejected entry


def test_add_and_load_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "benchmarks.json"
        add_benchmark_entry(VALID_ENTRY, path=path)
        loaded = load_benchmarks(path)
        assert loaded == [VALID_ENTRY]


def test_add_benchmark_entry_upserts_by_champion_role_patch_rank():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "benchmarks.json"
        add_benchmark_entry(VALID_ENTRY, path=path)
        updated = {**VALID_ENTRY, "metrics": {"cs_10": 80, "gold_10": 4300, "deaths_before_10": 0.4}}
        add_benchmark_entry(updated, path=path)

        loaded = load_benchmarks(path)
        assert len(loaded) == 1
        assert loaded[0]["metrics"]["cs_10"] == 80


def test_find_benchmarks_filters_by_champion_role_patch_rank():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "benchmarks.json"
        add_benchmark_entry(VALID_ENTRY, path=path)
        add_benchmark_entry({**VALID_ENTRY, "patch": "16.13", "metrics": {"cs_10": 75}}, path=path)
        add_benchmark_entry({**VALID_ENTRY, "rank": "pro", "metrics": {"cs_10": 82}}, path=path)

        by_champion_role = find_benchmarks("akali", "mid", path=path)  # case-insensitive
        assert len(by_champion_role) == 3

        by_patch = find_benchmarks("Akali", "MID", patch="16.14", path=path)
        assert len(by_patch) == 2

        by_rank = find_benchmarks("Akali", "MID", rank="pro", path=path)
        assert len(by_rank) == 1
        assert by_rank[0]["metrics"]["cs_10"] == 82


def test_find_benchmarks_supports_extra_descriptor_filters():
    # forward-compatibility check: a future "matchup" field, never added to
    # benchmark_schema.py, must still be filterable without code changes.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "benchmarks.json"
        add_benchmark_entry({**VALID_ENTRY, "matchup": "Akali_vs_Zed"}, path=path)
        add_benchmark_entry({**VALID_ENTRY, "rank": "pro", "matchup": "Akali_vs_Yasuo"}, path=path)

        results = find_benchmarks("Akali", "MID", path=path, matchup="Akali_vs_Zed")
        assert len(results) == 1
        assert results[0]["matchup"] == "Akali_vs_Zed"


if __name__ == "__main__":
    test_valid_entry_has_no_errors()
    test_missing_required_field_is_flagged()
    test_non_numeric_metric_is_flagged()
    test_empty_metrics_is_flagged()
    test_prompt_example_reproduces_exact_numbers()
    test_lower_is_better_metric_direction()
    test_player_meeting_or_exceeding_benchmark_is_severity_none()
    test_severity_tiers_scale_with_gap_size()
    test_unknown_metric_direction_is_unavailable_not_guessed()
    test_zero_benchmark_edge_case_does_not_crash()
    test_compare_to_benchmark_full_example()
    test_missing_player_metric_stays_unavailable_not_fabricated()
    test_load_benchmarks_missing_file_returns_empty_list()
    test_add_benchmark_entry_rejects_invalid_entry()
    test_add_and_load_round_trip()
    test_add_benchmark_entry_upserts_by_champion_role_patch_rank()
    test_find_benchmarks_filters_by_champion_role_patch_rank()
    test_find_benchmarks_supports_extra_descriptor_filters()
    print("All checks passed.")
