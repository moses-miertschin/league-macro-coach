# LeagueMacroCoach — Revised Development Roadmap

Written in response to a architecture course-correction: this is a personal
training tool, not a SaaS product, and must not depend on continuous paid
API spending. This document is strategy only — no code changes accompany
it. Read alongside `CHECKPOINT.md`, which this does not replace or
contradict; it redirects one phase (`src/ai/`) and adds two new ones
(itemization, live game state).

## 1. What must remain untouched

Everything upstream of "phrasing a report" is deterministic, already built,
already tested, and stays exactly as-is:

- `src/riot/client.py` — Riot match-v5 REST client
- `src/analysis/analyzer.py`, `macro_analyzer.py`, `timeline_analyzer.py`
- `src/knowledge/loader.py` and `knowledge/champions/*.md`, `knowledge/roles/*.md`, `knowledge/coaching_philosophy.md`
- `src/history/store.py`, `aggregate.py`, `importer.py`, `backfill.py`
- `src/profile/generator.py`, `src/insights/engine.py`
- All existing tests, `data/player_profile.json`, `.env` discipline

None of this required a network call to an LLM before, and none of it
should start now. The only thing that changes is what happens *after*
`player_insights.json` and `profile_summary.json` exist.

## 2. The core problem with the current `src/ai/`

As built, `report_generator.py` has exactly one path: build a prompt, call
`claude-opus-5`, validate the response. That's fine as a *capability*, but
wrong as a *default* — running the tool at all now means either paying per
report or wiring a key you have to remember to remove. For a personal tool
you'll run after every ranked game, that's a standing cost, not a one-time
one.

The fix isn't to delete what was built (`prompt_builder.py` and
`validator.py` are good, reusable work) — it's to stop treating "call an
LLM" as the only way to produce a report, and make LLM involvement one
interchangeable **backend** instead of the only path.

## 3. Redesigned AI layer

### Does `src/ai/` still exist? Yes — reframed around a backend interface.

```
src/ai/
    prompt_builder.py         # UNCHANGED — shared by every backend
    validator.py               # UNCHANGED, but now load-bearing for ALL backends
    report_generator.py        # CHANGED — picks a backend, defaults to free
    backends/
        __init__.py
        deterministic.py       # NEW — default. No network, no cost, no LLM.
        manual.py               # NEW — Claude Max copy/paste workflow
        api.py                  # MOVED from client.py — opt-in only, paid
```

**The backend "interface" is one function signature, not a class
hierarchy:** `generate(prompt: str, schema: dict) -> str`. Three modules
implement it; `report_generator.py` picks one by name and doesn't care
which. This is intentionally the smallest abstraction that lets three
implementations coexist — no plugin registry, no ABC, no config schema
beyond a single string.

#### `backends/deterministic.py` (new, default, zero cost)

Renders `coaching_report.json` directly from `player_insights.json` +
`profile_summary.json` + the *existing* qualitative knowledge base —
**no model call at all**. For each flagged weakness, it looks up the
matching `common_mistakes` / `improvement_categories` bullet already
written in `knowledge/champions/{champion}.md` and uses that text verbatim
(or with light templating) as the `coaching_explanation` /
`suggested_practice`. This is possible *because* the knowledge base is
already hand-curated prose, not numeric thresholds — the qualitative
writing you did there is exactly the content an LLM would otherwise be
asked to reconstruct. `validator.py` still runs over its output (cheap,
and it's the same safety net every backend gets) even though a
template-driven renderer can't hallucinate a pattern name.

This becomes the **default** `ai_backend` in `player_profile.json`. Running
the full pipeline end-to-end costs nothing, forever, unless you explicitly
opt into a different backend.

#### `backends/manual.py` (new, supports Claude Max manually)

For when you want LLM-quality phrasing without an API key: writes the
built prompt to `reports/generated_reports/coaching_prompt.txt`, prints
instructions to paste it into Claude Max (web or desktop) and save the
reply into `coaching_response.json`. On the next run, if that response
file exists and is newer than the prompt, it's read, parsed, and passed
through the *same* `validator.py` grounding check as the API path — a
pasted-in response gets no less scrutiny than an API one. This is a
one-person, zero-infrastructure way to get LLM output through a UI you
already pay for (Claude Max), with no API billing at all.

#### `backends/api.py` (moved from `client.py`, opt-in, paid)

Exactly what `src/ai/client.py` already does today. Nothing about it is
wrong — it's just no longer the only option, and no longer the default.
Selecting it should require an explicit, visible choice (a
`player_profile.json` field, not an environment-variable side effect),
so nobody accidentally leaves it on and gets billed per game.

#### Local model support (future, not built now)

The same `generate(prompt, schema) -> str` interface is what a
`backends/local.py` would implement later against something like Ollama
or llama.cpp — a local HTTP call instead of `anthropic.Anthropic()`. This
isn't built now (nothing to build against yet — YAGNI), but the interface
already accommodates it without touching `prompt_builder.py`,
`validator.py`, or `report_generator.py` again.

### Responsibilities moved away from the LLM

- **Deciding what the weaknesses/strengths are** — already rule-based
  (`macro_analyzer.py`, `aggregate.py`); was never the LLM's job, unchanged.
- **Ranking priority** — already deterministic (`games_flagged` counts in
  `insights/engine.py`); unchanged.
- **Producing the actual coaching prose for the common case** — this is
  the new move. The deterministic backend proves that most of what the
  prior design asked an LLM to *generate*, it was actually asked to
  *retrieve and lightly rephrase* from your own knowledge files. That
  doesn't need a model.
- **What's left for an LLM, if you choose to use one at all**: synthesizing
  a *single* narrative across several weaknesses at once, or phrasing that
  reads less template-y. That's a genuine, optional quality upgrade — not
  a requirement for the tool to function.

## 4. Item recommendation engine (rule-based, new)

Lives in `src/analysis/item_recommender.py` — it's the same kind of
deterministic module as `macro_analyzer.py`, not a new top-level system.

**Inputs:** champion, role, enemy team composition, currently-owned items,
available gold, (later) game phase/time.

**Knowledge source:** new `knowledge/items/` — hand-curated qualitative
markdown, same format discipline as `knowledge/champions/`: a champion's
core build, situational triggers ("enemy has 2+ heavy AD assassins →
prioritize X"), and matchup notes. Parsed with a loader that follows
`src/knowledge/loader.py`'s existing section/bullet pattern — this is
qualitative rule content, not a numeric optimizer, for the same reason the
champion knowledge base isn't one: it's the kind of judgment a human coach
already writes down, not a thing to fit a model to.

**Static data, not live data, not ML:** item costs/stats can come from
Riot's public Data Dragon JSON (a one-time or periodic download, cached
locally) — a thin client exactly like `src/riot/client.py`, no
authentication, no rate limit concerns.

**Output:** ranked recommendations, each with a `reason` string that names
the specific knowledge-base rule that triggered it — this is what
satisfies "explain WHY," and it's free, because the reason *is* the rule
that fired, not a generated explanation of one.

**Explicitly not built:** a machine-learned, win-rate-optimizing item
build system (the OP.GG/Lolalytics approach). That would require large
third-party statistical datasets this project has deliberately excluded as
a foundation (per `CHECKPOINT.md` §9 — external sources are supplementary
only). Staying qualitative/rule-based here is a continuation of that
decision, not a new one.

## 5. Live game-state analysis engine (new, biggest new subsystem)

This needs a genuinely different data source than everything built so
far: Riot's **Live Client Data API**, a local HTTP endpoint
(`127.0.0.1:2999`) the League client exposes only while a match is in
progress — not the cloud match-v5 REST API `src/riot/` already wraps.
Because it's a different integration surface (local polling vs. Riot
Games' servers), it gets its own top-level module rather than living
inside `src/riot/`:

```
src/live/
    client.py            # thin wrapper around the local live-data endpoint
    state_analyzer.py     # deterministic rules over a live snapshot
```

`state_analyzer.py` reuses the same rule-writing style as
`macro_analyzer.py` (fixed thresholds, `confidence`/`tier` fields, honest
`"unavailable"` markers) but evaluated against a live, partial game state
instead of a completed match: objective spawn timers, whether vision was
placed recently, whether the player is near/away from an impending
objective. It can also call `item_recommender.py` with the live snapshot's
current gold/items/enemy comp to get live item suggestions.

**Output for this phase:** structured JSON written to disk on a polling
interval (e.g. every 5–10s). No UI. The reason to stop here first: the
live data API's exact shape and reliability needs to be validated against
real games the same way the match timeline was validated before rules
were built on it (see `CHECKPOINT.md` — timeline enrichment happened only
after the schema was confirmed against real data). Building rules against
an unverified data shape is how the `participant_id` bug from the timeline
work happens twice.

## 6. Overlay system (deferred, UI, not started)

An overlay is a presentation layer over `src/live/`'s output — a
transparent always-on-top window, built with something like `pywebview`
or a small Electron shell, reading whatever `state_analyzer.py` is
writing. It has no analysis logic of its own and depends entirely on
Phase 5 (below) being proven against real games first. This roadmap
reserves the extension point (live engine emits structured, stable JSON)
without designing or building any UI now — that's a separate decision
once there's something real to display.

## 7. What requires what

| Capability | Riot/game data | Deterministic logic | ML | LLM |
|---|---|---|---|---|
| Post-game macro facts (deaths, CS, vision, objectives) | ✅ match-v5 + timeline | ✅ existing rules | — | — |
| Player trends/profile aggregation | ✅ (from above) | ✅ existing | — | — |
| Coaching report phrasing (default) | — | ✅ new deterministic backend | — | — |
| Coaching report phrasing (optional polish) | — | — | — | optional, opt-in |
| Item recommendations | ✅ Data Dragon (static) | ✅ new rule engine | — | optional phrasing only |
| Live game-state tips | ✅ live client API (local) | ✅ new live rules | — | not recommended (latency/cost, real-time) |
| Overlay | — | (presentation only) | — | — |

**No component in this roadmap requires machine learning.** Everything
achievable with hand-curated rules stays rule-based, per the project's
existing philosophy of "never fabricate, prefer evidence-backed decisions"
— a trained model is itself a kind of fabrication risk (it can be
confidently wrong in ways a cited rule can't). If a genuine ML use case
shows up later (e.g., a personalized win-probability model), that's a
distinct, much later, explicitly-opted-into research phase — not something
this roadmap builds toward by default.

## 8. What changes vs. what's removed in `src/ai/`

| File | Disposition |
|---|---|
| `prompt_builder.py` | Unchanged — reused by `manual.py` and `api.py` |
| `validator.py` | Unchanged — becomes the universal safety net for every LLM-based backend |
| `client.py` | Moved to `backends/api.py`; behavior unchanged, but no longer called by default |
| `report_generator.py` | Changed — adds backend selection (default: deterministic); no other logic changes |
| Nothing is deleted. | The API path stays fully available, just opt-in. |

---

## Implementation Plan (Phases)

### Phase 1 — Backend abstraction + free default
1. Add `player_profile.json["ai_backend"]` field, default `"deterministic"`.
2. Create `src/ai/backends/` package; move existing `client.py` logic into
   `backends/api.py` unchanged.
3. Write `backends/deterministic.py`: template-render `coaching_report.json`
   directly from insights + knowledge bullets, no network.
4. Write `backends/manual.py`: prompt-file-out / response-file-in workflow.
5. Update `report_generator.py` to select a backend by name and always run
   `validator.py` on LLM-sourced output (API or manual); deterministic
   output skips validation (nothing to ground-check — it only ever quotes
   real data).
6. Update `tests/test_ai_report_generator.py` (and add
   `test_deterministic_backend.py`) — assert-based, no network, matching
   existing style.
7. **Outcome:** running the full pipeline end-to-end costs $0 by default.

### Phase 2 — Item recommendation engine
1. Write `knowledge/items/{yone,akali,fizz,syndra}.md` + a mid-lane
   generic file, following the existing champion-knowledge markdown
   template.
2. Extend/sibling the knowledge loader for item files.
3. Fetch and cache Riot Data Dragon item data via a thin
   `src/riot/data_dragon.py` (or `src/items/static_data.py`) client.
4. Write `src/analysis/item_recommender.py` — pure function, rule-matched,
   reason-per-recommendation.
5. Assert-based tests with fixture enemy comps → expected recommendation +
   reason.

### Phase 3 — Live game-state foundation
1. Write `src/live/client.py` against the Live Client Data API; validate
   its real shape against an actual live game before building rules on it
   (same discipline as the timeline work).
2. Write `src/live/state_analyzer.py`: live-adapted macro rules +
   integration with `item_recommender.py`.
3. Polling loop writing structured JSON snapshots to disk. No UI.
4. Tests against captured/fixture live-data snapshots (no live game
   required to run the suite).

### Phase 4 — Overlay (deferred)
Only after Phase 3 is validated against real games. Presentation-only;
consumes Phase 3's JSON output. Design deferred to its own future
conversation — not scoped further here.

### Phase 5 — Optional LLM synthesis polish (revisit later)
Once Phases 1–3 are solid and actually in daily use, decide — based on
real experience, not assumption — whether `manual.py` or `api.py` output
is worth reaching for over the deterministic default, and for which
situations specifically (e.g., only when 3+ weaknesses fire in one game).
Not scheduled; revisit only if the deterministic backend proves
insufficient in practice.
