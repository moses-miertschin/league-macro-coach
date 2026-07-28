"""End-to-end draft runtime orchestration -- wires the existing draft
components (an LCUClient-shaped session source, DraftSnapshot builder,
champion catalog, recommend_draft) into one synchronous poll_once() that
produces a single, plain, source-agnostic application-state dict.

Coordinates existing modules only: no HTTP logic (never talks to the LCU
API directly -- only calls an injected session_source callable), no
recommendation logic (never decides what to recommend -- only calls the
injected recommender), no UI logic. Every dependency is injected; the two
LCU-specific ones (session_source, client_running_check) have no default,
matching SessionPoller's own "data_source is required, no default"
precedent -- there is no universally sensible default that wouldn't
silently create a real connection to something.

Application state distinguishes four states a future UI can render
differently:
    league_client_unavailable -- the League client itself isn't running
    idle_no_champ_select      -- client running, but no champ-select session
    champ_select_active       -- a real session was found and processed
    processing_error          -- something in this poll raised unexpectedly

"processing_error" is deliberately distinct from the other three: it means
a real bug or unexpected condition occurred, not an honestly-expected
absence -- a caller should surface it, never fold it into "idle" silently.
One failed poll never kills the service: every external call is wrapped
individually, nothing here retries internally or gives up permanently --
the very next poll_once() call always tries again from a clean slate. The
champion catalog is the one exception worth naming explicitly: it's loaded
lazily and cached only after a *successful* load, so a transient catalog
failure is retried on the next poll instead of being fetched repeatedly
forever, and a successful load is never wastefully re-fetched every poll.

Compatible with SessionPoller (src/runtime/poller.py) as a data_source:
poll_once() is a zero-argument callable returning a dict, which is exactly
what SessionPoller requires. Because this service's poll_once() always
returns a dict (never None, even for the "idle"-shaped states -- an
honestly-labeled state dict, not an absence), SessionPoller's own
idle/active tracking would always read "active" if driven this way; that's
expected and harmless -- this service's own "state" field is the real
source of truth for idle-vs-active, not SessionPoller's.

Never includes lockfile passwords, auth headers, raw credentials, or
secret environment variables in its output -- structurally guaranteed by
the dependency-injection boundary itself: this module never touches
LCUClient internals, only the plain values its injected callables return.
"""

from src.draft.recommender import recommend_draft
from src.draft.snapshot import build_draft_snapshot
from src.knowledge.champion_loader import load_champion_profile
from src.riot.data_dragon import load_champion_catalog

LEAGUE_CLIENT_UNAVAILABLE = "league_client_unavailable"
IDLE_NO_CHAMP_SELECT = "idle_no_champ_select"
CHAMP_SELECT_ACTIVE = "champ_select_active"
PROCESSING_ERROR = "processing_error"

STATE_SCHEMA_VERSION = 1


class DraftRuntimeService:
    def __init__(
        self,
        session_source,
        client_running_check,
        champion_catalog_loader=load_champion_catalog,
        snapshot_builder=build_draft_snapshot,
        recommender=recommend_draft,
        profile_loader_fn=load_champion_profile,
    ):
        self._session_source = session_source
        self._client_running_check = client_running_check
        self._champion_catalog_loader = champion_catalog_loader
        self._snapshot_builder = snapshot_builder
        self._recommender = recommender
        self._profile_loader_fn = profile_loader_fn
        self._champion_catalog = None  # lazily loaded, cached only after a successful load

    def poll_once(self) -> dict:
        try:
            client_running = self._client_running_check()
        except Exception as exc:
            return self._error_state(f"client_running_check raised: {exc!r}")

        if not client_running:
            return self._state(LEAGUE_CLIENT_UNAVAILABLE)

        try:
            raw_session = self._session_source()
        except Exception as exc:
            return self._error_state(f"session_source raised: {exc!r}")

        if raw_session is None:
            return self._state(IDLE_NO_CHAMP_SELECT)

        try:
            snapshot = self._snapshot_builder(raw_session)
        except Exception as exc:
            return self._error_state(f"snapshot_builder raised: {exc!r}")

        if snapshot is None:
            return self._state(IDLE_NO_CHAMP_SELECT)

        try:
            catalog = self._champion_catalog_for_this_poll()
        except Exception as exc:
            return self._error_state(f"champion_catalog_loader raised: {exc!r}", snapshot=snapshot)

        catalog_version = catalog.get("version") if isinstance(catalog, dict) else None

        try:
            recommendations = self._recommender(snapshot, catalog, profile_loader_fn=self._profile_loader_fn)
        except Exception as exc:
            return self._error_state(f"recommender raised: {exc!r}", snapshot=snapshot, catalog_version=catalog_version)

        return self._state(
            CHAMP_SELECT_ACTIVE,
            snapshot=snapshot,
            recommendations=recommendations,
            catalog_version=catalog_version,
        )

    def _champion_catalog_for_this_poll(self):
        if self._champion_catalog is None:
            self._champion_catalog = self._champion_catalog_loader()
        return self._champion_catalog

    def _state(self, state: str, *, snapshot=None, recommendations=None, catalog_version=None) -> dict:
        return {
            "state_schema_version": STATE_SCHEMA_VERSION,
            "state": state,
            "draft_snapshot": snapshot,
            "recommendations": recommendations if recommendations is not None else [],
            "champion_catalog_version": catalog_version,
            "warnings": [],  # reserved for a future stage; never fabricated, so always empty today
            "error": None,
        }

    def _error_state(self, message: str, *, snapshot=None, catalog_version=None) -> dict:
        return {
            "state_schema_version": STATE_SCHEMA_VERSION,
            "state": PROCESSING_ERROR,
            "draft_snapshot": snapshot,
            "recommendations": [],
            "champion_catalog_version": catalog_version,
            "warnings": [],
            "error": message,
        }
