"""Renders a benchmark comparison as plain terminal text.

Pure presentation, same rule as src/coaching/formatter.py -- no thresholds,
no re-ranking, no decision-making. Every value printed here was already
computed by comparison.py.
"""

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3, "unavailable": 4}


def format_comparison(benchmark_entry: dict, comparisons: list) -> str:
    champion = benchmark_entry.get("champion", "Unknown")
    role = benchmark_entry.get("role", "Unknown")
    rank = benchmark_entry.get("rank", "unknown")
    patch = benchmark_entry.get("patch", "unknown")

    lines = [
        f"Benchmark Comparison -- {champion} ({role})",
        f"Reference: {rank} rank, patch {patch}",
        "",
    ]

    ordered = sorted(comparisons, key=lambda c: SEVERITY_ORDER.get(c["severity"], 99))
    for c in ordered:
        if c["severity"] == "unavailable":
            lines.append(f"  {c['metric']}: unavailable -- {c.get('detail', 'no comparison possible')}")
            continue
        lines.append(
            f"  {c['metric']}: you={c['player_value']} vs benchmark={c['benchmark_value']} "
            f"(diff={c['difference']}, severity={c['severity']})"
        )

    return "\n".join(lines)


def print_comparison(benchmark_entry: dict, comparisons: list) -> None:
    print(format_comparison(benchmark_entry, comparisons))
