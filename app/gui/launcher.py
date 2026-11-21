"""Lansatorul (faza 6c, pasul 6c.2): A-001…A-007, A-010…A-016, A-100…A-111,
A-300…A-303.

Sarcinile din stanga (A-003, A-300), butonul `Options` stanga-jos (A-005),
`F1` cu manualul local (A-006), scenariile la hover (A-007, ca tooltip);
tabul `Open` cu grupurile `Open and Edit` si `Convert to` (A-301, A-302);
tabul `Compare` (A-303); tabul `Recent` cu cautare, stergere si golire
(A-102…A-105, A-111); tabul `Mobile application` peste un folder local
(A-106…A-110, faza_6c_pasi.md decizia 3).

Lansatorul nu face el munca: emite cererile (deschide in OCR Editor, converteste,
deschide un proiect sau un PDF) si aplicatia le duce la capat (6c.4).

INCOMPLET, marcat: tabul `Scan` vine cu modulul de scanare (faza 6d); `Compare`
deschide modulul din faza 12; `PDF Document` deschide PDF-ul cu aplicatia
sistemului pana la PDF Editor-ul din faza 7.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.recent import RecentDocument, RecentDocuments
from app.gui.i18n import tr

TASKS = ("open", "scan", "compare", "recent", "mobile")
"""A-003: cele cinci sarcini, in ordine."""

OPEN_CARDS = ("pdf_document", "ocr_editor")
CONVERT_CARDS = ("pdf", "docx", "xlsx", "other")
"""A-301: `Open and Edit` (doua carduri mari) si `Convert to` (patru carduri)."""

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".webp"}

MANUAL = Path(__file__).resolve().parents[2] / "docs" / "manual" / "index.html"
"""A-006: manualul local."""

CARD_STYLE = """
QToolButton[card="true"] { background: palette(base); border: 1px solid palette(mid);
                           border-radius: 8px; padding: 12px; }
QToolButton[card="true"]:hover { border: 2px solid palette(highlight); }
"""
"""A-302: carduri cu colturi rotunjite, chenar la hover (culorile sistemului)."""

TASK_STYLE = """
QListWidget#launcher_tasks::item:selected { background: palette(alternate-base);
    color: palette(text); border-left: 4px solid palette(highlight); }
"""
"""A-300: sarcina aleasa, cu fundal si bara verticala in stanga."""


class Launcher(QMainWindow):
    ocr_editor_requested = Signal(object)
    """Lista de fisiere de deschis in OCR Editor (A-012)."""
    convert_requested = Signal(str, object)
    """Cardul `Convert to` (A-013…A-016) si fisierele alese."""
    project_requested = Signal(object)
    """Un proiect OCR din `Recent` (A-102)."""
    pdf_requested = Signal(object)
    """Un PDF de deschis (A-010)."""
    options_requested = Signal()

    def __init__(self, context: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("launcher")
        self.setWindowTitle(tr("launcher.title"))
        self.context = context
        self.recent = RecentDocuments(context.app_db)
        self.setStyleSheet(CARD_STYLE + TASK_STYLE)
        self.tasks = QListWidget()  # A-003, A-300
        self.tasks.setObjectName("launcher_tasks")
        self.tasks.setFixedWidth(190)
        for key in TASKS:
            item = QListWidgetItem(tr(f"launcher.task.{key}"))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(tr(f"launcher.scenarios.{key}"))  # A-007
            self.tasks.addItem(item)
        self.options_button = QPushButton(tr("action.options"))  # A-005: stanga-jos
        self.options_button.setObjectName("launcher_options")
        self.options_button.clicked.connect(self.options_requested.emit)
        left = QVBoxLayout()
        left.addWidget(self.tasks, 1)
        left.addWidget(self.options_button)
        self.cards: dict[str, QToolButton] = {}
        self.pages = QStackedWidget()
        for key in TASKS:
            page = getattr(self, f"_page_{key}")()
            page.setObjectName(f"launcher_{key}")
            self.pages.addWidget(page)
        self.tasks.currentRowChanged.connect(self._task_changed)
        body = QWidget()
        layout = QHBoxLayout(body)
        layout.addLayout(left)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(body)
        for shortcut, slot in ((QKeySequence(Qt.Key.Key_F1), self.show_help),  # A-006
                               (QKeySequence("Ctrl+R"), self.open_in_ocr_editor)):  # A-012
            action = QAction(self)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda _=False, f=slot: f())
            self.addAction(action)
        self.resize(980, 640)
        self.show_task("open")  # A-001: tabul `Open` activ

    # --- sarcinile --------------------------------------------------------------------

    def show_task(self, key: str) -> None:
        self.tasks.setCurrentRow(TASKS.index(key))

    @property
    def current_task(self) -> str:
        return TASKS[self.tasks.currentRow()]

    def _task_changed(self, row: int) -> None:
        self.pages.setCurrentIndex(row)
        if TASKS[row] == "recent":
            self.refresh_recent()
        if TASKS[row] == "mobile":
            self.refresh_mobile()

    def _card(self, key: str, *, large: bool = False) -> QToolButton:
        card = QToolButton()
        card.setObjectName(f"card_{key}")
        card.setProperty("card", True)
        text = tr(f"launcher.card.{key}")
        card.setText(f"{text}\n{tr(f'launcher.card.{key}.hint')}" if large else text)
        card.setMinimumSize(QSize(300, 90) if large else QSize(140, 110))
        self.cards[key] = card
        return card

    @staticmethod
    def _section(layout: QVBoxLayout, key: str) -> None:
        title = QLabel(tr(f"launcher.section.{key}"))
        title.setObjectName(f"section_{key}")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

    # --- Open (A-301) ------------------------------------------------------------------

    def _page_open(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._section(layout, "open_and_edit")
        row = QHBoxLayout()
        for key in OPEN_CARDS:
            row.addWidget(self._card(key, large=True))
        row.addStretch(1)
        layout.addLayout(row)
        self._section(layout, "convert_to")
        grid = QHBoxLayout()
        for key in CONVERT_CARDS:
            self._card(key).clicked.connect(lambda _=False, k=key: self.convert(k))
            grid.addWidget(self.cards[key])
        grid.addStretch(1)
        layout.addLayout(grid)
        layout.addStretch(1)
        self.cards["ocr_editor"].clicked.connect(lambda: self.open_in_ocr_editor())
        self.cards["pdf_document"].clicked.connect(lambda: self.open_pdf())
        return page

    def pick_files(self, title_key: str) -> list[Path]:
        """A-304: dialogul de alegere, filtrul `All supported formats`."""
        files, _ = QFileDialog.getOpenFileNames(self, tr(title_key), "",
                                                tr("launcher.filter"))
        return [Path(f) for f in files]

    def open_in_ocr_editor(self, files: list[Path] | None = None) -> None:
        """A-012: OCR Editor cu proiect nou si fisierele alese."""
        if files is None:
            files = self.pick_files("launcher.pick.ocr_editor")
            if not files:
                return
        self.ocr_editor_requested.emit(list(files))

    def convert(self, key: str, files: list[Path] | None = None) -> None:
        """A-013…A-016: fisierele alese merg la ecranul de conversie (6c.3)."""
        if files is None:
            files = self.pick_files(f"launcher.pick.convert_{key}")
            if not files:
                return
        self.convert_requested.emit(key, list(files))

    def open_pdf(self, path: Path | None = None) -> None:
        """A-010. INCOMPLET: PDF Editor-ul vine in faza 7."""
        if path is None:
            chosen, _ = QFileDialog.getOpenFileName(self, tr("launcher.pick.pdf"), "",
                                                    "PDF (*.pdf)")
            if not chosen:
                return
            path = Path(chosen)
        self.pdf_requested.emit(Path(path))

    # --- Scan, Compare (A-303) ------------------------------------------------------------

    def _page_scan(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(tr("launcher.scan.pending"))  # INCOMPLET: faza 6d
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _page_compare(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._section(layout, "compare")
        card = self._card("compare", large=True)
        card.setEnabled(False)  # INCOMPLET: modulul de comparare, faza 12
        card.setToolTip(tr("launcher.compare.pending"))
        layout.addWidget(card)
        self._section(layout, "recent_comparisons")
        self.comparisons = QListWidget()  # A-101
        self.comparisons.setObjectName("recent_comparisons")
        for left, right in self.context.app_db.execute(
                "SELECT path_left, path_right FROM recent_comparison"
                " ORDER BY compared_at DESC").fetchall():
            self.comparisons.addItem(f"{Path(left).name}  ↔  {Path(right).name}")
        layout.addWidget(self.comparisons, 1)
        return page

    # --- Recent (A-102…A-105, A-111) -----------------------------------------------------

    def _page_recent(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.recent_search = QLineEdit()  # A-103
        self.recent_search.setObjectName("recent_search")
        self.recent_search.setPlaceholderText(tr("launcher.recent.search"))
        self.recent_search.textChanged.connect(lambda _: self.refresh_recent())
        find = QAction(self)
        find.setShortcut("Ctrl+F")
        find.triggered.connect(self.focus_search)
        self.addAction(find)
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("recent_list")
        self.recent_list.itemActivated.connect(
            lambda item: self.open_recent(item.data(Qt.ItemDataRole.UserRole)))
        self.recent_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.recent_list.customContextMenuRequested.connect(self._recent_menu)
        self.recent_empty = QWidget()  # A-111
        self.recent_empty.setObjectName("recent_empty")
        empty = QVBoxLayout(self.recent_empty)
        empty.addWidget(QLabel(tr("launcher.recent.empty")))
        open_button = QPushButton(tr("action.open"))
        open_button.setObjectName("recent_open")
        open_button.clicked.connect(lambda: self.open_in_ocr_editor())
        empty.addWidget(open_button)
        empty.addStretch(1)
        layout.addWidget(self.recent_search)
        layout.addWidget(self.recent_list, 1)
        layout.addWidget(self.recent_empty, 1)
        return page

    def focus_search(self) -> None:
        self.show_task("recent")
        self.recent_search.setFocus()

    def refresh_recent(self) -> None:
        docs = self.recent.list(query=self.recent_search.text())
        self.recent_list.clear()
        for doc in docs:
            label = doc.display_name if doc.exists else tr("launcher.recent.missing",
                                                           name=doc.display_name)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, doc)
            item.setToolTip(str(doc.path))
            if not doc.exists:  # A-102: fisierul mutat se marcheaza
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
            self.recent_list.addItem(item)
        nothing = not docs and not self.recent_search.text()
        self.recent_list.setVisible(not nothing)
        self.recent_empty.setVisible(nothing)

    def open_recent(self, doc: RecentDocument) -> None:
        """A-102: in modulul potrivit; fisierul mutat → mesaj si cautare."""
        if not doc.exists:
            self.locate_missing(doc)
            return
        if doc.kind == "ocr_project":
            self.project_requested.emit(doc.path)
        elif doc.kind == "pdf":
            self.pdf_requested.emit(doc.path)
        else:
            self.ocr_editor_requested.emit([doc.path])

    def pick_moved_file(self, doc: RecentDocument) -> Path | None:
        QMessageBox.information(self, tr("launcher.title"),
                                tr("launcher.recent.moved", path=str(doc.path)))
        chosen, _ = QFileDialog.getOpenFileName(self, tr("launcher.recent.locate"))
        return Path(chosen) if chosen else None

    def locate_missing(self, doc: RecentDocument) -> None:
        found = self.pick_moved_file(doc)
        if found is not None:
            self.recent.remove(doc.path)
            self.recent.add(found, doc.kind, display_name=found.name)
            self.refresh_recent()

    def _recent_menu(self, point: Any) -> None:
        item = self.recent_list.itemAt(point)
        menu = QMenu(self)
        if item is not None:
            menu.addAction(tr("launcher.recent.remove")).triggered.connect(
                lambda: self.remove_recent(item.data(Qt.ItemDataRole.UserRole)))
        menu.addAction(tr("launcher.recent.clear")).triggered.connect(self.clear_recent)
        menu.exec(self.recent_list.viewport().mapToGlobal(point))

    def remove_recent(self, doc: RecentDocument) -> None:
        """A-104: fisierul nu se atinge."""
        self.recent.remove(doc.path)
        self.refresh_recent()

    def confirm_clear(self) -> bool:
        answer = QMessageBox.question(self, tr("launcher.title"),
                                      tr("launcher.recent.confirm_clear"))
        return answer == QMessageBox.StandardButton.Yes

    def clear_recent(self) -> bool:
        """A-105: cu confirmare."""
        if not self.confirm_clear():
            return False
        self.recent.clear()
        self.refresh_recent()
        return True

    # --- Mobile application (A-106…A-110) -------------------------------------------------

    def _page_mobile(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(tr("launcher.mobile.requirements"))  # A-106
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.mobile_folder = QLabel()
        self.mobile_folder.setObjectName("mobile_folder")
        choose = QPushButton(tr("launcher.mobile.select_folder"))  # A-107
        choose.setObjectName("mobile_select")
        choose.clicked.connect(lambda: self.select_mobile_folder())
        row.addWidget(self.mobile_folder, 1)
        row.addWidget(choose)
        layout.addLayout(row)
        self.mobile_list = QListWidget()
        self.mobile_list.setObjectName("mobile_list")
        self.mobile_list.itemActivated.connect(
            lambda item: self.open_mobile(item.data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.mobile_list, 1)
        return page

    def select_mobile_folder(self, folder: Path | None = None) -> None:
        if folder is None:
            chosen = QFileDialog.getExistingDirectory(self,
                                                      tr("launcher.mobile.select_folder"))
            if not chosen:
                return
            folder = Path(chosen)
        self.context.settings.set("launcher.mobile_folder", str(folder))
        self.refresh_mobile()

    def mobile_items(self) -> list[Path]:
        """A-108: dupa data crearii, cel mai nou primul."""
        value = self.context.settings.get("launcher.mobile_folder")
        folder = Path(value) if value else None
        if folder is None or not folder.is_dir():
            return []
        items = [p for p in folder.iterdir() if not p.name.startswith(".")]
        return sorted(items, key=lambda p: p.stat().st_ctime, reverse=True)

    def refresh_mobile(self) -> None:
        value = self.context.settings.get("launcher.mobile_folder")
        if value and not Path(value).is_dir():  # A-107: folder sters → se cere din nou
            self.context.settings.set("launcher.mobile_folder", None)
            value = None
        self.mobile_folder.setText(str(value) if value else tr("launcher.mobile.no_folder"))
        self.mobile_list.clear()
        for path in self.mobile_items():
            stamp = datetime.fromtimestamp(path.stat().st_ctime, UTC).strftime("%Y-%m-%d")
            item = QListWidgetItem(f"{path.name}  ({stamp})")
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.mobile_list.addItem(item)

    def open_mobile(self, path: Path) -> None:
        """A-109: PDF → editor; folder de imagini → PDF din imagini; altceva → PDF."""
        if path.is_dir():
            images = sorted(p for p in path.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
            if images:
                self.convert_requested.emit("pdf", images)
        elif path.suffix.lower() == ".pdf":
            self.pdf_requested.emit(path)
        else:
            self.convert_requested.emit("pdf", [path])

    # --- ajutorul (A-006) -------------------------------------------------------------

    def show_help(self) -> bool:
        if MANUAL.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(MANUAL)))
            return True
        QMessageBox.information(self, tr("launcher.title"),
                                tr("launcher.help_missing", path=str(MANUAL)))
        return False
