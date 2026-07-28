"""Toolkit-independent transform of a DraftRuntimeService-shaped app-state
dict (src/draft/service.py) into stable render structures for the desktop
UI (Stage 5+). No PySide6 import, no filesystem access, no League API
logic -- this module only reshapes a dict the recommendation engine already
produced; it never recomputes a score, a severity, or a confidence level,
and never mutates its input.

Champion names: the runtime state only carries champion *ids* in
draft_snapshot (recommendation entries already carry resolved names as
their own subject/recommendation strings). Resolving an id to a name needs
the champion catalog, which this module doesn't load itself -- callers may
inject a `name_lookup(champion_id) -> str | None` callable (e.g. the
desktop app, which owns loading the catalog). Without one, or when the
lookup returns None for an id it doesn't recognize, the id itself is shown
plainly ("Champion ID 22" / "Unknown champion (ID 9999)") -- never a
guessed name.

Malformed recommendation entries (missing a required shared-schema field)
are silently skipped rather than rendered incompletely or raising -- that
would be a bug further upstream in the recommender, not something this
display layer should crash over or paper over with fabricated values.
"""

from src.draft.service import (
    CHAMP_SELECT_ACTIVE,
    IDLE_NO_CHAMP_SELECT,
    LEAGUE_CLIENT_UNAVAILABLE,
    PROCESSING_ERROR,
)

_STATUS_HEADERS = {
    LEAGUE_CLIENT_UNAVAILABLE: {
        "title": "League Client Not Running",
        "message": "Start League of Legends to begin receiving draft recommendations.",
        "severity": "low",
        "show_content": False,
    },
    IDLE_NO_CHAMP_SELECT: {
        "title": "Waiting for Champ Select",
        "message": "Connected to the League client. Recommendations will appear once champ select begins.",
        "severity": "low",
        "show_content": False,
    },
    CHAMP_SELECT_ACTIVE: {
        "title": "Champ Select Active",
        "message": "Live draft recommendations below.",
        "severity": "low",
        "show_content": True,
    },
    PROCESSING_ERROR: {
        "title": "Processing Error",
        "message": None,  # filled in from app_state["error"] below
        "severity": "high",
        "show_content": False,
    },
}

REQUIRED_CARD_FIELDS = ("category", "subject", "recommendation", "reason", "severity", "confidence", "priority")


def build_status_header(app_state: dict) -> dict:
    state = app_state.get("state")
    template = _STATUS_HEADERS.get(state)
    if template is None:
        return {
            "title": "Unknown State",
            "message": f"Unrecognized runtime state: {state!r}",
            "severity": "high",
            "show_content": False,
        }
    header = dict(template)
    if state == PROCESSING_ERROR:
        header["message"] = app_state.get("error") or "An unexpected error occurred with no further detail."
    return header


def _champion_display(champion_id, name_lookup) -> str | None:
    if champion_id is None:
        return None
    if name_lookup is None:
        return f"Champion ID {champion_id}"
    name = name_lookup(champion_id)
    return name if name is not None else f"Unknown champion (ID {champion_id})"


def build_draft_summary(app_state: dict, name_lookup=None) -> dict | None:
    snapshot = app_state.get("draft_snapshot")
    if not snapshot:
        return None
    current_player = snapshot.get("current_player") or {}
    phase = snapshot.get("phase") or {}
    champion_id = current_player.get("champion_id")
    return {
        "phase_name": phase.get("name"),
        "time_left_ms": phase.get("time_left_ms"),
        "is_infinite": phase.get("is_infinite"),
        "role": current_player.get("assigned_position"),
        "champion_id": champion_id,
        "champion_display_name": _champion_display(champion_id, name_lookup),
    }


def build_recommendation_cards(app_state: dict) -> list:
    recommendations = app_state.get("recommendations") or []
    cards = []
    for entry in recommendations:
        if not isinstance(entry, dict) or any(field not in entry for field in REQUIRED_CARD_FIELDS):
            continue
        details = entry.get("details") or {}
        cards.append({
            "priority": entry.get("priority"),
            "category": entry.get("category"),
            "subject": entry.get("subject"),
            "recommendation": entry.get("recommendation"),
            "reason": entry.get("reason"),
            "evidence": entry.get("evidence"),
            "severity": entry.get("severity"),
            "confidence": entry.get("confidence"),
            "confidence_score": entry.get("confidence_score"),
            "score_breakdown": details.get("score_breakdown"),
            "source": entry.get("source"),
            "details": details,
        })
    return cards


def build_diagnostics(app_state: dict) -> dict:
    recommendations = app_state.get("recommendations") or []
    unresolved_ally_ids, unresolved_enemy_ids, missing_ally_profiles = [], [], []
    for entry in recommendations:
        if not isinstance(entry, dict):
            continue
        details = entry.get("details") or {}
        if "unresolved_ally_ids" in details:
            unresolved_ally_ids = details["unresolved_ally_ids"]
        if "unresolved_enemy_ids" in details:
            unresolved_enemy_ids = details["unresolved_enemy_ids"]
        if "missing_ally_profiles" in details:
            missing_ally_profiles = details["missing_ally_profiles"]

    return {
        "warnings": app_state.get("warnings") or [],
        "error": app_state.get("error"),
        "state_schema_version": app_state.get("state_schema_version"),
        "champion_catalog_version": app_state.get("champion_catalog_version"),
        "unresolved_ally_ids": unresolved_ally_ids,
        "unresolved_enemy_ids": unresolved_enemy_ids,
        "missing_ally_profiles": missing_ally_profiles,
    }


def build_presentation(app_state: dict, name_lookup=None) -> dict:
    return {
        "status_header": build_status_header(app_state),
        "draft_summary": build_draft_summary(app_state, name_lookup),
        "recommendation_cards": build_recommendation_cards(app_state),
        "diagnostics": build_diagnostics(app_state),
    }
