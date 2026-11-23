"""Panoul Image si panoul Zoom (faza 6b, pasul 6b.2).

Structura din SPEC_10: toolbarul pe doua randuri (J-410, J-411), unealta
activa evidentiata (J-412), banda pentru PDF cu strat de text (J-413), bara
de proprietati cu doua taburi (J-414, J-415) parcursa cu sageti cand e prea
ingusta (M-029), bara de jos cu potrivirile si zoom-ul (J-416), panoul Zoom
cu zoom propriu (J-418).

Zonele se deseneaza si se editeaza cu mouse-ul (M-009…M-011, M-015, M-104…
M-111); fiecare modificare trece prin `AreaEditor`, care tine regulile
(dimensiunea minima, suprapunerea, iesirea din imagine). Erorile nucleului
se arata ca mesaj tradus, construit din codul lor (Y-013).

`Edit Image` deschide Image Editor (6b.4); `Save Page`, `Recognize Page` si
`Analyze Page` le leaga fereastra (6b.6); tot ea leaga `copy` din uneltele
contextuale (M-108) de clipboard-ul de zone (`Edit > Paste`, X-202).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.core.layout.areas import AreaEditor
from app.core.model import AreaData, AreaType, PageData, PdfRecognitionMode, Rect
from app.gui import icons, theme, zones
from app.gui.i18n import tr, tr_error

IMAGE_ICONS = {
    "edit_image": "pencil", "save_page": "save", "select": "cursor", "hand": "hand",
    "delete": "trash", "reorder": "reorder", "recognize_page": "recognize",
    "analyze_page": "grid", "copy": "file_plus", "add_part": "plus", "cut_part": "trash", "zoom_pane": "search",
    "fit_width": "fit_width", "fit_height": "fit_height", "fit_page": "fit_page",
    "zoom_out": "zoom_out", "zoom_in": "zoom_in",
}
"""Iconitele proprii ale uneltelor din panoul Image."""
SKEW_BUTTON_ANGLE = 0.3
"""N-106: de la cate grade se arata butonul de indreptare."""

ZOOM_STEPS = (10, 25, 50, 75, 100, 150, 200, 300, 400)
"""J-416: procentele din combo-ul de zoom."""

AREA_TOOLS = (AreaType.TEXT, AreaType.PICTURE, AreaType.TABLE, AreaType.BACKGROUND_PICTURE,
              AreaType.RECOGNITION)
"""J-411: uneltele de zona, in ordinea din toolbar."""

FILL_ALPHA = 40
"""M-102: fundal translucid in culoarea tipului."""

HANDLE_SIZE = 7
"""M-104: latura manerelor, in pixeli de ecran."""


@cache
def _text_layer(path: str, page: int) -> bool:
    from app.core.ocr import textlayer

    text = textlayer.read_page(Path(path), page)
    return bool(text is not None and text.words)


# J-413
def has_text_layer(page: PageData | None) -> bool:
    """Banda apare numai pentru paginile venite dintr-un PDF cu strat de text."""
    if page is None or page.source_file is None:
        return False
    if page.source_file.suffix.lower() != ".pdf" or not page.source_file.is_file():
        return False
    return _text_layer(str(page.source_file), page.source_page or 1)


def _qrect(rect: Rect) -> QRectF:
    return QRectF(rect.x, rect.y, rect.w, rect.h)


def _polygon(area: AreaData) -> QPolygonF:
    points = area.polygon or zones.rect_points(area.bbox)
    return QPolygonF([QPointF(x, y) for x, y in points])


class ImageView(QGraphicsView):
    """Imaginea paginii cu zonele desenate peste ea (M-102…M-109)."""

    changed = Signal()
    """Zonele paginii s-au schimbat (dupa o operatie reusita in nucleu)."""
    message = Signal(str)
    """Mesaj tradus pentru bara de stare (erorile nucleului)."""
    selection_changed = Signal()
    hovered = Signal(QPointF)
    """Punctul din imagine de sub mouse; panoul Zoom il urmareste."""
    zoom_changed = Signal(int)
    clicked = Signal(QPointF)
    """Clic in imagine cu unealta de selectie (O-021: cuvantul se arata in text)."""

    def __init__(self, project: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("image_view")
        self.project = project
        self.page: PageData | None = None
        self.tool: str | AreaType = "select"
        self.selected: list[int] = []
        self.selected_cells: set[int] = set()
        """M-109: celulele de tabel alese in panoul de text, evidentiate pe imagine."""
        self.reorder_session: zones.ReorderSession | None = None
        self._drag: dict[str, Any] | None = None
        self._zoom = 100
        self.auto_fit = True
        """Pana cand utilizatorul alege un zoom, fiecare pagina se potriveste pe latime."""
        self.word_box: Rect | None = None
        """O-021: cuvantul ales in panoul Text, evidentiat in imagine."""
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor(theme.COLORS["canvas"]))  # fond gri, ca in prototip
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self._pixmap = QGraphicsPixmapItem()
        self.scene().addItem(self._pixmap)
        shadow = QGraphicsDropShadowEffect()  # pagina „pe masa”, cu umbra
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(10, 14, 20, 90))
        self._pixmap.setGraphicsEffect(shadow)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # --- pagina ---------------------------------------------------------------------

    @property
    def editor(self) -> AreaEditor:
        return AreaEditor(self.project)

    @property
    def areas(self) -> list[AreaData]:
        return sorted(self.page.areas, key=lambda a: a.order_index) if self.page else []

    def set_page(self, page: PageData | None) -> None:
        same = page is not None and self.page is not None and page.id == self.page.id
        changed_image = not same or page.image_path != self.page.image_path
        self.page = page
        if not same:
            self.selected = []
            self.selected_cells = set()
            self.reorder_session = None
            self.word_box = None
        else:
            ids = {a.id for a in page.areas}
            self.selected = [i for i in self.selected if i in ids]
        if changed_image:
            pixmap = QPixmap(str(page.image_path)) if page else QPixmap()
            self._pixmap.setPixmap(pixmap)
            self.scene().setSceneRect(QRectF(pixmap.rect()))
            if self.auto_fit and page is not None:  # pagina noua: pe latime, ca in prototip
                QTimer.singleShot(0, self._auto_fit_width)
        self.viewport().update()
        self.selection_changed.emit()

    # O-021
    def show_word(self, box: Rect) -> None:
        self.word_box = box
        self.ensureVisible(_qrect(box), 40, 40)
        self.viewport().update()

    def reload(self) -> None:
        if self.page is not None:
            self.set_page(self.project.page(self.page.page_number))
        self.changed.emit()

    def area(self, area_id: int) -> AreaData | None:
        return next((a for a in self.areas if a.id == area_id), None)

    def area_at(self, point: QPointF) -> AreaData | None:
        """Zona de sub punct; fundalul (M-110) se alege ultimul."""
        hits = [a for a in self.areas
                if _polygon(a).containsPoint(point, Qt.FillRule.OddEvenFill)]
        hits.sort(key=lambda a: a.area_type is AreaType.BACKGROUND_PICTURE)
        return hits[0] if hits else None

    # --- zoom (J-416) ------------------------------------------------------------------

    @property
    def zoom(self) -> int:
        return self._zoom

    def set_zoom(self, percent: int) -> None:
        """Zoom-ul ales de utilizator: de aici inainte nu se mai potriveste singur."""
        self.auto_fit = False
        self._apply_zoom(percent)

    def _apply_zoom(self, percent: int) -> None:
        self._zoom = max(ZOOM_STEPS[0], min(int(percent), 800))
        self.resetTransform()
        self.scale(self._zoom / 100, self._zoom / 100)
        self.zoom_changed.emit(self._zoom)

    def _auto_fit_width(self) -> None:
        if self.auto_fit and self.isVisible():
            self.fit("width")

    def step_zoom(self, direction: int) -> None:
        bigger = [z for z in ZOOM_STEPS if z > self._zoom]
        smaller = [z for z in ZOOM_STEPS if z < self._zoom]
        if direction > 0 and bigger:
            self.set_zoom(bigger[0])
        elif direction < 0 and smaller:
            self.set_zoom(smaller[-1])

    def fit(self, mode: str) -> None:
        """`width`, `height` sau `page`: zoom-ul la care imaginea incape in panou."""
        image = self.scene().sceneRect()
        if image.isEmpty():
            return
        view = self.viewport().size()
        margin = 0.95  # pagina cu fond gri in jur, ca in prototip
        ratios = {"width": view.width() * margin / image.width(),
                  "height": view.height() * margin / image.height()}
        ratios["page"] = min(ratios.values())
        self._apply_zoom(max(1, int(ratios[mode] * 100)))

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.step_zoom(1 if event.angleDelta().y() > 0 else -1)
        else:
            super().wheelEvent(event)

    # --- unelte -----------------------------------------------------------------------

    def set_tool(self, tool: str | AreaType) -> None:
        self.tool = tool
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if tool == "hand"
                         else QGraphicsView.DragMode.NoDrag)
        drawing = isinstance(tool, AreaType) or tool in ("add_part", "cut_part")
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if drawing  # M-105
                                  else Qt.CursorShape.ArrowCursor)

    # M-111
    def start_reorder(self) -> None:
        if self.page is not None and self.page.areas:
            self.reorder_session = zones.ReorderSession([a.id for a in self.areas])
            self.viewport().update()

    def stop_reorder(self) -> None:
        self.reorder_session = None
        self.viewport().update()

    def select(self, ids: list[int]) -> None:
        self.selected = list(ids)
        self.viewport().update()
        self.selection_changed.emit()

    # --- operatii prin nucleu ---------------------------------------------------------

    def _run(self, operation: Callable[[], Any]) -> Any:
        """Operatia in nucleu; eroarea devine mesaj tradus, pagina se reciteste."""
        try:
            result = operation()
        except CoreError as exc:
            self.message.emit(tr_error(exc))
            self.viewport().update()
            return None
        self.reload()
        return result

    def create_area(self, rect: Rect, kind: AreaType) -> AreaData | None:
        if self.page is None:
            return None
        area = self._run(lambda: self.editor.create(self.page, zones.rect_points(rect), kind))
        if area is not None:
            self.select([area.id])
        return area

    def delete_selected(self) -> None:
        chosen = [a for a in self.areas if a.id in self.selected]
        if self.page is not None and chosen:
            self._run(lambda: self.editor.delete(self.page, chosen))
            self.select([])

    def change_type(self, kind: AreaType) -> None:
        for area_id in list(self.selected):
            area = self.area(area_id)
            if area is not None and area.area_type is not kind:
                self._run(lambda a=area: self.editor.change_type(self.page, a, kind))

    # --- mouse ------------------------------------------------------------------------

    def _tolerance(self) -> float:
        return HANDLE_SIZE * 100 / self._zoom

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self.page is None:
            super().mousePressEvent(event)
            return
        point = self.mapToScene(event.position().toPoint())
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        if self.reorder_session is not None:  # M-111
            self._reorder_click(point)
            return
        if self.tool == "hand":
            super().mousePressEvent(event)
            return
        kind = zones.type_for_modifiers(ctrl, shift, alt)  # M-009
        if kind is None and (isinstance(self.tool, AreaType)
                             or self.tool in ("add_part", "cut_part")):
            kind = self.tool
        if kind is not None:
            self._drag = {"mode": "draw", "kind": kind, "start": point, "end": point}
            return
        self.clicked.emit(point)
        single = self.area(self.selected[0]) if len(self.selected) == 1 else None
        if single is not None and not single.is_polygon:
            handle = zones.hit_handle(single.bbox, point.x(), point.y(), self._tolerance())
            if handle is not None:  # M-011
                self._drag = {"mode": "resize", "area": single, "handle": handle,
                              "rect": single.bbox, "end": point}
                return
        hit = self.area_at(point)
        if hit is None:
            self.select([])
            return
        if ctrl:  # M-015
            ids = ([i for i in self.selected if i != hit.id] if hit.id in self.selected
                   else [*self.selected, hit.id])
            self.select(ids)
            return
        if hit.id not in self.selected:
            self.select([hit.id])
        self._drag = {"mode": "move", "start": point, "end": point}

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        point = self.mapToScene(event.position().toPoint())
        self.hovered.emit(point)
        if self._drag is None:
            super().mouseMoveEvent(event)
            return
        self._drag["end"] = point
        if self._drag["mode"] == "resize":
            self._drag["rect"] = zones.resize(self._drag["area"].bbox, self._drag["handle"],
                                              point.x(), point.y())
        self.viewport().update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        drag, self._drag = self._drag, None
        if drag is None or self.page is None:
            super().mouseReleaseEvent(event)
            return
        start, end = drag.get("start"), drag["end"]
        if drag["mode"] == "draw":
            rect = zones.clamp(zones.normalize(start.x(), start.y(), end.x(), end.y()),
                               self.page.width_px, self.page.height_px)
            self._finish_draw(drag["kind"], rect)
        elif drag["mode"] == "move":
            dx, dy = round(end.x() - start.x()), round(end.y() - start.y())
            if dx or dy:
                for area in [a for a in self.areas if a.id in self.selected]:
                    self._run(lambda a=area: self.editor.move(self.page, a, dx, dy))
        elif drag["mode"] == "resize" and drag["rect"] != drag["area"].bbox:
            self._run(lambda: self.editor.resize(self.page, drag["area"],
                                                 zones.rect_points(drag["rect"])))
        self.viewport().update()

    def _finish_draw(self, kind: str | AreaType, rect: Rect) -> None:
        if kind in ("add_part", "cut_part"):  # M-107, M-108
            target = self.area(self.selected[0]) if len(self.selected) == 1 else None
            if target is None:
                self.message.emit(tr("image.select_one_area"))
                return
            op = self.editor.add_part if kind == "add_part" else self.editor.cut_part
            self._run(lambda: op(self.page, target, rect))
            return
        self.create_area(rect, AreaType(kind))

    def _reorder_click(self, point: QPointF) -> None:
        hit = self.area_at(point)
        session = self.reorder_session
        if hit is None or session is None:
            return
        order = session.click(hit.id)
        self._run(lambda: self.editor.reorder(self.page, order))
        if session.done:
            self.stop_reorder()
            self.message.emit(tr("image.reorder_done"))

    # --- tastatura (M-010) -----------------------------------------------------------

    def focusNextPrevChild(self, next: bool) -> bool:
        return False  # `Tab` ramane in panou: parcurge zonele

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            areas = self.areas
            current = next((i for i, a in enumerate(areas)
                            if self.selected and a.id == self.selected[-1]), None)
            index = zones.next_index(len(areas), current, backwards=key == Qt.Key.Key_Backtab)
            if index is not None:
                self.select([areas[index].id])
            return
        if key == Qt.Key.Key_Delete:
            self.delete_selected()
            return
        if key == Qt.Key.Key_Escape:
            self._drag = None
            self.stop_reorder()
            return
        super().keyPressEvent(event)

    # --- desenarea zonelor -----------------------------------------------------------

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        if self.page is None:
            return
        settings = self.project.settings()
        scale = 100 / self._zoom
        moving = self._drag if self._drag and self._drag["mode"] == "move" else None
        for area in self.areas:
            color, width = zones.area_style(settings, area.area_type)
            selected = area.id in self.selected
            painter.save()
            if moving and selected:
                painter.translate(moving["end"] - moving["start"])
            self._paint_area(painter, area, QColor(color), width * scale, selected, scale)
            painter.restore()
        if self._drag and self._drag["mode"] in ("draw", "resize"):
            self._paint_rubber_band(painter, settings, scale)
        if self.word_box is not None:  # O-021
            mark = QColor(settings.get("areas.uncertain_color"))
            mark.setAlpha(90)
            painter.fillRect(_qrect(self.word_box), mark)

    def _paint_area(self, painter: QPainter, area: AreaData, color: QColor, width: float,
                    selected: bool, scale: float) -> None:
        fill = QColor(color)
        fill.setAlpha(FILL_ALPHA)
        path = QPainterPath()
        path.addPolygon(_polygon(area))
        path.closeSubpath()
        painter.fillPath(path, QBrush(fill))  # M-102
        painter.setPen(QPen(color, width * (2 if selected else 1)))  # M-104
        painter.drawPath(path)
        if area.table is not None:  # M-109: grila tabelului
            painter.setPen(QPen(color, max(scale, width / 2)))
            for cell in area.table.cells:
                if cell.id in self.selected_cells:  # M-109: celula aleasa, evidentiata
                    highlight = QColor(color)
                    highlight.setAlpha(90)
                    painter.fillRect(_qrect(cell.bbox), highlight)
                painter.drawRect(_qrect(cell.bbox))
        # M-103: numarul de ordine, intr-un patrat in colțul din stanga-sus
        side = 18 * scale
        box = QRectF(area.bbox.x, area.bbox.y, side, side)
        painter.fillRect(box, color)
        painter.setPen(QPen(QColor("white")))
        font = painter.font()
        font.setPointSizeF(max(1.0, 8 * scale))
        painter.setFont(font)
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, str(area.order_index + 1))
        if selected and len(self.selected) == 1 and not area.is_polygon:
            half = HANDLE_SIZE * scale / 2
            for hx, hy in zones.handles(area.bbox).values():
                painter.fillRect(QRectF(hx - half, hy - half, 2 * half, 2 * half), color)

    def _paint_rubber_band(self, painter: QPainter, settings: Any, scale: float) -> None:
        drag = self._drag
        if drag["mode"] == "resize":
            rect = drag["rect"]
            kind = drag["area"].area_type
        else:
            start, end = drag["start"], drag["end"]
            rect = zones.normalize(start.x(), start.y(), end.x(), end.y())
            kind = drag["kind"] if isinstance(drag["kind"], AreaType) else AreaType.TEXT
        color, width = zones.area_style(settings, kind)
        painter.setPen(QPen(QColor(color), width * scale, Qt.PenStyle.DashLine))  # M-105
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(_qrect(rect))


class ScrollStrip(QWidget):
    """M-029: cand panoul e prea ingust, continutul se parcurge cu sageti."""

    STEP = 60

    def __init__(self, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.area = QScrollArea()
        self.area.setWidget(content)
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(content.sizeHint().height())
        self.left = QToolButton()
        self.left.setArrowType(Qt.ArrowType.LeftArrow)
        self.left.setObjectName("scroll_left")
        self.right = QToolButton()
        self.right.setArrowType(Qt.ArrowType.RightArrow)
        self.right.setObjectName("scroll_right")
        bar = self.area.horizontalScrollBar()
        self.left.clicked.connect(lambda: bar.setValue(bar.value() - self.STEP))
        self.right.clicked.connect(lambda: bar.setValue(bar.value() + self.STEP))
        bar.rangeChanged.connect(self._update)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.left)
        layout.addWidget(self.area, 1)
        layout.addWidget(self.right)
        self._update()

    @property
    def narrow(self) -> bool:
        return self.area.horizontalScrollBar().maximum() > 0

    def _update(self, *_: int) -> None:
        self.left.setVisible(self.narrow)
        self.right.setVisible(self.narrow)


class ImagePanel(QWidget):
    """Panoul Image: toolbarul, banda PDF, imaginea, proprietatile, bara de jos."""

    changed = Signal()
    """Pagina s-a schimbat in panou (indreptarea, N-106): fereastra se reimprospateaza."""

    def __init__(self, project: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("image_panel")
        self.project = project
        self.view = ImageView(project)
        self._skews: dict[tuple[int | None, str], float] = {}
        self.actions: dict[str, QAction] = {}
        self.tools = QActionGroup(self)
        self.tools.setExclusive(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._row1())
        row2 = QHBoxLayout()
        row2.addWidget(self._row2(), 1)
        row2.addWidget(self._pdf_band())
        layout.addLayout(row2)
        layout.addWidget(self.view, 1)
        layout.addWidget(self._properties())
        layout.addWidget(self._bottom_bar())
        self.view.selection_changed.connect(self._update_properties)
        self.view.zoom_changed.connect(self._show_zoom)
        self.view.changed.connect(self._update_properties)
        self._choose_tool("select")

    # --- toolbarul (J-410, J-411, J-412) ---------------------------------------------

    def _action(self, bar: QToolBar, key: str, *, checkable: bool = False) -> QAction:
        action = bar.addAction(tr(f"image.{key}"))
        action.setObjectName(f"image_{key}")
        if key.startswith("tool."):  # patratelul culorii tipului (M-100, prototipul)
            kind = AreaType(key.removeprefix("tool."))
            action.setIcon(icons.swatch(zones.area_style(self.project.settings(), kind)[0]))
        elif key in IMAGE_ICONS:
            action.setIcon(icons.icon(IMAGE_ICONS[key]))
        action.setCheckable(checkable)
        self.actions[key] = action
        return action

    def _tool(self, bar: QToolBar, key: str, tool: str | AreaType) -> None:
        action = self._action(bar, key, checkable=True)
        self.tools.addAction(action)
        action.triggered.connect(lambda _=False: self._choose_tool(tool))

    @staticmethod
    def _bar(name: str) -> QToolBar:
        bar = QToolBar()
        bar.setObjectName(name)
        bar.setIconSize(QSize(16, 16))
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        return bar

    def _row1(self) -> QToolBar:
        bar = self._bar("image_toolbar_1")
        bar.setObjectName("image_toolbar_1")
        self._action(bar, "edit_image")  # L-001: fereastra il leaga de Image Editor
        self._action(bar, "save_page")  # Q-030: fereastra o leaga de salvarea imaginilor
        bar.addSeparator()
        self._tool(bar, "select", "select")
        self._tool(bar, "hand", "hand")
        self._action(bar, "delete").triggered.connect(self.view.delete_selected)
        self._action(bar, "reorder", checkable=True).toggled.connect(self._toggle_reorder)
        return bar

    def _row2(self) -> QToolBar:
        bar = self._bar("image_toolbar_2")
        bar.setObjectName("image_toolbar_2")
        self._action(bar, "recognize_page")  # fereastra o leaga de recunoastere (6b.6a)
        self._action(bar, "analyze_page")  # fereastra o leaga de analiza (6b.6a)
        bar.addSeparator()
        for kind in AREA_TOOLS:
            self._tool(bar, f"tool.{kind.value}", kind)
        bar.addSeparator()
        self._action(bar, "train_patterns")  # P-055: fereastra deschide `Pattern Training`
        self._action(bar, "copy")  # M-108: fereastra copiaza zonele selectate
        deskew = self._action(bar, "correct_skew")  # N-106: numai pe paginile inclinate
        deskew.triggered.connect(self.correct_skew)
        for key in ("add_part", "cut_part"):  # M-108
            self._tool(bar, key, key)
        return bar

    @staticmethod
    def tool_key(tool: str | AreaType) -> str:
        return f"tool.{tool.value}" if isinstance(tool, AreaType) else tool

    def _choose_tool(self, tool: str | AreaType) -> None:
        self.actions[self.tool_key(tool)].setChecked(True)  # J-412
        self.view.set_tool(tool)

    def _toggle_reorder(self, on: bool) -> None:
        if on:
            self.view.start_reorder()
            if self.view.reorder_session is None:
                self.actions["reorder"].setChecked(False)
        else:
            self.view.stop_reorder()

    # --- banda PDF (J-413) ---------------------------------------------------------------

    def _pdf_band(self) -> QWidget:
        self.pdf_band = QWidget()
        self.pdf_band.setObjectName("pdf_band")
        layout = QHBoxLayout(self.pdf_band)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(QLabel(tr("image.pdf_text_layer")))
        button = QToolButton()
        button.setObjectName("pdf_mode")
        button.setText(tr("image.pdf_mode"))
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        self.pdf_mode_actions: dict[str, QAction] = {}
        group = QActionGroup(menu)
        for mode in PdfRecognitionMode:
            action = menu.addAction(tr(f"image.pdf_mode.{mode.value}"))
            action.setCheckable(True)
            group.addAction(action)
            action.triggered.connect(lambda _=False, m=mode: self._set_pdf_mode(m))
            self.pdf_mode_actions[mode.value] = action
        button.setMenu(menu)
        layout.addWidget(button)
        self.pdf_band.setVisible(False)
        return self.pdf_band

    def _set_pdf_mode(self, mode: PdfRecognitionMode) -> None:
        self.project.settings().set("ocr.pdf_mode", mode.value)  # X-060

    # --- proprietatile (J-414, J-415, M-029) -------------------------------------------

    def _properties(self) -> QTabWidget:
        self.properties = QTabWidget()
        self.properties.setObjectName("properties")
        self.properties.setMaximumHeight(92)  # bara compacta de sub imagine (J-414)
        area = QWidget()
        row = QHBoxLayout(area)
        row.setContentsMargins(4, 2, 4, 2)
        row.addWidget(QLabel(tr("image.area_type")))
        self.type_combo = QComboBox()
        self.type_combo.setObjectName("area_type")
        for kind in AreaType:
            self.type_combo.addItem(tr(f"image.tool.{kind.value}"), kind.value)
        self.type_combo.activated.connect(
            lambda i: self.view.change_type(AreaType(self.type_combo.itemData(i))))
        row.addWidget(self.type_combo)
        self.area_order = QLabel()
        self.area_order.setObjectName("area_order")
        row.addWidget(self.area_order)
        row.addStretch(1)
        self.area_strip = ScrollStrip(area)
        self.properties.addTab(self.area_strip, tr("image.area_properties"))
        image = QWidget()
        grid = QFormLayout(image)
        grid.setContentsMargins(4, 2, 4, 2)
        self.image_info: dict[str, QLabel] = {}
        for key in ("size", "resolution", "color_mode", "format", "source"):
            label = QLabel()
            label.setObjectName(f"image_info_{key}")
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.image_info[key] = label
            grid.addRow(tr(f"image.info.{key}"), label)
        self.properties.addTab(ScrollStrip(image), tr("image.image_properties"))
        return self.properties

    def _update_properties(self) -> None:
        view = self.view
        page = view.page
        single = view.area(view.selected[0]) if len(view.selected) == 1 else None
        self.type_combo.setEnabled(bool(view.selected))
        if single is not None:
            self.type_combo.setCurrentIndex(self.type_combo.findData(single.area_type.value))
            self.area_order.setText(tr("image.area_number", n=single.order_index + 1))
        else:
            self.area_order.setText("")
        if page is None:
            for label in self.image_info.values():
                label.setText("")
            return
        source = page.source_file or page.original_path
        self.image_info["size"].setText(tr("image.info.size_value", w=page.width_px,
                                           h=page.height_px))
        self.image_info["resolution"].setText(tr("image.info.dpi_value", dpi=page.dpi_x))
        self.image_info["color_mode"].setText(tr(f"color_mode.{page.color_mode.value}"))
        self.image_info["format"].setText(Path(source).suffix.lstrip(".").upper())
        self.image_info["source"].setText(str(source))

    # --- bara de jos (J-416) ----------------------------------------------------------

    def _bottom_bar(self) -> QToolBar:
        bar = self._bar("image_bottom_bar")
        bar.setObjectName("image_bottom_bar")
        self.zoom_pane_toggle = self._action(bar, "zoom_pane", checkable=True)
        self.zoom_pane_toggle.setChecked(False)  # ca in prototip: Zoom se deschide la cerere
        bar.addSeparator()
        for mode in ("width", "height", "page"):
            self._action(bar, f"fit_{mode}").triggered.connect(
                lambda _=False, m=mode: self.view.fit(m))
        self.zoom_combo = QComboBox()
        self.zoom_combo.setObjectName("image_zoom")
        self.zoom_combo.setEditable(True)
        for step in ZOOM_STEPS:
            self.zoom_combo.addItem(f"{step}%", step)
        self.zoom_combo.activated.connect(
            lambda i: self.view.set_zoom(self.zoom_combo.itemData(i)))
        self.zoom_combo.lineEdit().editingFinished.connect(self._typed_zoom)
        bar.addWidget(self.zoom_combo)
        self._action(bar, "zoom_out").triggered.connect(lambda: self.view.step_zoom(-1))
        self._action(bar, "zoom_in").triggered.connect(lambda: self.view.step_zoom(1))
        self._show_zoom(self.view.zoom)
        return bar

    def _typed_zoom(self) -> None:
        digits = "".join(c for c in self.zoom_combo.currentText() if c.isdigit())
        if digits:
            self.view.set_zoom(int(digits))

    def _show_zoom(self, percent: int) -> None:
        self.zoom_combo.setEditText(f"{percent}%")

    # --- pagina ------------------------------------------------------------------------

    def page_skew(self, page: PageData | None) -> float:
        """N-106: unghiul de inclinare al paginii (o data pe imagine)."""
        if page is None:
            return 0.0
        key = (page.id, str(page.image_path))
        if key not in self._skews:
            from app.core.layout.analyzer import LayoutAnalyzer

            try:
                self._skews[key] = float(LayoutAnalyzer().estimate_skew(page))
            except (OSError, ValueError):
                self._skews[key] = 0.0
        return self._skews[key]

    def correct_skew(self) -> None:
        """N-106: indreptarea paginii curente (L-011); zonele si textul se refac."""
        from app.core.model import PreprocessOp

        page = self.view.page
        if page is None:
            return
        try:
            self.project.preprocess_pages([page.page_number], [(PreprocessOp.DESKEW, {})])
        except CoreError as exc:
            self.view.message.emit(tr_error(exc))
            return
        self.changed.emit()

    def set_page(self, page: PageData | None) -> None:
        self.view.set_page(page)
        self.actions["correct_skew"].setVisible(  # N-106
            abs(self.page_skew(page)) >= SKEW_BUTTON_ANGLE)
        visible = has_text_layer(page)
        self.pdf_band.setVisible(visible)
        if visible:
            self.pdf_mode_actions[self.project.settings().get("ocr.pdf_mode")].setChecked(True)
        self.actions["reorder"].setChecked(self.view.reorder_session is not None)
        self._update_properties()


class ZoomPanel(QWidget):
    """J-418: aceeasi imagine, cu zoom propriu, centrata pe punctul de sub mouse."""

    def __init__(self, view: ImageView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("zoom_panel")
        self.zoom_view = QGraphicsView(view.scene())
        self.zoom_view.setObjectName("zoom_view")
        self.zoom_view.setInteractive(False)
        self.zoom_combo = QComboBox()
        self.zoom_combo.setObjectName("zoom_pane_zoom")
        for step in ZOOM_STEPS:
            self.zoom_combo.addItem(f"{step}%", step)
        self.zoom_combo.currentIndexChanged.connect(
            lambda i: self.set_zoom(self.zoom_combo.itemData(i)))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.zoom_view, 1)
        layout.addWidget(self.zoom_combo)
        self.zoom = 0
        self.zoom_combo.setCurrentIndex(ZOOM_STEPS.index(200))
        view.hovered.connect(self.follow)

    def set_zoom(self, percent: int) -> None:
        self.zoom = int(percent)
        self.zoom_view.resetTransform()
        self.zoom_view.scale(self.zoom / 100, self.zoom / 100)

    def follow(self, point: QPointF) -> None:
        self.zoom_view.centerOn(point)
