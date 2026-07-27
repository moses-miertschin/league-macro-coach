# LeagueMacroCoach — Test Coverage Audit

Every test file under `tests/` was read in full for this audit. No tests were changed. Special attention was given to `item_recommender.py`, `game_state.py`, `macro_analyzer.py`, and `timeline_analyzer.py` as requested — those four get the deepest treatment below. The cross-cutting finding at the end is the single most important one in this document.

## Current Coverage Summary

| Module | Test file | Lines (src/test) | What's covered |
|---|---|---|---|
| `riot/client.py` | `test_riot_client.py` | 55/35 | Region→continent mapping, participant lookup (pure logic, no network) |
| `analyzer.py` | `test_analyzer.py` | 98/102 | Extraction, `damage_share` team-scoping, missing-participant error |
| `timeline_analyzer.py` | `test_timeline_analyzer.py` | 138/106 | Death timing, objective correlation, fight clustering, empty timeline |
| `macro_analyzer.py` | `test_macro_analyzer.py` | 326/162 | Threshold flagging, knowledge de-prioritization, missing-champion fallback, timeline enrichment |
| `game_state.py` | `test_game_state.py` | 131/98 | Snapshot shape, `is_fed`, team_state diffs, one `game_state` branch |
| `item_recommender.py` | `test_item_recommender.py` | 313/185 | Trigger matching, scoring, ranking, gold-aware component/save_gold logic |
| `knowledge/loader.py` | `test_knowledge_loader.py` | 81/45 | Section parsing, case-insensitivity, missing file/role |
| `knowledge/item_loader.py` | `test_item_loader.py` | 104/77 | Core build, five-field record, avoid section, missing file |
| `riot/data_dragon.py` | `test_data_dragon.py` | 83/70 | Catalog shaping, cache-hit avoids re-fetch |
| `history/*`, `profile/*`, `insights/*` | (5 files) | — | Exhaustively covered per `CHECKPOINT.md`'s existing test table; not re-audited here since this pass's focus was the four modules above |
| `ai/*` | `test_ai_report_generator.py` | — | Grounding filter, insufficient-data short-circuit, prompt content |

## Deep Review: The Four Requested Modules

### `macro_analyzer.py`

**Well covered:** the full weak/strong game contrast, both directions of knowledge de-prioritization (Syndra+vision, Pyke+CS), a missing-champion-knowledge fallback, and the exact split between timeline-fillable and permanently-unavailable patterns.

**Missing:**
- **No test with role knowledge missing.** `test_missing_champion_knowledge_does_not_crash` only unsets the champion; role stays `"MIDDLE"` (a mapped role) throughout every test. `role_context_loaded == False` is never exercised, and neither is the equivalent all-champion-and-role-missing combination.
- **Correction after re-checking the source directly (an earlier draft of this section overstated this as a crash risk):** `macro_analyze()` already guards both lookups — `load_role(analysis["role"]) if analysis.get("role") else None` — so a missing or `None` role degrades safely to `role_context_loaded: False` rather than crashing in `load_role`'s `.lower()` call. There is no live bug here. The real gap is narrower than first thought: this graceful path is simply **untested**, not broken — worth a regression test precisely so it stays that way as this function evolves, not because it's currently wrong.
- **No boundary-value tests.** `HIGH_DEATH_COUNT` (8), `DEATHS_BEFORE_OBJECTIVES_CONCERN` (2), and every `BENCHMARKS` low/good pair are exercised well inside their bands, never exactly at the boundary. `_tier()`'s `< low` / `>= good` semantics are implicit and unverified at the edges.
- **No regression test for the fixed `PATTERN_KEYWORDS` collision bug.** `CHECKPOINT.md` documents a real historical bug (`"farm"` in a vision bullet suppressing CS/min). Nothing locks that fix in place — a future edit to `PATTERN_KEYWORDS` could reintroduce a similar collision with no test to catch it.

### `game_state.py`

**Well covered:** snapshot shape, `is_fed` flagging for one fed enemy, team_state arithmetic, and the "behind" branch of `game_state`.

**Missing — this is the biggest gap of the four modules:**
- **`"ahead"` and `"even"` are never tested.** Only "behind" has a fixture. `_game_state()`'s other two branches have zero coverage, despite `game_state_ahead` directly driving an `item_recommender.py` trigger — an untested branch here is a silent path to wrong item advice.
- **No boundary tests** for `AHEAD_GOLD_DIFF_THRESHOLD`/`AHEAD_KILL_DIFF_THRESHOLD` or `FED_GOLD_PER_MINUTE_THRESHOLD`/`FED_KILL_DEATH_DIFF_THRESHOLD`.
- **No zero/malformed-data test.** `enemy_levels`/`player_levels` are divided by their own length with no guard; a match with an incomplete enemy roster (fewer than 5 entries — plausible for a corrupted file, and *very* plausible once live/partial data exists) would raise `ZeroDivisionError` if the list were ever empty. Not exercised.
- **Multiple simultaneously-fed enemies** never tested (only one at a time).
- **`role` fallback to `individualPosition`** never tested (`teamPosition` is always populated in fixtures).

### `timeline_analyzer.py`

**Well covered:** death-to-objective correlation, per-objective-type participation counts, recall's permanent unavailability, fight clustering (including the "isolated kill isn't a fight" case), and full graceful handling of an empty timeline.

**Missing:**
- **No boundary test at exactly `OBJECTIVE_WINDOW_MS` (60,000ms).** The correlation condition is `death_ts < obj_ts <= death_ts + OBJECTIVE_WINDOW_MS` — inclusive at the upper edge. Untested exactly at that edge, so an off-by-one regression there wouldn't be caught.
- **No boundary test at exactly `FIGHT_WINDOW_MS` (30,000ms)** between two kills.
- **No test for one objective satisfying multiple deaths' windows** (current logic would count it once per qualifying death — plausibly intended, but silently unverified).
- **No test for a `CHAMPION_KILL`/`ELITE_MONSTER_KILL` event missing `assistingParticipantIds` entirely** (the code defends with `.get(..., [])`, but real Riot payloads are always well-formed in the fixtures used here).

### `item_recommender.py`

**Well covered (from this session's own work, reviewed critically here):** trigger matching against knowledge text, stacked-trigger score boosting, the self-conflict penalty (and it fired on real match data too, per the last implementation pass), owned-item exclusion, core-build baseline scoring, avoid-list exclusion, unrecognized-item flagging, ranking + `recommendation_type` assignment, gold-aware component substitution, and the save-gold fallback.

**Missing — several of these matter more than the others:**
- **The `general.md` fallback path has zero real coverage.** Every test fixture passes an *empty* `GENERAL_KNOWLEDGE`. The merge logic that lets `general.md` supply items a champion file doesn't have — the entire reason `general.md` exists — is untested. **This is the most important gap in the module**, because it's exactly the path that fires for every champion outside the current four-champion pool, which is most champions.
- **No end-to-end test for a champion with *no* knowledge file at all** (empty `champion_knowledge`, populated `general_knowledge`). This is the realistic "unrecognized/uncovered champion" scenario and it's currently unverified that the engine still produces sensible output rather than an empty or degenerate one.
- **No test for an avoid entry defined only in `general.md`.**
- **No confidence-score boundary tests** (69/70, 39/40) — the tier cutoffs are inlined in `_build_candidate`/`_build_core_build_candidate` rather than centralized, so there's more surface for an off-by-one than in `macro_analyzer.py`'s single `_tier()` helper.
- **No test where the raw score sum goes negative before clamping** — the `max(0, ...)` clamp exists but has never actually been exercised below zero.
- **No test for a partial/small enemy roster.** `AP_HEAVY_THRESHOLD`/`AD_HEAVY_THRESHOLD` are absolute counts (`>= 2`), not proportions of team size. A 2-enemy snapshot (plausible for early-draft live data in Phase 3) would trigger `enemy_ap_heavy` identically to a full 5-enemy comp where 2/5 are magic. Not a bug against today's post-game-only usage, but a real correctness risk to close **before** wiring this into live data.
- **No test for a malformed `from` (build-path) entry** pointing at an item ID absent from the catalog (Data Dragon does occasionally have stale/inconsistent cross-references).
- **No genuine tie-break test** for two items landing on the exact same `confidence_score`.

### `riot/data_dragon.py`

- No test for an HTTP error response (`raise_for_status()` firing) — confirm the caller fails loudly rather than silently producing an empty catalog.
- No test for a version bump between two `load_item_catalog()` calls (does the newer version's cache get created rather than reusing the stale one?).
- No test for a raw item entry missing `gold`/`tags`/`from` (Data Dragon has some non-purchasable items shaped this way).

### `knowledge/item_loader.py`

- No test for a field bullet whose recognized key doesn't match any entry in `FIELD_KEYS` (a typo like "Value when:" instead of "Valuable when:") — currently **silently dropped**, with no warning surfaced anywhere. Worth a test that documents this behavior explicitly, since a knowledge-file typo today fails silently rather than loudly.
- No test for a duplicate `## Item Name` heading within one file (last-one-wins via dict assignment, unverified/undocumented).

## Cross-Cutting Finding (the most important one in this document)

**No test anywhere feeds malformed or partial input through the "public" entrypoints** (`macro_analyze()`, `build_snapshot_from_match()`, `recommend_items()`) to confirm graceful degradation. Every existing test uses a hand-crafted, fully well-formed fixture.

For a normal application, "does it crash on bad input" would be the main concern. For a coaching tool built on the explicit philosophy **"never fabricate missing information, prefer evidence-backed decisions,"** the more dangerous failure mode isn't a crash (loud, safe, visible) — it's **silently producing a plausible-looking recommendation from incomplete or malformed data.** A crash tells the user something's wrong; a fabricated-looking recommendation doesn't.

Recommended future test category, applied across all four modules above: for each function, construct an input missing one required field / holding an unexpected type / representing a partial (not just empty) roster, and assert one of two acceptable outcomes — a clear, typed exception, or an explicit `"unavailable"`/`"unknown"` marker in the output. Never a numeric value or a ranked recommendation computed from data that wasn't really there.

## Recommended Priority Order for Future Test Work

1. `game_state.py`'s untested `"ahead"`/`"even"` branches — directly feeds `item_recommender.py`, currently the least-verified link in the item-recommendation chain.
2. `item_recommender.py`'s `general.md` fallback path — the most-used path once the champion pool grows, currently the least-tested.
3. `macro_analyzer.py`'s missing/`None`-role path — already safely guarded, just needs a regression test locking that in.
4. Boundary-value tests across all four modules' threshold constants.
5. The malformed/partial-input robustness category described above, prioritized for `game_state.py` first (most likely to receive genuinely partial data once Phase 3 live snapshots exist).
