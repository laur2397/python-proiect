"""Fereastra principala a OCR Editor-ului (faza 6b, pasul 6b.1): J-001..J-017,
J-400..J-420.

Structura din SPEC_10 (J-400..J-420), fara identitatea vizuala ABBYY
(CLAUDE.md §6.6): titlul (J-400), bara principala in ordinea din J-401,
butonul de salvare cu formatele (J-402) active dupa modul de layout (Q-001),
panourile Pages, Image, Text si Zoom, mutabile (J-409), indicatorul de
avertismente (J-419), `Verify` gri fara caractere nesigure (J-420).

Fereastra nu contine reguli de business (CLAUDE.md §4): citeste proiectul si
cheama nucleul. Toate textele vin din traduceri (`app.gui.i18n`).

INCOMPLET, marcat: continutul panourilor (miniaturile, imaginea cu zonele,
textul) vine in 6b.2 si 6b.3; dialogurile in 6b.4…6b.6.
"""

from __future__ import annotations

import itertools
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QTextEdit,
    QToolBar,
    QToolButton,
)

from app.core.model import ExportFormat, LayoutMode, PageStatus
from app.gui.i18n import tr

TOOLBAR_ORDER = ("new_task", "new_project", "open_project", "open", "scan", "page_counter",
                 "recognize", "language", "undo", "redo", "save", "layout_mode",
                 "arrange_side", "arrange_stacked", "verify")
"""J-401: ordinea exacta a barei principale."""

SAVE_FORMATS = ("pdf", "pdf_image", "pdfa", "pdfua", "docx", "rtf", "odt", "xlsx", "csv",
                "pptx", "txt", "html", "epub", "fb2", "djvu")
"""J-402: formatele butonului de salvare (cheile `format.*`)."""

_untitled = itertools.count(1)


def save_format(key: str) -> ExportFormat:
    return ExportFormat.PDF if key == "pdf_image" else ExportFormat(key)


class MainWindow(QMainWindow):
    def __init__(self, context: Any, project: Any = None) -> None:
        super().__init__()
        from app.core.project import OcrProject

        self.context = context
        self.project = project or OcrProject.create(context=context)
        self._untitled = next(_untitled)
        self._current = 1
        self.actions: dict[str, QAction] = {}
        self.toolbar_items: list[str] = []
        self.setObjectName("main_window")
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_panels()
        self.warnings = QLabel()
        self.warnings.setObjectName("warnings_indicator")
        self.statusBar().addWidget(self.warnings)  # J-419: stanga-jos
        self.refresh()

    # --- constructie ----------------------------------------------------------------

    def _build_actions(self) -> None:
        for key in ("new_task", "new_project", "open_project", "open", "scan", "page_up",
                    "page_down", "recognize", "undo", "redo", "arrange_side",
                    "arrange_stacked", "verify", "options", "exit", "save_project",
                    "save_project_as", "close_project"):
            action = QAction(tr(f"action.{key}"), self)
            action.setObjectName(key)
            self.actions[key] = action
        self.actions["undo"].triggered.connect(self._undo)
        self.actions["redo"].triggered.connect(self._redo)
        self.actions["exit"].triggered.connect(self.close)
        self.actions["page_up"].triggered.connect(lambda: self.go_to_page(self._current - 1))
        self.actions["page_down"].triggered.connect(lambda: self.go_to_page(self._current + 1))

    def _build_menus(self) -> None:
        layout: dict[str, tuple[str | None, ...]] = {
            "file": ("new_project", "open_project", "open", "scan", None, "save_project",
                     "save_project_as", "close_project", None, "exit"),
            "edit": ("undo", "redo"),
            "view": ("arrange_side", "arrange_stacked"),
            "recognize": ("recognize", "verify"),
            "area": (),
            "tools": ("options",),
            "help": (),
        }
        self.menus: dict[str, QMenu] = {}
        for name, keys in layout.items():
            menu = self.menuBar().addMenu(tr(f"menu.{name}"))
            menu.setObjectName(f"menu_{name}")
            for key in keys:
                if key is None:
                    menu.addSeparator()
                else:
                    menu.addAction(self.actions[key])
            self.menus[name] = menu

    def _build_toolbar(self) -> None:
        bar = QToolBar(self)
        bar.setObjectName("main_toolbar")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
        for key in TOOLBAR_ORDER:
            if key == "page_counter":  # [ N / M ] cu sageti sus si jos
                bar.addAction(self.actions["page_up"])
                self.page_counter = QLabel()
                self.page_counter.setObjectName("page_counter")
                bar.addWidget(self.page_counter)
                bar.addAction(self.actions["page_down"])
            elif key == "language":
                self.language_combo = QComboBox()
                self.language_combo.setObjectName("language")
                self.language_combo.setToolTip(tr("action.language"))
                bar.addWidget(self.language_combo)
            elif key == "save":
                self._build_save_button(bar)
            elif key == "layout_mode":
                self.layout_combo = QComboBox()
                self.layout_combo.setObjectName("layout_mode")
                self.layout_combo.setToolTip(tr("action.layout_mode"))
                for mode in LayoutMode:
                    self.layout_combo.addItem(tr(f"layout.{mode.value}"), mode.value)
                self.layout_combo.currentIndexChanged.connect(self._layout_changed)
                bar.addWidget(self.layout_combo)
            else:
                bar.addAction(self.actions[key])
            self.toolbar_items.append(key)
        self.layout_combo.setCurrentIndex(list(LayoutMode).index(LayoutMode.EDITABLE))
        self._layout_changed()

    def _build_save_button(self, bar: QToolBar) -> None:
        self.save_button = QToolButton()
        self.save_button.setObjectName("save")
        self.save_button.setText(tr("action.save"))
        self.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        menu = QMenu(self.save_button)
        self.save_actions: dict[str, QAction] = {}
        for fmt in SAVE_FORMATS:
            action = menu.addAction(tr(f"format.{fmt}"))
            action.setObjectName(f"save_{fmt}")
            self.save_actions[fmt] = action
        self.save_button.setMenu(menu)
        bar.addWidget(self.save_button)

    def _dock(self, key: str, widget: Any, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(tr(f"panel.{key}"), self)
        dock.setObjectName(f"panel_{key}")
        dock.setWidget(widget)
        # J-409: panourile se pot muta la stanga sau la dreapta
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea
                             | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(area, dock)
        return dock

    def _build_panels(self) -> None:
        self.pages_list = QListWidget()
        self.pages_list.setObjectName("pages_list")
        self.pages_list.currentRowChanged.connect(lambda row: self.go_to_page(row + 1))
        self.pages_dock = self._dock("pages", self.pages_list,
                                     Qt.DockWidgetArea.LeftDockWidgetArea)
        self.image_view = QLabel()
        self.image_view.setObjectName("image_view")
        self.image_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self.image_view)
        self.text_view = QTextEdit()
        self.text_view.setObjectName("text_view")
        self.text_view.setReadOnly(True)
        self.text_view.setPlaceholderText(tr("panel.text.empty"))  # O-103
        self.text_dock = self._dock("text", self.text_view,
                                    Qt.DockWidgetArea.RightDockWidgetArea)
        self.zoom_view = QLabel()
        self.zoom_view.setObjectName("zoom_view")
        self.zoom_dock = self._dock("zoom", self.zoom_view,
                                    Qt.DockWidgetArea.RightDockWidgetArea)

    # --- starea -------------------------------------------------------------------------

    @property
    def current(self) -> int:
        return self._current

    def go_to_page(self, number: int) -> None:
        total = len(self.project.pages)
        self._current = max(1, min(number, total)) if total else 1
        if total and self.pages_list.currentRow() != self._current - 1:
            self.pages_list.blockSignals(True)
            self.pages_list.setCurrentRow(self._current - 1)
            self.pages_list.blockSignals(False)
        self._show_page()

    def _show_page(self) -> None:
        pages = self.project.pages
        total = len(pages)
        self.page_counter.setText(tr("action.page_counter", n=self._current if total else 0,
                                     total=total))
        self.actions["page_up"].setEnabled(self._current > 1)
        self.actions["page_down"].setEnabled(self._current < total)
        page = pages[self._current - 1] if total else None
        recognized = page is not None and page.status in (PageStatus.RECOGNIZED,
                                                          PageStatus.VERIFIED)
        self.text_view.setPlainText(page.text if recognized else "")

    def update_title(self) -> None:
        """J-400: `<proiect> - DocuLens OCR Editor`; proiect nou: fara titlu N."""
        name = self.project.name or tr("window.untitled", n=self._untitled)
        self.setWindowTitle(tr("window.title", project=name))

    def refresh(self) -> None:
        """Totul din starea proiectului: titlul, paginile, contorul, butoanele."""
        self.update_title()
        pages = self.project.pages
        self.pages_list.blockSignals(True)
        self.pages_list.clear()
        for page in pages:
            item = QListWidgetItem(str(page.page_number))
            item.setToolTip(tr(f"page.status.{page.status.value}"))  # J-405, J-407
            self.pages_list.addItem(item)
        self.pages_list.blockSignals(False)
        warnings = sum(len(p.warnings) for p in pages)
        self.warnings.setText(tr("status.warnings", n=warnings) if warnings else "")
        self.warnings.setVisible(bool(warnings))
        uncertain = any(w.is_uncertain and not w.is_verified for p in pages
                        for w in p.iter_words())
        self.actions["verify"].setEnabled(uncertain)  # J-420
        self.actions["undo"].setEnabled(self.project.can_undo())
        self.actions["redo"].setEnabled(self.project.can_redo())
        languages = self.project.settings().ocr_settings().languages
        self.language_combo.clear()
        self.language_combo.addItem(" + ".join(languages))
        self.go_to_page(self._current)

    # --- actiuni ----------------------------------------------------------------------

    def _layout_changed(self) -> None:
        """Q-001: formatele permise de modul ales; PDF-ul doar-imagine merge oricum."""
        mode = LayoutMode(self.layout_combo.currentData())
        allowed = ExportFormat.allowed_for(mode)
        for key, action in self.save_actions.items():
            fmt = save_format(key)
            base = ExportFormat.PDF if fmt in (ExportFormat.PDFA, ExportFormat.PDFUA) else fmt
            action.setEnabled(key == "pdf_image" or base in allowed)

    def _undo(self) -> None:
        if self.project.can_undo():
            self.project.undo()
        self.refresh()

    def _redo(self) -> None:
        if self.project.can_redo():
            self.project.redo()
        self.refresh()
