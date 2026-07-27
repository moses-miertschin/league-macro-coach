# LeagueMacroCoach — Knowledge System Plan

Audits `knowledge/champions/`, `knowledge/roles/`, and `knowledge/items/` for scalability and designs how the system should grow. **This is a design document — no champion/item/matchup files are authored here**, per instruction.

## 1. Is the current knowledge format scalable?

**Structurally: yes. In authoring effort: no — and that's expected, not a flaw.**

Both `src/knowledge/loader.py` (champion/role) and `src/knowledge/item_loader.py` (items) already have the properties that make a knowledge format scale well:

- **Fixed, predictable section/field templates** — a new file is a copy-paste-and-fill exercise, not a design decision.
- **Graceful absence, everywhere.** `load_champion()`/`load_role()` return `None` for a missing file; `item_recommender.py` falls back to `general.md`; `macro_analyzer.py` sets `champion_context_loaded: False` and keeps working. **The system was already built to tolerate partial coverage from day one** — nothing crashes or fabricates when a champion isn't covered yet. This is the load-bearing property that makes the rest of this plan possible: coverage can grow incrementally, in any order, without a "complete the set or it breaks" requirement.

What doesn't scale is the same thing that doesn't scale for any hand-curated coaching content: **someone has to actually write it.** With ~170 champions, exhaustively authoring `knowledge/champions/*.md` and `knowledge/items/*.md` up front is not a good use of time. The rest of this document is about *not* doing that — growing coverage in the order it's actually needed.

## 2. Can we support all champions eventually?

Yes, but not by writing 170 files. Recommended tiered coverage strategy, in priority order:

1. **The player's own champion pool** (already done: Yone, Akali, Fizz, Syndra; Pyke exists for the support game). This tier is basically complete.
2. **Champions actually faced as opponents**, derived empirically from `data/database/game_history.json` — every game already records the enemy roster (via `game_state.py`'s `enemy_team`, once that's wired into the batch pipeline — see `ARCHITECTURE_AUDIT.md` §5). A champion that has appeared in 2+ real games as an opponent is a better authoring candidate than a champion picked at random, for the same "≥2 occurrences" evidentiary bar `history/aggregate.py` already uses for weaknesses/strengths. This turns "which champion do I write next" into a data-driven question instead of a guess.
3. **Champions common in the player's role** (mid, and support for the Pyke pool) not yet covered by tier 2.
4. **Everything else** — deferred indefinitely; the graceful-fallback behavior in §1 means this is fine.

**Reducing authoring effort without fabricating content:** a small local scaffolding script (no AI, no API) could generate a *skeleton* file for a new champion — role default position, ability names, and the fixed section headings, pulled from Data Dragon's `champion.json` (static data, same free source `data_dragon.py` already uses for items) — leaving every actual judgment (`Common Mistakes to Detect`, `Important Metrics`) as an empty section for a human to fill in. This reduces typing, not thinking — the qualitative content itself must stay human-authored, per the project's core philosophy. Not built now; noted as a low-cost future convenience.

**A further scaling idea worth naming, not building:** a middle tier between "generic role" and "full champion file" — an **archetype layer** (e.g., "burst mage," "duelist bruiser," "hypercarry marksman") that several champions could share for `Important Metrics`/`Metrics That Matter Less`, with only `Common Mistakes to Detect` needing to stay fully champion-specific (mistakes are rarely shareable across champions even within the same archetype). This would reduce the marginal cost of each new champion but adds a third lookup layer to `loader.py` — a real architecture change, not something to do speculatively. Revisit only once tier 2 above produces enough champions that duplicated archetype content becomes visibly repetitive across files, not before.

## 3. How should matchup knowledge work?

`knowledge/matchups/` is currently empty (`.gitkeep` only) — nothing consumes it yet either. Design for when it's built:

**Why this is a different scaling problem than champion knowledge.** Champion knowledge is one file per champion (~170 files, worst case). Matchup knowledge is inherently *pairwise* — up to N² combinations. Full coverage is never realistic, and shouldn't be the goal.

**Proposed format:** one file per matchup, from the player's champion's perspective (directional — "Yone into Zed" is a different coaching angle than "Zed into Yone" would be):

```
knowledge/matchups/{your_champion}_vs_{enemy_champion}.md
```

Fixed section template, mirroring the existing champion-knowledge style (qualitative prose, not numeric):

```
## Lane Priority          -- who's ahead pre-6 / post-6, and why
## Danger Windows         -- specific levels/timings where the enemy has kill pressure
## Trading Pattern        -- how to trade favorably in this specific pairing
## Common Mistakes in This Matchup
```

**Scope control, same principle as §2:** only author a matchup file for a pairing that's actually occurred in real games (again derivable from history — "which enemy champion was in my role"), never speculatively for a hypothetical pairing. This keeps matchup authoring bounded by what's actually happened instead of combinatorial.

**Consumption — an open design question worth flagging now.** Neither `macro_analyzer.py` nor `analyzer.py` currently know *who the enemy laner was* — that fact doesn't exist anywhere in the original macro pipeline's structured output. `game_state.py`'s `enemy_team` (built for the item recommender) already carries per-enemy `role`, so the data needed to identify "the same-role opponent" already exists in that newer pipeline. Two ways to wire matchup knowledge in, when it's built:

- **Extend `analyzer.py` additively** with an `enemy_laner_champion` field (a small, non-breaking addition — doesn't touch existing fields or callers) so `macro_analyzer.py` can load matchup knowledge the same way it loads champion/role knowledge today.
- **Or treat matchup awareness as an `item_recommender.py`-side concern only**, since `game_state.py` already has everything needed and matchup-flavored item advice ("into Zed, prioritize X") is arguably a more natural fit there than in the macro-mistake pipeline.

Not deciding this now — flagging it so it isn't accidentally solved twice, differently, in each pipeline later.

## 4. How should item knowledge expand?

Two independent axes, expanding at different rates and by different mechanisms — see `ARCHITECTURE_AUDIT.md` Finding E for the full reasoning:

- **Champion coverage** (which champion files exist): scales exactly like §2 above — pool first, faced-often opponents next, `general.md` covers the gap in between. No code changes needed, ever, for this axis.
- **Trigger vocabulary** (`enemy_ap_heavy`, `enemy_has_fed_carry`, etc. in `item_recommender.py`): this is the one axis that *does* require code, not just markdown, because each trigger is a named Python function plus a `TRIGGER_KEYWORDS` entry. This was a deliberate choice (a bracket-syntax condition DSL inside markdown was considered and rejected as overkill — see the implementation-planning history for this module) and it's the right call for a single-user tool, but it means "add a new situational axis" is a small code change, not a content edit.

**Recommended process for adding a new trigger**, to keep this disciplined rather than speculative: add a trigger only once a genuinely new situational pattern has shown up in **2 or more real games** — the same evidentiary bar `history/aggregate.py` already applies to weaknesses and strengths. This keeps the trigger vocabulary demand-driven (grown from what actually happened) rather than a guess at what *might* matter.

**Item data itself doesn't need manual scaling at all** — `data_dragon.py` already covers every item in the game automatically via the live catalog, and the cross-check against it (`unrecognized_items_flagged`) means a knowledge-file item that gets removed or renamed in a patch is caught automatically rather than silently recommended. Only the *judgment* about items (`Valuable when`/`Bad when`/`Priority`) needs a human, same as champion knowledge.

**Champion damage-type classification (`data/static/champion_damage_types.json`)** scales the same way as matchup/champion knowledge — grow it for champions actually faced, leave everyone else `"unknown"` (never guessed, per Finding E in the architecture audit and the module's own design). This file will need entries added at roughly the same pace as `knowledge/champions/*.md` grows.

## 5. How should patch changes be handled?

Covered in full in `PATCH_SYSTEM.md`. Summary of the knowledge-specific piece: item knowledge is already patch-resilient by construction (the Data Dragon cross-check catches stale item names automatically). Champion knowledge has no equivalent automatic staleness check today — a champion rework changing an ability's function could silently leave a `Common Mistakes to Detect` bullet describing a mechanic that no longer exists, with nothing in the system flagging it. This is a real gap, but champion reworks are far less frequent than item balance patches, so it's lower urgency — see `PATCH_SYSTEM.md` for the full handling plan.
