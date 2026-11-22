"""Legatura dintre Lansator, conversie si OCR Editor (faza 6c, pasul 6c.4).

Ecranul de pornire dupa `general.startup_screen` (A-001, X-001): Lansatorul,
OCR Editor cu proiect nou sau cu ultimul proiect (din documentele recente;
daca lipseste, proiect nou si o nota in jurnal). Din OCR Editor, `New Task`
(`Ctrl+N`) aduce Lansatorul, iar fereastra curenta ramane deschisa (A-002).
Cererile Lansatorului ajung aici: OCR Editor cu fisierele alese (A-012), un
proiect recent (A-102), conversia (A-013…A-016) si PDF-urile (A-010).

PDF-urile se deschid in PDF Editor (A-010, A-011, faza 7); OCR Editor si PDF
Editor isi trimit documentele unul altuia (I-017, I-019).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QDesktopServices

from app.core.applog import get_logger
from app.core.recent import RecentDocuments
from app.gui.convert_screen import ConvertScreen
from app.gui.launcher import Launcher
from app.gui.main_window import MainWindow

_log = get_logger("gui.application")


class Application(QObject):
    def __init__(self, context: Any) -> None:
        super().__init__()
        self.context = context
        self.recent = RecentDocuments(context.app_db)
        self._launcher: Launcher | None = None
        self._editor: MainWindow | None = None
        self._pdf_editor: Any = None
        self.ocr_engine: Any = None
        """Motorul OCR pentru editor si conversie; None = Tesseract."""
        self.scanner_service: Any = None
        """Serviciul de scanare; None = WIA."""

    # --- ferestrele ------------------------------------------------------------------

    @property
    def launcher(self) -> Launcher:
        if self._launcher is None:
            launcher = Launcher(self.context)
            launcher.ocr_editor_requested.connect(self.open_in_ocr_editor)
            launcher.project_requested.connect(self.open_project)
            launcher.pdf_requested.connect(self.open_pdf)
            launcher.convert_requested.connect(self.convert)
            launcher.options_requested.connect(self.open_options)
            launcher.options_tab_requested.connect(self.open_options)
            launcher.scan_requested.connect(self.scan)
            self._launcher = launcher
        return self._launcher

    @property
    def editor(self) -> MainWindow:
        if self._editor is None:
            editor = MainWindow(self.context)
            editor.ocr_engine = self.ocr_engine
            editor.scanner_service = self.scanner_service
            editor.launcher_requested.connect(self.show_launcher)  # A-002
            editor.pdf_editor_requested.connect(self.open_pdf)  # I-019
            self._editor = editor
        return self._editor

    @property
    def pdf_editor(self) -> Any:
        """Fereastra PDF Editor (faza 7), creata la prima nevoie."""
        if self._pdf_editor is None:
            from app.gui.pdf_editor import PdfEditorWindow

            window = PdfEditorWindow(self.context)
            window.launcher_requested.connect(self.show_launcher)
            window.options_requested.connect(lambda tab: self.open_options(tab or "general"))
            window.ocr_editor_requested.connect(self.open_in_ocr_editor)  # I-017
            self._pdf_editor = window
        return self._pdf_editor

    def windows(self) -> list[Any]:
        return [w for w in (self._launcher, self._editor, self._pdf_editor) if w is not None]

    # --- pornirea (A-001) -------------------------------------------------------------

    def start(self) -> Any:
        """Fereastra aratata la pornire, dupa `general.startup_screen`."""
        screen = self.context.settings.get("general.startup_screen")
        if screen == "ocr_new_project":
            return self.show_editor()
        if screen == "ocr_last_project":
            last = self.recent.last("ocr_project")
            if last is not None and last.exists and self.open_project(last.path):
                return self.editor
            _log.info("ultimul proiect OCR lipseste (%s); se deschide un proiect nou",
                      last.path if last else "-")
            return self.show_editor()
        return self.show_launcher()

    def show_launcher(self) -> Launcher:
        launcher = self.launcher
        launcher.show_home()
        launcher.show_task("open")
        launcher.show()
        launcher.raise_()
        return launcher

    def show_editor(self) -> MainWindow:
        editor = self.editor
        editor.show()
        editor.raise_()
        return editor

    # --- cererile Lansatorului ----------------------------------------------------------

    def open_in_ocr_editor(self, files: list[Path]) -> MainWindow:
        """A-012: OCR Editor cu proiect nou; fisierele nesuportate se raporteaza."""
        editor = self.show_editor()
        if editor.project.pages and not editor.new_project():
            return editor
        if files:
            editor.open_images(list(files))
        return editor

    def open_project(self, path: Path) -> bool:
        """A-102: un proiect OCR din documentele recente."""
        return self.show_editor().open_project(Path(path))

    def open_pdf(self, path: Path) -> Any:
        """A-010, A-011: PDF-ul se deschide in PDF Editor, intr-un tab nou."""
        path = Path(path)
        self.recent.add(path, "pdf")
        window = self.pdf_editor
        window.show()
        window.raise_()
        window.open_path(path)
        return window

    def open_external(self, path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def convert(self, key: str, files: list[Path]) -> ConvertScreen:
        """A-013…A-016: ecranul de conversie, peste Lansator (A-305)."""
        screen = ConvertScreen(self.context, key, list(files))
        screen.engine = self.ocr_engine
        screen.back_requested.connect(self.launcher.show_home)
        screen.ocr_editor_requested.connect(self.open_in_ocr_editor)  # A-017
        screen.options_requested.connect(self.open_options)
        self.launcher.show_screen(screen)
        self.launcher.show()
        return screen

    # --- scanarea din Lansator (A-080…A-090) ---------------------------------------------

    def scanner(self) -> Any:
        from app.core.images.wia import default_scanner

        if self.scanner_service is None:
            self.scanner_service = default_scanner()
        return self.scanner_service

    def acquire(self, key: str) -> list[Path]:
        """A-081, A-082: dispozitivul, previzualizarea, setarile, `Scan`, apoi
        `Scan Again` sau `Finish Scanning`. Intoarce imaginile scanate."""
        from app.gui.scan_dialog import ScanDialog

        dialog = ScanDialog(self.context, self.scanner(), auto_process=key == "ocr_editor",
                            parent=self._launcher)
        self.scan_dialog = dialog
        dialog.exec()
        return list(dialog.images)

    def scan(self, key: str, images: list[Path] | None = None) -> Any:
        """A-080: dupa scanare, paginile merg in OCR Editor (A-083, A-084), in
        ecranul de conversie (A-085, A-086, A-089) sau devin imagini (A-087)."""
        images = list(images) if images is not None else self.acquire(key)
        if not images:
            return None
        if key == "ocr_editor":  # A-083
            return self.open_in_ocr_editor(images)
        if key == "pdf":  # A-084: rezultatul se deschide in OCR Editor, apoi salvarea
            editor = self.open_in_ocr_editor(images)
            if self.context.settings.get("image.auto_mode") != "recognize" or \
                    not self.context.settings.get("image.auto_process"):
                editor.recognize()
            editor.documents.save_document("pdf")
            return editor
        if key == "images":  # A-087, A-088
            return self.save_scanned_images(images)
        return self.convert(key, images)  # A-085, A-086, A-089

    def save_scanned_images(self, images: list[Path],
                            choice: dict[str, Any] | None = None,
                            folder: Path | None = None) -> list[Path]:
        from PySide6.QtWidgets import QFileDialog

        from app.core.convert import save_images
        from app.core.model import ExportFormat
        from app.gui.scan_dialog import ImageFilesDialog

        if choice is None:
            dialog = ImageFilesDialog(self._launcher)
            if not dialog.exec():
                return []
            choice = dialog.choice()
        if folder is None:
            chosen = QFileDialog.getExistingDirectory(self._launcher, "")
            if not chosen:
                return []
            folder = Path(chosen)
        return save_images(images, folder, "scan", ExportFormat(choice["format"]),
                           compression=choice["compression"], multipage=choice["multipage"],
                           context=self.context)

    def open_options(self, tab: str = "general", fmt: str = "") -> Any:
        """A-004, A-005: aceleasi setari ca in OCR Editor."""
        from app.gui.options_dialog import FORMATS, OptionsDialog

        project = self._editor.project if self._editor is not None else None
        dialog = OptionsDialog(self.context, project, tab=tab or "general",
                               parent=self._launcher)
        keys = [k for k, _ in FORMATS]
        if fmt in keys:
            dialog.formats.setCurrentRow(keys.index(fmt))
        self.options_dialog = dialog
        dialog.open()
        return dialog
