"""Builds a source-agnostic DraftSnapshot from a raw LCU champ-select
session dict.

Same role for the draft phase that src/analysis/game_state.py plays for
post-game data: this is the only file that knows the LCU's specific field
names (myTeam/theirTeam/cellId/championId/...). A future pick/ban
recommendation engine only ever reads the resulting plain dict -- it has
no idea whether it came from a real LCUClient (src/draft/client.py) or a
test fixture. No recommendations, synergy, counters, runes, or UI here --
this is structured extraction only.

championId == 0 is the LCU's own convention for "no champion picked yet";
normalized to None here, same "never invent data" discipline
game_state.py already follows for post-game fields it can't derive.
"""


def _member_summary(member: dict) -> dict:
    champion_id = member.get("championId") or None
    return {
        "cell_id": member.get("cellId"),
        "champion_id": champion_id,
        "assigned_position": member.get("assignedPosition") or None,
    }


def _phase_info(timer: dict | None) -> dict:
    timer = timer or {}
    return {
        "name": timer.get("phase"),
        "time_left_ms": timer.get("adjustedTimeLeftInPhase"),
        "is_infinite": timer.get("isInfinite"),
    }


def build_draft_snapshot(raw_session: dict | None) -> dict | None:
    """Returns None when there's no champ-select session to snapshot --
    raw_session is None (SessionPoller idle) or an empty dict -- never a
    fabricated empty-but-present snapshot.
    """
    if not raw_session:
        return None

    ally_team = [_member_summary(m) for m in raw_session.get("myTeam", [])]
    enemy_team = [_member_summary(m) for m in raw_session.get("theirTeam", [])]

    local_cell_id = raw_session.get("localPlayerCellId")
    current_player = next((m for m in ally_team if m["cell_id"] == local_cell_id), None)

    bans = raw_session.get("bans") or {}

    return {
        "ally_team": ally_team,
        "enemy_team": enemy_team,
        "ally_picks": [m["champion_id"] for m in ally_team if m["champion_id"] is not None],
        "enemy_picks": [m["champion_id"] for m in enemy_team if m["champion_id"] is not None],
        "ally_bans": list(bans.get("myTeamBans", [])),
        "enemy_bans": list(bans.get("theirTeamBans", [])),
        "current_player": current_player,
        "phase": _phase_info(raw_session.get("timer")),
    }
