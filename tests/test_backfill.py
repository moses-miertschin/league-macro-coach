"""Self-check for src/history/backfill.py.

This tests the backfill wrapper's own behavior — configurable count,
result reporting, and CLI-level error handling — not the importer's
dedup/failure logic itself, which is already covered in depth by
tests/test_importer.py. run_import is injected as a fake, so this needs
no network access and no API key.

Run with: python -m tests.test_backfill
"""

import io
from contextlib import redirect_stdout

from src.history.backfill import DEFAULT_BACKFILL_COUNT, backfill, run_backfill_cli


def test_backfill_imports_multiple_matches():
    calls = []

    def fake_run_import(count):
        calls.append(count)
        return {"imported": ["NA1_A", "NA1_B", "NA1_C"], "skipped_existing": [], "failed": []}

    result = backfill(count=15, run_import_fn=fake_run_import)

    assert calls == [15]  # the configurable count was passed through untouched
    assert result["imported"] == ["NA1_A", "NA1_B", "NA1_C"]


def test_backfill_default_count_is_used_when_unspecified():
    captured = {}

    def fake_run_import(count):
        captured["count"] = count
        return {"imported": [], "skipped_existing": [], "failed": []}

    backfill(run_import_fn=fake_run_import)
    assert captured["count"] == DEFAULT_BACKFILL_COUNT


def test_backfill_skips_existing_matches():
    def fake_run_import(count):
        return {
            "imported": ["NA1_NEW"],
            "skipped_existing": ["NA1_OLD_1", "NA1_OLD_2"],
            "failed": [],
        }

    result = backfill(run_import_fn=fake_run_import)

    assert result["imported"] == ["NA1_NEW"]
    assert result["skipped_existing"] == ["NA1_OLD_1", "NA1_OLD_2"]


def test_backfill_reports_failed_retrieval_without_crashing():
    def fake_run_import(count):
        return {
            "imported": ["NA1_OK"],
            "skipped_existing": [],
            "failed": [{"match_id": "NA1_BROKEN", "error": "401 Client Error: Unauthorized"}],
        }

    result = backfill(run_import_fn=fake_run_import)

    assert result["imported"] == ["NA1_OK"]
    assert len(result["failed"]) == 1
    assert result["failed"][0]["match_id"] == "NA1_BROKEN"


def test_cli_reports_setup_error_without_raising():
    def fake_run_import(count):
        raise RuntimeError("RIOT_API_KEY is not set. Copy .env.example to .env and fill it in.")

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run_backfill_cli(5, run_import_fn=fake_run_import)  # must not raise

    output = buffer.getvalue()
    assert "Backfill aborted" in output
    assert "RIOT_API_KEY" in output


def test_cli_prints_summary_on_success():
    def fake_run_import(count):
        return {
            "imported": ["NA1_A", "NA1_B"],
            "skipped_existing": ["NA1_OLD"],
            "failed": [{"match_id": "NA1_BROKEN", "error": "boom"}],
        }

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run_backfill_cli(10, run_import_fn=fake_run_import)

    output = buffer.getvalue()
    assert "2 new game(s) imported" in output
    assert "1 already in history, skipped" in output
    assert "NA1_BROKEN: boom" in output


if __name__ == "__main__":
    test_backfill_imports_multiple_matches()
    test_backfill_default_count_is_used_when_unspecified()
    test_backfill_skips_existing_matches()
    test_backfill_reports_failed_retrieval_without_crashing()
    test_cli_reports_setup_error_without_raising()
    test_cli_prints_summary_on_success()
    print("All checks passed.")
