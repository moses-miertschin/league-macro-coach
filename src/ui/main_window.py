"""The desktop application's main window -- assembles the four
src/ui/widgets/ into one vertical layout and drives them from a
src/ui/presentation.py presentation dict. Contains no polling, no
filesystem access, no League API logic: Stage 6's LiveStateSource
(src/ui/live_state_source.py) is what actually calls
update_from_state_result() on every change; this module only reacts.

update_from_state_result() exists because a raw StateReadResult
(src/ui/state_reader.py) can carry four *reader*-level statuses
build_presentation() was never meant to know about (file missing,
invalid JSON, wrong shape, unexpected read error) alongside the one
status (valid_state) that actually carries a DraftRuntimeService-shaped
app-state dict. Keeping that reader-status-to-header mapping here,
rather than teaching presentation.py about StateReadResult, keeps
presentation.py's documented contract ("takes a DraftRuntimeService
app-state dict") exact -- this window is the natural place to bridge
the two, since it already bridges app_state -> widgets via
update_from_app_state().
"""

from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from src.ui.presentation import build_presentation
from src.ui.state_reader import FILE_MISSING, INVALID_JSON, INVALID_STATE_SHAPE, READ_ERROR, VALID_STATE
from src.ui.widgets.diagnostics import DiagnosticsWidget
from src.ui.widgets.draft_summary import DraftSummaryWidget
from src.ui.widgets.recommendations import RecommendationListWidget
from src.ui.widgets.status_header import StatusHeaderWidget

_READ_RESULT_HEADERS = {
    FILE_MISSING: {
        "title": "No Runtime State Found",
        "message": "reports/runtime/draft_state.json hasn't been created yet. Run the draft CLI (--once or --watch) or demo mode to generate it.",
        "severity": "low",
    },
    INVALID_JSON: {
        "title": "Runtime State File Corrupted",
        "message": "The state file exists but isn't valid JSON.",
        "severity": "high",
    },
    INVALID_STATE_SHAPE: {
        "title": "Runtime State File Has an Unexpected Shape",
        "message": "The state file's contents don't match the expected format.",
        "severity": "high",
    },
    READ_ERROR: {
        "title": "Could Not Read Runtime State File",
        "message": "An unexpected error occurred while reading the state file.",
        "severity": "high",
    },
}


def _empty_presentation(header: dict, error: str | None) -> dict:
    return {
        "status_header": {**header, "show_content": False},
        "draft_summary": None,
        "recommendation_cards": [],
        "diagnostics": {
            "warnings": [], "error": error, "state_schema_version": None, "champion_catalog_version": None,
            "unresolved_ally_ids": [], "unresolved_enemy_ids": [], "missing_ally_profiles": [],
        },
    }


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LeagueMacroCoach — Draft Assistant")

        self.status_header = StatusHeaderWidget()
        self.draft_summary = DraftSummaryWidget()
        self.recommendations = RecommendationListWidget()
        self.diagnostics = DiagnosticsWidget()

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.status_header)
        layout.addWidget(self.draft_summary)
        layout.addWidget(self.recommendations)
        layout.addWidget(self.diagnostics)
        self.setCentralWidget(central)

    def update_presentation(self, presentation: dict) -> None:
        self.status_header.update_header(presentation["status_header"])
        self.draft_summary.update_summary(presentation["draft_summary"])
        self.recommendations.update_cards(presentation["recommendation_cards"])
        self.diagnostics.update_diagnostics(presentation["diagnostics"])

    def update_from_app_state(self, app_state: dict, name_lookup=None) -> None:
        self.update_presentation(build_presentation(app_state, name_lookup=name_lookup))

    def update_from_state_result(self, result, name_lookup=None) -> None:
        if result.status == VALID_STATE:
            self.update_from_app_state(result.state, name_lookup=name_lookup)
            return

        header = _READ_RESULT_HEADERS.get(result.status, {
            "title": "Unknown Runtime State Status",
            "message": f"Unrecognized reader status: {result.status!r}",
            "severity": "high",
        })
        message = header["message"] if result.error is None else f"{header['message']} ({result.error})"
        self.update_presentation(_empty_presentation({**header, "message": message}, result.error))
