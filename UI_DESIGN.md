# LeagueMacroCoach — UI / Application Design

Design only, per instruction — no code, no framework commitment. The governing rule for every screen below: **the UI displays decisions the backend already made; it never makes or recomputes one.** If a screen needs a threshold, a color cutoff, or a "is this a concern" judgment, that value must already exist as a field in the JSON it's reading — never re-derived in the UI layer.

## Application Shape

A local desktop application with two very different surfaces, because they have opposite constraints:

- **Overlay** (live, in-game): must be glanceable in under a second, non-obstructive, and low-frequency in what it shows. Real-time gameplay leaves no time to read a paragraph.
- **Dashboard** (out-of-game, post-game review, history): can be as detailed and explorable as it needs to be, since the player has time to read.

Reasonable implementation candidates for later (not decided now): a transparent always-on-top window (`pywebview`, or a minimal native overlay) for the live surface, and any standard local web/desktop shell for the dashboard — both already floated as options in `ROADMAP.md` §6, not re-litigated here.

**Compliance note, worth flagging before this is ever built, not analyzed here:** a real-time gameplay-advice overlay sits closer to the category of third-party tools Riot scrutinizes than a passive stat tracker does. Worth explicitly verifying against Riot's third-party application policy before shipping the live-overlay surface specifically — the post-game dashboard surfaces (history, review, tracking) are unambiguously fine, being no different from any stats site.

## Screens

### 1. Live Assistant (overlay)

**Shown:** at most a handful of short lines at once — current gold + next purchase target (from the recall advisor), one active item-advisor line if a trigger is currently active ("Enemy Syndra is fed — consider MR"), and an objective countdown when one is within a couple of minutes.

**Source:** the live engine's output JSON (`LIVE_SYSTEM_DESIGN.md`), polled on the same cadence the engine writes it.

**Must NOT show:** the full `confidence_breakdown`, `evidence` list, or `reason` string in the overlay itself — those are exactly the fields that make the post-game review trustworthy, but reading them mid-fight is not the intended use, and cramming them in only produces clutter competing with the actual game. Show the *decision* (the item, the number, the one-line reason at most); the *justification* belongs one click away, not in the overlay. Also must not show anything with `confidence: "estimated"` at the same visual weight as a ground-truth number (see `LIVE_SYSTEM_DESIGN.md` — live enemy-gold figures are estimates, not measurements, and the UI needs a visual distinction, e.g. a subtle marker, not a disclaimer paragraph).

### 2. Match History

**Shown:** a sortable/filterable list of games — champion, result, KDA, CS/min, vision score, duration, date.

**Source:** `data/database/game_history.json` directly, via `src/history/store.py`'s existing `load_history()` — no new computation, this screen is a pure read.

**Must NOT show:** any invented trend projection (a "predicted next-game performance" or similar) that doesn't correspond to an actual field `history/aggregate.py` computes. If a chart implies a trend, it must be backed by `recent_trends`' real before/after comparison, not a fitted curve invented at render time.

### 3. Game Review (post-game, per match)

**Shown:** the full explainability the backend already computed and has nowhere else to go — every `detected_patterns` entry from `macro_analyzer.py` with its `tier`/`confidence`/`detail`, and every item recommendation with its full `reason`, `evidence`, and `confidence_breakdown` (this is the natural home for the detail the live overlay deliberately omits). A concern-flagged pattern and an `"unavailable"` one should look *visibly different*, not just differently labeled — `"unavailable"` must never be styled the same as "checked and fine."

**Source:** the per-match `{match_id}_analysis.json`, `{match_id}_macro_patterns.json`, and (once wired into the batch pipeline — see `ARCHITECTURE_AUDIT.md` §5) `{match_id}_item_recommendations.json`.

**Must NOT show:** a synthesized "grade" or single combined score for the game unless the backend actually computes one (it currently doesn't, deliberately — `macro_analyzer.py` reports a pattern list, not a letter grade). Inventing one at render time would be exactly the kind of fabrication the project's philosophy exists to prevent.

### 4. Item Recommendations (cross-game view)

**Shown:** recurring item recommendations across recent games — e.g., "Zhonya's Hourglass recommended in 6 of your last 10 games, most often because you were behind." A trend view, not a per-game one (that's screen 3).

**Source requirement this screen surfaces that doesn't exist yet:** item recommendations are currently written as standalone per-match files, not folded into `game_history.json` the way macro patterns are. This screen needs that persisted the same way — a natural, small extension of `store.py`'s existing upsert-by-match-id record, not a new storage system. Noted here as a data-layer prerequisite for this screen, not built in this pass.

**Must NOT show:** an aggregate "you should always buy X" without the same evidence discipline as the per-game view — a cross-game rollup is still built from real recorded recommendations and their real trigger reasons, never re-summarized through free text.

### 5. Improvement Tracking

**Shown:** whether flagged weaknesses (`player_insights.json`'s `weaknesses`/`priority_improvements`) are trending better or worse over time, using `profile_summary.json`'s existing early-half-vs-late-half `recent_trends` comparison.

**Source:** `player_insights.json` + `profile_summary.json`, both already computed, nothing new.

**Must NOT show:** a gamified "skill rating" or point system invented for the UI. The honest version of this screen is closer to "here's the same repeated-pattern count as before, now split by time window" — resist the temptation to turn evidence-backed counts into a synthetic score that reads as more precise than the underlying data supports.

## Cross-Cutting Rules

- **Every "why" is one interaction away, never zero and never forced.** Default view shows the decision (item, pattern, priority); an expand/"why" affordance reveals `evidence`/`confidence_breakdown`/`reason`. Never bury the justification entirely, and never force it into the primary view where it competes with the decision itself.
- **Confidence and unavailability markers are load-bearing, not decorative.** If a field is `"unavailable"`, `"insufficient_data"`, `null`, or an estimate rather than ground truth, the UI must render that distinction visibly — a muted style, an explicit label, anything that keeps it from reading identically to a real, checked value. This is the single most important visual rule in this document, because it's the UI-layer expression of the project's core philosophy: never let the interface imply certainty the data doesn't have.
- **No UI-side thresholds.** Color a pattern red because its own `concern`/`tier` field says so, never because the UI independently decided a number "looks bad." If the UI ever needs a cutoff that doesn't already exist as a backend field, that's a sign the computation belongs in `macro_analyzer.py`/`item_recommender.py`, not in a rendering component.
