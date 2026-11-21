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
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QToolBar,
    QToolButton,
)

from app.core.errors import CoreError
from app.core.model import AreaType, ExportFormat, LayoutMode
from app.gui.dialogs import VerifyDialog
from app.gui.document_actions import DocumentActions
from app.gui.i18n import tr, tr_error
from app.gui.image_editor import ImageEditor
from app.gui.image_panel import ImagePanel, ZoomPanel
from app.gui.options_dialog import OptionsDialog
from app.gui.pages_panel import PANEL_WIDTH, PagesPanel
from app.gui.progress import run_with_progress
from app.gui.text_panel import TextPanel

SHORTCUTS = {
    "new_task": "Ctrl+N", "open": "Ctrl+O", "scan": "Ctrl+K",
    "save_page_images": "Ctrl+Alt+S", "close_project": "Ctrl+W",
    "new_project": "Ctrl+Shift+N", "open_project": "Ctrl+Shift+O",
    "save_project": "Ctrl+Shift+S", "exit": "Ctrl+Q", "undo": "Ctrl+Z", "redo": "Ctrl+Y",
    "edit_images": "Ctrl+I", "page_down": "Ctrl+Down", "page_up": "Ctrl+Up",
    "first_page": "Ctrl+Home", "last_page": "Ctrl+End", "recognize": "Ctrl+Shift+R",
    "recognize_page": "Ctrl+R", "analyze": "Ctrl+Shift+E", "analyze_page": "Ctrl+E",
    "verify": "Ctrl+F7", "mark_verified": "Ctrl+T", "options": "Ctrl+>",
    "area_type_recognition": "Ctrl+1", "area_type_text": "Ctrl+2", "area_type_table": "Ctrl+3",
    "area_type_picture": "Ctrl+4", "area_type_barcode": "Ctrl+5",
    "area_type_background_picture": "Ctrl+6",
}
"""SPEC_09 A.3: scurtaturile OCR Editor-ului (O-003, O-011, L-001 si restul meniurilor)."""

AreaType_MENU = (AreaType.RECOGNITION, AreaType.TEXT, AreaType.TABLE, AreaType.PICTURE,
                 AreaType.BARCODE, AreaType.BACKGROUND_PICTURE)
"""Meniul Area, in ordinea scurtaturilor Ctrl+1…Ctrl+6."""

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
        self.ocr_engine: Any = None
        """Motorul OCR; None = Tesseract (testele pun un motor scriptat)."""
        self.actions: dict[str, QAction] = {}
        self.toolbar_items: list[str] = []
        self.setObjectName("main_window")
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_panels()
        self.documents = DocumentActions(self)
        self._build_document_actions()
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
                    "save_project_as", "close_project", "table_tools", "mark_verified",
                    "edit_images", "recognize_page", "analyze", "analyze_page",
                    "first_page", "last_page", "save_page_images",
                    *(f"area_type_{k.value}" for k in AreaType)):
            action = QAction(tr(f"action.{key}"), self)
            action.setObjectName(key)
            self.actions[key] = action
        self.actions["verify"].triggered.connect(self.verify)
        self.actions["mark_verified"].triggered.connect(self.mark_verified)
        self.actions["edit_images"].triggered.connect(self.open_image_editor)
        self.actions["options"].triggered.connect(lambda: self.open_options())
        for key, slot in (("new_project", self.new_project), ("open_project", self.open_project),
                          ("open", self.open_images), ("recognize", self.recognize),
                          ("save_project", self.save_project),
                          ("save_project_as", self.save_project_as),
                          ("close_project", self.close_project)):
            self.actions[key].triggered.connect(lambda _=False, f=slot: f())
        self.actions["recognize_page"].triggered.connect(lambda: self.recognize([self._current]))
        self.actions["analyze"].triggered.connect(lambda: self.analyze())
        self.actions["analyze_page"].triggered.connect(lambda: self.analyze([self._current]))
        self.actions["first_page"].triggered.connect(lambda: self.go_to_page(1))
        self.actions["last_page"].triggered.connect(
            lambda: self.go_to_page(len(self.project.pages)))
        self.actions["save_page_images"].triggered.connect(
            lambda: self.save_page_images(self.pages_panel.selected_numbers()))
        for kind in AreaType:  # M-017, SPEC_09 A.3 meniul Area
            self.actions[f"area_type_{kind.value}"].triggered.connect(
                lambda _=False, k=kind: self.image_view.change_type(k))
        for key, shortcut in SHORTCUTS.items():
            self.actions[key].setShortcut(shortcut)
        self.actions["new_task"].setEnabled(False)  # INCOMPLET: Lansatorul, faza 6c
        self.actions["scan"].setEnabled(False)  # INCOMPLET: scanarea, faza 6d
        self.actions["undo"].triggered.connect(self._undo)
        self.actions["redo"].triggered.connect(self._redo)
        self.actions["exit"].triggered.connect(self.close)
        self.actions["page_up"].triggered.connect(lambda: self.go_to_page(self._current - 1))
        self.actions["page_down"].triggered.connect(lambda: self.go_to_page(self._current + 1))

    def _build_menus(self) -> None:
        layout: dict[str, tuple[str | None, ...]] = {
            "file": ("new_task", "open", "scan", "save_page_images", "close_project", None,
                     "new_project", "open_project", "save_project", "save_project_as", None,
                     "exit"),
            "edit": ("undo", "redo", None, "edit_images"),
            "view": ("arrange_side", "arrange_stacked", None, "table_tools", None,
                     "page_down", "page_up", "first_page", "last_page"),
            "recognize": ("recognize", "recognize_page", "analyze", "analyze_page", None,
                          "verify", "mark_verified"),
            "area": tuple(f"area_type_{k.value}" for k in AreaType_MENU),
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
                self.language_combo.activated.connect(self._language_chosen)
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

    def _build_document_actions(self) -> None:
        """Q-100 (salvarea), Q-040…Q-050 (trimiterea, e-mailul, tiparirea)."""
        docs = self.documents
        self.save_button.clicked.connect(lambda: docs.save_document())
        for key, action in self.save_actions.items():
            action.triggered.connect(lambda _=False, k=key: docs.save_document(k))
        items: list[tuple[str, Any, str | None]] = [
            ("save_document", lambda: docs.save_document(), None),
            ("send_pdf_editor", docs.send_to_pdf_editor, None),
            ("send_word", lambda: docs.send_to_application(ExportFormat.DOCX), None),
            ("send_excel", lambda: docs.send_to_application(ExportFormat.XLSX), None),
            ("send_powerpoint", lambda: docs.send_to_application(ExportFormat.PPTX), None),
            ("send_browser", lambda: docs.send_to_application(ExportFormat.HTML), None),
            ("send_clipboard", docs.send_to_clipboard, None),
            ("email_document", lambda: docs.email_document(), "Ctrl+M"),
            ("email_images", lambda: docs.email_images(), "Ctrl+Alt+M"),
            ("send_kindle", lambda: docs.send_to_kindle(), None),
            ("print_text", lambda: docs.print_text(), "Ctrl+P"),
            ("print_image", lambda: docs.print_images(), "Ctrl+Alt+P"),
        ]
        for key, slot, shortcut in items:
            action = QAction(tr(f"action.{key}"), self)
            action.setObjectName(key)
            if shortcut:
                action.setShortcut(shortcut)
            action.triggered.connect(lambda _=False, f=slot: f())
            self.actions[key] = action
        menu = self.menus["file"]
        first = menu.actions()[4] if len(menu.actions()) > 4 else None
        menu.insertAction(first, self.actions["save_document"])
        send_menu = QMenu(tr("menu.send_to"), self)
        send_menu.setObjectName("menu_send_to")
        for key in ("send_pdf_editor", "send_word", "send_excel", "send_powerpoint",
                    "send_browser", "send_clipboard", "send_kindle"):
            send_menu.addAction(self.actions[key])
        email_menu = QMenu(tr("menu.email"), self)
        email_menu.setObjectName("menu_email")
        email_menu.addAction(self.actions["email_document"])
        email_menu.addAction(self.actions["email_images"])
        menu.insertMenu(first, send_menu)
        menu.insertMenu(first, email_menu)
        menu.insertAction(first, self.actions["print_text"])
        menu.insertAction(first, self.actions["print_image"])
        self.menus["send_to"], self.menus["email"] = send_menu, email_menu
        # Q-030…Q-032: imaginile paginilor din panoul Pages si din panoul Image
        for action, numbers in ((self.pages_panel.actions["save"],
                                 lambda: self.pages_panel.selected_numbers()),
                                (self.image_panel.actions["save_page"],
                                 lambda: [self._current])):
            action.setEnabled(True)
            action.triggered.connect(lambda _=False, n=numbers: self.save_page_images(n()))

    def pick_image_target(self) -> Path | None:
        path, _ = QFileDialog.getSaveFileName(self, tr("save.images_title"), "",
                                              tr("save.images_filter"))
        return Path(path) if path else None

    def save_page_images(self, numbers: list[int], target: Path | None = None) -> list[Path]:
        target = target or self.pick_image_target()
        if target is None or not numbers:
            return []
        fmt = {".tif": ExportFormat.TIFF, ".tiff": ExportFormat.TIFF,
               ".jpg": ExportFormat.JPEG, ".jpeg": ExportFormat.JPEG}.get(
            target.suffix.lower(), ExportFormat.PNG)
        written = self.documents.save_page_images(numbers, target, fmt)
        if written:
            self.show_message(tr("save.saved", n=len(written)))
        return written

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
        self.image_editor = ImageEditor(self.project, self.pages_panel.selected_numbers)
        self.image_editor.exited.connect(self.close_image_editor)
        self.image_editor.changed.connect(self._image_edited)
        self.image_editor.message.connect(self.show_message)
        self.image_editor.next_page.connect(lambda: self.go_to_page(self._current + 1))
        for key, slot in (("recognize_page", lambda: self.recognize([self._current])),
                          ("analyze_page", lambda: self.analyze([self._current]))):
            self.image_panel.actions[key].setEnabled(True)
            self.image_panel.actions[key].triggered.connect(lambda _=False, f=slot: f())
        edit_image = self.image_panel.actions["edit_image"]
        edit_image.setEnabled(True)  # L-001: butonul din bara panoului Image
        edit_image.triggered.connect(self.open_image_editor)
        self.center = QStackedWidget()
        self.center.addWidget(self.image_panel)
        self.center.addWidget(self.image_editor)
        self.setCentralWidget(self.center)
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
        page = self.project.page(self._current) if total else None
        self.image_panel.set_page(page)
        if self.editing_images:
            self.image_editor.set_page(page)
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
        number = getattr(self.project, "untitled_number", None) or self._untitled
        name = self.project.name or tr("window.untitled", n=number)
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
        self._fill_languages()
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
        dialog.options_requested.connect(lambda: self.open_options("areas"))  # O-009
        dialog.changed.connect(self.refresh)
        if not dialog.start():
            self.show_message(tr("verify.done"))
            return None
        self.verify_dialog = dialog
        dialog.show()
        return dialog

    # --- Options (X-400) ---------------------------------------------------------------

    def open_options(self, tab: str = "general", *, modal: bool = True) -> OptionsDialog:
        dialog = OptionsDialog(self.context, self.project, tab=tab, parent=self)
        dialog.applied.connect(self._options_applied)
        self.options_dialog = dialog
        if modal:
            dialog.exec()
        return dialog

    def _options_applied(self) -> None:
        """Culorile zonelor, fontul textului, limbile: totul se redeseneaza."""
        self.refresh()
        self.text_panel.render()
        self.image_view.viewport().update()

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


    # --- proiectul (J-030…J-032) ---------------------------------------------------------

    def set_project(self, project: Any) -> None:
        """Toate panourile trec pe proiectul nou."""
        self.project = project
        for holder in (self.pages_panel, self.image_panel, self.image_view, self.text_panel,
                       self.image_editor):
            holder.project = project
        self.image_view.page = None
        self.text_panel.page = None
        self._current = 1
        if self.editing_images:
            self.center.setCurrentWidget(self.image_panel)
        self.refresh()

    def ask_save(self) -> str:
        """`save`, `discard` sau `cancel`; testele inlocuiesc dialogul."""
        box = QMessageBox(QMessageBox.Icon.Question, tr("app.name"),
                          tr("project.save_changes"), parent=self)
        save = box.addButton(tr("project.save"), QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(tr("project.discard"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("project.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        return "save" if clicked is save else "discard" if clicked is discard else "cancel"

    def pick_folder(self, title_key: str) -> Path | None:
        folder = QFileDialog.getExistingDirectory(self, tr(title_key))
        return Path(folder) if folder else None

    def pick_files(self) -> list[Path]:
        files, _ = QFileDialog.getOpenFileNames(self, tr("open.title"), "",
                                                tr("open.filter"))
        return [Path(f) for f in files]

    def ask_password(self, name: str) -> str | None:
        text, ok = QInputDialog.getText(self, tr("open.password_title"),
                                        tr("open.password", file=name),
                                        QLineEdit.EchoMode.Password)
        return text if ok else None

    def confirm_discard(self) -> bool:
        """Inainte de a inchide proiectul curent: salvare, renuntare sau anulare."""
        self.text_panel.commit()
        if not self.project.is_modified:
            return True
        answer = self.ask_save()
        if answer == "save":
            return self.save_project()
        return answer == "discard"

    def new_project(self) -> bool:
        from app.core.project import OcrProject

        if not self.confirm_discard():
            return False
        old = self.project
        self.set_project(OcrProject.create(context=self.context))
        old.close()
        return True

    def open_project(self, path: Path | None = None) -> bool:
        from app.core.project import OcrProject

        if not self.confirm_discard():
            return False
        path = path or self.pick_folder("project.open_title")
        if path is None:
            return False
        try:
            project = OcrProject.open(path, context=self.context)
        except CoreError as exc:
            self.show_message(tr_error(exc))
            return False
        old = self.project
        self.set_project(project)
        old.close()
        return True

    def save_project(self) -> bool:
        if self.project.path is None:
            return self.save_project_as()
        return self._save(None)

    def save_project_as(self, path: Path | None = None) -> bool:
        path = path or self.pick_folder("project.save_title")
        return path is not None and self._save(path)

    def _save(self, path: Path | None) -> bool:
        self.text_panel.commit()
        try:
            self.project.save(path)
        except CoreError as exc:
            self.show_message(tr_error(exc))
            return False
        except (FileExistsError, OSError):
            self.show_message(tr("project.save_failed"))
            return False
        self.update_title()
        self.show_message(tr("project.saved"))
        return True

    def close_project(self) -> bool:
        """J-0xx: inchiderea lasa un proiect nou, gol."""
        return self.new_project()

    def closeEvent(self, event: Any) -> None:
        if self.confirm_discard():
            event.accept()
        else:
            event.ignore()

    # --- imaginile si recunoasterea (J-0xx, N-0xx) -------------------------------------

    def open_images(self, paths: list[Path] | None = None) -> int:
        """Imagini si PDF-uri adaugate la proiect, cu progres; prelucrarea automata
        (J-051, X-011) o face nucleul dupa setari."""
        paths = paths if paths is not None else self.pick_files()
        if not paths:
            return 0
        before = len(self.project.pages)
        result = run_with_progress(
            tr("open.title"),
            lambda progress, cancel: self.project.add_images(
                paths, password=self.ask_password, progress=progress, cancel=cancel),
            self)
        if result is not None:
            _, errors = result
            if errors:
                self.show_message(tr("open.failed", n=len(errors),
                                     error=tr_error(errors[0][1])))
        added = len(self.project.pages) - before
        if added:
            self._current = before + 1
        self.refresh()
        return added

    def recognize(self, numbers: list[int] | None = None) -> list[int]:
        """Recunoasterea cu progres si anulare (N-027, N-028); pagina fara zone se
        analizeaza intai (N-004)."""
        from app.core.ocr.service import RecognitionService

        if not self.project.pages:
            return []
        self.text_panel.commit()
        try:
            service = RecognitionService(self.project, engine=self.ocr_engine)
            done = run_with_progress(
                tr("recognize.title"),
                lambda progress, cancel: service.recognize_pages(
                    numbers, skip_recognized=numbers is None, progress=progress,
                    cancel=cancel), self)
        except CoreError as exc:
            self.show_message(tr_error(exc))
            done = None
        self.refresh()
        return list(done or [])

    def analyze(self, numbers: list[int] | None = None) -> None:
        if not self.project.pages:
            return
        chosen = numbers or [p.page_number for p in self.project.pages]
        try:
            self.project.analyze_pages(chosen)
        except CoreError as exc:
            self.show_message(tr_error(exc))
        self.refresh()

    # --- limbile documentului (J-401) ----------------------------------------------------

    def _fill_languages(self) -> None:
        from app.gui.options_dialog import language_name

        current = list(self.project.settings().ocr_settings().languages)
        recent = [c for c in self.context.settings.get("lang.recent") or () if c not in current]
        combo = self.language_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(" + ".join(language_name(c) for c in current), current)
        for code in recent[:8]:
            combo.addItem(language_name(code), [code])
        combo.addItem(tr("action.more_languages"), None)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _language_chosen(self, index: int) -> None:
        codes = self.language_combo.itemData(index)
        if codes is None:  # `More languages...`
            self.open_options("languages")
        else:  # recunoasterea citeste limbile din setarile proiectului (X-040, X-042)
            settings = self.project.settings()
            settings.set("lang.mode", "manual")
            settings.set("lang.manual", list(codes))
            self.project.languages = codes
        self.refresh()

    # --- Image Editor (L-001, L-002) ---------------------------------------------------

    @property
    def editing_images(self) -> bool:
        return self.center.currentWidget() is self.image_editor

    def open_image_editor(self) -> None:
        if not self.project.pages:
            return
        self.text_panel.commit()
        self.center.setCurrentWidget(self.image_editor)
        self.image_editor.set_page(self.project.page(self._current))

    def close_image_editor(self) -> None:
        """L-002: modificarile raman aplicate."""
        self.center.setCurrentWidget(self.image_panel)
        self.refresh()

    def _image_edited(self) -> None:
        self.refresh()

    def _undo(self) -> None:
        if self.project.can_undo():
            self.project.undo()
        self.refresh()

    def _redo(self) -> None:
        if self.project.can_redo():
            self.project.redo()
        self.refresh()
