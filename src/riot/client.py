"""Thin wrapper around the Riot API.

Riot API is the source of truth for all match data in this project.
No other data source (OP.GG, U.GG, etc.) is used here.
"""

from riotwatcher import LolWatcher, RiotWatcher

# ponytail: only NA is mapped since that's the only region in use;
# add entries here as more regions are needed.
REGION_TO_CONTINENT = {
    "NA": "americas",
}


def region_to_continent(region: str) -> str:
    try:
        return REGION_TO_CONTINENT[region.upper()]
    except KeyError:
        raise ValueError(
            f"Unsupported region: {region!r}. "
            "Add it to REGION_TO_CONTINENT in src/riot/client.py."
        )


def get_puuid(api_key: str, continent: str, game_name: str, tag_line: str) -> str:
    riot_watcher = RiotWatcher(api_key)
    account = riot_watcher.account.by_riot_id(continent, game_name, tag_line)
    return account["puuid"]


def get_ranked_match_ids(api_key: str, continent: str, puuid: str, count: int = 20) -> list:
    lol_watcher = LolWatcher(api_key)
    return lol_watcher.match.matchlist_by_puuid(
        continent, puuid, count=count, type="ranked"
    )


def get_recent_ranked_match_id(api_key: str, continent: str, puuid: str) -> str:
    match_ids = get_ranked_match_ids(api_key, continent, puuid, count=1)
    if not match_ids:
        raise RuntimeError("No ranked matches found for this account.")
    return match_ids[0]


def get_match(api_key: str, continent: str, match_id: str) -> dict:
    lol_watcher = LolWatcher(api_key)
    return lol_watcher.match.by_id(continent, match_id)


def get_match_timeline(api_key: str, continent: str, match_id: str) -> dict:
    """Not all matches have timeline data (Riot's own caveat) — callers
    should expect this to sometimes fail even for a valid match_id."""
    lol_watcher = LolWatcher(api_key)
    return lol_watcher.match.timeline_by_match(continent, match_id)
