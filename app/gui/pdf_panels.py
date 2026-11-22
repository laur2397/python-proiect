"""Panourile PDF Editor-ului (faza 7, pasul 7.7b): `Pages`, `Bookmarks`,
`Attachments`, `Digital Signatures` (B-019…B-024, B-307…B-309). Panoul
`Comments` e in `pdf_comments.py`.

Panourile nu iau decizii: citesc documentul prin nucleu si anunta fereastra
ce a cerut utilizatorul (`page_requested`, `open_requested`, `save_requested`).

INCOMPLET, marcat: toolbarul panoului `Pages` (rotirile si meniul `...`, B-308,
B-310) are comenzile paginilor din faza 8 (E-*); pana atunci butoanele sunt
dezactivate.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedLayout,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.gui.i18n import tr

THUMB = 84
"""Latimea miniaturii (B-307: panoul are circa 120 px)."""
TEXT_BADGE = "#2f6df6"
"""B-309: insigna albastra = pagina are strat de text."""
CURRENT_BACKGROUND = "#e5e7eb"
"""B-309: pagina curenta are fundal gri."""


class _Stacked(QWidget):
    """Continutul panoului si mesajul pentru starea goala (B-021)."""

    def __init__(self, empty_key: str, toolbar: QToolBar | None = None) -> None:
        super().__init__()
        self.empty = QLabel(tr(empty_key))
        self.empty.setObjectName("empty_state")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setProperty("muted", True)
        self.stack = QStackedLayout()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if toolbar is not None:
            layout.addWidget(toolbar)
        layout.addLayout(self.stack, 1)

    def set_content(self, widget: QWidget) -> None:
        self.stack.addWidget(widget)
        self.stack.addWidget(self.empty)
        self.content = widget

    def show_empty(self, empty: bool) -> None:
        self.stack.setCurrentWidget(self.empty if empty else self.content)

    def is_empty(self) -> bool:
        return self.stack.currentWidget() is self.empty


# --- Pages (B-020, B-307…B-309) -------------------------------------------------------


def thumbnail(image: QImage | None, has_text: bool) -> QIcon:
    """Miniatura cu chenar si, cand pagina are text, insigna albastra (B-309)."""
    width, height = THUMB, int(THUMB * 1.414)
    scale = 2
    canvas = QPixmap(width * scale, height * scale)
    canvas.setDevicePixelRatio(scale)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if image is not None and not image.isNull():
        fitted = image.scaled(QSize(width - 2, height - 2), Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        left, top = (width - fitted.width()) // 2, (height - fitted.height()) // 2
        painter.fillRect(left, top, fitted.width(), fitted.height(), QColor("#ffffff"))
        painter.drawImage(left, top, fitted)
        painter.setPen(QColor("#c9ced6"))
        painter.drawRect(left, top, fitted.width() - 1, fitted.height() - 1)
    else:
        painter.fillRect(0, 0, width, height, QColor("#c7ccd4"))
    if has_text:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(TEXT_BADGE))
        painter.drawRoundedRect(3, height - 13, 10, 10, 2, 2)
    painter.end()
    icon = QIcon()
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Selected):
        icon.addPixmap(canvas, mode)
    return icon


class PagesPanel(QWidget):
    page_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pdf_pages_panel")
        self.document: Any = None
        self.actions: dict[str, Any] = {}
        self.list = QListWidget()
        self.list.setObjectName("pdf_pages_list")
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setFlow(QListWidget.Flow.TopToBottom)
        self.list.setWrapping(False)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setIconSize(QSize(THUMB, int(THUMB * 1.414)))
        self.list.setSpacing(4)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setStyleSheet(
            f"QListWidget#pdf_pages_list::item:selected {{ background: {CURRENT_BACKGROUND};"
            " color: palette(text); }")
        self.list.currentRowChanged.connect(self._row_changed)
        self._pending: list[int] = []
        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._render_next)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar())
        layout.addWidget(self.list, 1)
        self.setMinimumWidth(120)

    def _toolbar(self) -> QToolBar:
        """B-308: rotiri si `...`; fereastra le leaga de comenzile paginilor (faza 8)."""
        from app.gui import icons

        bar = QToolBar()
        bar.setObjectName("pdf_pages_toolbar")
        bar.setIconSize(QSize(16, 16))
        for key in ("rotate_left", "rotate_right"):
            action = bar.addAction(icons.icon(key), tr(f"pdf.pages.{key}"))
            action.setObjectName(f"pdf_pages_{key}")
            action.setEnabled(False)
            self.actions[key] = action
        self.more = QToolButton()  # E-034, E-036, E-037: meniul paginilor
        self.more.setObjectName("pdf_pages_more")
        self.more.setText("...")
        self.more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more.setEnabled(False)
        bar.addWidget(self.more)
        return bar

    def set_document(self, document: Any) -> None:
        self.document = document
        self.refresh()

    def refresh(self) -> None:
        """Miniaturile se deseneaza pe rand, dupa afisare (lenes)."""
        self.list.blockSignals(True)
        self.list.clear()
        self._pending = []
        if self.document is not None:
            placeholder = thumbnail(None, False)
            for n in range(1, self.document.page_count + 1):
                item = QListWidgetItem(placeholder, str(n))
                item.setData(Qt.ItemDataRole.UserRole, n)
                self.list.addItem(item)
            self._pending = list(range(1, self.document.page_count + 1))
            self._timer.start()
        self.list.blockSignals(False)

    def _render_next(self) -> None:
        if not self._pending or self.document is None:
            self._timer.stop()
            return
        number = self._pending.pop(0)
        try:
            image: QImage | None = QImage.fromData(
                self.document.render_page(number, 0.15, annotations=True), "PNG")
        except (CoreError, ValueError):
            image = None
        item = self.list.item(number - 1)
        if item is not None:
            item.setIcon(thumbnail(image, self.document.has_searchable_text(number)))
            item.setData(Qt.ItemDataRole.UserRole + 1,
                         self.document.has_searchable_text(number))

    def render_all(self) -> None:
        """Toate miniaturile acum (pentru teste)."""
        while self._pending:
            self._render_next()

    def set_current(self, page: int) -> None:
        self.list.blockSignals(True)
        self.list.setCurrentRow(page - 1)
        self.list.blockSignals(False)

    def _row_changed(self, row: int) -> None:
        if row >= 0:
            self.page_requested.emit(row + 1)


# --- Bookmarks (B-021) ----------------------------------------------------------------


class BookmarksPanel(_Stacked):
    page_requested = Signal(int, float)
    """Pagina si pozitia verticala (puncte de sus); -1 = inceputul paginii."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("pdf.bookmarks.empty")
        self.setObjectName("pdf_bookmarks_panel")
        self.tree = QTreeWidget()
        self.tree.setObjectName("pdf_bookmarks_tree")
        self.tree.setHeaderHidden(True)
        self.set_content(self.tree)
        self.tree.itemClicked.connect(self._activated)
        self.tree.itemActivated.connect(self._activated)

    def set_document(self, document: Any) -> None:
        self.tree.clear()
        marks = document.bookmarks() if document is not None else []

        def add(parent: Any, items: list[Any]) -> None:
            for mark in items:
                node = QTreeWidgetItem(parent, [mark.title])
                node.setData(0, Qt.ItemDataRole.UserRole,
                             (mark.target_page or 0,
                              -1.0 if mark.target_y is None else float(mark.target_y)))
                add(node, mark.children)

        add(self.tree, marks)
        self.tree.expandToDepth(0)
        self.show_empty(not marks)

    def _activated(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        page, y = item.data(0, Qt.ItemDataRole.UserRole)
        if page:
            self.page_requested.emit(page, y)


# --- Attachments (B-023, B-034) -------------------------------------------------------


def size_text(octets: int) -> str:
    if octets < 1024:
        return tr("pdf.size.bytes", n=octets)
    if octets < 1024 * 1024:
        return tr("pdf.size.kb", n=f"{octets / 1024:.1f}")
    return tr("pdf.size.mb", n=f"{octets / 1024 / 1024:.1f}")


class AttachmentsPanel(_Stacked):
    open_requested = Signal(str)
    save_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        from app.gui import icons

        bar = QToolBar()
        bar.setIconSize(QSize(16, 16))
        super().__init__("pdf.attachments.empty", bar)
        self.setObjectName("pdf_attachments_panel")
        self.open_action = bar.addAction(icons.icon("folder_open"),
                                         tr("pdf.attachments.open"))
        self.save_action = bar.addAction(icons.icon("save"), tr("pdf.attachments.save"))
        self.list = QListWidget()
        self.list.setObjectName("pdf_attachments_list")
        self.set_content(self.list)
        self.open_action.triggered.connect(lambda: self._emit(self.open_requested))
        self.save_action.triggered.connect(lambda: self._emit(self.save_requested))
        self.list.itemActivated.connect(lambda _item: self._emit(self.open_requested))

    def set_document(self, document: Any) -> None:
        from app.gui import icons

        self.list.clear()
        files = document.attachments() if document is not None else []
        for name, size, executable in files:
            item = QListWidgetItem(f"{name}  ({size_text(size)})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            if executable:  # F-048: se vede inainte de deschidere
                item.setIcon(icons.icon("warning", "#b4690e"))
                item.setToolTip(tr("pdf.attachments.executable"))
            self.list.addItem(item)
        self.show_empty(not files)
        self.open_action.setEnabled(bool(files))
        self.save_action.setEnabled(bool(files))

    def selected(self) -> str | None:
        item = self.list.currentItem() or (self.list.item(0) if self.list.count() else None)
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)

    def _emit(self, signal: Any) -> None:
        name = self.selected()
        if name:
            signal.emit(name)


# --- Digital Signatures (B-024) -------------------------------------------------------


STATUS_COLORS = {"valid": "#15803d", "modified": "#b4690e", "invalid": "#b42318"}


class SignaturesPanel(_Stacked):
    page_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("pdf.signatures.empty")
        self.setObjectName("pdf_signatures_panel")
        self.list = QListWidget()
        self.list.setObjectName("pdf_signatures_list")
        self.list.setWordWrap(True)
        self.set_content(self.list)
        self.list.itemActivated.connect(self._activated)

    def set_document(self, document: Any) -> None:
        from app.core.pdf import signatures
        from app.gui import icons

        self.list.clear()
        found = signatures.signatures(document) if document is not None else []
        for sig in found:
            lines = [sig.field_name, tr(f"pdf.signatures.status.{sig.status}"),
                     tr("pdf.signatures.signer",
                        name=sig.signer or tr("pdf.signatures.unknown"))]
            if sig.signed_at:
                lines.append(tr("pdf.signatures.date",
                                date=sig.signed_at.replace("T", " ").rstrip("Z")))
            if sig.trusted is None:
                lines.append(tr("pdf.signatures.trust_unknown"))
            glyph = "check" if sig.status == "valid" else "warning"
            item = QListWidgetItem(icons.icon(glyph, STATUS_COLORS[sig.status]), "\n".join(lines))
            item.setData(Qt.ItemDataRole.UserRole, sig.page or 0)
            self.list.addItem(item)
        self.show_empty(not found)

    def _activated(self, item: QListWidgetItem) -> None:
        page = item.data(Qt.ItemDataRole.UserRole)
        if page:
            self.page_requested.emit(page)
