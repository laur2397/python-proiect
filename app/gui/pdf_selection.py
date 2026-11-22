"""Selectia din PDF Editor (faza 7, pasul 7.8b): C-040…C-049, C-112…C-115.

Cu unealta `Select` (B-300): o apasare pe text incepe o selectie de text, care
poate trece peste pagini (C-044); o apasare in afara textului trage o zona de
copiat, punctata (C-112), care trebuie sa ramana pe o singura pagina (C-040).
Langa zona apare un buton cu cele trei moduri de copiere, iar clic dreapta
deschide acelasi meniu (C-041…C-045).

Copierea ca tabel (C-045) intra in modul tabel: grila detectata se deseneaza
peste zona (C-113), iar sub ea apare toolbarul plutitor cu noua comenzi
(C-114, C-115): copiaza, separator orizontal, separator vertical, sterge
separatoare, imparte celule, uneste celule, uneste randuri, selectie si
`Analyze table structure`. Fisierul PDF nu se modifica (C-047).
"""

from __future__ import annotations

import io
from typing import Any

from PySide6.QtCore import (
    QEvent,
    QMimeData,
    QObject,
    QPoint,
    QPointF,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMenu, QToolBar, QToolButton

from app.core.errors import CoreError
from app.core.model import Rect
from app.core.pdf import copying
from app.gui.i18n import tr, tr_error

AREA_PEN = QColor("#2f6df6")
TEXT_SELECTION = QColor(47, 109, 246, 70)
GRID_COLOR = QColor("#6d5bd0")
"""C-113: liniile grilei, albastru-mov."""
CELL_SELECTED = QColor(109, 91, 208, 70)
"""C-113: celula selectata, mov."""
MIN_AREA = 3.0
"""O zona mai mica de 3 puncte e un clic, nu o zona."""
TABLE_TOOLS = ("copy", "add_horizontal", "add_vertical", "delete_separators", "split_cells",
               "merge_cells", "merge_rows", "select_cells", "analyze")
"""C-114: cele noua comenzi ale toolbarului de tabel, in ordine."""
TABLE_GLYPHS = {"copy": "file", "add_horizontal": "rows", "add_vertical": "columns",
                "delete_separators": "trash", "split_cells": "grid", "merge_cells": "table",
                "merge_rows": "reorder", "select_cells": "cursor", "analyze": "recognize"}


class SelectionController(QObject):
    """Selectia unei vizualizari. Fereastra cere copierea prin metodele `copy*`
    si afla daca exista ceva de copiat din `has_selection()`."""

    changed = Signal()
    message = Signal(str)
    double_clicked = Signal(int, float, float)
    """Dublu clic pe pagina (D-008: comentariul adnotarii de acolo)."""

    def __init__(self, view: Any, context: Any = None) -> None:
        super().__init__(view)
        self.view = view
        self.context = context
        self.mode: str | None = None
        """None, 'text', 'area' sau 'table'."""
        self.text_start: tuple[int, int] | None = None
        self.text_end: tuple[int, int] | None = None
        self.area: tuple[int, Rect] | None = None
        self.table: copying.AreaTable | None = None
        self.table_tool = "select_cells"
        self.selected_cells: list[Any] = []
        self._press: tuple[int, float, float] | None = None
        self._drag_point: QPointF | None = None
        self.grab_annotation: Any = None
        """Functie (pagina, x, y) → adnotarea care se muta, sau None (D-052)."""
        self.drop_annotation: Any = None
        """Functie (adnotare, dx, dy): adnotarea a fost mutata."""
        self._moving: tuple[Any, float, float] | None = None
        self._dragging = False
        view.viewport().installEventFilter(self)
        view.overlays.append(self.paint)
        self.area_button = self._area_button()
        self.table_bar = self._table_bar()

    # --- widgeturile plutitoare -------------------------------------------------------

    def _copy_menu(self) -> QMenu:
        menu = QMenu(self.view)
        menu.addAction(tr("selection.copy_image"), self.copy_area_image)
        menu.addAction(tr("selection.copy_text"), self.copy_area_text)
        menu.addAction(tr("selection.copy_table"), self.start_table)
        return menu

    def _area_button(self) -> QToolButton:
        """C-041: iconul de langa zona, cu cele trei moduri."""
        from app.gui import icons

        button = QToolButton(self.view.viewport())
        button.setObjectName("selection_copy_button")
        button.setIcon(icons.icon("file"))
        button.setToolTip(tr("selection.copy_options"))
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(self._copy_menu())
        button.hide()
        return button

    def _table_bar(self) -> QToolBar:
        """C-114, C-115: toolbarul plutitor de tabel."""
        from app.gui import icons

        bar = QToolBar(self.view.viewport())
        bar.setObjectName("table_toolbar")
        self.table_actions: dict[str, Any] = {}
        for key in TABLE_TOOLS:
            action = bar.addAction(icons.icon(TABLE_GLYPHS[key]), tr(f"selection.table.{key}"))
            action.setObjectName(f"table_{key}")
            self.table_actions[key] = action
        for key in ("add_horizontal", "add_vertical", "delete_separators", "select_cells"):
            self.table_actions[key].setCheckable(True)
            self.table_actions[key].triggered.connect(
                lambda _c=False, k=key: self.set_table_tool(k))
        self.table_actions["copy"].triggered.connect(self.copy_table)
        self.table_actions["split_cells"].triggered.connect(self.split_cells)
        self.table_actions["merge_cells"].triggered.connect(self.merge_cells)
        self.table_actions["merge_rows"].triggered.connect(self.merge_rows)
        self.table_actions["analyze"].triggered.connect(self.analyze_table)
        self.table_actions["select_cells"].setChecked(True)
        bar.hide()
        return bar

    def _place_widgets(self) -> None:
        self.area_button.hide()
        self.table_bar.hide()
        if self.area is None or self.mode not in ("area", "table"):
            return
        box = self.view.page_to_view(*self.area)
        if box is None:
            return
        box = box.translated(-QPointF(self.view.horizontalScrollBar().value(),
                                      self.view.verticalScrollBar().value()))
        if self.mode == "area":
            self.area_button.adjustSize()
            self.area_button.move(QPoint(int(box.right()) + 4, int(box.top())))
            self.area_button.show()
        else:
            self.table_bar.adjustSize()
            self.table_bar.move(QPoint(int(box.left()), int(box.bottom()) + 6))  # C-115
            self.table_bar.show()

    # --- starea -----------------------------------------------------------------------

    def clear(self) -> None:
        self.mode = None
        self.text_start = self.text_end = None
        self.area = None
        self.table = None
        self.selected_cells = []
        self._place_widgets()
        self.view.viewport().update()
        self.changed.emit()

    def has_selection(self) -> bool:
        return self.mode is not None

    def selected_text(self) -> str:
        if self.mode != "text" or self.text_start is None or self.text_end is None:
            return ""
        return copying.text_between(self.view.document, self.text_start, self.text_end)

    def select_all(self) -> None:
        """`Select All`: tot textul documentului."""
        document = self.view.document
        last = document.page_count
        self.mode = "text"
        self.text_start = (1, 0)
        self.text_end = (last, max(0, len(document.page_text(last).text) - 1))
        self._place_widgets()
        self.view.viewport().update()
        self.changed.emit()

    def set_area(self, page: int, rect: Rect) -> bool:
        """C-040: zona trebuie sa fie pe o singura pagina."""
        try:
            copying.check_area(self.view.document, page, rect)
        except ValueError:
            return False
        self.mode = "area"
        self.area = (page, rect)
        self.table = None
        self._place_widgets()
        self.view.viewport().update()
        self.changed.emit()
        return True

    # --- mouse-ul (C-040, C-044, C-112) -----------------------------------------------

    def _content_point(self, event: Any) -> QPointF:
        return event.position() + QPointF(self.view.horizontalScrollBar().value(),
                                          self.view.verticalScrollBar().value())

    def _char_at(self, page: int, x: float, y: float) -> int | None:
        if not self.view.document.has_searchable_text(page):
            return None
        return copying.char_index_at(self.view.document, page, x, y)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # API Qt
        from app.gui.pdf_view import Tool

        if self.view.active_tool is not Tool.SELECT or self.view.document is None:
            return False
        kind = event.type()
        if kind == QEvent.Type.MouseButtonDblClick:
            hit = self.view.view_to_page(self._content_point(event))
            if hit is not None:
                self.double_clicked.emit(*hit)
            return True
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            return self._press_at(self._content_point(event))
        if self._moving is not None and kind == QEvent.Type.MouseButtonRelease:
            annot, x0, y0 = self._moving
            self._moving = None
            hit = self.view.view_to_page(self._content_point(event))
            if hit is not None and hit[0] == annot.page_number and \
                    (abs(hit[1] - x0) > 1 or abs(hit[2] - y0) > 1) and self.drop_annotation:
                self.drop_annotation(annot, hit[1] - x0, hit[2] - y0)
            return True
        if self._moving is not None and kind == QEvent.Type.MouseMove:
            return True
        if kind == QEvent.Type.MouseMove and self._press is not None:
            self._move_to(self._content_point(event))
            return True
        if kind == QEvent.Type.MouseButtonRelease and self._press is not None:
            self._release_at(self._content_point(event))
            return True
        if kind == QEvent.Type.ContextMenu and self.mode in ("area", "text"):
            menu = self._copy_menu() if self.mode == "area" else self._text_menu()
            menu.exec(event.globalPos())
            return True
        return False

    def _text_menu(self) -> QMenu:
        menu = QMenu(self.view)
        menu.addAction(tr("selection.copy_text_selection"), self.copy)
        return menu

    def _press_at(self, point: QPointF) -> bool:
        hit = self.view.view_to_page(point)
        if self.mode == "table" and self.table is not None and hit is not None \
                and self.area is not None and hit[0] == self.area[0]:
            return self._table_click(hit[1], hit[2])
        if hit is None:
            self.clear()
            return False
        page, x, y = hit
        if self.grab_annotation is not None:
            annot = self.grab_annotation(page, x, y)
            if annot is not None:  # D-052: mutarea adnotarii selectate
                self._moving = (annot, x, y)
                return True
        self._press = hit
        self._drag_point = None
        self._dragging = False
        index = self._char_at(page, x, y)
        if index is not None:  # C-044: selectia de text
            self.mode = "text"
            self.text_start = self.text_end = (page, index)
        else:
            self.mode = None
        self.area = None
        self.table = None
        self._place_widgets()
        self.view.viewport().update()
        return True

    def _move_to(self, point: QPointF) -> None:
        self._dragging = True
        hit = self.view.view_to_page(point)
        if self.mode == "text":
            if hit is not None:
                index = self._char_at(hit[0], hit[1], hit[2])
                if index is not None:
                    self.text_end = (hit[0], index)
        else:
            self._drag_point = point
        self.view.viewport().update()

    def _release_at(self, point: QPointF) -> None:
        press, self._press = self._press, None
        self._drag_point = None
        if press is None:
            return
        if self.mode == "text":
            if not self._dragging:  # un clic pe text, fara tragere: nimic selectat
                self.clear()
                self.view.page_clicked.emit(*press)
                return
            self.changed.emit()
            return
        hit = self.view.view_to_page(point)
        if not self._dragging or hit is None or hit[0] != press[0]:
            self.clear()  # C-040: zona care traverseaza pagini nu se creeaza
            if not self._dragging:
                self.view.page_clicked.emit(*press)
            return
        x0, x1 = sorted((press[1], hit[1]))
        y0, y1 = sorted((press[2], hit[2]))
        if x1 - x0 < MIN_AREA or y1 - y0 < MIN_AREA:
            self.clear()
            return
        self.set_area(press[0], Rect(x0, y0, x1 - x0, y1 - y0))

    # --- desenul (C-112, C-113) -------------------------------------------------------

    def paint(self, painter: QPainter, view: Any) -> None:
        if view is not self.view:
            return
        if self.mode == "text" and self.text_start and self.text_end:
            self._paint_text(painter)
        if self._press is not None and self.mode != "text" and self._drag_point is not None:
            start = self.view.page_to_view(self._press[0],
                                           Rect(self._press[1], self._press[2], 0, 0))
            if start is not None:
                painter.setPen(QPen(AREA_PEN, 1, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(start.topLeft(), self._drag_point).normalized())
        if self.area is not None and self.mode in ("area", "table"):
            box = self.view.page_to_view(*self.area)
            if box is not None:
                painter.setPen(QPen(AREA_PEN, 1, Qt.PenStyle.DashLine))  # C-112
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(box)
                if self.mode == "table" and self.table is not None:
                    self._paint_grid(painter, box)

    def _paint_text(self, painter: QPainter) -> None:
        assert self.text_start is not None and self.text_end is not None
        start, end = sorted((self.text_start, self.text_end))
        visible = set(self.view.visible_pages())
        for page in range(start[0], end[0] + 1):
            if page not in visible:
                continue
            text = self.view.document.page_text(page)
            first = start[1] if page == start[0] else 0
            last = end[1] + 1 if page == end[0] else len(text.text)
            for rect in text.span_rects(first, max(0, last - first)):
                box = self.view.page_to_view(page, rect)
                if box is not None:
                    painter.fillRect(box, TEXT_SELECTION)

    def _cell_box(self, box: QRectF, cell: Any) -> QRectF:
        assert self.table is not None
        sx = box.width() / max(1, self.table.image.width)
        sy = box.height() / max(1, self.table.image.height)
        return QRectF(box.left() + cell.bbox.x * sx, box.top() + cell.bbox.y * sy,
                      cell.bbox.w * sx, cell.bbox.h * sy)

    def _paint_grid(self, painter: QPainter, box: QRectF) -> None:
        assert self.table is not None
        for cell in self.selected_cells:
            painter.fillRect(self._cell_box(box, cell), CELL_SELECTED)
        painter.setPen(QPen(GRID_COLOR, 1.5))
        for cell in self.table.table.cells:
            painter.drawRect(self._cell_box(box, cell))

    # --- copierea (C-042…C-047, C-049) ------------------------------------------------

    def copy(self) -> bool:
        """`Copy` (Ctrl+C): textul selectat; o zona se copiaza ca imagine (C-042);
        in modul tabel, tabelul (C-047)."""
        if self.mode == "text":
            QApplication.clipboard().setText(self.selected_text())
            return True
        if self.mode == "area":
            return self.copy_area_image()
        if self.mode == "table":
            return self.copy_table()
        return False

    def copy_area_image(self) -> bool:
        if self.area is None:
            return False
        image = copying.area_image(self.view.document, *self.area)
        out = io.BytesIO()
        image.save(out, "PNG")
        QApplication.clipboard().setImage(QImage.fromData(out.getvalue(), "PNG"))
        return True

    def copy_area_text(self) -> bool:
        """C-043; C-049: textul nepotrivit cu imaginea primeste un avertisment."""
        if self.area is None:
            return False
        try:
            copied = copying.area_text(self.view.document, *self.area, context=self.context)
        except CoreError as exc:
            self.message.emit(tr_error(exc))
            return False
        QApplication.clipboard().setText(copied.text)
        if copied.warning:
            self.message.emit(tr(copied.warning))
        return True

    def start_table(self) -> bool:
        """C-045: modul tabel, cu grila detectata si toolbarul plutitor."""
        if self.area is None:
            return False
        try:
            self.table = copying.area_table(self.view.document, *self.area,
                                            context=self.context)
        except CoreError as exc:
            self.message.emit(tr_error(exc))
            return False
        self.mode = "table"
        self.selected_cells = []
        self._place_widgets()
        self.view.viewport().update()
        self.changed.emit()
        return True

    def copy_table(self) -> bool:
        """C-047: tabelul (editat) in clipboard, ca text cu tab-uri si ca HTML."""
        if self.table is None:
            return False
        mime = QMimeData()
        mime.setText(self.table.to_tsv())
        mime.setHtml(self.table.to_html())
        QApplication.clipboard().setMimeData(mime)
        return True

    # --- editarea tabelului (C-046) ---------------------------------------------------

    def set_table_tool(self, key: str) -> None:
        self.table_tool = key
        for other in ("add_horizontal", "add_vertical", "delete_separators", "select_cells"):
            self.table_actions[other].setChecked(other == key)

    def _to_image(self, x: float, y: float) -> tuple[float, float]:
        assert self.area is not None and self.table is not None
        rect = self.area[1]
        return ((x - rect.x) * self.table.image.width / rect.w,
                (y - rect.y) * self.table.image.height / rect.h)

    def _report(self, exc: Exception) -> None:
        self.message.emit(tr_error(exc) if isinstance(exc, CoreError) else str(exc))

    def _table_click(self, x: float, y: float) -> bool:
        assert self.table is not None
        ix, iy = self._to_image(x, y)
        try:
            if self.table_tool == "add_horizontal":
                self.table.add_separator("horizontal", int(iy))
            elif self.table_tool == "add_vertical":
                self.table.add_separator("vertical", int(ix))
            elif self.table_tool == "delete_separators":
                self._delete_separator_near(ix, iy)
            else:
                self._toggle_cell(ix, iy)
        except (ValueError, CoreError) as exc:
            self._report(exc)
        self.view.viewport().update()
        self.changed.emit()
        return True

    def _toggle_cell(self, ix: float, iy: float) -> None:
        assert self.table is not None
        cell = next((c for c in self.table.table.cells
                     if c.bbox.x <= ix <= c.bbox.x + c.bbox.w
                     and c.bbox.y <= iy <= c.bbox.y + c.bbox.h), None)
        if cell is None:
            return
        key = (cell.row, cell.col)
        if key in [(c.row, c.col) for c in self.selected_cells]:
            self.selected_cells = [c for c in self.selected_cells if (c.row, c.col) != key]
        else:
            self.selected_cells.append(cell)

    def _delete_separator_near(self, ix: float, iy: float) -> None:
        assert self.table is not None
        table = self.table.table
        tolerance = 12  # pixeli ai imaginii zonei (300 dpi)
        horizontal = min(table.h_separators, key=lambda s: abs(s - iy), default=None)
        vertical = min(table.v_separators, key=lambda s: abs(s - ix), default=None)
        if horizontal is not None and abs(horizontal - iy) <= tolerance:
            self.table.remove_separator("horizontal", horizontal)
        elif vertical is not None and abs(vertical - ix) <= tolerance:
            self.table.remove_separator("vertical", vertical)

    def _refresh_selection(self) -> None:
        self.selected_cells = []
        self.view.viewport().update()
        self.changed.emit()

    def merge_cells(self) -> None:
        if self.table is not None and len(self.selected_cells) >= 2:
            try:
                self.table.merge_cells(self.selected_cells)
            except (ValueError, CoreError) as exc:
                self._report(exc)
            self._refresh_selection()

    def split_cells(self) -> None:
        if self.table is not None and self.selected_cells:
            try:
                for cell in self.selected_cells:
                    self.table.split_cell(cell)
            except (ValueError, CoreError) as exc:
                self._report(exc)
            self._refresh_selection()

    def merge_rows(self) -> None:
        if self.table is not None and self.selected_cells:
            try:
                self.table.merge_rows(sorted({c.row for c in self.selected_cells}))
            except ValueError as exc:
                self._report(exc)
            self._refresh_selection()

    def analyze_table(self) -> None:
        if self.table is not None:
            self.table.reanalyze()
            self._refresh_selection()
