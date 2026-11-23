"""Panoul Pages (faza 6b, pasul 6b.2): J-403…J-408.

Miniaturile paginilor, cu insigna de stare in stanga-jos (J-405) si
triunghiul de avertisment in dreapta-jos (J-406), tooltipul cu starea si
fisierul sursa (J-407), selectia multipla, toolbarul cu stergere si rotiri
(J-404). Operatiile trec prin `OcrProject` (undo, regulile paginilor).

INCOMPLET, marcat: in tooltip lipseste „Opened by” (J-407), care cere lucrul
in grup (nu exista inca in nucleu). Salvarea imaginilor o leaga fereastra (6b.6b).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStyle,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.core.model import PageData, PageStatus
from app.gui.i18n import tr, tr_error

PANEL_WIDTH = 120
"""J-403: latimea panoului, circa 95 px la miniatura (plus margini)."""

THUMB = 84
"""Latura miniaturii afisate."""

STATUS_MARKS = {
    PageStatus.IMPORTED: "○",
    PageStatus.PREPROCESSED: "○",
    PageStatus.ANALYZED: "◐",
    PageStatus.RECOGNIZED: "●",
    PageStatus.VERIFIED: "✓",
    PageStatus.ERROR: "!",
}
"""J-405: semnul insignei de stare (simbol, nu text de interfata)."""


def tooltip(page: PageData) -> str:
    """J-407: starea si fisierul sursa, cate unul pe rand."""
    lines = [tr(f"page.status.{page.status.value}")]
    source = page.source_file or page.original_path
    if source is not None:
        lines.append(tr("page.source", path=source.name))
    return "\n".join(lines)


STATUS_COLORS = {
    PageStatus.IMPORTED: "#8b95a6",
    PageStatus.PREPROCESSED: "#8b95a6",
    PageStatus.ANALYZED: "#b4690e",
    PageStatus.RECOGNIZED: "#2f6df6",
    PageStatus.VERIFIED: "#1a7f52",
    PageStatus.ERROR: "#b42318",
}
"""Culoarea insignei de stare (paleta proprie a temei)."""


def thumbnail(page: PageData, style: QStyle) -> QIcon:
    """Miniatura: foaia cu chenar, insigna de stare colorata in stanga-jos (J-405)
    si triunghiul de avertisment in dreapta-jos (J-406)."""
    from app.gui import icons

    width, height = THUMB, int(THUMB * 1.414)
    reader = QImageReader(str(page.image_path))
    size = reader.size()
    if size.isValid() and size.width() and size.height():
        reader.setScaledSize(size.scaled(QSize(width - 2, height - 2),
                                         Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    scale = 2
    canvas = QPixmap(width * scale, height * scale)
    canvas.setDevicePixelRatio(scale)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillRect(0, 0, width, height, QColor("#ffffff"))
    if not image.isNull():
        painter.drawImage((width - image.width()) // 2, (height - image.height()) // 2, image)
    painter.setPen(QColor("#d6dae1"))
    painter.drawRect(0, 0, width - 1, height - 1)
    badge = 14
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(STATUS_COLORS[page.status]))
    painter.drawRoundedRect(3, height - badge - 3, badge, badge, 3, 3)
    painter.setPen(QColor("#ffffff"))
    font = painter.font()
    font.setPixelSize(9)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(3, height - badge - 3, badge, badge, Qt.AlignmentFlag.AlignCenter,
                     STATUS_MARKS[page.status])
    if page.warnings:
        warn = icons.icon("warning", "#b4690e").pixmap(badge, badge)
        painter.drawPixmap(width - badge - 3, height - badge - 3, warn)
    painter.end()
    result = QIcon()
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Selected):  # selectia nu coloreaza foaia
        result.addPixmap(canvas, mode)
    return result


class PagesPanel(QWidget):
    page_activated = Signal(int)
    """Numarul paginii alese (1..N)."""
    changed = Signal()
    """Paginile s-au schimbat in proiect (stergere, rotire)."""
    message = Signal(str)

    def __init__(self, project: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pages_panel")
        self.project = project
        self.actions: dict[str, QAction] = {}
        self.list = QListWidget()
        self.list.setObjectName("pages_list")
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setFlow(QListWidget.Flow.TopToBottom)
        self.list.setWrapping(False)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setIconSize(QSize(THUMB, int(THUMB * 1.414)))
        self.list.setGridSize(QSize(THUMB + 16, int(THUMB * 1.414) + 26))
        self.list.setSpacing(4)
        self.list.setFrameShape(QListWidget.Shape.NoFrame)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.currentRowChanged.connect(self._row_changed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar())
        layout.addWidget(self.list, 1)
        self.setMinimumWidth(PANEL_WIDTH)

    # --- J-404 ------------------------------------------------------------------------

    def _toolbar(self) -> QToolBar:
        from app.gui import icons

        bar = QToolBar()
        bar.setObjectName("pages_toolbar")
        bar.setIconSize(QSize(16, 16))
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)  # textul in tooltip
        glyphs = {"save": "save", "delete": "trash", "rotate_left": "rotate_left",
                  "rotate_right": "rotate_right"}
        for key in ("save", "delete", "rotate_left", "rotate_right"):
            action = bar.addAction(icons.icon(glyphs[key]), tr(f"pages.{key}"))
            action.setObjectName(f"pages_{key}")
            self.actions[key] = action
        self.actions["delete"].triggered.connect(self.delete_selected)
        self.actions["rotate_left"].triggered.connect(lambda: self.rotate_selected(-90))
        self.actions["rotate_right"].triggered.connect(lambda: self.rotate_selected(90))
        more = QToolButton()
        more.setObjectName("pages_more")
        more.setText("...")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(more)
        select_all = menu.addAction(tr("pages.select_all"))
        select_all.triggered.connect(self.list.selectAll)
        more.setMenu(menu)
        self.more_menu = menu
        """Meniul `...`; OCR Editor adauga `Reorder Pages...` (J-059)."""
        bar.addWidget(more)
        return bar

    # --- continut ---------------------------------------------------------------------

    def refresh(self, current: int) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        style = self.style()
        for page in self.project.pages:
            item = QListWidgetItem(thumbnail(page, style), str(page.page_number))
            item.setToolTip(tooltip(page))
            item.setData(Qt.ItemDataRole.UserRole, page.page_number)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(max(0, min(current, self.list.count()) - 1))
        self.list.blockSignals(False)

    def selected_numbers(self) -> list[int]:
        rows = sorted({self.list.row(item) for item in self.list.selectedItems()})
        if not rows and self.list.currentRow() >= 0:
            rows = [self.list.currentRow()]
        return [r + 1 for r in rows]

    def _row_changed(self, row: int) -> None:
        if row >= 0:
            self.page_activated.emit(row + 1)

    def _run(self, operation: Any) -> None:
        try:
            operation()
        except CoreError as exc:
            self.message.emit(tr_error(exc))
            return
        self.changed.emit()

    def delete_selected(self) -> None:
        numbers = self.selected_numbers()
        if numbers:
            self._run(lambda: self.project.delete_pages(numbers))

    # J-058: sensul acelor de ceasornic pozitiv
    def rotate_selected(self, degrees: int) -> None:
        numbers = self.selected_numbers()
        if numbers:
            self._run(lambda: self.project.rotate_pages(numbers, degrees))
