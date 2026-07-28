"""Self-check for src/knowledge/champion_loader.py.

Writes fixture markdown files to a temp dir -- no dependency on real
knowledge/champions/*_profile.md content, same convention already
established in tests/test_item_loader.py. Run with:
python -m tests.test_champion_loader
"""

import tempfile
from pathlib import Path

from src.knowledge.champion_loader import list_available_champion_profiles, load_champion_profile
from src.knowledge.champion_schema import validate_champion_profile

SAMPLE_PROFILE_MD = """# Test Champion — Draft Profile

## Roles
- Middle
- Top

## Damage Type
Hybrid

## Scaling Profile
Scales Throughout

## Strengths
- Strong 1v1 duelist
- High mobility with a dash-based kit

## Weaknesses
- Vulnerable to hard CC before he can use his ultimate
- Falls off if behind in gold

## Preferred Playstyle
Aggressive skirmisher who looks for early trades and picks, then
snowballs off kills to close out the mid game.

## Common Counters
- Malphite
- Poppy

## Favorable Matchups
- Zed
- Akali

## Synergy Champions
- Nautilus
- Leona
"""


def test_parses_full_profile_with_all_fields():
    with tempfile.TemporaryDirectory() as tmp:
        champions_dir = Path(tmp)
        (champions_dir / "testchampion_profile.md").write_text(SAMPLE_PROFILE_MD, encoding="utf-8")

        profile = load_champion_profile("TestChampion", champions_dir=champions_dir)

        assert profile["champion"] == "Test Champion"
        assert profile["roles"] == ["middle", "top"]
        assert profile["damage_type"] == "hybrid"
        assert profile["scaling_profile"] == "scales_throughout"
        assert profile["strengths"] == ["Strong 1v1 duelist", "High mobility with a dash-based kit"]
        assert profile["weaknesses"] == [
            "Vulnerable to hard CC before he can use his ultimate",
            "Falls off if behind in gold",
        ]
        assert "Aggressive skirmisher" in profile["preferred_playstyle"]
        assert profile["common_counters"] == ["Malphite", "Poppy"]
        assert profile["favorable_matchups"] == ["Zed", "Akali"]
        assert profile["synergy_champions"] == ["Nautilus", "Leona"]


def test_case_insensitive_filename_lookup():
    with tempfile.TemporaryDirectory() as tmp:
        champions_dir = Path(tmp)
        (champions_dir / "testchampion_profile.md").write_text(SAMPLE_PROFILE_MD, encoding="utf-8")

        assert load_champion_profile("testchampion", champions_dir=champions_dir) is not None
        assert load_champion_profile("TESTCHAMPION", champions_dir=champions_dir) is not None


def test_missing_file_returns_none_not_a_fabricated_profile():
    with tempfile.TemporaryDirectory() as tmp:
        assert load_champion_profile("NoSuchChampion", champions_dir=Path(tmp)) is None


def test_missing_optional_sections_default_to_honest_empty_values():
    minimal_md = "# Minimal Champion\n\n## Roles\n- Middle\n"
    with tempfile.TemporaryDirectory() as tmp:
        champions_dir = Path(tmp)
        (champions_dir / "minimal_profile.md").write_text(minimal_md, encoding="utf-8")

        profile = load_champion_profile("Minimal", champions_dir=champions_dir)

        assert profile["roles"] == ["middle"]
        assert profile["damage_type"] == "unknown"
        assert profile["scaling_profile"] == "unknown"
        assert profile["strengths"] == []
        assert profile["weaknesses"] == []
        assert profile["preferred_playstyle"] is None
        assert profile["common_counters"] == []
        assert profile["favorable_matchups"] == []
        assert profile["synergy_champions"] == []


def test_loaded_profile_is_schema_valid():
    with tempfile.TemporaryDirectory() as tmp:
        champions_dir = Path(tmp)
        (champions_dir / "testchampion_profile.md").write_text(SAMPLE_PROFILE_MD, encoding="utf-8")

        profile = load_champion_profile("TestChampion", champions_dir=champions_dir)

        assert validate_champion_profile(profile) == []


def test_invalid_role_in_file_raises_instead_of_returning_bad_data():
    # A hand-authored file that fails validation is a real authoring bug,
    # not an honestly-expected absence -- must surface loudly, not
    # silently hand back a bad dict (same "missing vs malformed" split
    # already established for LCU lockfiles: src/draft/client.py returns
    # None for no lockfile, but raises LockfileFormatError for a malformed one).
    bad_md = "# Bad Champion\n\n## Roles\n- Carry\n"
    with tempfile.TemporaryDirectory() as tmp:
        champions_dir = Path(tmp)
        (champions_dir / "badchampion_profile.md").write_text(bad_md, encoding="utf-8")

        try:
            load_champion_profile("BadChampion", champions_dir=champions_dir)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError for an invalid role in a hand-authored file")


def test_title_without_subtitle_still_extracts_champion_name():
    md = "# JustAName\n\n## Roles\n- Top\n"
    with tempfile.TemporaryDirectory() as tmp:
        champions_dir = Path(tmp)
        (champions_dir / "justaname_profile.md").write_text(md, encoding="utf-8")

        profile = load_champion_profile("JustAName", champions_dir=champions_dir)

        assert profile["champion"] == "JustAName"


def test_list_available_champion_profiles_discovers_and_sorts_deterministically():
    with tempfile.TemporaryDirectory() as tmp:
        champions_dir = Path(tmp)
        (champions_dir / "testchampion_profile.md").write_text(SAMPLE_PROFILE_MD, encoding="utf-8")
        (champions_dir / "minimal_profile.md").write_text("# Minimal Champion\n\n## Roles\n- Top\n", encoding="utf-8")
        # a coexisting, unrelated coaching-notes file must never be picked up
        (champions_dir / "testchampion.md").write_text("# Test Champion\n\n## Expected Role\nMid\n", encoding="utf-8")

        names = list_available_champion_profiles(champions_dir=champions_dir)

        assert names == ["Minimal Champion", "Test Champion"]  # sorted by filename, canonical heading names


def test_list_available_champion_profiles_missing_directory_returns_empty():
    assert list_available_champion_profiles(champions_dir=Path("does/not/exist")) == []


if __name__ == "__main__":
    test_parses_full_profile_with_all_fields()
    test_case_insensitive_filename_lookup()
    test_missing_file_returns_none_not_a_fabricated_profile()
    test_missing_optional_sections_default_to_honest_empty_values()
    test_loaded_profile_is_schema_valid()
    test_invalid_role_in_file_raises_instead_of_returning_bad_data()
    test_title_without_subtitle_still_extracts_champion_name()
    test_list_available_champion_profiles_discovers_and_sorts_deterministically()
    test_list_available_champion_profiles_missing_directory_returns_empty()
    print("All checks passed.")
