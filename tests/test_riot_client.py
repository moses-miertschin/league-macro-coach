"""Self-check for the pure logic in the Riot API wiring — no network calls.

Run with: python -m tests.test_riot_client
"""

from src.main import find_participant
from src.riot.client import region_to_continent


def test_region_to_continent():
    assert region_to_continent("NA") == "americas"
    assert region_to_continent("na") == "americas"
    try:
        region_to_continent("EUW")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for unsupported region")


def test_find_participant():
    match = {"info": {"participants": [{"puuid": "a"}, {"puuid": "b"}]}}
    assert find_participant(match, "b") == {"puuid": "b"}
    try:
        find_participant(match, "missing")
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError for missing participant")


if __name__ == "__main__":
    test_region_to_continent()
    test_find_participant()
    print("All checks passed.")
