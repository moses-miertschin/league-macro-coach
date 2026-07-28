"""Self-check for src/draft/client.py -- the LCU (League Client Update)
API client, the first real SessionPoller data source (see
src/runtime/poller.py, ROADMAP.md Sec.2).

Written before client.py's implementation. No real League installation is
used anywhere here: lockfiles are temp files this suite writes itself, and
every HTTP call goes through a fake get_fn -- never the real requests.get.
Run with: python -m tests.test_draft_client
"""

import tempfile
from pathlib import Path

import requests

from src.draft.client import (
    LCUClient,
    LCUCredentials,
    LockfileFormatError,
    build_auth,
    parse_lockfile,
)
from src.runtime.poller import SessionPoller

REAL_SHAPED_LOCKFILE_CONTENTS = "LeagueClient:23236:54321:pAsSwOrD123:https"
CHAMP_SELECT_SESSION = {
    "actions": [[{"actorCellId": 0, "championId": 0, "type": "pick", "completed": False}]],
    "localPlayerCellId": 0,
    "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 30000},
}


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._json_data


class _TempLockfile:
    """A real temp file with fake contents -- not a real League install,
    per this milestone's testing requirement."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "lockfile"
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()

    def write(self, contents: str) -> None:
        self.path.write_text(contents, encoding="utf-8")


# ---- lockfile parsing ----


def test_parse_lockfile_extracts_port_and_password():
    credentials = parse_lockfile(REAL_SHAPED_LOCKFILE_CONTENTS)
    assert credentials == LCUCredentials(port="54321", password="pAsSwOrD123")


def test_parse_lockfile_tolerates_trailing_whitespace():
    credentials = parse_lockfile(REAL_SHAPED_LOCKFILE_CONTENTS + "\n")
    assert credentials.port == "54321"


def test_parse_lockfile_rejects_malformed_contents():
    try:
        parse_lockfile("not:enough:fields")
    except LockfileFormatError:
        pass
    else:
        raise AssertionError("Expected LockfileFormatError for a malformed lockfile")


# ---- authentication generation ----


def test_build_auth_uses_riot_username_and_lockfile_password():
    credentials = LCUCredentials(port="54321", password="pAsSwOrD123")
    assert build_auth(credentials) == ("riot", "pAsSwOrD123")


# ---- successful champ-select retrieval ----


def test_get_champ_select_session_returns_data_on_success():
    with _TempLockfile() as lf:
        lf.write(REAL_SHAPED_LOCKFILE_CONTENTS)
        calls = []

        def fake_get(url, auth=None, verify=None, timeout=None):
            calls.append({"url": url, "auth": auth, "verify": verify, "timeout": timeout})
            return _FakeResponse(status_code=200, json_data=CHAMP_SELECT_SESSION)

        client = LCUClient(lockfile_path=lf.path, get_fn=fake_get)
        result = client.get_champ_select_session()

        assert result == CHAMP_SELECT_SESSION
        assert len(calls) == 1
        assert calls[0]["url"] == "https://127.0.0.1:54321/lol-champ-select/v1/session"
        assert calls[0]["auth"] == ("riot", "pAsSwOrD123")
        assert calls[0]["verify"] is False  # LCU uses a self-signed cert


def test_lcu_client_is_directly_callable():
    with _TempLockfile() as lf:
        lf.write(REAL_SHAPED_LOCKFILE_CONTENTS)
        client = LCUClient(lockfile_path=lf.path, get_fn=lambda *a, **k: _FakeResponse(200, CHAMP_SELECT_SESSION))

        assert client() == CHAMP_SELECT_SESSION


# ---- graceful failure when League is closed / no session ----


def test_returns_none_when_no_lockfile_exists():
    with _TempLockfile() as lf:
        # lf.path is never written -- simulates League client not running
        calls = []

        def fake_get(*args, **kwargs):
            calls.append(1)
            return _FakeResponse(200, CHAMP_SELECT_SESSION)

        client = LCUClient(lockfile_path=lf.path, get_fn=fake_get)
        result = client.get_champ_select_session()

        assert result is None
        assert calls == []  # no HTTP call is even attempted without a lockfile


def test_returns_none_on_404_no_champ_select_in_progress():
    with _TempLockfile() as lf:
        lf.write(REAL_SHAPED_LOCKFILE_CONTENTS)
        client = LCUClient(lockfile_path=lf.path, get_fn=lambda *a, **k: _FakeResponse(status_code=404))

        assert client.get_champ_select_session() is None


def test_returns_none_on_connection_error():
    with _TempLockfile() as lf:
        lf.write(REAL_SHAPED_LOCKFILE_CONTENTS)

        def raising_get(*args, **kwargs):
            raise requests.exceptions.ConnectionError("client closed mid-poll")

        client = LCUClient(lockfile_path=lf.path, get_fn=raising_get)

        assert client.get_champ_select_session() is None


def test_propagates_unexpected_server_errors_instead_of_masking_them():
    # A 404 (no session) and a connection error (client closed) are the two
    # honestly-expected "nothing to report" cases. A 500 is neither --
    # masking it as None would hide a real bug instead of surfacing it.
    with _TempLockfile() as lf:
        lf.write(REAL_SHAPED_LOCKFILE_CONTENTS)
        client = LCUClient(lockfile_path=lf.path, get_fn=lambda *a, **k: _FakeResponse(status_code=500))

        try:
            client.get_champ_select_session()
        except requests.exceptions.HTTPError:
            pass
        else:
            raise AssertionError("Expected a 500 to raise rather than be swallowed as None")


# ---- client-running check (cheap, local-only, no network) ----


def test_is_client_running_true_when_lockfile_present():
    with _TempLockfile() as lf:
        lf.write(REAL_SHAPED_LOCKFILE_CONTENTS)
        client = LCUClient(lockfile_path=lf.path, get_fn=lambda *a, **k: _FakeResponse(200, CHAMP_SELECT_SESSION))

        assert client.is_client_running() is True


def test_is_client_running_false_when_no_lockfile():
    with _TempLockfile() as lf:
        # lf.path is never written -- simulates League client not running
        calls = []

        def fake_get(*args, **kwargs):
            calls.append(1)
            return _FakeResponse(200, CHAMP_SELECT_SESSION)

        client = LCUClient(lockfile_path=lf.path, get_fn=fake_get)

        assert client.is_client_running() is False
        assert calls == []  # no HTTP call is ever made by this check


# ---- SessionPoller compatibility ----


def test_lcu_client_works_as_a_session_poller_data_source_when_idle():
    with _TempLockfile() as lf:
        # no lockfile written -- League client not running
        client = LCUClient(lockfile_path=lf.path, get_fn=lambda *a, **k: _FakeResponse(200, CHAMP_SELECT_SESSION))
        poller = SessionPoller(data_source=client)

        poller.poll_once()

        assert poller.state == "idle"
        assert poller.last_result is None


def test_lcu_client_works_as_a_session_poller_data_source_when_active():
    with _TempLockfile() as lf:
        lf.write(REAL_SHAPED_LOCKFILE_CONTENTS)
        client = LCUClient(lockfile_path=lf.path, get_fn=lambda *a, **k: _FakeResponse(200, CHAMP_SELECT_SESSION))
        poller = SessionPoller(data_source=client)

        poller.poll_once()

        assert poller.state == "active"
        assert poller.last_result == CHAMP_SELECT_SESSION


if __name__ == "__main__":
    test_parse_lockfile_extracts_port_and_password()
    test_parse_lockfile_tolerates_trailing_whitespace()
    test_parse_lockfile_rejects_malformed_contents()
    test_build_auth_uses_riot_username_and_lockfile_password()
    test_get_champ_select_session_returns_data_on_success()
    test_lcu_client_is_directly_callable()
    test_returns_none_when_no_lockfile_exists()
    test_returns_none_on_404_no_champ_select_in_progress()
    test_returns_none_on_connection_error()
    test_propagates_unexpected_server_errors_instead_of_masking_them()
    test_is_client_running_true_when_lockfile_present()
    test_is_client_running_false_when_no_lockfile()
    test_lcu_client_works_as_a_session_poller_data_source_when_idle()
    test_lcu_client_works_as_a_session_poller_data_source_when_active()
    print("All checks passed.")
