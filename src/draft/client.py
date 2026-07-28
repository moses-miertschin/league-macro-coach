"""LCU (League Client Update) API client -- the first real data source for
src/runtime/poller.py's SessionPoller (see ROADMAP.md Sec.2: "LCU API ...
/lol-champ-select/v1/session is the key endpoint.").

Data access only. No pick/ban/synergy recommendation logic lives here --
that's explicitly separate, future work per this checkpoint's scope (see
RECOMMENDATION_SYSTEM_DESIGN.md and ROADMAP.md Sec.4 for where it belongs
once this foundation exists).

The LCU API is distinct from the Live Client Data API LIVE_SYSTEM_DESIGN.md
designs against: a different local port (read per-launch from a lockfile,
not the fixed 2999), HTTP Basic auth against a per-launch password (the
Live Client Data API is unauthenticated), and reachable whenever the
League *client* itself is open -- covering champ select/lobby, not only a
live game.

Lockfile format, written by the League client on every launch, one line,
colon-separated: `name:pid:port:password:protocol`. This is Riot's own
documented mechanism, read from disk -- not reverse-engineered traffic.
"""

from dataclasses import dataclass
from pathlib import Path

import requests

DEFAULT_LOCKFILE_PATH = Path("C:/Riot Games/League of Legends/lockfile")
CHAMP_SELECT_SESSION_ENDPOINT = "/lol-champ-select/v1/session"
REQUEST_TIMEOUT_SECONDS = 2
LCU_USERNAME = "riot"


@dataclass(frozen=True)
class LCUCredentials:
    port: str
    password: str


class LockfileFormatError(ValueError):
    """Raised when a lockfile exists but its contents don't match the
    documented 5-field shape -- an unexpected client version/format
    change, not the honestly-expected "client isn't running" case."""


def parse_lockfile(contents: str) -> LCUCredentials:
    fields = contents.strip().split(":")
    if len(fields) != 5:
        raise LockfileFormatError(
            f"Expected 5 colon-separated fields in lockfile, got {len(fields)}: {contents!r}"
        )
    _name, _pid, port, password, _protocol = fields
    return LCUCredentials(port=port, password=password)


def build_auth(credentials: LCUCredentials) -> tuple:
    """The LCU API uses HTTP Basic auth with the fixed username "riot"
    and the per-launch password from the lockfile."""
    return (LCU_USERNAME, credentials.password)


class LCUClient:
    """A zero-argument callable -- pass an instance directly as
    SessionPoller's data_source.

    Returns the raw /lol-champ-select/v1/session dict when a champ-select
    session is in progress, or None for every honestly-expected "nothing
    to report" case (League client not running, no lockfile, client open
    but no session, connection refused mid-poll) -- never fabricates a
    result and never raises for those, matching the project's
    "unavailable, not fabricated" discipline. Unexpected server errors
    (anything but 404) still raise, since silently swallowing those would
    hide a real bug rather than report a genuine absence.
    """

    def __init__(self, lockfile_path: Path = DEFAULT_LOCKFILE_PATH, get_fn=requests.get):
        self.lockfile_path = Path(lockfile_path)
        self._get_fn = get_fn

    def __call__(self):
        return self.get_champ_select_session()

    def get_champ_select_session(self):
        credentials = self._read_credentials()
        if credentials is None:
            return None

        url = f"https://127.0.0.1:{credentials.port}{CHAMP_SELECT_SESSION_ENDPOINT}"
        try:
            response = self._get_fn(
                url,
                auth=build_auth(credentials),
                verify=False,  # LCU serves a self-signed cert
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.exceptions.RequestException:
            return None  # client closed mid-poll, or unreachable

        if response.status_code == 404:
            return None  # client is open, but no champ-select session right now

        response.raise_for_status()
        return response.json()

    def _read_credentials(self):
        if not self.lockfile_path.exists():
            return None  # League client is not running
        contents = self.lockfile_path.read_text(encoding="utf-8")
        return parse_lockfile(contents)
