"""Renders src/ui/presentation.py's build_status_header() output -- the
title/message/severity banner at the top of the desktop window. Pure
display: never decides a title, message, or severity itself, only shows
what it's given.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StatusHeaderWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._severity = None
        self._title_label = QLabel()
        self._message_label = QLabel()
        self._message_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title_label)
        layout.addWidget(self._message_label)

    def update_header(self, header: dict) -> None:
        self._title_label.setText(header["title"])
        self._message_label.setText(header["message"])
        self._severity = header["severity"]

    @property
    def title_text(self) -> str:
        return self._title_label.text()

    @property
    def message_text(self) -> str:
        return self._message_label.text()

    @property
    def severity(self) -> str | None:
        return self._severity
