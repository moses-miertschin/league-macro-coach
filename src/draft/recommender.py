"""Deterministic draft recommendation engine -- reads a DraftSnapshot
(src/draft/snapshot.py) plus champion knowledge
(src/knowledge/champion_loader.py) and produces native shared-schema
(src/recommendations/schema.py) entries.

Two independent behaviors, dispatched from recommend_draft() on whether
current_player.champion_id is locked in yet:

1. Locked-champion informational callouts (current_player.champion_id is
   set) -- unchanged since this module's first version. Only surfaces
   facts the current player's own champion profile already states about
   itself: an enemy pick that's a common_counters entry
   ("counter_warning"), an enemy pick that's a favorable_matchups entry
   ("favorable_matchup"), or an ally pick that's a synergy_champions entry
   ("ally_synergy"). recommendation stays null on every entry -- these are
   warnings/callouts, not prescriptions.

2. Pre-lock pick recommendations (current_player.champion_id is None) --
   recommends *which* champion to consider. Candidates are the authored
   champion profiles that support the current player's assigned role and
   aren't already picked or banned by either team, ranked by a small,
   fully-inspectable point score built only from authored facts: role fit
   is a required filter, not scored; damage balance and direct synergy
   (both ally-side) and favorable-matchup/common-counter-risk (both
   enemy-side, added in the pre-lock signals stage) are the only scored
   signals. category: "pick_recommendation", recommendation: the
   candidate's own name.

   The two enemy-side signals read *only* the candidate's own profile
   against currently locked enemy picks -- never the enemy's own profile,
   and never an inferred/reversed relationship (a locked enemy whose own
   profile happens to list the candidate is irrelevant; only what the
   candidate's profile says about that enemy matters).

No cross-champion scoring beyond what's described above, no full 5v5
team-composition analysis, no win rates, no scraped statistics, no AI, no
hidden weights, no counter matrices -- that broader analysis is explicitly
knowledge/drafting/'s future job (ROADMAP.md Sec.4 step 4), not this one.

Emits native shared-schema output directly -- draft has no legacy shape to
preserve (RECOMMENDATION_SYSTEM_DESIGN.md Sec.4). Every entry is validated
with validate_recommendation() before being returned; a malformed entry
here would be a bug in this module, not an honestly-expected absence, so
it raises rather than silently degrading -- the same discipline
champion_loader.py already applies to its own output. Nothing in this
module mutates its snapshot/champion_catalog/profile inputs.
"""

from src.knowledge.champion_loader import list_available_champion_profiles, load_champion_profile
from src.recommendations.schema import validate_recommendation
from src.riot.data_dragon import champion_name_from_id

_SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}

# Pick-recommendation scoring -- small, named, fully inspectable. No
# win-rate-derived or otherwise invented weighting; these are the only
# scored signals per this project's explicit scope.
DAMAGE_BALANCE_BONUS = 2
DIRECT_SYNERGY_BONUS = 1
FAVORABLE_ENEMY_MATCHUP_BONUS = 1  # candidate's own profile lists a locked enemy as a favorable matchup
COMMON_COUNTER_RISK_PENALTY = 1  # candidate's own profile lists a locked enemy as one of its own common_counters
MIN_LOCKED_ALLIES_FOR_DAMAGE_SIGNAL = 2  # fewer known-damage-type allies than this -- insufficient data, no bonus
TOP_N_PICK_RECOMMENDATIONS = 3


def _resolve_names(champion_ids: list, champion_catalog: dict) -> list:
    """Never guesses -- an id the catalog doesn't recognize is dropped, not
    invented. Order-preserving; may be shorter than the input."""
    names = []
    for champion_id in champion_ids:
        name = champion_name_from_id(champion_catalog, champion_id)
        if name is not None:
            names.append(name)
    return names


def _resolve_names_with_unresolved(champion_ids: list, champion_catalog: dict) -> tuple:
    """Same resolution as _resolve_names(), but also reports which ids
    didn't resolve -- used only by the pick-recommendation path, which
    needs to report details.unresolved_ally_ids honestly rather than
    silently dropping them."""
    names = []
    unresolved = []
    for champion_id in champion_ids:
        name = champion_name_from_id(champion_catalog, champion_id)
        if name is not None:
            names.append(name)
        else:
            unresolved.append(champion_id)
    return names, unresolved


def _finalize(entries: list) -> list:
    """Assigns priority 1..n (entries must already be in final order) and
    validates every entry -- shared tail for both recommend_draft() paths."""
    for i, entry in enumerate(entries, start=1):
        entry["priority"] = i
        errors = validate_recommendation(entry)
        if errors:
            raise ValueError(f"recommend_draft() built an invalid recommendation entry: {errors} ({entry!r})")
    return entries


# ---------------------------------------------------------------------------
# Locked-champion informational callouts (unchanged behavior)
# ---------------------------------------------------------------------------


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


def _recommend_for_locked_champion(snapshot: dict, current_player: dict, champion_catalog: dict, profile_loader_fn) -> list:
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
    return _finalize(entries)


# ---------------------------------------------------------------------------
# Pre-lock pick recommendations
# ---------------------------------------------------------------------------


def _unavailable_pick_entry(subject: str, reason: str, details: dict | None = None) -> dict:
    return {
        "system": "draft",
        "category": "pick_recommendation",
        "subject": subject,
        "recommendation": None,
        "reason": reason,
        "evidence": [],
        "confidence": "unavailable",
        "confidence_score": None,
        "severity": "unavailable",
        "source": "champion_knowledge",
        "details": details or {},
    }


def _locked_ally_damage_counts(ally_names: list, profile_loader_fn) -> tuple:
    """Counts locked allies' damage types (physical/magic/hybrid only --
    "unknown" contributes to nothing, since nothing can be reasoned from
    it). Also reports which ally names have no authored profile at all, so
    the caller can report details.missing_ally_profiles honestly."""
    counts = {"physical": 0, "magic": 0, "hybrid": 0}
    missing_profiles = []
    for name in ally_names:
        profile = profile_loader_fn(name)
        if profile is None:
            missing_profiles.append(name)
            continue
        damage_type = profile["damage_type"]
        if damage_type in counts:
            counts[damage_type] += 1
    return counts, missing_profiles


def _damage_balance_need(counts: dict) -> str | None:
    """Returns "magic" (team leans physical), "physical_or_hybrid" (team
    leans magic), or None -- when the known composition is balanced or
    there isn't enough known data to say anything. Never invents a need."""
    known_total = counts["physical"] + counts["magic"] + counts["hybrid"]
    if known_total < MIN_LOCKED_ALLIES_FOR_DAMAGE_SIGNAL:
        return None  # insufficient data
    if counts["physical"] > counts["magic"]:
        return "magic"
    if counts["magic"] > counts["physical"]:
        return "physical_or_hybrid"
    return None  # balanced


def _damage_balance_score(candidate_damage_type: str, need: str | None) -> int:
    if need == "magic" and candidate_damage_type == "magic":
        return DAMAGE_BALANCE_BONUS
    if need == "physical_or_hybrid" and candidate_damage_type in ("physical", "hybrid"):
        return DAMAGE_BALANCE_BONUS
    return 0


def _direct_synergy_score(candidate_profile: dict, locked_ally_names: list) -> tuple:
    matches = [ally for ally in locked_ally_names if ally in candidate_profile["synergy_champions"]]
    return (DIRECT_SYNERGY_BONUS, matches) if matches else (0, [])


def _favorable_enemy_matchup_score(candidate_profile: dict, locked_enemy_names: list) -> tuple:
    """Reads only the candidate's own favorable_matchups -- never the
    enemy's profile, never an inferred/reversed relationship."""
    matches = [enemy for enemy in locked_enemy_names if enemy in candidate_profile["favorable_matchups"]]
    return (FAVORABLE_ENEMY_MATCHUP_BONUS, matches) if matches else (0, [])


def _common_counter_risk_score(candidate_profile: dict, locked_enemy_names: list) -> tuple:
    """Reads only the candidate's own common_counters -- a locked enemy
    that's a known counter *to the candidate*. Never the enemy's profile."""
    matches = [enemy for enemy in locked_enemy_names if enemy in candidate_profile["common_counters"]]
    return (COMMON_COUNTER_RISK_PENALTY, matches) if matches else (0, [])


def _build_pick_entry(
    name: str, profile: dict, assigned_role: str, damage_need, damage_counts: dict,
    ally_names: list, unresolved_ally_ids: list, missing_ally_profiles: list,
    enemy_names: list, unresolved_enemy_ids: list,
) -> dict:
    damage_score = _damage_balance_score(profile["damage_type"], damage_need)
    synergy_score, synergy_matches = _direct_synergy_score(profile, ally_names)
    favorable_score, favorable_matches = _favorable_enemy_matchup_score(profile, enemy_names)
    counter_risk_score, counter_risk_matches = _common_counter_risk_score(profile, enemy_names)
    total = damage_score + synergy_score + favorable_score - counter_risk_score

    evidence = [{"fact": "role_fit", "champion": name, "role": assigned_role}]
    if damage_score:
        evidence.append({
            "fact": "damage_balance",
            "candidate_damage_type": profile["damage_type"],
            "ally_damage_counts": dict(damage_counts),
        })
    if synergy_matches:
        evidence.append({"fact": "direct_synergy", "synergizes_with": list(synergy_matches)})
    if favorable_matches:
        evidence.append({"fact": "favorable_enemy_matchup", "favorable_against": list(favorable_matches)})
    if counter_risk_matches:
        evidence.append({"fact": "common_counter_risk", "countered_by": list(counter_risk_matches)})

    reason_parts = [f"{name} plays {assigned_role}."]
    if damage_score:
        reason_parts.append(
            f"{name}'s {profile['damage_type']} damage helps balance a locked team that currently leans away from it."
        )
    if synergy_matches:
        reason_parts.append(f"{name} has authored synergy with {', '.join(synergy_matches)}.")
    if favorable_matches:
        reason_parts.append(
            f"{name} has an authored favorable matchup against {', '.join(favorable_matches)}, already on the enemy team."
        )
    if counter_risk_matches:
        reason_parts.append(
            f"{name} is known to be countered by {', '.join(counter_risk_matches)}, already on the enemy team."
        )

    if total >= DAMAGE_BALANCE_BONUS + DIRECT_SYNERGY_BONUS:
        severity = "high"
    elif total > 0:
        severity = "medium"
    else:
        severity = "low"

    return {
        "system": "draft",
        "category": "pick_recommendation",
        "subject": name,
        "recommendation": name,
        "reason": " ".join(reason_parts),
        "evidence": evidence,
        "confidence": "high",
        "confidence_score": None,
        "severity": severity,
        "source": "champion_knowledge",
        "details": {
            "player_role": assigned_role,
            "score_breakdown": {
                "role_fit": "required",
                "damage_balance": damage_score,
                "direct_synergy": synergy_score,
                "favorable_enemy_matchup": favorable_score,
                "common_counter_risk": counter_risk_score,
                "total": total,
            },
            "strengths": list(profile["strengths"]),
            "preferred_playstyle": profile["preferred_playstyle"],
            "unresolved_ally_ids": list(unresolved_ally_ids),
            "missing_ally_profiles": list(missing_ally_profiles),
            "unresolved_enemy_ids": list(unresolved_enemy_ids),
            "locked_enemy_names": list(enemy_names),
        },
    }


def _recommend_champion_picks(
    snapshot: dict, current_player: dict, champion_catalog: dict, profile_loader_fn, candidate_names,
) -> list:
    assigned_role = current_player.get("assigned_position")
    if not assigned_role:
        return _finalize([_unavailable_pick_entry(
            subject="role_unavailable",
            reason="The current player's assigned role isn't known yet, so pick recommendations can't be filtered by role fit.",
        )])

    names = candidate_names if candidate_names is not None else list_available_champion_profiles()

    excluded = set()
    for key in ("ally_picks", "enemy_picks", "ally_bans", "enemy_bans"):
        excluded |= set(_resolve_names(snapshot.get(key, []), champion_catalog))

    ally_names, unresolved_ally_ids = _resolve_names_with_unresolved(snapshot.get("ally_picks", []), champion_catalog)
    damage_counts, missing_ally_profiles = _locked_ally_damage_counts(ally_names, profile_loader_fn)
    damage_need = _damage_balance_need(damage_counts)

    enemy_names, unresolved_enemy_ids = _resolve_names_with_unresolved(snapshot.get("enemy_picks", []), champion_catalog)
    enemy_names = list(dict.fromkeys(enemy_names))  # dedupe -- never double-count a repeated champion

    candidates = []
    for name in names:
        if name in excluded:
            continue
        profile = profile_loader_fn(name)
        if profile is None:
            continue  # never invent a profile
        if assigned_role not in profile["roles"]:
            continue  # role fit is required, not a bonus
        candidates.append((name, profile))

    if not candidates:
        return _finalize([_unavailable_pick_entry(
            subject="no_eligible_candidates",
            reason=f"No authored champion profile supports the {assigned_role} role after excluding champions already picked or banned.",
            details={
                "player_role": assigned_role,
                "unresolved_ally_ids": unresolved_ally_ids,
                "missing_ally_profiles": missing_ally_profiles,
                "unresolved_enemy_ids": unresolved_enemy_ids,
                "locked_enemy_names": enemy_names,
            },
        )])

    entries = [
        _build_pick_entry(
            name, profile, assigned_role, damage_need, damage_counts,
            ally_names, unresolved_ally_ids, missing_ally_profiles,
            enemy_names, unresolved_enemy_ids,
        )
        for name, profile in candidates
    ]

    entries.sort(key=lambda e: (-e["details"]["score_breakdown"]["total"], e["subject"]))
    entries = entries[:TOP_N_PICK_RECOMMENDATIONS]

    return _finalize(entries)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def recommend_draft(
    snapshot: dict | None,
    champion_catalog: dict,
    profile_loader_fn=load_champion_profile,
    candidate_names: list | None = None,
) -> list:
    if not snapshot:
        return []

    current_player = snapshot.get("current_player")
    if not current_player:
        return []

    if current_player.get("champion_id") is None:
        return _recommend_champion_picks(snapshot, current_player, champion_catalog, profile_loader_fn, candidate_names)

    return _recommend_for_locked_champion(snapshot, current_player, champion_catalog, profile_loader_fn)
