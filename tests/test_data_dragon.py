"""Self-check for src/riot/data_dragon.py.

Uses a fake get_fn and a temp cache directory -- no real network call.
Run with: python -m tests.test_data_dragon
"""

import json
import tempfile
from pathlib import Path

from src.riot.data_dragon import build_item_catalog, load_item_catalog

RAW_ITEM_DATA = {
    "1001": {"name": "Boots", "gold": {"total": 300}, "tags": ["Boots"], "from": []},
    "3020": {"name": "Sorcerer's Shoes", "gold": {"total": 1100}, "tags": ["Boots", "SpellDamage"], "from": ["1001"]},
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


if __name__ == "__main__":
    test_build_item_catalog_shapes_raw_data()
    test_load_item_catalog_caches_after_first_fetch()
    print("All checks passed.")
