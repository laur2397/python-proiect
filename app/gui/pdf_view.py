"""Zona de pagina a PDF Editor-ului (faza 7, pasul 7.7a): B-001…B-018,
B-300…B-302, B-311.

Randarea e lenesa (B-001): se cer numai paginile vizibile, plus una inainte si
una dupa; imaginile stau intr-un cache mic. O pagina stricata apare ca un
chenar gri cu mesaj, iar restul documentului ramane folosibil.

Cele patru moduri de vizualizare (B-002…B-005), paginile impare in dreapta
(B-006), zoom-ul cu limite (B-010), potrivirile (B-011…B-013), navigarea
(B-014…B-017) si istoricul de 50 de pozitii (B-018). Uneltele `Select` si
`Hand`, cu tasta spatiu pentru `Hand` temporar (B-300…B-302).

Coordonatele nucleului (puncte, sus-stanga MediaBox, pagina nerotita) se
transforma in pixelii vizualizarii cu `page_to_view` si inapoi cu
`view_to_page`, tinand cont de rotatia paginii.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import QAbstractScrollArea, QWidget

from app.core.errors import CoreError
from app.core.model import Rect
from app.gui.i18n import tr


class ViewMode(str, Enum):
    ONE_PAGE = "one_page"                   # B-002
    ONE_PAGE_SCROLLING = "one_page_scroll"  # B-003
    TWO_PAGE = "two_page"                   # B-004
    TWO_PAGE_SCROLLING = "two_page_scroll"  # B-005

    @property
    def two_pages(self) -> bool:
        return self in (ViewMode.TWO_PAGE, ViewMode.TWO_PAGE_SCROLLING)

    @property
    def scrolling(self) -> bool:
        return self in (ViewMode.ONE_PAGE_SCROLLING, ViewMode.TWO_PAGE_SCROLLING)


class FitMode(str, Enum):
    NONE = "none"
    BEST_FIT = "best_fit"        # B-011
    ACTUAL_SIZE = "actual_size"  # B-012
    FIT_WIDTH = "fit_width"      # B-013


class Tool(str, Enum):
    SELECT = "select"  # B-300
    HAND = "hand"      # B-301


ZOOM_STEPS = (10, 25, 33, 50, 66, 75, 100, 125, 150, 200, 300, 400, 600, 800, 1600, 3200,
              6400)
"""B-010: treptele de zoom (procente); la capete butonul se dezactiveaza."""
ZOOM_MIN, ZOOM_MAX = ZOOM_STEPS[0], ZOOM_STEPS[-1]
HISTORY_LIMIT = 50
"""B-018: istoricul de navigare."""
CACHE_LIMIT = 16
"""Cate imagini de pagina raman in memorie."""
SCREEN_DPI = 96
"""Zoom 100% = 96 de pixeli pe inch (ca `PdfDocument.render_page`)."""
MARGIN = 16
GAP = 12
CANVAS = "#dfe3e8"
"""B-311: fundalul zonei de pagina, gri deschis."""


# --- rotatia --------------------------------------------------------------------------


def to_display(rotation: int, width: float, height: float, x: float, y: float
               ) -> tuple[float, float]:
    """Un punct din pagina nerotita (latime, inaltime nerotite; sus-stanga) in
    pagina afisata, rotita in sensul acelor de ceasornic cu `rotation` grade."""
    rotation %= 360
    if rotation == 90:
        return height - y, x
    if rotation == 180:
        return width - x, height - y
    if rotation == 270:
        return y, width - x
    return x, y


def from_display(rotation: int, width: float, height: float, x: float, y: float
                 ) -> tuple[float, float]:
    """Inversul lui `to_display`."""
    rotation %= 360
    if rotation == 90:
        return y, height - x
    if rotation == 180:
        return width - x, height - y
    if rotation == 270:
        return width - y, x
    return x, y


@dataclass(frozen=True, slots=True)
class Slot:
    """O pagina asezata in vizualizare: pixelii ei pe panza."""

    page: int
    rect: QRectF


class PdfView(QAbstractScrollArea):
    page_changed = Signal(int)
    """Pagina curenta (1..N)."""
    zoom_changed = Signal(int)
    """Zoom-ul in procente."""
    mode_changed = Signal(str)
    history_changed = Signal()
    tool_changed = Signal(str)
    page_clicked = Signal(int, float, float)
    """Clic cu `Select` pe o pagina: pagina si punctul in coordonatele nucleului."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pdf_view")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setMouseTracking(True)
        self.canvas = self.viewport()
        """Suprafata pe care se deseneaza (fereastra vizibila). Paginile sunt
        asezate intr-un spatiu virtual oricat de lung; se picteaza numai ce se
        vede, deplasat cu derularea (Qt nu picteaza widgeturi mai inalte de
        ~32000 de pixeli, cat au cateva zeci de pagini A4)."""
        self._content = QSize(0, 0)
        self._prefetch_pending = False
        self.document: Any = None
        self.mode = ViewMode.ONE_PAGE_SCROLLING
        self.fit = FitMode.FIT_WIDTH
        self.odd_on_right = False
        self.zoom = 100
        self.tool = Tool.SELECT
        self._space_hand = False
        self._drag_from: QPoint | None = None
        self._current = 1
        self._sizes: list[tuple[float, float]] = []
        self._rotations: list[int] = []
        self._slots: list[Slot] = []
        self._cache: OrderedDict[tuple[int, int], QPixmap | None] = OrderedDict()
        self.render_count = 0
        """Cate pagini s-au randat (pentru teste: randarea e lenesa)."""
        self._history: list[tuple[int, int]] = []
        self._history_index = -1
        self.overlays: list[Callable[[QPainter, PdfView], None]] = []
        """Desenele de deasupra paginilor (rezultatele cautarii, selectia, 7.8)."""
        self.verticalScrollBar().valueChanged.connect(self._scrolled)

    # --- documentul -------------------------------------------------------------------

    def _read_geometry(self) -> None:
        doc = self.document
        count = doc.page_count if doc is not None else 0
        self._sizes = [doc.page_size(n) for n in range(1, count + 1)]
        self._rotations = [doc.page_rotation(n) for n in range(1, count + 1)]

    def set_document(self, document: Any) -> None:
        self.document = document
        self._cache.clear()
        self._current = 1
        self._history, self._history_index = [], -1
        self._read_geometry()
        self._relayout()
        self._record()
        self.page_changed.emit(self._current)

    def reload(self) -> None:
        """Documentul s-a schimbat (o adnotare, o redactare): imaginile se refac."""
        if self.document is None:
            return
        self._cache.clear()
        self._read_geometry()
        self._current = max(1, min(self._current, self.page_count))
        self._relayout()

    @property
    def page_count(self) -> int:
        return len(self._sizes)

    @property
    def current_page(self) -> int:
        return self._current

    # --- asezarea ---------------------------------------------------------------------

    @property
    def scale(self) -> float:
        """Pixeli pe punct."""
        return self.zoom / 100 * SCREEN_DPI / 72

    def spreads(self) -> list[tuple[int | None, int | None]]:
        """Perechile (stanga, dreapta) de pe ecran; cu o pagina: (n, None).
        B-004: impare in stanga; B-006: impare in dreapta (prima pagina singura
        in dreapta)."""
        pages = list(range(1, self.page_count + 1))
        if not self.mode.two_pages:
            return [(n, None) for n in pages]
        out: list[tuple[int | None, int | None]] = []
        rest = pages
        if self.odd_on_right and pages:
            out.append((None, 1))
            rest = pages[1:]
        for i in range(0, len(rest), 2):
            pair = rest[i:i + 2]
            out.append((pair[0], pair[1] if len(pair) > 1 else None))
        return out

    def _spread_of(self, page: int) -> int:
        for i, spread in enumerate(self.spreads()):
            if page in spread:
                return i
        return 0

    def _spread_size(self, spread: tuple[int | None, int | None]) -> tuple[float, float]:
        pages = [p for p in spread if p]
        height = max((self._sizes[p - 1][1] for p in pages), default=0) * self.scale
        if self.mode.two_pages:
            single = max((self._sizes[p - 1][0] for p in pages), default=0) * self.scale
            return 2 * single + GAP, height
        return sum(self._sizes[p - 1][0] for p in pages) * self.scale, height

    def _relayout(self) -> None:
        if not self._sizes:
            self._slots = []
            self._set_content(self.viewport().width(), self.viewport().height())
            return
        self._apply_fit()
        all_spreads = self.spreads()
        shown = all_spreads if self.mode.scrolling else \
            [all_spreads[self._spread_of(self._current)]]
        width = max(max(self._spread_size(s)[0] for s in shown) + 2 * MARGIN,
                    self.viewport().width())
        slots: list[Slot] = []
        y = float(MARGIN)
        for spread in shown:
            spread_w, spread_h = self._spread_size(spread)
            x = (width - spread_w) / 2
            half = (spread_w - GAP) / 2
            for i, page in enumerate(spread):
                if not page:
                    continue
                w, h = (v * self.scale for v in self._sizes[page - 1])
                left = x + i * (half + GAP) + (half - w) / 2 if self.mode.two_pages else x
                slots.append(Slot(page, QRectF(left, y + (spread_h - h) / 2, w, h)))
            y += spread_h + GAP
        height = max(y - GAP + MARGIN, self.viewport().height())
        self._slots = slots
        self._set_content(int(width), int(height))

    def _set_content(self, width: int, height: int) -> None:
        self._content = QSize(width, height)
        viewport = self.viewport().size()
        for bar, total, visible in ((self.horizontalScrollBar(), width, viewport.width()),
                                    (self.verticalScrollBar(), height, viewport.height())):
            bar.setPageStep(visible)
            bar.setSingleStep(max(20, visible // 20))
            bar.setRange(0, max(0, total - visible))
        self.viewport().update()

    def content_size(self) -> QSize:
        """Marimea spatiului virtual in care sunt asezate paginile."""
        return QSize(self._content)

    def _offset(self) -> QPointF:
        return QPointF(self.horizontalScrollBar().value(), self.verticalScrollBar().value())

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # API Qt
        self.viewport().update()

    def paintEvent(self, event: Any) -> None:  # API Qt: pictarea ferestrei vizibile
        painter = QPainter(self.viewport())
        painter.fillRect(event.rect(), QColor(CANVAS))
        offset = self._offset()
        painter.translate(-offset)
        self._paint(painter, QRectF(event.rect()).translated(offset))
        painter.end()
        if not self._prefetch_pending and self.document is not None:
            self._prefetch_pending = True
            QTimer.singleShot(0, self.prefetch)

    def prefetch(self) -> None:
        """B-001: paginile vecine celor vizibile se randeaza dinainte, ca derularea
        sa le gaseasca gata."""
        self._prefetch_pending = False
        if self.document is not None:
            for page in self.visible_pages():
                self._pixmap(page)

    def slots(self) -> list[Slot]:
        return list(self._slots)

    def slot(self, page: int) -> Slot | None:
        return next((s for s in self._slots if s.page == page), None)

    # --- potrivirea si zoom-ul (B-010…B-013) ------------------------------------------

    def _apply_fit(self) -> None:
        if self.fit is FitMode.NONE or not self._sizes:
            return
        if self.fit is FitMode.ACTUAL_SIZE:  # marimea fizica, dupa rezolutia ecranului
            self._set_zoom_value(round(100 * self.logicalDpiX() / SCREEN_DPI))
            return
        spread = self.spreads()[self._spread_of(self._current)]
        pages = [p for p in spread if p]
        w_pt = max(self._sizes[p - 1][0] for p in pages) * (2 if self.mode.two_pages else 1)
        h_pt = max(self._sizes[p - 1][1] for p in pages)
        unit = SCREEN_DPI / 72 / 100
        avail_w = max(50, self.viewport().width() - 2 * MARGIN -
                      (GAP if self.mode.two_pages else 0))
        avail_h = max(50, self.viewport().height() - 2 * MARGIN)
        zoom = avail_w / (w_pt * unit)
        if self.fit is FitMode.BEST_FIT:  # pagina intreaga, inaltimea inclusiv
            zoom = min(zoom, avail_h / (h_pt * unit))
        self._set_zoom_value(int(max(ZOOM_MIN, min(ZOOM_MAX, zoom))))

    def _set_zoom_value(self, zoom: int) -> None:
        if zoom != self.zoom:
            self.zoom = zoom
            self.zoom_changed.emit(zoom)

    def set_zoom(self, percent: int) -> None:
        """Zoom ales de utilizator: potrivirea automata se opreste."""
        self.fit = FitMode.NONE
        anchor = self._current
        self._set_zoom_value(int(max(ZOOM_MIN, min(ZOOM_MAX, percent))))
        self._relayout()
        self._scroll_to(anchor)

    def set_fit(self, fit: FitMode) -> None:
        self.fit = FitMode(fit)
        anchor = self._current
        self._relayout()
        self._scroll_to(anchor)

    def can_zoom_in(self) -> bool:
        return self.zoom < ZOOM_MAX

    def can_zoom_out(self) -> bool:
        return self.zoom > ZOOM_MIN

    def zoom_in(self) -> None:
        self.set_zoom(next((z for z in ZOOM_STEPS if z > self.zoom), ZOOM_MAX))

    def zoom_out(self) -> None:
        self.set_zoom(next((z for z in reversed(ZOOM_STEPS) if z < self.zoom), ZOOM_MIN))

    # --- modurile (B-002…B-006) -------------------------------------------------------

    def set_mode(self, mode: ViewMode) -> None:
        self.mode = ViewMode(mode)
        anchor = self._current
        self._relayout()
        self._scroll_to(anchor)
        self.mode_changed.emit(self.mode.value)

    def set_odd_on_right(self, on: bool) -> None:
        """B-006: are efect numai in modurile cu doua pagini."""
        self.odd_on_right = bool(on)
        anchor = self._current
        self._relayout()
        self._scroll_to(anchor)

    # --- navigarea (B-014…B-018) ------------------------------------------------------

    def go_to_page(self, page: int, *, record: bool = True) -> bool:
        """Sare la pagina data; in afara intervalului nu face nimic (B-014)."""
        if not 1 <= page <= self.page_count:
            return False
        self._current = page
        if not self.mode.scrolling:
            self._relayout()
        self._scroll_to(page)
        if record:
            self._record()
        self.page_changed.emit(page)
        return True

    def can_go_next(self) -> bool:
        return self._spread_of(self._current) < len(self.spreads()) - 1

    def can_go_previous(self) -> bool:
        return self._spread_of(self._current) > 0

    def next_page(self) -> None:
        spreads = self.spreads()
        index = self._spread_of(self._current)
        if index + 1 < len(spreads):
            self.go_to_page(next(p for p in spreads[index + 1] if p))

    def previous_page(self) -> None:
        spreads = self.spreads()
        index = self._spread_of(self._current)
        if index > 0:
            self.go_to_page(next(p for p in spreads[index - 1] if p))

    def first_page(self) -> None:
        self.go_to_page(1)

    def last_page(self) -> None:
        self.go_to_page(self.page_count)

    def _record(self) -> None:
        if not self.page_count:
            return
        entry = (self._current, self.zoom)
        if 0 <= self._history_index < len(self._history) and \
                self._history[self._history_index] == entry:
            return
        del self._history[self._history_index + 1:]
        self._history.append(entry)
        if len(self._history) > HISTORY_LIMIT:
            del self._history[0]
        self._history_index = len(self._history) - 1
        self.history_changed.emit()

    def can_go_back(self) -> bool:
        return self._history_index > 0

    def can_go_forward(self) -> bool:
        return self._history_index < len(self._history) - 1

    def _restore(self, index: int) -> None:
        self._history_index = index
        page, zoom = self._history[index]
        if zoom != self.zoom:
            self.fit = FitMode.NONE
            self._set_zoom_value(zoom)
            self._relayout()
        self.go_to_page(page, record=False)
        self.history_changed.emit()

    def back(self) -> None:
        """B-018: pozitia anterioara, cu zoom-ul ei."""
        if self.can_go_back():
            self._restore(self._history_index - 1)

    def forward(self) -> None:
        if self.can_go_forward():
            self._restore(self._history_index + 1)

    def history(self) -> list[tuple[int, int]]:
        return list(self._history)

    def _scroll_to(self, page: int) -> None:
        slot = self.slot(page)
        if slot is not None:
            self.verticalScrollBar().setValue(int(max(0, slot.rect.top() - MARGIN)))

    def _scrolled(self, _value: int) -> None:
        if not self.mode.scrolling or not self._slots:
            return
        top = self.verticalScrollBar().value() + self.viewport().height() * 0.3
        page = next((s.page for s in self._slots if s.rect.bottom() >= top),
                    self._slots[-1].page)
        if page != self._current:
            self._current = page
            self.page_changed.emit(page)

    # --- randarea (B-001) -------------------------------------------------------------

    def visible_pages(self) -> list[int]:
        """Paginile vizibile acum, plus una inainte si una dupa (B-001)."""
        top = self.verticalScrollBar().value()
        bottom = top + self.viewport().height()
        seen = [s.page for s in self._slots if s.rect.bottom() >= top and s.rect.top() <= bottom]
        if not seen:
            return []
        wanted = set(seen) | {min(seen) - 1, max(seen) + 1}
        return sorted(p for p in wanted if 1 <= p <= self.page_count)

    def _pixmap(self, page: int) -> QPixmap | None:
        key = (page, self.zoom)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        try:
            image = QImage.fromData(self.document.render_page(page, self.zoom / 100), "PNG")
            pixmap: QPixmap | None = None if image.isNull() else QPixmap.fromImage(image)
        except (CoreError, ValueError):
            pixmap = None  # B-001: pagina stricata
        self.render_count += 1
        self._cache[key] = pixmap
        while len(self._cache) > CACHE_LIMIT:
            self._cache.popitem(last=False)
        return pixmap

    def _paint(self, painter: QPainter, area: QRectF) -> None:
        if self.document is None:
            return
        wanted = set(self.visible_pages())
        for slot in self._slots:
            if not slot.rect.intersects(area) or slot.page not in wanted:
                continue
            painter.fillRect(slot.rect.translated(3, 3), QColor(0, 0, 0, 40))
            pixmap = self._pixmap(slot.page)
            if pixmap is None:
                painter.fillRect(slot.rect, QColor("#c7ccd4"))
                painter.setPen(QColor("#4b5563"))
                painter.drawText(slot.rect, Qt.AlignmentFlag.AlignCenter |
                                 Qt.TextFlag.TextWordWrap, tr("pdf.page_corrupt"))
            else:
                painter.fillRect(slot.rect, QColor("#ffffff"))
                painter.drawPixmap(slot.rect, pixmap, QRectF(pixmap.rect()))
        for overlay in self.overlays:
            overlay(painter, self)

    # --- coordonatele -----------------------------------------------------------------

    def _page_geometry(self, page: int) -> tuple[int, float, float]:
        """Rotatia si latimea, inaltimea nerotite (puncte)."""
        w, h = self._sizes[page - 1]
        rotation = self._rotations[page - 1] % 360
        if rotation in (90, 270):
            w, h = h, w
        return rotation, w, h

    def page_to_view(self, page: int, rect: Rect) -> QRectF | None:
        """Un dreptunghi din coordonatele nucleului, in pixelii panzei."""
        slot = self.slot(page)
        if slot is None:
            return None
        rotation, w, h = self._page_geometry(page)
        corners = [to_display(rotation, w, h, x, y) for x, y in (
            (rect.x, rect.y), (rect.x + rect.w, rect.y + rect.h))]
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        return QRectF(slot.rect.left() + min(xs) * self.scale,
                      slot.rect.top() + min(ys) * self.scale,
                      (max(xs) - min(xs)) * self.scale, (max(ys) - min(ys)) * self.scale)

    def view_to_page(self, point: QPointF) -> tuple[int, float, float] | None:
        """Un punct de pe panza → (pagina, x, y) in coordonatele nucleului."""
        for slot in self._slots:
            if slot.rect.contains(point):
                rotation, w, h = self._page_geometry(slot.page)
                dx = (point.x() - slot.rect.left()) / self.scale
                dy = (point.y() - slot.rect.top()) / self.scale
                x, y = from_display(rotation, w, h, dx, dy)
                return slot.page, x, y
        return None

    # --- uneltele (B-300…B-302) -------------------------------------------------------

    def set_tool(self, tool: Tool) -> None:
        self.tool = Tool(tool)
        self._update_cursor()
        self.tool_changed.emit(self.tool.value)

    @property
    def active_tool(self) -> Tool:
        return Tool.HAND if self._space_hand else self.tool

    def _update_cursor(self) -> None:
        if self.active_tool is Tool.HAND:
            shape = Qt.CursorShape.ClosedHandCursor if self._drag_from is not None \
                else Qt.CursorShape.OpenHandCursor
        else:
            shape = Qt.CursorShape.IBeamCursor
        self.canvas.setCursor(shape)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_hand = True  # B-302
            self._update_cursor()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_hand = False
            self._update_cursor()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # API Qt
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.active_tool is Tool.HAND:
            self._drag_from = event.globalPosition().toPoint()
            self._update_cursor()
            return
        hit = self.view_to_page(event.position() + self._offset())
        if hit is not None:
            self.page_clicked.emit(*hit)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # API Qt
        self._mouse_move(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # API Qt
        self._mouse_release(event)

    def _mouse_move(self, event: QMouseEvent) -> None:
        if self._drag_from is None:
            return
        now = event.globalPosition().toPoint()
        delta = now - self._drag_from
        self._drag_from = now
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())

    def _mouse_release(self, _event: QMouseEvent) -> None:
        self._drag_from = None
        self._update_cursor()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            return
        if not self.mode.scrolling:  # o pagina: la capat, rotita trece la pagina vecina
            bar = self.verticalScrollBar()
            if event.angleDelta().y() < 0 and bar.value() >= bar.maximum():
                self.next_page()
                return
            if event.angleDelta().y() > 0 and bar.value() <= bar.minimum():
                self.previous_page()
                return
        super().wheelEvent(event)

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        anchor = self._current
        self._relayout()
        self._scroll_to(anchor)

    def sizeHint(self) -> QSize:
        return QSize(800, 600)
