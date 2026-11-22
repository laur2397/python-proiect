"""Modul `Organize Pages` din PDF Editor (faza 8, pasul 8.3): E-001…E-009, E-018,
E-033, E-034, E-036, E-037, E-039, E-040, E-100…E-107."""

from __future__ import annotations

import os

import pikepdf
import pytest
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.core.pdf.document import PdfDocument
from app.gui.pdf_editor import LATER, RIBBON_TABS, UNDO_LIMIT, PdfEditorWindow
from app.gui.pdf_organize import ZOOM_MAX, ZOOM_MIN, ZOOM_STEP


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    w.open_path(text_pdf(tmp_path / "dosar.pdf", [[f"Pagina {n}"] for n in range(1, 6)]))
    yield w
    for extra in list(w.spawned_windows):
        extra.close()
    w.close()


def organize(window):
    window.ribbon_tabs.setCurrentIndex(list(RIBBON_TABS).index("organize"))
    view = window.current().organize
    view.render_all()
    return view


def texts(window):
    document = window.current().document
    return [document.extract_text(n).strip() for n in range(1, document.page_count + 1)]


def menu_action(menu, name):
    [action] = [a for a in menu.actions() if a.objectName() == f"organize_menu_{name}"]
    return action


# --- E-001, E-100, E-101, E-002, E-003, E-102 --------------------------------------------


def test_T_E001_organize_tab_shows_the_thumbnail_grid(window):
    entry = window.current()
    assert entry.page.currentWidget() is entry.view
    view = organize(window)
    assert window.organize_mode and entry.page.currentWidget() is view
    assert view.grid.count() == 5
    assert view.selected_pages() == [1]  # pagina curenta
    window.ribbon_tabs.setCurrentIndex(0)
    assert entry.page.currentWidget() is entry.view


def test_T_E002_E003_E102_selection_click_ctrl_shift_and_frame(window):
    view = organize(window)
    grid = view.grid
    rect = [grid.visualRect(grid.model().index(r, 0)) for r in range(5)]
    QTest.mouseClick(grid.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, rect[1].center())
    assert view.selected_pages() == [2]
    QTest.mouseClick(grid.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.ControlModifier, rect[3].center())
    assert view.selected_pages() == [2, 4]
    QTest.mouseClick(grid.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.ShiftModifier, rect[4].center())
    assert view.selected_pages() == [2, 4, 5]  # intervalul de la ultimul clic, adaugat
    assert grid.isSelectionRectVisible()  # E-102: cadrul de selectie
    assert grid.selectionMode() == grid.SelectionMode.ExtendedSelection


# --- E-004, E-103 ------------------------------------------------------------------------


def test_T_E004_E103_selected_pages_field(window):
    view = organize(window)
    messages = []
    window.show_message = messages.append
    assert window.apply_page_range("2, 4-5") == [2, 4, 5]
    assert view.selected_pages() == [2, 4, 5]
    assert window.apply_page_range("Paginile pare") == [2, 4]  # din lista
    assert window.apply_page_range("1, 7-9") == [1] and "7-9" in messages[-1]
    assert window.apply_page_range("abc") == [] and len(messages) == 2
    view.select_pages([3, 5])  # E-103: campul urmeaza selectia cu mouse-ul
    assert window.page_range.currentText() == "3, 5"


# --- E-005…E-009, E-104, E-040 -----------------------------------------------------------


def test_T_E005_delete_pages_from_the_grid_and_undo(window):
    view = organize(window)
    view.select_pages([2, 3])
    window.actions["delete_pages"].trigger()  # Ctrl+Backspace
    assert texts(window) == ["Pagina 1", "Pagina 4", "Pagina 5"]
    assert view.grid.count() == 3
    window.undo()  # E-040
    assert texts(window)[1] == "Pagina 2" and view.grid.count() == 5


def test_T_E005_the_last_page_cannot_be_deleted(window):
    view = organize(window)
    messages = []
    window.show_message = messages.append
    view.select_pages([1, 2, 3, 4, 5])
    window.actions["delete"].trigger()  # Del
    assert window.current().document.page_count == 5 and messages


def test_T_E006_E007_E008_rotate_and_correct_orientation(window, monkeypatch):
    view = organize(window)
    view.select_pages([2])
    window.actions["rotate_right"].trigger()
    window.actions["rotate_left"].trigger()
    window.actions["rotate_left"].trigger()
    assert window.current().document.page_rotation(2) == 270
    from app.core.pdf import organize as core

    monkeypatch.setattr(core, "_detect_orientation", lambda image: 90)
    window.actions["correct_orientation"].trigger()
    assert window.current().document.page_rotation(2) == 0
    messages = []
    window.show_message = messages.append
    monkeypatch.setattr(core, "_detect_orientation", lambda image: 0)
    window.actions["correct_orientation"].trigger()
    assert messages  # nimic de rotit


def test_T_E009_E104_hover_toolbar(window):
    view = organize(window)
    grid = view.grid
    rect = grid.visualRect(grid.model().index(2, 0))
    view._hover(2)
    bar = view.hover_bar
    assert bar.isVisible() and bar.page == 3
    assert list(bar.buttons) == ["delete", "rotate_left", "rotate_right"]
    assert bar.geometry().right() <= rect.right() and bar.geometry().top() >= rect.top()
    bar.buttons["rotate_right"].click()
    assert window.current().document.page_rotation(3) == 90
    view._hover(0)
    view.hover_bar.buttons["delete"].click()
    assert texts(window)[0] == "Pagina 2"


def test_T_E040_undo_keeps_at_least_50_steps(window):
    assert UNDO_LIMIT >= 50
    organize(window)
    for _ in range(52):
        window.rotate_pages(90, [1])
    assert len(window.current().undo) == UNDO_LIMIT


# --- E-018, E-105, E-106 -----------------------------------------------------------------


def test_T_E018_drag_and_drop_reorders(window):
    view = organize(window)
    grid = view.grid
    first = grid.visualRect(grid.model().index(0, 0))
    assert grid.target_at(QPoint(first.left() + 2, first.center().y())) == 1
    assert grid.target_at(QPoint(first.right() - 2, first.center().y())) == 2
    assert grid.target_at(QPoint(grid.viewport().width() - 1,
                                 grid.viewport().height() - 1)) == 6
    grid.drop_target = 1  # E-106: indicatorul de inserare
    assert grid.indicator_rect() is not None
    grid.drop_target = None
    view.select_pages([4, 5])
    view.move_requested.emit([4, 5], 1)
    assert texts(window)[:2] == ["Pagina 4", "Pagina 5"]
    assert view.selected_pages() == [1, 2]


# --- E-039, E-107 ------------------------------------------------------------------------


def test_T_E039_E107_thumbnail_zoom_slider(window):
    view = organize(window)
    start = view.thumb_width
    view.zoom_in.click()
    assert view.thumb_width == start + ZOOM_STEP
    view.slider.setValue(ZOOM_MAX)
    assert not view.zoom_in.isEnabled()
    view.slider.setValue(ZOOM_MIN)
    assert not view.zoom_out.isEnabled() and view.thumb_width == ZOOM_MIN
    view.render_all()
    assert not view.grid.item(0).icon().isNull()


# --- E-033, E-034, E-036, E-037, B-308 ---------------------------------------------------


def test_T_E036_create_pdf_from_selected_pages_opens_a_new_window(window):
    view = organize(window)
    view.select_pages([2, 4])
    menu_action(window.grid_menu, "create_pdf").trigger()
    [new] = window.spawned_windows
    document = new.current().document
    assert document.path is None and document.page_count == 2
    assert window.current().document.page_count == 5


def test_T_E037_save_as_selected_pages(window, tmp_path, monkeypatch):
    target = tmp_path / "parte.pdf"
    monkeypatch.setattr(PdfEditorWindow, "ask_save_path", lambda self, d, suffix=".pdf": target)
    view = organize(window)
    view.select_pages([1, 3, 5])
    menu_action(window.grid_menu, "save_selected").trigger()
    with pikepdf.open(target) as pdf:
        assert len(pdf.pages) == 3


def test_T_E034_send_selected_pages_to_ocr_editor(window):
    sent = []
    window.ocr_editor_requested.connect(sent.append)
    window.pages_panel.list.clearSelection()
    window.pages_panel.list.item(1).setSelected(True)
    menu_action(window.panel_menu, "send_selected").trigger()
    with PdfDocument.open(sent[0][0]) as doc:
        assert doc.page_count == 1 and doc.extract_text(1).strip() == "Pagina 2"


def test_T_E033_recognize_selected_pages(window, monkeypatch):
    seen = {}

    def store(self, *, pages=None, context=None, progress=None, **kw):
        seen["pages"] = pages
        return 0

    monkeypatch.setattr(PdfDocument, "recognize_and_store", store)
    view = organize(window)
    view.select_pages([2, 3])
    [action] = [a for a in window.recognize_menu.actions()
                if a.text() == "Recunoaște paginile selectate"]
    action.trigger()
    assert seen["pages"] == [2, 3]


def test_pages_panel_rotation_and_menu_are_enabled(window):
    panel = window.pages_panel
    assert panel.actions["rotate_left"].isEnabled() and panel.more.isEnabled()
    panel.list.clearSelection()
    panel.list.item(4).setSelected(True)
    panel.actions["rotate_left"].trigger()
    assert window.current().document.page_rotation(5) == 270
    for key in ("delete_pages", "rotate_left", "rotate_right", "correct_orientation",
                "selected_pages"):
        assert key not in LATER
