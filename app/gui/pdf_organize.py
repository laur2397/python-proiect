"""Modul `Organize Pages` din PDF Editor (faza 8, pasul 8.3):
E-001…E-003, E-009, E-018, E-039, E-100…E-107.

Grila de miniaturi mari, pe fundal gri, inlocuieste pagina in centrul ferestrei
cand e activ tabul `Organize Pages`. Selectia: clic, `Ctrl`+clic, `Shift`+clic si
cadrul tras peste miniaturi (E-102). La hover apare un mini-toolbar vertical cu
trei comenzi (E-104). Paginile se reordoneaza prin tragere: miniatura trasa e
semitransparenta (E-105), iar intre miniaturi apare indicatorul de inserare
(E-106). Sliderul din dreapta jos schimba marimea miniaturilor (E-107).

Vederea nu modifica documentul: cere operatiile prin semnale, iar fereastra le
aplica prin `PageOrganizer`, cu pas de Undo.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDrag, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.gui.i18n import tr

GRID_BACKGROUND = "#d5d8de"
"""E-100: fundalul gri al grilei."""
SELECTED_BACKGROUND = "#cddcfb"
"""E-101: fundalul albastru deschis, rotunjit, al paginii selectate."""
ACCENT = "#2f6df6"
"""E-101, E-106: eticheta cu numarul paginii selectate si indicatorul de inserare."""
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 80, 360, 20
"""E-107: latimea miniaturilor, in pixeli."""
ZOOM_DEFAULT = 180
"""E-100: patru-cinci coloane pe o fereastra obisnuita."""
LABEL_HEIGHT = 26
PAGE_ROLE = Qt.ItemDataRole.UserRole
HOVER_COMMANDS = ("delete", "rotate_left", "rotate_right")
"""E-104: cele trei iconuri ale mini-toolbarului."""


class _Delegate(QStyledItemDelegate):
    """E-101: fundal albastru deschis rotunjit si eticheta albastra cu numarul
    paginii, pe paginile selectate."""

    def __init__(self, grid: _Grid) -> None:
        super().__init__(grid)
        self.grid = grid

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # API Qt
        size = self.grid.iconSize()
        return QSize(size.width() + 20, size.height() + LABEL_HEIGHT + 16)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,  # API Qt
              index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRect(option.rect).adjusted(3, 3, -3, -3)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(SELECTED_BACKGROUND))
            painter.drawRoundedRect(rect, 8, 8)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        size = self.grid.iconSize()
        image_rect = QRect(rect.left() + (rect.width() - size.width()) // 2, rect.top() + 6,
                           size.width(), size.height())
        if isinstance(icon, QIcon):
            icon.paint(painter, image_rect, Qt.AlignmentFlag.AlignCenter)
        number = str(index.data(PAGE_ROLE))
        label = QRect(rect.left(), image_rect.bottom() + 6, rect.width(), LABEL_HEIGHT - 6)
        if selected:
            width = painter.fontMetrics().horizontalAdvance(number) + 16
            badge = QRect(label.center().x() - width // 2, label.top(), width, label.height())
            painter.setBrush(QColor(ACCENT))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, number)
        else:
            painter.setPen(QColor("#30343b"))
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, number)
        painter.restore()


class _Grid(QListWidget):
    """Grila; tragerea si plasarea sunt interpretate, nu executate de Qt."""

    move_requested = Signal(list, int)
    hovered = Signal(int)
    """Randul de sub mouse (-1 = niciunul), pentru mini-toolbar."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("organize_grid")
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Snap)
        self.setUniformItemSizes(True)
        self.setSpacing(10)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionRectVisible(True)  # E-102
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setMouseTracking(True)
        self.setStyleSheet(f"QListWidget#organize_grid {{ background: {GRID_BACKGROUND};"
                           " border: none; }")
        self.setItemDelegate(_Delegate(self))
        self.drop_target: int | None = None
        """E-106: pozitia de inserare in timpul tragerii (1..n+1)."""

    # --- E-018, E-105, E-106 ---------------------------------------------------------

    def selected_pages(self) -> list[int]:
        return sorted(int(i.data(PAGE_ROLE)) for i in self.selectedItems())

    def target_at(self, pos: QPoint) -> int:
        """Pozitia de inserare (1..n+1) pentru un punct din viewport: inaintea
        miniaturii de sub mouse, sau dupa ea in jumatatea ei din dreapta."""
        index = self.indexAt(pos)
        if not index.isValid():
            last = self.count()
            if last and pos.y() < self.visualRect(self.model().index(0, 0)).top():
                return 1
            return last + 1
        rect = self.visualRect(index)
        return index.row() + 1 + (1 if pos.x() > rect.center().x() else 0)

    def startDrag(self, actions: Any) -> None:  # API Qt
        items = self.selectedItems()
        if not items:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData(items))
        pixmap = items[0].icon().pixmap(self.iconSize())
        faded = QPixmap(pixmap.size())
        faded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(faded)
        painter.setOpacity(0.5)  # E-105: semitransparenta
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        drag.setPixmap(faded)
        drag.setHotSpot(QPoint(faded.width() // 2, faded.height() // 2))
        drag.exec(Qt.DropAction.MoveAction)
        self.drop_target = None
        self.viewport().update()

    def dragEnterEvent(self, event: Any) -> None:  # API Qt
        if event.source() is self:
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: Any) -> None:  # API Qt
        if event.source() is not self:
            event.ignore()
            return
        self.drop_target = self.target_at(event.position().toPoint())
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
        self.viewport().update()

    def dragLeaveEvent(self, event: Any) -> None:  # API Qt
        self.drop_target = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: Any) -> None:  # API Qt
        if event.source() is not self:
            event.ignore()
            return
        target = self.target_at(event.position().toPoint())
        pages = self.selected_pages()
        event.setDropAction(Qt.DropAction.IgnoreAction)  # ordinea o schimba fereastra
        event.accept()
        self.drop_target = None
        self.viewport().update()
        if pages:
            self.move_requested.emit(pages, target)

    def indicator_rect(self) -> QRect | None:
        """E-106: unde se deseneaza iconul albastru de pagina, intre miniaturi."""
        if self.drop_target is None or not self.count():
            return None
        row = min(self.drop_target, self.count()) - 1
        rect = self.visualRect(self.model().index(row, 0))
        x = rect.left() - 7 if self.drop_target <= self.count() else rect.right() + 3
        return QRect(x, rect.top() + rect.height() // 3, 12, 16)

    def paintEvent(self, event: Any) -> None:  # API Qt
        super().paintEvent(event)
        mark = self.indicator_rect()
        if mark is None:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(ACCENT))
        painter.drawRoundedRect(mark, 2, 2)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(mark.left() + 3, mark.top() + 4, mark.width() - 6, 2)
        painter.drawRect(mark.left() + 3, mark.top() + 8, mark.width() - 6, 2)
        painter.end()

    def mouseMoveEvent(self, event: Any) -> None:  # API Qt
        index = self.indexAt(event.position().toPoint())
        self.hovered.emit(index.row() if index.isValid() else -1)
        super().mouseMoveEvent(event)


class HoverBar(QFrame):
    """E-009, E-104: plutitor vertical, in coltul din dreapta-sus al miniaturii."""

    command = Signal(str, int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        from app.gui import icons

        self.setObjectName("organize_hover_bar")
        self.setStyleSheet("QFrame#organize_hover_bar { background: #ffffff;"
                           " border: 1px solid #c9ced6; border-radius: 4px; }")
        column = QVBoxLayout(self)
        column.setContentsMargins(1, 1, 1, 1)
        column.setSpacing(0)
        self.page = 0
        self.buttons: dict[str, QToolButton] = {}
        for key in HOVER_COMMANDS:
            button = QToolButton()
            button.setObjectName(f"organize_hover_{key}")
            button.setIcon(icons.icon({"delete": "trash"}.get(key, key)))
            button.setToolTip(tr(f"organize.hover.{key}"))
            button.setAutoRaise(True)
            button.clicked.connect(lambda _c=False, k=key: self.command.emit(k, self.page))
            column.addWidget(button)
            self.buttons[key] = button
        self.hide()


class OrganizeView(QWidget):
    """E-001: grila de miniaturi mari a documentului curent."""

    selection_changed = Signal()
    move_requested = Signal(list, int)
    """Paginile selectate si pozitia de inserare (1..n+1), E-018."""
    page_command = Signal(str, list)
    """O comanda din mini-toolbar (E-104) si pagina ei."""
    page_activated = Signal(int)
    """Dublu clic pe o miniatura: pagina se deschide in vizualizare."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.gui import icons

        self.setObjectName("organize_view")
        self.document: Any = None
        self.grid = _Grid()
        self.grid.itemSelectionChanged.connect(self.selection_changed.emit)
        self.grid.move_requested.connect(self.move_requested.emit)
        self.grid.hovered.connect(self._hover)
        self.grid.itemDoubleClicked.connect(
            lambda item: self.page_activated.emit(int(item.data(PAGE_ROLE))))
        self.grid.verticalScrollBar().valueChanged.connect(lambda _v: self._hover(-1))
        self.hover_bar = HoverBar(self.grid.viewport())
        self.hover_bar.command.connect(lambda key, page: self.page_command.emit(key, [page]))
        self.zoom_out = QToolButton()
        self.zoom_out.setObjectName("organize_zoom_out")
        self.zoom_out.setIcon(icons.icon("zoom_out"))
        self.zoom_out.setToolTip(tr("organize.zoom_out"))
        self.zoom_in = QToolButton()
        self.zoom_in.setObjectName("organize_zoom_in")
        self.zoom_in.setIcon(icons.icon("zoom_in"))
        self.zoom_in.setToolTip(tr("organize.zoom_in"))
        self.slider = QSlider(Qt.Orientation.Horizontal)  # E-039, E-107: - ---o--- +
        self.slider.setObjectName("organize_zoom")
        self.slider.setRange(ZOOM_MIN, ZOOM_MAX)
        self.slider.setSingleStep(ZOOM_STEP)
        self.slider.setPageStep(ZOOM_STEP)
        self.slider.setFixedWidth(140)
        self.slider.setValue(ZOOM_DEFAULT)
        self.slider.valueChanged.connect(self.set_thumb_width)
        self.zoom_out.clicked.connect(
            lambda: self.slider.setValue(self.slider.value() - ZOOM_STEP))
        self.zoom_in.clicked.connect(
            lambda: self.slider.setValue(self.slider.value() + ZOOM_STEP))
        bottom = QHBoxLayout()
        bottom.setContentsMargins(6, 2, 6, 2)
        bottom.addStretch(1)
        bottom.addWidget(self.zoom_out)
        bottom.addWidget(self.slider)
        bottom.addWidget(self.zoom_in)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.grid, 1)
        layout.addLayout(bottom)
        self._pending: list[int] = []
        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._render_next)
        self.set_thumb_width(ZOOM_DEFAULT)

    # --- continutul -------------------------------------------------------------------

    @property
    def thumb_width(self) -> int:
        return self.grid.iconSize().width()

    def set_thumb_width(self, width: int) -> None:
        """E-107: grila se rearanjeaza; miniaturile se redeseneaza la noua marime."""
        width = max(ZOOM_MIN, min(ZOOM_MAX, int(width)))
        if self.slider.value() != width:
            self.slider.setValue(width)
            return
        self.grid.setIconSize(QSize(width, int(width * 1.414)))
        self.zoom_out.setEnabled(width > ZOOM_MIN)
        self.zoom_in.setEnabled(width < ZOOM_MAX)
        self.grid.doItemsLayout()
        if self.document is not None:
            self._pending = list(range(1, self.grid.count() + 1))
            self._timer.start()

    def set_document(self, document: Any) -> None:
        self.document = document
        self.refresh()

    def refresh(self, selected: list[int] | None = None) -> None:
        """Miniaturile din nou (dupa o modificare); `selected` = paginile care
        raman selectate (implicit cele selectate inainte, daca mai exista)."""
        keep = self.selected_pages() if selected is None else selected
        self.grid.blockSignals(True)
        self.grid.clear()
        self._pending = []
        self.hover_bar.hide()
        if self.document is not None:
            total = self.document.page_count
            blank = _placeholder(self.grid.iconSize())
            for n in range(1, total + 1):
                item = QListWidgetItem(blank, "")
                item.setData(PAGE_ROLE, n)
                item.setToolTip(tr("organize.page", page=n))
                self.grid.addItem(item)
                item.setSelected(n in keep)
            self._pending = list(range(1, total + 1))
            self._timer.start()
        self.grid.blockSignals(False)
        self.selection_changed.emit()

    def _render_next(self) -> None:
        from app.core.pdf.document import SCREEN_DPI

        if not self._pending or self.document is None:
            self._timer.stop()
            return
        number = self._pending.pop(0)
        item = self.grid.item(number - 1)
        if item is None:
            return
        try:
            width_pt, _height = self.document.page_size(number)
            zoom = 2 * self.thumb_width * 72 / (max(width_pt, 1) * SCREEN_DPI)
            image = QImage.fromData(self.document.render_page(number, zoom), "PNG")
        except (CoreError, ValueError):
            return
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(2)
        item.setIcon(QIcon(pixmap))

    def render_all(self) -> None:
        """Toate miniaturile acum (pentru teste)."""
        while self._pending:
            self._render_next()

    # --- selectia (E-002…E-004) -------------------------------------------------------

    def selected_pages(self) -> list[int]:
        return self.grid.selected_pages()

    def select_pages(self, pages: list[int]) -> None:
        wanted = set(pages)
        self.grid.blockSignals(True)
        for row in range(self.grid.count()):
            item = self.grid.item(row)
            item.setSelected(int(item.data(PAGE_ROLE)) in wanted)
        self.grid.blockSignals(False)
        if wanted:
            first = self.grid.item(min(wanted) - 1)
            if first is not None:
                self.grid.scrollToItem(first)
        self.selection_changed.emit()

    # --- mini-toolbarul (E-009, E-104) ------------------------------------------------

    def _hover(self, row: int) -> None:
        if row < 0 or self.grid.state() == QAbstractItemView.State.DraggingState:
            if not self.hover_bar.underMouse():
                self.hover_bar.hide()
            return
        rect = self.grid.visualRect(self.grid.model().index(row, 0))
        self.hover_bar.page = row + 1
        self.hover_bar.adjustSize()
        self.hover_bar.move(rect.right() - self.hover_bar.width() - 6, rect.top() + 6)
        self.hover_bar.show()
        self.hover_bar.raise_()


def _placeholder(size: QSize) -> QIcon:
    pixmap = QPixmap(size)
    pixmap.fill(QColor("#eceef1"))
    return QIcon(pixmap)
