"""Fereastra PDF Editor (faza 7, pasul 7.7b): B-002…B-027, B-037…B-039,
B-043, B-200…B-209, B-303…B-306, X-201, I-024.

Structura dupa B-200: nu are bara de meniu clasica, ci un buton hamburger
(B-303) cu meniul principal si cinci tab-uri de ribbon: `Document`,
`Organize Pages`, `Edit Content`, `Security`, `Form Editor`. In dreapta sus:
setarile, ajutorul si restrangerea ribbonului (B-201, B-304); pe randul al
doilea `Undo`, `Redo` si `Comments (N)` (B-202, B-305). Stanga: bara verticala
cu panourile (B-208), jos: navigarea si zoom-ul (B-209). Documentele deschise
stau in tab-uri (B-043). Scurtaturile sunt cele din SPEC_09 A.2 (X-201).

INCOMPLET, marcat (comenzile se vad, dar sunt dezactivate, cu pasul sau faza
in tooltip, dupa `LATER`): paginile (tabul `Organize Pages`) in faza 8;
editarea continutului si semnele de carte noi in faza 9; securitatea si
semnarea in faza 10; formularele in faza 11; compararea in faza 12.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.applog import get_logger
from app.core.errors import CoreError
from app.core.model import AnnotationData, AnnotationType, Rect
from app.gui.i18n import tr, tr_error
from app.gui.pdf_panels import (
    AttachmentsPanel,
    BookmarksPanel,
    PagesPanel,
    SignaturesPanel,
)
from app.gui.pdf_view import ZOOM_STEPS, FitMode, PdfView, Tool, ViewMode

_log = get_logger("gui.pdf_editor")

# X-201: SPEC_09 A.2, exact. Doua comenzi ale tabelului impart o combinatie si
# deci o actiune: `Copy Area as Image` = `Copy` (Ctrl+C) si `Search and Mark Up`
# = panoul `Search` (Alt+Shift+3).
SHORTCUTS: dict[str, str] = {
    # File
    "new_task": "Ctrl+N", "open": "Ctrl+O", "save": "Ctrl+S", "save_as": "Ctrl+Shift+S",
    "close": "Ctrl+W", "print": "Ctrl+P", "options": "Ctrl+>", "exit": "Ctrl+Alt+W",
    # Edit
    "undo": "Ctrl+Z", "redo": "Ctrl+Y", "cut": "Ctrl+X", "copy": "Ctrl+C",
    "copy_area_text": "Ctrl+Shift+C", "copy_area_table": "Ctrl+Alt+C", "paste": "Ctrl+V",
    "delete": "Del", "select_all": "Ctrl+A",
    # Document
    "add_note": "Ctrl+M", "highlight": "Ctrl+H", "underline": "Ctrl+Shift+U",
    "strikethrough": "Ctrl+K", "insert_text": "Ctrl+J", "recognize_document": "Ctrl+Shift+R",
    "add_bookmark": "Ctrl+D", "find": "Ctrl+F", "find_next": "F3",
    # Organize Pages
    "add_blank_page": "Ctrl+Shift+B", "add_pages_pdf": "Ctrl+Shift+P",
    "add_pages_file": "Ctrl+Shift+O", "add_pages_scanner": "Ctrl+Shift+K",
    "rotate_right": "Ctrl+Shift+>", "rotate_left": "Ctrl+Shift+<",
    "correct_orientation": "Ctrl+Shift+/", "crop_pages": "Ctrl+Shift+X",
    "replace_pages": "Ctrl+Shift+E", "move_pages": "Ctrl+Shift+M",
    "delete_pages": "Ctrl+Backspace",
    # Edit Content si Security
    "add_link": "Ctrl+L", "redaction_mode": "Ctrl+Shift+H", "erase": "Ctrl+R",
    # View
    "navigation_pane": "F5", "pane_pages": "Alt+Shift+1", "pane_bookmarks": "Alt+Shift+2",
    "pane_search": "Alt+Shift+3", "pane_attachments": "Alt+Shift+4",
    "pane_signatures": "Alt+Shift+5", "comments_pane": "F7", "zoom_in": "Ctrl++",
    "zoom_out": "Ctrl+-", "best_fit": "Ctrl+0", "actual_size": "Ctrl+1",
    "fit_width": "Ctrl+2", "go_to_page": "Ctrl+G", "next_page": "Ctrl+Down",
    "previous_page": "Ctrl+Up", "first_page": "Home", "last_page": "End", "back": "Alt+Left",
    "forward": "Alt+Right", "one_page": "Ctrl+5", "one_page_scroll": "Ctrl+6",
    "two_page": "Ctrl+7", "two_page_scroll": "Ctrl+8", "full_screen": "F11",
    # Generale
    "save_pages": "Ctrl+Alt+S", "help": "F1",
    # Edit Content (F-001, F-007; nu sunt in tabelul SPEC_09 A.2)
    "edit_content": "Ctrl+E", "text_tools": "Ctrl+T",
}

LATER: dict[str, str] = {
    "compare": "12",
}
"""Comenzile vizibile dar dezactivate, cu pasul sau faza in care vin."""

RIBBON_TABS: dict[str, tuple[str, ...]] = {
    "document": ("new_task", "open", "save", "save_as", "print", "email", "add_note", "draw",
                 "highlight", "underline", "strikethrough", "insert_text", "add_stamp",
                 "recognize_document", "compare", "select", "hand"),            # B-203
    "organize": ("selected_pages", "delete_pages", "rotate_left", "rotate_right",
                 "correct_orientation", "crop_pages", "add_blank_page", "move_pages",
                 "replace_pages", "split", "delete_blank_pages", "recognize_document",
                 "enhance", "save_as"),                                            # B-204
    "content": ("header_footer", "picture", "add_text", "add_link", "correct_skew",
                "text_layer"),                                                   # B-205
    "security": ("signature", "password_security", "watermark", "erase", "redact",
                 "delete_objects", "select", "hand"),                              # B-206
    "forms": ("text_field", "check_box", "radio_button", "dropdown_list", "list_box",
              "button", "signature_field", "highlight_fields",
              "show_field_names"),                                  # B-207, H-002, H-011
}
"""B-200: cele cinci tab-uri si comenzile lor, in ordinea din SPEC_09 F."""

ICONS = {
    "new_task": "plus", "open": "folder_open", "save": "save", "save_as": "save",
    "print": "print", "email": "send", "add_note": "list", "draw": "pencil",
    "highlight": "text", "underline": "text", "strikethrough": "text", "insert_text": "text",
    "add_stamp": "check", "recognize_document": "recognize", "compare": "compare",
    "select": "cursor", "hand": "hand", "delete_pages": "trash", "rotate_left": "rotate_left",
    "rotate_right": "rotate_right", "redact": "redact", "undo": "undo", "redo": "redo",
    "zoom_in": "zoom_in", "zoom_out": "zoom_out", "next_page": "down",
    "previous_page": "up", "options": "gear", "help": "help",
}

PANES = ("pages", "bookmarks", "search", "attachments", "signatures")
"""B-019, B-208: panourile din bara verticala, in ordine."""

TEXT_MARKUP_TYPES = (AnnotationType.HIGHLIGHT, AnnotationType.UNDERLINE,
                     AnnotationType.STRIKETHROUGH)

FORM_MODE_DISABLED = ("add_note", "draw", "highlight", "underline", "strikethrough",
                      "insert_text", "add_stamp", "select", "hand", "add_link", "redact",
                      "erase", "signature", "copy_area_text", "copy_area_table")
"""H-010: uneltele principale de PDF, dezactivate in `Form Editor`."""

UNDO_LIMIT = 50
"""Cati pasi de Undo se pastreaza pe document (E-040: minimum 50)."""

ORGANIZE_COMMANDS = ("delete_pages", "rotate_left", "rotate_right", "correct_orientation",
                     "crop_pages", "add_blank_page", "add_pages_pdf", "add_pages_file",
                     "add_pages_scanner", "move_pages", "replace_pages", "split",
                     "delete_blank_pages", "enhance")
"""Comenzile din `Organize Pages` care lucreaza pe paginile selectate (8.3)."""
SELECTED_ANNOTATION = "#2f6df6"
"""D-106: adnotarea selectata capata chenar albastru."""

FULL_SCREEN_EDGE = 24
"""B-008: la cati pixeli de marginea de jos apare bara in ecranul complet."""


@dataclass
class OpenDocument:
    document: Any
    view: PdfView
    background: list[int]
    """Paginile care asteapta recunoasterea in fundal (B-028)."""
    selection: Any = None
    """`SelectionController` al vizualizarii (C-040…C-049)."""
    tools: Any = None
    """`ToolController` al vizualizarii (D-001…D-019)."""
    undo: list[Any] = field(default_factory=list)
    """Starile documentului inainte de fiecare modificare (Undo, Ctrl+Z)."""
    redo: list[Any] = field(default_factory=list)
    organize: Any = None
    """`OrganizeView` al documentului (E-001), aratat in tabul `Organize Pages`."""
    page: Any = None
    """Tabul documentului: vizualizarea sau grila de miniaturi."""


class PdfEditorWindow(QMainWindow):
    launcher_requested = Signal()
    options_requested = Signal(str)
    """Tabul dialogului Options care se deschide ('' = primul)."""
    help_requested = Signal()
    ocr_editor_requested = Signal(object)
    """I-017: fisierele de deschis in OCR Editor (lista de cai)."""
    closed = Signal()

    def __init__(self, context: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.core.pdf.document import AUTOSAVE_INTERVAL_S
        from app.core.pdf.navigation import ScriptPolicy

        self.setObjectName("pdf_editor")
        self.context = context
        self.settings = context.settings
        self.open_documents: list[OpenDocument] = []
        self.policy = ScriptPolicy.from_settings(self.settings)
        self.actions: dict[str, QAction] = {}
        self.spawned_windows: list[PdfEditorWindow] = []
        self.content_edit: Any = None
        """F-001: `ContentEditController` cat timp e activ tabul `Edit Content`."""
        self._editing_busy = False
        self.scanner_service: Any = None
        """E-017: driverul de scanare, creat la prima nevoie."""
        self.crop: Any = None
        """E-010: `CropController` cat timp e activ modul de decupare."""
        self._insert_at: int | None = None
        """E-013: pozitia aleasa cu butonul `+` dintre miniaturi."""
        """E-036: ferestrele noi deschise din aceasta (documente din pagini)."""
        self._full_screen_state: dict[str, bool] = {}
        from app.gui.pdf_forms import FormFillController

        self.forms = FormFillController(self)
        """H-001…H-007, H-100: completarea formularelor (faza 11)."""
        from app.gui.pdf_form_design import FormDesignController

        self.form_design = FormDesignController(self)
        """H-010…H-022: tabul `Form Editor` (faza 11, pasul 11.5)."""
        self._build_actions()
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_ribbon())
        layout.addWidget(self._build_style_bar())
        layout.addWidget(self._build_crop_bar())
        layout.addWidget(self._build_text_bar())
        layout.addWidget(self._build_redact_bar())
        layout.addWidget(self._build_js_banner())
        layout.addWidget(self.forms.build_band())  # H-100
        layout.addWidget(self._build_dossier_bar())
        layout.addWidget(self._build_body(), 1)
        layout.addWidget(self._build_bottom_bar())
        self.setCentralWidget(central)
        self._background_timer = QTimer(self)
        self._background_timer.setInterval(0)
        self._background_timer.timeout.connect(self._background_step)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(AUTOSAVE_INTERVAL_S * 1000)
        self._autosave_timer.timeout.connect(self.autosave)  # I-024
        self._autosave_timer.start()
        self.resize(1280, 860)
        self._update_state()

    # --- comenzile --------------------------------------------------------------------

    def _new_action(self, key: str) -> QAction:
        from app.gui import icons

        action = QAction(tr(f"pdf.action.{key}"), self)
        action.setObjectName(f"pdf_action_{key}")
        if key in ICONS:
            action.setIcon(icons.icon(ICONS[key]))
        if key in SHORTCUTS:
            action.setShortcut(QKeySequence(SHORTCUTS[key]))
        if key in LATER:
            action.setEnabled(False)
            action.setToolTip(tr("pdf.later", step=LATER[key]))
        self.addAction(action)
        self.actions[key] = action
        return action

    def _build_actions(self) -> None:
        for key in dict.fromkeys([*SHORTCUTS, *LATER, "select", "hand", "odd_on_right",
                                  "redact", "draw", "add_stamp", "print", "email",
                                  "save_pages", "split", "delete_blank_pages", "enhance",
                                  "selected_pages", "signed_merge",
                                  "document_properties", "header_footer", "watermark",
                                  "erase", "picture", "add_text", "correct_skew",
                                  "text_layer", "password_security", "delete_objects",
                                  "signature", "load_form_data", "save_form_data",
                                  "reset_form", "highlight_fields", "show_field_names",
                                  *RIBBON_TABS["forms"]]):
            self._new_action(key)
        a = self.actions
        connect = {
            "new_task": self.launcher_requested.emit, "open": self.ask_open,
            "save": self.save, "save_as": self.save_as, "close": self.close_current,
            "options": lambda: self.options_requested.emit(""), "exit": self.close,
            "recognize_document": self.recognize_document,
            "navigation_pane": self.toggle_navigation_pane,
            "comments_pane": self.toggle_comments_pane, "go_to_page": self.ask_go_to_page,
            "full_screen": self.toggle_full_screen, "help": self.show_help,
            "print": self.print_current, "email": self.email_current,  # I-020…I-022
            "save_pages": self.save_selected_pages,  # I-006
            "select": lambda: self._set_tool(Tool.SELECT),
            "hand": lambda: self._set_tool(Tool.HAND),
            "find": lambda: self.open_search("find"),  # C-001
            "find_next": lambda: self.search_panel.next_hit(),  # C-005, F3
            "redaction_mode": lambda: self.open_search("redact"),
            "redact": self.toggle_redaction,  # G-020, G-103
            "copy": lambda: self._on_selection("copy"),  # C-042, C-044, C-047
            "copy_area_text": lambda: self._on_selection("copy_area_text"),  # C-043
            "copy_area_table": lambda: self._on_selection("copy_area_table"),  # C-045
            "select_all": lambda: self._on_selection("select_all"),
            "undo": self.undo, "redo": self.redo,
            "add_note": lambda: self.set_annotation_tool(AnnotationType.NOTE),  # D-001
            "insert_text": lambda: self.set_annotation_tool(AnnotationType.INSERT_TEXT),
            "highlight": lambda: self.markup(AnnotationType.HIGHLIGHT),  # D-004
            "underline": lambda: self.markup(AnnotationType.UNDERLINE),  # D-005
            "strikethrough": lambda: self.markup(AnnotationType.STRIKETHROUGH),  # D-006
            "delete": self._delete_command,  # D-028, D-051; E-005 in Organize Pages
            "delete_pages": self.delete_pages,  # E-005, Ctrl+Backspace
            "rotate_left": lambda: self.rotate_pages(-90),  # E-007
            "rotate_right": lambda: self.rotate_pages(90),  # E-006
            "correct_orientation": self.correct_orientation,  # E-008
            "crop_pages": self.start_crop,  # E-010
            "add_blank_page": self.add_blank_page,  # E-013
            "add_pages_pdf": self.add_pages_from_pdf,  # E-014
            "add_pages_file": self.add_pages_from_file,  # E-015
            "add_pages_scanner": self.add_pages_from_scanner,  # E-017
            "move_pages": self.move_pages_dialog,  # E-019
            "replace_pages": self.replace_pages_dialog,  # E-020
            "delete_blank_pages": self.delete_blank_pages,  # E-021…E-023
            "split": self.split_document,  # E-024…E-032
            "enhance": self.enhance_images,  # E-035
            "signed_merge": lambda: self.signed_merge(),  # E-500
            "add_bookmark": lambda: self.add_bookmark(),  # F-032, Ctrl+D
            "add_link": self.start_add_link,  # F-026, Ctrl+L
            "document_properties": self.show_properties,  # F-054, F-055
            "header_footer": lambda: self.create_header_footer(),  # F-039
            "watermark": lambda: self.add_watermark(),  # F-045
            "erase": self.start_erase,  # F-024, F-025, Ctrl+R
            "edit_content": self.enter_edit_content,  # F-001, Ctrl+E
            "text_tools": self.toggle_text_bar,  # F-007, Ctrl+T
            "add_text": self.start_add_text,  # F-011
            "picture": self.add_picture,  # F-020
            "correct_skew": self.correct_skew,  # F-017
            "text_layer": self.replace_text_layer,  # F-018
            "password_security": self.password_security,  # G-001
            "delete_objects": self.delete_objects,  # G-022, G-111
            "signature": lambda: self.start_digital_signature(),  # G-030
            "load_form_data": lambda: self.forms.load_data(),  # H-003
            "save_form_data": lambda: self.forms.save_data(),  # H-004
            "reset_form": self.forms.reset_form,  # H-005
            "cut": self.cut_block,
            "paste": self.paste_block,
        }
        for key, slot in connect.items():
            a[key].triggered.connect(slot)
        for key in ("zoom_in", "zoom_out", "next_page", "previous_page", "first_page",
                    "last_page", "back", "forward"):
            a[key].triggered.connect(lambda _c=False, m=key: self._on_view(m))
        for key, fit in (("best_fit", FitMode.BEST_FIT), ("actual_size", FitMode.ACTUAL_SIZE),
                         ("fit_width", FitMode.FIT_WIDTH)):
            a[key].triggered.connect(lambda _c=False, f=fit: self.set_fit(f))
        modes = QActionGroup(self)
        for key, mode in (("one_page", ViewMode.ONE_PAGE),
                          ("one_page_scroll", ViewMode.ONE_PAGE_SCROLLING),
                          ("two_page", ViewMode.TWO_PAGE),
                          ("two_page_scroll", ViewMode.TWO_PAGE_SCROLLING)):
            a[key].setCheckable(True)
            modes.addAction(a[key])
            a[key].triggered.connect(lambda _c=False, m=mode: self.set_mode(m))
        a["one_page_scroll"].setChecked(True)
        a["odd_on_right"].setCheckable(True)
        a["odd_on_right"].triggered.connect(self._odd_on_right)
        tools = QActionGroup(self)
        for key in ("select", "hand"):
            a[key].setCheckable(True)
            tools.addAction(a[key])
        a["select"].setChecked(True)
        for i, pane in enumerate(PANES):
            a[f"pane_{pane}"].setCheckable(True)
            a[f"pane_{pane}"].triggered.connect(lambda _c=False, n=i: self.show_pane(n))
        a["comments_pane"].setCheckable(True)
        from app.gui.pdf_form_design import TOOL_ACTIONS

        for key, kind in TOOL_ACTIONS.items():  # B-207, H-012
            a[key].setCheckable(True)
            a[key].triggered.connect(
                lambda checked, k=kind: self.form_design.set_tool(k if checked else None))
        a["highlight_fields"].setCheckable(True)  # H-002
        a["highlight_fields"].toggled.connect(self.forms.set_highlight)
        a["show_field_names"].setCheckable(True)  # H-011
        a["show_field_names"].setChecked(True)
        a["show_field_names"].toggled.connect(self.form_design.set_show_names)

    # --- ribbon-ul (B-200…B-206, B-303, B-304) ----------------------------------------

    def _build_ribbon(self) -> QWidget:
        from app.gui import icons

        self.ribbon = QFrame()
        self.ribbon.setObjectName("pdf_ribbon")
        box = QVBoxLayout(self.ribbon)
        box.setContentsMargins(4, 2, 4, 2)
        box.setSpacing(2)
        top = QHBoxLayout()
        self.hamburger = QToolButton()
        self.hamburger.setObjectName("pdf_hamburger")
        self.hamburger.setText("☰")
        self.hamburger.setToolTip(tr("pdf.menu.main"))
        self.hamburger.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.hamburger.setMenu(self._main_menu())
        top.addWidget(self.hamburger)
        self.ribbon_tabs = QTabBar()
        self.ribbon_tabs.setObjectName("pdf_ribbon_tabs")
        for key in RIBBON_TABS:
            self.ribbon_tabs.addTab(tr(f"pdf.tab.{key}"))
        top.addWidget(self.ribbon_tabs)
        top.addStretch(1)
        for key in ("options", "help"):
            button = QToolButton()
            button.setDefaultAction(self.actions[key])
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            top.addWidget(button)
        self.collapse_button = QToolButton()
        self.collapse_button.setObjectName("pdf_ribbon_collapse")
        self.collapse_button.setIcon(icons.icon("up"))
        self.collapse_button.setToolTip(tr("pdf.ribbon.collapse"))
        self.collapse_button.setCheckable(True)
        self.collapse_button.toggled.connect(self._collapse_ribbon)
        top.addWidget(self.collapse_button)
        box.addLayout(top)
        second = QHBoxLayout()
        self.ribbon_pages = QStackedWidget()
        self.ribbon_pages.setObjectName("pdf_ribbon_pages")
        self.toolbars: dict[str, QToolBar] = {}
        for key, commands in RIBBON_TABS.items():
            bar = QToolBar()
            bar.setObjectName(f"pdf_tab_{key}")
            bar.setIconSize(QSize(18, 18))
            bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            for command in commands:
                if command == "selected_pages":  # E-004, E-103
                    bar.addWidget(self._build_page_range())
                    continue
                bar.addAction(self.actions[command])
            self.toolbars[key] = bar
            self.ribbon_pages.addWidget(bar)
        self.ribbon_tabs.currentChanged.connect(self.ribbon_pages.setCurrentIndex)
        self.ribbon_tabs.currentChanged.connect(lambda _i: self._ribbon_changed())
        second.addWidget(self.ribbon_pages, 1)
        for key in ("undo", "redo"):
            button = QToolButton()
            button.setDefaultAction(self.actions[key])
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            second.addWidget(button)
        self.comments_button = QToolButton()  # B-305
        self.comments_button.setObjectName("pdf_comments_button")
        self.comments_button.setDefaultAction(self.actions["comments_pane"])
        self.comments_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        second.addWidget(self.comments_button)
        box.addLayout(second)
        return self.ribbon

    def _main_menu(self) -> QMenu:
        """B-303: meniul principal, in locul barei de meniu."""
        menu = QMenu(self)
        menu.setObjectName("pdf_main_menu")
        groups = {
            "file": ("new_task", "open", "save", "save_as", "save_pages", "close", "print",
                     "email", "document_properties", "options", "exit"),
            "edit": ("undo", "redo", "cut", "copy", "copy_area_text", "copy_area_table",
                     "paste", "delete", "select_all", "add_link"),
            "view": ("navigation_pane", "pane_pages", "pane_bookmarks", "pane_search",
                     "pane_attachments", "pane_signatures", "comments_pane", "zoom_in",
                     "zoom_out", "best_fit", "actual_size", "fit_width", "go_to_page",
                     "next_page", "previous_page", "first_page", "last_page", "back",
                     "forward", "one_page", "one_page_scroll", "two_page", "two_page_scroll",
                     "odd_on_right", "full_screen"),
            "document": ("add_note", "highlight", "underline", "strikethrough", "insert_text",
                         "recognize_document", "add_bookmark", "find", "find_next"),
            "help": ("help",),
        }
        for group, keys in groups.items():
            sub = menu.addMenu(tr(f"pdf.menu.{group}"))
            sub.setObjectName(f"pdf_menu_{group}")
            for key in keys:
                sub.addAction(self.actions[key])
            if group == "document":  # H-003…H-005: meniul datelor de formular
                data = sub.addMenu(tr("pdf.menu.form_data"))
                data.setObjectName("pdf_menu_form_data")
                for key in ("load_form_data", "save_form_data", "reset_form"):
                    data.addAction(self.actions[key])
        return menu

    # --- uneltele de adnotare si bara de stil (D-001…D-023) ----------------------------

    def _build_draw_menu(self) -> None:
        """D-009…D-019: meniul `Draw ▾` cu formele si blocul de text."""
        from app.gui.pdf_tools import DRAW_MENU

        menu = QMenu(self)
        menu.setObjectName("pdf_draw_menu")
        for kind in DRAW_MENU:
            action = menu.addAction(tr(f"annotation.{kind.value}"))
            action.setObjectName(f"pdf_draw_{kind.value}")
            action.triggered.connect(lambda _c=False, k=kind: self.set_annotation_tool(k))
        block = menu.addAction(tr("tools.text_block"))  # D-019
        block.setObjectName("pdf_draw_text_block")
        block.triggered.connect(
            lambda: self.set_annotation_tool(AnnotationType.TEXT_BOX, text_block=True))
        self.draw_menu = menu
        self.actions["draw"].triggered.connect(lambda: menu.exec(self.cursor().pos()))
        button = self.toolbars["document"].widgetForAction(self.actions["draw"])
        if isinstance(button, QToolButton):
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    # --- salvarea, trimiterea, tiparirea (I-002…I-006, I-017…I-022) -----------------

    def _attach_menu(self, key: str, menu: QMenu) -> None:
        for bar in self.toolbars.values():
            button = bar.widgetForAction(self.actions[key])
            if isinstance(button, QToolButton):
                button.setMenu(menu)
                button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

    def _build_file_menus(self) -> None:
        """`Save As ▾` (I-002…I-005) si `Recognize ▾` (B-032, I-017)."""
        save_menu = QMenu(self)
        save_menu.setObjectName("pdf_save_as_menu")
        save_menu.addAction(tr("pdf.action.save_as"), self.save_as)  # I-002
        save_menu.addAction(tr("pdf.save.searchable"), lambda: self.save_as_pdf(True))  # I-003
        save_menu.addAction(tr("pdf.save.image_only"), lambda: self.save_as_pdf(False))  # I-004
        save_menu.addAction(tr("organize.save_selected"), self.save_selected_pages)  # E-037
        save_menu.addSeparator()
        save_menu.addAction(tr("pdf.save.options"),
                            lambda: self.options_requested.emit("format"))  # I-005
        self.save_menu = save_menu
        self._attach_menu("save_as", save_menu)
        recognize_menu = QMenu(self)
        recognize_menu.setObjectName("pdf_recognize_menu")
        recognize_menu.addAction(tr("pdf.action.recognize_document"), self.recognize_document)
        recognize_menu.addAction(tr("organize.recognize_selected"),  # E-033
                                 lambda: self.recognize_document(self.selected_pages()))
        recognize_menu.addAction(tr("pdf.send_ocr.action"), self.send_to_ocr_editor)  # I-017
        recognize_menu.addAction(tr("organize.send_selected"),  # E-034
                                 lambda: self.send_to_ocr_editor(self.selected_pages()))
        self.recognize_menu = recognize_menu
        self._attach_menu("recognize_document", recognize_menu)
        add_menu = QMenu(self)  # E-013…E-017, E-038
        add_menu.setObjectName("organize_add_menu")
        for key in ("add_blank_page", "add_pages_pdf", "add_pages_file", "add_pages_scanner"):
            add_menu.addAction(self.actions[key])
        add_menu.addSeparator()
        add_menu.addAction(tr("organize.image_settings"), self.image_processing_settings)
        add_menu.addSeparator()
        add_menu.addAction(self.actions["signed_merge"])  # E-500
        self.add_menu = add_menu
        self._attach_menu("add_blank_page", add_menu)
        self.header_menu = QMenu(self)  # F-039, F-044 si sabloanele salvate
        self.header_menu.setObjectName("pdf_header_menu")
        self.header_menu.aboutToShow.connect(self._fill_header_menu)
        self._fill_header_menu()
        self._attach_menu("header_footer", self.header_menu)
        watermark_menu = QMenu(self)  # F-045, F-050
        watermark_menu.setObjectName("pdf_watermark_menu")
        watermark_menu.addAction(tr("decorate.add_watermark"), lambda: self.add_watermark())
        delete = watermark_menu.addAction(tr("decorate.delete_watermarks"),
                                          self.delete_watermarks)
        delete.setObjectName("pdf_delete_watermarks")
        self.watermark_menu = watermark_menu
        self._attach_menu("watermark", watermark_menu)
        self.signature_menu = QMenu(self)  # G-110: digitala, text, imagine
        self.signature_menu.setObjectName("pdf_signature_menu")
        self.signature_menu.aboutToShow.connect(self._fill_signature_menu)
        self._fill_signature_menu()
        self._attach_menu("signature", self.signature_menu)

    def save_as_pdf(self, searchable: bool) -> bool:
        """I-003: PDF cautabil (paginile trec prin OCR); I-004: doar-imagine."""
        from app.core.export.base import ExportOptions
        from app.core.model import LayoutMode
        from app.gui.progress import run_with_progress

        current = self.current()
        if current is None:
            return False
        target = self.ask_save_path(current.document)
        if target is None:
            return False
        options = ExportOptions(layout_mode=LayoutMode.EXACT, searchable=searchable)
        try:
            run_with_progress(tr("pdf.save.progress"),
                              lambda progress, cancel: current.document.save_as(
                                  target, options=options, context=self.context), self)
        except (CoreError, OSError, ValueError) as exc:
            self._report(exc)
            return False
        current.view.reload()
        self._after_save()
        return True

    def selected_pages(self) -> list[int]:
        """Paginile selectate: in grila din `Organize Pages`, altfel in panoul
        `Pages`; fara selectie, pagina curenta."""
        current = self.current()
        if current is not None and self.organize_mode:
            chosen = current.organize.selected_pages()
            return chosen or [current.view.current_page]
        rows = sorted({self.pages_panel.list.row(i) for i in self.pages_panel.list.selectedItems()})
        if not rows and current is not None:
            return [current.view.current_page]
        return [r + 1 for r in rows]

    def save_selected_pages(self, pages: list[int] | None = None) -> bool:
        """I-006, E-037: paginile selectate, intr-un fisier separat."""
        current = self.current()
        if current is None:
            return False
        target = self.ask_save_path(current.document)
        if target is None:
            return False
        try:
            current.document.save_as(target, pages=list(pages or self.selected_pages()))
        except (CoreError, OSError, ValueError) as exc:
            self._report(exc)
            return False
        return True

    def send_to_ocr_editor(self, pages: list[int] | None = None) -> Path | None:
        """I-017, I-018: inainte, avertismentul despre ce nu se transfera.
        E-034: numai paginile alese."""
        current = self.current()
        if current is None or not self.ask_confirm(tr("pdf.send_ocr.lost")):
            return None
        folder = Path(tempfile.mkdtemp(prefix="doculens-ocr-"))
        name = current.document.path.name if current.document.path else \
            tr("pdf.untitled") + ".pdf"
        path = current.document.export_copy(folder / name, pages=pages)
        self.ocr_editor_requested.emit([path])
        return path

    def email_current(self) -> Path | None:
        """I-020, D-053: mesaj nou cu PDF-ul atasat, in programul de e-mail."""
        from app.core.export import send

        current = self.current()
        if current is None:
            return None
        answer = self.ask_email(current.document)
        if answer is None:
            return None
        name, pages = answer
        folder = Path(tempfile.mkdtemp(prefix="doculens-mail-"))
        try:
            message = send.email_pdf(current.document, folder, name, pages=pages)
        except (CoreError, OSError, ValueError) as exc:
            self._report(exc)
            return None
        if not self.open_external(QUrl.fromLocalFile(str(message))):
            # D-053: fara program de e-mail, mesajul se poate salva local
            self.show_message(tr("pdf.email.no_client"))
            target = self.ask_save_path(current.document, suffix=".eml")
            if target is not None:
                target.write_bytes(message.read_bytes())
        return message

    def ask_email(self, document: Any) -> tuple[str, list[int] | None] | None:
        """D-053: numele atasamentului si paginile (toate sau cele selectate)."""
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QRadioButton,
        )

        dialog = QDialog(self)
        dialog.setObjectName("pdf_email_dialog")
        dialog.setWindowTitle(tr("pdf.action.email"))
        name = QLineEdit(document.path.stem if document.path else tr("pdf.untitled"))
        every = QRadioButton(tr("pdf.email.all_pages"))
        every.setChecked(True)
        chosen = QRadioButton(tr("pdf.email.selected_pages"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        create = buttons.addButton(tr("pdf.email.create"), QDialogButtonBox.ButtonRole.AcceptRole)
        create.setObjectName("pdf_email_create")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form = QFormLayout(dialog)
        form.addRow(tr("stamps.name"), name)
        form.addRow(every)
        form.addRow(chosen)
        form.addRow(buttons)
        if not self.exec_dialog(dialog) or not name.text().strip():
            return None
        return name.text().strip(), self.selected_pages() if chosen.isChecked() else None

    def print_current(self) -> int:
        """I-021, I-022."""
        from app.gui.pdf_print import print_document, printers_available

        current = self.current()
        if current is None:
            return 0
        self.forms.warn_required()  # H-023
        if not printers_available():
            self.show_message(tr("pdf.print.no_printer"))  # I-021
            return 0
        chosen = self.choose_print(current.document)
        if chosen is None:
            return 0
        printer, settings = chosen
        try:
            return print_document(current.document, printer, settings,
                                  flip=lambda: self.ask_confirm(tr("pdf.print.flip")))
        except (CoreError, RuntimeError) as exc:
            self._report(exc)
            return 0

    def choose_print(self, document: Any) -> tuple[Any, Any] | None:
        """Dialogul de tiparire, cu tabul propriu (I-022)."""
        from PySide6.QtPrintSupport import QAbstractPrintDialog, QPrintDialog, QPrinter

        from app.gui.pdf_print import PrintOptions

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        options = PrintOptions()
        dialog = QPrintDialog(printer, self)
        dialog.setOptionTabs([options])
        dialog.setMinMax(1, document.page_count)
        dialog.setOption(QAbstractPrintDialog.PrintDialogOption.PrintSelection,
                         len(self.selected_pages()) > 1)
        if not self.exec_dialog(dialog):
            return None
        mode = dialog.printRange()
        if mode == QAbstractPrintDialog.PrintRange.PageRange:
            pages = list(range(dialog.fromPage(), dialog.toPage() + 1))
        elif mode == QAbstractPrintDialog.PrintRange.Selection:
            pages = self.selected_pages()
        else:
            pages = None
        return printer, options.settings(pages)

    def show_help(self) -> bool:
        """F1: manualul local (ca in Lansator, A-006)."""
        from app.gui.launcher import MANUAL

        self.help_requested.emit()
        if MANUAL.is_file():
            return bool(self.open_external(QUrl.fromLocalFile(str(MANUAL))))
        self.show_message(tr("launcher.help_missing", path=str(MANUAL)))
        return False

    # --- stampilele (D-045…D-052) -----------------------------------------------------

    def _build_stamp_menu(self) -> None:
        """D-045, D-047, D-048, D-050: meniul `Add Stamp ▾`."""
        from app.core.pdf.stamps import StampLibrary

        self.stamps = StampLibrary(self.context.app_db)
        self.pending_stamp: Any = None
        menu = QMenu(self)
        menu.setObjectName("pdf_stamp_menu")
        menu.aboutToShow.connect(self._fill_stamp_menu)
        self.stamp_menu = menu
        self._fill_stamp_menu()
        self.actions["add_stamp"].triggered.connect(lambda: menu.exec(self.cursor().pos()))
        button = self.toolbars["document"].widgetForAction(self.actions["add_stamp"])
        if isinstance(button, QToolButton):
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    def _fill_stamp_menu(self) -> None:
        from app.gui.pdf_stamps import stamp_label

        menu = self.stamp_menu
        menu.clear()
        for stamp in self.stamps.stamps():
            action = menu.addAction(stamp_label(stamp))
            action.setObjectName(f"pdf_stamp_{stamp.name}")
            action.triggered.connect(lambda _c=False, n=stamp.name: self.choose_stamp(n))
        menu.addSeparator()
        menu.addAction(tr("stamps.menu.create_image"), self.create_image_stamp)
        menu.addAction(tr("stamps.menu.create_text"), self.create_text_stamp)
        menu.addAction(tr("stamps.menu.manage"), self.manage_stamps)

    def choose_stamp(self, name: str) -> None:
        """Stampila aleasa se pune cu un clic pe pagina (D-045)."""
        self.pending_stamp = self.stamps.get(name)
        self.set_annotation_tool(AnnotationType.STAMP)

    def _place_stamp(self, page: int, x: float, y: float) -> None:
        from app.core.pdf.stamps import place_stamp
        from app.gui.i18n import language
        from app.gui.pdf_comments import default_author

        stamp = self.pending_stamp
        if stamp is None:
            return
        self.modify(lambda doc: place_stamp(doc, page, stamp, (x, y),
                                            author=default_author(self.settings) or None,
                                            language=language()))

    def create_image_stamp(self) -> None:
        """D-047, D-108."""
        from app.gui.pdf_stamps import ImageStampDialog

        dialog = ImageStampDialog(self)
        if not self.exec_dialog(dialog) or not dialog.image:
            return
        try:
            stamp = self.stamps.create_image(dialog.name.text(), dialog.image,
                                             scale=dialog.scale)
        except (CoreError, ValueError) as exc:
            self._report(exc)
            return
        self.choose_stamp(stamp.name)

    def create_text_stamp(self) -> None:
        """D-048, D-109, D-110."""
        from app.gui.pdf_stamps import TextStampDialog

        dialog = TextStampDialog(self)
        if not self.exec_dialog(dialog):
            return
        try:
            stamp = self.stamps.create_text(
                dialog.name.text(), dialog.text.toPlainText(),
                font_size=float(dialog.size.value()), text_color=dialog.color,
                border_style=dialog.border_value())
        except (CoreError, ValueError) as exc:
            self._report(exc)
            return
        self.choose_stamp(stamp.name)

    def edit_stamp(self, stamp: Any) -> None:
        """D-050 `Edit...` (cele livrate nu se modifica: eroare in nucleu)."""
        from app.gui.pdf_stamps import ImageStampDialog, TextStampDialog

        if stamp.is_builtin:
            self.stamps.update(stamp.name)  # ridica BuiltinNotEditableError
        if stamp.kind == "text":
            dialog = TextStampDialog(self, stamp=stamp)
            if self.exec_dialog(dialog):
                self.stamps.update(stamp.name, new_name=dialog.name.text(),
                                   text=dialog.text.toPlainText(),
                                   font_size=float(dialog.size.value()),
                                   text_color=dialog.color, border_style=dialog.border_value())
            return
        image_dialog = ImageStampDialog(self, name=stamp.name, image=stamp.image)
        if self.exec_dialog(image_dialog):
            self.stamps.update(stamp.name, new_name=image_dialog.name.text(),
                               image=image_dialog.image, scale=image_dialog.scale)

    def manage_stamps(self) -> None:
        """D-050: `Use` alege stampila pentru urmatorul clic."""
        from app.gui.pdf_stamps import ManageStampsDialog

        dialog = ManageStampsDialog(self.stamps, self)
        if self.exec_dialog(dialog) and dialog.chosen is not None:
            self.choose_stamp(dialog.chosen.name)

    def exec_dialog(self, dialog: Any) -> bool:
        from PySide6.QtWidgets import QDialog

        return dialog.exec() == QDialog.DialogCode.Accepted

    def _build_style_bar(self) -> QWidget:
        """D-018, D-020: setarile de desen, inainte de desenare."""
        from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox

        from app.gui.pdf_tools import DrawStyle

        self.draw_style = DrawStyle()
        self.annotation_tool: AnnotationType | None = None
        self._build_draw_menu()
        self._build_stamp_menu()
        self._build_file_menus()
        bar = QToolBar()
        bar.setObjectName("pdf_style_bar")
        self.style_color = QToolButton()
        self.style_color.setObjectName("style_color")
        self.style_color.setText(tr("style.color"))
        self.style_color.clicked.connect(lambda: self._pick_color("color"))
        self.style_width = QDoubleSpinBox()
        self.style_width.setObjectName("style_width")
        self.style_width.setRange(0.5, 12.0)  # D-016
        self.style_width.setSingleStep(0.5)
        self.style_width.setValue(self.draw_style.line_width)
        self.style_width.setSuffix(" pt")
        self.style_width.valueChanged.connect(
            lambda v: setattr(self.draw_style, "line_width", float(v)))
        self.style_fill = QToolButton()
        self.style_fill.setObjectName("style_fill")
        self.style_fill.setText(tr("style.fill"))
        self.style_fill.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        fill_menu = QMenu(self.style_fill)
        fill_menu.addAction(tr("style.no_fill"),
                            lambda: setattr(self.draw_style, "fill_color", None))
        fill_menu.addAction(tr("style.color"), lambda: self._pick_color("fill_color"))
        self.style_fill.setMenu(fill_menu)
        self.style_opacity = QSpinBox()
        self.style_opacity.setObjectName("style_opacity")
        self.style_opacity.setRange(10, 100)
        self.style_opacity.setSuffix(" %")
        self.style_opacity.setValue(100)
        self.style_opacity.valueChanged.connect(
            lambda v: setattr(self.draw_style, "opacity", v / 100))
        self.style_font = QSpinBox()
        self.style_font.setObjectName("style_font_size")
        self.style_font.setRange(6, 72)
        self.style_font.setValue(int(self.draw_style.font_size))
        self.style_font.valueChanged.connect(
            lambda v: setattr(self.draw_style, "font_size", float(v)))
        self.style_text_color = QToolButton()
        self.style_text_color.setObjectName("style_text_color")
        self.style_text_color.setText(tr("style.text_color"))
        self.style_text_color.clicked.connect(lambda: self._pick_color("text_color"))
        for label_key, widget in (("style.width", self.style_width),
                                  ("style.opacity", self.style_opacity),
                                  ("style.font_size", self.style_font)):
            bar.addWidget(QLabel(tr(label_key)))
            bar.addWidget(widget)
        for widget in (self.style_color, self.style_fill, self.style_text_color):
            bar.addWidget(widget)
        self.style_bar = bar
        bar.hide()
        return bar

    def _pick_color(self, field_name: str) -> None:
        color = self.ask_color(getattr(self.draw_style, field_name) or "#000000")
        if color:
            setattr(self.draw_style, field_name, color)

    def set_annotation_tool(self, kind: AnnotationType | None, *,
                            text_block: bool = False) -> None:
        """Unealta de adnotare activa (None = inapoi la `Select`)."""
        self.annotation_tool = kind
        for entry in self.open_documents:
            if entry.tools is not None:
                entry.tools.set_tool(kind, text_block=text_block)
            if kind is not None:
                entry.view.set_tool(Tool.SELECT)
        self.style_bar.setVisible(kind is not None and kind not in (
            AnnotationType.NOTE, AnnotationType.STAMP, *TEXT_MARKUP_TYPES))

    def markup(self, kind: AnnotationType) -> None:
        """D-004…D-006: pe textul selectat; fara selectie, unealta de marcare."""
        current = self.current()
        if current is None:
            return
        selection = current.selection
        if selection.mode != "text" or selection.text_start is None:
            self.set_annotation_tool(kind)
            return
        start, end = sorted((selection.text_start, selection.text_end))
        datas = []
        for page in range(start[0], end[0] + 1):
            text = current.document.page_text(page)
            first = start[1] if page == start[0] else 0
            last = end[1] + 1 if page == end[0] else len(text.text)
            rects = text.span_rects(first, max(0, last - first))
            if rects:
                datas.append(AnnotationData(None, kind, page, {"rects": rects}))
        selection.clear()
        if datas:
            self.modify(lambda doc: [doc.add_annotation(self._styled(d)) for d in datas])

    def _styled(self, data: AnnotationData) -> AnnotationData:
        """Autorul implicit (D-032) si culoarea marcajelor din setari (C-010, D-106)."""
        from dataclasses import replace

        from app.core.pdf.markup import default_color
        from app.gui.pdf_comments import default_author

        color = data.color
        if color is None and data.annot_type in TEXT_MARKUP_TYPES:
            color = default_color(self.settings, data.annot_type)
        return replace(data, color=color, author=data.author or default_author(self.settings)
                       or None)

    def _create_annotation(self, data: AnnotationData) -> Any:
        return self.modify(lambda doc: doc.add_annotation(self._styled(data)))

    def ask_annotation_text(self, kind: AnnotationType) -> str | None:
        """D-007, D-017: textul inserat sau al casetei."""
        if kind is AnnotationType.TEXT_BOX:
            text, ok = QInputDialog.getMultiLineText(self, tr("tools.text_box"),
                                                     tr("tools.text_label"))
        else:
            text, ok = QInputDialog.getText(self, tr("annotation.insert_text"),
                                            tr("tools.text_label"))
        return text if ok and text else None

    def ask_color(self, current: str) -> str | None:
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog

        color = QColorDialog.getColor(QColor(current), self, tr("style.color"))
        return color.name().upper() if color.isValid() else None

    def _collapse_ribbon(self, collapsed: bool) -> None:
        """B-304: ribbon-ul se restrange la randul cu tab-urile."""
        self.ribbon_pages.setVisible(not collapsed)

    # --- banda JavaScript (B-037…B-039) -----------------------------------------------

    def _build_js_banner(self) -> QWidget:
        self.js_banner = QFrame()
        self.js_banner.setObjectName("pdf_js_banner")
        self.js_banner.setProperty("warning", True)
        row = QHBoxLayout(self.js_banner)
        row.setContentsMargins(10, 4, 10, 4)
        row.addWidget(QLabel(tr("pdf.js.banner")), 1)
        self.js_document_button = QPushButton(tr("pdf.js.enable_document"))
        self.js_document_button.setObjectName("pdf_js_enable_document")
        self.js_document_button.clicked.connect(self.enable_javascript_for_document)
        self.js_all_button = QPushButton(tr("pdf.js.enable_all"))
        self.js_all_button.setObjectName("pdf_js_enable_all")
        self.js_all_button.clicked.connect(lambda: self.options_requested.emit("other"))
        row.addWidget(self.js_document_button)
        row.addWidget(self.js_all_button)
        self.js_banner.hide()
        return self.js_banner

    def enable_javascript_for_document(self) -> None:
        """B-038: numai documentul curent; scripturile documentului ruleaza acum."""
        current = self.current()
        if current is not None:
            self.policy.enable_for(current.document)
            outcome = self.forms.scripts().run_document_open()
            if outcome.commands or outcome.alerts or outcome.timed_out:
                self.forms.perform(outcome)
            self.forms.changed()
        self.js_banner.hide()

    def ask_form_data_file(self) -> Path | None:
        """H-003: fisierul FDF sau XFDF."""
        from app.gui.pdf_forms import ask_form_data_file

        return ask_form_data_file(self)

    def ask_form_data_target(self, document: Any) -> tuple[Path, str] | None:
        """H-004: fisierul si formatul (FDF, XFDF, HTML)."""
        from app.gui.pdf_forms import ask_form_data_target

        return ask_form_data_target(self, document)

    def _update_js_banner(self) -> None:
        from app.core.pdf.navigation import has_javascript

        current = self.current()
        show = current is not None and has_javascript(current.document) and \
            not self.policy.allows(current.document)
        self.js_banner.setVisible(show)

    # --- corpul: panouri, documente, comentarii ---------------------------------------

    def _build_body(self) -> QWidget:
        from app.gui import icons

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("pdf_body")
        self.side_bar = QToolBar()  # B-208: circa 30 px
        self.side_bar.setObjectName("pdf_side_bar")
        self.side_bar.setOrientation(Qt.Orientation.Vertical)
        self.side_bar.setIconSize(QSize(18, 18))
        self.side_bar.setFixedWidth(32)
        glyphs = {"pages": "file", "bookmarks": "list", "search": "search",
                  "attachments": "link", "signatures": "check"}
        for pane in PANES:
            action = self.actions[f"pane_{pane}"]
            action.setIcon(icons.icon(glyphs[pane]))
            self.side_bar.addAction(action)
        self.pages_panel = PagesPanel()
        self.bookmarks_panel = BookmarksPanel()
        from app.gui.pdf_search import SearchPanel

        self.search_panel = SearchPanel(self.context, self.current)
        self.search_panel.document_changed.connect(self._after_modify)
        self.search_panel.before_change = self.record_undo
        self.search_panel.hit_activated.connect(self._go_to)
        self.search_panel.closed.connect(self.nav_stack_hide)
        self.attachments_panel = AttachmentsPanel()
        self.signatures_panel = SignaturesPanel()
        self.nav_stack = QStackedWidget()
        self.nav_stack.setObjectName("pdf_navigation_pane")
        for panel in (self.pages_panel, self.bookmarks_panel, self.search_panel,
                      self.attachments_panel, self.signatures_panel):
            self.nav_stack.addWidget(panel)
        self.nav_stack.setMinimumWidth(150)  # B-027: intre 150 si 600 px
        self.nav_stack.setMaximumWidth(600)
        self.left = QWidget()
        left_row = QHBoxLayout(self.left)
        left_row.setContentsMargins(0, 0, 0, 0)
        left_row.setSpacing(0)
        left_row.addWidget(self.side_bar)
        left_row.addWidget(self.nav_stack, 1)
        self.tabs = QTabWidget()  # B-043
        self.tabs.setObjectName("pdf_documents")
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_document)
        self.tabs.currentChanged.connect(lambda _i: self._document_changed())
        self.empty_page = QLabel(tr("pdf.no_document"))
        self.empty_page.setObjectName("pdf_no_document")
        self.empty_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.center = QStackedWidget()
        self.center.addWidget(self.empty_page)
        self.center.addWidget(self.tabs)
        from app.gui.pdf_comments import CommentsPanel

        self.comments_panel = CommentsPanel(self.settings, self.current, self.modify)
        self.comments_panel.hide()
        self.comments_panel.annotation_selected.connect(self.select_annotation)
        self.comments_panel.closed.connect(self.toggle_comments_pane)
        self.selected_annotation: int | None = None
        self.splitter.addWidget(self.left)
        self.splitter.addWidget(self.center)
        self.splitter.addWidget(self.comments_panel)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([240, 900, 260])
        self.pages_panel.page_requested.connect(self._go_to)
        self.bookmarks_panel.page_requested.connect(lambda n, _y: self._go_to(n))
        self.signatures_panel.page_requested.connect(self._go_to)
        self.comments_panel.page_requested.connect(self._go_to)
        self.attachments_panel.open_requested.connect(self.open_attachment)
        self.attachments_panel.save_requested.connect(self.save_attachment)
        self.attachments_panel.add_requested.connect(self.add_attachment)  # F-052
        self.attachments_panel.rename_requested.connect(self.rename_attachment)
        self.attachments_panel.delete_requested.connect(self.delete_attachment)
        self.bookmarks_panel.command.connect(self.bookmark_command)  # F-032…F-038
        self.signatures_panel.properties_requested.connect(self.signature_properties)
        self.signatures_panel.remove_requested.connect(self.remove_signature)
        self.bookmarks_panel.moved.connect(self.move_bookmark)  # F-036
        self._wire_pages_panel()
        self.show_pane(0)
        return self.splitter

    def show_pane(self, index: int) -> None:
        """B-019…B-024: panoul ales; un clic pe panoul deschis il inchide."""
        action = self.actions[f"pane_{PANES[index]}"]
        if self.nav_stack.isVisibleTo(self) and self.nav_stack.currentIndex() == index \
                and not action.isChecked():
            self.nav_stack.hide()
            return
        for i, pane in enumerate(PANES):
            self.actions[f"pane_{pane}"].setChecked(i == index)
        self.nav_stack.setCurrentIndex(index)
        self.nav_stack.show()

    def nav_stack_hide(self) -> None:
        self.nav_stack.hide()
        for pane in PANES:
            self.actions[f"pane_{pane}"].setChecked(False)

    def open_search(self, tab: str) -> None:
        """C-001: panoul de cautare, pe tabul cerut, cu cursorul in camp."""
        self.show_pane(PANES.index("search"))
        self.search_panel.show_tab(tab)

    def toggle_navigation_pane(self) -> None:
        """B-019, F5."""
        self.nav_stack.setVisible(not self.nav_stack.isVisibleTo(self))

    def toggle_comments_pane(self) -> None:
        """B-025, B-305, F7."""
        visible = not self.comments_panel.isVisibleTo(self)
        self.comments_panel.setVisible(visible)
        self.actions["comments_pane"].setChecked(visible)

    # --- bara de jos (B-014, B-209, B-306) --------------------------------------------

    def _build_bottom_bar(self) -> QWidget:
        from app.gui import icons

        self.bottom_bar = QFrame()
        self.bottom_bar.setObjectName("pdf_bottom_bar")
        row = QHBoxLayout(self.bottom_bar)
        row.setContentsMargins(6, 2, 6, 2)
        row.addStretch(1)
        for key in ("previous_page", "next_page"):
            button = QToolButton()
            button.setDefaultAction(self.actions[key])
            row.addWidget(button)
        self.page_field = QLineEdit()
        self.page_field.setObjectName("pdf_page_field")
        self.page_field.setFixedWidth(52)
        self.page_field.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.page_field.returnPressed.connect(self._page_entered)
        self.page_total = QLabel("/ 0")
        self.page_total.setObjectName("pdf_page_total")
        row.addWidget(self.page_field)
        row.addWidget(self.page_total)
        self.fit_combo = QComboBox()
        self.fit_combo.setObjectName("pdf_fit_combo")
        for fit in (FitMode.BEST_FIT, FitMode.ACTUAL_SIZE, FitMode.FIT_WIDTH):
            self.fit_combo.addItem(tr(f"pdf.fit.{fit.value}"), fit.value)
        self.fit_combo.activated.connect(
            lambda i: self.set_fit(FitMode(self.fit_combo.itemData(i))))
        row.addWidget(self.fit_combo)
        self.mode_button = QToolButton()
        self.mode_button.setObjectName("pdf_mode_button")
        self.mode_button.setIcon(icons.icon("columns"))
        self.mode_button.setToolTip(tr("pdf.view_mode"))
        self.mode_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        modes = QMenu(self.mode_button)
        for key in ("one_page", "one_page_scroll", "two_page", "two_page_scroll"):
            modes.addAction(self.actions[key])
        modes.addSeparator()
        modes.addAction(self.actions["odd_on_right"])
        self.mode_button.setMenu(modes)
        row.addWidget(self.mode_button)
        self.zoom_combo = QComboBox()
        self.zoom_combo.setObjectName("pdf_zoom_combo")
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for step in ZOOM_STEPS:
            self.zoom_combo.addItem(f"{step}%", step)
        self.zoom_combo.activated.connect(lambda i: self.set_zoom(self.zoom_combo.itemData(i)))
        self.zoom_combo.lineEdit().returnPressed.connect(self._zoom_entered)
        row.addWidget(self.zoom_combo)
        for key in ("zoom_out", "zoom_in"):
            button = QToolButton()
            button.setDefaultAction(self.actions[key])
            row.addWidget(button)
        return self.bottom_bar

    def _page_entered(self) -> None:
        """B-014: in afara intervalului, campul devine rosu."""
        current = self.current()
        try:
            page = int(self.page_field.text().strip())
        except ValueError:
            page = 0
        ok = current is not None and current.view.go_to_page(page)
        self.page_field.setProperty("invalid", not ok)
        self.page_field.setStyleSheet("" if ok else
                                      "QLineEdit { border: 1px solid #b42318;"
                                      " background: #fde8e6; }")

    def _zoom_entered(self) -> None:
        text = self.zoom_combo.currentText().replace("%", "").strip()
        try:
            self.set_zoom(int(float(text)))
        except ValueError:
            self._update_state()

    # --- documentele (B-043) ----------------------------------------------------------

    def current(self) -> OpenDocument | None:
        index = self.tabs.currentIndex()
        return self.open_documents[index] if 0 <= index < len(self.open_documents) else None

    def add_document(self, document: Any) -> OpenDocument:
        view = PdfView()
        view.set_document(document)
        view.set_fit(FitMode.FIT_WIDTH)
        view.overlays.append(self.search_panel.paint_hits)  # C-108
        from app.gui.pdf_selection import SelectionController

        entry = OpenDocument(document, view, [])
        entry.selection = SelectionController(view, self.context)
        entry.selection.text_menu_hook = self._selection_menu  # F-033
        entry.selection.changed.connect(self._update_state)
        entry.selection.message.connect(lambda text: self.show_message(text))
        entry.selection.double_clicked.connect(self._double_clicked)  # D-008
        entry.selection.grab_annotation = self._grab_annotation  # D-052
        entry.selection.drop_annotation = self._drop_annotation
        from app.gui.pdf_tools import ToolController

        entry.tools = ToolController(view, self._create_annotation, self.ask_annotation_text,
                                     lambda: self.draw_style, self._place_stamp)
        entry.tools.finished.connect(lambda: self.set_annotation_tool(None))
        entry.tools.set_tool(self.annotation_tool)
        view.page_clicked.connect(self._page_clicked)
        view.viewport().installEventFilter(self)  # F-028…F-030: meniul linkurilor
        self.forms.attach(view)  # H-002, H-040: evidentierea, mouse-ul peste campuri
        view.overlays.append(self.paint_selected_annotation)
        self.open_documents.append(entry)
        view.page_changed.connect(lambda _n: self._update_state())
        view.page_changed.connect(self._edit_page_changed)
        view.zoom_changed.connect(lambda _z: self._update_state())
        view.history_changed.connect(self._update_state)
        view.mode_changed.connect(lambda _m: self._update_state())
        from app.gui.pdf_organize import OrganizeView

        entry.organize = OrganizeView()  # E-001
        entry.organize.selection_changed.connect(self._organize_selection_changed)
        entry.organize.move_requested.connect(self.move_pages_to)  # E-018
        entry.organize.page_command.connect(self._organize_command)  # E-009
        entry.organize.page_activated.connect(self._open_page_from_grid)
        entry.organize.insert_requested.connect(self._insert_here)  # E-013
        grid = entry.organize.grid
        grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        grid.customContextMenuRequested.connect(
            lambda pos, g=grid: self._grid_context_menu(g, pos))
        entry.page = QStackedWidget()
        entry.page.addWidget(view)
        entry.page.addWidget(entry.organize)
        title = document.path.name if document.path else tr("pdf.untitled")
        self.tabs.addTab(entry.page, title)
        self.center.setCurrentWidget(self.tabs)
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        self._start_background(entry)
        self._document_changed()
        return entry

    def open_path(self, path: Path) -> OpenDocument | None:
        """A-010: deschide PDF-ul intr-un tab nou; cere parola daca e nevoie,
        de cel mult trei ori (A-011)."""
        from app.core.pdf.document import PdfDocument

        attempts = {"n": 0}

        def password(_path: str) -> str | None:
            attempts["n"] += 1
            return self.ask_password() if attempts["n"] <= 3 else None

        try:
            document = PdfDocument.open(Path(path), password=password)
        except CoreError as exc:
            self.show_message(tr_error(exc))
            return None
        except FileNotFoundError:
            self.show_message(tr("pdf.file_missing", path=str(path)))
            return None
        return self.add_document(document)

    def close_document(self, index: int) -> bool:
        """Inchide documentul; modificarile nesalvate se confirma (I-023)."""
        if not 0 <= index < len(self.open_documents):
            return True
        entry = self.open_documents[index]
        if entry.document.is_modified:
            answer = self.ask_save(entry.document)
            if answer == "cancel":
                return False
            if answer == "save" and not self._save_document(entry.document):
                return False
        self.policy.forget(entry.document)
        entry.document.close()
        del self.open_documents[index]
        self.tabs.removeTab(index)
        entry.page.deleteLater()
        if not self.open_documents:
            self.center.setCurrentWidget(self.empty_page)
        self._document_changed()
        return True

    def close_current(self) -> None:
        self.close_document(self.tabs.currentIndex())

    # --- Organize Pages (E-001…E-009, E-018, E-033…E-037) ------------------------------

    @property
    def organize_mode(self) -> bool:
        """E-001: e activ tabul `Organize Pages`."""
        keys = list(RIBBON_TABS)
        index = self.ribbon_tabs.currentIndex()
        return 0 <= index < len(keys) and keys[index] == "organize"

    def _ribbon_changed(self) -> None:
        """E-001: in `Organize Pages`, centrul arata grila de miniaturi mari.
        F-001: in `Edit Content` incepe editarea; se iese comutand pe alt tab."""
        if self.crop is not None:
            self.exit_crop()
        self._sync_edit_content()
        organize = self.organize_mode
        for entry in self.open_documents:
            entry.page.setCurrentIndex(1 if organize else 0)
        current = self.current()
        if organize and current is not None:
            if current.organize.document is not current.document:
                current.organize.set_document(current.document)
                current.organize.select_pages([current.view.current_page])
            else:
                current.organize.refresh()
        if self.form_editor_mode and current is not None:  # H-010
            self.forms.cancel_editing()
            self.form_design.enter(current.view)
        else:
            self.form_design.exit()
        self._update_state()

    def _build_page_range(self) -> QWidget:
        """E-004, E-103: campul `Selected pages`, editabil, cu lista derulanta."""
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(4, 0, 8, 0)
        row.addWidget(QLabel(tr("organize.selected_pages")))
        self.page_range = QComboBox()
        self.page_range.setObjectName("organize_page_range")
        self.page_range.setEditable(True)
        self.page_range.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.page_range.setMinimumWidth(150)
        for key in ("all", "odd", "even"):
            self.page_range.addItem(tr(f"organize.range.{key}"), key)
        self.page_range.setCurrentIndex(-1)
        self.page_range.lineEdit().setPlaceholderText("2, 3, 5-7")
        self.page_range.lineEdit().returnPressed.connect(self.apply_page_range)
        self.page_range.activated.connect(lambda _i: self.apply_page_range())
        row.addWidget(self.page_range)
        return box

    def apply_page_range(self, text: str | None = None) -> list[int]:
        """E-004: selectia din textul tastat. Numerele din afara documentului se
        ignora, cu avertisment; un text de nerecunoscut coloreaza campul."""
        from app.core.pdf.organize import format_range, parse_range

        current = self.current()
        if current is None:
            return []
        text = self.page_range.currentText() if text is None else text
        index = self.page_range.findText(text)
        if index >= 0:
            text = str(self.page_range.itemData(index))
        try:
            result = parse_range(text, current.document.page_count)
        except ValueError:
            self.page_range.setStyleSheet("QComboBox { color: #c62828; }")
            self.show_message(tr("organize.range.invalid"))
            return []
        self.page_range.setStyleSheet("")
        if result.ignored:
            self.show_message(tr("organize.range.ignored", pages=format_range(result.ignored)))
        pages = list(result.pages)
        if self.organize_mode:
            current.organize.select_pages(pages)
        else:
            self.pages_panel.list.clearSelection()
            for n in pages:
                self.pages_panel.list.item(n - 1).setSelected(True)
        return pages

    def _organize_selection_changed(self) -> None:
        """E-103: campul se actualizeaza la selectia cu mouse-ul (`2, 5`)."""
        from app.core.pdf.organize import format_range

        current = self.current()
        if current is None or not self.organize_mode:
            return
        if not self.page_range.lineEdit().hasFocus():
            self.page_range.setEditText(format_range(current.organize.selected_pages()))
            self.page_range.setStyleSheet("")
        self._update_state()

    def _panel_pages(self) -> list[int]:
        """Paginile selectate in panoul `Pages` (cel putin cea curenta)."""
        rows = sorted({self.pages_panel.list.row(i) for i in self.pages_panel.list.selectedItems()})
        current = self.current()
        if not rows and current is not None:
            return [current.view.current_page]
        return [r + 1 for r in rows]

    def _grid_pages(self) -> list[int]:
        current = self.current()
        if current is None:
            return []
        return current.organize.selected_pages() or [current.view.current_page]

    def _delete_command(self) -> None:
        """`Del`: in `Organize Pages` sterge paginile (E-005), in `Edit Content`
        blocurile (F-012), altfel adnotarea."""
        if self.form_design.active:  # H-021
            self.form_design.delete()
        elif self.content_edit is not None and self.content_edit.active() is not None:
            self.delete_blocks()
        elif self.organize_mode:
            self.delete_pages()
        else:
            self.delete_selected_annotation()

    def _organize(self, operation: Any) -> Any:
        """O operatie `PageOrganizer` pe documentul curent, cu pas de Undo."""
        from app.core.pdf.organize import PageOrganizer

        return self.modify(lambda document: operation(PageOrganizer(document)))

    def delete_pages(self, pages: list[int] | None = None) -> bool:
        """E-005: paginile dispar si restul se renumeroteaza; ultima pagina nu
        se poate sterge (mesaj)."""
        current = self.current()
        if current is None:
            return False
        chosen = sorted(set(pages or self.selected_pages()))
        if len(chosen) >= current.document.page_count:
            self.show_message(tr("organize.last_page"))
            return False
        if self._organize(lambda o: o.delete(chosen) or True) is None:
            return False
        if self.organize_mode:
            current.organize.select_pages([min(chosen[0], current.document.page_count)])
        return True

    def rotate_pages(self, degrees: int, pages: list[int] | None = None) -> bool:
        """E-006, E-007: rotatia se scrie in pagina."""
        chosen = list(pages or self.selected_pages())
        return self._organize(lambda o: o.rotate(chosen, degrees) or True) is not None

    def correct_orientation(self, pages: list[int] | None = None) -> dict[int, int] | None:
        """E-008: orientarea dupa text; paginile fara text raman neschimbate."""
        chosen = list(pages or self.selected_pages())
        applied = self._organize(lambda o: o.correct_orientation(chosen))
        if applied == {}:
            self.show_message(tr("organize.orientation.unchanged"))
        return applied

    def move_pages_to(self, pages: list[int], to: int) -> list[int] | None:
        """E-018, E-019: paginile ajung inaintea paginii `to` (1..n+1)."""
        current = self.current()
        moved = self._organize(lambda o: o.move(pages, to))
        if moved and current is not None and self.organize_mode:
            current.organize.select_pages(moved)
        return moved

    def _organize_command(self, key: str, pages: list[int]) -> None:
        """E-009, E-104: comenzile mini-toolbarului, pe pagina de sub mouse."""
        if key == "delete":
            self.delete_pages(pages)
        else:
            self.rotate_pages(-90 if key == "rotate_left" else 90, pages)

    def _open_page_from_grid(self, page: int) -> None:
        self.ribbon_tabs.setCurrentIndex(0)
        self._go_to(page)

    def create_pdf_from_pages(self, pages: list[int] | None = None) -> PdfEditorWindow | None:
        """E-036: document nou din paginile alese, intr-o fereastra noua de PDF
        Editor."""
        from app.core.pdf.organize import PageOrganizer

        current = self.current()
        if current is None:
            return None
        try:
            document = PageOrganizer(current.document).extract_to_new_document(
                list(pages or self.selected_pages()))
        except (CoreError, ValueError) as exc:
            self._report(exc)
            return None
        window = PdfEditorWindow(self.context)
        for signal in ("launcher_requested", "options_requested", "help_requested",
                       "ocr_editor_requested"):
            getattr(window, signal).connect(getattr(self, signal).emit)
        window.add_document(document)
        window.show()
        self.spawned_windows.append(window)
        window.closed.connect(lambda: self.spawned_windows.remove(window)
                              if window in self.spawned_windows else None)
        return window

    def pages_menu(self, source: Any) -> QMenu:
        """Meniul paginilor (panoul `Pages`, B-308 `...`, si grila): `source()`
        intoarce paginile pe care lucreaza."""
        menu = QMenu(self)
        menu.setObjectName("organize_pages_menu")
        entries = (
            ("pdf.action.delete_pages", lambda: self.delete_pages(source())),  # E-005
            ("pdf.action.rotate_left", lambda: self.rotate_pages(-90, source())),
            ("pdf.action.rotate_right", lambda: self.rotate_pages(90, source())),
            None,
            ("organize.recognize_selected",  # E-033
             lambda: self.recognize_document(source())),
            ("organize.send_selected", lambda: self.send_to_ocr_editor(source())),  # E-034
            ("organize.create_pdf", lambda: self.create_pdf_from_pages(source())),  # E-036
            ("organize.save_selected", lambda: self.save_selected_pages(source())),  # E-037
        )
        for entry in entries:
            if entry is None:
                menu.addSeparator()
                continue
            key, slot = entry
            action = menu.addAction(tr(key))
            action.setObjectName(f"organize_menu_{key.rsplit('.', 1)[-1]}")
            action.triggered.connect(slot)
        return menu

    def _wire_pages_panel(self) -> None:
        """B-308: rotirile si `...` din panoul `Pages`; meniul contextual (E-034,
        E-036, E-037)."""
        panel = self.pages_panel
        panel.actions["rotate_left"].triggered.connect(
            lambda: self.rotate_pages(-90, self._panel_pages()))
        panel.actions["rotate_right"].triggered.connect(
            lambda: self.rotate_pages(90, self._panel_pages()))
        self.panel_menu = self.pages_menu(self._panel_pages)
        panel.more.setMenu(self.panel_menu)
        panel.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        panel.list.customContextMenuRequested.connect(
            lambda pos: self.panel_menu.popup(panel.list.viewport().mapToGlobal(pos)))
        self.grid_menu = self.pages_menu(self._grid_pages)

    def _grid_context_menu(self, grid: Any, pos: Any) -> None:
        self.grid_menu.popup(grid.viewport().mapToGlobal(pos))

    # --- semne de carte, linkuri, atasamente, proprietati (F-026…F-038, F-052…F-055) ---

    def ask_text(self, title_key: str, label_key: str, default: str = "") -> str | None:
        text, ok = QInputDialog.getText(self, tr(title_key), tr(label_key), text=default)
        return text if ok else None

    def ask_open_file(self, title_key: str) -> Path | None:
        name, _ = QFileDialog.getOpenFileName(self, tr(title_key))
        return Path(name) if name else None

    def _bookmark_target(self) -> tuple[int, float | None]:
        current = self.current()
        return (current.view.current_page if current is not None else 1), None

    def add_bookmark(self, title: str | None = None, page: int | None = None,
                     y: float | None = None) -> Any:
        """F-032: tinta implicita e inceputul paginii curente; F-035: noul semn de
        carte vine dupa cel selectat, la acelasi nivel."""
        from app.core.model import BookmarkData

        current = self.current()
        if current is None:
            return None
        if title is None:
            title = self.ask_text("bookmarks.add", "bookmarks.name",
                                  tr("bookmarks.untitled"))
            if title is None:
                return None
        if page is None:
            page, y = self._bookmark_target()
        after = self.bookmarks_panel.current_id()
        created = self.modify(lambda d: d.add_bookmark(BookmarkData(None, title, target_page=page,
                                                                    target_y=y), after_id=after))
        if created is not None:
            self.show_pane(PANES.index("bookmarks"))
            self.bookmarks_panel.select_id(created.id)
        return created

    def add_bookmark_from_selection(self) -> Any:
        """F-033: tinta e selectia, iar textul selectat devine numele."""
        current = self.current()
        if current is None or current.selection is None:
            return None
        anchor = current.selection.selection_anchor()
        title = " ".join(current.selection.selected_text().split())[:120]
        if anchor is None or not title:
            return None
        return self.add_bookmark(title, anchor[0], anchor[1])

    def _selection_menu(self, menu: QMenu) -> None:
        action = menu.addAction(tr("bookmarks.add_selection"), self.add_bookmark_from_selection)
        action.setObjectName("selection_add_bookmark")

    def bookmark_command(self, key: str) -> None:
        """F-032…F-038: comenzile panoului `Bookmarks`."""
        from app.core.pdf import outline

        panel = self.bookmarks_panel
        if key == "add":
            self.add_bookmark()
            return
        bm_id = panel.current_id()
        if bm_id is None:
            return
        if key == "rename":
            item = panel.tree.currentItem()
            title = self.ask_text("bookmarks.rename", "bookmarks.name", item.text(0))
            if title is not None:
                self.modify(lambda d: d.rename_bookmark(bm_id, title))
        elif key == "delete":  # F-038: cu copiii
            ids = panel.selected_ids()
            if self.ask_confirm(tr("bookmarks.delete_confirm", n=len(ids))):
                self.modify(lambda d: d.delete_bookmarks(ids))
        elif key == "level_left":
            self.modify(lambda d: outline.outdent(d, bm_id))
        elif key == "level_right":
            self.modify(lambda d: outline.indent(d, bm_id))
        elif key == "set_destination":  # F-034
            page, y = self._bookmark_target()
            self.modify(lambda d: d.set_bookmark_destination(bm_id, page, y))

    def move_bookmark(self, bm_id: int, parent_id: int | None, index: int) -> None:
        """F-036: tragerea in panou; aspectul documentului nu se schimba."""
        if self.modify(lambda d: d.move_bookmark(bm_id, parent_id, index) or True) is None:
            current = self.current()
            self.bookmarks_panel.set_document(current.document if current else None)

    # F-026, F-027
    def start_add_link(self) -> None:
        """`Add Link...`: se trage zona linkului, apoi `Link Editor`."""
        from app.gui.pdf_content import AreaPicker

        current = self.current()
        if current is None:
            return
        self._stop_picker()
        self.picker = AreaPicker(current.view, self._link_area_chosen)

    def _stop_picker(self) -> None:
        picker = getattr(self, "picker", None)
        if picker is not None:
            picker.detach()
            self.picker = None

    def _link_area_chosen(self, page: int, rect: Rect) -> None:
        self._stop_picker()
        self.add_link(page, rect)

    def add_link(self, page: int, rect: Rect) -> bool:
        from app.gui.pdf_content import LinkEditorDialog

        current = self.current()
        if current is None:
            return False
        dialog = LinkEditorDialog(current.document.page_count, None, self)
        if not self.exec_dialog(dialog):
            return False
        target = dialog.target()
        return self.modify(lambda d: d.add_link(page, rect, target) or True) is not None

    def link_at(self, page: int, x: float, y: float) -> Any:
        current = self.current()
        if current is None:
            return None
        for link in current.document.links(page):
            for r in link.rects:
                if r.x <= x <= r.x + r.w and r.y <= y <= r.y + r.h:
                    return r
        return None

    def _link_menu(self, watched: Any, event: Any) -> bool:
        """F-028…F-030: `Edit Link...`, `Copy Link`, `Remove Link`."""
        from PySide6.QtCore import QPointF

        current = self.current()
        if current is None or watched is not current.view.viewport():
            return False
        view = current.view
        point = QPointF(event.pos()) + QPointF(view.horizontalScrollBar().value(),
                                               view.verticalScrollBar().value())
        hit = view.view_to_page(point)
        if hit is None:
            return False
        page, x, y = hit
        rect = self.link_at(page, x, y)
        if rect is None:
            return False
        menu = self.link_menu(page, rect)
        menu.popup(event.globalPos())
        return True

    def link_menu(self, page: int, rect: Rect) -> QMenu:
        menu = QMenu(self)
        menu.setObjectName("pdf_link_menu")
        for key, slot in (("edit", lambda: self.edit_link(page, rect)),
                          ("copy", lambda: self.copy_link(page, rect)),
                          ("remove", lambda: self.remove_link(page, rect))):
            action = menu.addAction(tr(f"pdflink.{key}"))
            action.setObjectName(f"link_{key}")
            action.triggered.connect(slot)
        return menu

    def edit_link(self, page: int, rect: Rect) -> bool:
        """F-028: se redeschide `Link Editor`."""
        from app.core.pdf.navigation import link_target
        from app.gui.pdf_content import LinkEditorDialog

        current = self.current()
        if current is None:
            return False
        dialog = LinkEditorDialog(current.document.page_count,
                                  link_target(current.document, page, rect), self)
        if not self.exec_dialog(dialog):
            return False
        target = dialog.target()
        return self.modify(lambda d: d.update_link(page, rect, target) or True) is not None

    def copy_link(self, page: int, rect: Rect) -> str:
        """F-029: adresa in clipboard (pentru o pagina: `#page=N`)."""
        from app.core.pdf.navigation import link_target

        current = self.current()
        if current is None:
            return ""
        target = link_target(current.document, page, rect)
        text = target.get("uri") or f"#page={target.get('page')}"
        QApplication.clipboard().setText(text)
        return text

    def remove_link(self, page: int, rect: Rect) -> bool:
        """F-030."""
        return self.modify(lambda d: d.delete_link(page, rect) or True) is not None

    # F-052
    def add_attachment(self) -> str | None:
        path = self.ask_open_file("pdf.attachments.add")
        if path is None:
            return None
        return self.modify(lambda d: d.add_attachment(path))

    def rename_attachment(self, name: str) -> bool:
        new_name = self.ask_text("pdf.attachments.rename", "pdf.attachments.name", name)
        if new_name is None or new_name == name:
            return False
        return self.modify(lambda d: d.rename_attachment(name, new_name) or True) is not None

    def delete_attachment(self, name: str) -> bool:
        if not self.ask_confirm(tr("pdf.attachments.delete_confirm", name=name)):
            return False
        return self.modify(lambda d: d.delete_attachment(name) or True) is not None

    # F-054, F-055
    def show_properties(self) -> bool:
        from app.gui.pdf_content import PropertiesDialog

        current = self.current()
        if current is None:
            return False
        properties = current.document.properties()
        dialog = PropertiesDialog(properties, self)
        if not self.exec_dialog(dialog):
            return False
        changes = dialog.changes(properties)
        if not changes or not properties["editable"]:
            return False
        return self.modify(lambda d: d.set_metadata(**changes) or True) is not None

    # --- antet si subsol, filigran, Erase (F-024, F-025, F-039…F-050) -------------------

    def _header_store(self) -> Any:
        from app.core.pdf.decorate import HeaderFooterStore

        return HeaderFooterStore(self.context.app_db)

    def _fill_header_menu(self) -> None:
        """F-039, F-044: comenzile si sabloanele salvate (aplicate direct)."""
        menu = self.header_menu
        menu.clear()
        menu.addAction(tr("decorate.create_header"), lambda: self.create_header_footer())
        menu.addAction(tr("decorate.manage"), lambda: self.manage_headers())
        names = self._header_store().names()
        if names:
            menu.addSeparator()
        for name in names:
            menu.addAction(name, lambda _c=False, n=name: self.create_header_footer(n))

    def create_header_footer(self, template_name: str | None = None) -> bool:
        """F-039…F-043: dialogul, apoi antetul pe paginile alese; cu `Save and
        Add`, si sablonul (nume unic)."""
        from app.core.pdf.decorate import add_header_footer
        from app.gui.pdf_content import HeaderFooterDialog

        current = self.current()
        if current is None:
            return False
        store = self._header_store()
        template = store.load(template_name) if template_name else None
        dialog = HeaderFooterDialog(current.document.page_count, self.selected_pages(),
                                    bates_next=int(self.settings.get("pdf_editor.bates_next")),
                                    template=template, parent=self)
        if not self.exec_dialog(dialog):
            return False
        hf = dialog.settings()
        try:
            pages = dialog.pages.pages()
        except ValueError:
            self.show_message(tr("organize.range.invalid"))
            return False
        if dialog.save_and_add and not self._save_template(store, hf):
            return False
        done = self.modify(lambda d: ("ok", add_header_footer(d, hf, pages=pages)))
        if done is None:
            return False
        if done[1] is not None:  # F-040: `Continue from`
            self.settings.set("pdf_editor.bates_next", int(done[1]))
        return True

    def _save_template(self, store: Any, hf: Any) -> bool:
        """F-043: numele trebuie sa fie unic; un nume folosit se cere din nou."""
        for _attempt in range(3):
            name = self.ask_text("decorate.save_and_add", "decorate.template_name")
            if name is None:
                return False
            try:
                store.save(name, hf)
                return True
            except ValueError:
                self.show_message(tr("decorate.duplicate"))
        return False

    def manage_headers(self) -> Any:
        """F-044: `Copy...`, `Edit...` (cu `Save`), `Delete`."""
        from app.gui.pdf_content import HeaderFooterDialog, ManageHeadersDialog

        store = self._header_store()
        dialog = ManageHeadersDialog(store.names(), self)

        def copy() -> None:
            name = dialog.current()
            new = self.ask_text("decorate.manage.copy", "decorate.template_name",
                                f"{name} 2") if name else None
            if name and new:
                try:
                    store.copy(name, new)
                except ValueError:
                    self.show_message(tr("decorate.duplicate"))
                dialog.set_names(store.names())

        def edit() -> None:
            name = dialog.current()
            current = self.current()
            if name is None or current is None:
                return
            editor = HeaderFooterDialog(current.document.page_count, self.selected_pages(),
                                        template=store.load(name), parent=dialog)
            if self.exec_dialog(editor):
                store.save(name, editor.settings(), replace_existing=True)

        def delete() -> None:
            name = dialog.current()
            if name and self.ask_confirm(tr("decorate.delete_template", name=name)):
                store.delete(name)
                dialog.set_names(store.names())

        dialog.buttons["copy"].clicked.connect(copy)
        dialog.buttons["edit"].clicked.connect(edit)
        dialog.buttons["delete"].clicked.connect(delete)
        self.exec_dialog(dialog)
        self._fill_header_menu()
        return dialog

    def add_watermark(self) -> int:
        """F-045…F-049: cu `Save and Add` se adauga inca un filigran."""
        from app.core.pdf.decorate import add_watermark
        from app.gui.pdf_content import WatermarkDialog

        current = self.current()
        added = 0
        while current is not None and added < 20:
            dialog = WatermarkDialog(current.document.page_count, self.selected_pages(), self)
            if not self.exec_dialog(dialog):
                break
            wm = dialog.settings()
            try:
                pages = dialog.pages.pages()
            except ValueError:
                self.show_message(tr("organize.range.invalid"))
                break
            if self.modify(lambda d, w=wm, p=pages: add_watermark(d, w, pages=p) or True) \
                    is None:
                break
            added += 1
            if not dialog.add_another:
                break
        return added

    def delete_watermarks(self) -> int:
        """F-050: toate filigranele, nu doar cele puse de DocuLens."""
        from app.core.pdf.decorate import remove_watermarks

        if self.current() is None or not self.ask_confirm(tr("decorate.delete_confirm")):
            return 0
        removed = self.modify(remove_watermarks) or 0
        self.show_message(tr("decorate.deleted", n=removed))
        return int(removed)

    def start_erase(self) -> None:
        """F-024, F-025: se trage zona; continutul ei dispare si fundalul se
        completeaza."""
        from app.gui.pdf_content import AreaPicker

        current = self.current()
        if current is None:
            return
        self._stop_picker()
        self.picker = AreaPicker(current.view, self._erase_area)

    def _erase_area(self, page: int, rect: Rect) -> None:
        self._stop_picker()
        self.erase(page, rect)

    def erase(self, page: int, rect: Rect) -> bool:
        from app.core.pdf.editor import PdfContentEditor

        return self.modify(lambda d: PdfContentEditor(d).erase_region(page, rect)
                           or True) is not None

    # --- dosarul cu semnaturile pastrate (E-500, E-509, E-512) ---------------------------

    def ask_signed_merge(self, found: Any) -> str:
        from app.gui.dossier_dialog import ask_signed_merge

        return ask_signed_merge(self, found)

    def _signatures_may_be_lost(self, sources: list[Path]) -> bool:
        """E-509: inainte de inserarea paginilor (E-014, E-015, E-020), daca
        documentul sau sursa au semnaturi, avertismentul cu trei optiuni.
        True = se continua unirea clasica."""
        from app.core.pdf.dossier import signed_among

        current = self.current()
        paths = list(sources)
        if current is not None and current.document.path is not None:
            paths.insert(0, current.document.path)
        found = signed_among(paths)
        if not found:
            return True
        choice = self.ask_signed_merge(found)
        if choice == "dossier":
            self.signed_merge(paths)
            return False
        return choice == "continue"

    def signed_merge(self, files: list[Path] | None = None) -> Path | None:
        """E-500: dosarul cu originalele neschimbate; se deschide intr-un tab nou."""
        from app.gui.dossier_dialog import DossierDialog, make_dossier

        current = self.current()
        if files is None:
            files = [current.document.path] if current is not None and \
                current.document.path is not None else []
        dialog = DossierDialog(files, self)
        if not self.exec_dialog(dialog):
            return None
        path = make_dossier(dialog, self.context, self, password=self._source_password(),
                            show=self.show_message)
        if path is not None and path.suffix.lower() == ".pdf":
            self.open_path(path)
        return path

    def _build_dossier_bar(self) -> QWidget:
        """E-512: bara de informare a unui dosar, cu butonul de verificare."""
        self.dossier_bar = QFrame()
        self.dossier_bar.setObjectName("pdf_dossier_bar")
        self.dossier_bar.setProperty("info", True)
        row = QHBoxLayout(self.dossier_bar)
        row.setContentsMargins(10, 4, 10, 4)
        self.dossier_label = QLabel()
        self.dossier_label.setObjectName("pdf_dossier_label")
        self.dossier_label.setWordWrap(True)
        row.addWidget(self.dossier_label, 1)
        self.dossier_verify = QPushButton(tr("dossier.verify"))
        self.dossier_verify.setObjectName("pdf_dossier_verify")
        self.dossier_verify.clicked.connect(self.verify_dossier)
        row.addWidget(self.dossier_verify)
        self.dossier_bar.hide()
        self._dossier_cache: dict[tuple[str, float], Any] = {}
        return self.dossier_bar

    def _dossier_report(self) -> list[Any] | None:
        from app.core.pdf import dossier

        current = self.current()
        path = current.document.path if current is not None else None
        if path is None or not path.is_file():
            return None
        key = (str(path), path.stat().st_mtime)
        if key not in self._dossier_cache:
            try:
                is_dossier = dossier.manifest(path.read_bytes()) is not None
                self._dossier_cache[key] = dossier.dossier_report(path) if is_dossier \
                    else None
            except Exception as exc:  # noqa: BLE001 - un fisier ciudat nu blocheaza
                _log.warning("dosarul nu se poate verifica: %s", exc)
                self._dossier_cache[key] = None
        return self._dossier_cache[key]

    def _update_dossier_bar(self) -> None:
        """E-512: starea semnaturilor din atasamente, la deschiderea dosarului."""
        from app.core.pdf.signatures import STATUS_VALID

        report = self._dossier_report()
        if report is None:
            self.dossier_bar.hide()
            return
        signed = [r for r in report if r[2]]
        valid = [r for r in signed if r[1] and all(s.status == STATUS_VALID for s in r[2])]
        damaged = [r for r in report if not r[1]]
        self.dossier_label.setText(tr("dossier.bar", count=len(report), signed=len(signed),
                                      valid=len(valid), damaged=len(damaged)))
        self.dossier_bar.show()

    def verify_dossier(self) -> list[str]:
        """E-512: amprenta si semnaturile fiecarui original, din nou."""
        self._dossier_cache.clear()
        report = self._dossier_report() or []
        lines = []
        for name, ok, sigs in report:
            states = ", ".join(tr(f"dossier.status.{s.status}") for s in sigs) or \
                tr("dossier.status.none")
            key = "dossier.verify.ok" if ok else "dossier.verify.bad"
            lines.append(tr(key, name=name, states=states))
        self._update_dossier_bar()
        if lines:
            self.show_message("\n".join(lines))
        return lines

    # --- Security: parole, redactare, stergerea datelor, semnaturi (G-*) --------------------

    def ask_password_again(self, label_key: str) -> str | None:
        """G-012: parola se cere din nou la `OK`."""
        text, ok = QInputDialog.getText(self, tr("security.title"), tr(label_key),
                                        QLineEdit.EchoMode.Password)
        return text if ok else None

    def password_security(self) -> bool:
        """G-001…G-012: protectia, apoi salvarea peste document sau intr-unul nou."""
        from app.core.errors import SamePasswordError
        from app.core.pdf.security import SecurityService
        from app.gui.pdf_security_ui import PasswordDialog

        current = self.current()
        if current is None:
            return False
        dialog = PasswordDialog(self)
        if not self.exec_dialog(dialog):
            return False
        try:
            options = dialog.options()
        except SamePasswordError as exc:
            self.show_message(tr_error(exc))
            return False
        except ValueError:
            self.show_message(tr("security.mismatch"))
            return False
        for value, key in ((options.open_password, "security.again_open"),
                           (options.permissions_password, "security.again_permissions")):
            if value and self.ask_password_again(key) != value:  # G-012
                self.show_message(tr("security.mismatch"))
                return False
        document = current.document
        if document.path is not None and self.ask_confirm(tr("security.save_over")):
            SecurityService().apply(document, options)
            saved = self._save_document(document)
        else:
            target = self.ask_save_path(document)
            if target is None:
                return False
            SecurityService().apply(document, options)
            try:
                document.save_as(target)
                saved = True
            except (CoreError, OSError) as exc:
                self._report(exc)
                saved = False
        self._after_save()
        return saved

    def delete_objects(self) -> dict[str, int] | None:
        """G-022…G-024, G-111."""
        from app.core.pdf.security import SecurityService
        from app.gui.pdf_security_ui import DeleteObjectsDialog

        if self.current() is None:
            return None
        dialog = DeleteObjectsDialog(self)
        if not self.exec_dialog(dialog):
            return None
        choices = dialog.choices()
        if not any(choices.values()):
            return None
        if choices["hidden_text_and_objects"] and \
                not self.ask_confirm(tr("security.delete.image_only")):
            return None
        return self.modify(lambda d: SecurityService().delete_objects_and_data(d, **choices))

    # G-020, G-100…G-103
    def _build_redact_bar(self) -> QWidget:
        bar = QToolBar()
        bar.setObjectName("pdf_redact_bar")
        self.redact_bar = bar
        self.redact_color = str(self.settings.get("pdf_editor.redaction_color"))
        self.redact_buttons: dict[str, Any] = {}
        group = QActionGroup(self)
        for color in self.settings.get("pdf_editor.redaction_colors") or []:
            action = bar.addAction("■")
            action.setObjectName(f"redact_color_{color.lstrip('#')}")
            action.setToolTip(color)
            action.setCheckable(True)
            action.setChecked(color == self.redact_color)  # G-101: negru, selectat
            group.addAction(action)
            action.triggered.connect(lambda _c=False, c=color: self._set_redact_color(c))
            self.redact_buttons[color] = action
            button = bar.widgetForAction(action)
            if button is not None:
                button.setStyleSheet(f"color: {color}; font-size: 18px;")
        more = bar.addAction(tr("security.more_colors"), self._more_redact_colors)
        more.setObjectName("redact_more_colors")
        bar.hide()
        self.actions["redact"].setCheckable(True)  # G-103: comutator
        return bar

    def _set_redact_color(self, color: str) -> None:
        self.redact_color = color

    def _more_redact_colors(self) -> None:
        color = self.ask_color(self.redact_color)
        if color:
            self.redact_color = color

    def toggle_redaction(self) -> None:
        """G-020: modul de redactare: zonele trase se redacteaza cu culoarea aleasa."""
        on = self.actions["redact"].isChecked()
        self.redact_bar.setVisible(on)
        self._stop_picker()
        if on:
            self._arm_redaction()

    def _arm_redaction(self) -> None:
        from app.gui.pdf_content import AreaPicker

        current = self.current()
        if current is not None:
            self.picker = AreaPicker(current.view, self._redact_area)

    def _redact_area(self, page: int, rect: Rect) -> None:
        self.redact_area(page, rect)
        if self.actions["redact"].isChecked():  # modul ramane activ
            self._stop_picker()
            self._arm_redaction()

    def redact_area(self, page: int, rect: Rect) -> bool:
        """G-020, G-021: continutul zonei dispare si se verifica absenta lui."""
        from app.core.pdf.security import SecurityService

        color = self.redact_color
        return self.modify(lambda d: SecurityService().redact_regions(d, [(page, rect)], color)
                           or True) is not None

    # --- semnaturile (G-030…G-055, G-108, G-110) -----------------------------------------

    def _signature_service(self) -> Any:
        from app.core.pdf.signing import CertificateStore, SignatureService

        return SignatureService(CertificateStore(self.settings), tr)

    def _signature_library(self) -> Any:
        from app.core.pdf.handsign import SignatureImageLibrary

        return SignatureImageLibrary(self.context.app_db)

    def _fill_signature_menu(self) -> None:
        """G-110: semnatura digitala, text, imagine; cele salvate se pun direct."""
        menu = self.signature_menu
        menu.clear()
        for key, slot in (("digital", lambda: self.start_digital_signature()),
                          ("text", lambda: self.create_text_signature()),
                          ("image", lambda: self.create_image_signature()),
                          ("clipboard", lambda: self.create_image_signature(clipboard=True)),
                          ("manage", lambda: self.manage_signatures())):
            action = menu.addAction(tr(f"sign.menu.{key}"))
            action.setObjectName(f"signature_menu_{key}")
            action.triggered.connect(slot)
        saved = self._signature_library().signatures()
        if saved:
            menu.addSeparator()
        for signature in saved:
            menu.addAction(signature.name,
                           lambda _c=False, n=signature.name: self.start_place_signature(n))

    def start_digital_signature(self) -> None:
        """G-030: se trage zona semnaturii, apoi dialogul de semnare."""
        from app.gui.pdf_content import AreaPicker

        current = self.current()
        if current is None:
            return
        self._stop_picker()
        self.picker = AreaPicker(current.view, self._signature_area)

    def _signature_area(self, page: int, rect: Rect) -> None:
        self._stop_picker()
        self.sign_document(page, rect)

    def sign_document(self, page: int, rect: Rect, field_name: str | None = None
                      ) -> Path | None:
        """G-030…G-040: `Save and sign`; fara raspuns de la serverul de marca
        temporala se intreaba daca se semneaza fara (G-037). `field_name`: campul
        de semnatura gol din formular pe care s-a dat clic (H-035)."""
        from app.core.errors import TimestampUnavailableError
        from app.gui.pdf_security_ui import SignDialog

        current = self.current()
        if current is None:
            return None
        service = self._signature_service()
        dialog = SignDialog(service, self.settings, page, rect, self)
        dialog.add_certificate.clicked.connect(lambda: self.add_certificate(dialog))
        dialog.show_certificate.clicked.connect(
            lambda: self.show_certificate(dialog.certificate.currentData()))
        if not self.exec_dialog(dialog):
            return None
        options = dialog.options()
        if not options.certificate_id:
            self.show_message(tr("sign.no_certificate"))
            return None
        document = current.document
        if document.path is None:
            target = self.ask_save_path(document)
            if target is None:
                return None
            document.save_as(target)
        passphrase = self.ask_password()
        secret = passphrase.encode() if passphrase else None
        try:
            try:
                path = service.sign(document, options, passphrase=secret,
                                    field_name=field_name)
            except TimestampUnavailableError:
                if not self.ask_confirm(tr("sign.no_timestamp")):
                    return None
                path = service.sign(document, options, passphrase=secret,
                                    allow_without_timestamp=True, field_name=field_name)
        except CoreError as exc:
            self.show_message(tr_error(exc))
            return None
        except ValueError:
            self.show_message(tr("error.generic", code="SIGN"))
            return None
        current.view.reload()
        self._document_changed()
        self.show_pane(PANES.index("signatures"))
        return path

    def add_certificate(self, dialog: Any = None) -> str | None:
        """G-031: un certificat PKCS#12 (.p12, .pfx), verificat cu parola lui."""
        from app.core.pdf.signing import CertificateStore

        path = self.ask_open_file("sign.add_certificate")
        if path is None:
            return None
        passphrase = self.ask_password()
        try:
            cert_id = CertificateStore(self.settings).add(
                path, passphrase.encode() if passphrase else None)
        except CoreError as exc:
            self.show_message(tr_error(exc))
            return None
        if dialog is not None:
            dialog.reload_certificates()
        return cert_id

    def show_certificate(self, cert_id: str | None) -> str:
        """G-032 `Show Certificate...`."""
        if not cert_id:
            return ""
        details = self._signature_service().certificate_details(cert_id)
        text = tr("sign.certificate_details", subject=details["subject_dn"],
                  issuer=details["issuer_dn"], serial=details["serial"],
                  start=details["not_before"][:10], end=details["not_after"][:10])
        self.show_message(text)
        return text

    def signature_properties(self, field_name: str) -> str:
        """G-042 `Show Signature Properties...`."""
        current = self.current()
        if current is None:
            return ""
        props = self._signature_service().properties(current.document, field_name)
        text = tr("sign.properties_text", field=field_name,
                  status=tr(f"pdf.signatures.status.{props['status']}"),
                  signer=props["signer"] or "?", issuer=props["certificate_issuer"],
                  date=props["signed_at"] or "?", reason=props["reason"] or "-",
                  algorithm=props["hash_algorithm"], end=props["not_after"][:10])
        self.show_message(text)
        return text

    def remove_signature(self, field_name: str) -> bool:
        """G-043: cere certificatul potrivit."""
        if self.current() is None or not self.ask_confirm(tr("sign.remove_confirm",
                                                             field=field_name)):
            return False
        service = self._signature_service()
        done = self.modify(lambda d: service.delete_signature(d, field_name) or True)
        self.signatures_panel.set_document(self.current().document)
        return done is not None

    def create_text_signature(self) -> str | None:
        """G-050 `Create Text Signature...`."""
        text = self.ask_text("sign.menu.text", "sign.text")
        if not text:
            return None
        name = self.ask_text("sign.menu.text", "sign.name", text)
        if not name:
            return None
        try:
            self._signature_library().create_text(name, text)
        except ValueError:
            self.show_message(tr("sign.duplicate"))
            return None
        return name

    def create_image_signature(self, *, clipboard: bool = False) -> str | None:
        """G-051: din fisier sau `Paste from Clipboard`; fundal transparent la cerere."""
        from PySide6.QtCore import QBuffer, QIODevice

        if clipboard:
            image = QApplication.clipboard().image()
            if image.isNull():
                self.show_message(tr("sign.clipboard_empty"))
                return None
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, "PNG")
            data = bytes(buffer.data())
        else:
            path = self.ask_open_file("sign.menu.image")
            if path is None:
                return None
            data = path.read_bytes()
        name = self.ask_text("sign.menu.image", "sign.name")
        if not name:
            return None
        transparent = self.ask_confirm(tr("sign.transparent"))
        try:
            self._signature_library().create_image(name, data, transparent=transparent)
        except (CoreError, ValueError):
            self.show_message(tr("sign.duplicate"))
            return None
        return name

    def start_place_signature(self, name: str) -> None:
        """G-052: se trage zona; semnatura se pune la latimea ei."""
        from app.gui.pdf_content import AreaPicker

        current = self.current()
        if current is None:
            return
        self._stop_picker()
        self.picker = AreaPicker(current.view, lambda page, rect: self.place_signature(
            name, page, rect))

    def place_signature(self, name: str, page: int, rect: Rect) -> Any:
        import io as _io

        from PIL import Image

        from app.core.pdf.handsign import place_signature
        from app.core.pdf.stamps import IMAGE_DPI

        self._stop_picker()
        signature = self._signature_library().get(name)
        width = Image.open(_io.BytesIO(signature.image)).width * 72 / IMAGE_DPI
        scale = max(0.1, min(4.0, rect.w / width)) if width else 1.0
        return self.modify(lambda d: place_signature(d, page, signature, (rect.x, rect.y),
                                                     scale=scale))

    def manage_signatures(self) -> Any:
        """G-054, G-055: `Edit...` (nume, text), `Delete`, `Use`."""
        from app.gui.pdf_security_ui import ManageSignaturesDialog

        library = self._signature_library()
        dialog = ManageSignaturesDialog([s.name for s in library.signatures()], self)

        def edit() -> None:
            name = dialog.current()
            if not name:
                return
            new_name = self.ask_text("sign.manage.edit", "sign.name", name)
            if new_name:
                try:
                    library.update(name, new_name=new_name)
                except ValueError:
                    self.show_message(tr("sign.duplicate"))
                dialog.set_names([s.name for s in library.signatures()])

        def delete() -> None:
            name = dialog.current()
            if name and self.ask_confirm(tr("sign.delete_confirm", name=name)):
                library.delete(name)
                dialog.set_names([s.name for s in library.signatures()])

        def use() -> None:
            name = dialog.current()
            if name:
                dialog.accept()
                self.start_place_signature(name)

        dialog.buttons["edit"].clicked.connect(edit)
        dialog.buttons["delete"].clicked.connect(delete)
        dialog.buttons["use"].clicked.connect(use)
        self.exec_dialog(dialog)
        self._fill_signature_menu()
        return dialog

    # --- Edit Content (F-001…F-023, F-100…F-110) ------------------------------------------

    @property
    def edit_mode(self) -> bool:
        keys = list(RIBBON_TABS)
        index = self.ribbon_tabs.currentIndex()
        return 0 <= index < len(keys) and keys[index] == "content"

    @property
    def form_editor_mode(self) -> bool:
        """H-010: e activ tabul `Form Editor`."""
        keys = list(RIBBON_TABS)
        index = self.ribbon_tabs.currentIndex()
        return 0 <= index < len(keys) and keys[index] == "forms"

    def enter_form_editor(self) -> None:
        self.ribbon_tabs.setCurrentIndex(list(RIBBON_TABS).index("forms"))

    def sync_form_tools(self) -> None:
        """Butonul uneltei active ramane apasat (H-012, H-103)."""
        from app.gui.pdf_form_design import TOOL_ACTIONS

        for key, kind in TOOL_ACTIONS.items():
            self.actions[key].setChecked(self.form_design.tool == kind)

    def enter_edit_content(self) -> None:
        """F-001: `Ctrl+E` deschide tabul `Edit Content`."""
        self.ribbon_tabs.setCurrentIndex(list(RIBBON_TABS).index("content"))

    def _sync_edit_content(self) -> None:
        """Controlerul de editare exista numai in tabul `Edit Content`."""
        from app.gui.pdf_edit import ContentEditController

        current = self.current()
        wanted = self.edit_mode and current is not None
        if self.content_edit is not None and (not wanted or
                                              self.content_edit.view is not current.view):
            self.content_edit.detach()
            self.content_edit = None
        if wanted and self.content_edit is None:
            self.content_edit = ContentEditController(self, current.view)
            self.content_edit.changed.connect(self._sync_text_bar)
            self.content_edit.message.connect(self.edit_status.setText)
            self.content_edit.set_page(current.view.current_page)
            self._update_skew_button()
        self.text_bar.setVisible(wanted and self.actions["text_tools"].isChecked())
        self._sync_text_bar()

    def _edit_page_changed(self, page: int) -> None:
        if self.content_edit is not None and page != self.content_edit.page:
            self.content_edit.set_page(page)
            self._update_skew_button()

    def _update_skew_button(self) -> None:
        """F-017: butonul apare numai pe paginile cu inclinare detectata."""
        from app.core.pdf.editor import SKEW_VISIBLE

        edit = self.content_edit
        visible = False
        if edit is not None and edit.page is not None:
            try:
                visible = abs(edit.editor.skew_angle(edit.page)) > SKEW_VISIBLE
            except (CoreError, ValueError):
                visible = False
        self.actions["correct_skew"].setVisible(visible)

    def _edit(self, operation: Any) -> Any:
        """O operatie a controlerului, fara sa-l reincarce dupa ea."""
        self._editing_busy = True
        try:
            return operation()
        finally:
            self._editing_busy = False

    def _build_text_bar(self) -> QWidget:
        """F-007, F-100…F-110: bara de unelte de text."""
        from PySide6.QtWidgets import QDoubleSpinBox

        from app.gui.pdf_content import _font_names

        bar = QToolBar()
        bar.setObjectName("pdf_text_bar")
        self.text_bar = bar
        self.text_font = QComboBox()
        self.text_font.setObjectName("text_font")
        self.text_font.setEditable(False)
        self.text_font.setMinimumWidth(160)
        for name in _font_names():
            self.text_font.addItem(name, name)
        self.text_font.activated.connect(
            lambda _i: self._format(font_name=self.text_font.currentData()))
        bar.addWidget(self.text_font)
        self.text_size = QDoubleSpinBox()  # F-105
        self.text_size.setObjectName("text_size")
        self.text_size.setRange(1, 1638)
        self.text_size.setDecimals(1)
        self.text_size.editingFinished.connect(
            lambda: self._format(font_size=self.text_size.value()))
        bar.addWidget(self.text_size)
        self.text_controls: dict[str, Any] = {}
        for key, slot in (("bigger", lambda: self._step_size(1)),
                          ("smaller", lambda: self._step_size(-1))):  # F-106
            action = bar.addAction(tr(f"edit.{key}"), slot)
            action.setObjectName(f"text_{key}")
            self.text_controls[key] = action
        for key in ("bold", "italic", "underline"):
            action = bar.addAction(tr(f"edit.{key}"))
            action.setObjectName(f"text_{key}")
            action.setCheckable(True)
            action.triggered.connect(lambda on, k=key: self._format(**{k: bool(on)}))
            self.text_controls[key] = action
        bar.addSeparator()
        alignments = QActionGroup(self)
        for key in ("left", "center", "right", "justify"):  # F-107
            action = bar.addAction(tr(f"edit.align.{key}"))
            action.setObjectName(f"text_align_{key}")
            action.setCheckable(True)
            alignments.addAction(action)
            action.triggered.connect(lambda _c=False, k=key: self._format(alignment=k))
            self.text_controls[f"align_{key}"] = action
        rtl = bar.addAction(tr("edit.rtl"))  # F-108
        rtl.setObjectName("text_rtl")
        rtl.setCheckable(True)
        rtl.triggered.connect(lambda on: self._format(direction="rtl" if on else "ltr"))
        self.text_controls["rtl"] = rtl
        self.text_line_spacing = QDoubleSpinBox()  # F-109
        self.text_line_spacing.setObjectName("text_line_spacing")
        self.text_line_spacing.setRange(0.8, 3.0)
        self.text_line_spacing.setSingleStep(0.1)
        self.text_line_spacing.setToolTip(tr("edit.line_spacing"))
        self.text_line_spacing.editingFinished.connect(
            lambda: self._format(line_spacing=self.text_line_spacing.value()))
        bar.addWidget(self.text_line_spacing)
        self.text_paragraph_spacing = QDoubleSpinBox()
        self.text_paragraph_spacing.setObjectName("text_paragraph_spacing")
        self.text_paragraph_spacing.setRange(0, 100)
        self.text_paragraph_spacing.setSuffix(" pt")
        self.text_paragraph_spacing.setToolTip(tr("edit.paragraph_spacing"))
        self.text_paragraph_spacing.editingFinished.connect(
            lambda: self._format(paragraph_spacing=self.text_paragraph_spacing.value()))
        bar.addWidget(self.text_paragraph_spacing)
        color = bar.addAction("A", self._pick_text_color)  # F-110
        color.setObjectName("text_color")
        color.setToolTip(tr("edit.color"))
        self.text_controls["color"] = color
        self.edit_status = QLabel()  # F-003: pagina se pregateste
        self.edit_status.setObjectName("edit_status")
        bar.addWidget(self.edit_status)
        self.actions["text_tools"].setCheckable(True)
        self.actions["text_tools"].setChecked(True)
        bar.hide()
        return bar

    def toggle_text_bar(self) -> None:
        """F-007: `Ctrl+T` arata sau ascunde bara de text."""
        self.text_bar.setVisible(self.edit_mode and self.actions["text_tools"].isChecked())

    def _block_active(self) -> bool:
        return self.content_edit is not None and self.content_edit.active() is not None

    def _sync_text_bar(self) -> None:
        """F-101, F-102: bara arata formatarea blocului activ; gri fara bloc."""
        block = self.content_edit.active() if self.content_edit is not None else None
        self.actions["delete"].setEnabled(block is not None or self.organize_mode
                                          or self.selected_annotation is not None)
        widgets = [self.text_font, self.text_size, self.text_line_spacing,
                   self.text_paragraph_spacing]
        for widget in widgets:
            widget.setEnabled(block is not None)
        for action in self.text_controls.values():
            action.setEnabled(block is not None)
        for key in ("cut", "paste"):
            self.actions[key].setEnabled(self.content_edit is not None)
        if block is None:
            return
        for widget in widgets:
            widget.blockSignals(True)
        name = block.display_font or ""
        index = self.text_font.findData(block.font_name)
        if index < 0 and name:
            self.text_font.addItem(name, block.font_name)
            index = self.text_font.count() - 1
        self.text_font.setCurrentIndex(index)
        self.text_size.setValue(block.font_size)
        self.text_line_spacing.setValue(block.line_spacing)
        self.text_paragraph_spacing.setValue(block.paragraph_spacing)
        for widget in widgets:
            widget.blockSignals(False)
        for key in ("bold", "italic", "underline"):
            self.text_controls[key].setChecked(bool(getattr(block, key)))
        self.text_controls[f"align_{block.alignment}"].setChecked(True)
        self.text_controls["rtl"].setChecked(block.direction == "rtl")

    def _format(self, **attrs: Any) -> bool:
        if self.content_edit is None or self.content_edit.active() is None:
            return False
        return bool(self._edit(lambda: self.content_edit.format_active(**attrs)))

    def _step_size(self, step: int) -> bool:
        from app.gui.pdf_edit import next_size

        block = self.content_edit.active() if self.content_edit is not None else None
        if block is None:
            return False
        return self._format(font_size=next_size(block.font_size, step))

    def _pick_text_color(self) -> None:
        block = self.content_edit.active() if self.content_edit is not None else None
        if block is None:
            return
        color = self.ask_color(block.color)
        if color:
            self._format(color=color)

    def edit_block_text(self, text: str) -> bool:
        """F-008: textul blocului activ (si din editarea pe loc)."""
        if self.content_edit is None:
            return False
        return bool(self._edit(lambda: self.content_edit.edit_text(text)))

    def delete_blocks(self) -> bool:
        """F-012."""
        if self.content_edit is None:
            return False
        return bool(self._edit(self.content_edit.delete_active))

    def start_add_text(self) -> None:
        """`Add Text`: se trage zona noului bloc, apoi se scrie textul (F-011)."""
        if self.content_edit is None:
            self.enter_edit_content()
        if self.content_edit is not None:
            self.content_edit.adding_text = True

    def add_text_block(self, rect: Rect, text: str) -> bool:
        if self.content_edit is None:
            return False
        return bool(self._edit(lambda: self.content_edit.add_block(rect, text)))

    def add_picture(self) -> bool:
        """F-020: imaginea aleasa, in coltul din stanga-sus al paginii curente."""
        if self.content_edit is None:
            self.enter_edit_content()
        edit = self.content_edit
        if edit is None or edit.page is None:
            return False
        path = self.ask_open_file("edit.add_picture")
        if path is None:
            return False
        page = edit.page
        done = self._edit(lambda: self.modify(
            lambda _d: edit.editor.add_picture(page, path, (72, 72))))
        edit.refresh()
        return done is not None

    def picture_command(self, key: str, picture_id: int) -> bool:
        """F-021…F-023: `Bring Picture to Front`, rotirea, `Delete`."""
        edit = self.content_edit
        if edit is None or edit.page is None:
            return False
        page = edit.page
        operations = {
            "front": lambda _d: edit.editor.bring_to_front(page, picture_id) or True,
            "rotate": lambda _d: edit.editor.transform_picture(page, picture_id,
                                                               rotation=90) or True,
            "delete": lambda _d: edit.editor.delete_picture(page, picture_id) or True,
        }
        done = self._edit(lambda: self.modify(operations[key]))
        edit.refresh()
        return done is not None

    def picture_menu(self, picture_id: int) -> QMenu:
        """F-021…F-023: meniul contextual al unei imagini."""
        menu = QMenu(self)
        menu.setObjectName("edit_picture_menu")
        for key in ("front", "rotate", "delete"):
            action = menu.addAction(tr(f"edit.picture.{key}"))
            action.setObjectName(f"picture_{key}")
            action.triggered.connect(lambda _c=False, k=key: self.picture_command(k, picture_id))
        return menu

    def cut_block(self) -> bool:
        """`Cut`: textul blocului activ in clipboard, blocul dispare."""
        block = self.content_edit.active() if self.content_edit is not None else None
        if block is None:
            return False
        QApplication.clipboard().setText(block.text)
        return self.delete_blocks()

    def paste_block(self) -> bool:
        """`Paste`: textul din clipboard, intr-un bloc nou sub blocul activ (sau
        in coltul paginii)."""
        if self.form_design.active:  # H-015: `Ctrl+V`
            return bool(self.form_design.paste())
        edit = self.content_edit
        text = QApplication.clipboard().text().strip()
        if edit is None or edit.page is None or not text:
            return False
        block = edit.active()
        width, _height = self.current().document.page_size(edit.page)
        rect = Rect(block.rect.x, block.rect.y + block.rect.h + 6, block.rect.w,
                    block.rect.h) if block is not None else Rect(72, 72, width - 144, 20)
        return self.add_text_block(rect, text)

    def correct_skew(self) -> bool:
        """F-017: pagina curenta se indreapta."""
        edit = self.content_edit
        if edit is None or edit.page is None:
            return False
        page = edit.page
        done = self.modify(lambda _d: edit.editor.correct_skew(page, context=self.context)
                           or True)
        edit.refresh()
        self._update_skew_button()
        return done is not None

    def replace_text_layer(self) -> bool:
        """F-018: dialogul `Recognize Document`; stratul vechi se pierde."""
        from app.gui.pdf_content import RecognizeDialog

        edit = self.content_edit
        if edit is None or edit.page is None:
            return False
        dialog = RecognizeDialog(self)
        if not self.exec_dialog(dialog) or not self.ask_confirm(tr("edit.text_layer.confirm")):
            return False
        page = edit.page
        orientation, deskew = dialog.orientation.isChecked(), dialog.deskew.isChecked()
        done = self.modify(lambda _d: edit.editor.replace_text_layer(
            page, correct_orientation=orientation, deskew=deskew, context=self.context) or True)
        edit.refresh()
        return done is not None

    # --- dialogurile din Organize Pages (E-010…E-020, E-038) --------------------------

    def _anchor_page(self) -> int:
        """Pagina dupa care se insereaza implicit: ultima selectata."""
        pages = self.selected_pages()
        return max(pages) if pages else 1

    def _preset(self, position: Any) -> None:
        """E-013: pozitia aleasa cu `+` intre miniaturi se preia o singura data."""
        if self._insert_at is not None:
            position.set_at(self._insert_at)
            self._insert_at = None

    def _insert_here(self, at: int) -> None:
        """E-013: butonul `+` dintre miniaturi deschide meniul de adaugare."""
        from PySide6.QtGui import QCursor

        self._insert_at = at
        self.add_menu.popup(QCursor.pos())

    def _source_password(self) -> Any:
        """E-014: parola PDF-ului sursa, de cel mult trei ori (ca A-011)."""
        attempts = {"n": 0}

        def ask(_path: str) -> str | None:
            attempts["n"] += 1
            return self.ask_password() if attempts["n"] <= 3 else None

        return ask

    def add_blank_page(self) -> bool:
        """E-013: dimensiunea paginii si pozitia, apoi `Add`."""
        from app.gui.pdf_organize_dialogs import BlankPageDialog

        current = self.current()
        if current is None:
            return False
        dialog = BlankPageDialog(current.document.page_count, self._anchor_page(), self)
        self._preset(dialog.position)
        if not self.exec_dialog(dialog):
            return False
        at, size = dialog.position.at(), dialog.page_size()
        if self._organize(lambda o: o.add_blank(at, size) or True) is None:
            return False
        self._select_after_insert(at, 1)
        return True

    def _select_after_insert(self, at: int, count: int) -> None:
        current = self.current()
        if current is not None and count and self.organize_mode:
            current.organize.select_pages(list(range(at, at + count)))

    def add_pages_from_pdf(self) -> int:
        """E-014, E-016: paginile unui PDF, fara procesare de imagine."""
        from app.gui.pdf_organize_dialogs import InsertPagesDialog

        current = self.current()
        if current is None:
            return 0
        dialog = InsertPagesDialog("pdf", current.document.page_count, self._anchor_page(),
                                   self)
        self._preset(dialog.position)
        if not self.exec_dialog(dialog):
            return 0
        at, source, pages = dialog.position.at(), dialog.source(), dialog.source_pages()
        if not self._signatures_may_be_lost([source]):  # E-509
            return 0
        password = self._source_password()
        added = self._organize(lambda o: o.insert_from_pdf(source, source_pages=pages, at=at,
                                                           password=password))
        self._select_after_insert(at, added or 0)
        return added or 0

    def add_pages_from_file(self) -> int:
        """E-015, E-108: orice fisier, cu procesare de imagine (mai lent)."""
        from app.gui.pdf_organize_dialogs import InsertPagesDialog, image_options
        from app.gui.progress import run_with_progress

        current = self.current()
        if current is None:
            return 0
        dialog = InsertPagesDialog("file", current.document.page_count, self._anchor_page(),
                                   self)
        dialog.image_settings.clicked.connect(self.image_processing_settings)
        self._preset(dialog.position)
        if not self.exec_dialog(dialog):
            return 0
        at, source, pages = dialog.position.at(), dialog.source(), dialog.source_pages()
        if not self._signatures_may_be_lost([source]):  # E-509
            return 0
        split = dialog.split_facing.isChecked()
        options = image_options(self.settings)
        added = run_with_progress(
            tr("organize.insert.progress"),
            lambda progress, cancel: self._organize(lambda o: o.insert_from_file(
                source, source_pages=pages, at=at, split_facing_pages=split,
                options=options, context=self.context)), self)
        self._select_after_insert(at, added or 0)
        return added or 0

    def scanner(self) -> Any:
        from app.core.images.wia import default_scanner

        if self.scanner_service is None:
            self.scanner_service = default_scanner()
        return self.scanner_service

    def acquire_scan(self) -> list[Path]:
        """E-017: dispozitivul, parametrii, `Preview`, `Settings...`, `Scan`
        (dialogul de scanare din OCR Editor, fara proiect)."""
        from app.gui.scan_dialog import ScanDialog

        dialog = ScanDialog(self.context, self.scanner(), parent=self)
        dialog.exec()
        return list(dialog.images)

    def add_pages_from_scanner(self) -> int:
        """E-017: pozitia, apoi scanarea; paginile se proceseaza ca la E-015."""
        from app.gui.pdf_organize_dialogs import PositionDialog, image_options
        from app.gui.progress import run_with_progress

        current = self.current()
        if current is None:
            return 0
        dialog = PositionDialog("pdf.action.add_pages_scanner", current.document.page_count,
                                self._anchor_page(), self)
        self._preset(dialog.position)
        if not self.exec_dialog(dialog):
            return 0
        at = dialog.position.at()
        images = self.acquire_scan()
        if not images:
            return 0
        options = image_options(self.settings)
        added = run_with_progress(
            tr("organize.insert.progress"),
            lambda progress, cancel: self._organize(lambda o: o.insert_files(
                images, at=at, options=options, context=self.context)), self)
        self._select_after_insert(at, added or 0)
        return added or 0

    def image_processing_settings(self) -> bool:
        """E-038: `Image Processing Settings...`."""
        from app.gui.pdf_organize_dialogs import ImageProcessingDialog

        dialog = ImageProcessingDialog(self.settings, self)
        if not self.exec_dialog(dialog):
            return False
        dialog.store()
        return True

    def move_pages_dialog(self) -> list[int] | None:
        """E-019: inainte de prima, dupa ultima sau dupa o pagina aleasa."""
        from app.gui.pdf_organize_dialogs import MovePagesDialog

        current = self.current()
        if current is None:
            return None
        pages = self.selected_pages()
        dialog = MovePagesDialog(pages, current.document.page_count, self)
        if not self.exec_dialog(dialog):
            return None
        return self.move_pages_to(pages, dialog.position.at())

    def replace_pages_dialog(self) -> bool:
        """E-020: intervalele trebuie sa aiba acelasi numar de pagini."""
        from app.gui.pdf_organize_dialogs import ReplacePagesDialog

        current = self.current()
        if current is None:
            return False
        dialog = ReplacePagesDialog(self.selected_pages(), current.document.page_count, self)
        if not self.exec_dialog(dialog):
            return False
        try:
            target, source_pages = dialog.ranges()
        except ValueError:
            self.show_message(tr("organize.range.invalid"))
            return False
        if len(target) != len(source_pages):
            self.show_message(tr("organize.replace.mismatch", target=len(target),
                                 source=len(source_pages)))
            return False
        if not self._signatures_may_be_lost([dialog.source()]):  # E-509
            return False
        source, password = dialog.source(), self._source_password()
        return self._organize(lambda o: o.replace(target, source, source_pages,
                                                  password=password) or True) is not None

    def delete_blank_pages(self) -> list[int]:
        """E-021…E-023: paginile goale gasite, revizuite; inainte de stergere se
        verifica notele de mana si imaginile (E-022)."""
        from app.core.pdf.organize import BLANK_THRESHOLD, PageOrganizer
        from app.gui.pdf_organize_dialogs import BlankPagesDialog

        current = self.current()
        if current is None:
            return []
        organizer = PageOrganizer(current.document)
        if not organizer.find_blank(BLANK_THRESHOLD):
            self.show_message(tr("organize.blank.none"))
            return []
        dialog = BlankPagesDialog(current.document, organizer.find_blank, BLANK_THRESHOLD,
                                  self)
        if not self.exec_dialog(dialog):
            return []
        pages = dialog.checked_pages()
        if not pages:
            return []
        warnings = organizer.content_warnings(pages)
        if warnings:
            from app.core.pdf.organize import format_range

            if not self.ask_confirm(tr("organize.blank.content",
                                       pages=format_range(sorted(warnings)))):
                return []
        return pages if self.delete_pages(pages) else []

    def split_document(self) -> list[Path]:
        """E-024…E-032: fisierele noi, apoi folderul de iesire se deschide."""
        from app.core.pdf.organize import PageOrganizer
        from app.gui.pdf_organize_dialogs import SplitDialog
        from app.gui.progress import run_with_progress

        current = self.current()
        if current is None:
            return []
        organizer = PageOrganizer(current.document)
        dialog = SplitDialog(organizer, self)
        if not self.exec_dialog(dialog):
            return []
        folder = dialog.output_folder()
        method, value, naming = dialog.method(), dialog.value(), dialog.naming()
        try:
            files = run_with_progress(
                tr("organize.split.progress"),
                lambda progress, cancel: organizer.split(
                    by=method, value=value, output_folder=folder, naming=naming,
                    progress=progress), self)
        except (CoreError, ValueError, OSError) as exc:
            self._report(exc)
            return []
        self.open_external(QUrl.fromLocalFile(str(folder)))  # E-032
        return list(files or [])

    def enhance_images(self) -> bool:
        """E-035: imaginile paginilor selectate, imbunatatite pe loc."""
        from app.gui.pdf_organize_dialogs import EnhanceDialog, image_options
        from app.gui.progress import run_with_progress

        current = self.current()
        if current is None:
            return False
        dialog = EnhanceDialog(self.settings, self)
        dialog.change_languages.clicked.connect(
            lambda: self.options_requested.emit("languages"))
        if not self.exec_dialog(dialog):
            return False
        pages, preprocess = self.selected_pages(), dialog.preprocess()
        options = image_options(self.settings)
        done = run_with_progress(
            tr("organize.enhance.progress"),
            lambda progress, cancel: self._organize(lambda o: o.enhance_images(
                pages, preprocess, options=options, context=self.context) or True), self)
        return done is not None

    # --- decuparea (E-010…E-012) ------------------------------------------------------

    def _build_crop_bar(self) -> QWidget:
        """E-010…E-012: bara modului de decupare, cu cele doua variante."""
        self.crop_bar = QFrame()
        self.crop_bar.setObjectName("pdf_crop_bar")
        row = QHBoxLayout(self.crop_bar)
        row.setContentsMargins(8, 4, 8, 4)
        self.crop_mode = QComboBox()
        self.crop_mode.setObjectName("crop_mode")
        self.crop_mode.addItem(tr("organize.crop.same"), "same")
        self.crop_mode.addItem(tr("organize.crop.separate"), "separate")
        self.crop_mode.currentIndexChanged.connect(self._crop_mode_changed)
        hint = QLabel(tr("organize.crop.hint"))
        hint.setProperty("muted", True)
        row.addWidget(self.crop_mode)
        row.addWidget(hint, 1)
        for key, slot, keys in (("crop_apply", self.apply_crop, ("Return", "Enter")),
                                ("crop_exit", self.exit_crop, ("Esc",))):
            action = QAction(tr(f"organize.{key}"), self)
            action.setObjectName(f"pdf_action_{key}")
            action.setShortcuts([QKeySequence(k) for k in keys])
            action.setEnabled(False)
            action.triggered.connect(slot)
            self.addAction(action)
            self.actions[key] = action
            button = QToolButton()
            button.setDefaultAction(action)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            row.addWidget(button)
        self.crop_bar.hide()
        return self.crop_bar

    def start_crop(self) -> bool:
        """E-010: `Crop Pages` pe paginile selectate."""
        from app.gui.pdf_crop import CropController

        current = self.current()
        if current is None:
            return False
        if self.crop is not None:
            return True
        pages = self.selected_pages()
        current.page.setCurrentIndex(0)  # decuparea se face pe pagina
        self.crop = CropController(current.view, pages,
                                   same_for_all=self.crop_mode.currentData() == "same")
        self.crop_bar.show()
        self.actions["crop_apply"].setEnabled(True)
        self.actions["crop_exit"].setEnabled(True)
        self._go_to(pages[0])
        return True

    def _crop_mode_changed(self) -> None:
        if self.crop is not None:
            self.crop.same_for_all = self.crop_mode.currentData() == "same"
            self.crop.view.viewport().update()

    def apply_crop(self) -> bool:
        """E-011: `Apply Crop` (`Enter`)."""
        if self.crop is None:
            return False
        frame = self.crop.result()
        if frame is None:
            self.show_message(tr("organize.crop.no_frame"))
            return False
        pages, same = self.crop.pages, self.crop.same_for_all
        if not same:
            pages = sorted(frame)  # type: ignore[arg-type]
        self.exit_crop()
        return self._organize(lambda o: o.crop(pages, frame, same_for_all=same)
                              or True) is not None

    def exit_crop(self) -> None:
        """E-012: `Exit Crop` (`Esc`): iese fara modificari."""
        if self.crop is None:
            return
        self.crop.detach()
        self.crop = None
        self.crop_bar.hide()
        self.actions["crop_apply"].setEnabled(False)
        self.actions["crop_exit"].setEnabled(False)
        current = self.current()
        if current is not None:
            current.page.setCurrentIndex(1 if self.organize_mode else 0)

    # --- Undo/Redo si modificarile -----------------------------------------------------

    def record_undo(self) -> None:
        """Starea dinainte de o modificare, pentru Undo."""
        current = self.current()
        if current is None:
            return
        current.undo.append(current.document._snapshot())
        del current.undo[:-UNDO_LIMIT]
        current.redo.clear()

    def modify(self, operation: Any, error_key: str = "error.generic") -> Any:
        """Aplica `operation(document)` pe documentul curent, cu pas de Undo;
        o eroare se arata (`error_key` pentru cele care nu sunt `CoreError`) si
        documentul ramane neschimbat."""
        current = self.current()
        if current is None:
            return None
        snapshot = current.document._snapshot()
        try:
            result = operation(current.document)
        except (CoreError, ValueError, KeyError) as exc:
            current.document._restore(snapshot)
            self.show_message(tr_error(exc) if isinstance(exc, CoreError)
                              else tr(error_key))
            return None
        current.undo.append(snapshot)
        del current.undo[:-UNDO_LIMIT]
        current.redo.clear()
        self._after_modify()
        return result

    def undo(self) -> None:
        current = self.current()
        if current is None or not current.undo:
            return
        current.redo.append(current.document._snapshot())
        current.document._restore(current.undo.pop())
        self.selected_annotation = None
        self._after_modify()

    def redo(self) -> None:
        current = self.current()
        if current is None or not current.redo:
            return
        current.undo.append(current.document._snapshot())
        current.document._restore(current.redo.pop())
        self.selected_annotation = None
        self._after_modify()

    # --- adnotarile din pagina (D-008, D-028, D-106) ----------------------------------

    def annotation_at(self, page: int, x: float, y: float) -> Any:
        """Adnotarea de sub punct (cea desenata ultima, deasupra)."""
        current = self.current()
        if current is None:
            return None
        hits = [a for a in current.document.annotations(page)
                if a.bbox.x <= x <= a.bbox.x + a.bbox.w and a.bbox.y <= y <= a.bbox.y + a.bbox.h]
        return hits[-1] if hits else None

    def _page_clicked(self, page: int, x: float, y: float) -> None:
        if self.forms.activate(page, x, y):  # completarea formularului (11.4)
            return
        annot = self.annotation_at(page, x, y)
        self.select_annotation(annot.id if annot is not None else None)

    def _double_clicked(self, page: int, x: float, y: float) -> None:
        annot = self.annotation_at(page, x, y)
        if annot is None:
            return
        if not self.comments_panel.isVisibleTo(self):
            self.toggle_comments_pane()
        self.comments_panel.focus_comment(annot.id)

    def select_annotation(self, annot_id: int | None) -> None:
        self.selected_annotation = annot_id
        if annot_id is not None and self.comments_panel.selected_id != annot_id:
            self.comments_panel.selected_id = annot_id
            self.comments_panel.refresh()
        current = self.current()
        if current is not None:
            current.view.viewport().update()
        self._update_state()

    def _grab_annotation(self, page: int, x: float, y: float) -> Any:
        """D-052: tragerea pe adnotarea selectata o muta."""
        if self.selected_annotation is None:
            return None
        annot = self.annotation_at(page, x, y)
        return annot if annot is not None and annot.id == self.selected_annotation else None

    def _drop_annotation(self, annot: Any, dx: float, dy: float) -> None:
        from app.gui.pdf_tools import moved

        self.modify(lambda doc: doc.update_annotation(moved(annot, dx, dy)))

    def delete_selected_annotation(self) -> None:
        """D-028, D-051: `Del` sterge adnotarea selectata, cu raspunsurile ei."""
        if self.selected_annotation is None:
            return
        annot_id = self.selected_annotation
        self.selected_annotation = None
        self.modify(lambda doc: doc.delete_annotations([annot_id]))

    def paint_selected_annotation(self, painter: Any, view: Any) -> None:
        from PySide6.QtGui import QColor, QPen

        current = self.current()
        if current is None or view is not current.view or self.selected_annotation is None:
            return
        annot = next((a for a in current.document.annotations()
                      if a.id == self.selected_annotation), None)
        if annot is None:
            return
        box = view.page_to_view(annot.page_number, annot.bbox)
        if box is not None:
            painter.setPen(QPen(QColor(SELECTED_ANNOTATION), 2))
            painter.drawRect(box.adjusted(-2, -2, 2, 2))

    def _after_modify(self) -> None:
        """Documentul curent s-a schimbat (marcaje, inlocuire, redactare, pagini)."""
        current = self.current()
        if self.content_edit is not None and not self._editing_busy:
            self.content_edit.refresh()
        if current is not None:
            self.forms.invalidate(current.document)
            self.form_design.refresh()
            current.view.reload()
            self.bookmarks_panel.set_document(current.document)
            self.attachments_panel.set_document(current.document)
            if self.organize_mode:
                current.organize.refresh()
        self.pages_panel.refresh()
        self.refresh_comments()
        self._update_state()

    def _document_changed(self) -> None:
        if self.crop is not None:
            self.exit_crop()
        self.search_panel.document_switched()
        current = self.current()
        document = current.document if current is not None else None
        self.pages_panel.set_document(document)
        self.bookmarks_panel.set_document(document)
        self.attachments_panel.set_document(document)
        self.signatures_panel.set_document(document)
        self.refresh_comments()
        self._update_js_banner()
        self._update_dossier_bar()
        self.forms.cancel_editing()
        self.forms.invalidate()
        self.forms.update_band()  # H-001, H-100
        self._ribbon_changed()

    def refresh_comments(self) -> None:
        """B-305: `Comments (N)` arata numarul comentariilor."""
        current = self.current()
        count = self.comments_panel.set_document(current.document if current else None)
        self.actions["comments_pane"].setText(tr("pdf.action.comments_count", n=count))

    # --- salvarea (de baza; restul in 7.10) -------------------------------------------

    def ask_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("pdf.action.open"), "",
                                              tr("pdf.filter.pdf"))
        if path:
            self.open_path(Path(path))

    def _report(self, exc: Exception) -> None:
        self.show_message(tr_error(exc) if isinstance(exc, CoreError) else tr("error.generic"))

    def _save_document(self, document: Any) -> bool:
        self.forms.warn_required()  # H-023: numai avertisment
        try:
            if document.path is None:
                target = self.ask_save_path(document)
                if target is None:
                    return False
                document.save_as(target)
            else:
                document.save()
        except (CoreError, OSError, ValueError) as exc:
            self._report(exc)
            return False
        self._after_save()
        return True

    def save(self) -> bool:
        """I-001."""
        current = self.current()
        return current is not None and self._save_document(current.document)

    def save_as(self) -> bool:
        """I-002: copie noua; documentul deschis trece pe ea."""
        current = self.current()
        if current is None:
            return False
        self.forms.warn_required()  # H-023
        target = self.ask_save_path(current.document)
        if target is None:
            return False
        try:
            current.document.save_as(target)
        except (CoreError, OSError, ValueError) as exc:
            self._report(exc)
            return False
        self._after_save()
        return True

    def _after_save(self) -> None:
        current = self.current()
        if current is not None and current.document.path is not None:
            self.tabs.setTabText(self.tabs.currentIndex(), current.document.path.name)
        self._document_changed()

    def autosave(self) -> None:
        """I-024: copia de siguranta a documentelor modificate."""
        for entry in self.open_documents:
            try:
                entry.document.autosave(self.context)
            except (CoreError, OSError) as exc:
                _log.warning("salvarea automata a esuat: %s", exc)

    # --- recunoasterea (B-028, B-032) -------------------------------------------------

    def _start_background(self, entry: OpenDocument) -> None:
        """B-028: activa implicit, porneste la deschidere. Ruleaza pe firul
        ferestrei, cate o pagina pe rand, cu evenimentele procesate intre pagini
        (faza_7_pasi.md, decizia 23)."""
        from app.core.pdf import background

        if not background.enabled(self.settings):
            return
        entry.background = background.pages_without_text(entry.document)
        if entry.background:
            self._background_timer.start()

    def _background_step(self) -> None:
        pending = next((e for e in self.open_documents if e.background), None)
        if pending is None:
            self._background_timer.stop()
            return
        page = pending.background.pop(0)
        pending.document.recognize_in_background(
            pages=[page], context=self.context,
            progress=lambda _report: QApplication.processEvents())
        if pending is self.current():
            self.pages_panel.refresh()

    def recognize_document(self, pages: list[int] | None = None) -> None:
        """B-032: stratul de text permanent; fisierul se modifica, deci se confirma.
        E-033: numai paginile alese."""
        from app.gui.progress import run_with_progress

        current = self.current()
        if current is None or not self.ask_confirm(tr("pdf.recognize.confirm")):
            return
        if pages is None:
            current.background.clear()
        else:
            current.background[:] = [n for n in current.background if n not in pages]
        try:
            stored = run_with_progress(
                tr("pdf.recognize.title"),
                lambda progress, cancel: current.document.recognize_and_store(
                    pages=pages, context=self.context, progress=progress), self)
        except CoreError as exc:
            self.show_message(tr_error(exc))
            return
        current.view.reload()
        self._document_changed()
        if not stored:
            self.show_message(tr("pdf.recognize.nothing"))

    # --- vizualizarea -----------------------------------------------------------------

    def _on_view(self, method: str) -> None:
        current = self.current()
        if current is not None:
            getattr(current.view, method)()

    def _on_selection(self, command: str) -> None:
        current = self.current()
        if current is None:
            return
        if self.form_design.active and command == "copy":  # H-015: `Ctrl+C`
            self.form_design.copy()
            return
        selection = current.selection
        if command == "copy_area_table":
            if selection.mode == "table":
                selection.copy_table()
            else:
                selection.start_table()
            return
        getattr(selection, command)()

    def _go_to(self, page: int) -> None:
        current = self.current()
        if current is not None:
            current.view.go_to_page(page)

    def set_fit(self, fit: FitMode) -> None:
        current = self.current()
        if current is not None:
            current.view.set_fit(fit)
            self._update_state()

    def set_zoom(self, percent: int) -> None:
        current = self.current()
        if current is not None:
            current.view.set_zoom(int(percent))
            self._update_state()

    def set_mode(self, mode: ViewMode) -> None:
        current = self.current()
        if current is not None:
            current.view.set_mode(mode)
        self._update_state()

    def _odd_on_right(self, on: bool) -> None:
        current = self.current()
        if current is not None:
            current.view.set_odd_on_right(on)

    def _set_tool(self, tool: Tool) -> None:
        for entry in self.open_documents:
            entry.view.set_tool(tool)

    def ask_go_to_page(self) -> None:
        """B-015: `Go to Page > Page Number...`."""
        current = self.current()
        if current is None:
            return
        page, ok = QInputDialog.getInt(self, tr("pdf.action.go_to_page"),
                                       tr("pdf.go_to.label", n=current.view.page_count),
                                       current.view.current_page, 1, current.view.page_count)
        if ok:
            current.view.go_to_page(page)

    def _update_state(self) -> None:
        current = self.current()
        view = current.view if current else None
        has = view is not None
        a = self.actions
        for key in ("save", "save_as", "close", "recognize_document", "go_to_page",
                    "full_screen", "best_fit", "actual_size", "fit_width", "one_page",
                    "one_page_scroll", "two_page", "two_page_scroll", "first_page",
                    "last_page", "select", "hand"):
            a[key].setEnabled(has)
        a["zoom_in"].setEnabled(has and view.can_zoom_in())  # B-010
        a["zoom_out"].setEnabled(has and view.can_zoom_out())
        a["next_page"].setEnabled(has and view.can_go_next())  # B-016
        a["previous_page"].setEnabled(has and view.can_go_previous())
        a["back"].setEnabled(has and view.can_go_back())
        a["forward"].setEnabled(has and view.can_go_forward())
        a["odd_on_right"].setEnabled(has and view.mode.two_pages)  # B-006
        selection = current.selection if current else None
        a["copy"].setEnabled(bool(selection and selection.has_selection()))
        area = bool(selection and selection.mode in ("area", "table"))
        a["copy_area_text"].setEnabled(area)
        a["copy_area_table"].setEnabled(area)
        a["select_all"].setEnabled(has)
        a["undo"].setEnabled(bool(current and current.undo))
        a["redo"].setEnabled(bool(current and current.redo))
        a["delete"].setEnabled(has and (self.organize_mode
                                        or self.selected_annotation is not None
                                        or self._block_active()))
        for key in ORGANIZE_COMMANDS:  # E-005…E-008
            a[key].setEnabled(has)
        for key in ("rotate_left", "rotate_right"):  # B-308
            self.pages_panel.actions[key].setEnabled(has)
        self.pages_panel.more.setEnabled(has)
        self.page_range.setEnabled(has)
        for widget in (self.page_field, self.zoom_combo, self.fit_combo, self.mode_button):
            widget.setEnabled(has)
        from app.gui.pdf_form_design import TOOL_ACTIONS

        for key in (*TOOL_ACTIONS, "highlight_fields", "show_field_names"):
            a[key].setEnabled(has)
        form_mode = self.form_editor_mode
        for key in FORM_MODE_DISABLED:  # H-010: uneltele principale, oprite in Form Editor
            if key not in ("select", "hand", "copy_area_text", "copy_area_table"):
                a[key].setEnabled(not form_mode)
        if form_mode:
            for key in ("select", "hand", "copy_area_text", "copy_area_table"):
                a[key].setEnabled(False)
            a["delete"].setEnabled(bool(self.form_design.selected))
        if not has:
            self.page_field.setText("")
            self.page_total.setText("/ 0")
            self.setWindowTitle(tr("pdf.window.empty"))
            return
        self.page_field.setText(str(view.current_page))
        self.page_field.setStyleSheet("")
        self.page_total.setText(f"/ {view.page_count}")
        self.zoom_combo.setEditText(f"{view.zoom}%")
        self.fit_combo.setCurrentIndex(self.fit_combo.findData(view.fit.value))
        mode_key = {ViewMode.ONE_PAGE: "one_page",
                    ViewMode.ONE_PAGE_SCROLLING: "one_page_scroll",
                    ViewMode.TWO_PAGE: "two_page",
                    ViewMode.TWO_PAGE_SCROLLING: "two_page_scroll"}[view.mode]
        a[mode_key].setChecked(True)
        a["select" if view.tool is Tool.SELECT else "hand"].setChecked(True)
        self.pages_panel.set_current(view.current_page)
        name = current.document.path.name if current.document.path else tr("pdf.untitled")
        mark = "*" if current.document.is_modified else ""
        self.setWindowTitle(tr("pdf.window.title", name=name + mark))

    # --- ecranul complet (B-007…B-009) ------------------------------------------------

    def toggle_full_screen(self) -> None:
        if self.isFullScreen():
            self.exit_full_screen()
            return
        current = self.current()
        if current is None:
            return
        self._full_screen_state = {
            "ribbon": self.ribbon.isVisibleTo(self), "left": self.left.isVisibleTo(self),
            "comments": self.comments_panel.isVisibleTo(self),
            "bottom": self.bottom_bar.isVisibleTo(self),
            "tabs": self.tabs.tabBar().isVisibleTo(self)}
        for widget in (self.ribbon, self.left, self.comments_panel, self.bottom_bar,
                       self.js_banner):
            widget.hide()
        self.tabs.tabBar().hide()
        current.view.viewport().installEventFilter(self)
        current.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        current.view.customContextMenuRequested.connect(self._full_screen_menu)
        self.showFullScreen()

    def exit_full_screen(self) -> None:
        if not self.isFullScreen():
            return
        self.showNormal()
        state = self._full_screen_state
        self.ribbon.setVisible(state.get("ribbon", True))
        self.left.setVisible(state.get("left", True))
        self.comments_panel.setVisible(state.get("comments", False))
        self.bottom_bar.setVisible(state.get("bottom", True))
        self.tabs.tabBar().setVisible(state.get("tabs", True))
        current = self.current()
        if current is not None:
            current.view.viewport().removeEventFilter(self)
            current.view.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
            try:
                current.view.customContextMenuRequested.disconnect(self._full_screen_menu)
            except (RuntimeError, TypeError):
                pass
        self._update_js_banner()

    def full_screen_menu(self) -> QMenu:
        """B-009: comentarii, inserare de text, semne de carte, editare, iesire."""
        menu = QMenu(self)
        for key in ("add_note", "insert_text", "add_bookmark"):
            menu.addAction(self.actions[key])
        edit = menu.addAction(tr("pdf.action.edit_text_images"))
        edit.setEnabled(False)
        edit.setToolTip(tr("pdf.later", step="9"))
        menu.addSeparator()
        menu.addAction(tr("pdf.action.exit_full_screen"), self.exit_full_screen)
        return menu

    def _full_screen_menu(self, position: Any) -> None:
        current = self.current()
        if current is not None:
            self.full_screen_menu().exec(current.view.mapToGlobal(position))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # API Qt
        """B-008: in ecranul complet, bara de jos apare cand mouse-ul e la margine.
        F-028…F-030: clicul dreapta pe un link deschide meniul linkului."""
        if event.type() == QEvent.Type.ContextMenu and self._link_menu(watched, event):
            return True
        if self.isFullScreen() and event.type() == QEvent.Type.MouseMove:
            y = event.position().y()  # type: ignore[attr-defined]
            near = y >= watched.height() - FULL_SCREEN_EDGE  # type: ignore[attr-defined]
            self.bottom_bar.setVisible(near)
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: Any) -> None:  # API Qt
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():  # B-007
            self.exit_full_screen()
            return
        if event.key() == Qt.Key.Key_Escape and self.annotation_tool is not None:
            self.set_annotation_tool(None)
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: Any) -> None:  # API Qt
        if event.key() == Qt.Key.Key_Shift:  # D-009: traseele Ink adunate cu Shift
            current = self.current()
            if current is not None and current.tools is not None:
                current.tools.release_shift()
        super().keyReleaseEvent(event)

    # --- atasamentele (B-034) ---------------------------------------------------------

    def open_attachment(self, name: str) -> None:
        """B-034: se cere `Allow` sau `Cancel` inainte de deschidere."""
        current = self.current()
        if current is None or not self.ask_allow("attachment", name):
            return
        folder = Path(tempfile.mkdtemp(prefix="doculens-anexa-"))
        try:
            current.document.extract_attachment(name, folder)
        except (KeyError, OSError) as exc:
            _log.warning("atasamentul nu s-a putut extrage: %s", exc)
            return
        self.open_external(QUrl.fromLocalFile(str(folder / Path(name).name)))

    def ask_attachment_target(self, name: str) -> Path | None:
        target, _ = QFileDialog.getSaveFileName(self, tr("pdf.attachments.save"), name)
        return Path(target) if target else None

    def save_attachment(self, name: str) -> Path | None:
        """B-023; E-511: dintr-un dosar, originalul exact, cu amprenta verificata."""
        from app.core.pdf import dossier

        current = self.current()
        if current is None:
            return None
        target = self.ask_attachment_target(name)
        if target is None:
            return None
        path = current.document.path
        try:
            if path is not None and path.is_file() and \
                    dossier.manifest(path.read_bytes()) is not None:
                return dossier.extract_original(path, name, target)
            current.document.extract_attachment(name, target)
        except CoreError as exc:
            self.show_message(tr_error(exc))
            return None
        except (KeyError, OSError):
            self.show_message(tr("error.generic", code="ATTACHMENT"))
            return None
        return target

    # --- dialogurile (inlocuite in teste) ---------------------------------------------

    def ask_password(self) -> str | None:
        text, ok = QInputDialog.getText(self, tr("pdf.password.title"),
                                        tr("pdf.password.label"), QLineEdit.EchoMode.Password)
        return text if ok and text else None

    def ask_save(self, document: Any) -> str:
        """'save', 'discard' sau 'cancel'."""
        name = document.path.name if document.path else tr("pdf.untitled")
        box = QMessageBox(QMessageBox.Icon.Question, tr("pdf.window.empty"),
                          tr("pdf.close.ask_save", name=name), parent=self)
        save = box.addButton(tr("pdf.close.save"), QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(tr("pdf.close.discard"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("pdf.close.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        return "save" if clicked is save else "discard" if clicked is discard else "cancel"

    def ask_save_path(self, document: Any, suffix: str = ".pdf") -> Path | None:
        stem = document.path.with_suffix("") if document.path else Path(tr("pdf.untitled"))
        file_filter = tr("pdf.filter.pdf") if suffix == ".pdf" else tr("pdf.filter.eml")
        path, _ = QFileDialog.getSaveFileName(self, tr("pdf.action.save_as"),
                                              str(stem) + suffix, file_filter)
        return Path(path) if path else None

    def ask_confirm(self, text: str) -> bool:
        answer = QMessageBox.question(self, tr("pdf.window.empty"), text)
        return answer == QMessageBox.StandardButton.Yes

    def ask_allow(self, kind: str, target: str) -> bool:
        """B-034…B-036: `Allow` sau `Cancel`."""
        box = QMessageBox(QMessageBox.Icon.Warning, tr("pdf.window.empty"),
                          tr(f"pdf.allow.{kind}", target=target), parent=self)
        allow = box.addButton(tr("pdf.allow.allow"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("pdf.allow.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is allow

    def open_external(self, url: QUrl) -> bool:
        return bool(QDesktopServices.openUrl(url))

    def show_message(self, text: str) -> None:
        QMessageBox.information(self, tr("pdf.window.empty"), text)

    # --- inchiderea -------------------------------------------------------------------

    def closeEvent(self, event: Any) -> None:  # API Qt
        while self.open_documents:
            if not self.close_document(len(self.open_documents) - 1):
                event.ignore()
                return
        self._background_timer.stop()
        self._autosave_timer.stop()
        self.closed.emit()
        super().closeEvent(event)
