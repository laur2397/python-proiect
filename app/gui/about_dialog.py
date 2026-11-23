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
        self.license_button = QPushButton(tr("about.license_info"))  # X-047
        self.license_button.setObjectName("about_license_info")
        self.license_button.clicked.connect(lambda: self.show_license_info())
        layout.addWidget(self.license_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def show_system_info(self) -> SystemInfoDialog:
        dialog = SystemInfoDialog(self.context, self)
        self.system_info = dialog
        dialog.open()
        return dialog

    def show_license_info(self) -> QDialog:
        """X-047: `Help > About > License Info`: lista completa a limbilor OCR, pe
        categorii (X-044), cu asterisc la cele cu dictionar (X-045)."""
        dialog = LicenseInfoDialog(self)
        self.license_info = dialog
        dialog.open()
        return dialog


class LicenseInfoDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        from PySide6.QtWidgets import QPlainTextEdit

        from app.core.ocr import languages
        from app.gui.options_dialog import language_name

        super().__init__(parent)
        self.setObjectName("license_info_dialog")
        self.setWindowTitle(tr("about.license_info"))
        registry = languages.LanguageRegistry()
        lines: list[str] = []
        for category in (languages.NATURAL, languages.ARTIFICIAL, languages.FORMAL):
            codes = registry.by_category(category)
            lines.append(tr(f"about.languages.{category}", n=len(codes)))
            for code in codes:
                star = "*" if registry.has_dictionary(code) else ""
                lines.append(f"    {language_name(code)}{star}")
        lines.append("")
        lines.append(tr("about.languages.total", n=len(registry.all())))
        lines.append(tr("about.languages.dictionary_note"))
        self.text = QPlainTextEdit("\n".join(lines))
        self.text.setObjectName("license_languages")
        self.text.setReadOnly(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.text, 1)
        layout.addWidget(buttons)
        self.resize(420, 520)
