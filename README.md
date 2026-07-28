# LeagueMacroCoach

A private, personal League of Legends coaching system. It retrieves ranked
match data, analyzes recurring macro mistakes, generates evidence-backed item
recommendations, and produces personalized improvement goals — all
rule-based and deterministic, with an optional (not required) AI-phrasing
layer grounded in a hand-curated knowledge base.

This is a solo, local tool — not a public service. Match data and generated
reports stay on disk and out of version control (see `.gitignore`).

## Player Profile

- Riot ID: `HelloKittler#meow`
- Region: NA
- Role: Mid
- Champion pool: Yone, Akali, Fizz, Syndra

## Architecture

```
Riot API ──▶ src/riot/client.py ──▶ data/raw_matches/, data/raw_matches/timelines/
Data Dragon ─▶ src/riot/data_dragon.py ─▶ data/static/ (cached item catalog)
                              │
                              ▼
              src/analysis/analyzer.py, timeline_analyzer.py
                (structured per-game + per-event stats)
                              │
              knowledge/champions/, knowledge/roles/ ◀┤ (src/knowledge/loader.py)
                              ▼
                  src/analysis/macro_analyzer.py
                (rule-based macro pattern flags)
                              │
                              ▼
          src/history/store.py → data/database/game_history.json
                              │
                              ▼
       src/history/aggregate.py → src/profile/generator.py
                              │
                              ▼
                  src/insights/engine.py → player_insights.json
                              │
                              ▼
          src/ai/ (optional, opt-in phrasing layer — not required to use this tool)

                     ── a second, independent pipeline ──

              src/analysis/game_state.py (GameSnapshot, source-agnostic)
                              │
              knowledge/items/ ◀┤ (src/knowledge/item_loader.py)
                              ▼
              src/analysis/item_recommender.py
        (rule-based, explainable item recommendations — no ML, no AI)
```

**Riot API is the source of truth for match data.** Data Dragon (Riot's
static per-patch data CDN) is the source of truth for item costs/tags/build
paths — no API key, no rate limits. The `src/` layout keeps Riot-specific
code isolated in `src/riot/` so additional external sources (OP.GG, U.GG,
Lolalytics, patch notes) can be added later as their own modules without
becoming the foundation the system depends on. None of those sources are
implemented, and none are required.

**Every recommendation is deterministic and explainable.** Detected macro
patterns and item recommendations both trace back to a named rule and, for
items, a full evidence + confidence-score breakdown — nothing is generated
by a model. The one optional AI layer (`src/ai/`) only phrases
already-computed findings from `player_insights.json`; it never decides what
the findings are, and the tool is fully usable without it. See
`ARCHITECTURE_AUDIT.md` for the full data-flow breakdown.

## Draft Assistant (Champion Select)

A runnable command-line tool that watches League's champion select and
prints/publishes deterministic draft guidance — no UI required. It reads
the League client's local, unauthenticated-to-us API (via the lockfile
League itself writes on launch), builds a source-agnostic draft snapshot,
and runs it through the same rule-based recommendation engine as the rest
of this tool (no AI, no scraped stats, no win rates).

```
# One poll, publish the result, print a status line, exit:
python -m src.draft.cli --once

# Poll repeatedly until you press Ctrl+C:
python -m src.draft.cli --watch
```

Options (both modes): `--output PATH` (default `reports/runtime/draft_state.json`),
`--lockfile PATH` (default: the standard League install location),
`--verbose` (also print the full JSON state each poll). `--watch`-only:
`--interval SECONDS` (default `5.0`).

The published JSON always has this shape:

```json
{
  "state_schema_version": 1,
  "state": "champ_select_active",
  "draft_snapshot": { "...": "..." },
  "recommendations": [ { "...": "..." } ],
  "champion_catalog_version": "14.1.1",
  "warnings": [],
  "error": null
}
```

`state` is one of `league_client_unavailable` (League isn't open),
`idle_no_champ_select` (League is open, nothing to draft right now),
`champ_select_active` (a real session was found and processed — covers
both picking a champion and reviewing an already-locked one), or
`processing_error` (something unexpected happened during that poll — never
silently treated as idle). The file is written atomically, so nothing
reading it will ever see a partial write. Requires no network calls beyond
the League client itself already running on this machine, and no paid
service of any kind.

Champion-profile knowledge currently covers only the player's own pool
(Yone, Akali, Fizz, Syndra, Pyke) — see `CHECKPOINT.md` Sec.3 for the exact
current coverage and scoring limitations.

## Folder Structure

- `data/raw_matches/` — raw match + timeline JSON pulled from the Riot API.
- `data/database/` — `game_history.json`, one upserted record per game.
- `data/static/` — cached Data Dragon item data + hand-curated champion damage-type classifications.
- `knowledge/fundamentals/` — general macro concepts (not yet populated).
- `knowledge/champions/` — champion-specific coaching notes (Yone, Akali, Fizz, Syndra, Pyke).
- `knowledge/roles/` — role-level coaching notes (Mid, Support).
- `knowledge/items/` — champion-specific + general item-recommendation knowledge.
- `knowledge/matchups/` — matchup-specific notes (not yet populated — see `KNOWLEDGE_SYSTEM_PLAN.md`).
- `knowledge/coaching_philosophy.md` — principles the (optional) AI layer follows when phrasing feedback.
- `reports/generated_reports/` — generated analysis, macro patterns, insights, and item recommendations, one set per match.
- `reports/runtime/` — `draft_state.json`, published by `src/draft/cli.py`/`src/runtime/state_publisher.py` (generated, gitignored).
- `src/riot/` — Riot API client + Data Dragon static-data client (items and champions).
- `src/analysis/` — structured extraction and rule-based analysis (macro patterns, timeline facts, item recommendations).
- `src/history/`, `src/profile/`, `src/insights/` — persistence, cross-game aggregation, and insight generation.
- `src/knowledge/` — markdown knowledge-file parsers (macro-coaching notes, item guidance, champion draft profiles).
- `src/draft/` — LCU client, draft snapshot builder, draft recommender, runtime service, and the `--once`/`--watch` CLI (see "Draft Assistant" above).
- `src/runtime/` — `SessionPoller` (shared polling foundation) and `state_publisher.py` (atomic local JSON output).
- `src/ai/` — optional, opt-in prompt/validation/report layer (not required to use the rest of the tool).
- `src/main.py` — original Phase-1 bootstrap script, superseded by `src/history/importer.py`/`backfill.py` — see `ARCHITECTURE_AUDIT.md` Finding A.
- `.env.example` — template for required secrets/config; copy to `.env` (gitignored).
- `requirements.txt` — runtime dependencies.

## Status

Rule-based pipeline complete and exercised against 20 real ranked games:
Riot match + timeline retrieval, macro pattern analysis, cross-game
aggregation, player insights, and a deterministic item recommendation
engine are all built, tested, and validated against real match data. The AI
phrasing layer exists but is opt-in only. See `CHECKPOINT.md` for full
build history and `ARCHITECTURE_AUDIT.md` / `ROADMAP.md` for current
architecture and what's next.

## Planning & Audit Documents

- `CHECKPOINT.md` — build history and architectural decisions.
- `ROADMAP.md` — phased development plan (AI backend redesign, item engine, live game state, UI).
- `ARCHITECTURE_AUDIT.md` — full module inventory, data flow, and identified findings.
- `TEST_AUDIT.md` — test coverage review and recommended future tests.
- `KNOWLEDGE_SYSTEM_PLAN.md` — how champion/item/matchup knowledge should scale.
- `LIVE_SYSTEM_DESIGN.md` — design for the future live game-state coaching system.
- `UI_DESIGN.md` — design for the future desktop/overlay interface.
- `PATCH_SYSTEM.md` — how the system handles League's per-patch changes.

## Next Milestone

See `ROADMAP.md` — the AI layer's free-by-default backend (deterministic
report rendering, no required paid API calls) is the recommended next step,
ahead of live game-state work.
