"""Self-check for src/draft/service.py -- DraftRuntimeService, the
end-to-end draft orchestration layer (Stage 2 of this session's staged
implementation plan).

Written before service.py's implementation. Every dependency is a
hand-built fake -- no real LCUClient, no real network call, no real
filesystem champion-catalog fetch. Run with:
python -m tests.test_draft_service
"""

import copy
import inspect
import json

from src.draft.recommender import recommend_draft
from src.draft.service import (
    CHAMP_SELECT_ACTIVE,
    IDLE_NO_CHAMP_SELECT,
    LEAGUE_CLIENT_UNAVAILABLE,
    PROCESSING_ERROR,
    DraftRuntimeService,
)
from src.draft.snapshot import build_draft_snapshot
from src.knowledge.champion_loader import load_champion_profile
from src.riot.data_dragon import load_champion_catalog
from src.runtime.poller import SessionPoller

FAKE_CATALOG = {"version": "14.1.1", "champions_by_id": {}, "champions_by_name": {}}
FAKE_RAW_SESSION = {"myTeam": [], "theirTeam": [], "localPlayerCellId": 0, "bans": {}, "timer": {}}
FAKE_SNAPSHOT = {
    "ally_team": [], "enemy_team": [], "ally_picks": [], "enemy_picks": [],
    "ally_bans": [], "enemy_bans": [],
    "current_player": {"cell_id": 0, "champion_id": None, "assigned_position": "middle"},
    "phase": {"name": "PLANNING", "time_left_ms": 10000, "is_infinite": False},
}
FAKE_RECOMMENDATIONS = [{
    "system": "draft", "category": "pick_recommendation", "subject": "Annie",
    "recommendation": "Annie", "reason": "Annie plays middle.", "evidence": [],
    "confidence": "high", "confidence_score": None, "severity": "low", "priority": 1,
    "source": "champion_knowledge", "details": {},
}]


def _service(**overrides):
    defaults = dict(
        session_source=lambda: FAKE_RAW_SESSION,
        client_running_check=lambda: True,
        champion_catalog_loader=lambda: FAKE_CATALOG,
        snapshot_builder=lambda raw: FAKE_SNAPSHOT,
        recommender=lambda snapshot, catalog, profile_loader_fn=None: FAKE_RECOMMENDATIONS,
        profile_loader_fn=lambda name: None,
    )
    defaults.update(overrides)
    return DraftRuntimeService(**defaults)


EXPECTED_STATE_KEYS = {
    "state_schema_version", "state", "draft_snapshot", "recommendations",
    "champion_catalog_version", "warnings", "error",
}


def test_league_closed_returns_league_client_unavailable_state():
    calls = []
    service = _service(client_running_check=lambda: False, session_source=lambda: calls.append(1) or FAKE_RAW_SESSION)

    result = service.poll_once()

    assert result["state"] == LEAGUE_CLIENT_UNAVAILABLE
    assert result["draft_snapshot"] is None
    assert result["recommendations"] == []
    assert result["error"] is None
    assert calls == []  # session_source must not even be called once client is known unavailable


def test_league_open_no_champ_select_returns_idle_state():
    service = _service(session_source=lambda: None)

    result = service.poll_once()

    assert result["state"] == IDLE_NO_CHAMP_SELECT
    assert result["draft_snapshot"] is None
    assert result["recommendations"] == []
    assert result["error"] is None


def test_active_pre_lock_draft_returns_champ_select_active_with_recommendations():
    service = _service()

    result = service.poll_once()

    assert result["state"] == CHAMP_SELECT_ACTIVE
    assert result["draft_snapshot"] == FAKE_SNAPSHOT
    assert result["recommendations"] == FAKE_RECOMMENDATIONS
    assert result["champion_catalog_version"] == "14.1.1"
    assert result["error"] is None


def test_active_post_lock_draft_still_returns_champ_select_active():
    locked_snapshot = dict(FAKE_SNAPSHOT, current_player={"cell_id": 0, "champion_id": 157, "assigned_position": "middle"})
    locked_recs = [{
        "system": "draft", "category": "counter_warning", "subject": "Malphite",
        "recommendation": None, "reason": "Malphite is a known counter to Yone.", "evidence": [],
        "confidence": "high", "confidence_score": None, "severity": "high", "priority": 1,
        "source": "champion_knowledge", "details": {},
    }]
    service = _service(
        snapshot_builder=lambda raw: locked_snapshot,
        recommender=lambda s, c, profile_loader_fn=None: locked_recs,
    )

    result = service.poll_once()

    assert result["state"] == CHAMP_SELECT_ACTIVE
    assert result["draft_snapshot"]["current_player"]["champion_id"] == 157
    assert result["recommendations"] == locked_recs


def test_snapshot_builder_returning_none_is_treated_as_idle():
    service = _service(snapshot_builder=lambda raw: None)

    result = service.poll_once()

    assert result["state"] == IDLE_NO_CHAMP_SELECT


def test_catalog_failure_returns_processing_error_but_keeps_the_snapshot():
    def failing_catalog_loader():
        raise RuntimeError("Data Dragon unreachable")

    service = _service(champion_catalog_loader=failing_catalog_loader)

    result = service.poll_once()

    assert result["state"] == PROCESSING_ERROR
    assert result["error"] is not None
    assert "Data Dragon unreachable" in result["error"]
    assert result["draft_snapshot"] == FAKE_SNAPSHOT  # already built before the catalog step failed
    assert result["recommendations"] == []


def test_malformed_snapshot_recovers_as_processing_error_not_a_crash():
    # Uses the real recommend_draft (not the default fake, which ignores
    # its snapshot argument entirely) so this test actually exercises code
    # that chokes on a malformed shape, proving poll_once()'s own
    # try/except recovers instead of letting the exception propagate.
    service = _service(snapshot_builder=lambda raw: "not a real snapshot", recommender=recommend_draft)

    result = service.poll_once()  # must not raise out of poll_once()

    assert result["state"] == PROCESSING_ERROR
    assert result["error"] is not None


def test_processing_exception_does_not_permanently_kill_the_service():
    attempts = {"count": 0}

    def flaky_session_source():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient failure")
        return FAKE_RAW_SESSION

    service = _service(session_source=flaky_session_source)

    first = service.poll_once()
    second = service.poll_once()

    assert first["state"] == PROCESSING_ERROR
    assert second["state"] == CHAMP_SELECT_ACTIVE  # fully recovered on the very next poll, no persistent damage


def test_champion_catalog_is_loaded_once_and_cached_across_polls():
    calls = []

    def counting_catalog_loader():
        calls.append(1)
        return FAKE_CATALOG

    service = _service(champion_catalog_loader=counting_catalog_loader)

    service.poll_once()
    service.poll_once()
    service.poll_once()

    assert len(calls) == 1  # loaded once, reused for every subsequent poll


def test_every_poll_result_is_a_plain_dict_with_the_documented_shape():
    scenarios = [
        _service(client_running_check=lambda: False),
        _service(session_source=lambda: None),
        _service(),
    ]
    for service in scenarios:
        result = service.poll_once()
        assert isinstance(result, dict)
        assert set(result.keys()) == EXPECTED_STATE_KEYS


def test_no_credentials_or_secrets_appear_in_output():
    service = _service()
    result = service.poll_once()

    serialized = json.dumps(result, default=str).lower()
    for forbidden in ("password", "authorization", "lockfile", "secret", "bearer "):
        assert forbidden not in serialized


def test_does_not_mutate_raw_session_or_snapshot():
    raw_session_copy = copy.deepcopy(FAKE_RAW_SESSION)
    snapshot_copy = copy.deepcopy(FAKE_SNAPSHOT)

    _service().poll_once()

    assert FAKE_RAW_SESSION == raw_session_copy
    assert FAKE_SNAPSHOT == snapshot_copy


def test_poll_once_is_a_valid_session_poller_data_source():
    service = _service()
    poller = SessionPoller(data_source=service.poll_once)

    result = poller.poll_once()

    assert isinstance(result, dict)
    # poll_once() always returns a dict, never None -- so SessionPoller's
    # own idle/active tracking always reads "active" when used this way;
    # this service's own "state" field is the real source of truth.
    assert poller.state == "active"


def test_default_dependencies_are_the_real_project_functions():
    sig = inspect.signature(DraftRuntimeService.__init__)
    assert sig.parameters["champion_catalog_loader"].default is load_champion_catalog
    assert sig.parameters["snapshot_builder"].default is build_draft_snapshot
    assert sig.parameters["recommender"].default is recommend_draft
    assert sig.parameters["profile_loader_fn"].default is load_champion_profile


if __name__ == "__main__":
    test_league_closed_returns_league_client_unavailable_state()
    test_league_open_no_champ_select_returns_idle_state()
    test_active_pre_lock_draft_returns_champ_select_active_with_recommendations()
    test_active_post_lock_draft_still_returns_champ_select_active()
    test_snapshot_builder_returning_none_is_treated_as_idle()
    test_catalog_failure_returns_processing_error_but_keeps_the_snapshot()
    test_malformed_snapshot_recovers_as_processing_error_not_a_crash()
    test_processing_exception_does_not_permanently_kill_the_service()
    test_champion_catalog_is_loaded_once_and_cached_across_polls()
    test_every_poll_result_is_a_plain_dict_with_the_documented_shape()
    test_no_credentials_or_secrets_appear_in_output()
    test_does_not_mutate_raw_session_or_snapshot()
    test_poll_once_is_a_valid_session_poller_data_source()
    test_default_dependencies_are_the_real_project_functions()
    print("All checks passed.")
