"""Salvarea in formate, trimiterea si tiparirea (faza 6b, pasul 6b.6b).

Q-100…Q-104 (dialogul de salvare, avertismentele), Q-022 (cate un fisier pe
pagina), Q-030…Q-032 (imaginile paginilor), Q-040…Q-050 (trimiterea in PDF
Editor, in aplicatii, in clipboard, pe e-mail, la Kindle, tiparirea).

Exportul il face nucleul (`ExportService`, `app.core.export.send`); aici se
aleg optiunile din setari si din dialog. Mesajele de e-mail se scriu ca
fisiere `.eml` si se deschid cu programul de e-mail al utilizatorului:
DocuLens nu trimite nimic in retea (CLAUDE.md §6.1).

`Send to PDF Editor` (Q-040) deschide PDF-ul in PDF Editor-ul DocuLens.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRectF, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QPainter, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox

from app.core.errors import CoreError
from app.core.export import send
from app.core.export.base import (
    default_service,
    export_page_images,
    options_from_settings,
)
from app.core.model import ExportFormat, LayoutMode, PdfAVersion
from app.gui.i18n import tr, tr_error
from app.gui.progress import run_with_progress
from app.gui.save_dialog import (
    OPTIONS_TAB,
    EmailDialog,
    KindleDialog,
    SaveDialog,
    export_format,
)

PDF_FAMILY = ("pdf", "pdf_image", "pdfa", "pdfua")


def warning_text(error: CoreError) -> str:
    """Avertismentele nucleului: cu cod (Q-051) sau cu cheie de traducere (Q-104)."""
    if error.code == CoreError.code and error.message.startswith("warning."):
        return tr(error.message)
    return tr_error(error)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class DocumentActions(QObject):
    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.last_format = "pdf"
        self.last_folder: Path = Path.home()

    @property
    def project(self) -> Any:
        return self.window.project

    @property
    def pages(self) -> list[Any]:
        return list(self.project.pages)

    @property
    def name(self) -> str:
        return self.project.name or tr("save.default_name")

    def _temp(self) -> Path:
        folder = self.window.context.paths.temp_root / "send" / uuid.uuid4().hex
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    # --- intrebarile (testele le inlocuiesc) -------------------------------------------

    def ask_continue(self, warnings: list[str]) -> bool:
        answer = QMessageBox.question(self.window, tr("save.title"),
                                      "\n".join([*warnings, "", tr("save.continue")]))
        return answer == QMessageBox.StandardButton.Yes

    def ask_password(self) -> str | None:
        text, ok = QInputDialog.getText(self.window, tr("save.password_title"),
                                        tr("save.password"), QLineEdit.EchoMode.Password)
        return text if ok and text else None

    def open_file(self, path: Path) -> None:
        """Q-101, Q-046: fisierul se deschide cu aplicatia asociata (local)."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def choose_printer(self) -> QPrinter | None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self.window)
        return printer if dialog.exec() else None

    # --- salvarea (Q-100…Q-104) ---------------------------------------------------------

    def _mode(self) -> LayoutMode:
        return LayoutMode(self.window.layout_combo.currentData())

    def save_document(self, fmt_key: str | None = None, *, target: Path | None = None,
                      separate: bool = False, open_after: bool = False) -> list[Path]:
        """Fara `target` se deschide dialogul `Save document as` (Q-100)."""
        if not self.pages:
            return []
        if target is None:
            dialog = SaveDialog(self._mode(), self.name, self.last_folder,
                                fmt_key or self.last_format, self.window)
            dialog.options_requested.connect(self._format_options)
            if not dialog.exec():
                return []
            fmt_key, target = dialog.format_key, dialog.target
            separate, open_after = dialog.separate_files, dialog.open_after.isChecked()
        fmt_key = fmt_key or self.last_format
        written = self.export(fmt_key, Path(target), separate=separate)
        if written:
            self.last_format, self.last_folder = fmt_key, Path(target).parent
            self.window.show_message(tr("save.saved", n=len(written)))
            if open_after:  # Q-101
                self.open_file(written[0])
        return written

    def _format_options(self, fmt_key: str) -> None:
        """Q-102: Options pe tabul `Format Settings`, cu formatul ales."""
        from app.gui.options_dialog import FORMATS

        dialog = self.window.open_options("format", modal=False)
        keys = [k for k, _ in FORMATS]
        dialog.formats.setCurrentRow(keys.index(OPTIONS_TAB.get(fmt_key, fmt_key)))
        dialog.exec()

    def options_for(self, fmt_key: str, *, separate: bool = False) -> Any:
        settings = self.project.settings()
        fmt = export_format(fmt_key)
        base = ExportFormat.PDF if fmt_key in PDF_FAMILY else fmt
        options = options_from_settings(settings, base, layout_mode=self._mode(),
                                        separate_file_per_page=separate)
        options.metadata = {k: v for k, v in self.project.metadata.items() if v}  # J-038
        if fmt_key in PDF_FAMILY:
            options.searchable = fmt_key != "pdf_image"
            options.create_bookmarks_from_headings = bool(
                settings.get("pdf.bookmarks_from_headings"))
            options.tagged_pdf = bool(settings.get("pdf.create_tags"))
            if fmt_key == "pdfa":
                options.pdfa_version = PdfAVersion(settings.get("pdf.pdfa_version"))
        return options

    def export(self, fmt_key: str, target: Path, *, separate: bool = False) -> list[Path]:
        service = default_service()
        fmt = export_format(fmt_key)
        try:
            options = self.options_for(fmt_key, separate=separate)
            if fmt_key in ("pdf", "pdf_image", "pdfua") and \
                    self.project.settings().get("pdf.protect_with_password"):
                options.password = self.ask_password()
            warnings = [warning_text(w) for w in
                        service.check_before_export(self.pages, options, fmt)]
            if warnings and not self.ask_continue(warnings):  # Q-051, Q-104
                return []
            written = run_with_progress(
                tr("save.title"),
                lambda progress, cancel: service.export(self.pages, target, fmt, options,
                                                        progress=progress, cancel=cancel),
                self.window)
        except CoreError as exc:
            self.window.show_message(tr_error(exc))
            return []
        except (ValueError, OSError):
            self.window.show_message(tr("save.failed"))
            return []
        return list(written or [])

    # Q-030…Q-032
    def save_page_images(self, numbers: list[int], target: Path,
                         fmt: ExportFormat = ExportFormat.PNG) -> list[Path]:
        pages = [self.project.page(n) for n in numbers]
        try:
            return export_page_images(pages, target, fmt)
        except (CoreError, ValueError, OSError):
            self.window.show_message(tr("save.failed"))
            return []

    # --- trimiterea (Q-040…Q-048) ------------------------------------------------------

    def _run(self, operation: Callable[[], Path | None]) -> Path | None:
        if not self.pages:
            return None
        try:
            path = operation()
        except CoreError as exc:
            self.window.show_message(tr_error(exc))
            return None
        except ValueError:
            self.window.show_message(tr("send.invalid"))
            return None
        if path is not None:
            self.open_file(path)
        return path

    def send_to_pdf_editor(self) -> Path | None:
        """Q-040; Q-041: atasamentele, semnele de carte si comentariile nu trec."""
        path = self._run(lambda: send.send_to_pdf_editor(self.pages, self._temp(), self.name))
        if path is not None:
            self.window.show_message(tr("send.lost"))
        return path

    def send_to_application(self, fmt: ExportFormat) -> Path | None:
        """Q-046 (Word, Excel, PowerPoint), Q-048 (browser)."""
        return self._run(lambda: send.send_to_application(self.pages, self._temp(), self.name,
                                                          fmt))

    def send_to_clipboard(self) -> str:
        """Q-047: textul paginilor, separate prin rand gol."""
        text = "\n\n".join(send.text_pages(self.pages))
        QApplication.clipboard().setText(text)
        return text

    def email_document(self, fmt_key: str | None = None, split: str | None = None
                       ) -> Path | None:
        """Q-042 (`Ctrl+M`), Q-043."""
        if fmt_key is None:
            dialog = EmailDialog(parent=self.window)
            if not dialog.exec():
                return None
            fmt_key, split = dialog.format_key, dialog.split.currentData()
        options = self.options_for(fmt_key)
        return self._run(lambda: send.email_document(
            self.pages, self._temp(), self.name, export_format(fmt_key), options,
            split=split or send.ALL))

    def email_images(self, fmt: str | None = None, multipage: bool | None = None
                     ) -> Path | None:
        """Q-044 (`Ctrl+Alt+M`)."""
        if fmt is None:
            dialog = EmailDialog(images=True, parent=self.window)
            if not dialog.exec():
                return None
            fmt, multipage = dialog.format_key, dialog.multipage.isChecked()
        return self._run(lambda: send.email_images(self.pages, self._temp(), self.name,
                                                   ExportFormat(fmt),
                                                   multipage=bool(multipage)))

    def send_to_kindle(self, address: str | None = None, split: str = send.ALL,
                       name: str | None = None) -> Path | None:
        """Q-045: mesajul catre contul Kindle; il trimite utilizatorul."""
        if address is None:
            dialog = KindleDialog(self.name, self.window)
            if not dialog.exec():
                return None
            address, split = dialog.address.text(), dialog.split.currentData()
            name = dialog.name.text()
        return self._run(lambda: send.send_to_kindle(self.pages, self._temp(),
                                                     name or self.name, address, split=split))

    # --- tiparirea (Q-049, Q-050) -------------------------------------------------------

    def print_text(self, printer: QPrinter | None = None) -> bool:
        """Q-049 (`Ctrl+P`): textul recunoscut, fiecare pagina pe foaia ei."""
        printer = printer or self.choose_printer()
        if printer is None or not self.pages:
            return False
        self.text_document().print_(printer)
        return True

    def text_document(self) -> QTextDocument:
        """Documentul tiparit de `Print text`: o pagina de text pe foaie."""
        doc = QTextDocument()
        parts = []
        for n, text in enumerate(send.text_pages(self.pages)):
            style = ' style="page-break-before: always"' if n else ""  # fara foaie goala
            parts.append(f"<div{style}>{_escape(text).replace(chr(10), '<br>')}</div>")
        doc.setHtml("".join(parts))
        return doc

    def print_images(self, printer: QPrinter | None = None) -> bool:
        """Q-050 (`Ctrl+Alt+P`): imaginile paginilor, cate una pe foaie."""
        printer = printer or self.choose_printer()
        if printer is None or not self.pages:
            return False
        painter = QPainter()
        if not painter.begin(printer):
            return False
        try:
            for n, path in enumerate(send.image_pages(self.pages)):
                if n:
                    printer.newPage()
                image = QImage(str(path))
                size = image.size().scaled(painter.viewport().size(),
                                           Qt.AspectRatioMode.KeepAspectRatio)
                painter.drawImage(QRectF(0, 0, size.width(), size.height()), image)
        finally:
            painter.end()
        return True
