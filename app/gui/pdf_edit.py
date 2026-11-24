"""Modul `Edit Content` din PDF Editor (faza 9, pasul 9.6): F-001, F-003, F-007…F-023,
F-100…F-110.

Cat timp e activ tabul `Edit Content`, pagina curenta se pregateste (F-003) si
blocurile ei capata contur; blocul activ are manere albastre la colturi si la
mijlocul laturilor (F-100, F-103). Clic intr-un bloc il activeaza si combo-ul de
font arata fontul lui (F-101; incorporat dar neinstalat = `[Nume]`, F-005);
dublu clic deschide editarea textului, cu reflow in latimea blocului (F-008,
F-104); clic in afara sau `Esc` termina editarea (F-009). `Ctrl`+clic selecteaza
blocul pentru stergere (`Delete`, F-012); tragerea unui maner il
redimensioneaza (F-013), `Ctrl`+tragerea sau tragerea marginii il muta (F-014).

Toate modificarile trec prin `window.modify`, cu pas de Undo.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPlainTextEdit

from app.core.errors import CoreError
from app.core.model import Rect
from app.gui.i18n import tr, tr_error

OUTLINE = QColor("#c46fd0")
"""B-312: in modul de editare, toate blocurile au un contur subtire roz-mov."""
ACTIVE = QColor("#2f6df6")
DRAG_FILL = QColor(47, 109, 246, 70)
"""B-313: suprapunerea albastra semitransparenta a blocului tras."""
HANDLE = 6.0
"""F-103: latura manerelor, in pixeli."""
SIZE_STEPS = (6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 60, 72, 96)
"""F-106: pasii lui `A+` si `A-`."""


def next_size(size: float, step: int) -> float:
    """F-106: marimea urmatoare (sau anterioara) din lista de pasi."""
    if step > 0:
        return float(next((s for s in SIZE_STEPS if s > size + 0.01), min(1638, size * 1.25)))
    return float(next((s for s in reversed(SIZE_STEPS) if s < size - 0.01),
                      max(1, size * 0.8)))


class ContentEditController(QObject):
    """Editarea continutului pe o vizualizare (F-001…F-023)."""

    changed = Signal()
    """Blocul activ sau pagina s-au schimbat (bara de text se actualizeaza)."""
    message = Signal(str)

    def __init__(self, window: Any, view: Any) -> None:
        from app.core.pdf.editor import PdfContentEditor

        super().__init__(view)
        self.window = window
        self.view = view
        self.editor = PdfContentEditor(view.document)
        self.page: int | None = None
        self.prepared: Any = None
        self.active_id: int | None = None
        self.marked: set[int] = set()
        """F-012: blocurile selectate cu `Ctrl`+clic, pentru `Delete`."""
        self.inline: QPlainTextEdit | None = None
        self._drag: tuple[str, int, float, float, Rect] | None = None
        self._drag_to: tuple[float, float] | None = None
        self.drawing: tuple[int, float, float] | None = None
        self.adding_text = False
        """`Add Text`: urmatoarea zona trasa devine un bloc nou."""
        view.viewport().installEventFilter(self)
        view.overlays.append(self.paint)

    def detach(self) -> None:
        self.finish_inline(commit=True)
        self.view.viewport().removeEventFilter(self)
        if self.paint in self.view.overlays:
            self.view.overlays.remove(self.paint)
        self.view.viewport().update()

    # --- pregatirea paginii (F-002, F-003) ------------------------------------------------

    def set_page(self, page: int) -> bool:
        """Pregateste pagina; o pagina care nu se poate edita da un mesaj si
        fereastra ramane in vizualizare (F-003)."""
        self.finish_inline(commit=True)
        self.message.emit(tr("edit.preparing"))
        try:
            self.prepared = self.editor.prepare_page(page, context=self.window.context)
        except CoreError as exc:
            self.prepared = None
            self.page = None
            self.message.emit("")
            self.window.show_message(tr_error(exc))
            return False
        self.page = page
        self.active_id = None
        self.marked.clear()
        # F-004: textul unei scanari vine din OCR; limbile alese conteaza
        scanned = any(getattr(b, "source", None) == "ocr" for b in self.prepared.blocks)
        self.message.emit(tr("edit.ocr_languages") if scanned else "")
        self.view.viewport().update()
        self.changed.emit()
        return True

    def refresh(self) -> None:
        """Dupa Undo sau dupa alta modificare: pagina se pregateste din nou."""
        self.editor = type(self.editor)(self.view.document)
        if self.page is not None:
            keep = self.active_id
            if self.set_page(min(self.page, self.view.document.page_count)) and keep:
                self.active_id = keep if any(b.id == keep for b in self.blocks()) else None
                self.changed.emit()

    def blocks(self) -> list[Any]:
        return list(self.prepared.blocks) if self.prepared is not None else []

    def active(self) -> Any:
        return next((b for b in self.blocks() if b.id == self.active_id), None)

    def select_block(self, block_id: int | None) -> None:
        self.active_id = block_id
        self.view.viewport().update()
        self.changed.emit()

    def picture_at(self, x: float, y: float) -> Any:
        pictures = list(self.prepared.pictures) if self.prepared is not None else []
        for picture in reversed(pictures):
            r = picture.rect
            if r.x <= x <= r.x + r.w and r.y <= y <= r.y + r.h:
                return picture
        return None

    def block_at(self, x: float, y: float) -> Any:
        for block in reversed(self.blocks()):
            r = block.rect
            if r.x <= x <= r.x + r.w and r.y <= y <= r.y + r.h:
                return block
        return None

    # --- modificarile -------------------------------------------------------------------------

    def _run(self, operation: Any) -> bool:
        """O modificare prin fereastra (Undo); modelul paginii se actualizeaza."""
        if self.page is None:
            return False
        self.window._editing_busy = True  # modelul se actualizeaza aici, nu se reciteste
        try:
            done = self.window.modify(lambda _document: operation() or True)
        finally:
            self.window._editing_busy = False
        if done is None:
            self.refresh()
            return False
        self.prepared = self.editor._pages.get(self.page) or \
            self.editor.prepare_page(self.page, context=self.window.context)
        self.view.viewport().update()
        self.changed.emit()
        return True

    def _select_matching(self, text: str) -> None:
        match = next((b for b in self.blocks() if b.text == text.strip()), None)
        self.select_block(match.id if match is not None else None)

    def edit_text(self, text: str) -> bool:
        """F-008: textul blocului activ, cu reflow."""
        block = self.active()
        if block is None:
            return False
        ok = self._run(lambda: self.editor.set_block_text(self.page, block.id, text))
        self._select_matching(text)
        return ok

    def delete_active(self) -> bool:
        """F-012: blocurile marcate cu `Ctrl`+clic (sau blocul activ)."""
        ids = sorted(self.marked) or ([self.active_id] if self.active_id else [])
        if not ids:
            return False

        def delete() -> None:
            for block_id in sorted(ids, reverse=True):
                self.editor.delete_block(self.page, block_id)
        ok = self._run(delete)
        self.marked.clear()
        self.select_block(None)
        return ok

    def move_active(self, dx: float, dy: float) -> bool:
        """F-014."""
        block = self.active()
        if block is None:
            return False
        ok = self._run(lambda: self.editor.move_block(self.page, block.id, dx, dy))
        self._select_matching(block.text)
        return ok

    def resize_active(self, rect: Rect) -> bool:
        """F-013: textul face reflow."""
        block = self.active()
        if block is None:
            return False
        ok = self._run(lambda: self.editor.resize_block(self.page, block.id, rect))
        self._select_matching(block.text)
        return ok

    def format_active(self, **attrs: Any) -> bool:
        """F-015, F-016, F-106…F-110: pe tot blocul activ."""
        block = self.active()
        if block is None:
            return False
        ok = self._run(lambda: self.editor.apply_text_format(self.page, block.id, **attrs))
        self._select_matching(block.text)
        return ok

    def add_block(self, rect: Rect, text: str) -> bool:
        """F-011: un bloc nou, in limitele paginii."""
        ok = self._run(lambda: self.editor.add_text_block(self.page, rect, text))
        self._select_matching(text)
        return ok

    # --- editarea pe loc (F-008, F-009, F-104) -------------------------------------------------

    def start_inline(self) -> QPlainTextEdit | None:
        block = self.active()
        if block is None or self.page is None:
            return None
        self.finish_inline(commit=False)
        box = self.view.page_to_view(self.page, block.rect)
        if box is None:
            return None
        editor = QPlainTextEdit(self.view.viewport())
        editor.setObjectName("edit_inline")
        editor.setPlainText(block.text)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)  # F-104: reflow
        offset = QPointF(self.view.horizontalScrollBar().value(),
                         self.view.verticalScrollBar().value())
        editor.setGeometry(box.translated(-offset).toRect().adjusted(-2, -2, 2, 40))
        editor.installEventFilter(self)
        editor.show()
        editor.setFocus()
        self.inline = editor
        return editor

    def finish_inline(self, *, commit: bool) -> bool:
        """F-009: clic in afara sau `Esc`: modificarile raman."""
        editor, self.inline = self.inline, None
        if editor is None:
            return False
        text = editor.toPlainText()
        editor.hide()
        editor.deleteLater()
        block = self.active()
        if commit and block is not None and text != block.text:
            return self.edit_text(text)
        return False

    # --- mouse-ul ------------------------------------------------------------------------------

    def _content(self, event: Any) -> QPointF:
        return event.position() + QPointF(self.view.horizontalScrollBar().value(),
                                          self.view.verticalScrollBar().value())

    def _page_point(self, event: Any) -> tuple[int, float, float] | None:
        return self.view.view_to_page(self._content(event))

    def handle_at(self, x: float, y: float) -> str | None:
        """Manerul de sub punct (`tl`, `t`, `tr`, `r`, `br`, `b`, `bl`, `l`)."""
        block = self.active()
        if block is None:
            return None
        r = block.rect
        tolerance = HANDLE / max(self.view.scale, 0.01)
        xs = {"l": r.x, "c": r.x + r.w / 2, "r": r.x + r.w}
        ys = {"t": r.y, "m": r.y + r.h / 2, "b": r.y + r.h}
        for name, hx, hy in (("tl", "l", "t"), ("t", "c", "t"), ("tr", "r", "t"),
                             ("r", "r", "m"), ("br", "r", "b"), ("b", "c", "b"),
                             ("bl", "l", "b"), ("l", "l", "m")):
            if abs(x - xs[hx]) <= tolerance and abs(y - ys[hy]) <= tolerance:
                return name
        return None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # API Qt
        kind = event.type()
        if watched is self.inline:
            if kind == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.finish_inline(commit=True)
                return True
            return False
        if self.prepared is None:
            return False
        if kind == QEvent.Type.ContextMenu:  # F-021…F-023: meniul imaginii
            point = QPointF(event.pos()) + QPointF(self.view.horizontalScrollBar().value(),
                                                   self.view.verticalScrollBar().value())
            hit = self.view.view_to_page(point)
            picture = self.picture_at(hit[1], hit[2]) if hit and hit[0] == self.page else None
            if picture is None:
                return False
            self.window.picture_menu(picture.id).popup(event.globalPos())
            return True
        if kind == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Delete:
            return self.delete_active()
        if kind == QEvent.Type.MouseButtonDblClick:
            hit = self._page_point(event)
            if hit is not None and hit[0] == self.page:
                block = self.block_at(hit[1], hit[2])
                if block is not None:
                    self.select_block(block.id)
                    self.start_inline()
            return True
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            return self._press(event)
        if kind == QEvent.Type.MouseMove and (self._drag or self.drawing):
            hit = self._page_point(event)
            if hit is not None and hit[0] == self.page:
                self._drag_to = (hit[1], hit[2])
            self.view.viewport().update()
            return True
        if kind == QEvent.Type.MouseButtonRelease and (self._drag or self.drawing):
            return self._release(event)
        return False

    def _press(self, event: Any) -> bool:
        hit = self._page_point(event)
        if self.inline is not None:
            self.finish_inline(commit=True)
        if hit is None or hit[0] != self.page:
            return False
        _page, x, y = hit
        if self.adding_text:
            self.drawing = (self.page, x, y)
            return True
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        handle = self.handle_at(x, y)
        if handle is not None and self.active() is not None:
            self._drag = ("resize:" + handle, self.active_id, x, y, self.active().rect)
            return True
        block = self.block_at(x, y)
        if block is None:
            self.marked.clear()
            self.select_block(None)
            return True
        if ctrl:  # F-012: selectie pentru stergere; F-014: Ctrl+tragere muta
            self.marked.symmetric_difference_update({block.id})
            self.select_block(block.id)
            self._drag = ("move", block.id, x, y, block.rect)
            return True
        on_border = min(x - block.rect.x, block.rect.x + block.rect.w - x,
                        y - block.rect.y, block.rect.y + block.rect.h - y) <= \
            HANDLE / max(self.view.scale, 0.01)
        self.select_block(block.id)
        if on_border:
            self._drag = ("move", block.id, x, y, block.rect)
        return True

    def _release(self, event: Any) -> bool:
        hit = self._page_point(event)
        if self.drawing is not None:
            page, x0, y0 = self.drawing
            self.drawing = None
            self.adding_text = False
            if hit is not None and hit[0] == page:
                rect = Rect(min(x0, hit[1]), min(y0, hit[2]), abs(hit[1] - x0),
                            abs(hit[2] - y0))
                if rect.w >= 10 and rect.h >= 5:
                    text = self.window.ask_text("edit.add_text", "edit.text")
                    if text:
                        self.add_block(rect, text)
            return True
        kind, _block_id, x0, y0, rect = self._drag  # type: ignore[misc]
        self._drag = None
        self._drag_to = None
        if hit is None:
            return True
        dx, dy = hit[1] - x0, hit[2] - y0
        if abs(dx) < 1 and abs(dy) < 1:
            return True
        if kind == "move":
            self.move_active(dx, dy)
        else:
            self.resize_active(resized(rect, kind.split(":")[1], dx, dy))
        return True

    # --- desenul (F-100, F-103) -----------------------------------------------------------------

    def drag_preview(self) -> tuple[Rect, Rect] | None:
        """B-313: (locul vechi, locul nou) cat timp un bloc e tras; altfel None."""
        if self._drag is None or self._drag_to is None or self._drag[0] != "move":
            return None
        _kind, _block_id, x0, y0, rect = self._drag
        dx, dy = self._drag_to[0] - x0, self._drag_to[1] - y0
        return rect, Rect(rect.x + dx, rect.y + dy, rect.w, rect.h)

    def paint(self, painter: QPainter, view: Any) -> None:
        if view is not self.view or self.page is None:
            return
        painter.save()
        for block in self.blocks():
            box = view.page_to_view(self.page, block.rect)
            if box is None:
                continue
            active = block.id == self.active_id
            color = ACTIVE if active or block.id in self.marked else OUTLINE
            painter.setPen(QPen(color, 1.2 if active else 0.8))  # B-312: contur subtire
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(box)
            if active:
                _draw_handles(painter, box)  # B-314: opt manere
        preview = self.drag_preview()
        if preview is not None:  # B-313
            old = view.page_to_view(self.page, preview[0])
            new = view.page_to_view(self.page, preview[1])
            if old is not None:
                painter.setPen(QPen(ACTIVE, 1, Qt.PenStyle.DotLine))  # locul vechi, punctat
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(old)
            if new is not None:
                painter.setPen(QPen(ACTIVE, 1))
                painter.setBrush(DRAG_FILL)
                painter.drawRect(new)
                _draw_handles(painter, new)
        painter.restore()


def _draw_handles(painter: QPainter, box: QRectF) -> None:
    painter.setPen(QPen(ACTIVE, 1))
    painter.setBrush(ACTIVE)
    for point in _handle_points(box):
        painter.drawRect(QRectF(point.x() - HANDLE / 2, point.y() - HANDLE / 2,
                                HANDLE, HANDLE))


def _handle_points(box: QRectF) -> list[QPointF]:
    cx, cy = box.center().x(), box.center().y()
    return [box.topLeft(), QPointF(cx, box.top()), box.topRight(), QPointF(box.right(), cy),
            box.bottomRight(), QPointF(cx, box.bottom()), box.bottomLeft(),
            QPointF(box.left(), cy)]


def resized(rect: Rect, handle: str, dx: float, dy: float) -> Rect:
    """F-013: dreptunghiul dupa tragerea manerului `handle`."""
    x0, y0, x1, y1 = rect.x, rect.y, rect.x + rect.w, rect.y + rect.h
    if "l" in handle:
        x0 += dx
    if "r" in handle:
        x1 += dx
    if handle in ("t", "tl", "tr"):
        y0 += dy
    if handle in ("b", "bl", "br"):
        y1 += dy
    return Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
