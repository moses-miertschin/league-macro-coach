"""Rule-based analysis of Riot match timeline data.

The match-detail endpoint (src/analysis/analyzer.py) only gives end-of-game
totals. The Match-V5 timeline endpoint gives per-event timestamps, which
answers questions totals can't: exactly when a player died, whether an
objective fell shortly after, and whether they were credited (kill or
assist) on a dragon/baron/tower takedown.

No AI, no coaching language — every field here is either a raw
timestamp/count pulled straight from timeline events, or a small,
documented rule-based derivation (a fixed time window, a kill-clustering
heuristic). Both are marked with `ponytail:` comments since the exact
window/threshold values are reasonable guesses, not Riot-defined facts.

Timeline events identify players by integer `participantId` (1-10), which
is already present on every match-detail participant
(src/analysis/analyzer.py's `participant_id` field) — no separate puuid
lookup into the timeline's own participant list is needed.

Riot's timeline has no explicit "recall" event. Item-purchase timestamps
are the closest proxy, but they also fire for non-recall restocks (e.g.
remote purchases), so using them would misrepresent a guess as a
measurement. Recall timing is reported as unavailable instead.
"""

CHAMPION_KILL = "CHAMPION_KILL"
ELITE_MONSTER_KILL = "ELITE_MONSTER_KILL"
BUILDING_KILL = "BUILDING_KILL"
DRAGON = "DRAGON"
BARON = "BARON_NASHOR"
TOWER = "TOWER_BUILDING"

# ponytail: a death "before an objective" is one where a dragon/baron/
# tower falls within this many ms afterward. A guess at "meaningfully
# related", not a Riot-defined relationship — tune if it proves too
# loose/tight once there's more real data to check it against.
OBJECTIVE_WINDOW_MS = 60_000

# ponytail: consecutive champion kills within this gap are treated as one
# "fight" (must have at least this many kills to count). No official
# teamfight event exists in the timeline — this is a clustering heuristic.
FIGHT_WINDOW_MS = 30_000
MIN_FIGHT_KILLS = 2


def _all_events(timeline: dict) -> list:
    events = []
    for frame in timeline["info"]["frames"]:
        events.extend(frame["events"])
    return events


def _is_player_credited(event: dict, participant_id: int) -> bool:
    return event.get("killerId") == participant_id or participant_id in event.get(
        "assistingParticipantIds", []
    )


def _death_timing(events: list, participant_id: int) -> tuple:
    death_timestamps = [
        e["timestamp"]
        for e in events
        if e["type"] == CHAMPION_KILL and e.get("victimId") == participant_id
    ]

    objective_timestamps = [
        e["timestamp"]
        for e in events
        if (e["type"] == ELITE_MONSTER_KILL and e.get("monsterType") in (DRAGON, BARON))
        or (e["type"] == BUILDING_KILL and e.get("buildingType") == TOWER)
    ]

    deaths_before_objectives = sum(
        1
        for death_ts in death_timestamps
        if any(death_ts < obj_ts <= death_ts + OBJECTIVE_WINDOW_MS for obj_ts in objective_timestamps)
    )

    return death_timestamps, deaths_before_objectives


def _objective_participation(events: list, participant_id: int) -> dict:
    def _tally(predicate):
        matching = [e for e in events if predicate(e)]
        participated = sum(1 for e in matching if _is_player_credited(e, participant_id))
        return {"total": len(matching), "participated": participated}

    return {
        "dragons": _tally(lambda e: e["type"] == ELITE_MONSTER_KILL and e.get("monsterType") == DRAGON),
        "barons": _tally(lambda e: e["type"] == ELITE_MONSTER_KILL and e.get("monsterType") == BARON),
        "towers": _tally(lambda e: e["type"] == BUILDING_KILL and e.get("buildingType") == TOWER),
    }


def _fight_participation(events: list, participant_id: int) -> dict:
    kills = sorted((e for e in events if e["type"] == CHAMPION_KILL), key=lambda e: e["timestamp"])

    fights, current = [], []
    for kill in kills:
        if current and kill["timestamp"] - current[-1]["timestamp"] > FIGHT_WINDOW_MS:
            fights.append(current)
            current = []
        current.append(kill)
    if current:
        fights.append(current)

    fights = [f for f in fights if len(f) >= MIN_FIGHT_KILLS]
    participated = sum(
        1
        for fight in fights
        if any(_is_player_credited(k, participant_id) or k.get("victimId") == participant_id for k in fight)
    )

    return {
        "fights_detected": len(fights),
        "fights_participated": participated,
        "participation_rate": round(participated / len(fights), 2) if fights else None,
    }


def analyze_timeline(timeline: dict, participant_id: int) -> dict:
    events = _all_events(timeline)
    death_timestamps, deaths_before_objectives = _death_timing(events, participant_id)

    return {
        "death_timestamps_ms": death_timestamps,
        "deaths_before_objectives": deaths_before_objectives,
        "objective_participation": _objective_participation(events, participant_id),
        "recall_patterns": {
            "status": "unavailable",
            "detail": (
                "Riot's match timeline has no explicit recall event; item purchase "
                "timestamps are a weak proxy (they also fire for non-recall restocks) "
                "and were not used to avoid a misleading signal."
            ),
        },
        "fight_participation": _fight_participation(events, participant_id),
    }
