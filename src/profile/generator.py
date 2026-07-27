"""Generates the player profile summary from stored game history.

Consumes data/database/game_history.json (via src/history/store.py) and
produces reports/generated_reports/profile_summary.json. Reuses the
aggregation functions in src/history/aggregate.py rather than
re-implementing the arithmetic — this module's job is shaping that
arithmetic into the requested profile schema. Rule-based only: no AI, no
LLM calls, no coaching language.
"""

import json
from pathlib import Path

from src.history import store
from src.history.aggregate import (
    average_stats_by_champion,
    avg,
    improvement_trends,
    most_played_champions,
    repeated_strengths,
    repeated_weaknesses,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "generated_reports"


def _role_distribution(history: list) -> dict:
    total = len(history)
    if not total:
        return {}

    counts = {}
    for g in history:
        counts[g["role"]] = counts.get(g["role"], 0) + 1
    return {
        role: {"games": count, "percentage": round(count / total * 100, 1)}
        for role, count in counts.items()
    }


def _overall_average_stats(history: list) -> dict:
    return {
        "kills": avg([g["kda"]["kills"] for g in history]),
        "deaths": avg([g["deaths"] for g in history]),
        "assists": avg([g["kda"]["assists"] for g in history]),
        "cs_per_minute": avg([g["cs_per_minute"] for g in history]),
        "gold_per_minute": avg([g["gold_per_minute"] for g in history]),
        "damage_share": avg([g.get("damage_share") for g in history]),
        "vision_score": avg([g["vision_score"] for g in history]),
    }


def _most_played_with_win_rate(history: list) -> list:
    by_champion = average_stats_by_champion(history)
    return [
        {
            "champion": entry["champion"],
            "games": entry["games_played"],
            "win_rate": by_champion[entry["champion"]]["win_rate"],
        }
        for entry in most_played_champions(history)  # already sorted by games desc
    ]


def _champion_profiles(history: list) -> list:
    by_champion = average_stats_by_champion(history)
    profiles = [
        {
            "champion": champion,
            "games": stats["games_played"],
            "win_rate": stats["win_rate"],
            "average_stats": {
                "kills": stats["avg_kills"],
                "deaths": stats["avg_deaths"],
                "assists": stats["avg_assists"],
                "cs_per_minute": stats["avg_cs_per_minute"],
                "gold_per_minute": stats["avg_gold_per_minute"],
                "vision_score": stats["avg_vision_score"],
            },
        }
        for champion, stats in by_champion.items()
    ]
    return sorted(profiles, key=lambda p: p["games"], reverse=True)


def generate_profile_summary(history: list) -> dict:
    return {
        "games_played": len(history),
        "most_played_champions": _most_played_with_win_rate(history),
        "role_distribution": _role_distribution(history),
        "overall_average_stats": _overall_average_stats(history),
        "champion_profiles": _champion_profiles(history),
        "strength_patterns": repeated_strengths(history),
        "weakness_patterns": repeated_weaknesses(history),
        "recent_trends": improvement_trends(history),
    }


def main() -> None:
    history = store.load_history()
    summary = generate_profile_summary(history)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "profile_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved player profile summary to {out_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
