"""Selectia de text si zona de copiat din PDF Editor (faza 7, pasul 7.8b):
C-040…C-049, C-112…C-115."""

from __future__ import annotations

import os

import pytest
from _pdftext import make_text_pdf
from PIL import Image
from test_pdf_copy import TABLE_AREA, table_pdf
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.context import AppContext
from app.core.model import Rect
from app.core.paths import AppPaths
from app.gui.pdf_editor import PdfEditorWindow
from app.gui.pdf_selection import TABLE_TOOLS


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx):
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    yield w
    w.close()


def open_doc(window, path, zoom=75):
    entry = window.open_path(path)
    entry.view.set_zoom(zoom)
    entry.view.go_to_page(1)
    QApplication.processEvents()
    return entry


def at(view, page, x, y):
    """Punctul (puncte, sus-stanga) pe fereastra vizibila a vizualizarii."""
    box = view.page_to_view(page, Rect(x, y, 0, 0))
    offset = QPointF(view.horizontalScrollBar().value(), view.verticalScrollBar().value())
    point = box.topLeft() - offset
    return QPoint(int(point.x()), int(point.y()))


def drag(view, start, end):
    viewport = view.viewport()
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(viewport, QPoint((start.x() + end.x()) // 2, (start.y() + end.y()) // 2))
    QTest.mouseMove(viewport, end)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)


@pytest.fixture
def doc_path(tmp_path):
    return text_pdf(tmp_path / "dosar.pdf", [
        ["Cerere de finantare", "Bugetul total: 1200 lei"], ["Anexa 2: buget detaliat"]])


# --- C-044 ----------------------------------------------------------------------------


def test_T_C044_1_text_selection_and_copy(window, doc_path):
    entry = open_doc(window, doc_path)
    view, selection = entry.view, entry.selection
    first = next(h for h in entry.document.search("Bugetul") if h.source == "text").rect
    last = next(h for h in entry.document.search("1200") if h.source == "text").rect
    drag(view, at(view, 1, first.x + 1, first.y + first.h / 2),
         at(view, 1, last.x + last.w - 1, last.y + last.h / 2))
    assert selection.mode == "text"
    assert selection.selected_text() == "Bugetul total: 1200"
    assert window.actions["copy"].isEnabled()
    window.actions["copy"].trigger()  # Ctrl+C
    assert QApplication.clipboard().text() == "Bugetul total: 1200"


def test_T_C044_2_select_all_spans_pages(window, doc_path):
    entry = open_doc(window, doc_path)
    window.actions["select_all"].trigger()
    text = entry.selection.selected_text()
    assert text.startswith("Cerere de finantare") and text.endswith("buget detaliat")


def test_click_without_drag_is_a_click(window, doc_path, qtbot):
    entry = open_doc(window, doc_path)
    with qtbot.waitSignal(entry.view.page_clicked):
        QTest.mouseClick(entry.view.viewport(), Qt.MouseButton.LeftButton,
                         pos=at(entry.view, 1, 400, 400))
    assert not entry.selection.has_selection()


# --- C-040, C-042, C-043, C-112 -------------------------------------------------------


def test_T_C040_1_area_on_one_page_and_copy_as_image(window, doc_path):
    entry = open_doc(window, doc_path)
    view, selection = entry.view, entry.selection
    drag(view, at(view, 1, 300, 400), at(view, 1, 450, 500))
    assert selection.mode == "area" and selection.area[0] == 1
    _page, rect = selection.area
    assert (rect.x, rect.y) == pytest.approx((300, 400), abs=2)
    assert selection.area_button.isVisible()  # C-041
    assert window.actions["copy_area_text"].isEnabled()
    window.actions["copy"].trigger()  # C-042: Ctrl+C pe o zona = imagine
    image = QApplication.clipboard().image()
    assert not image.isNull()
    assert abs(image.width() - rect.w * 300 / 72) <= 3


def test_T_C040_2_area_across_pages_is_not_created(window, doc_path):
    entry = open_doc(window, doc_path, zoom=25)
    view = entry.view
    assert view.slot(2) is not None
    drag(view, at(view, 1, 300, 800), at(view, 2, 300, 100))
    assert entry.selection.area is None and not entry.selection.has_selection()


def test_T_C043_1_copy_area_as_text(window, doc_path):
    entry = open_doc(window, doc_path)
    line = next(h for h in entry.document.search("Bugetul") if h.source == "text").rect
    entry.selection.set_area(1, Rect(60, line.y - 2, 400, line.h + 4))
    window.actions["copy_area_text"].trigger()  # Ctrl+Shift+C
    assert QApplication.clipboard().text() == "Bugetul total: 1200 lei"


def test_T_C049_1_mismatch_warning_is_shown(window, tmp_path, monkeypatch):
    path = make_text_pdf(tmp_path / "img.pdf", ["Text"], image=Image.new("L", (200, 100), 30),
                         image_box=(72, 300, 300, 150))
    entry = open_doc(window, path)
    messages = []
    monkeypatch.setattr(PdfEditorWindow, "show_message",
                        lambda self, text: messages.append(text))
    entry.selection.set_area(1, Rect(100, 420, 100, 60))
    window.actions["copy_area_text"].trigger()
    assert messages and "limbile de recunoaștere" in messages[0]


# --- C-045…C-047, C-113…C-115 ---------------------------------------------------------


def test_T_C045_1_table_mode_and_copy(window, tmp_path):
    path = table_pdf(tmp_path / "tabel.pdf")
    original = path.read_bytes()
    entry = open_doc(window, path)
    selection = entry.selection
    selection.set_area(1, TABLE_AREA)
    window.actions["copy_area_table"].trigger()  # Ctrl+Alt+C: intra in modul tabel
    assert selection.mode == "table"
    assert selection.table_bar.isVisible()  # C-115
    assert [a.objectName() for a in selection.table_bar.actions()] == \
        [f"table_{k}" for k in TABLE_TOOLS]  # C-114: noua comenzi
    window.actions["copy_area_table"].trigger()  # a doua oara: copiaza
    mime = QApplication.clipboard().mimeData()
    assert mime.text() == "Nume\tSuma\nAna\t1200"
    assert "<table>" in mime.html()
    assert path.read_bytes() == original  # C-047


def test_T_C046_1_edit_the_grid_before_copying(window, tmp_path):
    entry = open_doc(window, table_pdf(tmp_path / "tabel.pdf"))
    selection, view = entry.selection, entry.view
    selection.set_area(1, TABLE_AREA)
    selection.start_table()
    assert (selection.table.table.rows, selection.table.table.cols) == (2, 2)
    selection.table_actions["select_cells"].trigger()  # unirea primului rand
    for x in (100, 300):
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=at(view, 1, x, 270))
    assert len(selection.selected_cells) == 2
    selection.table_actions["merge_cells"].trigger()
    assert selection.table.cell_texts()[0] == ["Nume Suma", ""]
    selection.table_actions["analyze"].trigger()  # structura detectata din nou
    assert selection.table.cell_texts() == [["Nume", "Suma"], ["Ana", "1200"]]
    selection.table_actions["delete_separators"].trigger()  # separatorul de la x = 222
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=at(view, 1, 222, 320))
    assert selection.table.table.cols == 1
    selection.table_actions["add_vertical"].trigger()  # si inapoi
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=at(view, 1, 222, 320))
    assert selection.table.table.cols == 2
    assert selection.table.cell_texts() == [["Nume", "Suma"], ["Ana", "1200"]]
