"""First deterministic draft recommendation engine -- reads a DraftSnapshot
(src/draft/snapshot.py) plus champion knowledge
(src/knowledge/champion_loader.py) and produces native shared-schema
(src/recommendations/schema.py) entries.

Scope, per this checkpoint's explicit instruction: only the fact-lookup
signals the current player's own champion profile already states about
itself -- "this enemy pick is one of my counters," "this enemy pick is a
favorable matchup for me," "this ally pick has synergy with me." No
cross-champion scoring, no full-team synergy/counter analysis (that is
knowledge/drafting/'s job, per ROADMAP.md Sec.4 step 4, not started), no
pick/ban prescriptions -- the underlying facts already exist as flat
champion-name lists on the current player's own champion_profile, so this
is a lookup-and-translate layer, not a new scoring algorithm.

Emits native shared-schema output directly -- draft has no legacy shape to
preserve (RECOMMENDATION_SYSTEM_DESIGN.md Sec.4), so unlike item/macro
this never needs an adapter. Every entry is validated with
validate_recommendation() before being returned; a malformed entry here
would be a bug in this module, not an honestly-expected absence, so it
raises rather than silently degrading -- the same discipline
champion_loader.py already applies to its own output.
"""

from src.knowledge.champion_loader import load_champion_profile
from src.recommendations.schema import validate_recommendation
from src.riot.data_dragon import champion_name_from_id

_SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def _resolve_names(champion_ids: list, champion_catalog: dict) -> list:
    """Never guesses -- an id the catalog doesn't recognize is dropped, not
    invented. Order-preserving; may be shorter than the input."""
    names = []
    for champion_id in champion_ids:
        name = champion_name_from_id(champion_catalog, champion_id)
        if name is not None:
            names.append(name)
    return names


def _build_entry(*, category: str, subject: str, reason: str, evidence: list, severity: str, player_role) -> dict:
    return {
        "system": "draft",
        "category": category,
        "subject": subject,
        "recommendation": None,
        "reason": reason,
        "evidence": evidence,
        "confidence": "high",  # hand-curated champion knowledge -- same trust level item_recommender.py gives champion_knowledge-sourced facts
        "confidence_score": None,  # qualitative fact lookup, not a computed score
        "severity": severity,
        "source": "champion_knowledge",
        "details": {"player_role": player_role},
    }


def recommend_draft(snapshot: dict | None, champion_catalog: dict, profile_loader_fn=load_champion_profile) -> list:
    if not snapshot:
        return []

    current_player = snapshot.get("current_player")
    if not current_player or current_player.get("champion_id") is None:
        return []  # nothing locked in yet -- honestly nothing to recommend

    player_champion = champion_name_from_id(champion_catalog, current_player["champion_id"])
    if player_champion is None:
        return []  # unrecognized champion id -- never guess

    player_profile = profile_loader_fn(player_champion)
    if player_profile is None:
        return []  # no authored knowledge for this champion yet

    player_role = current_player.get("assigned_position")
    enemy_names = _resolve_names(snapshot.get("enemy_picks", []), champion_catalog)
    ally_names = _resolve_names(snapshot.get("ally_picks", []), champion_catalog)

    entries = []

    for enemy in enemy_names:
        if enemy in player_profile["common_counters"]:
            entries.append(_build_entry(
                category="counter_warning",
                subject=enemy,
                reason=f"{enemy} is a known counter to {player_champion}.",
                evidence=[{"fact": "common_counter", "champion": enemy, "player_champion": player_champion}],
                severity="high",
                player_role=player_role,
            ))
        if enemy in player_profile["favorable_matchups"]:
            entries.append(_build_entry(
                category="favorable_matchup",
                subject=enemy,
                reason=f"{enemy} is a favorable matchup for {player_champion}.",
                evidence=[{"fact": "favorable_matchup", "champion": enemy, "player_champion": player_champion}],
                severity="low",
                player_role=player_role,
            ))

    for ally in ally_names:
        if ally in player_profile["synergy_champions"]:
            entries.append(_build_entry(
                category="ally_synergy",
                subject=ally,
                reason=f"{ally} has strong synergy with {player_champion}.",
                evidence=[{"fact": "synergy_champion", "champion": ally, "player_champion": player_champion}],
                severity="medium",
                player_role=player_role,
            ))

    entries.sort(key=lambda e: _SEVERITY_WEIGHT.get(e["severity"], 0), reverse=True)
    for i, entry in enumerate(entries, start=1):
        entry["priority"] = i
        errors = validate_recommendation(entry)
        if errors:
            raise ValueError(f"recommend_draft() built an invalid recommendation entry: {errors} ({entry!r})")

    return entries
