"""Uneltele de adnotare din PDF Editor (faza 7, pasul 7.9b): D-001…D-023,
D-052, D-106.

O unealta activa primeste mouse-ul inaintea selectiei:
- `note` (D-001) si `insert_text` (D-007): un clic pune adnotarea; unealta
  revine apoi la `Select`;
- marcajele (D-004…D-006): cu text selectat, fereastra le aplica direct pe
  selectie; altfel unealta marcheaza textul tras cu mouse-ul (D-003: fara strat
  de text, nucleul refuza, iar fereastra arata mesajul);
- formele (D-009…D-016): tragere pentru linie, sageata, dreptunghi, oval,
  caseta si blocul de text; clicuri pentru poligon, nor si polilinie (poligonul
  si norul se inchid cu clic pe primul varf, polilinia se termina cu dublu
  clic); `Ink` deseneaza liber, iar cu `Shift` tinut mai multe trasee fac o
  singura adnotare (D-009). `Shift` fixeaza linia la 0/45/90 de grade (D-010),
  face patrat (D-012) si cerc (D-013).
Setarile de desen (D-018: culoare, grosime, fundal, transparenta; pentru
casete marimea si culoarea textului, D-020) se aleg in bara de stil inainte de
desenare si raman pentru formele urmatoare.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from app.core.model import AnnotationData, AnnotationType, Rect
from app.core.pdf.markup import TEXT_MARKUPS
from app.gui.pdf_view import from_display

T = AnnotationType

DRAG_SHAPES = (T.LINE, T.ARROW, T.RECTANGLE, T.OVAL, T.TEXT_BOX)
CLICK_SHAPES = (T.POLYGON, T.CLOUD, T.POLYLINE)
ONE_SHOT = (T.NOTE, T.INSERT_TEXT, T.STAMP)
DRAW_MENU = (T.INK, T.LINE, T.ARROW, T.RECTANGLE, T.OVAL, T.POLYGON, T.CLOUD, T.POLYLINE,
             T.TEXT_BOX)
"""D-009…D-017: meniul `Draw ▾`, in ordine; blocul de text e separat (D-019)."""
CLOSE_DISTANCE = 6.0
"""Puncte: un clic atat de aproape de primul varf inchide poligonul (D-014)."""
PREVIEW = QColor("#2f6df6")


@dataclass
class DrawStyle:
    """D-018, D-020: setarile formelor urmatoare."""

    color: str = "#d92d20"
    line_width: float = 1.0
    fill_color: str | None = None
    opacity: float = 1.0
    font_size: float = 12.0
    text_color: str = "#000000"


@dataclass
class _Draft:
    kind: AnnotationType
    page: int
    points: list[tuple[float, float]] = field(default_factory=list)
    paths: list[list[tuple[float, float]]] = field(default_factory=list)
    text_block: bool = False


def constrain(start: tuple[float, float], end: tuple[float, float], kind: AnnotationType
              ) -> tuple[float, float]:
    """`Shift`: linie la multiplu de 45 de grade (D-010, D-011), patrat sau cerc
    (D-012, D-013)."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    if kind in (T.LINE, T.ARROW):
        length = math.hypot(dx, dy)
        angle = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
        return start[0] + length * math.cos(angle), start[1] + length * math.sin(angle)
    if kind in (T.RECTANGLE, T.OVAL):
        side = max(abs(dx), abs(dy))
        return start[0] + math.copysign(side, dx or 1), start[1] + math.copysign(side, dy or 1)
    return end


def moved(annot: AnnotationData, dx: float, dy: float) -> AnnotationData:
    """D-052: adnotarea mutata cu (dx, dy) puncte."""

    def shift(points: Any) -> list[tuple[float, float]]:
        return [(float(p[0]) + dx, float(p[1]) + dy) for p in points]

    geometry = dict(annot.geometry)
    if "points" in geometry:
        geometry["points"] = shift(geometry["points"])
    if "paths" in geometry:
        geometry["paths"] = [shift(path) for path in geometry["paths"]]
    if "point" in geometry:
        geometry["point"] = shift([geometry["point"]])[0]
    if "rects" in geometry:
        geometry["rects"] = [Rect(r.x + dx, r.y + dy, r.w, r.h) for r in geometry["rects"]]
    box = annot.bbox
    return replace(annot, geometry=geometry, bbox=Rect(box.x + dx, box.y + dy, box.w, box.h))


class ToolController(QObject):
    """Unealta de adnotare a unei vizualizari. `create(data)` primeste adnotarea
    gata (fereastra o adauga cu Undo); `ask_text(tip)` cere textul pentru
    `Insert Text` si casete."""

    finished = Signal()
    """Unealta s-a terminat (nota, Insert Text): fereastra revine la `Select`."""

    def __init__(self, view: Any, create: Callable[[AnnotationData], Any],
                 ask_text: Callable[[AnnotationType], str | None],
                 style: Callable[[], DrawStyle],
                 place_stamp: Callable[[int, float, float], Any] | None = None) -> None:
        super().__init__(view)
        self.view = view
        self.create = create
        self.place_stamp = place_stamp
        """D-045: stampila aleasa se pune cu un clic (coltul stanga-sus)."""
        self.ask_text = ask_text
        self.style = style
        self.kind: AnnotationType | None = None
        self.text_block = False
        self.draft: _Draft | None = None
        self._pointer: tuple[float, float] | None = None
        self._pressed = False
        view.viewport().installEventFilter(self)  # dupa selectie: primeste evenimentele primul
        view.overlays.append(self.paint)

    def set_tool(self, kind: AnnotationType | None, *, text_block: bool = False) -> None:
        self.kind = kind
        self.text_block = text_block
        self.draft = None
        self.view.viewport().setCursor(Qt.CursorShape.CrossCursor if kind is not None
                                       else Qt.CursorShape.IBeamCursor)
        self.view.viewport().update()

    # --- coordonatele -----------------------------------------------------------------

    def _content(self, event: Any) -> QPointF:
        return event.position() + QPointF(self.view.horizontalScrollBar().value(),
                                          self.view.verticalScrollBar().value())

    def _clamp(self, page: int, event: Any) -> tuple[float, float]:
        """Punctul pe pagina `page`, chiar daca mouse-ul a iesit din ea."""
        point = self._content(event)
        slot = self.view.slot(page)
        x = min(max(point.x(), slot.rect.left()), slot.rect.right())
        y = min(max(point.y(), slot.rect.top()), slot.rect.bottom())
        rotation, w, h = self.view._page_geometry(page)
        return from_display(rotation, w, h, (x - slot.rect.left()) / self.view.scale,
                            (y - slot.rect.top()) / self.view.scale)

    # --- evenimentele -----------------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # API Qt
        if self.kind is None or self.view.document is None:
            return False
        kind = event.type()
        if kind not in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove,
                        QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            return False
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._press(event)
        elif kind == QEvent.Type.MouseMove:
            self._move(event, shift)
        elif kind == QEvent.Type.MouseButtonRelease and \
                event.button() == Qt.MouseButton.LeftButton:
            self._release(shift)
        elif kind == QEvent.Type.MouseButtonDblClick:
            self._double_click()
        return True

    def _press(self, event: Any) -> None:
        hit = self.view.view_to_page(self._content(event))
        self._pressed = True
        assert self.kind is not None
        if hit is None:
            return
        page, x, y = hit
        if self.kind in CLICK_SHAPES:
            if self.draft is None or self.draft.page != page:
                self.draft = _Draft(self.kind, page, [(x, y)])
                return
            first = self.draft.points[0]
            if self.kind is not T.POLYLINE and len(self.draft.points) >= 3 and \
                    math.dist(first, (x, y)) <= CLOSE_DISTANCE:  # D-014, D-015
                self._commit()
                return
            self.draft.points.append((x, y))
            return
        if self.kind in ONE_SHOT:
            self._place_point(page, x, y)
            return
        if self.kind is T.INK:
            if self.draft is None or self.draft.page != page:
                self.draft = _Draft(T.INK, page)
            self.draft.paths.append([(x, y)])
            return
        self.draft = _Draft(self.kind, page, [(x, y), (x, y)], text_block=self.text_block)

    def _move(self, event: Any, shift: bool) -> None:
        if self.draft is None:
            return
        point = self._clamp(self.draft.page, event)
        self._pointer = point
        if self.kind is T.INK and self._pressed and self.draft.paths:
            self.draft.paths[-1].append(point)
        elif self._pressed and len(self.draft.points) == 2 and self.kind not in CLICK_SHAPES:
            start = self.draft.points[0]
            self.draft.points[1] = constrain(start, point, self.draft.kind) if shift else point
        self.view.viewport().update()

    def _release(self, shift: bool) -> None:
        self._pressed = False
        if self.draft is None:
            return
        if self.kind is T.INK:
            if not shift:  # D-009: cu Shift, traseele se aduna intr-o singura adnotare
                self._commit()
            return
        if self.kind in DRAG_SHAPES or self.kind in TEXT_MARKUPS:
            self._commit()

    def _double_click(self) -> None:
        """D-016: polilinia se termina cu dublu clic (si poligonul, ca scurtatura)."""
        minimum = 2 if self.kind is T.POLYLINE else 3
        if self.draft is not None and self.kind in CLICK_SHAPES and \
                len(self.draft.points) >= minimum:
            self._commit()

    def release_shift(self) -> None:
        """`Shift` eliberat: traseele Ink adunate devin o adnotare (D-009)."""
        if self.kind is T.INK and self.draft is not None and self.draft.paths:
            self._commit()

    # --- crearea ----------------------------------------------------------------------

    def _place_point(self, page: int, x: float, y: float) -> None:
        assert self.kind is not None
        if self.kind is T.STAMP:
            if self.place_stamp is not None:
                self.place_stamp(page, x, y)
            self.finished.emit()
            return
        if self.kind is T.NOTE:
            data = AnnotationData(None, T.NOTE, page, {"point": (x, y)})
        else:
            text = self.ask_text(T.INSERT_TEXT)
            if text is None:
                return
            data = AnnotationData(None, T.INSERT_TEXT, page, {"point": (x, y)}, content=text,
                                  color=self.style().color)
        self.create(data)
        self.finished.emit()

    def _markup(self, draft: _Draft) -> AnnotationData | None:
        """Textul dintre punctul de apasare si cel de eliberare (D-004…D-006)."""
        from app.core.pdf.copying import char_index_at

        (x0, y0), (x1, y1) = draft.points
        first = char_index_at(self.view.document, draft.page, x0, y0)
        last = char_index_at(self.view.document, draft.page, x1, y1)
        if first is None or last is None:
            return None
        start, end = sorted((first, last))
        rects = self.view.document.page_text(draft.page).span_rects(start, end - start + 1)
        return AnnotationData(None, draft.kind, draft.page, {"rects": rects}) if rects else None

    def _commit(self) -> None:
        draft, self.draft = self.draft, None
        self.view.viewport().update()
        if draft is None:
            return
        style = self.style()
        common = {"color": style.color, "opacity": style.opacity,
                  "line_width": style.line_width}
        kind = draft.kind
        if kind in TEXT_MARKUPS:
            data = self._markup(draft)
            if data is not None:
                self.create(data)
        elif kind is T.INK:
            paths = [p for p in draft.paths if len(p) >= 2]
            if paths:
                self.create(AnnotationData(None, T.INK, draft.page, {"paths": paths}, **common))
        elif kind in (T.LINE, T.ARROW):
            start, end = draft.points
            if math.dist(start, end) >= 2:
                self.create(AnnotationData(None, kind, draft.page, {"points": [start, end]},
                                           **common))
        elif kind in (T.RECTANGLE, T.OVAL, T.TEXT_BOX):
            (x0, y0), (x1, y1) = draft.points
            rect = Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            if rect.w < 4 or rect.h < 4:
                return
            if kind is not T.TEXT_BOX:
                self.create(AnnotationData(None, kind, draft.page, {}, bbox=rect,
                                           fill_color=style.fill_color, **common))
                return
            text = self.ask_text(T.TEXT_BOX)
            if text is not None:
                self.create(AnnotationData(
                    None, T.TEXT_BOX, draft.page,
                    {"font_size": style.font_size, "text_color": style.text_color,
                     "text_block": draft.text_block}, bbox=rect, content=text,
                    color=None if draft.text_block else style.color,
                    fill_color=style.fill_color, opacity=style.opacity,
                    line_width=style.line_width))
        elif kind in CLICK_SHAPES:
            fill = style.fill_color if kind is not T.POLYLINE else None
            self.create(AnnotationData(None, kind, draft.page, {"points": draft.points},
                                       fill_color=fill, **common))

    # --- previzualizarea --------------------------------------------------------------

    def _to_view(self, page: int, point: tuple[float, float]) -> QPointF | None:
        box = self.view.page_to_view(page, Rect(point[0], point[1], 0, 0))
        return None if box is None else box.topLeft()

    def paint(self, painter: QPainter, view: Any) -> None:
        if view is not self.view or self.draft is None:
            return
        draft = self.draft
        painter.setPen(QPen(PREVIEW, 1.5, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        groups = draft.paths if draft.kind is T.INK else [draft.points]
        for group in groups:
            points = [p for p in (self._to_view(draft.page, q) for q in group) if p]
            if draft.kind in CLICK_SHAPES and self._pointer is not None:
                pointer = self._to_view(draft.page, self._pointer)
                if pointer is not None:
                    points.append(pointer)
            if len(points) < 2:
                continue
            if draft.kind in (T.RECTANGLE, T.TEXT_BOX, *TEXT_MARKUPS):
                painter.drawRect(QRectF(points[0], points[1]).normalized())
            elif draft.kind is T.OVAL:
                painter.drawEllipse(QRectF(points[0], points[1]).normalized())
            else:
                line = QPainterPath(points[0])
                for p in points[1:]:
                    line.lineTo(p)
                painter.drawPath(line)
