"""`Help > About` (faza 16, Y-014, Y-015): numele, versiunea, numarul de build;
`System Info...` cu raportul de sistem si `Save...` (raportul pentru suport)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.context import APP_VERSION
from app.core.sysinfo import build_number, system_info, write_report
from app.gui.i18n import tr


def _labels(context: Any) -> dict[str, str]:
    return {key: tr(f"sysinfo.{key}") for key, _value in system_info(context)}


class SystemInfoDialog(QDialog):
    """Y-014: raportul, copiabil, cu `Save...`."""

    def __init__(self, context: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("system_info")
        self.setWindowTitle(tr("sysinfo.title"))
        self.context = context
        layout = QVBoxLayout(self)
        labels = _labels(context)
        self.text = QPlainTextEdit("\n".join(
            f"{labels[key]}: {value}" for key, value in system_info(context)))
        self.text.setObjectName("system_info_text")
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        self.save_button = QPushButton(tr("sysinfo.save"))
        self.save_button.setObjectName("system_info_save")
        self.save_button.clicked.connect(lambda: self.save())
        layout.addWidget(self.save_button)
        self.resize(640, 420)

    def pick_target(self) -> Path | None:
        chosen, _ = QFileDialog.getSaveFileName(self, tr("sysinfo.save"), "DocuLens-system.txt",
                                                tr("sysinfo.filter"))
        return Path(chosen) if chosen else None

    def save(self, target: Path | None = None) -> Path | None:
        target = target or self.pick_target()
        if target is None:
            return None
        return write_report(self.context, target, _labels(self.context))


class AboutDialog(QDialog):
    """Y-015: versiunea si numarul de build."""

    def __init__(self, context: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("about_dialog")
        self.setWindowTitle(tr("about.title"))
        self.context = context
        layout = QVBoxLayout(self)
        title = QLabel(f"<h2>{tr('app.name')}</h2>")
        layout.addWidget(title)
        self.version = QLabel(tr("about.version", version=APP_VERSION, build=build_number()))
        self.version.setObjectName("about_version")
        layout.addWidget(self.version)
        notice = QLabel(tr("about.notice"))
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.info_button = QPushButton(tr("about.system_info"))
        self.info_button.setObjectName("about_system_info")
        self.info_button.clicked.connect(lambda: self.show_system_info())
        layout.addWidget(self.info_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def show_system_info(self) -> SystemInfoDialog:
        dialog = SystemInfoDialog(self.context, self)
        self.system_info = dialog
        dialog.open()
        return dialog
