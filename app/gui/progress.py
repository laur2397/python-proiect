"""Operatiile lungi cu progres si anulare (faza 6b, pasul 6b.6a).

Nucleul raporteaza prin `ProgressCallback` (cheia etapei + detaliu) si se
opreste cand `CancelToken` intoarce True (N-028: paginile terminate raman).

[DECIZIE AUTONOMA] (faza_6b_pasi.md, decizia 11) Operatia ruleaza pe firul
interfetei, iar dialogul de progres proceseaza evenimentele la fiecare raport:
conexiunile SQLite ale proiectului sunt legate de firul care le-a deschis, iar
recunoasterea are deja propriul fond de fire pentru OCR (N-027). Interfata
raspunde intre pagini; butonul `Cancel` opreste dupa pagina in lucru.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog, QWidget

from app.core.errors import OperationCancelledError
from app.core.model import CancelToken, Progress, ProgressCallback
from app.gui.i18n import tr

T = TypeVar("T")


class ProgressRunner:
    """Un dialog de progres modal; `progress` si `cancel` se dau nucleului."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        self.dialog = QProgressDialog(title, tr("progress.cancel"), 0, 0, parent)
        self.dialog.setObjectName("progress_dialog")
        self.dialog.setWindowTitle(title)
        self.dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.dialog.setMinimumDuration(400)
        self.cancelled = False
        self.reports: list[Progress] = []

    def progress(self, report: Progress) -> None:
        self.reports.append(report)
        self.dialog.setMaximum(max(report.total, 1))
        self.dialog.setValue(min(report.current, report.total))
        text = tr(report.stage)
        if report.stage == "stage.recognizing":  # Y-308: `N of M pages recognized`
            text = tr("progress.pages_recognized", n=report.current, total=report.total)
        self.dialog.setLabelText(f"{text}\n{report.detail}" if report.detail else text)
        QApplication.processEvents()

    def cancel(self) -> bool:
        QApplication.processEvents()
        self.cancelled = self.cancelled or self.dialog.wasCanceled()
        return self.cancelled

    def run(self, operation: Callable[[ProgressCallback, CancelToken], T]) -> T | None:
        """Rezultatul operatiei; None daca a fost anulata (ce s-a terminat ramane)."""
        try:
            return operation(self.progress, self.cancel)
        except OperationCancelledError:
            return None
        finally:
            self.dialog.reset()
            self.dialog.hide()


def run_with_progress(title: str, operation: Callable[[ProgressCallback, CancelToken], Any],
                      parent: QWidget | None = None) -> Any:
    return ProgressRunner(title, parent).run(operation)
