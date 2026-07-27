# LeagueMacroCoach — Architecture Audit

Read in full for this audit: `CHECKPOINT.md`, `ROADMAP.md`, `README.md`, every file under `src/`, `tests/`, `knowledge/`. No code was changed while writing this document.

## 1. Current Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ Riot API (match-v5 REST, cloud)          Data Dragon (static, CDN)  │
└──────────────┬────────────────────────────────────┬─────────────────┘
               │                                     │
       src/riot/client.py                  src/riot/data_dragon.py
       (matches, timelines)                (item catalog, cached)
               │                                     │
               ▼                                     │
      data/raw_matches/*.json                        │
      data/raw_matches/timelines/*.json               │
               │                                     │
               ▼                                     │
    src/analysis/analyzer.py  ──┐                    │
    (per-game structured stats) │                    │
               │                │                    │
               ▼                │                    │
    src/analysis/timeline_analyzer.py                │
    (per-event timeline facts)  │                    │
               │                │                    │
               ▼                │                    │
    src/analysis/macro_analyzer.py ◀── knowledge/champions/*.md
    (rule-based pattern flags)       knowledge/roles/*.md
               │                     (src/knowledge/loader.py)
               ▼
      src/history/store.py  →  data/database/game_history.json
               │
               ▼
      src/history/aggregate.py
      (cross-game trends/repeats)
               │
               ▼
      src/profile/generator.py → profile_summary.json
               │
               ▼
      src/insights/engine.py → player_insights.json
               │
               ├─────────────────────────────┐
               ▼                             ▼
      src/ai/ (report_generator.py    src/analysis/game_state.py
      + prompt_builder + validator    (builds GameSnapshot from a
      + client, all opt-in,           completed match, reusing
      not yet wired to a free         analyzer.find_participant)
      default backend — see §5)                │
                                                ▼
                                     src/analysis/item_recommender.py ◀── knowledge/items/*.md
                                     (rule-based item recommendations)   (src/knowledge/item_loader.py)
                                                │                        data/static/champion_damage_types.json
                                                ▼                        src/riot/data_dragon.py (item catalog)
                                     {match_id}_item_recommendations.json

      src/history/backfill.py — CLI wrapper over importer.run_import(), bulk historical pull
      src/history/importer.py — orchestrates: raw match → analyzer → timeline → macro_analyzer → store, per match_id
      src/main.py — original Phase-1 bootstrap script; superseded by importer/backfill (see §4, Finding A)
```

Two independent "leaf" pipelines currently exist downstream of `analyzer.py`/`game_state.py`:
1. The **macro coaching chain** (`macro_analyzer` → `store` → `aggregate` → `profile/generator` → `insights/engine` → `ai/`), fully wired end-to-end and exercised against 20 real games.
2. The **item recommendation chain** (`game_state` → `item_recommender`), fully wired and exercised against one real game, but **not yet connected to a batch runner** — today it only runs one match at a time via its own `main()`, unlike the macro chain which `importer.py` drives automatically for every new match.

## 2. Data Flow: Riot API → raw data → analysis → insights → recommendations

| Stage | Module(s) | Input | Output | Notes |
|---|---|---|---|---|
| Retrieval | `src/riot/client.py` | Riot ID, region | raw match/timeline JSON | Thin wrapper, no business logic |
| Raw storage | `src/history/importer.py` | raw JSON | `data/raw_matches/*.json` | Dedup by match_id before any API call |
| Structured extraction | `src/analysis/analyzer.py` | raw match | flat per-game stats dict | Pure function, no knowledge lookups |
| Timeline extraction | `src/analysis/timeline_analyzer.py` | raw timeline | per-event derived facts | Best-effort; `None` result if timeline missing/failed |
| Rule application | `src/analysis/macro_analyzer.py` | structured stats (+ timeline) | pattern list w/ concern/tier/confidence | Only place knowledge de-prioritization happens |
| Persistence | `src/history/store.py` | analysis + macro result | one record in `game_history.json` | Upsert by match_id |
| Aggregation | `src/history/aggregate.py` | full history list | most-played, averages, repeated patterns, trends | Pure function over the stored list |
| Profile shaping | `src/profile/generator.py` | aggregation output | `profile_summary.json` | Shape-only, reuses `aggregate.py` math |
| Insight shaping | `src/insights/engine.py` | profile summary | `player_insights.json` | Confidence is a step function of game count |
| (Optional) AI phrasing | `src/ai/*` | insights + profile summary + knowledge | `coaching_report.json` | Opt-in only per `ROADMAP.md`; not yet made the default-free path (see §5) |
| Game-state extraction | `src/analysis/game_state.py` | a completed raw match | `GameSnapshot` dict | Source-agnostic by design — this is the seam Phase 3 (live data) will extend |
| Item recommendation | `src/analysis/item_recommender.py` | `GameSnapshot` + item knowledge + Data Dragon catalog | ranked, explainable recommendations | Fully deterministic, no ML/LLM |

The pipeline is a **strict left-to-right pipeline with no back-edges** — nothing downstream ever mutates something upstream, and every stage's output is a plain dict/JSON file, not a live object handed forward. This is a real strength: any stage can be re-run independently from its input file.

## 3. Every Module and Its Responsibility

| Module | Responsibility |
|---|---|
| `src/riot/client.py` | Riot match-v5 REST calls: puuid lookup, match ID list, match detail, timeline |
| `src/riot/data_dragon.py` | Static Data Dragon item catalog: fetch, cache, name/id lookup |
| `src/analysis/analyzer.py` | Raw match → flat structured per-game stats (no rules, no knowledge) |
| `src/analysis/timeline_analyzer.py` | Raw timeline → per-event derived facts (death timing, objective participation, fight participation) |
| `src/analysis/macro_analyzer.py` | Structured stats (+ timeline) → threshold-based pattern flags, knowledge-aware de-prioritization |
| `src/analysis/game_state.py` | Completed match → source-agnostic `GameSnapshot` (team aggregates, `is_fed`, `game_state`) |
| `src/analysis/item_recommender.py` | `GameSnapshot` + item knowledge + item catalog → ranked, scored, explainable item recommendations |
| `src/knowledge/loader.py` | Parses champion/role markdown into structured dicts (fixed section template) |
| `src/knowledge/item_loader.py` | Parses item markdown into structured dicts (five-field-per-item template; sibling to `loader.py`, not shared code — see §4, Finding D) |
| `src/history/store.py` | Flat-JSON persistence of one record per game, upsert by match_id |
| `src/history/aggregate.py` | Pure math over the stored history list: averages, repeats, trends |
| `src/history/importer.py` | Orchestrates retrieval → analysis → storage for N match IDs; owns dedup and per-match failure isolation |
| `src/history/backfill.py` | Thin CLI wrapper over `importer.run_import()` for bulk historical pulls |
| `src/profile/generator.py` | Shapes aggregation output into the fixed `profile_summary.json` schema |
| `src/insights/engine.py` | Shapes profile summary into `player_insights.json` (strengths/weaknesses/priorities) |
| `src/ai/prompt_builder.py` | Assembles a grounded prompt from insights + knowledge — no API calls |
| `src/ai/validator.py` | Strips any AI-output item not actually present in the source insights |
| `src/ai/client.py` | Thin Anthropic API wrapper — the one paid, opt-in path |
| `src/ai/report_generator.py` | Orchestrates prompt → generate → validate → `coaching_report.json` |
| `src/main.py` | **Superseded bootstrap script** — see Finding A below |

## 4. Findings

### A. Dead/superseded code: `src/main.py`

`src/main.py` still implements the original Phase-1 workflow (fetch most recent match, find participant by `puuid`, print a plain-text summary) and has its own **duplicate `find_participant(match, puuid)`** — a second implementation of exactly what `src/analysis/analyzer.py`'s `find_participant(match, game_name, tag_line)` already does, just keyed differently (puuid vs. Riot ID). `README.md` still describes this as the "Next Milestone," but `src/history/importer.py` + `backfill.py` have fully superseded it — they do everything `main.py` does plus analysis, macro rules, and storage. `src/main.py` is not called by anything else in the codebase.

**Recommendation:** not a "large destructive change" to remove, but worth a deliberate decision later — either delete it and update `README.md`, or repurpose it as a genuinely useful single-match CLI (`analyze one match and print a summary`) built on the existing `analyzer.py`/`macro_analyzer.py` functions instead of duplicating extraction logic. Left untouched in this pass per your constraint on large changes.

### B. Duplicate `PROJECT_ROOT` boilerplate

`PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent` (or `.parent.parent` in `main.py`, one level shallower) is independently repeated in 10 files: `data_dragon.py`, `engine.py`, `generator.py`, `loader.py`, `item_loader.py`, `store.py`, `importer.py`, `report_generator.py`, `macro_analyzer.py`, `item_recommender.py`, `analyzer.py`. Harmless today (each file correctly locates the project root), but it's the same three-line idiom copy-pasted eleven times.

**Recommendation:** a single `src/paths.py` exposing `PROJECT_ROOT` would remove the duplication. **Not done in this pass** — touching eleven files' import lines is a broader change than "low-risk cleanup" should cover in an unattended session, even though each individual edit is trivial.

### C. Three different "confidence" vocabularies

- `macro_analyzer.py`: per-pattern `confidence` ∈ `"high" | "medium" | "unavailable"`, plus a separate `tier` ∈ `"low" | "adequate" | "good"`.
- `insights/engine.py`: `confidence` ∈ `"high" | "medium" | "low"`, derived from a raw game-count step function.
- `item_recommender.py`: `confidence_tier` ∈ `"high" | "medium" | "low"` **plus** a numeric `confidence_score` (0–100) with a named breakdown.

These are genuinely different concepts (data availability vs. evidence volume vs. a deterministic point score) and each is well-designed *in isolation* — this isn't a bug. But a future reader (or a future AI-layer prompt) skimming `confidence` fields across three JSON outputs will find the same word meaning three different things with three different value sets. Worth standardizing vocabulary (not necessarily mechanism) before a UI ever has to render all three side by side — see `UI_DESIGN.md`.

### D. Structural duplication between `loader.py` and `item_loader.py` (by design, documented tradeoff)

Both files parse markdown into structured dicts via a heading-scan + bullet-collection loop. `item_loader.py` was deliberately kept as a *sibling* rather than a generalization of `loader.py`, because item knowledge's shape (item-name headings, five fixed fields per item) is different enough from champion/role knowledge's shape (fixed section names, flat bullet lists) that sharing a parser would mean threading a section-key map through `loader.py`'s existing callers for no clear benefit. The tradeoff: `item_loader.py`'s `_parse_core_build()` re-implements the same "strip `- ` prefix from a bullet line" logic `loader.py`'s `_bullets()` already has. This is a small, deliberate, previously-reasoned duplication — flagged here for visibility, not treated as a defect.

### E. Item-trigger vocabulary only scales via code, not markdown

Item *knowledge* (which item, why, for which champion) scales cleanly by adding markdown files — no code changes needed. But item *trigger types* (`enemy_ap_heavy`, `enemy_has_fed_carry`, `game_state_ahead`, etc.) only scale by editing `TRIGGER_KEYWORDS` and `_evaluate_triggers()` in `item_recommender.py`. Adding a genuinely new situational axis (e.g., "enemy has heavy CC lockdown" or "enemy has a split-pusher") requires a code change, not just a markdown edit. This is a real, deliberate ceiling (see `ROADMAP.md`'s rejection of a bracket-syntax condition DSL as overkill for one user) — worth naming explicitly rather than letting it surface as a surprise later. See `KNOWLEDGE_SYSTEM_PLAN.md` §3.

### F. No live/long-running execution model exists yet

Every entrypoint in the codebase today (`analyzer.main()`, `macro_analyzer.main()`, `importer.run_import()`, `item_recommender.main()`) is a **one-shot script**: load input, compute, write output, exit. Nothing in the architecture currently models a long-running poll loop, a persistent connection, or incremental/streaming state. This isn't a flaw in what exists — it's a genuine gap that Phase 4 (live game state) must design for from scratch; see `LIVE_SYSTEM_DESIGN.md`.

### G. Naming: raw vs. derived gold fields

`analyzer.py` keeps Riot's raw field name `gold_earned`; `store.py`/`macro_analyzer.py` derive `gold_per_minute`; `game_state.py` introduces `current_gold` / `total_gold_earned` for the `GameSnapshot` shape. All three are correct and non-conflicting in their own module, but a reader moving between the macro pipeline and the item-recommendation pipeline needs to know these aren't the same field reused three ways — they're three different derivations of one underlying Riot stat. Documented here so it doesn't get "fixed" into an accidental bug later.

### H. Stale/inconsistent `.gitkeep` files (see `TEST_AUDIT.md`/cleanup section)

`src/ai/.gitkeep`, `src/analysis/.gitkeep`, `src/riot/.gitkeep` are still tracked in git even though all three directories now contain real modules — the `.gitkeep`s were only ever needed to keep the empty directories present in early commits. `knowledge/fundamentals/.gitkeep` and `knowledge/matchups/.gitkeep` are still legitimately needed (those directories are still empty). Addressed in Phase 7.

### I. `tests/` has no `__init__.py`

Every `src/` subpackage (`ai`, `analysis`, `history`, `insights`, `knowledge`, `profile`, `riot`) has an explicit (empty) `__init__.py`; `tests/` does not, and relies on Python's implicit namespace-package behavior instead. Tests all pass this way — it isn't broken — but it's an inconsistency with the rest of the project's explicit-package convention. Addressed in Phase 7.

## 5. Can the current architecture support...?

| Future capability | Verdict | Why |
|---|---|---|
| **Post-game coaching** | ✅ Already built | Full chain from raw match to `player_insights.json`/`coaching_report.json` exists and runs against real data today. |
| **Item recommendations** | ✅ Already built | `game_state.py` → `item_recommender.py` runs end-to-end against real matches; only gap is it isn't yet wired into `importer.py`'s automatic per-match run (currently a separate manual `main()` invocation — a wiring task, not an architecture problem). |
| **Live game state** | ⚠️ Partially — data model ready, runtime model is not | `GameSnapshot` was deliberately designed source-agnostic specifically so a live builder could produce the same shape (see `game_state.py`'s docstring and `ROADMAP.md` Phase 3). What's missing is anything resembling a poll loop, a new data source client, or incremental-state handling — see Finding F and `LIVE_SYSTEM_DESIGN.md`. |
| **Overlay UI** | ⚠️ Not yet, but not blocked | No UI code exists anywhere. Because every stage already communicates via plain JSON files rather than in-process objects, a UI is architecturally a pure consumer with no coupling risk — but it has nothing to render in real time until the live-state gap above is closed. See `UI_DESIGN.md`. |
| **Conversational coaching** | ⚠️ Foundation exists, not built | `src/ai/prompt_builder.py` and `validator.py` were explicitly designed to be reusable outside the one-shot report path (per `ROADMAP.md` §6), but no chat loop, message history, or turn-taking logic exists. Would be new code, not a rework of what's there. |
| **Local AI models** | ✅ Architecturally ready, not implemented | `src/ai/client.py` is one interchangeable backend behind an implicit `generate(prompt, schema) -> str` contract; a `backends/local.py` (per `ROADMAP.md`) slots in without touching `prompt_builder.py`, `validator.py`, or `report_generator.py`. Not built because there is nothing to wire it to yet — correctly deferred, not blocked. |

**Overall assessment:** the architecture is in good shape for what's been asked of it. The strict pipeline-of-JSON-files structure is the single biggest reason every "can it support X" answer above is "yes" or "partially, by extension" rather than "no" — nothing here requires an in-place rewrite to grow. The two real gaps are (1) no long-running/live execution model yet, which is expected since it hasn't been needed until now, and (2) the AI layer's free-by-default backend from `ROADMAP.md` §1 hasn't been implemented yet (only the paid `client.py` path exists) — worth prioritizing before item (1), since it's a smaller, already-fully-designed piece of work.
