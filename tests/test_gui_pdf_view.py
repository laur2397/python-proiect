"""Zona de pagina a PDF Editor-ului (faza 7, pasul 7.7a): B-001…B-018,
B-300…B-302."""

from __future__ import annotations

import os

import pikepdf
import pytest
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest

from app.core.errors import FileCorruptError
from app.core.model import Rect
from app.core.pdf.document import PdfDocument
from app.gui.pdf_view import (
    HISTORY_LIMIT,
    ZOOM_MAX,
    ZOOM_MIN,
    FitMode,
    PdfView,
    Tool,
    ViewMode,
    from_display,
    to_display,
)


@pytest.fixture
def doc(tmp_path):
    path = text_pdf(tmp_path / "doc.pdf", [[f"Pagina {n}"] for n in range(1, 6)])
    with PdfDocument.open(path) as d:
        yield d


def make_view(qtbot, document):
    v = PdfView()
    qtbot.addWidget(v)
    v.resize(800, 600)
    v.show()
    qtbot.waitExposed(v)
    v.set_document(document)
    return v


@pytest.fixture
def view(qtbot, doc):
    return make_view(qtbot, doc)


def paint(view):
    """Pictarea si pregatirea vecinilor (offscreen, ele vin prin bucla de evenimente)."""
    from PySide6.QtWidgets import QApplication

    view.viewport().repaint()
    QApplication.processEvents()
    QApplication.processEvents()


# --- B-001 ----------------------------------------------------------------------------


def test_T_B001_1_rendering_is_lazy(qtbot, tmp_path):
    path = text_pdf(tmp_path / "lung.pdf", [[f"Pagina {n}"] for n in range(1, 41)])
    with PdfDocument.open(path) as long_doc:
        v = make_view(qtbot, long_doc)
        paint(v)
        assert v.visible_pages() == [1, 2]
        assert v.render_count == 2  # pagina vizibila si cea de dupa ea, nu toate 40
        v.go_to_page(20)
        paint(v)
        assert 19 in v.visible_pages() and 21 in v.visible_pages()  # una inainte, una dupa
        assert v.render_count < 12
        assert v.content_size().height() > 32767  # mai lung decat poate picta un widget
        v.last_page()
        paint(v)
        assert 40 in v.visible_pages() and v._cache.get((40, v.zoom)) is not None


def test_T_B001_2_corrupt_page_shows_a_grey_box(view, monkeypatch):
    def broken(number, zoom, **kw):
        raise FileCorruptError("stricat", page=number)

    view._cache.clear()
    monkeypatch.setattr(view.document, "render_page", broken)
    paint(view)  # fara exceptie
    assert view._cache[(1, view.zoom)] is None


# --- B-002…B-006 ----------------------------------------------------------------------


def test_T_B002_B005_view_modes(view):
    view.set_mode(ViewMode.ONE_PAGE)
    assert [s.page for s in view.slots()] == [1]
    view.set_mode(ViewMode.ONE_PAGE_SCROLLING)
    assert [s.page for s in view.slots()] == [1, 2, 3, 4, 5]
    view.set_mode(ViewMode.TWO_PAGE)
    assert view.spreads() == [(1, 2), (3, 4), (5, None)]
    left, right = view.slots()
    assert (left.page, right.page) == (1, 2) and left.rect.left() < right.rect.left()
    view.set_mode(ViewMode.TWO_PAGE_SCROLLING)
    assert [s.page for s in view.slots()] == [1, 2, 3, 4, 5]


def test_T_B006_1_odd_pages_on_the_right(view):
    view.set_odd_on_right(True)
    assert view.spreads() == [(1, None), (2, None), (3, None), (4, None), (5, None)]
    view.set_mode(ViewMode.TWO_PAGE)
    assert view.spreads() == [(None, 1), (2, 3), (4, 5)]
    assert view.slot(1).rect.left() > view.content_size().width() / 2 - 1  # in dreapta


# --- B-010…B-013 ----------------------------------------------------------------------


def test_T_B010_1_zoom_steps_and_limits(view):
    view.set_zoom(100)
    view.zoom_in()
    assert view.zoom == 125 and view.fit is FitMode.NONE
    view.zoom_out()
    view.zoom_out()
    assert view.zoom == 75
    view.set_zoom(99999)
    assert view.zoom == ZOOM_MAX and not view.can_zoom_in()
    view.set_zoom(1)
    assert view.zoom == ZOOM_MIN and not view.can_zoom_out()


def test_T_B011_B013_fit_modes(view):
    view.set_mode(ViewMode.ONE_PAGE)
    view.set_fit(FitMode.FIT_WIDTH)
    page = view.slot(1).rect
    available = view.viewport().width() - 32
    assert available * 0.99 - 1 <= page.width() <= available  # zoom-ul e un procent intreg
    view.set_fit(FitMode.BEST_FIT)
    page = view.slot(1).rect
    assert page.height() <= view.viewport().height() - 32 + 1
    assert page.width() <= view.viewport().width()
    view.set_fit(FitMode.ACTUAL_SIZE)
    assert view.zoom == round(100 * view.logicalDpiX() / 96)


# --- B-014…B-018 ----------------------------------------------------------------------


def test_T_B014_B017_navigation(view):
    pages = []
    view.page_changed.connect(pages.append)
    assert not view.go_to_page(0) and not view.go_to_page(6)  # B-014: in afara intervalului
    assert view.go_to_page(3) and view.current_page == 3
    view.next_page()
    assert view.current_page == 4
    view.previous_page()
    view.previous_page()
    assert view.current_page == 2
    view.last_page()
    assert view.current_page == 5 and not view.can_go_next()
    view.first_page()
    assert view.current_page == 1 and not view.can_go_previous()
    assert pages[-1] == 1
    view.set_mode(ViewMode.TWO_PAGE)
    view.next_page()
    assert view.current_page == 3  # pe perechi


def test_T_B018_1_history_back_and_forward_with_zoom(view):
    view.set_zoom(100)
    view.go_to_page(3)
    view.set_zoom(200)
    view.go_to_page(5)
    view.back()
    assert (view.current_page, view.zoom) == (3, 100)
    view.back()
    assert view.current_page == 1
    view.forward()
    view.forward()
    assert (view.current_page, view.zoom) == (5, 200)
    assert not view.can_go_forward()
    for i in range(80):
        view.go_to_page(1 + i % 5)
    assert len(view.history()) == HISTORY_LIMIT


# --- B-300…B-302 ----------------------------------------------------------------------


def test_T_B300_B302_tools(view):
    assert view.tool is Tool.SELECT
    view.setFocus()
    QTest.keyPress(view, Qt.Key.Key_Space)
    assert view.active_tool is Tool.HAND  # B-302: spatiu = Hand temporar
    QTest.keyRelease(view, Qt.Key.Key_Space)
    assert view.active_tool is Tool.SELECT
    view.set_zoom(300)
    view.set_tool(Tool.HAND)
    start = view.verticalScrollBar().value()
    QTest.mousePress(view.canvas, Qt.MouseButton.LeftButton, pos=QPoint(200, 300))
    QTest.mouseMove(view.canvas, QPoint(200, 150))
    QTest.mouseRelease(view.canvas, Qt.MouseButton.LeftButton, pos=QPoint(200, 150))
    assert view.verticalScrollBar().value() > start  # pagina s-a mutat in sus


def test_T_B300_1_select_click_reports_the_page_point(view, qtbot):
    view.set_zoom(100)
    view.set_mode(ViewMode.ONE_PAGE)
    slot = view.slot(1).rect
    with qtbot.waitSignal(view.page_clicked) as blocker:
        QTest.mouseClick(view.canvas, Qt.MouseButton.LeftButton,
                         pos=QPoint(int(slot.left() + 96), int(slot.top() + 48)))
    page, x, y = blocker.args
    assert page == 1
    assert (x, y) == pytest.approx((72, 36), abs=1.5)  # 96 px la 100% = 72 pt


# --- coordonatele si rotatia ----------------------------------------------------------


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotation_round_trip(rotation):
    for x, y in ((0, 0), (100, 20), (595, 842)):
        dx, dy = to_display(rotation, 595, 842, x, y)
        assert from_display(rotation, 595, 842, dx, dy) == pytest.approx((x, y))


def test_page_to_view_on_rotated_page(qtbot, tmp_path):
    path = text_pdf(tmp_path / "rotit.pdf", [["a"]])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.pages[0].obj.Rotate = 90
        pdf.save(path)
    with PdfDocument.open(path) as rotated:
        v = make_view(qtbot, rotated)
        v.set_zoom(100)
        slot = v.slot(1).rect
        assert slot.width() > slot.height()  # afisata in latime
        box = v.page_to_view(1, Rect(0, 0, 100, 50))  # coltul de sus-stanga al paginii
        assert box.right() == pytest.approx(slot.right(), abs=0.5)  # ajunge in dreapta-sus
        assert box.top() == pytest.approx(slot.top(), abs=0.5)
        hit = v.view_to_page(QPointF(slot.right() - 1, slot.top() + 1))
        assert hit[0] == 1 and hit[1] < 5 and hit[2] < 5
