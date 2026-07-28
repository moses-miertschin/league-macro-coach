"""Renders src/ui/presentation.py's build_draft_summary() output -- phase,
role, and the current player's champion. Hidden entirely when there's no
active draft snapshot, matching build_draft_summary() returning None in
that case.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DraftSummaryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase_label = QLabel()
        self._role_label = QLabel()
        self._champion_label = QLabel()

        layout = QVBoxLayout(self)
        layout.addWidget(self._phase_label)
        layout.addWidget(self._role_label)
        layout.addWidget(self._champion_label)

    def update_summary(self, summary: dict | None) -> None:
        if summary is None:
            self.setVisible(False)
            return

        self.setVisible(True)
        phase = summary.get("phase_name") or "Unknown phase"
        time_left_ms = summary.get("time_left_ms")
        if time_left_ms is not None:
            phase = f"{phase} ({time_left_ms // 1000}s left)"
        self._phase_label.setText(phase)
        self._role_label.setText(f"Role: {summary.get('role') or 'Unknown'}")
        champion = summary.get("champion_display_name") or "No champion selected yet"
        self._champion_label.setText(f"Champion: {champion}")

    @property
    def phase_text(self) -> str:
        return self._phase_label.text()

    @property
    def role_text(self) -> str:
        return self._role_label.text()

    @property
    def champion_text(self) -> str:
        return self._champion_label.text()
