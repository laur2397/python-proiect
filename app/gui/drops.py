"""Fisierele trase in ferestre (faza 15, W-091): Lansatorul, OCR Editor si PDF
Editor accepta fisiere locale si le dau aplicatiei (`files_dropped`), care le
deschide in modulul potrivit (`Application.open_paths`)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QDragEnterEvent, QDropEvent


def dropped_files(event: QDragEnterEvent | QDropEvent) -> list[Path]:
    mime = event.mimeData()
    if not mime.hasUrls():
        return []
    return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]


class FileDropMixin:
    """Se pune inaintea clasei Qt; clasa trebuie sa aiba semnalul `files_dropped`."""

    def enable_file_drops(self) -> None:
        self.setAcceptDrops(True)  # type: ignore[attr-defined]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # API Qt
        if dropped_files(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # API Qt
        files = dropped_files(event)
        if files:
            event.acceptProposedAction()
            self.files_dropped.emit(files)  # type: ignore[attr-defined]
