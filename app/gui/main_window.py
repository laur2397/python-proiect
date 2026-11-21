"""Fereastra principala a OCR Editor-ului (faza 6b, pasul 6b.1): J-001..J-017,
J-400..J-420.

Structura din SPEC_10 (J-400..J-420), fara identitatea vizuala ABBYY
(CLAUDE.md §6.6): titlul (J-400), bara principala in ordinea din J-401,
butonul de salvare cu formatele (J-402) active dupa modul de layout (Q-001),
panourile Pages, Image, Text si Zoom, mutabile (J-409), indicatorul de
avertismente (J-419), `Verify` gri fara caractere nesigure (J-420).

Fereastra nu contine reguli de business (CLAUDE.md §4): citeste proiectul si
cheama nucleul. Toate textele vin din traduceri (`app.gui.i18n`).

Panourile: `pages_panel.py`, `image_panel.py` (6b.2), `text_panel.py` (6b.3).
INCOMPLET, marcat: dialogurile vin in 6b.3b…6b.6.
"""

from __future__ import annotations

import itertools
from typing import Any

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QLabel,
    QMainWindow,
    QMenu,
    QToolBar,
    QToolButton,
)

from app.core.model import ExportFormat, LayoutMode
from app.gui.dialogs import VerifyDialog
from app.gui.i18n import tr
from app.gui.image_panel import ImagePanel, ZoomPanel
from app.gui.pages_panel import PANEL_WIDTH, PagesPanel
from app.gui.text_panel import TextPanel

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
        self._arrange()
        self.warnings = QLabel()
        self.warnings.setObjectName("warnings_indicator")
        self.statusBar().addWidget(self.warnings)  # J-419: stanga-jos
        self.refresh()

    # --- constructie ----------------------------------------------------------------

    def _build_actions(self) -> None:
        for key in ("new_task", "new_project", "open_project", "open", "scan", "page_up",
                    "page_down", "recognize", "undo", "redo", "arrange_side",
                    "arrange_stacked", "verify", "options", "exit", "save_project",
                    "save_project_as", "close_project", "table_tools", "mark_verified"):
            action = QAction(tr(f"action.{key}"), self)
            action.setObjectName(key)
            self.actions[key] = action
        self.actions["verify"].setShortcut("Ctrl+F7")  # O-003
        self.actions["verify"].triggered.connect(self.verify)
        self.actions["mark_verified"].setShortcut("Ctrl+T")  # O-011
        self.actions["mark_verified"].triggered.connect(self.mark_verified)
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
            "view": ("arrange_side", "arrange_stacked", None, "table_tools"),
            "recognize": ("recognize", "verify", "mark_verified"),
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
        self.pages_panel = PagesPanel(self.project)
        self.pages_list = self.pages_panel.list
        self.pages_panel.page_activated.connect(self.go_to_page)
        self.pages_panel.changed.connect(self.refresh)
        self.pages_panel.message.connect(self.show_message)
        self.pages_dock = self._dock("pages", self.pages_panel,
                                     Qt.DockWidgetArea.LeftDockWidgetArea)
        self.image_panel = ImagePanel(self.project)
        self.image_view = self.image_panel.view
        self.image_view.changed.connect(self._areas_changed)
        self.image_view.message.connect(self.show_message)
        self.setCentralWidget(self.image_panel)
        self.text_panel = TextPanel(self.project)
        self.text_view = self.text_panel.view
        self.text_panel.changed.connect(self._text_changed)
        self.text_panel.message.connect(self.show_message)
        self.text_panel.word_selected.connect(self._word_selected)
        self.image_view.clicked.connect(self._image_clicked)
        self.text_dock = self._dock("text", self.text_panel,
                                    Qt.DockWidgetArea.RightDockWidgetArea)
        self.zoom_panel = ZoomPanel(self.image_view)
        self.zoom_dock = self._dock("zoom", self.zoom_panel,
                                    Qt.DockWidgetArea.RightDockWidgetArea)
        self.image_panel.zoom_pane_toggle.toggled.connect(self.zoom_dock.setVisible)
        # O-064: uneltele de tabel se adauga din View > Toolbars
        tools = self.actions["table_tools"]
        tools.setCheckable(True)
        tools.toggled.connect(self.text_panel.table_bar.setVisible)

    def _arrange(self) -> None:
        """Imaginea ia partea cea mai mare; Pages ingust (J-403), Text si Zoom in dreapta."""
        width = max(self.width(), 1200)
        self.resizeDocks([self.pages_dock, self.text_dock],
                         [PANEL_WIDTH + 40, int(width * 0.35)], Qt.Orientation.Horizontal)
        self.resizeDocks([self.text_dock, self.zoom_dock], [600, 200],
                         Qt.Orientation.Vertical)

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if not getattr(self, "_arranged", False) and self.isVisible():
            self._arranged = True
            self._arrange()

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
        self.image_panel.set_page(self.project.page(self._current) if total else None)
        self._show_page()

    def _show_page(self) -> None:
        pages = self.project.pages
        total = len(pages)
        self.page_counter.setText(tr("action.page_counter", n=self._current if total else 0,
                                     total=total))
        self.actions["page_up"].setEnabled(self._current > 1)
        self.actions["page_down"].setEnabled(self._current < total)
        self.text_panel.set_page(self.project.page(self._current) if total else None)

    def update_title(self) -> None:
        """J-400: `<proiect> - DocuLens OCR Editor`; proiect nou: fara titlu N."""
        name = self.project.name or tr("window.untitled", n=self._untitled)
        self.setWindowTitle(tr("window.title", project=name))

    def refresh(self) -> None:
        """Totul din starea proiectului: titlul, paginile, contorul, butoanele."""
        self.update_title()
        pages = self.project.pages
        self.pages_panel.refresh(self._current)
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

    def show_message(self, text: str) -> None:
        self.statusBar().showMessage(text, 8000)

    def _areas_changed(self) -> None:
        """O zona s-a schimbat: textul paginii, starea si undo se recitesc (N-026)."""
        self.refresh()

    def _text_changed(self) -> None:
        """Textul s-a schimbat in panoul Text: starea paginii si undo se recitesc."""
        self.refresh()

    # O-021: sincronizarea dintre panouri
    def _word_selected(self, word: Any) -> None:
        self.image_view.show_word(word.bbox)
        center = word.bbox
        self.zoom_panel.follow(QPointF(center.x + center.w / 2, center.y + center.h / 2))

    def _image_clicked(self, point: QPointF) -> None:
        page = self.image_view.page
        if page is None:
            return
        for word in page.iter_words():
            box = word.bbox
            if box.x <= point.x() < box.x + box.w and box.y <= point.y() < box.y + box.h:
                self.text_panel.select_word(word)
                return

    # --- verificarea (O-003, O-011) --------------------------------------------------

    def verify(self) -> VerifyDialog | None:
        """`Verify Text...`: dialogul nemodal; fara cuvinte nesigure → mesaj."""
        self.text_panel.commit()
        dialog = VerifyDialog(self.project, self)
        dialog.word_changed.connect(self._show_word)
        dialog.changed.connect(self.refresh)
        if not dialog.start():
            self.show_message(tr("verify.done"))
            return None
        self.verify_dialog = dialog
        dialog.show()
        return dialog

    def _show_word(self, word: Any) -> None:
        for page in self.project.pages:
            if any(w.id == word.id for w in page.iter_words()):
                self.go_to_page(page.page_number)
                self.text_panel.select_word(word)
                return

    def mark_verified(self) -> None:
        """O-011 (`Ctrl+T`): pagina curenta devine verificata."""
        from app.core.text.editor import TextEditor

        if self.project.pages:
            self.text_panel.commit()
            TextEditor(self.project).mark_verified(self.project.page(self._current))
            self.refresh()

    def _undo(self) -> None:
        if self.project.can_undo():
            self.project.undo()
        self.refresh()

    def _redo(self) -> None:
        if self.project.can_redo():
            self.project.redo()
        self.refresh()
