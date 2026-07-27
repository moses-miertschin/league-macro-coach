"""Rule-based aggregation over stored game history.

No AI, no advice text — every function here is arithmetic over
src/history/store.py records: counts, averages, and comparisons.
"""

from collections import Counter, defaultdict


def avg(values: list) -> float | None:
    values = [v for v in values if v is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _stats_block(games: list) -> dict:
    wins = sum(1 for g in games if g["win"])
    return {
        "games_played": len(games),
        "win_rate": round(wins / len(games), 2) if games else None,
        "avg_kills": avg([g["kda"]["kills"] for g in games]),
        "avg_deaths": avg([g["deaths"] for g in games]),
        "avg_assists": avg([g["kda"]["assists"] for g in games]),
        "avg_cs_per_minute": avg([g["cs_per_minute"] for g in games]),
        "avg_gold_per_minute": avg([g["gold_per_minute"] for g in games]),
        "avg_kill_participation": avg([g["kill_participation"] for g in games]),
        "avg_damage": avg([g["damage"] for g in games]),
        "avg_vision_score": avg([g["vision_score"] for g in games]),
    }


def most_played_champions(history: list) -> list:
    counts = Counter(g["champion"] for g in history)
    return [{"champion": champ, "games_played": count} for champ, count in counts.most_common()]


def average_stats_by_champion(history: list) -> dict:
    by_champion = defaultdict(list)
    for g in history:
        by_champion[g["champion"]].append(g)
    return {champ: _stats_block(games) for champ, games in by_champion.items()}


def average_stats_by_role(history: list) -> dict:
    by_role = defaultdict(list)
    for g in history:
        by_role[g["role"]].append(g)
    return {role: _stats_block(games) for role, games in by_role.items()}


def _repeated_patterns(history: list, predicate, min_occurrences: int) -> list:
    counts = Counter()
    categories = {}
    for g in history:
        for p in g.get("detected_patterns", []):
            if predicate(p):
                counts[p["pattern"]] += 1
                categories[p["pattern"]] = p["category"]

    matches = [
        {
            "pattern": pattern,
            "category": categories[pattern],
            "games_flagged": count,
            "rate": round(count / len(history), 2) if history else None,
        }
        for pattern, count in counts.items()
        if count >= min_occurrences
    ]
    return sorted(matches, key=lambda m: m["games_flagged"], reverse=True)


def repeated_weaknesses(history: list, min_occurrences: int = 2) -> list:
    return _repeated_patterns(history, lambda p: p["concern"] is True, min_occurrences)


def repeated_strengths(history: list, min_occurrences: int = 2) -> list:
    return _repeated_patterns(history, lambda p: p.get("tier") == "good", min_occurrences)


def improvement_trends(history: list) -> dict:
    if len(history) < 2:
        return {
            "status": "insufficient_data",
            "detail": f"Need at least 2 games to compare trends, have {len(history)}.",
        }

    # ponytail: splits history in half by timestamp (earlier vs. later) as a
    # simple trend proxy. A real trendline (e.g. rolling average, slope) can
    # replace this once there's enough history for it to be worth the math.
    ordered = sorted(history, key=lambda g: g.get("game_start_timestamp") or 0)
    midpoint = len(ordered) // 2
    earlier_stats = _stats_block(ordered[:midpoint])
    later_stats = _stats_block(ordered[midpoint:])

    change = {}
    for metric in (
        "avg_deaths",
        "avg_cs_per_minute",
        "avg_gold_per_minute",
        "avg_kill_participation",
        "avg_vision_score",
    ):
        before, after = earlier_stats[metric], later_stats[metric]
        change[metric] = round(after - before, 2) if before is not None and after is not None else None

    return {
        "status": "ok",
        "earlier_games": earlier_stats["games_played"],
        "later_games": later_stats["games_played"],
        "change": change,
    }


