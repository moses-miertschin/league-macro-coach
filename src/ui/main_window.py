"""The desktop application's main window -- assembles the four
src/ui/widgets/ into one vertical layout and drives them from a
src/ui/presentation.py presentation dict. Contains no polling, no
filesystem access, no League API logic: Stage 6 (live file-watcher
integration) is what will actually call update_presentation()/
update_from_app_state() on a timer; this stage only builds the window
that's ready to receive those calls.
"""

from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from src.ui.presentation import build_presentation
from src.ui.widgets.diagnostics import DiagnosticsWidget
from src.ui.widgets.draft_summary import DraftSummaryWidget
from src.ui.widgets.recommendations import RecommendationListWidget
from src.ui.widgets.status_header import StatusHeaderWidget


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
