"""Self-check for src/riot/data_dragon.py.

Uses a fake get_fn and a temp cache directory -- no real network call.
Run with: python -m tests.test_data_dragon
"""

import json
import tempfile
from pathlib import Path

from src.riot.data_dragon import (
    build_champion_catalog,
    build_item_catalog,
    champion_id_from_name,
    champion_name_from_id,
    load_champion_catalog,
    load_item_catalog,
)

RAW_ITEM_DATA = {
    "1001": {"name": "Boots", "gold": {"total": 300}, "tags": ["Boots"], "from": []},
    "3020": {"name": "Sorcerer's Shoes", "gold": {"total": 1100}, "tags": ["Boots", "SpellDamage"], "from": ["1001"]},
}

# "MonkeyKing" is the internal id-slug; "Wukong" is the real display name --
# a real edge case Data Dragon's champion.json always has, worth covering
# explicitly so the catalog is proven to key off "name", not the outer dict key.
RAW_CHAMPION_DATA = {
    "Yone": {"version": "14.1.1", "id": "Yone", "key": "777", "name": "Yone", "title": "the Unforgotten"},
    "MonkeyKing": {"version": "14.1.1", "id": "MonkeyKing", "key": "62", "name": "Wukong", "title": "the Monkey King"},
}


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _make_get_fn(calls: list):
    def get_fn(url, timeout=10):
        calls.append(url)
        if "versions.json" in url:
            return _FakeResponse(["14.1.1"])
        return _FakeResponse({"data": RAW_ITEM_DATA})

    return get_fn


def _make_champion_get_fn(calls: list):
    def get_fn(url, timeout=10):
        calls.append(url)
        if "versions.json" in url:
            return _FakeResponse(["14.1.1"])
        return _FakeResponse({"data": RAW_CHAMPION_DATA})

    return get_fn


def test_build_item_catalog_shapes_raw_data():
    catalog = build_item_catalog(RAW_ITEM_DATA, version="14.1.1")

    assert catalog["version"] == "14.1.1"
    assert catalog["items_by_id"]["3020"]["name"] == "Sorcerer's Shoes"
    assert catalog["items_by_id"]["3020"]["cost"] == 1100
    assert catalog["items_by_id"]["3020"]["from"] == ["1001"]
    assert catalog["items_by_name"]["sorcerer's shoes"]["id"] == "3020"


def test_load_item_catalog_caches_after_first_fetch():
    with tempfile.TemporaryDirectory() as tmp:
        static_dir = Path(tmp)
        calls = []
        get_fn = _make_get_fn(calls)

        catalog = load_item_catalog(static_dir=static_dir, get_fn=get_fn)
        assert catalog["items_by_name"]["boots"]["cost"] == 300
        assert len(calls) == 2  # versions + item data (cache miss)
        assert (static_dir / "item_data_14.1.1.json").exists()

        # second call: same version, cache hit -- only the version check should fire
        catalog_again = load_item_catalog(static_dir=static_dir, get_fn=get_fn)
        assert catalog_again["items_by_name"]["boots"]["cost"] == 300
        assert len(calls) == 3  # +1 for the version check only, no re-fetch of item data


def test_build_champion_catalog_shapes_raw_data():
    catalog = build_champion_catalog(RAW_CHAMPION_DATA, version="14.1.1")

    assert catalog["version"] == "14.1.1"
    assert catalog["champions_by_id"][777]["name"] == "Yone"
    # keyed by numeric "key", not the outer dict key or the "id" slug
    assert catalog["champions_by_id"][62]["name"] == "Wukong"
    assert catalog["champions_by_name"]["wukong"]["id"] == 62


def test_load_champion_catalog_caches_after_first_fetch():
    with tempfile.TemporaryDirectory() as tmp:
        static_dir = Path(tmp)
        calls = []
        get_fn = _make_champion_get_fn(calls)

        catalog = load_champion_catalog(static_dir=static_dir, get_fn=get_fn)
        assert catalog["champions_by_name"]["yone"]["id"] == 777
        assert len(calls) == 2  # versions + champion data (cache miss)
        assert (static_dir / "champion_data_14.1.1.json").exists()

        # second call: same version, cache hit -- only the version check should fire
        catalog_again = load_champion_catalog(static_dir=static_dir, get_fn=get_fn)
        assert catalog_again["champions_by_name"]["yone"]["id"] == 777
        assert len(calls) == 3


def test_champion_name_from_id_never_guesses_unknown_ids():
    catalog = build_champion_catalog(RAW_CHAMPION_DATA, version="14.1.1")

    assert champion_name_from_id(catalog, 777) == "Yone"
    assert champion_name_from_id(catalog, 999999) is None


def test_champion_id_from_name_never_guesses_unknown_names():
    catalog = build_champion_catalog(RAW_CHAMPION_DATA, version="14.1.1")

    assert champion_id_from_name(catalog, "Yone") == 777
    assert champion_id_from_name(catalog, "yone") == 777  # case-insensitive
    assert champion_id_from_name(catalog, "NotAChampion") is None


def test_item_and_champion_catalogs_coexist_without_interference():
    # Proves Part A didn't disturb the existing item catalog behavior --
    # both caches live in the same static_dir under different filenames.
    with tempfile.TemporaryDirectory() as tmp:
        static_dir = Path(tmp)

        item_catalog = load_item_catalog(static_dir=static_dir, get_fn=_make_get_fn([]))
        champion_catalog = load_champion_catalog(static_dir=static_dir, get_fn=_make_champion_get_fn([]))

        assert item_catalog["items_by_name"]["boots"]["cost"] == 300
        assert champion_catalog["champions_by_name"]["yone"]["id"] == 777
        assert (static_dir / "item_data_14.1.1.json").exists()
        assert (static_dir / "champion_data_14.1.1.json").exists()


if __name__ == "__main__":
    test_build_item_catalog_shapes_raw_data()
    test_load_item_catalog_caches_after_first_fetch()
    test_build_champion_catalog_shapes_raw_data()
    test_load_champion_catalog_caches_after_first_fetch()
    test_champion_name_from_id_never_guesses_unknown_ids()
    test_champion_id_from_name_never_guesses_unknown_names()
    test_item_and_champion_catalogs_coexist_without_interference()
    print("All checks passed.")
