"""Builds a source-agnostic GameSnapshot from a completed Riot match.

This is the only file that knows how to turn a specific data source into a
GameSnapshot. src/analysis/item_recommender.py only ever reads the
resulting dict -- it has no idea whether the snapshot came from a finished
match (this module, today) or a live game (a future src/live/ builder
producing the identical shape). No AI, no knowledge-base lookups here --
this is structured extraction, the same role src/analysis/analyzer.py
plays for the deterministic macro pipeline.

Two fields are genuinely derived rather than passed through verbatim:
`is_fed` per enemy and `game_state` (ahead/even/behind) for the player's
team -- both computed once here so item_recommender.py only ever reads
facts, never derives them.
"""

from src.analysis.analyzer import find_participant

# ponytail: guesses at "fed", same caveat as macro_analyzer.py's BENCHMARKS --
# tune once there's more real data to check these against.
FED_GOLD_PER_MINUTE_THRESHOLD = 600
FED_KILL_DEATH_DIFF_THRESHOLD = 5

# ponytail: guesses at "ahead"/"behind", same caveat as above.
AHEAD_GOLD_DIFF_THRESHOLD = 1500
AHEAD_KILL_DIFF_THRESHOLD = 3


def _items(participant: dict) -> list:
    return [participant[f"item{i}"] for i in range(7) if participant.get(f"item{i}", 0)]


def _is_fed(gold_earned_total: int, kills: int, deaths: int, duration_seconds: int) -> bool:
    minutes = duration_seconds / 60 if duration_seconds else 1
    gold_per_minute = gold_earned_total / minutes
    return (kills - deaths) >= FED_KILL_DEATH_DIFF_THRESHOLD or gold_per_minute >= FED_GOLD_PER_MINUTE_THRESHOLD


def _participant_summary(p: dict) -> dict:
    return {
        "champion": p["championName"],
        "role": p.get("teamPosition") or p.get("individualPosition"),
        "level": p["champLevel"],
        "items": _items(p),
        "gold_earned_total": p["goldEarned"],
        "kills": p["kills"],
        "deaths": p["deaths"],
        "assists": p["assists"],
    }


def _team_objectives(teams: list, team_id: int) -> dict:
    team = next(t for t in teams if t["teamId"] == team_id)
    objectives = team["objectives"]
    return {
        "dragon": objectives["dragon"]["kills"],
        "baron": objectives["baron"]["kills"],
        "tower": objectives["tower"]["kills"],
    }


def _game_state(gold_diff: int, kill_diff: int) -> str:
    if gold_diff >= AHEAD_GOLD_DIFF_THRESHOLD or kill_diff >= AHEAD_KILL_DIFF_THRESHOLD:
        return "ahead"
    if gold_diff <= -AHEAD_GOLD_DIFF_THRESHOLD or kill_diff <= -AHEAD_KILL_DIFF_THRESHOLD:
        return "behind"
    return "even"


def build_snapshot_from_match(match: dict, game_name: str, tag_line: str) -> dict:
    participant = find_participant(match, game_name, tag_line)
    info = match["info"]
    duration_seconds = info["gameDuration"]
    player_team_id = participant["teamId"]

    teammates = [
        p for p in info["participants"]
        if p["teamId"] == player_team_id and p["participantId"] != participant["participantId"]
    ]
    enemies = [p for p in info["participants"] if p["teamId"] != player_team_id]

    enemy_summaries = []
    for p in enemies:
        summary = _participant_summary(p)
        summary["is_fed"] = _is_fed(summary["gold_earned_total"], summary["kills"], summary["deaths"], duration_seconds)
        enemy_summaries.append(summary)

    player_team_objectives = _team_objectives(info["teams"], player_team_id)
    enemy_team_id = next(t["teamId"] for t in info["teams"] if t["teamId"] != player_team_id)
    enemy_team_objectives = _team_objectives(info["teams"], enemy_team_id)

    player_total_gold = participant["goldEarned"] + sum(p["goldEarned"] for p in teammates)
    enemy_total_gold = sum(p["goldEarned"] for p in enemies)
    player_total_kills = participant["kills"] + sum(p["kills"] for p in teammates)
    enemy_total_kills = sum(p["kills"] for p in enemies)
    player_levels = [participant["champLevel"]] + [p["champLevel"] for p in teammates]
    enemy_levels = [p["champLevel"] for p in enemies]

    gold_diff = player_total_gold - enemy_total_gold
    kill_diff = player_total_kills - enemy_total_kills

    return {
        "champion": participant["championName"],
        "role": participant.get("teamPosition") or participant.get("individualPosition"),
        "game_time_seconds": duration_seconds,
        "player": {
            "level": participant["champLevel"],
            "current_items": _items(participant),
            "current_gold": None,  # not derivable from a completed match
            "total_gold_earned": participant["goldEarned"],
            "kills": participant["kills"],
            "deaths": participant["deaths"],
            "assists": participant["assists"],
        },
        "player_team": [_participant_summary(p) for p in teammates],
        "enemy_team": enemy_summaries,
        "objectives": {
            "dragons_taken": {"player_team": player_team_objectives["dragon"], "enemy_team": enemy_team_objectives["dragon"]},
            "barons_taken": {"player_team": player_team_objectives["baron"], "enemy_team": enemy_team_objectives["baron"]},
            "towers_destroyed": {"player_team": player_team_objectives["tower"], "enemy_team": enemy_team_objectives["tower"]},
        },
        "team_state": {
            "gold_diff": gold_diff,
            "kill_diff": kill_diff,
            "turret_diff": player_team_objectives["tower"] - enemy_team_objectives["tower"],
            "dragon_diff": player_team_objectives["dragon"] - enemy_team_objectives["dragon"],
            "baron_diff": player_team_objectives["baron"] - enemy_team_objectives["baron"],
            "avg_level_diff": round(sum(player_levels) / len(player_levels) - sum(enemy_levels) / len(enemy_levels), 2),
        },
        "game_state": _game_state(gold_diff, kill_diff),
    }
