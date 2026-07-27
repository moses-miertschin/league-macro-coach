"""Load/save benchmark datasets.

Flat-JSON storage, deliberately mirroring src/history/store.py's existing
load/save/upsert pattern rather than inventing a new storage idiom.
Upserts by (champion, role, patch, rank), case-insensitive on
champion/role/rank -- the same "re-processing must update, never
duplicate" discipline store.py already applies to match_id.

No benchmark data ships with this module. load_benchmarks() returns an
empty list until a real data source (none built yet -- see
benchmark_schema.py) actually adds entries.
"""

import json
from pathlib import Path

from src.benchmark.benchmark_schema import validate_benchmark_entry

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BENCHMARK_DATA_PATH = PROJECT_ROOT / "data" / "benchmarks" / "benchmark_data.json"


def _key(entry: dict) -> tuple:
    return (
        entry.get("champion", "").lower(),
        entry.get("role", "").lower(),
        entry.get("patch"),
        str(entry.get("rank", "")).lower(),
    )


def load_benchmarks(path: Path = BENCHMARK_DATA_PATH) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_benchmarks(entries: list, path: Path = BENCHMARK_DATA_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def add_benchmark_entry(entry: dict, path: Path = BENCHMARK_DATA_PATH) -> dict:
    errors = validate_benchmark_entry(entry)
    if errors:
        raise ValueError(f"Invalid benchmark entry: {'; '.join(errors)}")

    entries = load_benchmarks(path)
    entries = [e for e in entries if _key(e) != _key(entry)]
    entries.append(entry)
    save_benchmarks(entries, path)
    return entry


def find_benchmarks(champion: str, role: str, patch: str = None, rank: str = None,
                     path: Path = BENCHMARK_DATA_PATH, **extra_filters) -> list:
    """Query stored benchmarks by champion/role plus optional patch/rank.

    **extra_filters matches any additional descriptor key exactly (e.g.
    matchup="Akali_vs_Zed") -- this is what lets matchup-specific or any
    other future benchmark dimension be queried without changing this
    function, per benchmark_schema.py's permissive-extra-fields design.
    """
    entries = load_benchmarks(path)
    results = []
    for e in entries:
        if e.get("champion", "").lower() != champion.lower():
            continue
        if e.get("role", "").lower() != role.lower():
            continue
        if patch is not None and e.get("patch") != patch:
            continue
        if rank is not None and str(e.get("rank", "")).lower() != rank.lower():
            continue
        if any(e.get(k) != v for k, v in extra_filters.items()):
            continue
        results.append(e)
    return results
