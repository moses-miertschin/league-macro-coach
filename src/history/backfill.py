"""Historical match backfill.

Bulk-imports recent ranked games so the player profile and insights have
more than a single match to work from. This is a thin wrapper around
src/history/importer.py's run_import() — it does not re-implement match
retrieval, deduplication, analysis, or storage. Those stay exactly as
built: same Riot API client, same analyzer, same macro analyzer, same
history store, same "mark it unavailable, don't fabricate it" philosophy.
No AI, no LLM calls.

The only things this module adds are a configurable game count and a
backfill-specific summary/CLI. run_import_fn is injectable so this can be
tested without hitting the network or needing an API key.
"""

import argparse

from src.history.importer import run_import

DEFAULT_BACKFILL_COUNT = 20


def backfill(count: int = DEFAULT_BACKFILL_COUNT, run_import_fn=run_import) -> dict:
    return run_import_fn(count=count)


def _print_summary(result: dict) -> None:
    print(f"Backfill complete: {len(result['imported'])} new game(s) imported.")
    if result["skipped_existing"]:
        print(f"  {len(result['skipped_existing'])} already in history, skipped.")
    if result.get("timeline_unavailable"):
        print(
            f"  {len(result['timeline_unavailable'])} imported without timeline data "
            "(not available for that match)."
        )
    if result["failed"]:
        print(f"  {len(result['failed'])} failed to retrieve:")
        for failure in result["failed"]:
            print(f"    {failure['match_id']}: {failure['error']}")


def run_backfill_cli(count: int, run_import_fn=run_import) -> None:
    try:
        result = backfill(count=count, run_import_fn=run_import_fn)
    except RuntimeError as exc:
        # setup-level failure (e.g. missing RIOT_API_KEY) — distinct from
        # the per-match failures already handled inside import_matches,
        # which are reported in result["failed"] instead of raised.
        print(f"Backfill aborted: {exc}")
        return
    _print_summary(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill recent ranked match history.")
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_BACKFILL_COUNT,
        help=f"Number of recent ranked matches to check (default: {DEFAULT_BACKFILL_COUNT})",
    )
    args = parser.parse_args()
    run_backfill_cli(args.count)


if __name__ == "__main__":
    main()
