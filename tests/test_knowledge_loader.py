"""Self-check for src/knowledge/loader.py's markdown parsing.

No API calls. Run with: python -m tests.test_knowledge_loader
"""

from src.knowledge.loader import load_champion, load_role


def test_load_champion_parses_sections():
    yone = load_champion("Yone")
    assert yone is not None
    assert yone["expected_role"] == "Mid Lane (secondary: Top Lane)"
    assert any("CS per minute" in m for m in yone["important_metrics"])
    assert len(yone["common_mistakes"]) > 0
    assert len(yone["improvement_categories"]) > 0


def test_load_champion_case_insensitive():
    assert load_champion("akali") is not None
    assert load_champion("AKALI") is not None


def test_load_champion_missing_returns_none():
    assert load_champion("NotARealChampion") is None


def test_load_role_maps_riot_position_names():
    mid = load_role("MIDDLE")
    support = load_role("UTILITY")
    assert mid is not None
    assert support is not None
    assert any("vision score" in m.lower() for m in support["important_metrics"])


def test_load_role_missing_returns_none():
    assert load_role("JUNGLE") is None  # no knowledge/roles/jungle.md yet


if __name__ == "__main__":
    test_load_champion_parses_sections()
    test_load_champion_case_insensitive()
    test_load_champion_missing_returns_none()
    test_load_role_maps_riot_position_names()
    test_load_role_missing_returns_none()
    print("All checks passed.")
