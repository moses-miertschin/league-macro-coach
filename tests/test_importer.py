"""Self-check for src/history/importer.py's dedup/import/failure logic.

Uses fake get_match_fn callables and temp directories — no network, no API
key, no live Riot API. Run with: python -m tests.test_importer
"""

import json
import tempfile
from pathlib import Path

from src.history import store
from src.history.importer import enrich_existing_timelines, import_matches

GAME_NAME, TAG_LINE = "HelloKittler", "meow"


def _make_match(match_id: str, kills: int) -> dict:
    return {
        "metadata": {"matchId": match_id},
        "info": {
            "gameDuration": 1800,
            "gameStartTimestamp": 1700000000000,
            "participants": [
                {
                    "riotIdGameName": GAME_NAME,
                    "riotIdTagline": TAG_LINE,
                    "championName": "Syndra",
                    "teamPosition": "MIDDLE",
                    "teamId": 100,
                    "participantId": 1,
                    "win": True,
                    "kills": kills,
                    "deaths": 2,
                    "assists": 8,
                    "totalMinionsKilled": 150,
                    "neutralMinionsKilled": 10,
                    "goldEarned": 12000,
                    "totalDamageDealtToChampions": 20000,
                    "damageDealtToObjectives": 3000,
                    "visionScore": 25,
                    "challenges": {"killParticipation": 0.65},
                }
            ],
        },
    }


def _make_timeline(match_id: str, participant_id: int = 1) -> dict:
    return {
        "metadata": {"matchId": match_id},
        "info": {
            "frames": [
                {
                    "timestamp": 0,
                    "events": [
                        {"type": "CHAMPION_KILL", "timestamp": 100000, "killerId": 2, "victimId": participant_id, "assistingParticipantIds": []},
                        {"type": "ELITE_MONSTER_KILL", "timestamp": 130000, "killerId": 2, "monsterType": "DRAGON", "assistingParticipantIds": []},
                    ],
                }
            ],
        },
    }


class _TempPipeline:
    """Isolated raw/reports/history/timeline paths so tests never touch real project data."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.raw_dir = root / "raw_matches"
        self.reports_dir = root / "reports"
        self.history_path = root / "database" / "game_history.json"
        self.timelines_dir = root / "raw_matches" / "timelines"
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()


def test_duplicate_match_handling():
    with _TempPipeline() as pipeline:
        existing_analysis = {
            "match_id": "NA1_EXISTING",
            "game_start_timestamp": 1,
            "champion": "Syndra",
            "role": "MIDDLE",
            "win": True,
            "kda": {"kills": 5, "deaths": 1, "assists": 5},
            "cs_per_minute": 8.0,
            "damage_to_champions": 15000,
            "objectives_participation": {"kill_participation": 0.6, "damage_to_objectives": 2000},
            "vision_score": 20,
            "game_duration_seconds": 1800,
        }
        existing_macro = {"match_id": "NA1_EXISTING", "detected_patterns": []}
        store.record_game(existing_analysis, existing_macro, path=pipeline.history_path)

        calls = []

        def get_match_fn(match_id):
            calls.append(match_id)
            return _make_match(match_id, kills=7)

        result = import_matches(
            ["NA1_EXISTING", "NA1_NEW"],
            get_match_fn,
            GAME_NAME,
            TAG_LINE,
            raw_matches_dir=pipeline.raw_dir,
            reports_dir=pipeline.reports_dir,
            history_path=pipeline.history_path,
        )

        assert result["skipped_existing"] == ["NA1_EXISTING"]
        assert result["imported"] == ["NA1_NEW"]
        assert calls == ["NA1_NEW"]  # the API was never called for the already-stored match


def test_multiple_match_import():
    with _TempPipeline() as pipeline:
        match_ids = ["NA1_A", "NA1_B", "NA1_C"]

        def get_match_fn(match_id):
            return _make_match(match_id, kills=match_ids.index(match_id) + 1)

        result = import_matches(
            match_ids,
            get_match_fn,
            GAME_NAME,
            TAG_LINE,
            raw_matches_dir=pipeline.raw_dir,
            reports_dir=pipeline.reports_dir,
            history_path=pipeline.history_path,
        )

        assert result["imported"] == match_ids
        assert result["failed"] == []

        for match_id in match_ids:
            assert (pipeline.raw_dir / f"{match_id}.json").exists()
            assert (pipeline.reports_dir / f"{match_id}_analysis.json").exists()
            assert (pipeline.reports_dir / f"{match_id}_macro_patterns.json").exists()

        history = store.load_history(pipeline.history_path)
        assert {g["match_id"] for g in history} == set(match_ids)


def test_failed_api_response_handling():
    with _TempPipeline() as pipeline:
        def get_match_fn(match_id):
            if match_id == "NA1_BROKEN":
                raise RuntimeError("401 Client Error: Unauthorized")
            return _make_match(match_id, kills=3)

        result = import_matches(
            ["NA1_BROKEN", "NA1_OK"],
            get_match_fn,
            GAME_NAME,
            TAG_LINE,
            raw_matches_dir=pipeline.raw_dir,
            reports_dir=pipeline.reports_dir,
            history_path=pipeline.history_path,
        )

        assert result["imported"] == ["NA1_OK"]
        assert len(result["failed"]) == 1
        assert result["failed"][0]["match_id"] == "NA1_BROKEN"
        assert "401" in result["failed"][0]["error"]

        # the failed match must not have been partially written or stored
        assert not (pipeline.raw_dir / "NA1_BROKEN.json").exists()
        history = store.load_history(pipeline.history_path)
        assert {g["match_id"] for g in history} == {"NA1_OK"}


def test_timeline_is_fetched_saved_and_used():
    with _TempPipeline() as pipeline:
        def get_match_fn(match_id):
            return _make_match(match_id, kills=5)

        def get_timeline_fn(match_id):
            return _make_timeline(match_id)

        result = import_matches(
            ["NA1_WITH_TIMELINE"],
            get_match_fn,
            GAME_NAME,
            TAG_LINE,
            raw_matches_dir=pipeline.raw_dir,
            reports_dir=pipeline.reports_dir,
            history_path=pipeline.history_path,
            timelines_dir=pipeline.timelines_dir,
            get_timeline_fn=get_timeline_fn,
        )

        assert result["imported"] == ["NA1_WITH_TIMELINE"]
        assert result["timeline_unavailable"] == []

        timeline_path = pipeline.timelines_dir / "NA1_WITH_TIMELINE_timeline.json"
        assert timeline_path.exists()

        with open(pipeline.reports_dir / "NA1_WITH_TIMELINE_macro_patterns.json", encoding="utf-8") as f:
            macro_result = json.load(f)

        deaths_before = next(
            p for p in macro_result["detected_patterns"] if p["pattern"] == "deaths_before_objectives"
        )
        # proves the timeline was actually parsed and used, not just fetched
        assert deaths_before["confidence"] == "high"
        assert deaths_before["value"] == 1


def test_timeline_failure_does_not_fail_match_import():
    with _TempPipeline() as pipeline:
        def get_match_fn(match_id):
            return _make_match(match_id, kills=5)

        def get_timeline_fn(match_id):
            raise RuntimeError("timeline not available for this match")

        result = import_matches(
            ["NA1_NO_TIMELINE"],
            get_match_fn,
            GAME_NAME,
            TAG_LINE,
            raw_matches_dir=pipeline.raw_dir,
            reports_dir=pipeline.reports_dir,
            history_path=pipeline.history_path,
            timelines_dir=pipeline.timelines_dir,
            get_timeline_fn=get_timeline_fn,
        )

        # the match itself still imports successfully — only the optional
        # timeline enrichment failed, which is expected/normal per Riot
        assert result["imported"] == ["NA1_NO_TIMELINE"]
        assert result["failed"] == []
        assert result["timeline_unavailable"] == ["NA1_NO_TIMELINE"]

        with open(pipeline.reports_dir / "NA1_NO_TIMELINE_macro_patterns.json", encoding="utf-8") as f:
            macro_result = json.load(f)

        deaths_before = next(
            p for p in macro_result["detected_patterns"] if p["pattern"] == "deaths_before_objectives"
        )
        assert deaths_before["confidence"] == "unavailable"


def test_enrich_existing_timelines_backfills_already_imported_match():
    with _TempPipeline() as pipeline:
        # simulate a match imported before timeline support existed: an
        # analysis file on disk (with participant_id, as analyzer.py now
        # produces) but no timeline and an "unavailable" macro result.
        analysis = {
            "match_id": "NA1_OLD",
            "game_start_timestamp": 1,
            "participant_id": 1,
            "champion": "Syndra",
            "role": "MIDDLE",
            "win": True,
            "kda": {"kills": 5, "deaths": 2, "assists": 5},
            "cs_per_minute": 8.0,
            "gold_earned": 12000,
            "damage_to_champions": 15000,
            "damage_share": 0.3,
            "objectives_participation": {"kill_participation": 0.6, "damage_to_objectives": 2000},
            "vision_score": 20,
            "game_duration_seconds": 1800,
        }
        pipeline.reports_dir.mkdir(parents=True, exist_ok=True)
        with open(pipeline.reports_dir / "NA1_OLD_analysis.json", "w", encoding="utf-8") as f:
            json.dump(analysis, f)
        stale_macro = {"match_id": "NA1_OLD", "detected_patterns": [], "possible_improvement_areas": [], "confidence_level": "partial", "champion_context_loaded": False, "role_context_loaded": False}
        with open(pipeline.reports_dir / "NA1_OLD_macro_patterns.json", "w", encoding="utf-8") as f:
            json.dump(stale_macro, f)
        store.record_game(analysis, stale_macro, path=pipeline.history_path)

        def get_timeline_fn(match_id):
            return _make_timeline(match_id)

        result = enrich_existing_timelines(
            get_timeline_fn,
            reports_dir=pipeline.reports_dir,
            timelines_dir=pipeline.timelines_dir,
            history_path=pipeline.history_path,
        )

        assert result["enriched"] == ["NA1_OLD"]
        assert result["failed"] == []
        assert (pipeline.timelines_dir / "NA1_OLD_timeline.json").exists()

        with open(pipeline.reports_dir / "NA1_OLD_macro_patterns.json", encoding="utf-8") as f:
            macro_result = json.load(f)
        deaths_before = next(
            p for p in macro_result["detected_patterns"] if p["pattern"] == "deaths_before_objectives"
        )
        assert deaths_before["confidence"] == "high"
        assert deaths_before["value"] == 1

        history = store.load_history(pipeline.history_path)
        assert len(history) == 1  # upserted, not duplicated
        history_patterns = {p["pattern"]: p["value"] for p in history[0]["detected_patterns"]}
        assert history_patterns["deaths_before_objectives"] == 1


if __name__ == "__main__":
    test_duplicate_match_handling()
    test_multiple_match_import()
    test_failed_api_response_handling()
    test_timeline_is_fetched_saved_and_used()
    test_timeline_failure_does_not_fail_match_import()
    test_enrich_existing_timelines_backfills_already_imported_match()
    print("All checks passed.")
