"""Panoul `Comments` al PDF Editor-ului (faza 7, pasul 7.9a): D-008,
D-024…D-044, D-100…D-105.

Antetul cu `X` (D-101), campul de filtrare dupa text (D-102, D-034), randul de
controale: navigarea `<` `>` (D-033), sortarea `AZ ▾` (D-035), palnia de filtre
(D-036…D-043) si optiunile (D-044, ascunderea textului). Fiecare comentariu e o
fisa: iconul colorat dupa tip, data si pagina, bifa personala (D-030), textul
(`Enter your comment`, D-025), raspunsurile si `Add Reply` (D-026). Meniul
contextual: raspuns, stergere (D-027, D-028), status (D-031), proprietati cu
istoricul statusurilor si `Set Default` pentru autor (D-032).

Panoul nu modifica documentul direct: cere ferestrei `modify(operatie)`, care
pastreaza pasul pentru Undo si reimprospateaza vizualizarea.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.model import AnnotationData, ReviewStatus
from app.core.pdf import annotations as ann
from app.gui.i18n import tr

PANEL_WIDTH = 150
"""D-100: latimea panoului."""
SELECTED_BACKGROUND = "#dbe7fe"
"""D-105: comentariul selectat are fundal albastru deschis."""


def when(iso: str, now: datetime | None = None) -> str:
    """D-104: `Azi 19:02` sau data, in ora locala."""
    if not iso:
        return ""
    try:
        moment = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).astimezone()
    except ValueError:
        return ""
    now = (now or datetime.now(UTC)).astimezone()
    if moment.date() == now.date():
        return tr("comments.today", time=moment.strftime("%H:%M"))
    return moment.strftime("%d.%m.%Y %H:%M")


def default_author(settings: Any) -> str:
    """D-032: autorul memorat cu `Set Default`, altfel numele contului."""
    import getpass

    saved = settings.get("pdf_editor.default_author")
    if saved:
        return str(saved)
    try:
        return getpass.getuser()
    except (OSError, KeyError):
        return ""


def status_text(value: ReviewStatus | None) -> str:
    return tr(f"comments.status.{value.value}") if value else tr("comments.status.none")


class PropertiesDialog(QDialog):
    """D-032: autor, subiect si istoricul statusurilor; `Set Default`."""

    def __init__(self, annot: AnnotationData, history: list[tuple[Any, Any, str]],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("comment_properties")
        self.setWindowTitle(tr("comments.properties.title"))
        self.set_default = False
        self.author = QLineEdit(annot.author or "")
        self.author.setObjectName("properties_author")
        self.subject = QLineEdit(annot.subject or "")
        self.subject.setObjectName("properties_subject")
        self.history = QListWidget()
        self.history.setObjectName("properties_history")
        for status, who, date in history:
            self.history.addItem(f"{status_text(status)} · {who or ''} · {when(date)}")
        default = QPushButton(tr("comments.properties.set_default"))
        default.setObjectName("properties_set_default")
        default.clicked.connect(self._mark_default)
        form = QFormLayout()
        form.addRow(tr("comments.properties.author"), self.author)
        form.addRow(tr("comments.properties.subject"), self.subject)
        form.addRow(tr("comments.properties.history"), self.history)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(default)
        layout.addWidget(buttons)

    def _mark_default(self) -> None:
        self.set_default = True


class CommentCard(QFrame):
    """D-104: o fisa de comentariu, cu raspunsurile ei."""

    selected = Signal(int)

    def __init__(self, panel: CommentsPanel, annot: AnnotationData) -> None:
        from app.gui import icons

        super().__init__()
        self.panel = panel
        self.annot = annot
        self.setObjectName("comment_card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.context_menu().exec(self.mapToGlobal(pos)))
        head = QHBoxLayout()
        kind = QLabel()
        kind.setPixmap(icons.swatch(annot.color or "#64748b").pixmap(QSize(12, 12)))
        kind.setToolTip(tr(f"annotation.{annot.annot_type.value}"))
        head.addWidget(kind)
        stamp = f"{when(annot.created_at)}  {tr('comments.page', n=annot.page_number)}"
        self.header = QLabel(stamp.strip())
        self.header.setObjectName("comment_header")
        head.addWidget(self.header, 1)
        if annot.review_status is not None:
            status = QLabel(status_text(annot.review_status))
            status.setObjectName("comment_status")
            status.setProperty("muted", True)
            head.addWidget(status)
        self.check = QCheckBox()  # D-030
        self.check.setObjectName("comment_check")
        self.check.setChecked(annot.is_checked)
        self.check.setToolTip(tr("comments.checkmark"))
        self.check.toggled.connect(self._checked)
        head.addWidget(self.check)
        self.author = QLabel(annot.author or tr("pdf.comments.no_author"))
        self.author.setObjectName("comment_author")
        self.text = QLineEdit(annot.content or "")  # D-025
        self.text.setObjectName("comment_text")
        self.text.setPlaceholderText(tr("comments.enter"))
        self.text.editingFinished.connect(self._text_changed)
        self.replies = QVBoxLayout()
        for reply in annot.replies:
            self._add_reply_row(reply, 0)
        self.reply_link = QPushButton(tr("comments.add_reply"))  # D-026
        self.reply_link.setObjectName("comment_add_reply")
        self.reply_link.setFlat(True)
        self.reply_link.clicked.connect(self.start_reply)
        self.reply_field = QLineEdit()
        self.reply_field.setObjectName("comment_reply_field")
        self.reply_field.setPlaceholderText(tr("comments.reply_placeholder"))
        self.reply_field.returnPressed.connect(self.submit_reply)
        self.reply_field.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)
        layout.addLayout(head)
        layout.addWidget(self.author)
        layout.addWidget(self.text)
        layout.addLayout(self.replies)
        layout.addWidget(self.reply_field)
        layout.addWidget(self.reply_link, 0, Qt.AlignmentFlag.AlignLeft)
        self.set_text_hidden(panel.text_hidden)

    def _add_reply_row(self, reply: AnnotationData, depth: int) -> None:
        row = QLabel(f"{'  ' * depth}↳ {reply.author or ''}: {reply.content or ''}")
        row.setObjectName("comment_reply")
        row.setWordWrap(True)
        row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        row.customContextMenuRequested.connect(
            lambda pos, r=reply, w=row: self._reply_menu(r).exec(w.mapToGlobal(pos)))
        row.setProperty("reply_id", reply.id)
        self.replies.addWidget(row)
        for child in reply.replies:
            self._add_reply_row(child, depth + 1)

    def _reply_menu(self, reply: AnnotationData) -> QMenu:
        menu = QMenu(self)
        menu.addAction(tr("comments.delete_reply"),
                       lambda: self.panel.delete([reply.id]))  # D-027
        return menu

    def set_text_hidden(self, hidden: bool) -> None:
        """D-044: raman vizibili numai autorii si datele."""
        for widget in (self.text, self.reply_link):
            widget.setVisible(not hidden)
        for i in range(self.replies.count()):
            self.replies.itemAt(i).widget().setVisible(not hidden)

    def mousePressEvent(self, event: Any) -> None:  # API Qt
        self.selected.emit(self.annot.id or 0)
        super().mousePressEvent(event)

    def context_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction(tr("comments.add_comment"), self.text.setFocus)  # D-025
        menu.addAction(tr("comments.reply"), self.start_reply)  # D-026
        menu.addAction(tr("comments.checkmark"), lambda: self.check.setChecked(True))
        status = menu.addMenu(tr("comments.status"))  # D-031
        for value in (*ReviewStatus, None):
            status.addAction(status_text(value),
                             lambda v=value: self.panel.set_status(self.annot.id, v))
        menu.addSeparator()
        menu.addAction(tr("comments.delete"), lambda: self.panel.delete([self.annot.id]))
        menu.addAction(tr("comments.properties"), lambda: self.panel.properties(self.annot))
        return menu

    def start_reply(self) -> None:
        self.reply_field.show()
        self.reply_field.setFocus()

    def submit_reply(self) -> None:
        """D-026: raspunsul, cu autorul implicit."""
        text = self.reply_field.text().strip()
        if text:
            self.panel.reply(self.annot.id, text)

    def _text_changed(self) -> None:
        if self.text.text() != (self.annot.content or ""):
            self.panel.set_content(self.annot, self.text.text())

    def _checked(self, checked: bool) -> None:
        if checked != self.annot.is_checked:
            self.panel.set_checked(self.annot.id, checked)

    def set_selected(self, on: bool) -> None:
        self.setStyleSheet(f"QFrame#comment_card {{ background: {SELECTED_BACKGROUND}; }}"
                           if on else "")


class CommentsPanel(QWidget):
    page_requested = Signal(int)
    annotation_selected = Signal(int)
    closed = Signal()

    def __init__(self, settings: Any, current: Callable[[], Any],
                 modify: Callable[[Callable[[Any], Any]], Any],
                 parent: QWidget | None = None) -> None:
        from app.gui import icons

        super().__init__(parent)
        self.setObjectName("pdf_comments_panel")
        self.setMinimumWidth(PANEL_WIDTH)
        self.settings = settings
        self._current = current
        self._modify = modify
        """Aplica operatia pe documentul curent, cu Undo si reimprospatare."""
        self.filter = ann.CommentFilter()
        self.sort_key = "page"
        self.text_hidden = False
        self.all: list[AnnotationData] = []
        self.items: list[AnnotationData] = []
        self.cards: list[CommentCard] = []
        self.selected_id: int | None = None
        header = QHBoxLayout()  # D-101
        title = QLabel(tr("pdf.action.comments_pane"))
        title.setObjectName("comments_title")
        close = QToolButton()
        close.setObjectName("comments_close")
        close.setText("✕")
        close.clicked.connect(self.closed.emit)
        header.addWidget(title, 1)
        header.addWidget(close)
        self.search = QLineEdit()  # D-102
        self.search.setObjectName("comments_filter")
        self.search.setPlaceholderText(tr("comments.filter_text"))
        self.search.addAction(icons.icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(lambda _t: self.refresh())
        controls = QHBoxLayout()  # D-103
        self.previous_button = QToolButton()
        self.previous_button.setObjectName("comments_previous")
        self.previous_button.setText("<")
        self.previous_button.clicked.connect(lambda: self.step(-1))
        self.next_button = QToolButton()
        self.next_button.setObjectName("comments_next")
        self.next_button.setText(">")
        self.next_button.clicked.connect(lambda: self.step(1))
        self.sort_button = QToolButton()
        self.sort_button.setObjectName("comments_sort")
        self.sort_button.setText("AZ ▾")
        self.sort_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.sort_button.setMenu(self._sort_menu())
        self.filter_button = QToolButton()
        self.filter_button.setObjectName("comments_filter_menu")
        self.filter_button.setText("⏷")
        self.filter_button.setToolTip(tr("comments.filter"))
        self.filter_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.filter_button.setMenu(QMenu(self.filter_button))
        self.filter_button.menu().aboutToShow.connect(self.fill_filter_menu)
        self.options_button = QToolButton()
        self.options_button.setObjectName("comments_options")
        self.options_button.setIcon(icons.icon("gear"))
        self.options_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        options = QMenu(self.options_button)
        self.hide_text_action = QAction(tr("comments.hide_text"), self)  # D-044
        self.hide_text_action.setCheckable(True)
        self.hide_text_action.toggled.connect(self.set_text_hidden)
        options.addAction(self.hide_text_action)
        self.options_button.setMenu(options)
        for widget in (self.previous_button, self.next_button, self.sort_button,
                       self.filter_button):
            controls.addWidget(widget)
        controls.addStretch(1)
        controls.addWidget(self.options_button)
        self.list_box = QVBoxLayout()
        self.list_box.addStretch(1)
        holder = QWidget()
        holder.setLayout(self.list_box)
        scroll = QScrollArea()
        scroll.setObjectName("comments_scroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        self.empty = QLabel(tr("pdf.comments.empty"))
        self.empty.setObjectName("comments_empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(header)
        layout.addWidget(self.search)
        layout.addLayout(controls)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.empty)

    # --- lista ------------------------------------------------------------------------

    def set_document(self, _document: Any = None) -> int:
        """Reciteste comentariile; intoarce numarul total (B-305)."""
        current = self._current()
        self.all = current.document.annotations() if current is not None else []
        if self.selected_id not in {a.id for a in self.all}:
            self.selected_id = None
        self.refresh()
        return len(self.all)

    def refresh(self) -> None:
        shown = ann.filter_comments(self.all, self.filter, self.search.text().strip())
        self.items = ann.sort_comments(shown, self.sort_key)
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards = []
        for annot in self.items:
            card = CommentCard(self, annot)
            card.selected.connect(self.select)
            self.list_box.insertWidget(self.list_box.count() - 1, card)
            self.cards.append(card)
        self.empty.setVisible(not self.items)
        self._mark_selected()

    def card(self, annot_id: int) -> CommentCard | None:
        return next((c for c in self.cards if c.annot.id == annot_id), None)

    def select(self, annot_id: int) -> None:
        """D-105; duce la pagina comentariului."""
        self.selected_id = annot_id
        self._mark_selected()
        card = self.card(annot_id)
        if card is not None:
            self.page_requested.emit(card.annot.page_number)
            self.annotation_selected.emit(annot_id)

    def _mark_selected(self) -> None:
        for card in self.cards:
            card.set_selected(card.annot.id == self.selected_id)

    def step(self, delta: int) -> None:
        """D-033: comentariul urmator sau anterior."""
        if not self.items:
            return
        ids = [a.id for a in self.items]
        index = ids.index(self.selected_id) if self.selected_id in ids else -1
        self.select(ids[max(0, min(len(ids) - 1, index + delta))])

    def focus_comment(self, annot_id: int) -> None:
        """D-008: dublu clic pe adnotare = campul comentariului."""
        self.select(annot_id)
        card = self.card(annot_id)
        if card is not None:
            card.text.setFocus()

    # --- sortarea si filtrele (D-035…D-044) -------------------------------------------

    def _sort_menu(self) -> QMenu:
        menu = QMenu(self)
        group = QActionGroup(self)
        for key in ann.SORT_KEYS:
            action = menu.addAction(tr(f"comments.sort.{key}"))
            action.setCheckable(True)
            action.setChecked(key == self.sort_key)
            action.triggered.connect(lambda _c=False, k=key: self.set_sort(k))
            group.addAction(action)
        return menu

    def set_sort(self, key: str) -> None:
        self.sort_key = key
        self.refresh()

    def fill_filter_menu(self) -> None:
        menu = self.filter_button.menu()
        menu.clear()
        menu.addAction(tr("comments.show_all"), self.show_all)  # D-036
        menu.addAction(tr("comments.hide_current"), self.hide_current)
        menu.addSeparator()
        types = menu.addMenu(tr("comments.filter.type"))  # D-037
        for kind in sorted({a.annot_type for a in self.all}, key=lambda k: k.value):
            self._check_action(types, tr(f"annotation.{kind.value}"),
                               self.filter.types is None or kind in self.filter.types,
                               lambda on, k=kind: self.toggle_filter("types", k, on))
        authors = menu.addMenu(tr("comments.filter.author"))  # D-038
        for who in sorted({a.author or "" for a in self.all}):
            self._check_action(authors, who or tr("pdf.comments.no_author"),
                               self.filter.authors is None or who in self.filter.authors,
                               lambda on, w=who: self.toggle_filter("authors", w, on))
        menu.addAction(tr("comments.filter.page"), self.ask_page_range)  # D-039
        menu.addAction(tr("comments.filter.date"), self.ask_date_range)  # D-040
        flags = menu.addMenu(tr("comments.filter.flag"))  # D-041
        for value, key in ((None, "all"), (True, "checked"), (False, "unchecked")):
            self._check_action(flags, tr(f"comments.filter.flag.{key}"),
                               self.filter.checked == value,
                               lambda _on, v=value: self.set_flag_filter(v))
        statuses = menu.addMenu(tr("comments.status"))  # D-042
        for value in (*ReviewStatus, None):
            self._check_action(statuses, status_text(value),
                               self.filter.statuses is None or value in self.filter.statuses,
                               lambda on, v=value: self.toggle_filter("statuses", v, on))
        menu.addSeparator()
        menu.addAction(tr("comments.filter.reset"), self.reset_filters)  # D-043

    @staticmethod
    def _check_action(menu: QMenu, text: str, checked: bool,
                      slot: Callable[[bool], None]) -> QAction:
        action = menu.addAction(text)
        action.setCheckable(True)
        action.setChecked(checked)
        action.toggled.connect(slot)
        return action

    def toggle_filter(self, field: str, value: Any, on: bool) -> None:
        """D-037, D-038, D-042: o valoare intra sau iese din filtru."""
        current = getattr(self.filter, field)
        if current is None:
            current = {"types": {a.annot_type for a in self.all},
                       "authors": {a.author or "" for a in self.all},
                       "statuses": {*ReviewStatus, None}}[field]
        current = set(current)
        if on:
            current.add(value)
        else:
            current.discard(value)
        setattr(self.filter, field, current)
        self.refresh()

    def set_flag_filter(self, value: bool | None) -> None:
        """D-041."""
        self.filter.checked = value
        self.refresh()

    def show_all(self) -> None:
        """D-036 `Show All Comments`."""
        self.filter.hidden = set()
        self.refresh()

    def hide_current(self) -> None:
        """D-036 `Hide Current Comments`: cele afisate acum se ascund."""
        self.filter.hidden |= {a.id for a in self.items if a.id is not None}
        self.refresh()

    def reset_filters(self) -> None:
        """D-043."""
        self.filter.reset()
        self.search.clear()
        self.refresh()

    def set_text_hidden(self, hidden: bool) -> None:
        """D-044."""
        self.text_hidden = hidden
        for card in self.cards:
            card.set_text_hidden(hidden)

    def ask_page_range(self) -> None:
        """D-039."""
        current = self._current()
        total = current.document.page_count if current is not None else 1
        first, ok = QInputDialog.getInt(self, tr("comments.filter.page"),
                                        tr("comments.filter.page_from"), 1, 1, total)
        if not ok:
            return
        last, ok = QInputDialog.getInt(self, tr("comments.filter.page"),
                                       tr("comments.filter.page_to"), total, first, total)
        if ok:
            self.filter.pages = (first, last)
            self.refresh()

    def ask_date_range(self) -> None:
        """D-040: datele in forma AAAA-LL-ZZ."""
        first, ok = QInputDialog.getText(self, tr("comments.filter.date"),
                                         tr("comments.filter.date_from"))
        if not ok:
            return
        last, ok = QInputDialog.getText(self, tr("comments.filter.date"),
                                        tr("comments.filter.date_to"))
        if ok and first.strip() and last.strip():
            self.filter.dates = (first.strip(), last.strip())
            self.refresh()

    # --- modificarile -----------------------------------------------------------------

    def author(self) -> str:
        return default_author(self.settings)

    def set_content(self, annot: AnnotationData, text: str) -> None:
        """D-025: textul comentariului."""
        self._modify(lambda doc: doc.update_annotation(replace(annot, content=text)))

    def reply(self, annot_id: int | None, text: str) -> None:
        if annot_id is not None:
            self._modify(lambda doc: doc.add_reply(annot_id, text, self.author()))

    def delete(self, ids: list[int | None]) -> None:
        """D-027, D-028: cu raspunsurile si statusurile."""
        chosen = [i for i in ids if i is not None]
        if chosen:
            self._modify(lambda doc: doc.delete_annotations(chosen))

    def set_status(self, annot_id: int | None, status: ReviewStatus | None) -> None:
        if annot_id is not None:
            self._modify(lambda doc: ann.set_review_status(doc, annot_id, status,
                                                           self.author()))

    def set_checked(self, annot_id: int | None, checked: bool) -> None:
        if annot_id is not None:
            self._modify(lambda doc: ann.set_checked(doc, annot_id, checked, self.author()))

    def properties(self, annot: AnnotationData) -> None:
        """D-032."""
        current = self._current()
        if current is None or annot.id is None:
            return
        dialog = PropertiesDialog(annot, ann.status_history(current.document, annot.id), self)
        if not self.exec_dialog(dialog):
            return
        author, subject = dialog.author.text().strip(), dialog.subject.text().strip()
        if dialog.set_default and author:
            self.settings.set("pdf_editor.default_author", author)
        if (author, subject) != (annot.author or "", annot.subject or ""):
            self._modify(lambda doc: doc.update_annotation(
                replace(annot, author=author or None, subject=subject or None)))

    def exec_dialog(self, dialog: QDialog) -> bool:
        return dialog.exec() == QDialog.DialogCode.Accepted

    def sizeHint(self) -> QSize:  # API Qt
        return QSize(PANEL_WIDTH + 110, 400)
