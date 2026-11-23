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
        self._compare: Any = None
        self._hot_folder: Any = None
        self._tasks: Any = None
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
            launcher.compare_requested.connect(self.open_compare)  # R-001
            launcher.automated_tasks_requested.connect(self.open_automated_tasks)  # T-019
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
            editor.compare_requested.connect(lambda path: self.open_compare(path, None))
            editor.automated_tasks_requested.connect(self.open_automated_tasks)  # T-001
            editor.hot_folder_requested.connect(self.open_hot_folder)  # S-002
            editor.task_run_requested.connect(self.run_automated_task)  # T-020
            self._editor = editor
            self._apply_task_shortcuts()
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
            window.compare_requested.connect(lambda path: self.open_compare(path, None))
            self._pdf_editor = window
        return self._pdf_editor

    @property
    def compare_window(self) -> Any:
        """Modulul `Compare Documents` (faza 12), creat la prima nevoie."""
        if self._compare is None:
            from app.gui.compare_window import CompareWindow

            window = CompareWindow(self.context)
            window.engine = self.ocr_engine
            self._compare = window
        return self._compare

    def open_compare(self, left: Path | None = None, right: Path | None = None) -> Any:
        """R-001: din Lansator, din PDF Editor (`Compare`) sau din OCR Editor
        (`Tools > Compare Documents`); perechea data se incarca."""
        window = self.compare_window
        window.show()
        window.raise_()
        window.open_pair(left, right)
        if self._launcher is not None:
            self._launcher.refresh_comparisons()
        return window

    # --- automatizarea (faza 13) ----------------------------------------------------------

    @property
    def task_runner(self) -> Any:
        from app.core.automation.tasks import AutomatedTaskRunner

        if self._tasks is None:
            self._tasks = AutomatedTaskRunner(self.context, engine=self.ocr_engine)
        return self._tasks

    def open_automated_tasks(self) -> Any:
        """T-001: `Tools > Automated Tasks` si cardul din Lansator (T-019)."""
        from app.gui.tasks_window import TasksManager

        manager = TasksManager(self.task_runner, parent=self._editor or self._launcher)
        manager.run_requested.connect(self.run_automated_task)
        manager.finished.connect(lambda *_: self._apply_task_shortcuts())
        self.tasks_manager = manager
        manager.open()
        return manager

    def _apply_task_shortcuts(self) -> None:
        """T-020: scurtaturile sarcinilor in OCR Editor."""
        if self._editor is not None:
            self._editor.set_task_shortcuts({t.shortcut: t.name
                                             for t in self.task_runner.all_tasks()
                                             if t.shortcut})

    def task_inputs(self, task: Any) -> list[Path] | None:
        """T-007: fisierele alese sau paginile scanate; None = renuntare."""
        from PySide6.QtWidgets import QFileDialog

        from app.gui.i18n import tr

        source = task.steps[0].parameters.get("source", "files")
        if source == "scan":
            return self.acquire("task") or None
        files, _ = QFileDialog.getOpenFileNames(self._editor or self._launcher,
                                                tr("tasks.pick_files"), "",
                                                tr("launcher.filter"))
        return [Path(f) for f in files] or None

    def run_automated_task(self, name: str, inputs: list[Path] | None = None) -> Any:
        """T-019: fisierele (sau scanerul), progresul, apoi rezultatul. Pasii
        `send_to` se dau mai departe aici (decizia 7)."""
        from PySide6.QtWidgets import QMessageBox

        from app.gui.i18n import tr
        from app.gui.progress import run_with_progress
        from app.gui.tasks_window import task_title

        runner = self.task_runner
        task = runner.task(name)
        mode = task.steps[0].parameters.get("project", "new")
        project = self._editor.project if self._editor is not None else None
        if inputs is None:
            inputs = self.task_inputs(task)
            if inputs is None:
                return None
        parent = self._editor or self._launcher
        from app.core.errors import CoreError
        from app.gui.i18n import tr_error

        try:
            result = run_with_progress(
                task_title(task),
                lambda progress, cancel: runner.run(
                    task, inputs, progress=progress, cancel=cancel,
                    project=project if mode == "current" else None,
                    wait_for_areas=self._wait_for_areas if mode == "current" else None),
                parent)
        except CoreError as exc:
            reason = exc.params.get("reason")
            self.last_task_message = tr(f"tasks.error.{reason}", n=1) if reason \
                else tr_error(exc)
            if not getattr(self, "quiet", False):
                QMessageBox.warning(parent, task_title(task), self.last_task_message)
            return None
        if result is None:
            return None
        if mode == "current" and self._editor is not None:
            self._editor.refresh()
        self._send(runner.last_run.sent)
        errors = [(p, e) for p, _o, e in result if e is not None]
        outputs = runner.last_run.outputs
        text = tr("tasks.run_done", count=len(outputs),
                  files="\n".join(str(p) for p in outputs))
        if errors:
            text += "\n\n" + tr("tasks.run_errors") + "\n" + "\n".join(
                f"{p.name}: {tr_error(e)}" for p, e in errors)
        self.last_task_message = text
        if not getattr(self, "quiet", False):
            QMessageBox.information(parent, task_title(task), text)
        return result

    def _wait_for_areas(self, project: Any) -> None:
        """T-106: sarcina se opreste pana cand utilizatorul deseneaza zonele in OCR
        Editor si confirma."""
        from PySide6.QtWidgets import QMessageBox

        from app.gui.i18n import tr

        if self._editor is not None:
            self._editor.refresh()
            self._editor.show()
        QMessageBox.information(self._editor, tr("tasks.title"), tr("tasks.draw_areas"))

    def _send(self, sent: list[tuple[str, str | None, list[Path]]]) -> None:
        """T-012, T-013, T-015: aplicatia aleasa primeste documentul; pentru e-mail se
        deschid clientul de e-mail si folderul cu fisierele (decizia 7)."""
        from PySide6.QtCore import QProcess

        for kind, app, files in sent:
            if not files:
                continue
            if kind == "app" and app:
                QProcess.startDetached(app, [str(f) for f in files])
            else:
                QDesktopServices.openUrl(QUrl("mailto:"))
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(files[0].parent)))

    @property
    def hot_folder(self) -> Any:
        """S-002: fereastra Hot Folder, creata la prima nevoie."""
        if self._hot_folder is None:
            from app.gui.hotfolder_window import HotFolderWindow

            window = HotFolderWindow(self.context, engine=self.ocr_engine)
            window.options_requested.connect(lambda tab: self.open_options(tab))
            self._hot_folder = window
        return self._hot_folder

    def open_hot_folder(self) -> Any:
        """S-002: `Tools > Hot Folder` (`Ctrl+Shift+F`)."""
        window = self.hot_folder
        window.refresh()
        window.show_window()
        return window

    def start_hot_folder(self) -> Any:
        """S-002, S-071: la pornirea aplicatiei, daca exista sarcini si pornirea
        automata e permisa, ceasul Hot Folder porneste ascuns (iconul din bara de
        sistem)."""
        if not self.context.settings.get("hotfolder.autostart"):
            return None
        count = self.context.app_db.execute("SELECT COUNT(*) FROM hot_folder_task").fetchone()[0]
        return self.hot_folder if count else None

    def windows(self) -> list[Any]:
        return [w for w in (self._launcher, self._editor, self._pdf_editor, self._compare,
                            self._hot_folder) if w is not None]

    # --- pornirea (A-001) -------------------------------------------------------------

    def start(self) -> Any:
        """Fereastra aratata la pornire, dupa `general.startup_screen`."""
        self.start_hot_folder()
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
        screen.dossier_created.connect(  # E-500: dosarul PDF se deschide in PDF Editor
            lambda path: self.open_pdf(path) if Path(path).suffix.lower() == ".pdf" else None)
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
