"""Self-check for src/coaching/ -- coaching_report.py and priorities.py.

Uses fixture dicts and temp files -- no network, no API key, no dependency
on real match data. Run with: python -m tests.test_coaching_report
"""

import json
import tempfile
from pathlib import Path

from src.benchmark.storage import add_benchmark_entry
from src.coaching.coaching_report import build_coaching_session
from src.coaching.priorities import MAX_LESSONS, select_priorities

STRONG_INSIGHTS = {
    "player_summary": {"games_analyzed": 20, "main_champion": "Yone", "main_role": "MIDDLE"},
    "strengths": [{"pattern": "damage_to_objectives", "evidence": "Observed in 14 of 20 games", "confidence": "high"}],
    "weaknesses": [],
    "priority_improvements": [],
}
STRONG_MACRO_PATTERNS = {
    "match_id": "NA1_STRONG",
    "detected_patterns": [
        {"category": "deaths", "pattern": "death_count", "value": 2, "confidence": "high", "detail": "2 deaths this game", "concern": False, "tier": "normal"},
        {"category": "farming", "pattern": "cs_per_minute", "value": 9.0, "confidence": "high", "detail": "good", "concern": False, "tier": "good"},
    ],
}

WEAK_INSIGHTS = {
    "player_summary": {"games_analyzed": 20, "main_champion": "Akali", "main_role": "MIDDLE"},
    "strengths": [{"pattern": "damage_to_objectives", "evidence": "Observed in 13 of 20 games", "confidence": "high"}],
    "weaknesses": [
        {"pattern": "kill_participation", "evidence": "Observed in 19 of 20 games", "confidence": "high"},
        {"pattern": "death_count", "evidence": "Observed in 10 of 20 games", "confidence": "high"},
    ],
    "priority_improvements": [
        {"issue": "kill_participation", "reason": "Observed in 19 of 20 games", "impact": "high"},
        {"issue": "death_count", "reason": "Observed in 10 of 20 games", "impact": "high"},
        {"issue": "cs_per_minute", "reason": "Observed in 7 of 20 games", "impact": "medium"},
        {"issue": "gold_per_minute", "reason": "Observed in 7 of 20 games", "impact": "medium"},
    ],
}
WEAK_MACRO_PATTERNS = {
    "match_id": "NA1_WEAK",
    "detected_patterns": [
        {"category": "deaths", "pattern": "death_count", "value": 9, "confidence": "high", "detail": "9 deaths this game", "concern": True, "tier": "high"},
        {"category": "objectives", "pattern": "kill_participation", "value": 0.3, "confidence": "medium", "detail": "low", "concern": True, "tier": "low"},
        {"category": "vision", "pattern": "vision_score_per_minute", "value": 0.4, "confidence": "medium", "detail": "low", "concern": True, "tier": "low"},
    ],
}


def test_strong_game_produces_fewer_priorities():
    lessons = select_priorities(STRONG_INSIGHTS, STRONG_MACRO_PATTERNS)
    assert lessons == []


def test_weak_game_identifies_improvement_areas():
    lessons = select_priorities(WEAK_INSIGHTS, WEAK_MACRO_PATTERNS)
    assert len(lessons) == MAX_LESSONS  # capped even though 4 priority_improvements exist
    assert [l["issue"] for l in lessons] == ["kill_participation", "death_count", "cs_per_minute"]
    assert all(l["scope"] == "recurring" for l in lessons)
    assert [l["priority"] for l in lessons] == [1, 2, 3]


def test_single_game_patterns_fill_remaining_slots_when_history_is_thin():
    thin_insights = {
        "priority_improvements": [
            {"issue": "kill_participation", "reason": "Observed in 2 of 3 games", "impact": "low"},
        ],
    }
    lessons = select_priorities(thin_insights, WEAK_MACRO_PATTERNS)
    # 1 recurring + up to 2 single-game (death_count, vision_score_per_minute -- both concern=True, not excluded)
    assert lessons[0]["scope"] == "recurring"
    assert lessons[0]["issue"] == "kill_participation"
    assert all(l["scope"] == "this_game" for l in lessons[1:])
    assert len(lessons) == MAX_LESSONS


def test_no_fabricated_evidence():
    lessons = select_priorities(WEAK_INSIGHTS, WEAK_MACRO_PATTERNS)
    recurring = lessons[0]
    # evidence must be copied verbatim from the source "reason" string, not reworded
    assert recurring["evidence"] == ["Observed in 19 of 20 games"]

    thin_insights = {"priority_improvements": []}
    single_game_lessons = select_priorities(thin_insights, WEAK_MACRO_PATTERNS)
    for lesson in single_game_lessons:
        # every evidence string must contain the pattern's real detail and value verbatim
        source = next(p for p in WEAK_MACRO_PATTERNS["detected_patterns"] if p["pattern"] == lesson["issue"])
        assert source["detail"] in lesson["evidence"][0]
        assert str(source["value"]) in lesson["evidence"][0]


class _TempReports:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.reports_dir = Path(self._tmp.name)
        self.profile_path = self.reports_dir / "player_profile.json"
        self.benchmark_path = self.reports_dir / "benchmarks.json"  # not created until a test writes to it
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump({"riot_id": "HelloKittler#meow"}, f)
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()

    def write(self, name: str, data: dict) -> None:
        with open(self.reports_dir / name, "w", encoding="utf-8") as f:
            json.dump(data, f)


ANALYSIS = {"match_id": "NA1_TEST", "champion": "Akali", "role": "MID", "win": False, "vision_score": 8}
BENCHMARK_ENTRY = {
    "champion": "Akali",
    "role": "MID",
    "patch": "16.14",
    "rank": "challenger",
    # vision_score is deliberately not one of the macro-pattern-derived
    # issues in WEAK_MACRO_PATTERNS/WEAK_INSIGHTS, so a benchmark gap on it
    # can never be confused with a real recurring-pattern priority.
    "metrics": {"vision_score": 30},
}
ITEM_RECOMMENDATIONS = {
    "champion": "Akali",
    "player_state": {"current_items": ["Riftmaker"], "available_gold": 1200, "game_state": "behind"},
    "recommendations": [
        {"item": "Zhonya's Hourglass", "priority": 1, "reason": "Zhonya's Hourglass: Valuable when behind.", "confidence_score": 75},
    ],
    "unrecognized_items_flagged": [],
}


def test_full_session_combines_all_sources():
    with _TempReports() as tmp:
        tmp.write("NA1_TEST_analysis.json", ANALYSIS)
        tmp.write("NA1_TEST_macro_patterns.json", WEAK_MACRO_PATTERNS)
        tmp.write("NA1_TEST_item_recommendations.json", ITEM_RECOMMENDATIONS)
        tmp.write("player_insights.json", WEAK_INSIGHTS)

        session = build_coaching_session("NA1_TEST", reports_dir=tmp.reports_dir, profile_path=tmp.profile_path)

        assert session["player"] == "HelloKittler#meow"
        assert session["champion"] == "Akali"
        assert session["game_result"] == "Loss"
        assert len(session["main_lessons"]) == MAX_LESSONS
        assert session["item_review"]["status"] == "available"
        assert session["item_review"]["top_recommendations"][0]["item"] == "Zhonya's Hourglass"
        assert session["strengths"] == WEAK_INSIGHTS["strengths"]
        assert session["next_game_focus"] == [l["issue"] for l in session["main_lessons"]]


def test_missing_item_recommendations_stays_unavailable_not_fabricated():
    with _TempReports() as tmp:
        tmp.write("NA1_TEST_analysis.json", ANALYSIS)
        tmp.write("NA1_TEST_macro_patterns.json", WEAK_MACRO_PATTERNS)
        # no item_recommendations file written, and no player_insights.json either

        session = build_coaching_session("NA1_TEST", reports_dir=tmp.reports_dir, profile_path=tmp.profile_path)

        assert session["item_review"]["status"] == "unavailable"
        assert "not generated" in session["item_review"]["detail"]
        assert session["strengths"] == []  # no insights file -- stays empty, not invented
        # macro_patterns alone still surfaces this-game concerns rather than an empty report
        assert len(session["main_lessons"]) > 0
        assert all(l["scope"] == "this_game" for l in session["main_lessons"])


def test_benchmark_comparison_appears_in_coaching_output():
    with _TempReports() as tmp:
        tmp.write("NA1_TEST_analysis.json", ANALYSIS)
        tmp.write("NA1_TEST_macro_patterns.json", WEAK_MACRO_PATTERNS)
        tmp.write("player_insights.json", WEAK_INSIGHTS)
        add_benchmark_entry(BENCHMARK_ENTRY, path=tmp.benchmark_path)

        session = build_coaching_session(
            "NA1_TEST", reports_dir=tmp.reports_dir, profile_path=tmp.profile_path, benchmark_path=tmp.benchmark_path
        )

        assert session["benchmark"]["status"] == "available"
        vision = next(c for c in session["benchmark"]["comparisons"] if c["metric"] == "vision_score")
        assert vision["player_value"] == 8
        assert vision["benchmark_value"] == 30
        assert vision["severity"] == "high"
        assert "evidence" in vision


def test_missing_benchmark_data_remains_unavailable_in_full_session():
    with _TempReports() as tmp:
        tmp.write("NA1_TEST_analysis.json", ANALYSIS)
        tmp.write("NA1_TEST_macro_patterns.json", WEAK_MACRO_PATTERNS)
        tmp.write("player_insights.json", WEAK_INSIGHTS)
        # no benchmark entry ever added at tmp.benchmark_path

        session = build_coaching_session(
            "NA1_TEST", reports_dir=tmp.reports_dir, profile_path=tmp.profile_path, benchmark_path=tmp.benchmark_path
        )

        assert session["benchmark"]["status"] == "unavailable"
        assert session["benchmark"]["comparisons"] == []
        # the rest of the report must be unaffected by the missing benchmark
        assert len(session["main_lessons"]) == MAX_LESSONS


def test_benchmark_gaps_never_become_coaching_priorities():
    with _TempReports() as tmp:
        tmp.write("NA1_TEST_analysis.json", ANALYSIS)
        tmp.write("NA1_TEST_macro_patterns.json", WEAK_MACRO_PATTERNS)
        tmp.write("player_insights.json", WEAK_INSIGHTS)

        session_without_benchmark = build_coaching_session(
            "NA1_TEST", reports_dir=tmp.reports_dir, profile_path=tmp.profile_path, benchmark_path=tmp.benchmark_path
        )

        add_benchmark_entry(BENCHMARK_ENTRY, path=tmp.benchmark_path)
        session_with_benchmark = build_coaching_session(
            "NA1_TEST", reports_dir=tmp.reports_dir, profile_path=tmp.profile_path, benchmark_path=tmp.benchmark_path
        )

        # a real, high-severity benchmark gap exists (vision_score) -- it
        # must never leak into main_lessons/next_game_focus, which are only
        # ever derived from priorities.py's cross-game/this-game patterns.
        assert session_with_benchmark["main_lessons"] == session_without_benchmark["main_lessons"]
        assert session_with_benchmark["next_game_focus"] == session_without_benchmark["next_game_focus"]
        assert "vision_score" not in session_with_benchmark["next_game_focus"]
        assert all(l["issue"] != "vision_score" for l in session_with_benchmark["main_lessons"])


def test_missing_analysis_raises_rather_than_fabricating_a_report():
    with _TempReports() as tmp:
        try:
            build_coaching_session("NA1_DOES_NOT_EXIST", reports_dir=tmp.reports_dir, profile_path=tmp.profile_path)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected RuntimeError for a match with no structured analysis")


if __name__ == "__main__":
    test_strong_game_produces_fewer_priorities()
    test_weak_game_identifies_improvement_areas()
    test_single_game_patterns_fill_remaining_slots_when_history_is_thin()
    test_no_fabricated_evidence()
    test_full_session_combines_all_sources()
    test_missing_item_recommendations_stays_unavailable_not_fabricated()
    test_benchmark_comparison_appears_in_coaching_output()
    test_missing_benchmark_data_remains_unavailable_in_full_session()
    test_benchmark_gaps_never_become_coaching_priorities()
    test_missing_analysis_raises_rather_than_fabricating_a_report()
    print("All checks passed.")
