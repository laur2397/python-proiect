"""Fereastra de comparare (faza 12, pasul 12.4): R-001…R-068, R-300, R-400…R-416.

Doua zone de afisare cu documentele (R-040), panoul din dreapta cu tabul
`Compare` si tabul `Differences (N)` (R-404, R-405), banda rosie cu numarul de
diferente (R-407), evidentierea in documente (R-413), navigarea si derularea
sincronizata (R-045, R-046), ignorarea (R-048…R-050) si salvarea (R-060…R-065).
Regulile sunt in nucleu (`app/core/compare`); aici e numai interfata.
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.applog import get_logger
from app.core.errors import CoreError
from app.core.model import CompareOptions, Difference, DiffType
from app.gui.i18n import tr, tr_error
from app.gui.pdf_view import FitMode, PdfView

_log = get_logger("gui.compare")

PANEL_WIDTH = 170
"""R-404: latimea panoului din dreapta."""
DIFF_FILL = QColor(200, 170, 240, 90)
"""R-413: diferentele, in mov deschis."""
CURRENT_LINE = QColor(220, 30, 30)
"""R-413: diferenta curenta, subliniata rosu."""
ADDED_BORDER = QColor(40, 110, 230)
"""R-413: textul adaugat are chenar albastru."""
ICON_COLORS = {DiffType.INSERTED: "#2e9d4f", DiffType.DELETED: "#d93636",
               DiffType.REPLACED: "#7a4bc4", DiffType.FORMATTING: "#7a4bc4"}
"""R-410: sageata verde la adaugare, rosie la stergere."""
SHORTCUTS = {
    "new": "Ctrl+N", "open": "Ctrl+O", "close": "Ctrl+W", "save": "Ctrl+S", "exit": "Ctrl+Q",
    "undo": "Ctrl+Z", "redo": "Ctrl+Y", "select_all": "Ctrl+A", "zoom_in": "Ctrl++",
    "zoom_out": "Ctrl+-", "fit_width": "Ctrl+0", "next_page": "Ctrl+Down",
    "previous_page": "Ctrl+Up", "compare": "Ctrl+R", "next_difference": "Ctrl+Right",
    "previous_difference": "Ctrl+Left", "ignore": "Del", "help": "F1", "print": "Ctrl+P",
    "switch_area": "Ctrl+Tab", "area_1": "Alt+1", "area_2": "Alt+2",
}
"""SPEC_09 A.4 (X-203), plus R-004 si R-068."""
MENUS = {
    "file": ("new", "open", "close", "recent", None, "save", "print", None, "exit"),
    "edit": ("undo", "redo", None, "copy_difference", "select_all", "ignore",
             "ignore_identical"),
    "view": ("zoom_in", "zoom_out", "fit_width", None, "next_page", "previous_page", None,
             "split_horizontally", "synchronize"),
    "compare": ("compare", "advanced", None, "next_difference", "previous_difference"),
    "help": ("help",),
}
"""R-300: meniurile `File`, `Edit`, `View`, `Compare`, `Help`."""
SAVE_SETTING = "compare.last_save"
REPORT_NAME_KEY = "compare.report.default_name"
"""R-415: numele implicit al raportului (`Differences`)."""


class DisplayArea(QFrame):
    """R-040, R-401…R-403: o zona de afisare: bara de sus (deschidere sau
    inchidere, calea, documentele recente), documentul si bara de jos."""

    open_requested = Signal()
    close_requested = Signal()
    file_dropped = Signal(object)
    recent_chosen = Signal(object)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self.setObjectName(f"compare_area_{index}")
        self.setAcceptDrops(True)  # R-002: tragere peste zona
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        top = QHBoxLayout()
        self.open_button = QToolButton()
        self.open_button.setObjectName(f"compare_open_{index}")
        self.open_button.setText("📂")
        self.open_button.setToolTip(tr("compare.action.open"))
        self.open_button.clicked.connect(self._open_or_close)
        top.addWidget(self.open_button)
        self.path = QComboBox()  # R-401: calea, cu documentele recente
        self.path.setObjectName(f"compare_path_{index}")
        self.path.setEditable(False)
        self.path.activated.connect(self._recent)
        top.addWidget(self.path, 1)
        layout.addLayout(top)
        self.stack = QStackedWidget()
        self.empty = QPushButton(tr("compare.area.empty", n=index))
        self.empty.setObjectName(f"compare_empty_{index}")
        self.empty.setFlat(True)
        self.empty.clicked.connect(self.open_requested.emit)  # R-002: clic in zona
        self.loading = QLabel("⟳ " + tr("compare.loading"))  # R-402
        self.loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view = PdfView()
        for widget in (self.empty, self.loading, self.view):
            self.stack.addWidget(widget)
        layout.addWidget(self.stack, 1)
        bottom = QHBoxLayout()  # R-403
        self.buttons: dict[str, QToolButton] = {}
        for key, text in (("previous_page", "▲"), ("next_page", "▼")):
            self.buttons[key] = self._button(key, text, bottom)
        self.counter = QLabel("")
        bottom.addWidget(self.counter)
        bottom.addStretch(1)
        for key, text in (("zoom_out", "−"), ("fit_width", "↔"), ("zoom_in", "+")):
            self.buttons[key] = self._button(key, text, bottom)
        self.sync = self._button("synchronize", "⇅", bottom)
        self.sync.setCheckable(True)
        self.sync.setChecked(True)  # R-046: activa implicit
        layout.addLayout(bottom)
        self.buttons["previous_page"].clicked.connect(self.view.previous_page)
        self.buttons["next_page"].clicked.connect(self.view.next_page)
        self.buttons["zoom_in"].clicked.connect(self.view.zoom_in)
        self.buttons["zoom_out"].clicked.connect(self.view.zoom_out)
        self.buttons["fit_width"].clicked.connect(lambda: self.view.set_fit(FitMode.FIT_WIDTH))
        self.view.page_changed.connect(self._update_counter)
        self.source: Any = None

    def _button(self, key: str, text: str, row: QHBoxLayout) -> QToolButton:
        button = QToolButton()
        button.setObjectName(f"compare_{key}_{self.index}")
        button.setText(text)
        button.setToolTip(tr(f"compare.action.{key}"))
        row.addWidget(button)
        return button

    def _open_or_close(self) -> None:
        if self.source is None:
            self.open_requested.emit()
        else:
            self.close_requested.emit()

    def _recent(self, index: int) -> None:
        path = self.path.itemData(index)
        if path is not None and (self.source is None or Path(path) != self.source.path):
            self.recent_chosen.emit(Path(path))

    def set_recent(self, paths: list[Path]) -> None:
        current = self.source.path if self.source is not None else None
        self.path.blockSignals(True)
        self.path.clear()
        if current is not None:
            self.path.addItem(str(current), str(current))
        for path in paths:
            if path != current:
                self.path.addItem(str(path), str(path))
        self.path.setCurrentIndex(0 if current is not None else -1)
        self.path.blockSignals(False)

    def show_loading(self) -> None:
        self.stack.setCurrentWidget(self.loading)
        QApplication.processEvents()

    def set_source(self, source: Any) -> None:
        self.source = source
        if source is None:
            self.view.set_document(None)
            self.stack.setCurrentWidget(self.empty)
            self.open_button.setText("📂")
            self.open_button.setToolTip(tr("compare.action.open"))
            self.counter.setText("")
            return
        self.view.set_document(source.document)
        self.view.set_fit(FitMode.FIT_WIDTH)
        self.stack.setCurrentWidget(self.view)
        self.open_button.setText("✕")
        self.open_button.setToolTip(tr("compare.action.close"))
        self._update_counter(self.view.current_page)

    def _update_counter(self, page: int) -> None:
        if self.source is not None:
            self.counter.setText(f"{page} / {self.view.page_count}")

    def dragEnterEvent(self, event: Any) -> None:  # API Qt
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: Any) -> None:  # API Qt
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.file_dropped.emit(Path(urls[0].toLocalFile()))
            event.acceptProposedAction()


class AdvancedDialog(QDialog):
    """R-020…R-023: `Compare > Advanced`."""

    def __init__(self, options: CompareOptions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.core.compare.sources import PDF_MODES

        self.setObjectName("compare_advanced")
        self.setWindowTitle(tr("compare.advanced.title"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.mode = QComboBox()
        for mode in PDF_MODES:
            self.mode.addItem(tr(f"compare.mode.{mode}"), mode)
        self.mode.setCurrentIndex(max(0, self.mode.findData(options.pdf_mode)))
        form.addRow(tr("compare.advanced.pdf_mode"), self.mode)
        layout.addLayout(form)
        self.note = QLabel(tr("compare.mode.ocr_note"))  # R-021
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.headers = QCheckBox(tr("compare.advanced.headers"))  # R-022
        self.headers.setChecked(options.find_headers_footers)
        layout.addWidget(self.headers)
        reset = QPushButton(tr("compare.advanced.reset"))  # R-023
        reset.setObjectName("compare_advanced_reset")
        reset.clicked.connect(self.reset)
        layout.addWidget(reset)
        from app.gui.pdf_content import dialog_buttons

        layout.addWidget(dialog_buttons(self, "compare.ok"))

    def reset(self) -> None:
        defaults = CompareOptions()
        self.mode.setCurrentIndex(self.mode.findData(defaults.pdf_mode))
        self.headers.setChecked(defaults.find_headers_footers)

    def apply(self, options: CompareOptions) -> CompareOptions:
        return replace(options, pdf_mode=str(self.mode.currentData()),
                       find_headers_footers=self.headers.isChecked())


class SaveDialog(QDialog):
    """R-060…R-062: `DOCX in Track Changes Mode`, `PDF with Comments`,
    `Comparison Report`; formatul implicit e cel folosit ultima data."""

    def __init__(self, last: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.core.compare.report import SAVE_KINDS

        self.setObjectName("compare_save")
        self.setWindowTitle(tr("compare.save.title"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.kind = QComboBox()
        for kind in SAVE_KINDS:
            self.kind.addItem(tr(f"compare.save.{kind}"), kind)
        self.kind.setCurrentIndex(max(0, self.kind.findData(last)))
        form.addRow(tr("compare.save.kind"), self.kind)
        self.document = QComboBox()
        self.document.addItem(tr("compare.save.document", n=1), 1)
        self.document.addItem(tr("compare.save.document", n=2), 2)
        self.document.addItem(tr("compare.save.both"), 0)
        form.addRow(tr("compare.save.which"), self.document)
        layout.addLayout(form)
        self.warning = QLabel(tr("compare.save.docx_warning"))  # R-062
        self.warning.setObjectName("compare_save_warning")
        self.warning.setWordWrap(True)
        self.warning.setProperty("warning", True)
        layout.addWidget(self.warning)
        from app.gui.pdf_content import dialog_buttons

        layout.addWidget(dialog_buttons(self, "compare.save.ok"))
        self.kind.currentIndexChanged.connect(self._changed)
        self._changed()

    def _changed(self) -> None:
        kind = self.kind.currentData()
        self.document.setEnabled(kind != "report")
        both = self.document.findData(0)
        if kind == "pdf_comments" and self.document.currentData() == 0:
            self.document.setCurrentIndex(1)
        self.document.model().item(both).setEnabled(kind == "track_changes")
        self.warning.setVisible(kind == "track_changes")  # R-062: inainte de salvare


class CompareWindow(QMainWindow):
    """R-001…R-068: modulul `Compare Documents`."""

    closed = Signal()

    def __init__(self, context: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.core.compare.engine import DocumentComparer

        self.setObjectName("compare_window")
        self.context = context
        self.settings = context.settings
        self.engine: Any = None
        """Motorul OCR (None = Tesseract); testele dau unul fals."""
        self.comparer = DocumentComparer(context=context, texts=tr)
        self.options = CompareOptions(languages=("ron",))
        self.differences: list[Difference] = []
        self.compared = False
        self.current: int | None = None
        """`order_index` al diferentei curente."""
        self.grouping = True
        self._history: list[list[Difference]] = []
        self._future: list[list[Difference]] = []
        self._syncing = False
        self.actions: dict[str, QAction] = {}
        self._build_actions()
        self._build_menus()
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.band = QLabel()  # R-407
        self.band.setObjectName("compare_result_band")
        self.band.setStyleSheet("background: #d93636; color: white; padding: 4px 10px;"
                                " font-weight: 600;")
        self.band.hide()
        outer.addWidget(self.band)
        body = QHBoxLayout()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.areas = [DisplayArea(1), DisplayArea(2)]
        for area in self.areas:
            self.splitter.addWidget(area)
            area.open_requested.connect(lambda a=area: self.ask_open(a.index))
            area.close_requested.connect(lambda a=area: self.close_document(a.index))
            area.file_dropped.connect(lambda path, a=area: self.load(a.index, path))
            area.recent_chosen.connect(lambda path, a=area: self.load(a.index, path))
            area.view.overlays.append(self._paint)
            area.view.verticalScrollBar().valueChanged.connect(
                lambda _v, a=area: self._synchronize(a))
            area.view.installEventFilter(self)
            area.view.viewport().installEventFilter(self)
            area.sync.toggled.connect(self.set_synchronize)  # R-403, R-046
        body.addWidget(self.splitter, 1)
        body.addWidget(self._build_panel())
        outer.addLayout(body, 1)
        self.setCentralWidget(central)
        self.active = 1
        self.resize(1280, 820)
        self._refresh_recent()
        self._update()

    # --- comenzile, meniurile (R-300, SPEC_09 A.4) ---------------------------------------

    def _build_actions(self) -> None:
        keys = {k for menu in MENUS.values() for k in menu if k} | {
            "switch_area", "area_1", "area_2"}
        for key in sorted(keys - {"recent"}):
            action = QAction(tr(f"compare.action.{key}"), self)
            action.setObjectName(f"compare_action_{key}")
            if key in SHORTCUTS:
                action.setShortcut(QKeySequence(SHORTCUTS[key]))
            self.addAction(action)
            self.actions[key] = action
        a = self.actions
        connect = {
            "new": self.new_comparison, "open": lambda: self.ask_open(self.active),
            "close": lambda: self.close_document(self.active), "save": self.save,
            "exit": self.close, "undo": self.undo, "redo": self.redo,
            "select_all": self.select_all, "ignore": self.ignore_selected,
            "ignore_identical": self.ignore_identical, "copy_difference": self.copy_difference,
            "zoom_in": lambda: self._view().zoom_in(), "zoom_out": lambda: self._view().zoom_out(),
            "fit_width": lambda: self._view().set_fit(FitMode.FIT_WIDTH),
            "next_page": lambda: self._view().next_page(),
            "previous_page": lambda: self._view().previous_page(),
            "compare": self.compare, "advanced": self.advanced,
            "next_difference": lambda: self.step(1),
            "previous_difference": lambda: self.step(-1), "help": self.show_help,
            "print": self.print_result, "switch_area": lambda: self.set_active(3 - self.active),
            "area_1": lambda: self.set_active(1), "area_2": lambda: self.set_active(2),
            "split_horizontally": self.toggle_split,
        }
        for key, slot in connect.items():
            a[key].triggered.connect(slot)
        a["split_horizontally"].setCheckable(True)  # R-041
        a["synchronize"].setCheckable(True)  # R-046
        a["synchronize"].setChecked(True)
        a["synchronize"].toggled.connect(self.set_synchronize)

    def _build_menus(self) -> None:
        self.menus: dict[str, QMenu] = {}
        for name, keys in MENUS.items():
            menu = self.menuBar().addMenu(tr(f"compare.menu.{name}"))
            menu.setObjectName(f"compare_menu_{name}")
            for key in keys:
                if key is None:
                    menu.addSeparator()
                elif key == "recent":
                    self.recent_menu = menu.addMenu(tr("compare.action.recent"))  # R-006
                    self.recent_menu.setObjectName("compare_recent_menu")
                else:
                    menu.addAction(self.actions[key])
            self.menus[name] = menu

    def _build_panel(self) -> QWidget:
        """R-404, R-405: panoul din dreapta, cu `Compare` si `Differences (N)`."""
        from app.core.compare.sources import compare_languages
        from app.gui.options_dialog import language_name

        self.panel = QTabWidget()
        self.panel.setObjectName("compare_panel")
        self.panel.setFixedWidth(PANEL_WIDTH + 60)
        page = QWidget()
        box = QVBoxLayout(page)
        box.addWidget(QLabel(tr("compare.language")))
        self.language = QComboBox()  # R-008
        self.language.setObjectName("compare_language")
        for code in compare_languages():
            self.language.addItem(language_name(code), code)
        self.language.setCurrentIndex(max(0, self.language.findData("ron")))
        box.addWidget(self.language)
        self.punctuation = QCheckBox(tr("compare.punctuation"))  # R-015
        self.one_letter = QCheckBox(tr("compare.one_letter"))  # R-016
        for check in (self.punctuation, self.one_letter):
            check.setChecked(False)
            box.addWidget(check)
        self.compare_button = QPushButton(tr("compare.action.compare"))  # R-406
        self.compare_button.setObjectName("compare_button")
        self.compare_button.setMinimumHeight(40)
        self.compare_button.setStyleSheet("background: #2f6df6; color: white;"
                                          " font-weight: 600; border-radius: 6px;")
        self.compare_button.clicked.connect(self.compare)
        box.addWidget(self.compare_button)
        box.addStretch(1)
        self.panel.addTab(page, tr("compare.tab.compare"))
        differences = QWidget()
        layout = QVBoxLayout(differences)
        bar = QHBoxLayout()  # R-408
        self.save_button = QToolButton()
        self.save_button.setObjectName("compare_save_button")
        self.save_button.setText("W  " + tr("compare.action.save"))
        self.save_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.save_button.setMinimumWidth(96)
        self.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.save_button.clicked.connect(self.save)
        save_menu = QMenu(self.save_button)
        from app.core.compare.report import SAVE_KINDS

        for kind in SAVE_KINDS:
            save_menu.addAction(tr(f"compare.save.{kind}"), lambda k=kind: self.save(k))
        self.save_button.setMenu(save_menu)
        self.save_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.save_button)
        for key, text in (("next_difference", "▼"), ("previous_difference", "▲"),
                          ("ignore", "🗑")):
            button = QToolButton()
            button.setObjectName(f"compare_bar_{key}")
            button.setText(text)
            button.setToolTip(tr(f"compare.action.{key}"))
            button.clicked.connect(self.actions[key].trigger)
            bar.addWidget(button)
        self.group_button = QToolButton()  # R-034: gruparea se poate dezactiva
        self.group_button.setObjectName("compare_group_button")
        self.group_button.setText("☰")
        self.group_button.setToolTip(tr("compare.action.group"))
        self.group_button.setCheckable(True)
        self.group_button.setChecked(True)
        self.group_button.toggled.connect(self.set_grouping)
        bar.addWidget(self.group_button)
        bar.addStretch(1)
        layout.addLayout(bar)
        self.tree = QTreeWidget()  # R-043
        self.tree.setObjectName("compare_differences")
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2)
        self.tree.setWordWrap(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setIndentation(10)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        header.setSectionResizeMode(1, header.ResizeMode.ResizeToContents)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.setStyleSheet("QTreeWidget::item:selected { background: #c9d3e6;"
                                " color: black; }")  # R-412: gri-albastru
        self.tree.itemSelectionChanged.connect(self._selected)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.tree, 1)
        self.panel.addTab(differences, tr("compare.tab.differences", n=0))
        return self.panel

    # --- documentele (R-002…R-010) ---------------------------------------------------------

    def _view(self) -> PdfView:
        return self.areas[self.active - 1].view

    def set_active(self, index: int) -> None:
        """R-004: `Ctrl+Tab`, `Alt+1`, `Alt+2`."""
        self.active = index
        for area in self.areas:
            area.setStyleSheet("" if area.index != index else
                               f"QFrame#compare_area_{index} {{ border: 2px solid #2f6df6; }}")
        self.areas[index - 1].view.setFocus()

    def ask_open_path(self, index: int) -> Path | None:
        path, _ = QFileDialog.getOpenFileName(self, tr("compare.action.open"), "",
                                              tr("compare.filter"))
        return Path(path) if path else None

    def ask_password(self) -> str | None:
        from PySide6.QtWidgets import QInputDialog, QLineEdit

        text, ok = QInputDialog.getText(self, tr("compare.password"), tr("compare.password"),
                                        QLineEdit.EchoMode.Password)
        return text if ok and text else None

    def ask_open(self, index: int) -> bool:
        """R-002, R-003: buton din bara, `File > Open Document...`, clic in zona."""
        path = self.ask_open_path(index)
        return path is not None and self.load(index, path)

    def _options(self) -> CompareOptions:
        return replace(self.options, languages=(str(self.language.currentData()),),
                       find_punctuation=self.punctuation.isChecked(),
                       find_one_letter=self.one_letter.isChecked())

    def load(self, index: int, path: Path) -> bool:
        """R-002, R-005, R-007: documentul se citeste (cu OCR la nevoie) si se
        afiseaza in zona; un format nesuportat da mesaj."""
        from app.core.compare.sources import load_source

        area = self.areas[index - 1]
        area.show_loading()
        attempts = {"n": 0}

        def password(_path: str) -> str | None:
            attempts["n"] += 1
            return self.ask_password() if attempts["n"] <= 3 else None

        options = self._options()
        try:
            source = load_source(Path(path), mode=options.pdf_mode, languages=options.languages,
                                 password=password, context=self.context, engine=self.engine)
        except CoreError as exc:
            area.set_source(area.source)
            self.show_message(tr_error(exc))
            return False
        except (FileNotFoundError, OSError):
            area.set_source(area.source)
            self.show_message(tr("compare.missing", path=str(path)))
            return False
        if area.source is not None:
            area.source.close()
        area.set_source(source)
        self._reset_result()
        self.set_active(index)
        self._refresh_recent()
        self._update()
        return True

    def close_document(self, index: int) -> None:
        """R-009: zona se goleste."""
        area = self.areas[index - 1]
        if area.source is not None:
            area.source.close()
        area.set_source(None)
        self._reset_result()
        self._update()

    def new_comparison(self) -> None:
        """R-010: ambele zone se golesc."""
        for area in self.areas:
            self.close_document(area.index)

    def _reset_result(self) -> None:
        self.differences = []
        self.compared = False
        self.current = None
        self._history.clear()
        self._future.clear()
        self._show_differences()

    # --- compararea (R-017, R-036, R-416) --------------------------------------------------

    def advanced(self) -> bool:
        """R-020…R-023."""
        dialog = AdvancedDialog(self.options, self)
        if not self.exec_dialog(dialog):
            return False
        self.options = dialog.apply(self.options)
        return True

    def compare(self) -> list[Difference] | None:
        """R-017: lista de diferente, cu progres si sfaturi (R-416)."""
        from app.core.compare.engine import compare_sources, record_recent

        left, right = (a.source for a in self.areas)
        if left is None or right is None:
            self.show_message(tr("compare.need_two"))
            return None
        options = self._options()
        progress = self._progress_dialog()

        def report(step: Any) -> None:
            if progress is not None:
                progress.setMaximum(max(step.total, 1))
                progress.setValue(min(step.current, step.total))
                QApplication.processEvents()

        try:
            result = compare_sources(left, right, options, progress=report,
                                     cancel=lambda: bool(progress and progress.wasCanceled()))
        finally:
            if progress is not None:
                progress.close()
        self.differences = result
        self.compared = True
        self.current = result[0].order_index if result else None
        self._history.clear()
        self._future.clear()
        record_recent(self.context.app_db, left.path, right.path, options.languages,
                      len(result))
        self._refresh_recent()
        self._show_differences()
        self.panel.setCurrentIndex(1)
        if self.current is not None:
            self.go_to(self.current)
        return result

    def _progress_dialog(self) -> QProgressDialog | None:
        """R-416: dialogul de progres, cu un sfat."""
        if QApplication.platformName() == "offscreen":
            return None
        dialog = QProgressDialog(tr("compare.tip"), tr("compare.cancel"), 0, 1, self)
        dialog.setWindowTitle(tr("compare.progress"))
        dialog.setMinimumDuration(400)
        return dialog

    # --- lista de diferente (R-034, R-043, R-044, R-409…R-412) -----------------------------

    def _visible(self) -> list[Difference]:
        return [d for d in self.differences if not d.is_ignored]

    def _item(self, difference: Difference) -> QTreeWidgetItem:
        """R-410, R-411: sageata colorata, titlul in bold, pagina la dreapta; la o
        modificare, ambele versiuni."""
        kind = {DiffType.INSERTED: "added", DiffType.DELETED: "deleted"}.get(
            difference.diff_type, "edited")
        lines = [tr(f"compare.kind.{kind}")]
        if difference.text_left and difference.diff_type != DiffType.INSERTED:
            lines.append(("− " if difference.text_right else "") + difference.text_left)
        if difference.text_right and difference.diff_type != DiffType.DELETED:
            lines.append(("+ " if difference.text_left else "") + difference.text_right)
        item = QTreeWidgetItem(["\n".join(lines), tr(
            "compare.page_short", n=difference.page_right or difference.page_left or 1)])
        item.setData(0, Qt.ItemDataRole.UserRole, difference.order_index)
        font = QFont(item.font(0))
        font.setBold(True)
        item.setFont(0, font)
        arrow = "→" if difference.diff_type != DiffType.DELETED else "←"
        item.setText(0, arrow + " " + item.text(0))
        item.setForeground(0, QColor(ICON_COLORS[difference.diff_type]))
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        return item

    def _show_differences(self) -> None:
        from app.core.compare.engine import grouped

        self.tree.blockSignals(True)
        self.tree.clear()
        visible = self._visible()
        if self.grouping:
            for group, items in grouped(self.differences).items():
                if not items:
                    continue
                parent = QTreeWidgetItem([tr(f"compare.group.{group}", n=len(items))])
                parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.tree.addTopLevelItem(parent)
                parent.addChildren([self._item(d) for d in items])
                parent.setExpanded(True)
        else:
            self.tree.addTopLevelItems([self._item(d) for d in visible])
        self.tree.blockSignals(False)
        self._select_current()
        self.panel.setTabText(1, tr("compare.tab.differences", n=len(visible)))  # R-405
        if self.compared:
            self.band.setText(tr("compare.found", n=len(visible)))  # R-407
            self.band.show()
        else:
            self.band.hide()
        self._update()

    def _items(self) -> list[QTreeWidgetItem]:
        out: list[QTreeWidgetItem] = []
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.data(0, Qt.ItemDataRole.UserRole) is not None:
                out.append(top)
            out += [top.child(k) for k in range(top.childCount())]
        return out

    def _select_current(self) -> None:
        self.tree.blockSignals(True)
        for item in self._items():
            item.setSelected(item.data(0, Qt.ItemDataRole.UserRole) == self.current)
            if item.isSelected():
                self.tree.scrollToItem(item)
        self.tree.blockSignals(False)

    def selected_indices(self) -> list[int]:
        return [int(i.data(0, Qt.ItemDataRole.UserRole)) for i in self.tree.selectedItems()
                if i.data(0, Qt.ItemDataRole.UserRole) is not None]

    def _selected(self) -> None:
        chosen = self.selected_indices()
        if len(chosen) == 1:
            self.go_to(chosen[0])

    def set_grouping(self, on: bool) -> None:
        """R-034: gruparea se poate dezactiva din butonul tabului `Differences`."""
        self.grouping = on
        self._show_differences()

    # --- navigarea si evidentierea (R-045, R-046, R-413) ------------------------------------

    def _difference(self, index: int) -> Difference | None:
        return next((d for d in self.differences if d.order_index == index), None)

    def go_to(self, index: int) -> None:
        """R-045: ambele zone sar la locul diferentei."""
        difference = self._difference(index)
        if difference is None:
            return
        self.current = index
        self._syncing = True
        try:
            for area, page, box in ((self.areas[0], difference.page_left, difference.bbox_left),
                                    (self.areas[1], difference.page_right,
                                     difference.bbox_right)):
                if area.source is None or page is None:
                    continue
                view = area.view
                view.go_to_page(page)
                if box is not None:
                    target = view.page_to_view(page, box)
                    slot = view.slot(page)
                    if target is not None and slot is not None:
                        bar = view.verticalScrollBar()
                        top = max(slot.rect.top(), target.top() - view.viewport().height() / 3)
                        bar.setValue(int(top))
                view.viewport().update()
        finally:
            self._syncing = False
        self._select_current()
        self._update()

    def step(self, direction: int) -> None:
        """R-045: `Ctrl+Dreapta` / `Ctrl+Stanga`."""
        order = [d.order_index for d in self._ordered()]
        if not order:
            return
        if self.current not in order:
            self.go_to(order[0] if direction > 0 else order[-1])
            return
        position = order.index(self.current) + direction
        if 0 <= position < len(order):
            self.go_to(order[position])

    def _ordered(self) -> list[Difference]:
        if not self.grouping:
            return self._visible()
        from app.core.compare.engine import grouped

        return [d for items in grouped(self.differences).values() for d in items]

    def _paint(self, painter: Any, view: Any) -> None:
        """R-413: diferentele in mov deschis; cea curenta subliniata rosu; textul
        adaugat cu chenar albastru."""
        side = 1 if view is self.areas[0].view else 2
        for difference in self._visible():
            rects = difference.rects_left if side == 1 else difference.rects_right
            for page, rect in rects:
                box = view.page_to_view(page, rect)
                if box is None:
                    continue
                painter.fillRect(box, DIFF_FILL)
                if side == 2 and difference.diff_type == DiffType.INSERTED:
                    painter.setPen(QPen(ADDED_BORDER, 1))
                    painter.drawRect(box)
                if difference.order_index == self.current:
                    painter.setPen(QPen(CURRENT_LINE, 2))
                    painter.drawLine(box.bottomLeft(), box.bottomRight())

    def set_synchronize(self, on: bool) -> None:
        """R-046: derularea sincronizata (activa implicit)."""
        self.actions["synchronize"].setChecked(on)
        for area in self.areas:
            area.sync.setChecked(on)

    def _synchronize(self, moved: DisplayArea) -> None:
        if self._syncing or not self.actions["synchronize"].isChecked():
            return
        other = self.areas[2 - moved.index]
        if other.source is None or moved.source is None:
            return
        source, target = moved.view.verticalScrollBar(), other.view.verticalScrollBar()
        share = source.value() / source.maximum() if source.maximum() else 0.0
        self._syncing = True
        try:
            target.setValue(int(share * target.maximum()))
        finally:
            self._syncing = False

    def toggle_split(self) -> None:
        """R-041: `Split Document Pane Horizontally`."""
        horizontal = self.actions["split_horizontally"].isChecked()
        self.splitter.setOrientation(Qt.Orientation.Vertical if horizontal
                                     else Qt.Orientation.Horizontal)

    # --- ignorarea, copierea (R-047…R-050) ----------------------------------------------------

    def _remember(self) -> None:
        self._history.append(list(self.differences))
        self._future.clear()

    def ignore_selected(self) -> int:
        """R-048: `Del`; cu `Ctrl` se aleg mai multe."""
        from app.core.compare.engine import ignore

        chosen = self.selected_indices() or ([self.current] if self.current is not None else [])
        if not chosen:
            return 0
        self._remember()
        self.differences = ignore(self.differences, chosen)
        self._after_ignore()
        return len(chosen)

    def ignore_identical(self) -> int:
        """R-049: toate diferentele identice cu cea aleasa."""
        from app.core.compare.engine import ignore_identical

        if self.current is None:
            return 0
        before = len(self._visible())
        self._remember()
        self.differences = ignore_identical(self.differences, self.current)
        self._after_ignore()
        return before - len(self._visible())

    def _after_ignore(self) -> None:
        visible = [d.order_index for d in self._visible()]
        if self.current not in visible:
            later = [i for i in visible if self.current is not None and i > self.current]
            self.current = later[0] if later else (visible[-1] if visible else None)
        self._show_differences()
        for area in self.areas:
            area.view.viewport().update()

    def undo(self) -> None:
        if self._history:
            self._future.append(list(self.differences))
            self.differences = self._history.pop()
            self._after_ignore()

    def redo(self) -> None:
        if self._future:
            self._history.append(list(self.differences))
            self.differences = self._future.pop()
            self._after_ignore()

    def select_all(self) -> None:
        """R-050: `Ctrl+A`."""
        for item in self._items():
            item.setSelected(True)

    def copy_difference(self) -> str:
        """R-047: textul diferentei in clipboard."""
        chosen = self.selected_indices() or ([self.current] if self.current is not None else [])
        parts: list[str] = []
        for index in chosen:
            difference = self._difference(index)
            if difference is None:
                continue
            if difference.text_left and difference.text_right:
                parts.append(f"{difference.text_left} → {difference.text_right}")
            else:
                parts.append(difference.text_left or difference.text_right or "")
        text = "\n".join(parts)
        if text:
            QApplication.clipboard().setText(text)
        return text

    def _context_menu(self, position: Any) -> None:
        menu = QMenu(self)
        for key in ("copy_difference", "ignore", "ignore_identical", "select_all"):
            menu.addAction(self.actions[key])
        menu.addSeparator()
        menu.addAction(self.actions["synchronize"])
        menu.popup(self.tree.viewport().mapToGlobal(position))

    # --- salvarea si tiparirea (R-060…R-068) --------------------------------------------------

    def ask_save_target(self, kind: str, suggested: str) -> Path | None:
        suffix = ".pdf" if kind == "pdf_comments" else ".docx"
        file_filter = tr("compare.filter.pdf") if suffix == ".pdf" else tr(
            "compare.filter.docx")  # R-065
        path, _ = QFileDialog.getSaveFileName(self, tr("compare.action.save"),
                                              suggested + suffix, file_filter)
        if not path:
            return None
        target = Path(path)
        return target if target.suffix.lower() == suffix else target.with_suffix(suffix)

    def save(self, kind: str | None = None) -> list[Path]:
        """R-060: dialogul cu cele trei variante; formatul implicit e ultimul
        folosit. R-062: avertismentul pentru DOCX apare inainte de salvare."""
        if not self.compared:
            self.show_message(tr("compare.nothing_to_save"))
            return []
        last = kind or str(self.settings.get(SAVE_SETTING) or "report")
        dialog = SaveDialog(last, self)
        if not self.exec_dialog(dialog):
            return []
        kind = str(dialog.kind.currentData())
        which = int(dialog.document.currentData())
        self.settings.set(SAVE_SETTING, kind)
        left, right = (a.source for a in self.areas)
        written: list[Path] = []
        try:
            if kind == "report":
                target = self.ask_save_target(kind, tr(REPORT_NAME_KEY))  # R-415
                if target is not None:
                    written.append(self.comparer.save_report(
                        self.differences, target, left=left.path, right=right.path))
            elif kind == "pdf_comments":
                source = left if which == 1 else right
                target = self.ask_save_target(kind, source.path.stem)
                if target is not None:
                    written.append(self.comparer.save_as_pdf_with_comments(
                        source, self.differences, target, side=which or 2))
            else:
                for side in ((1, 2) if which == 0 else (which,)):
                    source = left if side == 1 else right
                    target = self.ask_save_target(kind, source.path.stem)
                    if target is not None:
                        written.append(self.comparer.save_as_track_changes(
                            source, self.differences, target, side=side,
                            author=tr("compare.author")))
        except (CoreError, OSError) as exc:
            self.show_message(tr_error(exc) if isinstance(exc, CoreError)
                              else tr("error.generic"))
        return written

    def print_result(self) -> int:
        """R-068: documentul activ, cu diferentele ca adnotari."""
        from app.core.compare.report import save_pdf_with_comments
        from app.core.pdf.document import PdfDocument
        from app.gui.pdf_print import print_document

        area = self.areas[self.active - 1]
        if area.source is None:
            return 0
        with tempfile.TemporaryDirectory(prefix="doculens-compare-") as tmp:
            target = save_pdf_with_comments(area.source, self.differences,
                                            Path(tmp) / "rezultat.pdf", side=area.index,
                                            texts=tr)
            with PdfDocument.open(target) as document:
                chosen = self.choose_print(document)
                if chosen is None:
                    return 0
                printer, settings = chosen
                return print_document(document, printer, settings)

    def choose_print(self, document: Any) -> tuple[Any, Any] | None:
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter

        from app.gui.pdf_print import PrintOptions

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        options = PrintOptions()
        dialog = QPrintDialog(printer, self)
        dialog.setOptionTabs([options])
        if not self.exec_dialog(dialog):
            return None
        return printer, options.settings(None)

    # --- recentele, starea, utilitare -------------------------------------------------------

    def _refresh_recent(self) -> None:
        """R-006: `File > Recent Comparisons`; un fisier lipsa marcheaza randul."""
        from app.core.compare.engine import recent_comparisons

        recents = recent_comparisons(self.context.app_db)
        self.recent_menu.clear()
        for entry in recents:
            text = f"{entry.left.name}  ↔  {entry.right.name}"
            if entry.missing:
                text += "  " + tr("compare.recent_missing")
            action = self.recent_menu.addAction(text)
            action.setEnabled(not entry.missing)
            action.triggered.connect(lambda _c=False, e=entry: self.open_pair(e.left, e.right))
        self.recent_menu.setEnabled(bool(recents))
        paths: list[Path] = []
        for entry in recents:
            for path in (entry.left, entry.right):
                if path not in paths and path.is_file():
                    paths.append(path)
        for area in self.areas:
            area.set_recent(paths)

    def open_pair(self, left: Path | None, right: Path | None) -> bool:
        """R-001, R-006: perechea data (din recente sau din alt modul)."""
        done = True
        if left is not None:
            done = self.load(1, Path(left)) and done
        if right is not None:
            done = self.load(2, Path(right)) and done
        return done

    def _update(self) -> None:
        a = self.actions
        both = all(area.source is not None for area in self.areas)
        visible = bool(self._visible())
        a["compare"].setEnabled(both)
        self.compare_button.setEnabled(both)
        for key in ("save", "print"):
            a[key].setEnabled(self.compared)
        self.save_button.setEnabled(self.compared)
        for key in ("next_difference", "previous_difference", "ignore", "ignore_identical",
                    "copy_difference", "select_all"):
            a[key].setEnabled(visible)
        a["undo"].setEnabled(bool(self._history))
        a["redo"].setEnabled(bool(self._future))
        names = [area.source.path.name if area.source else "—" for area in self.areas]
        self.setWindowTitle(tr("compare.window_title", left=names[0], right=names[1]))  # R-400

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # API Qt
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            for area in self.areas:
                if watched in (area.view, area.view.viewport()) and self.active != area.index:
                    self.set_active(area.index)
        return False

    def exec_dialog(self, dialog: Any) -> bool:
        return bool(dialog.exec())

    def show_message(self, text: str) -> None:
        QMessageBox.information(self, tr("compare.title"), text)

    def show_help(self) -> None:
        self.show_message(tr("compare.help"))

    def closeEvent(self, event: Any) -> None:  # API Qt
        for area in self.areas:
            if area.source is not None:
                area.source.close()
                area.set_source(None)
        self.closed.emit()
        super().closeEvent(event)

    def sizeHint(self) -> QSize:  # API Qt
        return QSize(1280, 820)
