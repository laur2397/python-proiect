"""Panoul de cautare al PDF Editor-ului (faza 7, pasul 7.8a): C-001…C-011,
C-015…C-018, C-025…C-032, C-100…C-111.

Tab-urile `FIND`, `REPLACE`, `REDACT` (C-101), campul de cautare cu optiunile
`Exact Match` si `Match Case` (C-102, C-003, C-004), arborele de rezultate
grupate pe sursa, cu bife si context (C-105, C-106, C-002), navigarea
(C-104, C-005), contorul (C-109, C-110). Toate rezultatele se evidentiaza
galben in pagina deodata (C-108).

Marcarea rezultatelor (C-007…C-010), inlocuirea (C-015…C-018) si redactarea
(C-025, C-026) lucreaza pe rezultatele bifate (C-011). Listele de cuvinte
cheie (C-027…C-032) se pastreaza in app.db.
"""

from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.core.model import AnnotationType
from app.core.pdf.keywords import Keyword, KeywordListStore, search_keywords
from app.core.pdf.text import SOURCES, SearchHit
from app.gui.i18n import tr, tr_error

PANEL_WIDTH = 190
"""C-100: latimea panoului de cautare."""
HIT_COLOR = QColor(255, 216, 77, 110)
"""C-108: evidentierea galbena a rezultatelor in pagina."""
CURRENT_COLOR = QColor("#b4690e")
MATCH_BACKGROUND = "#ffd84d"
"""C-105: potrivirea evidentiata galben in context."""
MARKUPS = (AnnotationType.HIGHLIGHT, AnnotationType.STRIKETHROUGH, AnnotationType.UNDERLINE)
TABS = ("find", "replace", "redact")


def context_html(hit: SearchHit) -> str:
    """Contextul rezultatului, cu potrivirea evidentiata (C-105)."""
    text, found = hit.context, hit.found
    index = text.casefold().find(found.casefold()) if found else -1
    if index < 0:
        return html.escape(text)
    before, match, after = text[:index], text[index:index + len(found)], \
        text[index + len(found):]
    return (f"{html.escape(before)}<span style='background:{MATCH_BACKGROUND}'>"
            f"{html.escape(match)}</span>{html.escape(after)}")


class KeywordListDialog(QDialog):
    """C-029, C-030: `Edit Keyword List...`: adaugare, editare, stergere,
    salvare; `Save and Find` salveaza si cauta."""

    def __init__(self, name: str, keywords: list[Keyword], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("keyword_list_dialog")
        self.setWindowTitle(tr("search.keywords.edit_title", name=name))
        self.find_after = False
        self.list = QListWidget()
        self.list.setObjectName("keyword_list")
        for keyword in keywords:
            self._add_item(keyword)
        self.word = QLineEdit()
        self.word.setObjectName("keyword_word")
        self.match_case = QCheckBox(tr("search.match_case"))
        self.whole_word = QCheckBox(tr("search.exact_match"))
        self.is_regex = QCheckBox(tr("search.keywords.regex"))
        add = QPushButton(tr("search.keywords.add"))
        add.setObjectName("keyword_add")
        add.clicked.connect(self.add_current)
        remove = QPushButton(tr("search.keywords.remove"))
        remove.setObjectName("keyword_remove")
        remove.clicked.connect(self.remove_selected)
        self.list.currentItemChanged.connect(self._show_selected)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        self.save_and_find = buttons.addButton(tr("search.keywords.save_and_find"),
                                               QDialogButtonBox.ButtonRole.AcceptRole)
        self.save_and_find.setObjectName("keyword_save_and_find")
        self.save_and_find.clicked.connect(self._mark_find)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(self.word, 1)
        row.addWidget(add)
        row.addWidget(remove)
        options = QHBoxLayout()
        for box in (self.match_case, self.whole_word, self.is_regex):
            options.addWidget(box)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list, 1)
        layout.addLayout(row)
        layout.addLayout(options)
        layout.addWidget(buttons)

    def _add_item(self, keyword: Keyword) -> None:
        item = QListWidgetItem(keyword.text)
        item.setData(Qt.ItemDataRole.UserRole, keyword)
        self.list.addItem(item)

    def add_current(self) -> None:
        text = self.word.text().strip()
        if not text or text in [k.text for k in self.keywords()]:
            return
        self._add_item(Keyword(text, self.match_case.isChecked(), self.whole_word.isChecked(),
                               self.is_regex.isChecked()))
        self.word.clear()

    def remove_selected(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            self.list.takeItem(row)

    def _show_selected(self, item: QListWidgetItem | None, _previous: Any = None) -> None:
        if item is None:
            return
        keyword: Keyword = item.data(Qt.ItemDataRole.UserRole)
        self.word.setText(keyword.text)
        self.match_case.setChecked(keyword.match_case)
        self.whole_word.setChecked(keyword.whole_word)
        self.is_regex.setChecked(keyword.is_regex)

    def _mark_find(self) -> None:
        self.find_after = True

    def keywords(self) -> list[Keyword]:
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list.count())]


class SearchPanel(QWidget):
    document_changed = Signal()
    """Documentul s-a modificat (marcaje, inlocuire, redactare)."""
    hit_activated = Signal(int)
    """Pagina rezultatului curent (C-005)."""
    closed = Signal()

    def __init__(self, context: Any, current: Callable[[], Any],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pdf_search_panel")
        self.setMinimumWidth(PANEL_WIDTH)
        self.context = context
        self._current = current
        """Functie: documentul si vizualizarea curente (`OpenDocument` sau None)."""
        self.store = KeywordListStore(context.app_db)
        self.hits: list[SearchHit] = []
        self.index = -1
        self.active_list: str | None = None
        self.before_change: Callable[[], None] | None = None
        """Se apeleaza inainte de o modificare a documentului (pasul de Undo)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(self._build_top())
        layout.addLayout(self._build_field())
        layout.addWidget(self._build_keywords())
        layout.addWidget(self._build_tab_pages())
        layout.addLayout(self._build_navigation())
        self.tree = QTreeWidget()  # C-105, C-106
        self.tree.setObjectName("search_results")
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("QTreeWidget#search_results::item:selected"
                                " { background: #dbe7fe; color: palette(text); }")  # C-107
        self.tree.itemChanged.connect(lambda _i, _c: self._update_state())
        self.tree.currentItemChanged.connect(self._current_item_changed)
        self.empty = QLabel(tr("search.no_matches"))  # C-109, C-110
        self.empty.setObjectName("search_no_matches")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.hide()
        self.status = QLabel()
        self.status.setObjectName("search_status")
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.empty, 1)
        layout.addWidget(self.status)
        self.tab_bar.currentChanged.connect(self._tab_changed)
        self._tab_changed(0)
        self._refresh_lists()
        self._update_state()

    # --- constructia ------------------------------------------------------------------

    def _build_top(self) -> QHBoxLayout:
        """C-101: tab-urile cu majuscule si X de inchidere."""
        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("search_tabs")
        for key in TABS:
            self.tab_bar.addTab(tr(f"search.tab.{key}").upper())
        close = QToolButton()
        close.setObjectName("search_close")
        close.setText("✕")
        close.setToolTip(tr("search.close"))
        close.clicked.connect(self.closed.emit)
        row = QHBoxLayout()
        row.addWidget(self.tab_bar, 1)
        row.addWidget(close)
        return row

    def _build_field(self) -> QHBoxLayout:
        """C-102: campul cu golire si rotita cu optiunile de potrivire."""
        from app.gui import icons

        self.field = QLineEdit()
        self.field.setObjectName("search_field")
        self.field.setPlaceholderText(tr("search.find_what"))
        self.field.setClearButtonEnabled(True)
        self.field.returnPressed.connect(self.run_search)
        self.options_button = QToolButton()
        self.options_button.setObjectName("search_options")
        self.options_button.setIcon(icons.icon("gear"))
        self.options_button.setToolTip(tr("search.options"))
        self.options_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        options = QMenu(self.options_button)
        self.exact_match = QAction(tr("search.exact_match"), self)
        self.match_case = QAction(tr("search.match_case"), self)
        for action in (self.exact_match, self.match_case):
            action.setCheckable(True)
            options.addAction(action)
        self.options_button.setMenu(options)
        row = QHBoxLayout()
        row.addWidget(self.field, 1)
        row.addWidget(self.options_button)
        return row

    def _build_keywords(self) -> QWidget:
        """C-111: combo-ul listelor de cuvinte cheie (tabul REDACT)."""
        self.keyword_combo = QComboBox()
        self.keyword_combo.setObjectName("keyword_combo")
        self.keyword_combo.setEditable(True)
        self.keyword_combo.lineEdit().setPlaceholderText(tr("search.keywords.placeholder"))
        self.keyword_combo.activated.connect(self._list_chosen)
        self.keyword_combo.lineEdit().returnPressed.connect(self._redact_text_entered)
        menu_button = QToolButton()
        menu_button.setObjectName("keyword_menu")
        menu_button.setText("▾")
        menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(menu_button)
        menu.addAction(tr("search.keywords.add_to_list"), self.add_keyword_to_list)  # C-027
        menu.addAction(tr("search.keywords.find_using"), self.find_using_list)  # C-028
        menu.addAction(tr("search.keywords.edit"), self.edit_keyword_list)  # C-029
        menu.addAction(tr("search.keywords.close"), self.close_keyword_list)  # C-032
        menu_button.setMenu(menu)
        self.keyword_menu = menu
        self.keyword_box = QWidget()
        row = QHBoxLayout(self.keyword_box)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.keyword_combo, 1)
        row.addWidget(menu_button)
        return self.keyword_box

    def _build_tab_pages(self) -> QWidget:
        find_page = QWidget()  # C-007…C-010: marcarea
        find_row = QHBoxLayout(find_page)
        find_row.setContentsMargins(0, 0, 0, 0)
        self.mark_buttons: dict[AnnotationType, QToolButton] = {}
        for kind in MARKUPS:
            button = QToolButton()
            button.setObjectName(f"search_mark_{kind.value}")
            button.setText(tr(f"annotation.{kind.value}"))
            button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            colors = QMenu(button)
            colors.addAction(tr("search.color"), lambda k=kind: self.choose_color(k))
            button.setMenu(colors)
            button.clicked.connect(lambda _c=False, k=kind: self.mark(k))
            find_row.addWidget(button)
            self.mark_buttons[kind] = button
        find_row.addStretch(1)
        replace_page = QWidget()  # C-015, C-103
        replace_box = QVBoxLayout(replace_page)
        replace_box.setContentsMargins(0, 0, 0, 0)
        self.replace_field = QLineEdit()
        self.replace_field.setObjectName("replace_field")
        self.replace_field.setPlaceholderText(tr("search.replace_with"))
        self.replace_button = QPushButton(tr("search.replace"))
        self.replace_button.setObjectName("replace_button")
        self.replace_button.clicked.connect(self.replace)
        replace_row = QHBoxLayout()
        replace_row.addStretch(1)
        replace_row.addWidget(self.replace_button)
        replace_box.addWidget(self.replace_field)
        replace_box.addLayout(replace_row)
        redact_page = QWidget()  # C-025, C-026
        redact_row = QHBoxLayout(redact_page)
        redact_row.setContentsMargins(0, 0, 0, 0)
        redact_row.addStretch(1)
        self.redact_button = QPushButton(tr("search.redact"))
        self.redact_button.setObjectName("redact_button")
        self.redact_button.clicked.connect(self.redact)
        redact_row.addWidget(self.redact_button)
        self.tab_pages = QStackedWidget()
        for page in (find_page, replace_page, redact_page):
            self.tab_pages.addWidget(page)
        return self.tab_pages

    def _build_navigation(self) -> QHBoxLayout:
        """C-104: sagetile, la stanga."""
        self.previous_button = QToolButton()
        self.previous_button.setObjectName("search_previous")
        self.previous_button.setText("<")
        self.previous_button.clicked.connect(self.previous_hit)
        self.next_button = QToolButton()
        self.next_button.setObjectName("search_next")
        self.next_button.setText(">")
        self.next_button.clicked.connect(self.next_hit)
        row = QHBoxLayout()
        row.addWidget(self.previous_button)
        row.addWidget(self.next_button)
        row.addStretch(1)
        return row

    # --- tab-urile --------------------------------------------------------------------

    def show_tab(self, key: str) -> None:
        self.tab_bar.setCurrentIndex(TABS.index(key))
        self.field.setFocus()

    def _tab_changed(self, index: int) -> None:
        self.tab_pages.setCurrentIndex(index)
        self.keyword_box.setVisible(TABS[index] == "redact")

    # --- cautarea (C-002…C-006) -------------------------------------------------------

    def run_search(self) -> None:
        current = self._current()
        query = self.field.text()
        if current is None or not query:
            self.set_hits([])
            return
        self.set_hits(current.document.search(query, match_case=self.match_case.isChecked(),
                                              whole_word=self.exact_match.isChecked()))

    def find_using_list(self, name: str | None = None) -> None:
        """C-028: cautarea cu o lista salvata (implicit, cea aleasa in combo)."""
        name = name or self.active_list or self.keyword_combo.currentText()
        current = self._current()
        if current is None or name not in self.store.names():
            return
        self.active_list = name
        self.keyword_combo.setEditText(name)
        self.set_hits(search_keywords(current.document, self.store.keywords(name)))

    def set_hits(self, hits: list[SearchHit]) -> None:
        self.hits = list(hits)
        self.index = -1
        self._fill_tree()
        if self.hits:
            self.go_to_hit(0)
        self._update_state()
        self._repaint_view()

    def _fill_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        for source in SOURCES:
            group = [(i, h) for i, h in enumerate(self.hits) if h.source == source]
            if not group:
                continue
            parent = QTreeWidgetItem(self.tree, [tr(f"search.source.{source}", n=len(group)),
                                                 ""])
            parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsUserCheckable |
                            Qt.ItemFlag.ItemIsAutoTristate)
            parent.setCheckState(0, Qt.CheckState.Unchecked)
            parent.setData(0, Qt.ItemDataRole.UserRole, -1)
            for index, hit in group:
                child = QTreeWidgetItem(parent, ["", str(hit.page) if hit.page else ""])
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setData(0, Qt.ItemDataRole.UserRole, index)
                child.setTextAlignment(1, Qt.AlignmentFlag.AlignRight)
                label = QLabel(context_html(hit))
                label.setTextFormat(Qt.TextFormat.RichText)
                label.setObjectName("search_context")
                self.tree.setItemWidget(child, 0, label)
            parent.setExpanded(True)
        self.tree.resizeColumnToContents(1)
        self.tree.blockSignals(False)

    def _items(self) -> list[QTreeWidgetItem]:
        out = []
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            out += [parent.child(j) for j in range(parent.childCount())]
        return out

    def checked_hits(self) -> list[SearchHit]:
        """C-011: rezultatele bifate (folosite la marcare, inlocuire, redactare)."""
        return [self.hits[item.data(0, Qt.ItemDataRole.UserRole)] for item in self._items()
                if item.checkState(0) == Qt.CheckState.Checked]

    def set_checked(self, indices: list[int] | None = None, checked: bool = True) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for item in self._items():
            if indices is None or item.data(0, Qt.ItemDataRole.UserRole) in indices:
                item.setCheckState(0, state)

    def _current_item_changed(self, item: QTreeWidgetItem | None, _previous: Any) -> None:
        if item is None:
            return
        index = item.data(0, Qt.ItemDataRole.UserRole)
        if index is not None and index >= 0 and index != self.index:
            self.go_to_hit(index)

    # --- navigarea (C-005, C-104) -----------------------------------------------------

    def go_to_hit(self, index: int) -> None:
        if not self.hits:
            return
        self.index = index % len(self.hits)
        hit = self.hits[self.index]
        for item in self._items():
            if item.data(0, Qt.ItemDataRole.UserRole) == self.index:
                self.tree.blockSignals(True)
                self.tree.setCurrentItem(item)
                self.tree.blockSignals(False)
        if hit.page:
            self.hit_activated.emit(hit.page)
        self._repaint_view()

    def next_hit(self) -> None:
        """C-005, F3."""
        if self.hits:
            self.go_to_hit(self.index + 1)

    def previous_hit(self) -> None:
        if self.hits:
            self.go_to_hit(self.index - 1)

    # --- evidentierea in pagina (C-108) -----------------------------------------------

    def paint_hits(self, painter: QPainter, view: Any) -> None:
        """Toate rezultatele din text, galben; cel curent, cu contur."""
        current = self._current()
        if current is None or view is not current.view:
            return
        visible = set(view.visible_pages())
        for i, hit in enumerate(self.hits):
            if hit.source != "text" or hit.page not in visible:
                continue
            for rect in hit.rects:
                box = view.page_to_view(hit.page, rect)
                if box is None:
                    continue
                painter.fillRect(box, HIT_COLOR)
                if i == self.index:
                    painter.setPen(QPen(CURRENT_COLOR, 2))
                    painter.drawRect(box.adjusted(-1, -1, 1, 1))

    def _repaint_view(self) -> None:
        current = self._current()
        if current is not None:
            current.view.viewport().update()

    # --- marcarea (C-007…C-010) -------------------------------------------------------

    def color_for(self, kind: AnnotationType) -> str:
        from app.core.pdf.markup import default_color

        return default_color(self.context.settings, kind)

    def choose_color(self, kind: AnnotationType) -> None:
        """C-010: alta culoare, care devine implicita."""
        color = self.ask_color(self.color_for(kind))
        if color:
            self.context.settings.set(f"pdf_editor.markup_color.{kind.value}", color)

    def mark(self, kind: AnnotationType) -> int:
        """C-007…C-009: comentarii pe rezultatele bifate; textul nu se schimba."""
        current = self._current()
        hits = [h for h in self.checked_hits() if h.source == "text"]
        if current is None or not hits:
            return 0
        author = self.context.settings.get("pdf_editor.default_author") or None
        self._before()
        count = current.document.mark_hits(hits, kind, self.color_for(kind), author=author)
        self.document_changed.emit()
        return count

    # --- inlocuirea (C-015…C-018) -----------------------------------------------------

    def replace(self) -> int:
        """C-015, C-016: rezultatele inlocuite ies din lista. C-018: pe un fond
        neuniform se avertizeaza inainte. C-017: se salveaza explicit."""
        from app.core.pdf.redact import background_is_uniform

        current = self._current()
        hits = [h for h in self.checked_hits() if h.source == "text"]
        if current is None or not hits:
            return 0
        document = current.document
        uneven = [h for h in hits if not all(background_is_uniform(document, h.page, r)
                                            for r in h.rects)]
        if uneven and not self.ask_confirm(tr("search.replace.uneven")):
            return 0
        self._before()
        try:
            count = document.replace_text(hits, self.replace_field.text())
        except CoreError as exc:
            self.show_message(tr_error(exc))
            return 0
        replaced = {id(h) for h in hits}
        self.set_hits([h for h in self.hits if id(h) not in replaced])
        self.document_changed.emit()
        return count

    # --- redactarea (C-025, C-026, G-021) ---------------------------------------------

    def redact(self) -> int:
        from app.core.pdf.security import SecurityService

        current = self._current()
        hits = [h for h in self.checked_hits() if h.source == "text"]
        if current is None or not hits:
            return 0
        if not self.ask_confirm(tr("search.redact.confirm", n=len(hits))):
            return 0
        words = [(h.found, True, False) for h in hits]
        self._before()
        try:
            count = SecurityService().redact_hits(current.document, hits, words=words)
        except CoreError as exc:  # G-021: verificarea a esuat, documentul a revenit
            self.show_message(tr_error(exc))
            return 0
        done = {id(h) for h in hits}
        self.set_hits([h for h in self.hits if id(h) not in done])
        self.document_changed.emit()
        return count

    def _before(self) -> None:
        if self.before_change is not None:
            self.before_change()

    # --- listele de cuvinte cheie (C-027…C-032) ---------------------------------------

    def _refresh_lists(self) -> None:
        text = self.keyword_combo.currentText()
        self.keyword_combo.blockSignals(True)
        self.keyword_combo.clear()
        for name in self.store.names():
            self.keyword_combo.addItem(name)
            words = ", ".join(k.text for k in self.store.keywords(name))
            self.keyword_combo.setItemData(self.keyword_combo.count() - 1, words,
                                           Qt.ItemDataRole.ToolTipRole)  # C-031
        self.keyword_combo.setEditText(text)
        self.keyword_combo.blockSignals(False)

    def _list_chosen(self, index: int) -> None:
        self.find_using_list(self.keyword_combo.itemText(index))

    def _redact_text_entered(self) -> None:
        self.field.setText(self.keyword_combo.currentText())
        self.run_search()

    def add_keyword_to_list(self) -> None:
        """C-027: textul curent intra intr-o lista (cea activa sau una noua)."""
        text = self.field.text().strip() or self.keyword_combo.currentText().strip()
        if not text:
            return
        name = self.active_list or self.ask_list_name()
        if not name:
            return
        self.store.add(name, Keyword(text, self.match_case.isChecked(),
                                     self.exact_match.isChecked()))
        self.active_list = name
        self._refresh_lists()

    def edit_keyword_list(self) -> None:
        """C-029, C-030."""
        name = self.active_list or self.ask_list_name()
        if not name:
            return
        keywords = self.store.keywords(name) if name in self.store.names() else []
        dialog = KeywordListDialog(name, keywords, self)
        if not self.exec_dialog(dialog):
            return
        self.store.save(name, dialog.keywords())
        self.active_list = name
        self._refresh_lists()
        if dialog.find_after:
            self.find_using_list(name)

    def close_keyword_list(self) -> None:
        """C-032: lista nu mai e folosita la cautare."""
        self.active_list = None
        self.keyword_combo.setEditText("")

    # --- starea -----------------------------------------------------------------------

    def _update_state(self) -> None:
        count = len(self.hits)
        self.status.setText(tr("search.found", n=count))  # C-109
        searched = bool(self.field.text()) or self.active_list is not None
        self.empty.setVisible(searched and count == 0)
        self.tree.setVisible(count > 0)
        has_checked = bool(self.checked_hits())
        self.replace_button.setEnabled(has_checked)  # C-103
        self.redact_button.setEnabled(has_checked)
        for button in self.mark_buttons.values():
            button.setEnabled(has_checked)
        self.previous_button.setEnabled(count > 1)
        self.next_button.setEnabled(count > 1)

    def document_switched(self) -> None:
        """Alt document in fata: rezultatele vechi nu mai sunt valabile."""
        self.set_hits([])

    # --- dialogurile (inlocuite in teste) ---------------------------------------------

    def ask_color(self, current: str) -> str | None:
        color = QColorDialog.getColor(QColor(current), self, tr("search.color"))
        return color.name().upper() if color.isValid() else None

    def ask_list_name(self) -> str | None:
        name, ok = QInputDialog.getText(self, tr("search.keywords.new_title"),
                                        tr("search.keywords.new_label"))
        return name.strip() if ok and name.strip() else None

    def ask_confirm(self, text: str) -> bool:
        return QMessageBox.question(self, tr("pdf.window.empty"), text) == \
            QMessageBox.StandardButton.Yes

    def show_message(self, text: str) -> None:
        QMessageBox.information(self, tr("pdf.window.empty"), text)

    def exec_dialog(self, dialog: QDialog) -> bool:
        return dialog.exec() == QDialog.DialogCode.Accepted

    def sizeHint(self) -> QSize:  # API Qt
        return QSize(PANEL_WIDTH + 60, 400)
