"""Extracts structured per-game stats from a saved Riot match JSON.

No mistake-judging or coaching logic yet — this only reshapes raw Riot API
match data into a flat, structured summary for later phases to build on.
Works entirely from locally saved match JSON and player_profile.json;
makes no API calls.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROFILE_PATH = PROJECT_ROOT / "data" / "player_profile.json"
RAW_MATCHES_DIR = PROJECT_ROOT / "data" / "raw_matches"
REPORTS_DIR = PROJECT_ROOT / "reports" / "generated_reports"


def find_participant(match: dict, game_name: str, tag_line: str) -> dict:
    for participant in match["info"]["participants"]:
        if (
            participant.get("riotIdGameName", "").lower() == game_name.lower()
            and participant.get("riotIdTagline", "").lower() == tag_line.lower()
        ):
            return participant
    raise RuntimeError(f"{game_name}#{tag_line} not found in match participants.")


def analyze_match(match: dict, game_name: str, tag_line: str) -> dict:
    participant = find_participant(match, game_name, tag_line)
    info = match["info"]
    challenges = participant.get("challenges", {})

    duration_seconds = info["gameDuration"]
    duration_minutes = duration_seconds / 60
    cs = participant["totalMinionsKilled"] + participant["neutralMinionsKilled"]

    team_damage = sum(
        p["totalDamageDealtToChampions"]
        for p in info["participants"]
        if p["teamId"] == participant["teamId"]
    )
    damage_share = (
        round(participant["totalDamageDealtToChampions"] / team_damage, 3) if team_damage else None
    )

    return {
        "match_id": match["metadata"]["matchId"],
        "game_start_timestamp": info.get("gameStartTimestamp"),
        "participant_id": participant["participantId"],
        "champion": participant["championName"],
        "role": participant.get("teamPosition") or participant.get("individualPosition"),
        "win": participant["win"],
        "kda": {
            "kills": participant["kills"],
            "deaths": participant["deaths"],
            "assists": participant["assists"],
        },
        "cs_per_minute": round(cs / duration_minutes, 2) if duration_minutes else 0,
        "gold_earned": participant["goldEarned"],
        "damage_to_champions": participant["totalDamageDealtToChampions"],
        "damage_share": damage_share,
        "objectives_participation": {
            "kill_participation": challenges.get("killParticipation"),
            "damage_to_objectives": participant.get("damageDealtToObjectives"),
        },
        "vision_score": participant["visionScore"],
        "game_duration_seconds": duration_seconds,
    }


def latest_raw_match() -> Path:
    matches = sorted(RAW_MATCHES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not matches:
        raise RuntimeError(f"No raw match files found in {RAW_MATCHES_DIR}")
    return matches[-1]


def main() -> None:
    with open(PROFILE_PATH, encoding="utf-8") as f:
        profile = json.load(f)
    game_name, tag_line = profile["riot_id"].split("#")

    raw_match_path = latest_raw_match()
    with open(raw_match_path, encoding="utf-8") as f:
        match = json.load(f)

    analysis = analyze_match(match, game_name, tag_line)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{analysis['match_id']}_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2)

    print(f"Saved structured analysis to {out_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
