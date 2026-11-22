"""Uneltele de adnotare din PDF Editor (faza 7, pasul 7.9b): D-001…D-023, D-052."""

from __future__ import annotations

import os

import pytest
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.context import AppContext
from app.core.model import AnnotationData, AnnotationType, Rect
from app.core.paths import AppPaths
from app.gui.pdf_editor import PdfEditorWindow
from app.gui.pdf_tools import DRAW_MENU, constrain, moved

T = AnnotationType


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    c.settings.set("pdf_editor.default_author", "Ana")
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    path = text_pdf(tmp_path / "dosar.pdf", [["Cerere de finantare", "Bugetul total"]])
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    entry = w.open_path(path)
    entry.view.set_zoom(75)
    entry.view.go_to_page(1)
    QApplication.processEvents()
    yield w
    w.close()


def at(view, x, y, page=1):
    box = view.page_to_view(page, Rect(x, y, 0, 0))
    point = box.topLeft() - QPointF(view.horizontalScrollBar().value(),
                                    view.verticalScrollBar().value())
    return QPoint(int(point.x()), int(point.y()))


def drag(view, points, modifier=Qt.KeyboardModifier.NoModifier):
    viewport = view.viewport()
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, modifier, at(view, *points[0]))
    for x, y in points[1:]:
        QTest.mouseMove(viewport, at(view, x, y))
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, modifier, at(view, *points[-1]))


def click(view, x, y):
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=at(view, x, y))


def created(window, kind):
    return [a for a in window.current().document.annotations() if a.annot_type is kind]


# --- D-001, D-007 ---------------------------------------------------------------------


def test_T_D001_1_note_tool_places_a_note(window):
    window.actions["add_note"].trigger()  # Ctrl+M
    click(window.current().view, 300, 400)
    note = created(window, T.NOTE)[-1]
    assert note.geometry["point"] == pytest.approx((300, 400), abs=2)
    assert note.author == "Ana"
    assert window.annotation_tool is None  # unealta revine la Select


def test_T_D007_1_insert_text(window):
    window.actions["insert_text"].trigger()  # Ctrl+J
    click(window.current().view, 200, 300)
    [caret] = created(window, T.INSERT_TEXT)
    assert caret.content == "Text"


# --- D-004…D-006 ----------------------------------------------------------------------


def test_T_D004_1_highlight_the_text_selection(window, ctx):
    entry = window.current()
    hit = next(h for h in entry.document.search("Bugetul") if h.source == "text")
    entry.selection.mode = "text"
    entry.selection.text_start = (1, hit.start)
    entry.selection.text_end = (1, hit.start + hit.length - 1)
    window.actions["highlight"].trigger()  # Ctrl+H
    [mark] = created(window, T.HIGHLIGHT)
    assert mark.color == ctx.settings.get("pdf_editor.markup_color.highlight")
    assert mark.geometry["rects"][0].x == pytest.approx(hit.rect.x, abs=0.5)
    assert not entry.selection.has_selection()


def test_T_D005_1_underline_tool_marks_dragged_text(window):
    entry = window.current()
    window.actions["underline"].trigger()  # fara selectie: unealta
    assert window.annotation_tool is T.UNDERLINE
    hit = next(h for h in entry.document.search("Cerere") if h.source == "text").rect
    drag(entry.view, [(hit.x + 1, hit.y + hit.h / 2), (hit.x + hit.w - 1, hit.y + hit.h / 2)])
    [mark] = created(window, T.UNDERLINE)
    assert mark.geometry["rects"][0].w == pytest.approx(hit.w, abs=1)


# --- D-009…D-019 ----------------------------------------------------------------------


def test_T_D009_1_ink_and_shift_strokes(window):
    view = window.current().view
    window.set_annotation_tool(T.INK)
    drag(view, [(100, 100), (120, 110), (140, 100)])
    assert len(created(window, T.INK)) == 1
    shift = Qt.KeyboardModifier.ShiftModifier
    drag(view, [(100, 200), (120, 210)], shift)  # D-009: cu Shift, trasee adunate
    drag(view, [(150, 200), (170, 210)], shift)
    assert len(created(window, T.INK)) == 1
    window.current().tools.release_shift()
    inks = created(window, T.INK)
    assert len(inks) == 2 and len(inks[-1].geometry["paths"]) == 2


def test_T_D010_D013_shift_constraints():
    assert constrain((0, 0), (10, 9), T.LINE) == pytest.approx((9.51, 9.51), abs=0.01)
    assert constrain((0, 0), (10, 1), T.ARROW) == pytest.approx((10.05, 0), abs=0.01)
    assert constrain((0, 0), (10, 4), T.RECTANGLE) == (10, 10)
    assert constrain((5, 5), (1, 8), T.OVAL) == (1, 9)


@pytest.mark.parametrize("kind", [T.LINE, T.ARROW, T.RECTANGLE, T.OVAL])
def test_T_D010_D013_drag_shapes(window, kind):
    window.set_annotation_tool(kind)
    assert window.style_bar.isVisible()  # D-018: setarile inainte de desenare
    window.style_width.setValue(3)
    window.style_opacity.setValue(50)
    drag(window.current().view, [(100, 300), (160, 340), (200, 360)])
    [shape] = created(window, kind)
    assert shape.line_width == 3 and shape.opacity == pytest.approx(0.5)
    if kind in (T.RECTANGLE, T.OVAL):
        assert (shape.bbox.x, shape.bbox.y) == pytest.approx((100, 300), abs=2)
        assert (shape.bbox.w, shape.bbox.h) == pytest.approx((100, 60), abs=2)


@pytest.mark.parametrize("kind", [T.POLYGON, T.CLOUD])
def test_T_D014_D015_polygon_closes_on_first_vertex(window, kind):
    view = window.current().view
    window.set_annotation_tool(kind)
    for x, y in ((100, 300), (200, 300), (150, 380)):
        click(view, x, y)
    assert created(window, kind) == []
    click(view, 101, 301)  # clic pe primul varf
    [shape] = created(window, kind)
    assert len(shape.geometry["points"]) == 3


def test_T_D016_1_polyline_ends_with_double_click(window):
    view = window.current().view
    window.set_annotation_tool(T.POLYLINE)
    click(view, 100, 300)
    click(view, 200, 320)
    QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, pos=at(view, 200, 320))
    [line] = created(window, T.POLYLINE)
    assert len(line.geometry["points"]) >= 2


def test_T_D017_D019_text_box_and_text_block(window):
    view = window.current().view
    window.set_annotation_tool(T.TEXT_BOX)
    window.style_font.setValue(14)
    drag(view, [(100, 400), (250, 450)])
    [box] = created(window, T.TEXT_BOX)
    assert box.content == "Text" and box.geometry["font_size"] == 14
    assert not box.geometry["text_block"]
    window.draw_menu.findChild(QAction, "pdf_draw_text_block").trigger()
    drag(view, [(100, 500), (250, 540)])
    block = created(window, T.TEXT_BOX)[-1]
    assert block.geometry["text_block"] and block.line_width == 0  # D-020: fara chenar


def test_T_D009_2_draw_menu_lists_the_shapes(window):
    names = [a.objectName() for a in window.draw_menu.actions()]
    assert names == [f"pdf_draw_{k.value}" for k in DRAW_MENU] + ["pdf_draw_text_block"]


def test_escape_cancels_the_tool(window):
    window.set_annotation_tool(T.RECTANGLE)
    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert window.annotation_tool is None and not window.style_bar.isVisible()


# --- D-052 ----------------------------------------------------------------------------


def test_T_D052_1_drag_moves_the_selected_annotation(window):
    data = AnnotationData(None, T.RECTANGLE, 1, {}, bbox=Rect(100, 300, 60, 40))
    rect = window.modify(lambda doc: doc.add_annotation(data))
    window._page_clicked(1, 120, 320)  # selectata
    drag(window.current().view, [(120, 320), (170, 345), (220, 370)])
    after = next(a for a in window.current().document.annotations() if a.id == rect.id)
    assert (after.bbox.x, after.bbox.y) == pytest.approx((200, 350), abs=2)
    window.undo()
    before = next(a for a in window.current().document.annotations() if a.id == rect.id)
    assert (before.bbox.x, before.bbox.y) == pytest.approx((100, 300), abs=0.5)


def test_moved_shifts_every_kind_of_geometry():
    note = AnnotationData(1, T.NOTE, 1, {"point": (10, 10)}, bbox=Rect(10, 10, 20, 20))
    assert moved(note, 5, 6).geometry["point"] == (15, 16)
    ink = AnnotationData(2, T.INK, 1, {"paths": [[(0, 0), (1, 1)]]})
    assert moved(ink, 1, 1).geometry["paths"] == [[(1, 1), (2, 2)]]
    mark = AnnotationData(3, T.HIGHLIGHT, 1, {"rects": [Rect(0, 0, 5, 5)]})
    assert moved(mark, 2, 3).geometry["rects"] == [Rect(2, 3, 5, 5)]
    assert moved(mark, 2, 3).bbox == Rect(2, 3, 0, 0)
