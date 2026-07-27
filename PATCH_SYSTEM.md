# LeagueMacroCoach — Patch and Data Strategy

Design only. League changes every patch; this defines how each data source in the current architecture should handle that, and what genuinely requires a human versus what can stay automatic.

## What Already Handles Patches Automatically (a real existing strength)

`src/riot/data_dragon.py`'s `load_item_catalog()` calls `fetch_latest_version()` on **every** invocation — it always checks Data Dragon for the current patch's version string, and only skips re-fetching `item.json` if a cache file for *that specific version* already exists locally. This means item cost, tags, and build-path data **self-update every patch with no manual step**, and this was true before this audit — it's a design decision from the original implementation plan (`load_item_catalog` checking latest version was explicit, not accidental), worth recognizing as already correct.

`item_recommender.py`'s cross-check against the catalog (`unrecognized_items_flagged`) means that if an item is **removed or renamed** in a patch, any knowledge-file reference to its old name is caught automatically — flagged, excluded from output, never silently recommended. This is real, working protection against one entire category of staleness, already built.

## What Does NOT Update Automatically

| Data | Why it goes stale | Automatic protection today |
|---|---|---|
| `knowledge/champions/*.md` | A champion rework can change what "Common Mistakes to Detect" or "Important Metrics" even mean for that champion | **None** — no cross-check exists |
| `knowledge/roles/*.md` | Meta shifts (e.g., objective/bounty system reworks) can change what matters for a role | **None**, but changes far less often |
| `knowledge/items/*.md` | An item can be reworked (build path, stats, identity) while keeping its name — the Data Dragon cross-check only verifies the *name* still resolves, not that the qualitative judgment is still true | **Partial** — name-resolution only |
| `data/static/champion_damage_types.json` | A rework can shift a champion's damage profile | **None** |
| Live-system game-rule constants (`LIVE_SYSTEM_DESIGN.md`'s objective respawn timers) | Riot periodically changes fixed timers (dragon/baron spawn schedules) directly in balance patches | **None** — these would be hardcoded constants |

**The item-rework gap is the most important one to name precisely:** an item keeping its name while being fundamentally reworked (a mythic-to-legendary conversion, a stat rebalance, a passive rewrite) passes the existing name-resolution check with no warning, even though the knowledge file's "Valuable when"/"Priority" reasoning about it may no longer be true. This is not solvable by checking Data Dragon data alone — it requires a human to notice the item changed and re-read the relevant knowledge bullets.

## Why This Can't (and Shouldn't) Be Fully Automated

Detecting *that a change matters* — not just that a number changed, but that a champion's identity or an item's role shifted — requires understanding patch notes, not just diffing JSON fields. The tempting shortcut is to have an LLM read patch notes and flag affected knowledge files. This is deliberately **not** recommended: an LLM summarizing patch notes could misjudge or hallucinate the significance of a change, and acting on that misjudgment is exactly the failure mode the project's "never fabricate, prefer evidence-backed decisions" philosophy exists to prevent. Patch-impact judgment stays a human review task — the goal of this document is to make that review **cheap and well-targeted**, not to eliminate it.

## Recommended System: Staleness Surfacing, Not Staleness Fixing

A small, fully deterministic addition (not built in this pass) that never guesses *what* changed, only *how long it's been* since a file was checked:

1. Add one front-matter line to each knowledge file: `<!-- last_reviewed_patch: 14.10 -->` (champion, role, and item files alike).
2. A small script compares each file's recorded patch against the current Data Dragon version (already fetched by `data_dragon.py` for the item catalog — the version string is right there, no new network call needed).
3. Report, plainly: *"knowledge/champions/akali.md last reviewed at patch 14.10; current patch is 14.16 — 3 patches behind, worth a check."*

This surfaces staleness honestly without ever claiming to know whether anything actually changed — the human decides whether a 3-patch gap matters for a given champion, the same way the human already writes every qualitative bullet in these files. It's the same "mark it, never fabricate it" discipline the rest of the system already follows, applied to *time* instead of to missing data.

## Recommended Review Cadence (human task, not automatable)

- **Item knowledge:** check against patch notes whenever an item present in `knowledge/items/*.md` appears in that patch's balance-change list — the staleness report above tells you *when* to look, patch notes tell you *what* to check.
- **Champion knowledge:** check whenever a champion in the current pool (or any champion with a knowledge file) receives a rework or a significant ability change — reworks are announced well in advance and are infrequent enough that this is a small, occasional task, not a per-patch one.
- **Live-system game-rule constants** (once Phase 4 is built): these are the highest-consequence staleness risk of everything in this document, because they're silent numeric constants with no name-resolution safety net at all — a stale objective timer doesn't fail loudly, it just quietly tells the player the wrong number. These deserve an explicit version comment at the point of definition (e.g., "`DRAGON_RESPAWN_SECONDS = 300  # per patch 14.x rules — reverify if objective timers are mentioned in patch notes`") so a future reader knows exactly what to double-check and when, mirroring the existing `ponytail:` comment convention already used throughout this codebase for exactly this kind of "this is a guess, here's the caveat" flag.

## Summary

- **Data Dragon (items):** already self-updating per patch — no action needed.
- **Item name validity:** already automatically checked — no action needed.
- **Item *judgment* validity, champion knowledge, role knowledge, damage-type classification, and future live-system constants:** all require human review, by design — the system's job is to make that review cheap (the staleness-surfacing tool above) and clearly scoped (this document's per-category cadence), never to attempt it automatically.
