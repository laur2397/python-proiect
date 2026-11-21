"""Raportarea unei erori neasteptate (Y-025), partea de interfata.

Nucleul scrie eroarea in jurnal si raportul separat (`applog.
record_unexpected_error`); dialogul arata mesajul, urma stivei copiabila si
salvarea raportului. Aplicatia nu se inchide: documentul deschis ramane si se
poate salva.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from types import TracebackType
from typing import Any

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.applog import CrashReport, record_unexpected_error
from app.gui.i18n import tr


class ErrorDialog(QDialog):
    def __init__(self, report: CrashReport, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("error_dialog")
        self.setWindowTitle(tr("crash.title"))
        self.report = report
        intro = QLabel(tr("crash.intro"))
        intro.setWordWrap(True)
        message = QLabel(f"{report.error_type}: {report.message}")
        message.setObjectName("crash_message")
        message.setWordWrap(True)
        self.trace = QPlainTextEdit(report.traceback_text)
        self.trace.setObjectName("crash_trace")
        self.trace.setReadOnly(True)
        self.copy_button = QPushButton(tr("crash.copy"))
        self.copy_button.setObjectName("crash_copy")
        self.copy_button.clicked.connect(self.copy)
        self.save_button = QPushButton(tr("crash.save"))
        self.save_button.setObjectName("crash_save")
        self.save_button.setEnabled(report.report_path is not None)
        self.save_button.clicked.connect(lambda: self.save())
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.addButton(self.copy_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self.save_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(message)
        layout.addWidget(self.trace, 1)
        layout.addWidget(buttons)
        self.resize(640, 420)

    def copy(self) -> None:
        QApplication.clipboard().setText(
            f"{self.report.error_type}: {self.report.message}\n\n{self.report.traceback_text}")

    def save(self, target: Path | None = None) -> bool:
        """Copiaza raportul (cu ultimele randuri din jurnal) unde alege utilizatorul."""
        source = self.report.report_path
        if source is None:
            return False
        if target is None:
            chosen, _ = QFileDialog.getSaveFileName(self, tr("crash.save"), source.name,
                                                    "*.txt")
            if not chosen:
                return False
            target = Path(chosen)
        shutil.copyfile(source, target)
        return True


def install_excepthook(context: Any, parent: QWidget | None = None) -> None:
    """Orice exceptie neprinsa pe firul interfetei ajunge in dialog, nu inchide
    aplicatia."""

    def hook(kind: type[BaseException], exc: BaseException,
             tb: TracebackType | None) -> None:
        if issubclass(kind, KeyboardInterrupt):
            sys.__excepthook__(kind, exc, tb)
            return
        report = record_unexpected_error(exc.with_traceback(tb), context.paths.log_dir,
                                         app_version=getattr(context, "app_version", ""))
        ErrorDialog(report, parent).exec()

    sys.excepthook = hook
