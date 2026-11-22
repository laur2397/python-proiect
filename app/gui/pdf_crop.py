"""Decuparea paginilor in PDF Editor (faza 8, pasul 8.4a): E-010…E-012.

`Crop Pages` (`Ctrl+Shift+X`) trece vizualizarea in modul de decupare: cadrul
se trage cu mouse-ul pe pagina, iar in afara lui pagina se intuneca
(previzualizare live). Doua variante (E-010): un singur cadru pentru toate
paginile selectate, sau un cadru separat pe fiecare pagina. `Apply Crop`
(`Enter`) aplica, `Exit Crop` (`Esc`) iese fara modificari.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from app.core.model import Rect
from app.gui.pdf_view import from_display

SHADE = QColor(20, 24, 31, 120)
"""In afara cadrului, pagina se intuneca."""
FRAME = QColor("#2f6df6")
MIN_SIZE = 4.0
"""Un cadru mai mic de atat (puncte) e un clic, nu un cadru."""


class CropController(QObject):
    """Cadrele de decupare pe o vizualizare, pentru paginile `pages`."""

    changed = Signal()

    def __init__(self, view: Any, pages: list[int], *, same_for_all: bool = True) -> None:
        super().__init__(view)
        self.view = view
        self.pages = sorted(set(pages))
        self.same_for_all = same_for_all
        self.frames: dict[int, Rect] = {}
        """Cadrul fiecarei pagini, in coordonatele nucleului (puncte)."""
        self.last: Rect | None = None
        """Ultimul cadru tras: cel folosit pentru toate paginile (E-010)."""
        self._start: tuple[int, float, float] | None = None
        self._draft: tuple[int, Rect] | None = None
        view.viewport().installEventFilter(self)
        view.overlays.append(self.paint)
        view.viewport().setCursor(Qt.CursorShape.CrossCursor)
        view.viewport().update()

    def detach(self) -> None:
        self.view.viewport().removeEventFilter(self)
        if self.paint in self.view.overlays:
            self.view.overlays.remove(self.paint)
        self.view.viewport().unsetCursor()
        self.view.viewport().update()

    # --- cadrele ----------------------------------------------------------------------

    def frame_for(self, page: int) -> Rect | None:
        if page not in self.pages:
            return None
        if self._draft is not None and (self._draft[0] == page or self.same_for_all):
            return self._draft[1]
        return self.last if self.same_for_all else self.frames.get(page)

    def set_frame(self, page: int, rect: Rect) -> None:
        """Un cadru pe pagina `page` (si din cod, pentru teste)."""
        self.frames[page] = rect
        self.last = rect
        self.changed.emit()
        self.view.viewport().update()

    def result(self) -> Rect | dict[int, Rect] | None:
        """Ce se aplica: un cadru (toate paginile) sau cadrele per pagina."""
        if self.same_for_all:
            return self.last
        chosen = {n: r for n, r in self.frames.items() if n in self.pages}
        return chosen or None

    # --- mouse-ul ---------------------------------------------------------------------

    def _content(self, event: Any) -> QPointF:
        return event.position() + QPointF(self.view.horizontalScrollBar().value(),
                                          self.view.verticalScrollBar().value())

    def _clamped(self, page: int, event: Any) -> tuple[float, float]:
        point = self._content(event)
        slot = self.view.slot(page)
        x = min(max(point.x(), slot.rect.left()), slot.rect.right())
        y = min(max(point.y(), slot.rect.top()), slot.rect.bottom())
        rotation, w, h = self.view._page_geometry(page)
        return from_display(rotation, w, h, (x - slot.rect.left()) / self.view.scale,
                            (y - slot.rect.top()) / self.view.scale)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # API Qt
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            hit = self.view.view_to_page(self._content(event))
            if hit is not None and hit[0] in self.pages:
                self._start = hit
            return True
        if kind == QEvent.Type.MouseMove and self._start is not None:
            page, x0, y0 = self._start
            x1, y1 = self._clamped(page, event)
            self._draft = (page, _rect(x0, y0, x1, y1))
            self.view.viewport().update()
            return True
        if kind == QEvent.Type.MouseButtonRelease and self._start is not None:
            draft, self._draft, self._start = self._draft, None, None
            if draft is not None and draft[1].w >= MIN_SIZE and draft[1].h >= MIN_SIZE:
                self.set_frame(*draft)
            self.view.viewport().update()
            return True
        return kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                        QEvent.Type.MouseButtonDblClick)

    # --- desenul (previzualizarea live) -----------------------------------------------

    def paint(self, painter: QPainter, view: Any) -> None:
        if view is not self.view:
            return
        painter.save()
        for slot in view.slots():
            frame = self.frame_for(slot.page)
            if frame is None:
                continue
            inner = view.page_to_view(slot.page, frame)
            if inner is None:
                continue
            outside = QPainterPath()
            outside.addRect(QRectF(slot.rect))
            hole = QPainterPath()
            hole.addRect(inner)
            painter.fillPath(outside.subtracted(hole), SHADE)
            painter.setPen(QPen(FRAME, 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(inner)
        painter.restore()


def _rect(x0: float, y0: float, x1: float, y1: float) -> Rect:
    return Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
