"""`Help > Supported formats` (faza 16, Y-112): ce format merge in ce modul, dupa
tabelul B.1 (Y-100); formatele pe care DocuLens nu le citeste inca sunt marcate."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.core.formats import FORMATS, UNREAD_OLD_OFFICE
from app.gui.i18n import tr

COLUMNS = ("format", "extensions", "ocr_editor", "pdf_editor", "compare", "output")


def mark(value: bool) -> str:
    return tr("formats.yes") if value else tr("formats.no")


class FormatsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("formats_dialog")
        self.setWindowTitle(tr("formats.title"))
        layout = QVBoxLayout(self)
        self.table = QTableWidget(len(FORMATS), len(COLUMNS))
        self.table.setObjectName("formats_table")
        self.table.setHorizontalHeaderLabels([tr(f"formats.col.{c}") for c in COLUMNS])
        for row, fmt in enumerate(FORMATS):
            name = tr(f"format.name.{fmt.key}")
            unread = not fmt.readable or any(e in UNREAD_OLD_OFFICE for e in fmt.extensions)
            if unread:
                name += " " + tr("formats.unread_mark")
            values = (name, " ".join(fmt.extensions), mark(fmt.ocr_editor),
                      mark(fmt.pdf_editor), mark(fmt.compare), mark(fmt.output))
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.resize(820, 620)
