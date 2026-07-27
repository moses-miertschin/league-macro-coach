# LeagueMacroCoach — Project Checkpoint

Handoff summary for continuing development. Everything below reflects the state of the repo as of this checkpoint: a complete rule-based coaching pipeline — match retrieval through structured player insights, timeline enrichment, a deterministic item recommendation engine, a cross-pipeline coaching-session aggregator, and a benchmark-comparison foundation — plus one clearly-optional AI phrasing layer. **No part of the tool requires a paid API to function.** This supersedes the original checkpoint's "what's built" and "what's next" sections; those phases are complete and summarized below rather than repeated in full (see git history for the turn-by-turn build order).

Player profile (`data/player_profile.json`): Riot ID `HelloKittler#meow`, NA, Mid, champion pool Yone/Akali/Fizz/Syndra. **20 real ranked games are in `data/database/game_history.json`**, all with timeline data enriched (deaths-before-objectives, objective-fight-presence are real numbers, not `"unavailable"`, for all 20).

## 1. What's built

**Rule-based macro pipeline (complete, exercised against real data):**
1. Riot API client — auth, PUUID lookup, match ID retrieval, match + timeline retrieval.
2. Multi-match importer/backfill — pulls N recent ranked matches, dedupes, runs each through the full pipeline, isolates per-match failures. `enrich_existing_timelines()` backfills timeline data onto matches imported before timeline support existed.
3. Structured analyzer — raw match → flat per-game stats.
4. Timeline analyzer — raw timeline → per-event derived facts (death timing vs. objectives, objective participation, fight participation). Only processes timeline *events*; does not parse per-minute `participantFrames` (see Limitations).
5. Macro pattern analyzer — threshold-based pattern flags, knowledge-aware de-prioritization, timeline-enriched when available.
6. Champion/role knowledge layer — hand-written markdown parsed into structured dicts.
7. History storage/aggregation — flat-JSON, upsert by match_id, cross-game trends and repeated-pattern detection.
8. Player profile + insight generation — `profile_summary.json` → `player_insights.json`, count-based confidence, honest `"insufficient_data"` handling.

**Deterministic item recommendation engine (complete, exercised against real data):**
9. `GameSnapshot` architecture (`src/analysis/game_state.py`) — source-agnostic shape, deliberately built so a future live-data builder can produce the same shape without touching anything downstream.
10. Item recommendation engine (`src/analysis/item_recommender.py`) — keyword-matched trigger evaluation against qualitative item knowledge, deterministic confidence scoring with a full breakdown, gold-aware `recommendation_type` (`complete_item`/`component`/`alternative`/`save_gold`), Data Dragon cross-check that flags (never silently drops or trusts) unrecognized item names.
11. Data Dragon static client (`src/riot/data_dragon.py`) — self-updates per patch automatically (see `PATCH_SYSTEM.md`).

**Optional AI phrasing layer (complete, never required):**
12. `src/ai/prompt_builder.py` / `validator.py` / `client.py` / `report_generator.py` — grounds a prompt in already-computed insights + knowledge, strips any model output not traceable to real data, opt-in Anthropic backend. The tool works fully without this layer; `ROADMAP.md` still recommends a free deterministic backend as the actual default (not yet built — see Next Milestone).

**Coaching-session aggregation layer (complete, exercised against real data):**
13. `src/coaching/coaching_report.py` — combines `player_insights.json`, one match's macro patterns + item recommendations, and (if present) a benchmark comparison into one `coaching_session.json`. Pure combination, no new analysis.
14. `src/coaching/priorities.py` — selects top 1–3 lessons, preferring cross-game recurring patterns over this-game-only observations, explicitly labeled by evidence `scope`.
15. `src/coaching/formatter.py` — pure terminal rendering, no decision-making.

**Benchmark comparison foundation (complete, zero real data by design):**
16. `src/benchmark/benchmark_schema.py` — benchmark entry shape + `METRIC_DIRECTIONS` registry (direction-aware: higher-is-better vs. lower-is-better).
17. `src/benchmark/storage.py` — flat-JSON load/save/upsert, mirroring `history/store.py`'s pattern; `find_benchmarks()` supports arbitrary extra descriptor filters (e.g. a future `matchup` field) with no code changes needed later.
18. `src/benchmark/comparison.py` — direction-aware gap-ratio severity scoring, verified against a hand-worked example before trusting the formula.
19. `src/coaching/benchmark_section.py` — wires stored benchmarks into `coaching_session.json` as a strictly informational section. **Benchmark gaps never become coaching priorities** — verified by a test that builds the same session with and without benchmark data present and asserts `main_lessons`/`next_game_focus` are identical either way.
20. **No real benchmark data exists anywhere in the repo.** `data/benchmarks/` isn't even created yet. No scraping, no AI-sourced numbers — this is 100% foundation, verified only with synthetic test fixtures.

**Architecture/planning documentation (complete):**
21. `ROADMAP.md`, `ARCHITECTURE_AUDIT.md`, `TEST_AUDIT.md`, `KNOWLEDGE_SYSTEM_PLAN.md`, `LIVE_SYSTEM_DESIGN.md`, `UI_DESIGN.md`, `PATCH_SYSTEM.md` — a full engineering review and forward design pass covering everything not yet built (live game state, overlay UI, knowledge scaling, patch handling).

## 2. Current Architecture

```
Riot API ──▶ src/riot/client.py ──▶ data/raw_matches/, data/raw_matches/timelines/
Data Dragon ─▶ src/riot/data_dragon.py ─▶ data/static/ (cached item catalog)
                              │
                              ▼
        src/analysis/analyzer.py, timeline_analyzer.py
                              │
knowledge/champions/, roles/ ◀┤ (src/knowledge/loader.py)
                              ▼
              src/analysis/macro_analyzer.py
                              │
                              ▼
      src/history/store.py → game_history.json
                              │
                              ▼
   src/history/aggregate.py → src/profile/generator.py
                              │
                              ▼
        src/insights/engine.py → player_insights.json
                              │                              ┌── independent pipeline ──┐
                              │                    src/analysis/game_state.py (GameSnapshot)
                              │                              │
                              │                knowledge/items/ ◀┤ (src/knowledge/item_loader.py)
                              │                              ▼
                              │                src/analysis/item_recommender.py
                              │                              │
                              │                {match}_item_recommendations.json
                              │                              │
                              ▼                              ▼
                    ┌─────────────────────────────────────────────┐
                    │        src/coaching/coaching_report.py       │
                    │  (combines insights + macro patterns +       │
                    │   item recommendations + benchmark section)  │
                    └─────────────────────┬─────────────────────────┘
                                          ▼
                              coaching_session.json
                                          │
                              src/coaching/formatter.py (terminal output)

              ┌── benchmark pipeline, no real data yet ──┐
knowledge/items/-style      src/benchmark/storage.py (data/benchmarks/, empty)
qualitative discipline               │
              (future: Challenger/pro/patch/matchup sources)
                                      ▼
                    src/benchmark/comparison.py ──▶ src/coaching/benchmark_section.py
                    (feeds into coaching_session.json's "benchmark" key, informational only)

          src/ai/ (optional, opt-in, never required) ──▶ its own coaching_report.json
```

Two things worth being precise about, since they're easy to conflate:
- `src/ai/report_generator.py` writes `coaching_report.json` (optional, LLM-based). `src/coaching/coaching_report.py` writes `coaching_session.json` (required-path, deterministic). Different files, similar names, by explicit design choice at the time — see the relevant turn's plan discussion if this needs to be renamed later.
- The item-recommendation pipeline is **not yet wired into `src/history/importer.py`'s automatic per-match run** — it's currently invoked separately via `item_recommender.main()`. This means `coaching_session.json`'s item-review section will show `"unavailable"` for any match that hasn't had that separate step run on it, which is correct/honest behavior, not a bug (see `ARCHITECTURE_AUDIT.md` §5).

## 3. Current Limitations

- **No real benchmark data exists.** The entire `src/benchmark/` system is verified foundation only — no Challenger/pro/patch data has been scraped or entered, by explicit instruction. `coaching_session.json`'s benchmark section will read `"unavailable"` for every match until a real source is wired in.
- **Benchmark metrics are limited to whole-game averages.** Minute-10-specific metrics (`cs_10`, `gold_10`, `deaths_before_10` — the original illustrative example) aren't computable without parsing timeline `participantFrames`, which `timeline_analyzer.py` doesn't currently do and wasn't modified to do (out of scope, protected file). `METRIC_DIRECTIONS` currently only has real support for `cs_per_minute`/`gold_per_minute`/`kill_participation`/`damage_to_objectives`/`vision_score`/`death_count`.
- **No patch tracking on the player's side.** `analyzer.py` doesn't extract `gameVersion`, so patch-filtered benchmark lookup can't be meaningfully exercised yet; `find_benchmarks()` is called with `patch=None`.
- **Item recommendation engine isn't in the automatic batch pipeline.** See architecture note above — a real wiring task, not a design flaw.
- **The AI layer's free-by-default backend (per `ROADMAP.md` §1) still isn't built.** `src/ai/client.py`'s paid Anthropic path is the only backend that exists; it's opt-in, never called automatically by anything, but the *deterministic* backend that should be the actual default hasn't been implemented yet.
- **Storage is flat JSON, not SQLite** — still a deliberately flagged, still-unresolved decision per the original checkpoint; unchanged this pass.
- **Knowledge coverage is narrow by design** (5 champions, 2 roles, 4 champions' worth of item knowledge) — see `KNOWLEDGE_SYSTEM_PLAN.md` for the intended incremental-growth strategy (grow from real opponents faced, not exhaustive upfront authoring).
- **No live game state, no overlay UI, no conversational coaching, no local model backend** — all deliberately deferred; full designs exist in `LIVE_SYSTEM_DESIGN.md` and `UI_DESIGN.md` but nothing in those documents is built.

## 4. Recommended Next Milestone

Per `ROADMAP.md`, the AI layer's free-by-default backend (`src/ai/backends/deterministic.py` — render `coaching_report.json`-equivalent phrasing directly from knowledge-file text, no API call) was already the recommended next step before this session and still is — it's the smallest remaining gap between "what the architecture promises" (never requires paid API spend) and "what's actually wired as the default." Everything built this session (coaching aggregation, benchmark foundation) sits comfortably alongside it without conflict.

A close second, now that `src/coaching/coaching_report.py` exists as the integration point: wiring `item_recommender.py` into `src/history/importer.py`'s automatic per-match run, so `coaching_session.json`'s item-review section stops depending on a separate manual step for every match.

## 5. Tests

All 19 modules are self-contained (assert-based, no framework), run with `python -m tests.<module>`, and **all currently pass**:

`test_riot_client`, `test_analyzer`, `test_timeline_analyzer`, `test_macro_analyzer`, `test_knowledge_loader`, `test_history_store`, `test_history_aggregate`, `test_importer`, `test_profile_generator`, `test_insight_engine`, `test_backfill`, `test_ai_report_generator`, `test_data_dragon`, `test_game_state`, `test_item_loader`, `test_item_recommender`, `test_coaching_report`, `test_benchmark`, `test_benchmark_section`.

```
for m in tests.test_riot_client tests.test_analyzer tests.test_timeline_analyzer tests.test_macro_analyzer tests.test_knowledge_loader tests.test_history_store tests.test_history_aggregate tests.test_importer tests.test_profile_generator tests.test_insight_engine tests.test_backfill tests.test_ai_report_generator tests.test_data_dragon tests.test_game_state tests.test_item_loader tests.test_item_recommender tests.test_coaching_report tests.test_benchmark tests.test_benchmark_section; do
  .venv/Scripts/python.exe -m "$m" || exit 1
done
```

## 6. Architectural Decisions That Should Not Be Changed Without Explicit Confirmation

Carried forward from the original checkpoint (still true, unchanged this session):

- **Riot API is the sole source of truth for match data.** Data Dragon is the sole source of truth for static item data. No OP.GG/U.GG/Lolalytics scraping — supplementary only, never foundational, and still not implemented anywhere.
- **Rule-based analysis and AI coaching are separate layers.** Every fact-finding module must stay deterministic and explainable; the AI layer only phrases already-computed findings, never decides what they are.
- **Missing data is marked, never fabricated.** `"unavailable"`, `"insufficient_data"`, `null` are load-bearing signals throughout — extended this session to `src/benchmark/` (a metric with no known direction, or no player data, reports `"unavailable"`, never a guessed score) and `src/coaching/` (missing item recommendations, missing benchmark data, both stay honestly absent).
- **API keys live only in `.env`**, never printed/logged, gitignored.
- **`game_history.json` upserts by `match_id`**; `src/benchmark/storage.py` and `src/coaching/`'s file lookups follow the same upsert/no-duplication discipline.
- **Champion/role/item knowledge is qualitative markdown, hand-curated**, not numeric thresholds.
- **The JSON-vs-SQLite storage choice is still flagged but unresolved.**
- **New entrypoints wrap existing logic instead of duplicating it** (`backfill.py` calling `importer.run_import()` unchanged is the original example; `src/coaching/coaching_report.py` combining already-computed JSON without re-deriving anything is this session's continuation of the same rule).

New decisions established this session:

- **`GameSnapshot`'s "independent of data source" principle was deliberately reapplied to benchmarks.** `src/benchmark/comparison.py` operates on plain dicts and has no idea whether a benchmark came from a future scraper, a manual entry, or a patch-aggregate import — the same reasoning that made `game_state.py` reusable for a future live-data builder without any downstream changes.
- **Benchmark comparisons are informational only and must never become coaching priorities.** `src/coaching/priorities.py` never imports `src/coaching/benchmark_section.py` or reads its output. This is enforced by a test (`test_benchmark_gaps_never_become_coaching_priorities`) that asserts `main_lessons`/`next_game_focus` are byte-identical whether or not benchmark data is present — not just a docstring claim.
- **A metric registry (`METRIC_DIRECTIONS`) is a deliberate, small, code-level scaling ceiling** — the same tradeoff already accepted for `item_recommender.py`'s `TRIGGER_KEYWORDS` (see `ARCHITECTURE_AUDIT.md` Finding E). Adding a new benchmark metric means adding one dict entry, not touching comparison logic.
