"""Self-check for src/analysis/game_state.py.

Builds a fixture match dict (all 10 participants, both teams' objectives) --
no network, no raw match file needed. Run with: python -m tests.test_game_state
"""

from src.analysis.game_state import build_snapshot_from_match

GAME_NAME, TAG_LINE = "HelloKittler", "meow"


def _participant(participant_id, team_id, champion, **overrides):
    p = {
        "participantId": participant_id,
        "teamId": team_id,
        "championName": champion,
        "teamPosition": "MIDDLE",
        "champLevel": 10,
        "goldEarned": 6000,
        "kills": 2,
        "deaths": 2,
        "assists": 2,
        "item0": 0, "item1": 0, "item2": 0, "item3": 0, "item4": 0, "item5": 0, "item6": 0,
    }
    p.update(overrides)
    return p


def _make_match():
    player = _participant(
        1, 100, "Yone",
        riotIdGameName=GAME_NAME, riotIdTagline=TAG_LINE,
        champLevel=11, goldEarned=9000, kills=4, deaths=2, assists=3, item0=4,
    )
    teammates = [_participant(i, 100, "Ally", champLevel=10, goldEarned=6000, kills=2) for i in range(2, 6)]
    fed_enemy = _participant(6, 200, "Caitlyn", champLevel=12, goldEarned=15000, kills=15, deaths=2, assists=1)
    other_enemies = [_participant(i, 200, "Enemy", champLevel=11, goldEarned=6000, kills=3, deaths=3) for i in range(7, 11)]

    return {
        "metadata": {"matchId": "NA1_TEST"},
        "info": {
            "gameDuration": 1500,
            "participants": [player, *teammates, fed_enemy, *other_enemies],
            "teams": [
                {"teamId": 100, "objectives": {"dragon": {"kills": 1}, "baron": {"kills": 0}, "tower": {"kills": 3}}},
                {"teamId": 200, "objectives": {"dragon": {"kills": 2}, "baron": {"kills": 1}, "tower": {"kills": 6}}},
            ],
        },
    }


def test_snapshot_shape_and_player_fields():
    snapshot = build_snapshot_from_match(_make_match(), GAME_NAME, TAG_LINE)

    assert snapshot["champion"] == "Yone"
    assert snapshot["role"] == "MIDDLE"
    assert snapshot["game_time_seconds"] == 1500
    assert snapshot["player"]["level"] == 11
    assert snapshot["player"]["current_items"] == [4]
    assert snapshot["player"]["current_gold"] is None  # not derivable post-game
    assert snapshot["player"]["total_gold_earned"] == 9000
    assert len(snapshot["player_team"]) == 4
    assert len(snapshot["enemy_team"]) == 5


def test_is_fed_flags_only_the_fed_enemy():
    snapshot = build_snapshot_from_match(_make_match(), GAME_NAME, TAG_LINE)
    fed_flags = {e["champion"]: e["is_fed"] for e in snapshot["enemy_team"] if e["champion"] == "Caitlyn"}
    assert fed_flags["Caitlyn"] is True
    assert all(e["is_fed"] is False for e in snapshot["enemy_team"] if e["champion"] == "Enemy")


def test_team_state_and_objectives_diffs():
    snapshot = build_snapshot_from_match(_make_match(), GAME_NAME, TAG_LINE)
    team_state = snapshot["team_state"]

    # player total gold: 9000 + 4*6000 = 33000; enemy total: 15000 + 4*6000 = 39000
    assert team_state["gold_diff"] == 33000 - 39000
    # player total kills: 4 + 4*2 = 12; enemy total: 15 + 4*3 = 27
    assert team_state["kill_diff"] == 12 - 27
    assert team_state["turret_diff"] == 3 - 6
    assert team_state["dragon_diff"] == 1 - 2
    assert team_state["baron_diff"] == 0 - 1

    assert snapshot["objectives"]["towers_destroyed"] == {"player_team": 3, "enemy_team": 6}


def test_game_state_behind_when_far_behind_on_gold_and_kills():
    snapshot = build_snapshot_from_match(_make_match(), GAME_NAME, TAG_LINE)
    assert snapshot["game_state"] == "behind"


def _make_ahead_match():
    # mirror image of _make_match(): the *player's* team is the fed one.
    match = _make_match()
    match["info"]["participants"][0]["goldEarned"] = 15000  # player
    match["info"]["participants"][0]["kills"] = 15
    for enemy in match["info"]["participants"][6:]:
        enemy["goldEarned"] = 3000
        enemy["kills"] = 0
    return match


def _make_even_match():
    match = _make_match()
    for p in match["info"]["participants"]:
        p["goldEarned"] = 6000
        p["kills"] = 2
    return match


def test_game_state_ahead_when_far_ahead_on_gold_and_kills():
    # regression test: this branch of _game_state() had no coverage at all
    # (TEST_AUDIT.md flagged it as the single biggest gap in this module,
    # since it directly drives item_recommender.py's game_state_ahead trigger).
    snapshot = build_snapshot_from_match(_make_ahead_match(), GAME_NAME, TAG_LINE)
    assert snapshot["game_state"] == "ahead"


def test_game_state_even_when_close_on_gold_and_kills():
    snapshot = build_snapshot_from_match(_make_even_match(), GAME_NAME, TAG_LINE)
    assert snapshot["game_state"] == "even"


if __name__ == "__main__":
    test_snapshot_shape_and_player_fields()
    test_is_fed_flags_only_the_fed_enemy()
    test_team_state_and_objectives_diffs()
    test_game_state_behind_when_far_behind_on_gold_and_kills()
    test_game_state_ahead_when_far_ahead_on_gold_and_kills()
    test_game_state_even_when_close_on_gold_and_kills()
    print("All checks passed.")
