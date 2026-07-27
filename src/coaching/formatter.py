"""Renders a coaching_session.json dict as plain terminal text.

Pure presentation -- no thresholds, no filtering, no re-ranking, no
decision-making of any kind. Every value printed here already exists in the
session dict; this module only decides how it looks, never what it means.
"""


def format_session(session: dict) -> str:
    lines = [
        f"Coaching Report -- {session.get('champion', 'Unknown')} ({session.get('game_result', 'Unknown')})",
        f"Player: {session.get('player', 'unknown')}",
        "",
    ]

    lessons = session.get("main_lessons", [])
    if lessons:
        lines.append("Top Priorities:")
        for lesson in lessons:
            lines.append(f"  {lesson['priority']}. {lesson['issue']} [{lesson.get('scope', 'unknown')} / {lesson.get('confidence', 'unknown')}]")
            lines.append(f"     Why: {lesson['why_it_matters']}")
            for ev in lesson.get("evidence", []):
                lines.append(f"     Evidence: {ev}")
            lines.append(f"     Practice: {lesson['practice_goal']}")
    else:
        lines.append("No priority issues flagged -- strong game.")

    strengths = session.get("strengths", [])
    if strengths:
        lines.append("")
        lines.append("Strengths:")
        for s in strengths:
            lines.append(f"  - {s.get('pattern')}: {s.get('evidence')} (confidence: {s.get('confidence')})")

    item_review = session.get("item_review", {})
    lines.append("")
    if item_review.get("status") == "available":
        lines.append("Item Recommendations:")
        for rec in item_review.get("top_recommendations", []):
            lines.append(f"  - {rec.get('item')}: {rec.get('reason')}")
    else:
        lines.append(f"Item Recommendations: unavailable ({item_review.get('detail', 'no data')})")

    benchmark = session.get("benchmark", {})
    lines.append("")
    if benchmark.get("status") == "available":
        source = benchmark.get("benchmark_source", {})
        lines.append(f"Benchmark Comparison ({source.get('rank', 'unknown')}, patch {source.get('patch', 'unknown')}):")
        for c in benchmark.get("comparisons", []):
            if c["severity"] == "unavailable":
                lines.append(f"  - {c['metric']}: unavailable ({c.get('evidence', 'no data')})")
            else:
                lines.append(f"  - {c['metric']}: {c['evidence']} [severity: {c['severity']}]")
    else:
        lines.append(f"Benchmark Comparison: unavailable ({benchmark.get('detail', 'no data')})")

    next_focus = session.get("next_game_focus", [])
    if next_focus:
        lines.append("")
        lines.append("Next Game Focus: " + ", ".join(next_focus))

    return "\n".join(lines)


def print_session(session: dict) -> None:
    print(format_session(session))
