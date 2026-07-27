# LeagueMacroCoach — Future Live Game Architecture

Design only, per instruction — no code. This designs the eventual live coaching system described in `ROADMAP.md` Phase 3, using what's actually exposed by Riot's official local API, not what would be convenient.

## Data Source: the Live Client Data API

League's client exposes a local, unauthenticated HTTPS endpoint at `https://127.0.0.1:2999/liveclientdata/...` **only while a match is in progress on that machine** — a fundamentally different integration than the cloud match-v5 REST API `src/riot/client.py` already wraps (see `ROADMAP.md` §5, `src/live/` reserved for exactly this reason). Key facts that shape everything below:

- It's local-only — this tool can only coach the game running on the same machine it's installed on. Fine for a personal tool; rules out ever coaching someone else's game.
- It requires disabling TLS certificate verification (self-signed cert) — a small, known implementation detail, not a blocker.
- The most useful endpoint is `allgamedata`, which bundles `activePlayer`, `allPlayers`, `events`, and `gameData` in one call.

## What Data Is Actually Available (and to Whom)

This is the most important table in this document — several assumptions that seem natural turn out to be wrong.

| Data | Available for you (`activePlayer`) | Available for teammates/enemies (`allPlayers`) |
|---|---|---|
| Current gold | ✅ | ❌ **not exposed for anyone but yourself** |
| Current items | ✅ (full detail) | ⚠️ fog-of-war limited — only what you've actually seen; stale once vision is lost |
| Level | ✅ | ✅ (visible on the scoreboard for everyone) |
| Kills / deaths / assists / creep score / ward score | ✅ | ✅ (public scoreboard stats, not fog-of-war restricted) |
| Champion, role assignment | ✅ | ✅ |
| Map position (coordinates) | ❌ | ❌ — **not exposed for anyone, including yourself**, beyond what's already on your own screen |
| Ability ranks / current stats (AD, AP, resistances) | ✅ | ❌ |
| Game time, game events (kills, objective takedowns, building destruction) with timestamps | ✅ | ✅ (event feed is global) |
| "Is recalling right now" | ❌ — **no such event exists**, live or post-game (same gap `timeline_analyzer.py` already documents for match history) | ❌ |

**The single biggest consequence:** any "ahead/behind" or "is this enemy fed" logic that reused `game_state.py`'s post-game approach verbatim (which leans on `gold_earned_total`) **cannot be reused as-is live**, because current gold for anyone but yourself simply isn't in the API. A live-specific version of that logic has to substitute kills/deaths/level/creep-score differentials for the gold comparison it can't make. This doesn't change `GameSnapshot`'s *shape* — `team_state.gold_diff` can still exist as a field — but it does mean the live-side builder has to either omit it, mark it `null`/`"unavailable"`, or approximate it from creep score (see below). This is exactly the kind of seam `game_state.py` was designed to isolate: `item_recommender.py` and everything downstream stays untouched; only the live builder's internals differ from the post-game builder's.

**The second-biggest consequence:** there is no positional data at all. Any feature that would need "are you near the objective," "is your team grouped," or "is the enemy jungler visible on your side of the map" cannot be built from this API. That rules out true tactical fight-calling and wave-state awareness, addressed feature-by-feature below.

## Feature-by-Feature Design

### 1. Recall Advisor — *"You have 1100 gold. Buy components for Kraken."*

**Feasibility: high — this is mostly already built.** `activePlayer.currentGold` gives real current gold (unlike the post-game snapshot, where it's always `null`), and `item_recommender.py`'s existing component-fallback logic (from this session's implementation) already does exactly this computation — "can't afford the full item, here's the best affordable component" — it was built and tested against a `current_gold` value for precisely this reason.

**Important framing correction:** there is no "recall" event to detect, live or post-game. So this can't be "notice the player is recalling, then advise" — it has to be "whenever polled (or on-demand), state what to buy with current gold right now." That's a fine, honest framing — arguably more useful, since it works whether the player is about to recall or just checking — but it's a different feature than the name implies, and should be described that way to the user rather than implying detection that doesn't exist.

**What requires rules:** all of it. No prediction needed — this is the existing deterministic component/cost logic, fed a live gold number instead of `null`.

### 2. Item Advisor — *"Enemy Syndra is fed. Consider MR."*

**Feasibility: high — the rule logic is already built and tested.** `is_fed` and `enemy_ap_heavy` (`game_state.py`/`item_recommender.py`) already exist. The only new work for this feature is a live snapshot builder — not new rule logic.

**What's different from the post-game version:** the post-game `_is_fed()` uses `gold_earned_total`, which isn't available live for any player but the active one. A live-side fed-check has to substitute something computable from public scoreboard stats — e.g., kills/deaths differential plus a **rule-based gold estimate from creep score** (a fixed, documented gold-per-CS constant multiplied by visible creep score, plus known kill/assist gold bounties from visible kill events). This is still fully deterministic and rule-based — it is an *estimate*, not a guess, and it should be labeled as an estimate in the output (a `confidence: "estimated"` marker, consistent with the project's existing confidence vocabulary) rather than presented with the same certainty as the post-game version's ground-truth number.

**What's unavailable:** an enemy's actual current gold and exact item inventory beyond what you've warded/seen. The item-suggestion side of this feature (which item to build) is unaffected — that logic only needs *your own* gold and items, both fully available.

### 3. Objective Timer Coach

**Feasibility: high — fully rule-based, no prediction needed.** The event feed gives exact timestamps for every dragon/baron takedown. Respawn timers are fixed, publicly known game rules (e.g., dragons respawn a fixed interval after the last one falls; baron has a fixed first-spawn time and fixed respawn interval) — not something the API hands you directly as a countdown, but fully derivable by adding a known constant to the last event's timestamp.

**Important caveat, and a direct link to `PATCH_SYSTEM.md`:** these respawn-interval constants are exactly the kind of thing Riot changes between seasons/patches. This feature's correctness depends entirely on those constants staying in sync with the current patch — it needs the same "is this still true this patch" discipline `PATCH_SYSTEM.md` designs for game-rule constants generally, not just item/champion data.

**What's unavailable:** whether your team actually has priority to contest the objective (needs position, jungle-tracking, vision state — none of which this API exposes). The honest version of this feature is a countdown reminder ("dragon in 2:15"), not a contest-recommendation ("you should go now") — the latter needs data this API doesn't have.

### 4. Wave Management Coach

**Feasibility: low — not achievable with this API as currently understood.** There is no minion-count, minion-health, or lane-state field exposed anywhere in the Live Client Data API. Building this would require either:
- Reading the game screen directly (OCR/computer vision) — a fundamentally different technical approach, with real reliability and terms-of-service risk, and explicitly out of scope for this project's boundaries.
- A rough, unreliable inference from CS-timing patterns alone — likely to produce confidently-wrong advice, which directly conflicts with "never fabricate, prefer evidence-backed decisions."

**Recommendation: do not build this feature** until/unless Riot exposes lane-state data through an official API. This is the one feature from the requested list that should be marked infeasible rather than "future work," and said so plainly rather than quietly deferred.

### 5. Fight Evaluation

**Feasibility: partial — a coarse "team strength" indicator is achievable; a true tactical "should you engage" call is not.**

Achievable, rule-based: a live analog of `team_state` built from what *is* available for every player — level differential, kill/death differential, visible-item count, and the creep-score-based gold estimate from feature 2. This can produce an honest, coarse "your team appears stronger/weaker right now" signal, clearly labeled as an estimate.

Not achievable: whether this specific skirmish, right now, at these positions, is winnable — that needs map position and vision state for both teams, neither of which this API exposes. A tool that tried to answer "fight or don't fight" moment-to-moment without position data would necessarily be guessing dressed up as a rule, which is exactly what this project's philosophy exists to avoid.

## Summary Table: What Requires What

| Feature | Data available | Data unavailable | Requires estimation (rule-based, not ML) | Requires rules only |
|---|---|---|---|---|
| Recall advisor | Own gold, own items | Recall-action detection (doesn't exist) | — | ✅ (already built) |
| Item advisor | Own gold/items, all kills/deaths/creep score, fog-limited enemy items | Enemy/ally current gold, unwarded enemy items | Enemy gold (from creep score + kill bounties) | ✅ for the item-suggestion half |
| Objective timer | Event timestamps | Objective contest/priority | — | ✅ (constants patch-dependent) |
| Wave management | Nothing usable | Minion count/state, entirely | — | ❌ not currently feasible |
| Fight evaluation | Level, kills/deaths, visible items | Map position, vision state, ally/enemy gold | Team-strength estimate | ⚠️ coarse only, not tactical |

**No feature on this list requires machine learning.** Every achievable feature is either already-built rule logic (recall/item advisor) fed a new live data source, or a new deterministic estimate built the same way `game_state.py`'s existing `is_fed`/`game_state` derivations were — a named formula over visible facts, always labeled honestly when it's an estimate rather than ground truth. Wave management is the one feature this document recommends *not* pursuing, because no available data source supports it honestly.

## Runtime Model (the real new work)

Every module in this codebase today is a one-shot script — load input, compute, write output, exit (`ARCHITECTURE_AUDIT.md` Finding F). A live system needs, for the first time:

- A polling loop against `allgamedata` — a low frequency is fine (every few seconds; this is a coaching cadence, not a reaction-time system, and it's a local call with no rate-limit concern).
- Handling "no game in progress" gracefully (the endpoint simply isn't reachable outside a live match) rather than treating it as an error.
- Incremental/changed-state awareness, so the coach doesn't repeat the same advice every poll cycle — likely a simple "don't re-emit an identical recommendation within N seconds" guard, not a complex state machine.

This is genuinely new architecture, not an extension of an existing pattern, and should be scoped as its own implementation phase rather than squeezed into the existing `analysis/` module style.
