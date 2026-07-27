# LeagueMacroCoach — Project Checkpoint

Handoff summary for continuing development. Everything below reflects the state of the repo as of this checkpoint: a complete rule-based pipeline from raw match retrieval through structured player insights, now with per-event timeline enrichment. **No AI/LLM code exists anywhere yet** — that has been deliberately deferred at every phase.

Player profile (`data/player_profile.json`): Riot ID `HelloKittler#meow`, NA, Mid, champion pool Yone/Akali/Fizz/Syndra (learning). **The backfill has been run**: 20 real ranked games are now in `data/database/game_history.json` (mostly Akali/Yone, one Pyke support game, one Zoe, one Syndra). None of those 20 games have cached timeline data yet — the timeline feature was built after that backfill ran, so it hasn't been exercised against real matches yet (see Limitations).

## 1. What was built

An end-to-end, rule-based coaching-data pipeline:

1. **Riot API client** — auth, PUUID lookup, ranked match ID retrieval (single + batch), full match retrieval.
2. **Multi-match importer** — pulls N recent ranked matches, dedupes against history and cached raw files, runs each new match through the full pipeline, isolates per-match failures.
3. **Structured analyzer** — reshapes one raw Riot match into flat per-game stats (KDA, CS/min, gold, damage, damage share, objectives, vision, timestamp).
4. **Macro pattern analyzer** — rule-based threshold checks (deaths, farming, objectives, vision) producing `concern`/`tier`/`confidence` per pattern; explicitly marks checks that need data not yet collected (match timeline, opponent stats) as `confidence: "unavailable"` rather than faking them.
5. **Champion/role knowledge layer** — hand-written markdown (5 champions, 2 roles) parsed into structured dicts; used to de-prioritize metrics a champion/role explicitly expects to be low (e.g. CS/min for Pyke) so they're reported but not flagged as concerns.
6. **History storage** — flat-JSON store of one record per game, upserted by `match_id`.
7. **History aggregation** — most-played champions, per-champion/role averages, repeated weaknesses/strengths (pattern seen in ≥2 games), earlier-half-vs-later-half trend comparison.
8. **Player profile generator** — shapes aggregation output into a fixed `profile_summary.json` schema.
9. **Insight engine** — reshapes `profile_summary.json` into `player_insights.json` (player summary, strengths, weaknesses, priority improvements), with count-based confidence and honest `"insufficient_data"` handling.
10. **Backfill workflow** — a thin, configurable-count CLI wrapper around the existing importer, purpose-built for bulk-importing history in one run rather than one match at a time. Adds no new retrieval/analysis/storage logic of its own.

## 2. Files created

```
src/riot/client.py, __init__.py
src/analysis/analyzer.py, macro_analyzer.py, __init__.py
src/knowledge/loader.py, __init__.py
src/history/store.py, aggregate.py, importer.py, backfill.py, __init__.py
src/profile/generator.py, __init__.py
src/insights/engine.py, __init__.py
src/main.py, src/__init__.py

knowledge/champions/{yone,akali,fizz,syndra,pyke}.md
knowledge/roles/{mid,support}.md
knowledge/coaching_philosophy.md
data/player_profile.json

tests/test_riot_client.py
tests/test_analyzer.py
tests/test_macro_analyzer.py
tests/test_knowledge_loader.py
tests/test_history_store.py
tests/test_history_aggregate.py
tests/test_importer.py
tests/test_profile_generator.py
tests/test_insight_engine.py
tests/test_backfill.py

.env, .env.example, .gitignore, requirements.txt, README.md, .venv/
```

Generated (not hand-authored, produced by running the pipeline):
`data/raw_matches/NA1_5609585521.json`, `data/database/game_history.json`, `reports/generated_reports/NA1_5609585521_analysis.json`, `..._macro_patterns.json`, `profile_summary.json`, `player_insights.json`.

## 3. Files modified (iterative, across phases)

Nothing existing was modified to add the backfill workflow — `backfill.py` only calls `importer.run_import()` as-is. The list below is unchanged from the prior checkpoint.

- **`src/main.py`** — added Match ID to the printed summary.
- **`src/analysis/analyzer.py`** — added `game_start_timestamp` (for chronological trend ordering) and `damage_share` (per-participant damage ÷ team damage, both computed from data already in the raw match).
- **`src/analysis/macro_analyzer.py`** — added knowledge-context de-prioritization; added an explicit `tier` field (`low`/`adequate`/`good`) alongside `concern` so downstream code doesn't need to parse the `detail` string; fixed a keyword-matching bug where `"farm"` in a vision-score knowledge bullet incorrectly suppressed CS/min concerns.
- **`src/riot/client.py`** — added `get_ranked_match_ids(count=N)`; the old single-match function now calls it with `count=1` instead of duplicating the request logic.
- **`src/history/store.py`** — added `damage_share` to the stored game record; `load_history`/`save_history`/`record_game` accept an injectable `path` for test isolation.
- **`src/history/aggregate.py`** — renamed `_avg` → `avg` (now used cross-module by `generator.py`); factored `repeated_weaknesses`/`repeated_strengths` onto one shared `_repeated_patterns(predicate)` helper; **removed** `build_profile_summary()`/`main()` — see architectural note below.

## 4. Current architecture pipeline

```
src/history/backfill.py  (CLI, configurable --count, default 20)
        │  calls run_import(count) as-is
        ▼
Riot API
   │
   ▼
src/riot/client.py ──(get_ranked_match_ids, get_match)──▶ src/history/importer.py
                                                                  │
                              dedup against game_history.json ───┤
                              dedup against data/raw_matches/ ───┤
                                                                  ▼
                                                     data/raw_matches/{id}.json
                                                                  │
                                                                  ▼
                                                    src/analysis/analyzer.py
                                                                  │
                                              reports/generated_reports/{id}_analysis.json
                                                                  │
                                    knowledge/{champions,roles}/*.md ──▶ src/knowledge/loader.py
                                                                  │              │
                                                                  ▼              │
                                              src/analysis/macro_analyzer.py ◀───┘
                                                                  │
                                        reports/generated_reports/{id}_macro_patterns.json
                                                                  │
                                                                  ▼
                                                      src/history/store.py
                                                                  │
                                                data/database/game_history.json
                                                                  │
                                                                  ▼
                                                    src/history/aggregate.py
                                                                  │
                                                                  ▼
                                                    src/profile/generator.py
                                                                  │
                                            reports/generated_reports/profile_summary.json
                                                                  │
                                                                  ▼
                                                    src/insights/engine.py
                                                                  │
                                            reports/generated_reports/player_insights.json
                                                                  │
                                                                  ▼
                                                    (AI coaching layer — not built yet)
```

## 5. Data flow changes over the course of this build

- Started as a **single manual match** flow (`src/main.py`: one Riot API call → one printed summary).
- Became a **single-match analysis pipeline** (analyzer → macro analyzer → one JSON report per match).
- Became **multi-match and persistent** once `src/history/` was added: every analyzed match now accumulates in `game_history.json` instead of being a one-off report.
- Became **automated ingestion** once `importer.py` was added: one call now pulls N ranked matches, skips anything already processed, and feeds every new one through the full analyzer → macro → store chain.
- Became **cross-game aggregate** once `aggregate.py` / `generator.py` / `engine.py` were layered on: individual match reports now feed a standing player profile and insight summary that updates as more games are imported, rather than each match being analyzed in isolation.
- Became **bulk-loadable** once `backfill.py` was added: instead of running the importer once per small batch, one CLI call now sweeps a configurable number of recent ranked games in a single pass — a pure convenience layer, no new data path.

## 6. Tests added and results

All 10 test modules are self-contained (`assert`-based, no framework), run with `python -m tests.<module>`, and **all currently pass**:

| Module | Covers |
|---|---|
| `test_riot_client` | region→continent mapping, participant lookup (pure logic only, no network) |
| `test_analyzer` | stat extraction, `damage_share` team-scoping, `game_start_timestamp` |
| `test_macro_analyzer` | tier/concern thresholds, knowledge de-prioritization, unknown-champion graceful fallback |
| `test_knowledge_loader` | markdown section/bullet parsing, case-insensitive lookup, missing-file handling |
| `test_history_store` | record building, upsert-not-duplicate, missing-history-file handling |
| `test_history_aggregate` | most-played, per-champion/role averages, repeated weaknesses/strengths, trend comparison |
| `test_importer` | duplicate-skip (no API call made), multi-match import, per-match failure isolation |
| `test_profile_generator` | empty/single/multi-game aggregation, champion frequency, win rate |
| `test_insight_engine` | empty profile, insufficient games, weakness/strength detection, priority ordering (unsorted input) |
| `test_backfill` | configurable count pass-through, result reporting (imported/skipped/failed), CLI-level setup-error handling — via an injected fake `run_import_fn`, not re-testing `importer`'s own dedup/failure logic |

Run everything with:
```
for m in tests.test_riot_client tests.test_analyzer tests.test_macro_analyzer tests.test_knowledge_loader tests.test_history_store tests.test_history_aggregate tests.test_importer tests.test_profile_generator tests.test_insight_engine tests.test_backfill; do
  .venv/Scripts/python.exe -m "$m" || exit 1
done
```

## 7. Current limitations

- **Still only 1 real game in history.** `backfill.py` exists and is fully tested, but **has not been run against the live Riot API yet** — that's the immediate next action, not something already done. Until it's run, real `strength_patterns`/`weakness_patterns`/`recent_trends` remain empty/`insufficient_data` (upstream gate requires ≥2 occurrences for a pattern, ≥2 games for a trend).
- **Four checks are permanently `confidence: "unavailable"`** until match-timeline data is added: `deaths_before_objectives`, `deaths_after_extended_no_recall`, `objective_fight_presence`, `vision_score_vs_enemy_laner`. Riot's match-v5 **timeline** endpoint (`/lol/match/v5/matches/{id}/timeline`) has never been called — only match details.
- **Benchmarks in `macro_analyzer.py` (`BENCHMARKS` dict) are static and role-agnostic guesses**, not derived from rank/role/champion data. Marked with `ponytail:` comments as a known ceiling.
- **Knowledge base covers only 5 champions and 2 roles.** A champion without a file degrades gracefully (`champion_context_loaded: false`) but gets no de-prioritization.
- **Storage is flat JSON (`data/database/game_history.json`), not SQLite**, despite the original architecture phase naming SQLite for local storage. This was a deliberate, flagged deviation (JSON was adequate for personal, low-volume data and avoided premature schema/connection complexity) — **not yet reversed or re-confirmed by the user.**
- **No AI coaching layer exists.** `player_insights.json` is the last rule-based artifact in the chain; nothing yet turns it into natural-language coaching output.

## 8. Recommended next development step

1. **Actually run the backfill.** `.venv/Scripts/python.exe -m src.history.backfill --count 20` against the real Riot account (`HelloKittler#meow`) — this is the one remaining action, not a build task. Everything needed for it exists and is tested; it just hasn't been executed against the live API yet. Do this before building anything further on top of insights, since every strength/weakness/trend feature is currently provably correct but has nothing real to show.
2. **Then build the AI coaching layer** (`src/ai/`, per the original architecture's empty placeholder folder) that consumes `player_insights.json` + `knowledge/*.md` and turns deterministic findings into natural-language coaching text via the Anthropic API (already in `requirements.txt`, unused so far). This was always the end goal; everything built so far exists to feed it clean, evidence-backed input.

## 9. Architectural decisions that should not be changed without explicit confirmation

- **Riot API is the sole source of truth for match data.** No OP.GG/U.GG/Lolalytics scraping — those were explicitly named as future *supplementary* sources only, never foundational.
- **Rule-based analysis and AI coaching are separate layers.** Every fact-finding module (analyzer, macro analyzer, aggregation, insights) must stay deterministic and explainable; the AI layer's job (when built) is only to phrase already-computed findings, never to decide what the findings are. Don't let an LLM call creep into `src/analysis/`, `src/history/`, `src/profile/`, or `src/insights/`.
- **Missing data is marked, never fabricated.** `confidence: "unavailable"`, `"insufficient_data"`, and `null` values are load-bearing signals throughout this pipeline (macro analyzer, trends, insight engine). If the AI coaching layer is built next, it must preserve this — it should refuse to editorialize past what `player_insights.json` actually supports.
- **API keys live only in `.env`, are never printed/logged**, and `.env` is gitignored. This discipline held through every phase including live-auth testing.
- **`game_history.json` upserts by `match_id`** — re-processing a match must update its record, never duplicate it. Both `store.record_game` and `importer.import_matches` depend on this.
- **Champion/role knowledge is qualitative markdown, hand-curated**, not a numeric config — the parser (`src/knowledge/loader.py`) and its consumer (`macro_analyzer.py`'s de-prioritization) are built around parsing prose sections, not structured thresholds. Don't quietly convert this to numeric per-champion benchmarks without deciding that deliberately (it changes the whole `_is_deprioritized` keyword-matching design).
- **The JSON-vs-SQLite storage choice is flagged but unresolved** (see Limitations) — treat it as a live decision, not a settled one, before building more on top of `data/database/game_history.json`.
- **New entrypoints wrap existing logic instead of duplicating it.** `backfill.py` is the clearest example: it calls `importer.run_import()` unchanged rather than re-implementing retrieval/dedup/analysis/storage. If another new entrypoint is needed later (e.g. a scheduled re-sync), follow the same pattern — inject the real function as a default parameter (`run_import_fn=run_import`) so the wrapper stays unit-testable without network access, the way `import_matches`' `get_match_fn` and `backfill`'s `run_import_fn` already do.
