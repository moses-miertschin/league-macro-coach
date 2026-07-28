"""Renders src/ui/presentation.py's build_diagnostics() output -- errors,
warnings, unresolved ids, missing champion knowledge, and version info.
The one section deliberately allowed to look "technical"; per
UI_DESIGN.md, an "unavailable"/missing-data marker must stay visible and
distinct, never silently dropped, so nothing here is hidden by default.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DiagnosticsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = QLabel()
        self._label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)

    def update_diagnostics(self, diagnostics: dict) -> None:
        lines = []
        if diagnostics.get("error"):
            lines.append(f"Error: {diagnostics['error']}")
        for warning in diagnostics.get("warnings") or []:
            lines.append(f"Warning: {warning}")
        if diagnostics.get("unresolved_ally_ids"):
            lines.append(f"Unresolved ally champion ids: {diagnostics['unresolved_ally_ids']}")
        if diagnostics.get("unresolved_enemy_ids"):
            lines.append(f"Unresolved enemy champion ids: {diagnostics['unresolved_enemy_ids']}")
        if diagnostics.get("missing_ally_profiles"):
            lines.append(f"Missing ally champion knowledge: {diagnostics['missing_ally_profiles']}")
        catalog_version = diagnostics.get("champion_catalog_version")
        lines.append(f"Champion catalog: {catalog_version or 'unavailable'}")

        self._label.setText("\n".join(lines))

    @property
    def text(self) -> str:
        return self._label.text()
