"""Rule-based item recommendation engine.

Reads a GameSnapshot (src/analysis/game_state.py) plus qualitative item
knowledge (src/knowledge/item_loader.py) and a Data Dragon item catalog
(src/riot/data_dragon.py), and produces ranked, explainable recommendations.
No AI, no paid API, no ML -- every recommendation traces back to a named
Python trigger function and a human-authored knowledge-file sentence, and
every confidence score is a sum of named, signed point contributions.

Trigger vocabulary and its keyword mapping are deliberately small and are
guesses at real-world phrasing, same caveat as macro_analyzer.py's
PATTERN_KEYWORDS -- tune once there's more real knowledge-file content to
check them against.
"""

import json
import sys
from pathlib import Path

from src.analysis.analyzer import latest_raw_match
from src.analysis.game_state import build_snapshot_from_match
from src.knowledge.item_loader import load_champion_items, load_general_items
from src.riot.data_dragon import load_item_catalog

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROFILE_PATH = PROJECT_ROOT / "data" / "player_profile.json"
DAMAGE_TYPES_PATH = PROJECT_ROOT / "data" / "static" / "champion_damage_types.json"
REPORTS_DIR = PROJECT_ROOT / "reports" / "generated_reports"

TRIGGER_KEYWORDS = {
    "enemy_ap_heavy": ["magic damage", "ap-heavy", "ap heavy"],
    "enemy_ad_heavy": ["physical damage", "ad-heavy", "ad heavy"],
    "enemy_has_sustain": ["healing", "sustain", "lifesteal"],
    "enemy_has_fed_carry": ["fed enemy carry", "fed carry", "burst threat", "burst kills"],
    "game_state_ahead": ["ahead"],
    "game_state_behind": ["behind"],
}

EVIDENCE_TEMPLATES = {
    "enemy_ap_heavy": lambda ev: f"{ev['value']} of {ev['team_size']} enemies ({', '.join(ev['champions'])}) deal primarily magic damage",
    "enemy_ad_heavy": lambda ev: f"{ev['value']} of {ev['team_size']} enemies ({', '.join(ev['champions'])}) deal primarily physical damage",
    "enemy_has_sustain": lambda ev: f"enemy sustain champions: {', '.join(ev['champions'])}",
    "enemy_has_fed_carry": lambda ev: f"fed enemy champions: {', '.join(ev['champions'])}",
    "game_state_ahead": lambda ev: f"your team is ahead (gold_diff={ev['gold_diff']}, kill_diff={ev['kill_diff']})",
    "game_state_behind": lambda ev: f"your team is behind (gold_diff={ev['gold_diff']}, kill_diff={ev['kill_diff']})",
}

# ponytail: guesses at "heavy", same caveat as the rest of this module.
AP_HEAVY_THRESHOLD = 2
AD_HEAVY_THRESHOLD = 2


def load_damage_type_table(path: Path = DAMAGE_TYPES_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        table = json.load(f)
    table.pop("_comment", None)
    return table


def _evaluate_triggers(snapshot: dict, damage_types: dict) -> tuple:
    enemy_team = snapshot["enemy_team"]
    magic_champs, physical_champs, sustain_champs, fed_champs = [], [], [], []

    for e in enemy_team:
        classification = damage_types.get(e["champion"], {})
        dtype = classification.get("damage_type", "unknown")
        if dtype in ("magic", "hybrid"):
            magic_champs.append(e["champion"])
        if dtype in ("physical", "hybrid"):
            physical_champs.append(e["champion"])
        if classification.get("sustain"):
            sustain_champs.append(e["champion"])
        if e.get("is_fed"):
            fed_champs.append(e["champion"])

    active, evidence = {}, {}

    if len(magic_champs) >= AP_HEAVY_THRESHOLD:
        active["enemy_ap_heavy"] = True
        evidence["enemy_ap_heavy"] = {"value": len(magic_champs), "team_size": len(enemy_team), "champions": magic_champs}
    if len(physical_champs) >= AD_HEAVY_THRESHOLD:
        active["enemy_ad_heavy"] = True
        evidence["enemy_ad_heavy"] = {"value": len(physical_champs), "team_size": len(enemy_team), "champions": physical_champs}
    if sustain_champs:
        active["enemy_has_sustain"] = True
        evidence["enemy_has_sustain"] = {"champions": sustain_champs}
    if fed_champs:
        active["enemy_has_fed_carry"] = True
        evidence["enemy_has_fed_carry"] = {"champions": fed_champs}
    if snapshot["game_state"] == "ahead":
        active["game_state_ahead"] = True
        evidence["game_state_ahead"] = {"gold_diff": snapshot["team_state"]["gold_diff"], "kill_diff": snapshot["team_state"]["kill_diff"]}
    if snapshot["game_state"] == "behind":
        active["game_state_behind"] = True
        evidence["game_state_behind"] = {"gold_diff": snapshot["team_state"]["gold_diff"], "kill_diff": snapshot["team_state"]["kill_diff"]}

    return active, evidence


def _match_triggers(field_text: str, active_triggers: dict) -> list:
    text = (field_text or "").lower()
    return [trigger for trigger in active_triggers if any(kw in text for kw in TRIGGER_KEYWORDS[trigger])]


def _build_candidate(item_name: str, fields: dict, source: str, active_triggers: dict, evidence: dict) -> dict | None:
    matched = _match_triggers(fields.get("valuable_when", ""), active_triggers)
    if not matched:
        return None

    conflicting = bool(_match_triggers(fields.get("bad_when", ""), active_triggers))

    breakdown = [{"factor": "trigger_matched", "points": 40}]
    if len(matched) > 1:
        breakdown.append({"factor": "additional_trigger_matched", "points": 20 * (len(matched) - 1)})
    if source == "champion_knowledge":
        breakdown.append({"factor": "champion_specific_knowledge", "points": 15})
    else:
        breakdown.append({"factor": "general_knowledge", "points": 5})
    if conflicting:
        breakdown.append({"factor": "conflicting_signal", "points": -30})

    score = max(0, min(100, sum(b["points"] for b in breakdown)))
    tier = "high" if score >= 70 else "medium" if score >= 40 else "low"

    evidence_list = [{"fact": t, **evidence[t]} for t in matched]
    evidence_str = "; ".join(EVIDENCE_TEMPLATES[t](evidence[t]) for t in matched)

    return {
        "item": item_name,
        "triggered_rules": matched,
        "evidence": evidence_list,
        "confidence_score": score,
        "confidence_tier": tier,
        "confidence_breakdown": breakdown,
        "conflicting_signal": conflicting,
        "reason": f"{item_name}: Valuable when {fields.get('valuable_when', '')}. Evidence: {evidence_str}.",
        "source": source,
    }


def _build_core_build_candidate(item_name: str, champion: str, source: str) -> dict:
    return {
        "item": item_name,
        "triggered_rules": ["core_build"],
        "evidence": [{"fact": "core_build_item", "value": True}],
        "confidence_score": 40,
        "confidence_tier": "medium",
        "confidence_breakdown": [{"factor": "core_build_item", "points": 40}],
        "conflicting_signal": False,
        "reason": f"{item_name}: default core-build item for {champion}.",
        "source": source,
    }


def _merge_core_build(champion_knowledge: dict, general_knowledge: dict) -> list:
    result = [(name, "champion_knowledge") for name in champion_knowledge.get("core_build", [])]
    seen = {n.lower() for n, _ in result}
    for name in general_knowledge.get("core_build", []):
        if name.lower() not in seen:
            result.append((name, "general_knowledge"))
    return result


def _merge_situational_items(champion_knowledge: dict, general_knowledge: dict) -> list:
    result = [(name, fields, "champion_knowledge") for name, fields in champion_knowledge.get("items", {}).items()]
    seen = {name.lower() for name, _, _ in result}
    for name, fields in general_knowledge.get("items", {}).items():
        if name.lower() not in seen:
            result.append((name, fields, "general_knowledge"))
    return result


def _merged_avoid_set(champion_knowledge: dict, general_knowledge: dict) -> set:
    return {n.lower() for n in champion_knowledge.get("avoid", {})} | {n.lower() for n in general_knowledge.get("avoid", {})}


def _cheapest_progress_component(item_entry: dict, owned_ids: set, available_gold: int, catalog: dict):
    """The most expensive not-yet-owned component the player can currently
    afford -- standard "buy the biggest piece you can afford" logic."""
    candidates = []
    for component_id in item_entry.get("from", []):
        component = catalog["items_by_id"].get(component_id)
        if component and component["id"] not in owned_ids and component["cost"] <= available_gold:
            candidates.append(component)
    return max(candidates, key=lambda c: c["cost"]) if candidates else None


def _enrich_with_catalog(candidate: dict, catalog: dict, owned_ids: set, available_gold, unrecognized: set):
    entry = catalog["items_by_name"].get(candidate["item"].lower())
    if entry is None:
        unrecognized.add(candidate["item"])
        return None
    if entry["id"] in owned_ids:
        return None

    candidate["cost"] = entry["cost"]
    candidate["builds_toward"] = None

    if available_gold is None:
        candidate["purchasable_now"] = None
    elif available_gold >= entry["cost"]:
        candidate["purchasable_now"] = True
    else:
        component = _cheapest_progress_component(entry, owned_ids, available_gold, catalog)
        if component:
            candidate["item"] = component["name"]
            candidate["builds_toward"] = entry["name"]
            candidate["cost"] = component["cost"]
            candidate["purchasable_now"] = True
            candidate["recommendation_type"] = "component"
        else:
            candidate["purchasable_now"] = False

    return candidate


def _build_save_gold_entry(available_gold: int, priority: int) -> dict:
    return {
        "item": None,
        "recommendation_type": "save_gold",
        "priority": priority,
        "reason": f"Available gold ({available_gold}) isn't enough for any recommended item or component right now -- hold gold for your next back.",
        "triggered_rules": [],
        "evidence": [{"fact": "available_gold", "value": available_gold}],
        "confidence_score": 100,
        "confidence_tier": "high",
        "confidence_breakdown": [{"factor": "gold_insufficient_for_all_candidates", "points": 100}],
        "conflicting_signal": False,
        "builds_toward": None,
        "cost": None,
        "purchasable_now": None,
        "source": "computed",
    }


def recommend_items(snapshot: dict, champion_knowledge: dict, general_knowledge: dict,
                     item_catalog: dict, damage_type_table: dict) -> dict:
    active_triggers, evidence = _evaluate_triggers(snapshot, damage_type_table)
    avoid = _merged_avoid_set(champion_knowledge, general_knowledge)
    owned_ids = {str(i) for i in snapshot["player"]["current_items"]}
    available_gold = snapshot["player"]["current_gold"]
    unrecognized = set()

    candidates = []
    for name, source in _merge_core_build(champion_knowledge, general_knowledge):
        if name.lower() not in avoid:
            candidates.append(_build_core_build_candidate(name, snapshot["champion"], source))

    for name, fields, source in _merge_situational_items(champion_knowledge, general_knowledge):
        if name.lower() in avoid:
            continue
        candidate = _build_candidate(name, fields, source, active_triggers, evidence)
        if candidate:
            candidates.append(candidate)

    enriched = []
    for candidate in candidates:
        result = _enrich_with_catalog(candidate, item_catalog, owned_ids, available_gold, unrecognized)
        if result:
            enriched.append(result)

    enriched.sort(key=lambda c: (-c["confidence_score"], -len(c["triggered_rules"]), c["item"]))
    for i, c in enumerate(enriched):
        c["priority"] = i + 1
        c.setdefault("recommendation_type", "complete_item" if i == 0 else "alternative")

    if available_gold is not None and not any(c.get("purchasable_now") for c in enriched):
        enriched.append(_build_save_gold_entry(available_gold, len(enriched) + 1))

    return {
        "champion": snapshot["champion"],
        "game_time_seconds": snapshot["game_time_seconds"],
        "player_state": {
            "current_items": [
                item_catalog["items_by_id"].get(str(i), {}).get("name", str(i))
                for i in snapshot["player"]["current_items"]
            ],
            "available_gold": available_gold,
            "game_state": snapshot["game_state"],
        },
        "recommendations": enriched,
        "unrecognized_items_flagged": sorted(unrecognized),
    }


def generate_item_recommendations(
    match: dict, game_name: str, tag_line: str, item_catalog: dict, damage_type_table: dict
) -> dict:
    """Composes GameSnapshot construction + knowledge loading + recommend_items
    into one callable.

    This is the seam src/history/importer.py calls to produce item
    recommendations as part of normal match processing -- importer.py
    contains no item-recommendation logic itself, it just calls this and
    saves the result, the same way it already calls analyze_match()/
    macro_analyze() from their own modules. main() below calls this too, so
    the composition exists in exactly one place.
    """
    snapshot = build_snapshot_from_match(match, game_name, tag_line)
    champion_knowledge = load_champion_items(snapshot["champion"])
    general_knowledge = load_general_items()
    return recommend_items(snapshot, champion_knowledge, general_knowledge, item_catalog, damage_type_table)


def main() -> None:
    with open(PROFILE_PATH, encoding="utf-8") as f:
        profile = json.load(f)
    game_name, tag_line = profile["riot_id"].split("#")

    match_path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_raw_match()
    with open(match_path, encoding="utf-8") as f:
        match = json.load(f)

    item_catalog = load_item_catalog()
    damage_type_table = load_damage_type_table()

    result = generate_item_recommendations(match, game_name, tag_line, item_catalog, damage_type_table)

    match_id = match["metadata"]["matchId"]
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{match_id}_item_recommendations.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Saved item recommendations to {out_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
