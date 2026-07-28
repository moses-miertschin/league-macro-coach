# LeagueMacroCoach — Project Checkpoint

Handoff summary for continuing development. Everything below reflects the state of the repo as of this checkpoint: a complete rule-based coaching pipeline — match retrieval through structured player insights, timeline enrichment, a deterministic item recommendation engine, a cross-pipeline coaching-session aggregator, and a benchmark-comparison foundation — plus one clearly-optional AI phrasing layer. **No part of the tool requires a paid API to function.** This supersedes the original checkpoint's "what's built" and "what's next" sections; those phases are complete and summarized below rather than repeated in full (see git history for the turn-by-turn build order).

**Strategic pivot (this checkpoint):** the project's primary goal is no longer AI coaching — it's a deterministic League intelligence system (live recommendations, drafting assistance, itemization, rune decisions, matchup analysis, a future overlay UI), with AI now formally an optional explanation layer project-wide, never the decision-maker. See the revised `ROADMAP.md` and new `RECOMMENDATION_SYSTEM_DESIGN.md`. Nothing already built changes meaning or behavior because of this pivot — it's additive, and the "AI never decides" rule it formalizes was already true for everything in this repo.

Player profile (`data/player_profile.json`): Riot ID `HelloKittler#meow`, NA, Mid, champion pool Yone/Akali/Fizz/Syndra. **20 real ranked games are in `data/database/game_history.json`**, all with timeline data enriched (deaths-before-objectives, objective-fight-presence are real numbers, not `"unavailable"`, for all 20).

## 1. What's built

**Rule-based macro pipeline (complete, exercised against real data):**
1. Riot API client — auth, PUUID lookup, match ID retrieval, match + timeline retrieval.
2. Multi-match importer/backfill — pulls N recent ranked matches, dedupes, runs each through the full pipeline (analysis → timeline → macro patterns → **item recommendations** → history), isolates per-match failures. `enrich_existing_timelines()` backfills timeline data onto matches imported before timeline support existed.
3. Structured analyzer — raw match → flat per-game stats.
4. Timeline analyzer — raw timeline → per-event derived facts (death timing vs. objectives, objective participation, fight participation). Only processes timeline *events*; does not parse per-minute `participantFrames` (see Limitations).
5. Macro pattern analyzer — threshold-based pattern flags, knowledge-aware de-prioritization, timeline-enriched when available.
6. Champion/role knowledge layer — hand-written markdown parsed into structured dicts.
7. History storage/aggregation — flat-JSON, upsert by match_id, cross-game trends and repeated-pattern detection.
8. Player profile + insight generation — `profile_summary.json` → `player_insights.json`, count-based confidence, honest `"insufficient_data"` handling.

**Deterministic item recommendation engine (complete, exercised against real data):**
9. `GameSnapshot` architecture (`src/analysis/game_state.py`) — source-agnostic shape, deliberately built so a future live-data builder can produce the same shape without touching anything downstream.
10. Item recommendation engine (`src/analysis/item_recommender.py`) — keyword-matched trigger evaluation against qualitative item knowledge, deterministic confidence scoring with a full breakdown, gold-aware `recommendation_type` (`complete_item`/`component`/`alternative`/`save_gold`), Data Dragon cross-check that flags (never silently drops or trusts) unrecognized item names. `generate_item_recommendations(match, game_name, tag_line, item_catalog, damage_type_table)` composes the full snapshot→knowledge→recommend pipeline into one callable — **now wired into `src/history/importer.py`'s `import_matches()`**, so item recommendations are generated automatically for every newly-imported match, not just via a separate manual step (see the architecture note below — this closed the exact gap the previous checkpoint flagged as a limitation).
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
21. `ROADMAP.md`, `ARCHITECTURE_AUDIT.md`, `TEST_AUDIT.md`, `KNOWLEDGE_SYSTEM_PLAN.md`, `LIVE_SYSTEM_DESIGN.md`, `UI_DESIGN.md`, `PATCH_SYSTEM.md` — a full engineering review and forward design pass covering everything not yet built (live game state, overlay UI, knowledge scaling, patch handling). `ROADMAP.md` was revised this checkpoint for the deterministic-intelligence-system pivot (below); `RECOMMENDATION_SYSTEM_DESIGN.md` is new.

**Shared recommendation contract (foundation only, no migration yet):**
22. `src/recommendations/schema.py` — the shared shape every future recommendation-producing system (item, draft, rune, live, macro) will eventually emit: `system`/`category`/`subject`/`recommendation`/`reason`/`evidence`/`confidence`/`confidence_score`/`severity`/`priority`/`source`/`details`. Two deliberately separate axes — `confidence` (data quality) and `severity` (impact/urgency) — replace the three previously-incompatible confidence vocabularies `ARCHITECTURE_AUDIT.md` Finding C flagged. `validate_recommendation(entry) -> list[str]` follows the exact convention `benchmark_schema.py`'s `validate_benchmark_entry()` already established. **`recommendation`/`confidence_score` may be `null`, and `confidence`/`severity` may be `"unavailable"` — this is a valid, expected state, never rejected.** `details` stays permissive of arbitrary domain-specific keys, same precedent as benchmark entries.
23. `src/recommendations/adapters.py`: `adapt_item_recommendation(entry)` and `adapt_macro_lesson(lesson)` translate one entry from `item_recommender.recommend_items()`'s output / one lesson from `priorities.select_priorities()`'s output into the shared schema. **Neither source module is imported, called, or modified** — the adapters are hand-written pure functions operating on plain dicts matching those modules' real shapes; `item_recommender.py` and `coaching/priorities.py` are byte-for-byte unchanged. Both adapters reuse each source's single confidence value for the schema's `severity` field too, since neither source system computes impact/urgency independently yet — an explicitly-documented simplification, not a hidden decision.
24. **The Stage-1 adapters are now wired into `src/coaching/coaching_report.py`.** `build_coaching_session()` calls a new private helper, `_shared_recommendations(item_recommendations, main_lessons)`, which runs every item recommendation through `adapt_item_recommendation()` and every selected macro lesson through `adapt_macro_lesson()`, and adds the combined list as a new `"shared_recommendations"` key on the returned session dict — purely additive, alongside `main_lessons`/`item_review`, never replacing either. `coaching_session.json` now carries this extra key; every existing key (`player`, `champion`, `game_result`, `main_lessons`, `item_review`, `benchmark`, `strengths`, `next_game_focus`) is unchanged in shape or value. `_shared_recommendations()` contains no translation logic of its own — it only calls the two existing adapters and concatenates their output, keeping the "modules perform logic, orchestrators only coordinate" rule intact. When item recommendations are unavailable for a match, `shared_recommendations` simply contains macro-only entries rather than failing — same honest-degradation behavior as `item_review`'s existing `"unavailable"` path. `src/coaching/formatter.py` was not touched; it renders known keys via `.get()` and silently ignores the new one, so terminal output is byte-for-byte unchanged.

**Shared polling/runtime foundation (new this checkpoint, foundation only):**
25. `src/runtime/poller.py` — `SessionPoller`, the shared runtime `ROADMAP.md` §1 and `LIVE_SYSTEM_DESIGN.md`'s "Runtime Model" section both call the actual prerequisite for `src/draft/`/`src/live/`. Deliberately domain-blind: it has zero knowledge of champ select, live games, draft, runes, or any analysis — it only calls an injected zero-argument `data_source()` callable (returns a dict when a session exists, `None` when it doesn't — the same "endpoint simply isn't reachable" idle condition `LIVE_SYSTEM_DESIGN.md` documents for the Live Client Data API), tracks `state` (`"idle"`/`"active"`) off the last result, and hands each result to an optional `on_result` callback. `poll_once()` is the single synchronous unit everything else is built from — it's also the integration point a future desktop app can call directly from its own timer/event loop instead of using this module's background thread at all. `start()`/`stop()` run/stop that same `poll_once()` on a background `threading.Thread` at a configurable `interval_seconds`, with an injectable `sleep_fn` (defaults to `time.sleep`) so tests never depend on real wall-clock waits longer than tens of milliseconds. Both `start()` and `stop()` are idempotent. No draft/rune/live analysis logic, no UI, nothing League-specific lives here — exactly the scope this checkpoint's instructions specified.

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

     ┌── shared runtime foundation, not yet wired to a real source ──┐
     src/runtime/poller.py (SessionPoller: injectable data_source,
     configurable interval, idle/active state, start/stop lifecycle)
     -- domain-blind; a future LCU client / Live Client Data API client
     becomes its data_source, feeding a future src/draft/ or src/live/
```

Two things worth being precise about, since they're easy to conflate:
- `src/ai/report_generator.py` writes `coaching_report.json` (optional, LLM-based). `src/coaching/coaching_report.py` writes `coaching_session.json` (required-path, deterministic). Different files, similar names, by explicit design choice at the time — see the relevant turn's plan discussion if this needs to be renamed later.
- **The item-recommendation pipeline is now wired into `src/history/importer.py`'s automatic per-match run** (as of this checkpoint). `import_matches()` accepts optional `item_catalog`/`damage_type_table` parameters; when both are supplied (as `run_import()` now does, loading them once per batch via `load_item_catalog()`/`load_damage_type_table()`), every newly-imported match gets a `{match_id}_item_recommendations.json` automatically, with the same best-effort failure isolation already established for timeline retrieval (tracked in `result["item_recommendations_unavailable"]`, never fails the match itself). Importer.py contains no item-recommendation logic of its own — it only calls `item_recommender.generate_item_recommendations()` and saves the result, the same pattern it already used for `analyze_match()`/`macro_analyze()`. Matches imported *before* this integration (or via a caller that omits the catalog/table) still show `"unavailable"` in `coaching_session.json`'s item-review section — that remains correct, honest behavior for data that genuinely wasn't generated, not a bug.

## 3. Current Limitations

- **No real benchmark data exists.** The entire `src/benchmark/` system is verified foundation only — no Challenger/pro/patch data has been scraped or entered, by explicit instruction. `coaching_session.json`'s benchmark section will read `"unavailable"` for every match until a real source is wired in.
- **Benchmark metrics are limited to whole-game averages.** Minute-10-specific metrics (`cs_10`, `gold_10`, `deaths_before_10` — the original illustrative example) aren't computable without parsing timeline `participantFrames`, which `timeline_analyzer.py` doesn't currently do and wasn't modified to do (out of scope, protected file). `METRIC_DIRECTIONS` currently only has real support for `cs_per_minute`/`gold_per_minute`/`kill_participation`/`damage_to_objectives`/`vision_score`/`death_count`.
- **No patch tracking on the player's side.** `analyzer.py` doesn't extract `gameVersion`, so patch-filtered benchmark lookup can't be meaningfully exercised yet; `find_benchmarks()` is called with `patch=None`.
- **The AI layer's free-by-default backend (per `ROADMAP.md` §1) still isn't built.** `src/ai/client.py`'s paid Anthropic path is the only backend that exists; it's opt-in, never called automatically by anything, but the *deterministic* backend that should be the actual default hasn't been implemented yet.
- **Storage is flat JSON, not SQLite** — still a deliberately flagged, still-unresolved decision per the original checkpoint; unchanged this pass.
- **Knowledge coverage is narrow by design** (5 champions, 2 roles, 4 champions' worth of item knowledge) — see `KNOWLEDGE_SYSTEM_PLAN.md` for the intended incremental-growth strategy (grow from real opponents faced, not exhaustive upfront authoring).
- **No live game state, no overlay UI, no conversational coaching, no local model backend** — all deliberately deferred; full designs exist in `LIVE_SYSTEM_DESIGN.md` and `UI_DESIGN.md` but nothing in those documents is built.
- **No draft or rune system exists.** `src/draft/`, `knowledge/runes/`, `knowledge/drafting/`, and the LCU API client are all still design-only (`ROADMAP.md` §2–4).
- **`src/draft/` and `src/live/` remain unstarted.** The shared polling/runtime infrastructure they depend on (`src/runtime/poller.py`) now exists, but nothing calls it with a real LCU or Live Client Data API source yet — `SessionPoller` has only ever been exercised with fake, hand-built data sources in tests. No LCU client, no Live Client Data API client, no `DraftSnapshot`, no draft/rune/live analysis logic exists anywhere. Wiring the Stage-1 adapters into `coaching_report.py` (prior checkpoint) also only exposes a shared-schema *view* of the two existing systems' output — it does not build a second real system against the schema natively, which `RECOMMENDATION_SYSTEM_DESIGN.md`'s Stage 2 still requires before retiring the adapters.

## 4. Recommended Next Milestone

The shared polling/runtime foundation (`src/runtime/poller.py`) now exists and is tested against fake data sources only, per explicit instruction this checkpoint (no draft, rune, live analysis, or UI/overlay work was done). Per `ROADMAP.md` §4's ordering ("1. Shared polling/runtime infrastructure. 2. `src/draft/` — LCU client + `DraftSnapshot`."), the recommended next step is building the first *real* data source: an LCU client that authenticates via the lockfile and polls `/lol-champ-select/v1/session`, returning `None` when no champ-select session exists — i.e., something that can be handed to `SessionPoller` as its `data_source` in place of the test fakes used so far. `src/draft/`'s actual pick/ban recommendation logic is explicitly the step after that, not this one.

The AI layer's free-by-default backend (`src/ai/backends/deterministic.py`) is no longer the top priority given the pivot — de-prioritized, not abandoned, since nothing in the pipeline calls the paid backend automatically anyway.

Also still open: backfilling item recommendations onto the 20 already-imported games (`enrich_existing_item_recommendations()`, mirroring `enrich_existing_timelines()`) — unchanged from the prior checkpoint, still not built.

## 5. Tests

All 22 modules are self-contained (assert-based, no framework), run with `python -m tests.<module>`, and **all currently pass**:

`test_riot_client`, `test_analyzer`, `test_timeline_analyzer`, `test_macro_analyzer`, `test_knowledge_loader`, `test_history_store`, `test_history_aggregate`, `test_importer`, `test_profile_generator`, `test_insight_engine`, `test_backfill`, `test_ai_report_generator`, `test_data_dragon`, `test_game_state`, `test_item_loader`, `test_item_recommender`, `test_coaching_report`, `test_benchmark`, `test_benchmark_section`, `test_recommendation_schema`, `test_recommendation_adapters`, `test_runtime_poller`.

```
for m in tests.test_riot_client tests.test_analyzer tests.test_timeline_analyzer tests.test_macro_analyzer tests.test_knowledge_loader tests.test_history_store tests.test_history_aggregate tests.test_importer tests.test_profile_generator tests.test_insight_engine tests.test_backfill tests.test_ai_report_generator tests.test_data_dragon tests.test_game_state tests.test_item_loader tests.test_item_recommender tests.test_coaching_report tests.test_benchmark tests.test_benchmark_section tests.test_recommendation_schema tests.test_recommendation_adapters tests.test_runtime_poller; do
  .venv/Scripts/python.exe -m "$m" || exit 1
done
```

`test_runtime_poller` is the one module in this list that uses real (bounded) threading and small real sleeps — every test either calls `poll_once()` directly (no thread at all) or bounds its background-thread tests with small fixed sleeps (tens of milliseconds) plus a `stop(timeout=2.0)` join, so a loop bug fails the test instead of hanging it. Run 5x consecutively during development with no flakes observed.

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
- **Wiring a new analysis step into the automatic import flow means adding one composition function to the owning analysis module and one call site in `importer.py`, never inline logic in `importer.py` itself.** `item_recommender.generate_item_recommendations()` (composing `build_snapshot_from_match` + knowledge loading + `recommend_items`) is the concrete precedent for this — the same "importer orchestrates, modules analyze" rule already established for `analyze_match()`/`macro_analyze()`, now proven out a second time for a genuinely different analysis pipeline.

New decisions established this checkpoint (the recommendation-system pivot):

- **AI is optional and explanation-only, project-wide, not just for post-game coaching.** Any future draft/rune/live explanation feature must reuse `src/ai/prompt_builder.py`/`validator.py`'s existing grounding pattern — one AI wrapper for the whole project, never a new one per domain.
- **A shared recommendation contract (`src/recommendations/schema.py`) exists, and Stage-1 adapters (`src/recommendations/adapters.py`) now translate both existing systems onto it.** `item_recommender.py` and `coaching/priorities.py` keep their current output shapes completely unchanged — the adapters are additive pure functions, not called by anything in the pipeline yet. A native-format Stage 2 migration (retiring the adapters, having `recommend_items()`/`select_priorities()` emit the shared shape directly) is explicitly deferred until a second real system (draft or rune) has proven the schema out. Do not force Stage 2 prematurely, and do not wire the Stage-1 adapters into the live pipeline without deciding that deliberately (see Next Milestone).
- **When a source system doesn't distinguish two axes the shared schema keeps separate, the adapter reuses one value for both rather than inventing a new derivation.** Both `adapt_item_recommendation()` and `adapt_macro_lesson()` set `severity` equal to `confidence`, since neither `item_recommender.py` nor `priorities.py` computes impact/urgency independently of data-quality confidence today. This is deliberately conservative — a translation layer should never manufacture information its source doesn't have, even to fill a field the target schema expects.
- **`confidence` (data quality) and `severity` (impact/urgency) are two distinct axes going forward**, resolving `ARCHITECTURE_AUDIT.md` Finding C's three-incompatible-vocabularies problem for any *new* system built against the shared schema. Existing systems (`macro_analyzer.py`'s `confidence`/`tier`, `item_recommender.py`'s `confidence_tier`/`confidence_score`) are not retrofitted — only the adapters translate into this vocabulary, per the point above.
- **`src/draft/` and `src/live/` are not started.** Per explicit instruction this checkpoint, only the shared contract was built — no champion-select or live-client integration exists yet.

New decisions established this checkpoint (Stage-1 wiring):

- **`coaching_report.py` is the correct place to call the adapters, not a new module.** It already combines already-computed JSON from multiple sources (`_item_review()` is the existing precedent for a small combination helper living directly in this orchestrator); calling two existing pure functions and concatenating their output is coordination, not new recommendation logic, so it doesn't violate "modules perform logic, orchestrators coordinate."
- **`shared_recommendations` adapts every item recommendation, not just the top-3 `item_review.top_recommendations` slice.** The two views are independent and serve different consumers — `item_review` is the existing truncated display view, `shared_recommendations` is the full-fidelity shared-schema view a future cross-system consumer (overlay, draft/rune aggregator) would read. Truncation stays local to `_item_review()`, not duplicated into the new helper.

New decisions established this checkpoint (shared polling/runtime foundation):

- **`src/runtime/poller.py` is intentionally the only thing this checkpoint built.** No LCU client, no Live Client Data API client, no `DraftSnapshot`, no draft/rune/live logic — `SessionPoller` is exercised only against fake, hand-built data sources in `tests/test_runtime_poller.py`. Per explicit instruction, real data sources and any analysis on top of them are separate, future work.
- **The data-source contract is a bare zero-argument callable returning `dict | None`, not a class or protocol.** This is the same "operates on plain dicts, doesn't know where they came from" discipline already established for `GameSnapshot` (`src/analysis/game_state.py`) and `src/benchmark/comparison.py` — a future LCU client or Live Client API client just needs to be *a callable*, nothing more, to be a valid `SessionPoller` data source.
- **`poll_once()` is the single synchronous unit both the background thread and any future external caller go through.** This was a deliberate design choice specifically so a future desktop app (Qt/Tk) can drive polling from its own timer/event loop by calling `poll_once()` directly, without ever touching this module's background thread — avoids the common desktop-app pitfall of updating UI state from a non-UI thread, without needing two separate code paths to keep in sync.
- **Idle vs. active state is presence-of-a-result, not any inspection of the result's contents.** `state` is `"idle"` when `last_result is None`, `"active"` otherwise — `SessionPoller` never looks inside the dict a data source returns. Interpreting *what kind* of session is active (champ select vs. live game) is explicitly left to the caller, not this module — keeping it domain-blind per this checkpoint's instructions.
- **Tests exercise the real `threading`-based `start()`/`stop()` loop, not just `poll_once()` in isolation, but bound every real sleep to tens of milliseconds and cap `stop()`'s join with a timeout.** This was a deliberate choice to actually prove the loop mechanism works (interval passed to `sleep_fn` matches configuration, `is_running` flips correctly, repeated `start()`/`stop()` calls are idempotent) rather than only testing the thread-free `poll_once()` unit, while still guaranteeing every test terminates in well under a second even if the loop logic were broken.
