"""LeagueMacroCoach entrypoint.

Phase 1: connect to the Riot API, fetch the most recent ranked match for
the player in data/player_profile.json, save the raw match JSON, and print
a basic summary. Analysis and AI coaching are not wired in yet.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from src.riot.client import (
    get_match,
    get_puuid,
    get_recent_ranked_match_id,
    region_to_continent,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = PROJECT_ROOT / "data" / "player_profile.json"
RAW_MATCHES_DIR = PROJECT_ROOT / "data" / "raw_matches"


def load_profile() -> dict:
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return json.load(f)


def find_participant(match: dict, puuid: str) -> dict:
    for participant in match["info"]["participants"]:
        if participant["puuid"] == puuid:
            return participant
    raise RuntimeError("Player not found in match participants.")


def print_summary(participant: dict, match: dict, match_id: str) -> None:
    duration_seconds = match["info"]["gameDuration"]
    minutes, seconds = divmod(duration_seconds, 60)
    cs = participant["totalMinionsKilled"] + participant["neutralMinionsKilled"]

    print("\n--- Most Recent Ranked Match ---")
    print(f"Match ID:  {match_id}")
    print(f"Champion:  {participant['championName']}")
    print(f"Result:    {'Win' if participant['win'] else 'Loss'}")
    print(
        f"KDA:       {participant['kills']}/{participant['deaths']}/{participant['assists']}"
    )
    print(f"CS:        {cs}")
    print(f"Duration:  {minutes}m {seconds}s")


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("RIOT_API_KEY")
    if not api_key:
        raise RuntimeError(
            "RIOT_API_KEY is not set. Copy .env.example to .env and fill it in."
        )

    profile = load_profile()
    game_name, tag_line = profile["riot_id"].split("#")
    continent = region_to_continent(profile["region"])

    puuid = get_puuid(api_key, continent, game_name, tag_line)
    match_id = get_recent_ranked_match_id(api_key, continent, puuid)
    match = get_match(api_key, continent, match_id)

    RAW_MATCHES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_MATCHES_DIR / f"{match_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(match, f, indent=2)
    print(f"Saved raw match data to {out_path.relative_to(PROJECT_ROOT)}")

    participant = find_participant(match, puuid)
    print_summary(participant, match, match_id)


if __name__ == "__main__":
    main()
