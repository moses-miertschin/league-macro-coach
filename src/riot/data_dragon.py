"""Thin client for Riot's public Data Dragon static item data.

No API key, no rate limits -- this is static per-patch JSON served over
plain HTTPS. Used only for item cost/tags/build-path lookups (the item
recommendation engine's "does this item still exist, what does it cost,
what does it build from" ground truth), never for match or live data.

Cached to disk per-version so a normal run doesn't re-fetch every time.
"""

import json
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = PROJECT_ROOT / "data" / "static"

VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
ITEM_URL_TEMPLATE = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/item.json"


def fetch_latest_version(get_fn=requests.get) -> str:
    response = get_fn(VERSIONS_URL, timeout=10)
    response.raise_for_status()
    versions = response.json()
    return versions[0]


def fetch_item_data(version: str, get_fn=requests.get) -> dict:
    """Returns Data Dragon's raw item.json 'data' mapping: item_id -> fields."""
    response = get_fn(ITEM_URL_TEMPLATE.format(version=version), timeout=10)
    response.raise_for_status()
    return response.json()["data"]


def build_item_catalog(raw_item_data: dict, version: str = "unknown") -> dict:
    """Reshapes Data Dragon's raw item data into a lookup catalog keyed both
    by lowercased item name and by item id. Pure function -- no network.
    """
    items_by_id = {}
    items_by_name = {}

    for item_id, fields in raw_item_data.items():
        entry = {
            "id": item_id,
            "name": fields["name"],
            "cost": fields.get("gold", {}).get("total", 0),
            "tags": fields.get("tags", []),
            "from": fields.get("from", []),
        }
        items_by_id[item_id] = entry
        items_by_name[fields["name"].lower()] = entry

    return {"version": version, "items_by_id": items_by_id, "items_by_name": items_by_name}


def load_item_catalog(static_dir: Path = STATIC_DIR, get_fn=requests.get) -> dict:
    """Loads the cached item catalog, fetching and caching it if missing or
    if a newer patch version is available.
    """
    version = fetch_latest_version(get_fn=get_fn)
    cache_path = static_dir / f"item_data_{version}.json"

    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            raw_item_data = json.load(f)
    else:
        raw_item_data = fetch_item_data(version, get_fn=get_fn)
        static_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(raw_item_data, f, indent=2)

    return build_item_catalog(raw_item_data, version=version)


def main() -> None:
    catalog = load_item_catalog()
    print(f"Loaded item catalog for patch {catalog['version']} ({len(catalog['items_by_id'])} items).")


if __name__ == "__main__":
    main()
