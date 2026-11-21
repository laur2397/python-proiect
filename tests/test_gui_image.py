"""Faza 6b, pasul 6b.2: panourile Pages, Image si Zoom; zonele cu mouse-ul
(J-403…J-418, M-009…M-011, M-015, M-029, M-100…M-111)."""

from __future__ import annotations

import os

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from _pdfgen import make_pdf
from _pdftext import make_text_pdf
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QToolBar

from app.core.context import AppContext
from app.core.layout.areas import AreaEditor
from app.core.model import AreaType, AutoProcessMode, PageStatus, Rect
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.gui import zones
from app.gui.i18n import tr_error
from app.gui.image_panel import ImagePanel, has_text_layer
from app.gui.main_window import MainWindow
from app.gui.pages_panel import PANEL_WIDTH, STATUS_MARKS, tooltip

CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
ALT = Qt.KeyboardModifier.AltModifier
NONE = Qt.KeyboardModifier.NoModifier


# =============================================================================
# Geometria (fara Qt)
# =============================================================================


def test_T_M009_1_modifier_shortcuts():
    assert zones.type_for_modifiers(True, True, False) is AreaType.TEXT
    assert zones.type_for_modifiers(False, True, True) is AreaType.PICTURE
    assert zones.type_for_modifiers(True, False, True) is AreaType.TABLE
    assert zones.type_for_modifiers(True, True, True) is AreaType.BACKGROUND_PICTURE
    assert zones.type_for_modifiers(True, False, False) is None  # Ctrl = selectie multipla


def test_T_M106_1_any_drag_direction():
    expected = Rect(10, 20, 90, 80)
    for a, b in (((10, 20), (100, 100)), ((100, 100), (10, 20)), ((100, 20), (10, 100)),
                 ((10, 100), (100, 20))):
        assert zones.normalize(*a, *b) == expected
    assert zones.clamp(Rect(-5, -5, 50, 50), 30, 40) == Rect(0, 0, 30, 40)


def test_T_M011_1_handles_and_resize():
    rect = Rect(100, 100, 200, 100)
    assert set(zones.handles(rect)) == set(zones.HANDLE_NAMES)  # M-104: 8 manere
    assert zones.hit_handle(rect, 301, 199, 3) == "bottom_right"
    assert zones.hit_handle(rect, 200, 150, 3) is None
    assert zones.resize(rect, "right", 350, 0) == Rect(100, 100, 250, 100)
    assert zones.resize(rect, "top_left", 50, 60) == Rect(50, 60, 250, 140)
    assert zones.resize(rect, "left", 400, 0) == Rect(300, 100, 100, 100)  # trecut peste


def test_T_M010_1_tab_cycles():
    assert zones.next_index(3, None) == 0
    assert zones.next_index(3, 2) == 0
    assert zones.next_index(3, 0, backwards=True) == 2
    assert zones.next_index(0, None) is None


def test_T_M111_1_reorder_session():
    session = zones.ReorderSession([1, 2, 3])
    assert session.click(3) == [3, 1, 2]  # numerele se recalculeaza la fiecare clic
    assert session.click(3) == [3, 1, 2]
    assert session.click(1) == [3, 1, 2] and not session.done
    session.click(2)
    assert session.done


def test_T_M100_1_colors_come_from_settings(ctx):
    """M-100, M-101: culorile sunt setari (X-165), nu valori in cod."""
    settings = ctx.settings
    assert zones.area_style(settings, AreaType.TEXT) == (settings.get("areas.color.text"), 2)
    settings.set("areas.color.text", "#123456")
    assert zones.area_style(settings, AreaType.TEXT)[0].lower() == "#123456"


# =============================================================================
# Fereastra
# =============================================================================


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def page_images(tmp_path, n=2):
    paths = []
    for i in range(n):
        Image.new("L", (600, 800), 255).save(tmp_path / f"p{i + 1}.png", dpi=(300, 300))
        paths.append(tmp_path / f"p{i + 1}.png")
    return paths


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    project = OcrProject.create(context=ctx)
    project.add_images(page_images(tmp_path), auto_process=AutoProcessMode.NONE)
    w = MainWindow(ctx, project)
    qtbot.addWidget(w)
    w.resize(1400, 1100)
    w.show()
    w.image_view.set_zoom(100)
    w.image_view.horizontalScrollBar().setValue(0)
    w.image_view.verticalScrollBar().setValue(0)
    yield w
    project.close()


def at(view, x, y) -> QPoint:
    return view.mapFromScene(QPointF(x, y))


def drag(qtbot, view, start, end, modifiers=NONE):
    vp = view.viewport()
    qtbot.mousePress(vp, Qt.MouseButton.LeftButton, modifiers, at(view, *start))
    qtbot.mouseMove(vp, at(view, (start[0] + end[0]) / 2, (start[1] + end[1]) / 2))
    qtbot.mouseMove(vp, at(view, *end))
    qtbot.mouseRelease(vp, Qt.MouseButton.LeftButton, modifiers, at(view, *end))


def click(qtbot, view, point, modifiers=NONE):
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, modifiers, at(view, *point))


def areas(window):
    return sorted(window.project.page(window.current).areas, key=lambda a: a.order_index)


def toolbar_names(parent, name):
    bar = parent.findChild(QToolBar, name)
    return [a.objectName() for a in bar.actions() if a.objectName()]


def test_T_J410_1_and_J411_1_image_toolbars(window):
    panel = window.image_panel
    assert toolbar_names(panel, "image_toolbar_1") == [
        "image_edit_image", "image_save_page", "image_select", "image_hand", "image_delete",
        "image_reorder"]
    assert toolbar_names(panel, "image_toolbar_2")[:7] == [
        "image_recognize_page", "image_analyze_page", "image_tool.text", "image_tool.picture",
        "image_tool.table", "image_tool.background_picture", "image_tool.recognition"]


def test_T_J412_1_active_tool_is_checked(window):
    panel = window.image_panel
    assert panel.actions["select"].isChecked()
    panel.actions["tool.table"].trigger()
    assert panel.actions["tool.table"].isChecked() and not panel.actions["select"].isChecked()
    assert window.image_view.tool is AreaType.TABLE
    # M-105: cursorul `+` la desenare
    assert window.image_view.viewport().cursor().shape() == Qt.CursorShape.CrossCursor


def test_draw_with_the_area_tool(window, qtbot):
    window.image_panel.actions["tool.text"].trigger()
    drag(qtbot, window.image_view, (300, 300), (50, 40))  # M-106: de jos-dreapta in sus
    (area,) = areas(window)
    assert area.area_type is AreaType.TEXT and area.bbox == Rect(50, 40, 250, 260)
    assert window.image_view.selected == [area.id]


def test_T_M009_2_draw_with_modifiers_without_tool(window, qtbot):
    view = window.image_view
    drag(qtbot, view, (20, 20), (200, 100), CTRL | SHIFT)
    drag(qtbot, view, (20, 150), (200, 250), ALT | SHIFT)
    drag(qtbot, view, (20, 300), (200, 400), CTRL | ALT)
    assert [a.area_type for a in areas(window)] == [AreaType.TEXT, AreaType.PICTURE,
                                                    AreaType.TABLE]


def test_core_errors_become_translated_messages(window, qtbot):
    """Regulile raman in nucleu (M-008 prea mica, M-034 suprapunere); GUI-ul
    arata mesajul tradus (Y-013)."""
    messages = []
    window.image_view.message.connect(messages.append)
    window.image_panel.actions["tool.text"].trigger()
    drag(qtbot, window.image_view, (10, 10), (13, 13))
    assert areas(window) == [] and messages[-1] == "Zona e prea mică"
    drag(qtbot, window.image_view, (100, 100), (300, 300))
    drag(qtbot, window.image_view, (200, 200), (400, 400))
    assert len(areas(window)) == 1 and messages[-1] == "Zona se suprapune peste altă zonă"
    assert window.statusBar().currentMessage() == messages[-1]


def test_T_M015_1_ctrl_click_multiple_selection(window, qtbot):
    editor = AreaEditor(window.project)
    page = window.project.page(1)
    a = editor.create(page, zones.rect_points(Rect(20, 20, 100, 100)), AreaType.TEXT)
    b = editor.create(page, zones.rect_points(Rect(200, 20, 100, 100)), AreaType.TEXT)
    window.refresh()
    view = window.image_view
    click(qtbot, view, (50, 50))
    assert view.selected == [a.id]
    click(qtbot, view, (250, 50), CTRL)
    assert view.selected == [a.id, b.id]
    click(qtbot, view, (50, 50), CTRL)
    assert view.selected == [b.id]
    click(qtbot, view, (500, 700))
    assert view.selected == []


def test_T_M010_2_tab_walks_the_areas(window, qtbot):
    editor = AreaEditor(window.project)
    page = window.project.page(1)
    ids = [editor.create(page, zones.rect_points(Rect(20 + 150 * i, 20, 100, 100)),
                         AreaType.TEXT).id for i in range(3)]
    window.refresh()
    view = window.image_view
    view.setFocus()
    for expected in (*ids, ids[0]):
        qtbot.keyClick(view, Qt.Key.Key_Tab)
        assert view.selected == [expected]
    qtbot.keyClick(view, Qt.Key.Key_Backtab)
    assert view.selected == [ids[2]]


def test_T_M011_2_drag_a_handle_resizes(window, qtbot):
    editor = AreaEditor(window.project)
    area = editor.create(window.project.page(1), zones.rect_points(Rect(100, 100, 200, 100)),
                         AreaType.TEXT)
    window.refresh()
    view = window.image_view
    view.select([area.id])
    drag(qtbot, view, (300, 200), (400, 260))  # coltul din dreapta-jos
    assert areas(window)[0].bbox == Rect(100, 100, 300, 160)


def test_move_and_delete_selected(window, qtbot):
    editor = AreaEditor(window.project)
    editor.create(window.project.page(1), zones.rect_points(Rect(100, 100, 100, 100)),
                  AreaType.PICTURE)
    window.refresh()
    view = window.image_view
    drag(qtbot, view, (150, 150), (180, 200))
    assert areas(window)[0].bbox == Rect(130, 150, 100, 100)
    view.setFocus()
    qtbot.keyClick(view, Qt.Key.Key_Delete)
    assert areas(window) == []
    window.actions["undo"].trigger()  # J-041: operatiile intra in istoric
    assert len(areas(window)) == 1


def test_T_M107_1_add_area_part_makes_a_polygon(window, qtbot):
    editor = AreaEditor(window.project)
    area = editor.create(window.project.page(1), zones.rect_points(Rect(100, 100, 200, 100)),
                         AreaType.TEXT)
    window.refresh()
    view = window.image_view
    view.select([area.id])
    window.image_panel.actions["add_part"].trigger()
    drag(qtbot, view, (100, 200), (150, 300))
    assert areas(window)[0].is_polygon


def test_T_M111_2_reorder_mode(window, qtbot):
    editor = AreaEditor(window.project)
    page = window.project.page(1)
    ids = [editor.create(page, zones.rect_points(Rect(20, 20 + 150 * i, 100, 100)),
                         AreaType.TEXT).id for i in range(3)]
    window.refresh()
    panel, view = window.image_panel, window.image_view
    panel.actions["reorder"].setChecked(True)
    assert view.reorder_session is not None
    click(qtbot, view, (50, 350))  # a treia zona devine prima
    assert [a.id for a in areas(window)] == [ids[2], ids[0], ids[1]]
    click(qtbot, view, (50, 200))
    click(qtbot, view, (50, 50))
    assert [a.id for a in areas(window)] == [ids[2], ids[1], ids[0]]
    assert view.reorder_session is None  # toate zonele apasate: modul se inchide


def test_T_M102_1_area_is_drawn_translucent_in_its_color(qtbot, ctx, tmp_path):
    project = OcrProject.create(context=ctx)
    project.add_images(page_images(tmp_path, 1), auto_process=AutoProcessMode.NONE)
    project.settings().set("areas.color.picture", "#0000FF")
    AreaEditor(project).create(project.page(1), zones.rect_points(Rect(40, 40, 120, 120)),
                               AreaType.PICTURE)
    panel = ImagePanel(project)
    qtbot.addWidget(panel)
    panel.resize(900, 1000)
    panel.show()
    panel.set_page(project.page(1))
    view = panel.view
    view.set_zoom(100)
    view.horizontalScrollBar().setValue(0)
    view.verticalScrollBar().setValue(0)
    image = view.viewport().grab().toImage()
    inside = QColor(image.pixel(at(view, 120, 120)))
    outside = QColor(image.pixel(at(view, 200, 300)))
    assert outside.blue() == outside.red() == 255  # imaginea alba, neatinsa
    assert inside.blue() > inside.red() + 10 and inside.red() > 150  # albastru translucid
    panel.hide()
    project.close()


def test_the_image_gets_the_largest_share(window, qtbot):
    """Pages ingust (J-403); imaginea are cel mai mult loc."""
    qtbot.waitUntil(lambda: window.image_panel.width() > window.width() * 0.35)
    assert window.pages_dock.width() < window.image_panel.width()
    assert window.text_dock.width() < window.image_panel.width()


def test_T_M029_1_property_bar_scrolls_with_arrows(window, qtbot):
    strip = window.image_panel.area_strip
    strip.area.widget().setMinimumWidth(2000)
    qtbot.waitUntil(lambda: strip.narrow)
    assert not strip.left.isHidden() and not strip.right.isHidden()
    bar = strip.area.horizontalScrollBar()
    strip.right.click()
    assert bar.value() > 0


def test_T_J414_1_and_J415_1_properties(window):
    tabs = window.image_panel.properties
    assert [tabs.tabText(i) for i in range(tabs.count())] == ["Proprietățile zonei",
                                                              "Proprietățile imaginii"]
    info = window.image_panel.image_info
    assert info["size"].text() == "600 x 800 pixeli"
    assert info["resolution"].text() == "300 dpi"
    assert info["format"].text() == "PNG"
    assert info["source"].text().endswith("p1.png")


def test_area_type_combo_changes_the_type(window):
    editor = AreaEditor(window.project)
    area = editor.create(window.project.page(1), zones.rect_points(Rect(10, 10, 100, 100)),
                         AreaType.TEXT)
    window.refresh()
    window.image_view.select([area.id])
    combo = window.image_panel.type_combo
    index = combo.findData(AreaType.PICTURE.value)
    combo.setCurrentIndex(index)
    combo.activated.emit(index)
    assert areas(window)[0].area_type is AreaType.PICTURE


def test_T_J416_1_zoom_and_fit(window):
    panel, view = window.image_panel, window.image_view
    panel.actions["zoom_in"].trigger()
    assert view.zoom == 150 and panel.zoom_combo.currentText() == "150%"
    panel.actions["zoom_out"].trigger()
    panel.actions["zoom_out"].trigger()
    assert view.zoom == 75
    panel.actions["fit_width"].trigger()
    width = view.zoom
    panel.actions["fit_height"].trigger()
    height = view.zoom
    panel.actions["fit_page"].trigger()
    assert view.zoom == min(width, height)


def test_T_J418_1_zoom_pane_has_its_own_zoom(window):
    window.image_view.set_zoom(50)
    assert window.zoom_panel.zoom == 200
    window.zoom_panel.zoom_combo.setCurrentIndex(window.zoom_panel.zoom_combo.findData(400))
    assert window.zoom_panel.zoom == 400 and window.image_view.zoom == 50
    window.image_panel.zoom_pane_toggle.setChecked(False)
    assert not window.zoom_dock.isVisible()


def test_T_J413_1_pdf_band_only_for_pdf_with_text_layer(qtbot, ctx, tmp_path):
    project = OcrProject.create(context=ctx)
    project.add_images([make_text_pdf(tmp_path / "t.pdf", ["Factura 12"]),
                        make_pdf(tmp_path / "i.pdf", [(595, 842, (0.5, 0.5, 0.5))])],
                       auto_process=AutoProcessMode.NONE)
    assert has_text_layer(project.page(1)) and not has_text_layer(project.page(2))
    panel = ImagePanel(project)
    qtbot.addWidget(panel)
    panel.set_page(project.page(1))
    assert not panel.pdf_band.isHidden()
    panel.pdf_mode_actions["ocr"].trigger()
    assert project.settings().get("ocr.pdf_mode") == "ocr"  # X-060
    panel.set_page(project.page(2))
    assert panel.pdf_band.isHidden()
    project.close()


# =============================================================================
# Panoul Pages (J-403…J-408)
# =============================================================================


def test_T_J403_1_and_J404_1_pages_panel(window):
    panel = window.pages_panel
    assert panel.minimumWidth() == PANEL_WIDTH
    assert toolbar_names(panel, "pages_toolbar")[:4] == [
        "pages_save", "pages_delete", "pages_rotate_left", "pages_rotate_right"]


def test_T_J405_1_status_badges_cover_every_state():
    assert set(STATUS_MARKS) == set(PageStatus)


def test_T_J407_1_tooltip_has_status_and_source(window):
    page = window.project.page(2)
    assert tooltip(page) == "Neprocesată\nSursa: p2.png"
    assert window.pages_list.item(1).toolTip() == tooltip(page)


def test_pages_rotate_and_delete(window):
    panel = window.pages_panel
    window.pages_list.setCurrentRow(1)
    panel.actions["rotate_right"].trigger()
    assert window.project.page(2).rotation == 90
    assert window.project.page(2).width_px == 800
    panel.actions["delete"].trigger()
    assert len(window.project.pages) == 1 and window.page_counter.text() == "[ 1 / 1 ]"
    messages = []
    panel.message.connect(messages.append)
    panel.actions["delete"].trigger()  # ultima pagina: LastPageError din nucleu
    assert len(window.project.pages) == 1
    assert messages == ["Proiectul trebuie să păstreze cel puțin o pagină"]


def test_page_change_shows_the_image(window):
    window.pages_list.setCurrentRow(1)
    assert window.image_view.page.page_number == 2
    assert window.image_view.scene().sceneRect().width() == 600


def test_unknown_error_code_has_a_generic_message():
    class Odd(Exception):
        code = "SOMETHING_NEW"
        params = None

    assert tr_error(Odd()) == "Operația nu a reușit (SOMETHING_NEW)"


@pytest.mark.parametrize("language", ["ro", "en"])
def test_no_untranslated_key_is_shown(qtbot, ctx, tmp_path, language):
    """CLAUDE.md §6.5: niciun text de interfata ramas cheie (`image.tool.text`)."""
    import re

    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QAbstractButton, QLabel, QTabWidget

    from app.gui import i18n

    i18n.set_language(language)
    try:
        project = OcrProject.create(context=ctx)
        project.add_images(page_images(tmp_path, 1), auto_process=AutoProcessMode.NONE)
        w = MainWindow(ctx, project)
        qtbot.addWidget(w)
        texts = [a.text() for a in w.findChildren(QAction)]
        texts += [x.text() for x in w.findChildren(QLabel) + w.findChildren(QAbstractButton)]
        for tabs in w.findChildren(QTabWidget):
            texts += [tabs.tabText(i) for i in range(tabs.count())]
        key = re.compile(r"^[a-z_]+(\.[a-z_0-9]+)+$")
        assert [t for t in texts if key.match(t)] == []
        project.close()
    finally:
        i18n.set_language("ro")
