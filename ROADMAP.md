# LeagueMacroCoach — Development Roadmap (Revised)

**Strategic pivot, superseding the prior version of this document.** The project's primary goal is no longer AI coaching — it is a **deterministic League intelligence system**: live recommendations, drafting assistance, itemization, rune decisions, matchup analysis, and (eventually) an overlay UI. AI is now formally an **optional explanation layer**, never the decision-maker, project-wide — not just for the post-game coaching report where this rule originated.

This document is strategy only. No code accompanies it. See `CHECKPOINT.md` for what's actually built as of this revision; see `ARCHITECTURE_AUDIT.md`, `LIVE_SYSTEM_DESIGN.md`, `KNOWLEDGE_SYSTEM_PLAN.md`, `UI_DESIGN.md`, `PATCH_SYSTEM.md` for the detailed designs this roadmap builds on rather than repeats.

## What This Changes vs. the Prior Roadmap

- **De-prioritized:** the AI layer's free-by-default backend (`src/ai/backends/deterministic.py`). Nothing in the pipeline ever calls the paid Anthropic backend automatically — the practical "never requires paid API spend" guarantee already holds without that refactor. Worth doing eventually, not urgent given the new focus.
- **Elevated:** live game-state features (`LIVE_SYSTEM_DESIGN.md`), previously a "someday" phase, are now central.
- **New, not previously scoped anywhere:** drafting assistance and rune decisions. Both are genuinely new decision domains, not extensions of existing ones.
- **Unchanged:** everything already built (post-game pipeline, item recommendations, coaching aggregation, benchmark foundation) stays exactly as-is. This pivot is additive.

## 1. Systems Required for Live Decision-Making

"Live decision-making" spans three temporal phases, each with a different data source:

| Phase | When | System |
|---|---|---|
| Draft | Champion select | `src/draft/` (new) — LCU client + `DraftSnapshot` |
| In-game | Loading screen → game end | `src/live/` (reserved, designed in `LIVE_SYSTEM_DESIGN.md`) |
| Post-game | After the game | Already built |

The one piece of infrastructure bigger than either data client: a **shared polling/runtime model**. Every existing module is a one-shot script (load → compute → write → exit — see `ARCHITECTURE_AUDIT.md` Finding F). Draft and in-game both need something that stays alive, re-polls on an interval, and idles cleanly when no session exists. Build this once, shared by both phases — don't duplicate it per phase.

Second: a **shared recommendation output contract** (`type`, `recommendation`, `reason`, `evidence`, `confidence`, `priority`) that draft picks, rune choices, and in-game tips all conform to, so a future overlay renders one shape, not three. Formalize this only after real cases from phases below exist to check it against — not designed in the abstract up front.

## 2. Data Sources

| Source | Status | Notes |
|---|---|---|
| Riot match-v5 (cloud) | Built | Unchanged |
| Data Dragon (static) | Built | Extend for `runesReforged.json` |
| **LCU API** | New | Local API the League *client* exposes during champ select/lobby — distinct from Live Client Data API (different port, lockfile-token auth vs. unauthenticated). `/lol-champ-select/v1/session` is the key endpoint. |
| Live Client Data API | New, fully designed | Exactly per `LIVE_SYSTEM_DESIGN.md` — those constraints (no enemy gold, no map position, no recall event) are unchanged by this pivot. |

Still no external scraping. A deterministic draft advisor without statistical backing (matchup win rates, pro data) is necessarily coarser than a stats site — an accepted, stated tradeoff of "never fabricate," not a gap to quietly work around later.

## 3. Knowledge Bases

| Knowledge | Status |
|---|---|
| `knowledge/champions/`, `roles/`, `items/` | Built |
| `knowledge/matchups/` | Designed, empty — now load-bearing for draft too; reprioritize populating |
| `knowledge/runes/` | **New** — same five-field qualitative shape as items, reusing the same trigger vocabulary where possible |
| `knowledge/drafting/` | **New** — team-comp (5v5) granularity, distinct from per-lane `matchups/`; more patch-volatile, flag for `PATCH_SYSTEM.md`'s review cadence once built |
| Champion role/archetype static data | **New** — hand-curated first, same discipline as `champion_damage_types.json` |

Design note for when runes are built: extract the trigger-matching core currently embedded in `item_recommender.py` into a shared module both item and rune recommenders call, rather than duplicating `TRIGGER_KEYWORDS`. Noted now so it isn't duplicated later; not extracted speculatively today.

## 4. Modules to Build Before UI

In order:

1. Shared polling/runtime infrastructure. **Done** (`src/runtime/poller.py`).
2. `src/draft/` — LCU client + `DraftSnapshot`. **Done, and substantially further along than this line implies** — `src/draft/` now also has a native recommendation engine (`recommender.py`, both locked-champion callouts and pre-lock pick recommendations), an orchestration service (`service.py`), a runnable CLI (`cli.py`, `--once`/`--watch`), a local state publisher (`src/runtime/state_publisher.py`), and a real-fixture-validation capture tool (`capture.py`, `--capture-once`) — everything short of a real champion-select session ever having driven it and a UI to read the published state. See `CHECKPOINT.md` for the authoritative current inventory; this line is intentionally not rewritten in full here to avoid this strategy document drifting into a build log.
3. `knowledge/runes/` + rune recommender. Not started.
4. `knowledge/drafting/` + draft/synergy recommender (full 5v5 team-composition scoring — distinct from and bigger than the pairwise ally/enemy signals `src/draft/recommender.py` already has). Not started.
5. `src/live/` — per `LIVE_SYSTEM_DESIGN.md` (recall/item advisor, objective timer). Wave management stays explicitly out of scope — infeasible with available data, not merely deferred. Not started.
6. The shared recommendation-output contract, formalized once 2–5 exist. **Built earlier than this ordering anticipated** (`src/recommendations/schema.py`) — proven out by three real producers now (item via adapter, macro via adapter, draft natively), ahead of steps 3–5. Not a problem: the contract was designed to generalize across all five systems from the start, so building it early didn't require guessing at rune/live's specifics.
7. UI/overlay — not part of this roadmap.

## 5. AI vs. Deterministic (Project-Wide Policy)

- **Deterministic, required, zero AI dependency:** every recommendation engine — item, rune, draft/synergy, live in-game tips, benchmark comparison, macro coaching. Every ranking, severity, confidence score.
- **AI, optional, explanation-only, never load-bearing:** phrasing an already-computed decision. Any future draft/rune/live explanation reuses `src/ai/prompt_builder.py` + `validator.py`'s existing grounding pattern — one AI wrapper for the whole project, never one per domain.
- The system decides; AI, when used at all, only narrates the decision already made.
