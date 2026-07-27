"""Rule-based macro pattern detection over structured match analysis.

Reads a structured analysis JSON (produced by src/analysis/analyzer.py) and
applies fixed threshold rules to flag possible macro situations. No AI
generation, no coaching language — output is pattern labels, raw numbers,
and confidence levels only.

Some requested checks (deaths relative to objective timing, deaths after an
extended period without recalling, objective-fight presence, vision score
compared to the enemy laner) originally needed per-event match timeline
data or opponent stats that structured analysis alone doesn't capture.
Two of them — deaths_before_objectives and objective_fight_presence — are
now computed for real when a `timeline_result` (from
src/analysis/timeline_analyzer.py) is passed in. The other two stay
`confidence="unavailable"` even with a timeline: Riot's timeline has no
recall event at all (not a missing-data problem, a doesn't-exist one), and
comparing vision to the enemy laner needs their match-detail stats, which
is unrelated to the timeline. Whenever real data genuinely isn't available,
that's what's reported — never a faked result standing in for it.

Champion and role knowledge (knowledge/champions/*.md, knowledge/roles/*.md)
is loaded via src/knowledge/loader.py and used to de-prioritize metrics a
given champion/role explicitly calls out as expected to be low (e.g. CS/min
for Pyke) — a pattern that would otherwise be flagged as low is still
reported, but no longer counted as a concern. The knowledge files are
qualitative (no numeric thresholds), so this is the only adjustment they
currently drive; per-champion/role numeric benchmarks are a future step.
"""

import json
from pathlib import Path

from src.analysis.timeline_analyzer import analyze_timeline
from src.knowledge.loader import load_champion, load_role

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "generated_reports"
TIMELINES_DIR = PROJECT_ROOT / "data" / "raw_matches" / "timelines"

# ponytail: keyword match against knowledge markdown prose, not a formal
# taxonomy. Extend as new pattern keys or metric phrasings are added.
PATTERN_KEYWORDS = {
    "death_count": ["death"],
    "cs_per_minute": ["cs per minute", "cs/min"],
    "gold_per_minute": ["gold"],
    "kill_participation": ["kill participation"],
    "damage_to_objectives": ["damage to objectives", "objective damage"],
    "vision_score_per_minute": ["vision"],
}

# ponytail: static, role-agnostic rule-of-thumb thresholds, not tuned per
# rank/role/champion yet. Revisit once enough games are logged to derive
# personal or rank-appropriate baselines instead of guessing them.
BENCHMARKS = {
    "cs_per_minute": {"low": 6.0, "good": 8.0},
    "gold_per_minute": {"low": 350, "good": 450},
    "vision_score_per_minute": {"low": 0.8, "good": 1.2},
    "damage_to_objectives": {"low": 2000, "good": 5000},
    "kill_participation": {"low": 0.5, "good": 0.65},
    "objective_fight_presence": {"low": 0.3, "good": 0.6},
}
HIGH_DEATH_COUNT = 8
# ponytail: another guess, same caveat as the rest of BENCHMARKS above.
DEATHS_BEFORE_OBJECTIVES_CONCERN = 2


def _tier(value, low, good):
    if value is None:
        return "unknown"
    if value < low:
        return "low"
    if value >= good:
        return "good"
    return "adequate"


def analyze_deaths(analysis: dict, timeline_result: dict | None = None) -> list:
    deaths = analysis["kda"]["deaths"]
    death_tier = "high" if deaths >= HIGH_DEATH_COUNT else "normal"
    patterns = [
        {
            "category": "deaths",
            "pattern": "death_count",
            "value": deaths,
            "confidence": "high",
            "detail": f"{deaths} deaths this game",
            "concern": death_tier == "high",
            "tier": death_tier,
        }
    ]

    if timeline_result is not None:
        before_obj = timeline_result["deaths_before_objectives"]
        before_obj_tier = "high" if before_obj >= DEATHS_BEFORE_OBJECTIVES_CONCERN else "normal"
        patterns.append(
            {
                "category": "deaths",
                "pattern": "deaths_before_objectives",
                "value": before_obj,
                "confidence": "high",
                "detail": f"{before_obj} death(s) shortly before a dragon/baron/tower fell",
                "concern": before_obj_tier == "high",
                "tier": before_obj_tier,
            }
        )
    else:
        patterns.append(
            {
                "category": "deaths",
                "pattern": "deaths_before_objectives",
                "value": None,
                "confidence": "unavailable",
                "detail": "requires match timeline data (event timestamps) — not retrieved for this match",
                "concern": None,
                "tier": None,
            }
        )

    patterns.append(
        {
            "category": "deaths",
            "pattern": "deaths_after_extended_no_recall",
            "value": None,
            "confidence": "unavailable",
            "detail": "Riot's match timeline has no recall event — not measurable even with timeline data",
            "concern": None,
            "tier": None,
        }
    )

    return patterns


def analyze_farming(analysis: dict) -> list:
    cs_pm = analysis["cs_per_minute"]
    duration_minutes = analysis["game_duration_seconds"] / 60
    gold_pm = round(analysis["gold_earned"] / duration_minutes, 2) if duration_minutes else None

    cs_tier = _tier(cs_pm, **BENCHMARKS["cs_per_minute"])
    gold_tier = _tier(gold_pm, **BENCHMARKS["gold_per_minute"])

    return [
        {
            "category": "farming",
            "pattern": "cs_per_minute",
            "value": cs_pm,
            "confidence": "high",
            "detail": cs_tier,
            "concern": cs_tier == "low",
            "tier": cs_tier,
        },
        {
            "category": "farming",
            "pattern": "gold_per_minute",
            "value": gold_pm,
            "confidence": "high",
            "detail": f"{gold_tier} (gold/min, a rough efficiency proxy — not itemization-aware)",
            "concern": gold_tier == "low",
            "tier": gold_tier,
        },
    ]


def analyze_objectives(analysis: dict, timeline_result: dict | None = None) -> list:
    kp = analysis["objectives_participation"]["kill_participation"]
    dmg_obj = analysis["objectives_participation"]["damage_to_objectives"]

    kp_tier = _tier(kp, **BENCHMARKS["kill_participation"])
    dmg_tier = _tier(dmg_obj, **BENCHMARKS["damage_to_objectives"])

    patterns = [
        {
            "category": "objectives",
            "pattern": "kill_participation",
            "value": kp,
            "confidence": "medium",
            "detail": f"{kp_tier} (overall kill participation, not specific to dragon/baron presence)",
            "concern": kp_tier == "low",
            "tier": kp_tier,
        },
        {
            "category": "objectives",
            "pattern": "damage_to_objectives",
            "value": dmg_obj,
            "confidence": "high",
            "detail": dmg_tier,
            "concern": dmg_tier == "low",
            "tier": dmg_tier,
        },
    ]

    if timeline_result is not None:
        participation = timeline_result["objective_participation"]
        total = sum(v["total"] for v in participation.values())
        participated = sum(v["participated"] for v in participation.values())
        rate = round(participated / total, 2) if total else None
        rate_tier = _tier(rate, **BENCHMARKS["objective_fight_presence"])
        patterns.append(
            {
                "category": "objectives",
                "pattern": "objective_fight_presence",
                "value": rate,
                "confidence": "high",
                "detail": f"{rate_tier} ({participated} of {total} dragon/baron/tower takedowns credited)",
                "concern": rate_tier == "low",
                "tier": rate_tier,
            }
        )
    else:
        patterns.append(
            {
                "category": "objectives",
                "pattern": "objective_fight_presence",
                "value": None,
                "confidence": "unavailable",
                "detail": "requires match timeline data (who was present at each objective takedown) — not retrieved for this match",
                "concern": None,
                "tier": None,
            }
        )

    return patterns


def analyze_vision(analysis: dict) -> list:
    duration_minutes = analysis["game_duration_seconds"] / 60
    vision_pm = (
        round(analysis["vision_score"] / duration_minutes, 2) if duration_minutes else None
    )
    vision_tier = _tier(vision_pm, **BENCHMARKS["vision_score_per_minute"])

    return [
        {
            "category": "vision",
            "pattern": "vision_score_per_minute",
            "value": vision_pm,
            "confidence": "medium",
            "detail": f"{vision_tier} (compared to a static benchmark, not the enemy laner)",
            "concern": vision_tier == "low",
            "tier": vision_tier,
        },
        {
            "category": "vision",
            "pattern": "vision_score_vs_enemy_laner",
            "value": None,
            "confidence": "unavailable",
            "detail": "requires enemy laner's vision score — not currently captured in structured analysis",
            "concern": None,
            "tier": None,
        },
    ]


def _is_deprioritized(pattern_key: str, knowledge: dict | None) -> bool:
    if not knowledge:
        return False
    text = " ".join(knowledge.get("metrics_that_matter_less", [])).lower()
    return any(keyword in text for keyword in PATTERN_KEYWORDS.get(pattern_key, []))


def _apply_knowledge_context(patterns: list, champion_knowledge: dict | None, role_knowledge: dict | None) -> None:
    for p in patterns:
        if p["concern"] is not True:
            continue
        if _is_deprioritized(p["pattern"], champion_knowledge) or _is_deprioritized(p["pattern"], role_knowledge):
            p["concern"] = False
            p["detail"] += " — deprioritized for this champion/role, not counted as a concern"


def macro_analyze(analysis: dict, timeline_result: dict | None = None) -> dict:
    patterns = (
        analyze_deaths(analysis, timeline_result)
        + analyze_farming(analysis)
        + analyze_objectives(analysis, timeline_result)
        + analyze_vision(analysis)
    )

    champion_knowledge = load_champion(analysis["champion"]) if analysis.get("champion") else None
    role_knowledge = load_role(analysis["role"]) if analysis.get("role") else None
    _apply_knowledge_context(patterns, champion_knowledge, role_knowledge)

    improvement_areas = [p["pattern"] for p in patterns if p["concern"] is True]
    measured = [p for p in patterns if p["confidence"] != "unavailable"]
    overall_confidence = "high" if len(measured) == len(patterns) else "partial"

    return {
        "match_id": analysis["match_id"],
        "champion_context_loaded": champion_knowledge is not None,
        "role_context_loaded": role_knowledge is not None,
        "detected_patterns": patterns,
        "possible_improvement_areas": improvement_areas,
        "confidence_level": overall_confidence,
    }


def latest_structured_analysis() -> Path:
    reports = sorted(REPORTS_DIR.glob("*_analysis.json"), key=lambda p: p.stat().st_mtime)
    if not reports:
        raise RuntimeError(f"No structured analysis files found in {REPORTS_DIR}")
    return reports[-1]


def main() -> None:
    analysis_path = latest_structured_analysis()
    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    timeline_result = None
    timeline_path = TIMELINES_DIR / f"{analysis['match_id']}_timeline.json"
    if timeline_path.exists():
        with open(timeline_path, encoding="utf-8") as f:
            timeline = json.load(f)
        timeline_result = analyze_timeline(timeline, analysis["participant_id"])

    result = macro_analyze(analysis, timeline_result)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{result['match_id']}_macro_patterns.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Saved macro pattern analysis to {out_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
