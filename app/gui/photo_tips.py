"""Recomandarile pentru fotografierea documentelor (faza 6d, pasul 6d.4).

K-014 (camera si rezolutia), K-015 (iluminarea), K-016 (pozitionarea) si
K-017 (pozele neclare se corecteaza cu `Photo Correction` din Image Editor).
Textele sunt in traduceri; dialogul doar le aranjeaza.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.gui.i18n import tr

SECTIONS = {
    "camera": 6,  # K-014
    "light": 4,  # K-015
    "position": 6,  # K-016
}
"""Grupurile si numarul de recomandari din fiecare (`photo.<grup>.<n>`)."""


def tips(section: str) -> list[str]:
    return [tr(f"photo.{section}.{n}") for n in range(1, SECTIONS[section] + 1)]


class PhotoTipsDialog(QDialog):
    photo_correction_requested = Signal()
    """K-017: deschide `Photo Correction` din Image Editor."""

    def __init__(self, *, can_correct: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("photo_tips")
        self.setWindowTitle(tr("photo.title"))
        layout = QVBoxLayout(self)
        for section in SECTIONS:
            group = QGroupBox(tr(f"photo.section.{section}"))
            group.setObjectName(f"photo_{section}")
            box = QVBoxLayout(group)
            for text in tips(section):
                label = QLabel(f"• {text}")
                label.setWordWrap(True)
                box.addWidget(label)
            layout.addWidget(group)
        blurry = QLabel(tr("photo.blurry"))  # K-017
        blurry.setObjectName("photo_blurry")
        blurry.setWordWrap(True)
        layout.addWidget(blurry)
        self.correct = QPushButton(tr("photo.open_correction"))
        self.correct.setObjectName("photo_open_correction")
        self.correct.setEnabled(can_correct)
        self.correct.clicked.connect(self._correct)
        layout.addWidget(self.correct)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _correct(self) -> None:
        self.photo_correction_requested.emit()
        self.accept()
