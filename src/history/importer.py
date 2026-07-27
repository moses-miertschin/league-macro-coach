"""Ingests multiple recent ranked matches through the existing pipeline.

For each new match: save raw match JSON, fetch and save timeline data if
available, run the structured analyzer, run the macro pattern analyzer
(enriched with timeline data when present), then store the result in game
history. Matches already present in game history are skipped without
calling the Riot API. No AI, no advice text — this only wires together
modules that already exist (src/riot/client.py, src/analysis/analyzer.py,
src/analysis/timeline_analyzer.py, src/analysis/macro_analyzer.py,
src/history/store.py).

Timeline retrieval is best-effort and isolated from match import success:
Riot's own docs note "not all matches have timeline data," so a missing or
failed timeline does not fail the match — it just means that match's
macro patterns fall back to the pre-timeline "unavailable" markers for the
checks that need it, tracked separately in result["timeline_unavailable"].

import_matches() takes injected get_match_fn/get_timeline_fn so it can be
tested with fakes — no network, no API key, no live Riot API needed to
verify the dedup/import/failure-handling logic.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from src.analysis.analyzer import analyze_match
from src.analysis.macro_analyzer import macro_analyze
from src.analysis.timeline_analyzer import analyze_timeline
from src.history import store
from src.riot.client import (
    get_match,
    get_match_timeline,
    get_puuid,
    get_ranked_match_ids,
    region_to_continent,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROFILE_PATH = PROJECT_ROOT / "data" / "player_profile.json"
RAW_MATCHES_DIR = PROJECT_ROOT / "data" / "raw_matches"
TIMELINES_DIR = PROJECT_ROOT / "data" / "raw_matches" / "timelines"
REPORTS_DIR = PROJECT_ROOT / "reports" / "generated_reports"


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _load_or_fetch_timeline(
    match_id: str, get_timeline_fn, timelines_dir: Path, participant_id: int
) -> dict | None:
    timeline_path = timelines_dir / f"{match_id}_timeline.json"
    try:
        if timeline_path.exists():
            with open(timeline_path, encoding="utf-8") as f:
                timeline = json.load(f)
        else:
            timeline = get_timeline_fn(match_id)
            _save_json(timeline_path, timeline)
        return analyze_timeline(timeline, participant_id)
    except Exception:
        # timelines are best-effort (Riot: "not all matches have timeline
        # data") — a failure here must not fail the whole match import.
        return None


def import_matches(
    match_ids: list,
    get_match_fn,
    game_name: str,
    tag_line: str,
    raw_matches_dir: Path = RAW_MATCHES_DIR,
    reports_dir: Path = REPORTS_DIR,
    history_path: Path = store.HISTORY_PATH,
    timelines_dir: Path = TIMELINES_DIR,
    get_timeline_fn=None,
) -> dict:
    already_recorded = {g["match_id"] for g in store.load_history(history_path)}

    result = {"imported": [], "skipped_existing": [], "failed": [], "timeline_unavailable": []}

    for match_id in match_ids:
        if match_id in already_recorded:
            result["skipped_existing"].append(match_id)
            continue

        try:
            raw_path = raw_matches_dir / f"{match_id}.json"
            if raw_path.exists():
                with open(raw_path, encoding="utf-8") as f:
                    match = json.load(f)
            else:
                match = get_match_fn(match_id)
                _save_json(raw_path, match)

            analysis = analyze_match(match, game_name, tag_line)
            _save_json(reports_dir / f"{match_id}_analysis.json", analysis)

            timeline_result = None
            if get_timeline_fn is not None:
                timeline_result = _load_or_fetch_timeline(
                    match_id, get_timeline_fn, timelines_dir, analysis["participant_id"]
                )
                if timeline_result is None:
                    result["timeline_unavailable"].append(match_id)

            macro_result = macro_analyze(analysis, timeline_result)
            _save_json(reports_dir / f"{match_id}_macro_patterns.json", macro_result)

            store.record_game(analysis, macro_result, path=history_path)
            result["imported"].append(match_id)
        except Exception as exc:
            result["failed"].append({"match_id": match_id, "error": str(exc)})

    return result


def run_import(count: int = 10) -> dict:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("RIOT_API_KEY")
    if not api_key:
        raise RuntimeError(
            "RIOT_API_KEY is not set. Copy .env.example to .env and fill it in."
        )

    with open(PROFILE_PATH, encoding="utf-8") as f:
        profile = json.load(f)
    game_name, tag_line = profile["riot_id"].split("#")
    continent = region_to_continent(profile["region"])

    puuid = get_puuid(api_key, continent, game_name, tag_line)
    match_ids = get_ranked_match_ids(api_key, continent, puuid, count=count)

    def get_match_fn(match_id):
        return get_match(api_key, continent, match_id)

    def get_timeline_fn(match_id):
        return get_match_timeline(api_key, continent, match_id)

    return import_matches(match_ids, get_match_fn, game_name, tag_line, get_timeline_fn=get_timeline_fn)


def main() -> None:
    result = run_import()
    print(f"Imported {len(result['imported'])} new match(es).")
    if result["skipped_existing"]:
        print(f"Skipped {len(result['skipped_existing'])} already-recorded match(es).")
    if result["timeline_unavailable"]:
        print(
            f"Timeline unavailable for {len(result['timeline_unavailable'])} match(es) "
            "(imported without timeline-based patterns)."
        )
    if result["failed"]:
        print(f"Failed {len(result['failed'])} match(es):")
        for failure in result["failed"]:
            print(f"  {failure['match_id']}: {failure['error']}")


if __name__ == "__main__":
    main()
