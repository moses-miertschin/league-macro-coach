# LeagueMacroCoach — Shared Recommendation System Design

Design only, per instruction — no code. Read `CHECKPOINT.md` and `ROADMAP.md` in full before writing this; grounded in the *actual* current output shapes of `item_recommender.py` and `coaching/priorities.py`, not an idealized version of them.

## Grounding: What Actually Exists Today

Two systems already produce recommendation-shaped output, and they disagree with each other:

**`item_recommender.py`'s `recommend_items()`** — rich, ~13 fields per entry: `item`, `priority`, `reason`, `triggered_rules`, `evidence`, `confidence_score`, `confidence_tier`, `confidence_breakdown`, `conflicting_signal`, `cost`, `builds_toward`, `purchasable_now`, `source`, `recommendation_type`.

**`coaching/priorities.py`'s lessons** (the actual prescriptive layer for macro coaching — not `macro_analyzer.py`'s raw `detected_patterns`, which are descriptive findings, not recommendations) — a different 7 fields: `priority`, `issue`, `evidence`, `why_it_matters`, `practice_goal`, `scope`, `confidence`.

This matters for the design: **`priorities.py`'s lessons are already the closest thing to a "shared recommendation" that exists in this codebase.** The unification below is informed by reconciling these two real shapes, not invented from a blank page. It also settles a question before it's asked: "macro recommendations" means `priorities.py`'s lessons, not `macro_analyzer.py`'s raw patterns — those patterns feed `player_insights.json` too and aren't themselves prescriptive.

`ARCHITECTURE_AUDIT.md` Finding C already flagged three incompatible confidence vocabularies across the codebase. This unification is the natural place to finally resolve that, not a separate cleanup task.

## 1. Where This Should Live

**New top-level package: `src/recommendations/`**, containing a schema module only (`schema.py`) — no business logic, mirroring exactly how `src/benchmark/benchmark_schema.py` is a pure shape-definition-plus-`validate_*`-function with zero analysis logic.

Why a new package rather than folding into an existing one: the schema is consumed *across* `src/analysis/` (item, future draft/rune), a future `src/live/`, and `src/coaching/` (which aggregates and would adapt macro lessons). Putting it inside any one of those creates a backwards dependency — e.g., if it lived in `src/coaching/`, then `src/analysis/item_recommender.py` would have to depend on `src/coaching/`, inverting the current flow where `coaching/` depends on `analysis/`, never the reverse. A neutral package avoids that inversion entirely.

```
src/recommendations/
    __init__.py
    schema.py   # REQUIRED_FIELDS, enums, validate_recommendation() -- shape only
```

## 2. The Shared JSON Schema

```json
{
  "system": "item",
  "category": "core_build",
  "subject": "Zhonya's Hourglass",
  "recommendation": "Zhonya's Hourglass",
  "reason": "Zhonya's Hourglass: Valuable when behind, or facing a fed enemy carry...",
  "evidence": [{"fact": "enemy_has_fed_carry", "champions": ["Caitlyn"]}],
  "confidence": "high",
  "confidence_score": 75,
  "severity": "high",
  "priority": 1,
  "source": "champion_knowledge",
  "details": {"cost": 3250, "purchasable_now": null, "recommendation_type": "complete_item"}
}
```

| Field | Required | Notes |
|---|---|---|
| `system` | ✅ | `"item"` \| `"draft"` \| `"rune"` \| `"live"` \| `"macro"` — which engine produced this |
| `category` | ✅ | Domain-specific sub-classification (item's `core_build`/situational trigger name; draft's `pick`/`ban`; macro's pattern category) |
| `subject` | ✅ | The specific named thing this entry is about — item name, champion name, rune name, pattern name |
| `recommendation` | ⚠️ nullable | The actionable suggestion. **`null` is valid and expected** for a purely observational entry (see confidence/severity below) — never fabricate a recommendation to fill this field |
| `reason` | ✅ | Deterministic, templated string — never free-form generated text, same discipline `item_recommender.py`/`priorities.py` already enforce |
| `evidence` | ✅ (may be `[]`) | List of grounded facts, copied verbatim from source data |
| `confidence` | ✅ | `"high"` \| `"medium"` \| `"low"` \| `"unavailable"` — **one vocabulary, replacing the three incompatible ones `ARCHITECTURE_AUDIT.md` Finding C flagged**. Data-quality axis: *how sure are we this claim is true* |
| `confidence_score` | ⚠️ nullable | 0–100 for systems that can produce one deterministically (item, future rune/draft); `null` for qualitative-only checks (macro) — never backfilled with a guess |
| `severity` | ✅ | `"high"` \| `"medium"` \| `"low"` \| `"unavailable"` — a **second, distinct axis**: impact/urgency, *how much should the player care*, independent of confidence. (Today's codebase conflates these in places; keeping them separate is deliberate.) |
| `priority` | ✅ | Integer rank within the batch this entry came from (1 = most important) |
| `source` | ✅ | Provenance label — `"champion_knowledge"`, `"general_knowledge"`, `"recurring_pattern"`, `"this_game"`, etc. |
| `details` | ✅ (may be `{}`) | **The extension bucket.** Every domain-specific field that doesn't generalize (item's `cost`/`purchasable_now`/`builds_toward`/`recommendation_type`; a future draft entry's `champion_role`; anything else) lives here, never forced into the core shape. Same permissive-extension precedent `benchmark_schema.py` already established for benchmark entries' optional descriptor fields. |

**The "unavailable" rule, stated explicitly per your constraint:** when a system has nothing genuine to recommend for an expected slot, it emits an entry with `confidence`/`severity: "unavailable"` and `recommendation: null` — never omits the entry silently, never fabricates a plausible-looking one. This is the same discipline `comparison.py`'s missing-metric path and `item_recommender.py`'s component-fallback-to-`null` already follow, just written as an explicit schema rule now.

`src/recommendations/schema.py` gets one function, `validate_recommendation(entry) -> list[str]`, in the exact style of `benchmark_schema.py`'s `validate_benchmark_entry()` — returns error strings, doesn't raise, so a batch of entries can be validated all at once.

## 3. Migrating `item_recommender.py` Without Breaking Anything

**Two-stage migration, only the first stage happens soon:**

**Stage 1 (near-term, zero risk):** add a pure adapter function — `adapt_item_recommendation(entry: dict) -> dict` — that translates `recommend_items()`'s existing output into the shared shape (`item` → `subject`/`recommendation`, `confidence_tier` → `confidence`, `cost`/`purchasable_now`/`builds_toward`/`recommendation_type` → `details`). **`recommend_items()`'s actual return value does not change at all.** `coaching_report.py`'s `_item_review()`, every existing test, and the saved `{match_id}_item_recommendations.json` files keep working completely unmodified — the adapter is a new, additive, read-only function that something new (a future cross-system aggregator, or the eventual overlay) calls when it wants the unified view.

**Stage 2 (later, not scheduled now):** once `draft`/`rune` are built natively against the shared schema and it's been proven against two real new systems, *consider* refactoring `recommend_items()` to emit the shared shape as its primary output (moving today's rich fields into `details`), retiring the adapter. This is explicitly not decided now — the same "wait for a second real use case before generalizing" discipline already applied elsewhere in this project (e.g., `KNOWLEDGE_SYSTEM_PLAN.md`'s archetype-layer deferral).

The same adapter pattern applies to macro: `adapt_macro_lesson(lesson: dict) -> dict` converts a `priorities.py` lesson (already close to this shape) into the shared entry — again purely additive, `priorities.py`'s actual output and `coaching_session.json`'s `main_lessons` are untouched.

## 4. How Draft, Rune, and Live Would Consume This

Unlike item/macro, **these have no legacy shape to preserve** — they don't exist yet. They should be written to emit the shared schema *natively* from their first line of code, no adapter needed:

- **Draft** (`system: "draft"`): `category` ∈ `pick`/`ban`/`synergy_warning`; `subject` = champion name; `recommendation` = `"Pick"`/`"Ban"`/a swap suggestion.
- **Rune** (`system: "rune"`): `category` ∈ `keystone`/`secondary_tree`/`shard`; `subject` = rune name; `recommendation` = the rune itself.
- **Live** (`system: "live"`): `category` ∈ `recall_advisor`/`item_advisor`/`objective_timer`/`fight_evaluation` (per `LIVE_SYSTEM_DESIGN.md`'s existing feature breakdown); `subject`/`recommendation` vary by category (an item name, a countdown value, a coarse team-strength label).

Each is free to design its own trigger/rule logic (per `ROADMAP.md` §3's note on eventually sharing trigger-matching code between item and rune) — the shared schema constrains only the *output shape*, never the internal decision logic, which stays wherever `ROADMAP.md` already scoped it.

## 5. How the Future Overlay Would Read These

Directly extends `UI_DESIGN.md`'s existing rule — **the UI displays decisions, never creates them** — now generalized across all five systems instead of restated per-screen:

- The overlay reads a list of shared-schema entries, filtered by which `system`s are relevant to the current phase (draft+rune during champ select; live during the game; item+macro post-game) — that filter is just reading the `system` field, not a decision, so it doesn't violate "no recommendation logic in UI."
- Sorted by `priority`, rendered compactly (`subject`, `recommendation`, `severity`) by default.
- `reason`/`evidence`/`details` sit behind a "why" expansion — the exact two-tier disclosure `UI_DESIGN.md` already specified for the coaching screens, now free to be **one rendering component instead of five**, because every system emits the same shape.
- `confidence`/`severity: "unavailable"` renders visually distinct from a real value, per `UI_DESIGN.md`'s existing rule that unavailability must never look the same as a checked, real result.

This is the concrete payoff of unification: without it, the overlay would need five bespoke renderers; with it, one.

## 6. Tests to Write Before Implementation

Proposed `tests/test_recommendation_schema.py`, written before `schema.py` exists (same discipline as the benchmark-integration turn):

1. `validate_recommendation()` accepts a hand-built, well-formed entry for **each** of the five `system` values — proving the schema genuinely generalizes across all five, not just the one it was designed against first.
2. Each required field, individually removed, is flagged.
3. An invalid `system`/`confidence`/`severity` enum value is flagged.
4. `recommendation: null` combined with `confidence`/`severity: "unavailable"` is explicitly **valid** — a test proving this is an accepted state, not rejected as incomplete.
5. `details` may be `{}` or hold arbitrary domain-specific keys without validation failure — proving the extension bucket is genuinely open.
6. `adapt_item_recommendation()`: given a real fixture matching `recommend_items()`'s actual current output, produces a schema-valid entry, **and** the original input fixture dict is unmodified afterward (proves the adapter is a pure, non-mutating, purely additive function — the concrete test of requirement 3, "without breaking existing functionality").
7. `adapt_macro_lesson()`: same proof, using a `priorities.py`-shaped fixture.
8. **Cross-domain consistency test:** an adapted item entry and an adapted macro lesson both pass the *same* `validate_recommendation()` call — proving real unification, not two schemas that coincidentally share a file.

## Constraints Preserved (explicitly checked against this design)

- **Deterministic decisions:** the schema constrains output shape only; every field in it (`confidence`, `severity`, `priority`, `reason`) must still be computed by existing deterministic logic — the schema doesn't introduce a new decision-making step anywhere.
- **AI optional, explanation-only:** nothing here requires or assumes an AI call. A future AI explanation layer would consume `reason`/`evidence`/`details` as grounding input (the same `prompt_builder.py`/`validator.py` pattern already established), never write to `recommendation`/`confidence`/`severity` directly.
- **No recommendation logic in UI:** §5 above — the UI's only "decision" is which `system`s to display, driven by phase, not by judging the recommendations themselves.
- **No fabricated data:** `reason` stays templated from real fields; `details` only ever holds real domain data; adapters are pure translations, never inventions.
- **Missing information returns `"unavailable"`:** made an explicit, first-class schema rule (§2), not an implicit convention scattered across modules.

---

No code written. Waiting for approval before implementing.
