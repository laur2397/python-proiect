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
in tooltip, dupa `LATER`): copierea vine in 7.8b; notele,
desenele, marcajele, stampilele si Undo/Redo in 7.9; tiparirea, e-mailul si
salvarea paginilor in 7.10; paginile (tabul `Organize Pages`) in faza 8;
editarea continutului si semnele de carte noi in faza 9; securitatea si
semnarea in faza 10; formularele in faza 11; compararea in faza 12.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
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
from app.gui.i18n import tr, tr_error
from app.gui.pdf_panels import (
    AttachmentsPanel,
    BookmarksPanel,
    CommentsList,
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
}

LATER: dict[str, str] = {
    **{k: "7.8" for k in ("copy", "copy_area_text", "copy_area_table", "select_all")},
    **{k: "7.9" for k in ("undo", "redo", "delete", "add_note", "highlight", "underline",
                          "strikethrough", "insert_text", "draw", "add_stamp")},
    **{k: "7.10" for k in ("print", "email", "save_pages")},
    **{k: "8" for k in ("add_blank_page", "add_pages_pdf", "add_pages_file",
                        "add_pages_scanner", "rotate_right", "rotate_left",
                        "correct_orientation", "crop_pages", "replace_pages", "move_pages",
                        "delete_pages", "selected_pages", "split", "delete_blank_pages",
                        "enhance")},
    **{k: "9" for k in ("cut", "paste", "add_bookmark", "add_link", "erase",
                        "header_footer", "picture", "add_text")},
    **{k: "10" for k in ("signature", "password_security", "watermark",
                         "delete_objects")},
    **{k: "11" for k in ("text_field", "check_box", "radio_button", "dropdown_list",
                         "list_box", "button", "signature_field")},
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
    "content": ("header_footer", "picture", "add_text", "add_link"),               # B-205
    "security": ("signature", "password_security", "watermark", "erase", "redact",
                 "delete_objects", "select", "hand"),                              # B-206
    "forms": ("text_field", "check_box", "radio_button", "dropdown_list", "list_box",
              "button", "signature_field"),                                        # B-207
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

FULL_SCREEN_EDGE = 24
"""B-008: la cati pixeli de marginea de jos apare bara in ecranul complet."""


@dataclass
class OpenDocument:
    document: Any
    view: PdfView
    background: list[int]
    """Paginile care asteapta recunoasterea in fundal (B-028)."""


class PdfEditorWindow(QMainWindow):
    launcher_requested = Signal()
    options_requested = Signal(str)
    """Tabul dialogului Options care se deschide ('' = primul)."""
    help_requested = Signal()
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
        self._full_screen_state: dict[str, bool] = {}
        self._build_actions()
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_ribbon())
        layout.addWidget(self._build_js_banner())
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
                                  "redact"]):
            self._new_action(key)
        a = self.actions
        connect = {
            "new_task": self.launcher_requested.emit, "open": self.ask_open,
            "save": self.save, "save_as": self.save_as, "close": self.close_current,
            "options": lambda: self.options_requested.emit(""), "exit": self.close,
            "recognize_document": self.recognize_document,
            "navigation_pane": self.toggle_navigation_pane,
            "comments_pane": self.toggle_comments_pane, "go_to_page": self.ask_go_to_page,
            "full_screen": self.toggle_full_screen, "help": self.help_requested.emit,
            "select": lambda: self._set_tool(Tool.SELECT),
            "hand": lambda: self._set_tool(Tool.HAND),
            "find": lambda: self.open_search("find"),  # C-001
            "find_next": lambda: self.search_panel.next_hit(),  # C-005, F3
            "redaction_mode": lambda: self.open_search("redact"),
            "redact": lambda: self.open_search("redact"),
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
                bar.addAction(self.actions[command])
            self.toolbars[key] = bar
            self.ribbon_pages.addWidget(bar)
        self.ribbon_tabs.currentChanged.connect(self.ribbon_pages.setCurrentIndex)
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
                     "email", "options", "exit"),
            "edit": ("undo", "redo", "cut", "copy", "copy_area_text", "copy_area_table",
                     "paste", "delete", "select_all"),
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
        return menu

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
        """B-038: numai documentul curent."""
        current = self.current()
        if current is not None:
            self.policy.enable_for(current.document)
        self.js_banner.hide()

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
        self.comments_panel = CommentsList()
        self.comments_panel.hide()
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
        entry = OpenDocument(document, view, [])
        self.open_documents.append(entry)
        view.page_changed.connect(lambda _n: self._update_state())
        view.zoom_changed.connect(lambda _z: self._update_state())
        view.history_changed.connect(self._update_state)
        view.mode_changed.connect(lambda _m: self._update_state())
        title = document.path.name if document.path else tr("pdf.untitled")
        self.tabs.addTab(view, title)
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
        entry.view.deleteLater()
        if not self.open_documents:
            self.center.setCurrentWidget(self.empty_page)
        self._document_changed()
        return True

    def close_current(self) -> None:
        self.close_document(self.tabs.currentIndex())

    def _after_modify(self) -> None:
        """Documentul curent s-a schimbat (marcaje, inlocuire, redactare)."""
        current = self.current()
        if current is not None:
            current.view.reload()
        self.pages_panel.refresh()
        self.refresh_comments()
        self._update_state()

    def _document_changed(self) -> None:
        self.search_panel.document_switched()
        current = self.current()
        document = current.document if current is not None else None
        self.pages_panel.set_document(document)
        self.bookmarks_panel.set_document(document)
        self.attachments_panel.set_document(document)
        self.signatures_panel.set_document(document)
        self.refresh_comments()
        self._update_js_banner()
        self._update_state()

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

    def recognize_document(self) -> None:
        """B-032: stratul de text permanent; fisierul se modifica, deci se confirma."""
        from app.gui.progress import run_with_progress

        current = self.current()
        if current is None or not self.ask_confirm(tr("pdf.recognize.confirm")):
            return
        current.background.clear()
        try:
            stored = run_with_progress(
                tr("pdf.recognize.title"),
                lambda progress, cancel: current.document.recognize_and_store(
                    context=self.context, progress=progress), self)
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
        for widget in (self.page_field, self.zoom_combo, self.fit_combo, self.mode_button):
            widget.setEnabled(has)
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
        """B-008: in ecranul complet, bara de jos apare cand mouse-ul e la margine."""
        if self.isFullScreen() and event.type() == QEvent.Type.MouseMove:
            y = event.position().y()  # type: ignore[attr-defined]
            near = y >= watched.height() - FULL_SCREEN_EDGE  # type: ignore[attr-defined]
            self.bottom_bar.setVisible(near)
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: Any) -> None:  # API Qt
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():  # B-007
            self.exit_full_screen()
            return
        super().keyPressEvent(event)

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

    def save_attachment(self, name: str) -> None:
        current = self.current()
        if current is None:
            return
        target, _ = QFileDialog.getSaveFileName(self, tr("pdf.attachments.save"), name)
        if target:
            current.document.extract_attachment(name, Path(target))

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

    def ask_save_path(self, document: Any) -> Path | None:
        start = str(document.path) if document.path else tr("pdf.untitled") + ".pdf"
        path, _ = QFileDialog.getSaveFileName(self, tr("pdf.action.save_as"), start,
                                              tr("pdf.filter.pdf"))
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

    def open_external(self, url: QUrl) -> None:
        QDesktopServices.openUrl(url)

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
