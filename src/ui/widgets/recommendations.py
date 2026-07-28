"""Renders src/ui/presentation.py's build_recommendation_cards() output --
one label per recommendation entry, rebuilt on every update since the
recommendation list changes shape between polls (a different number of
entries, not just different text). Never re-sorts, re-filters, or
recomputes anything about a card -- ordering and content are exactly
what build_recommendation_cards() already decided.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class RecommendationListWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._empty_label = QLabel("No recommendations available.")
        self._layout.addWidget(self._empty_label)
        self._card_labels: list[QLabel] = []

    def update_cards(self, cards: list) -> None:
        for label in self._card_labels:
            self._layout.removeWidget(label)
            label.deleteLater()
        self._card_labels = []

        self._empty_label.setVisible(not cards)
        for card in cards:
            label = QLabel(self._format_card(card))
            label.setWordWrap(True)
            self._layout.addWidget(label)
            self._card_labels.append(label)

    @staticmethod
    def _format_card(card: dict) -> str:
        subject = card.get("subject") or "Unknown"
        recommendation = card.get("recommendation")
        header = f"{recommendation} — {subject}" if recommendation else subject
        severity = card.get("severity") or "unavailable"
        confidence = card.get("confidence") or "unavailable"
        reason = card.get("reason") or ""
        return f"[{severity}/{confidence}] {header}\n{reason}"

    @property
    def card_count(self) -> int:
        return len(self._card_labels)

    @property
    def card_texts(self) -> list:
        return [label.text() for label in self._card_labels]
