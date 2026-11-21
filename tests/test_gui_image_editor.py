"""Faza 6b, pasul 6b.4: Image Editor (L-001…L-004, L-100…L-108)."""

from __future__ import annotations

import os

import pytest
from PIL import Image, ImageDraw

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QPushButton, QToolBox

from app.core.context import AppContext
from app.core.model import AutoProcessMode, PreprocessOp, Rect
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.gui.image_editor import BACKGROUND, SELECTIONS, TOOLS
from app.gui.main_window import MainWindow


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    paths = []
    for n in range(1, 5):
        img = Image.new("L", (600, 800), 255)
        ImageDraw.Draw(img).rectangle((100, 100, 300, 140), fill=0)
        img.save(tmp_path / f"p{n}.png", dpi=(300, 300))
        paths.append(tmp_path / f"p{n}.png")
    project = OcrProject.create(context=ctx)
    project.add_images(paths, auto_process=AutoProcessMode.NONE)
    w = MainWindow(ctx, project)
    qtbot.addWidget(w)
    w.resize(1400, 1000)
    w.show()
    yield w
    w.hide()
    project.close()


def ops(window, n):
    return [op for op, _ in window.project.applied_operations(n)]


def test_T_L001_1_open_from_button_menu_and_shortcut(window):
    assert window.actions["edit_images"].shortcut().toString() == "Ctrl+I"
    assert window.actions["edit_images"] in window.menus["edit"].actions()
    window.image_panel.actions["edit_image"].trigger()
    assert window.editing_images
    window.image_editor.exit_button.click()  # L-002
    assert not window.editing_images
    window.actions["edit_images"].trigger()
    assert window.editing_images


def test_T_L100_1_header_and_L101_tool_order(window):
    window.open_image_editor()
    editor = window.image_editor
    assert editor.findChild(QPushButton, "editor_exit").text() == "< Ieșire din Image Editor"
    box = editor.findChild(QToolBox, "editor_tools")
    assert box.count() == 14
    assert [box.widget(i).objectName() for i in range(14)] == [f"editor_{t}" for t in TOOLS]
    assert box.itemText(0) == "Preprocesare recomandată"
    assert box.itemText(13) == "Eliminarea marcajelor colorate"


def test_T_L102_1_tool_expands_inline(window):
    """QToolBox: unealta aleasa se deschide sub numele ei, nu intr-un dialog."""
    window.open_image_editor()
    editor = window.image_editor
    editor.open_tool("levels")
    assert editor.toolbox.currentWidget().objectName() == "editor_levels"
    assert editor.toolbox.currentWidget().isVisibleTo(editor)


def test_T_L003_1_selection_combo_in_every_tool(window):
    window.open_image_editor()
    editor = window.image_editor
    assert set(editor.selections) == set(TOOLS)
    for combo in editor.selections.values():
        assert [combo.itemData(i) for i in range(combo.count())] == list(SELECTIONS)


def test_rotate_on_odd_pages(window):
    window.open_image_editor()
    editor = window.image_editor
    editor.open_tool("rotate_flip")
    editor.selections["rotate_flip"].setCurrentIndex(SELECTIONS.index("odd"))
    editor.buttons["rotate_right"].click()
    assert ops(window, 1) == [PreprocessOp.ROTATE] and ops(window, 3) == [PreprocessOp.ROTATE]
    assert ops(window, 2) == [] and ops(window, 4) == []
    assert window.project.page(1).width_px == 800
    window.actions["undo"].trigger()  # L-109: un singur pas de undo
    assert ops(window, 1) == [] and ops(window, 3) == []


def test_T_L004_1_show_next_page(window):
    window.open_image_editor()
    editor = window.image_editor
    editor.show_next.setChecked(True)
    editor.open_tool("invert")
    editor.buttons["invert"].click()
    assert ops(window, 1) == [PreprocessOp.INVERT]
    assert window.current == 2 and editor.page.page_number == 2


def test_T_L103_1_crop_fields_and_paper(window):
    window.open_image_editor()
    editor = window.image_editor
    editor.open_tool("crop")
    names = [editor.paper.itemData(i) for i in range(editor.paper.count())]
    assert "a4" in names and names[0] is None
    editor.unit_buttons["mm"].setChecked(True)
    for key, value in (("width", 25.4), ("height", 25.4), ("x", 25.4), ("y", 0)):
        editor.crop_fields[key].setValue(value)
    assert editor.crop_chain() == [(PreprocessOp.CROP,
                                    {"x": 300, "y": 0, "width": 300, "height": 300})]
    editor.unit_buttons["in"].setChecked(True)
    editor.crop_fields["width"].setValue(1)
    editor.crop_fields["height"].setValue(2)
    editor.crop_fields["x"].setValue(0)
    assert editor.crop_chain()[0][1] == {"x": 0, "y": 0, "width": 300, "height": 600}
    editor.buttons["crop"].click()
    assert (window.project.page(1).width_px, window.project.page(1).height_px) == (300, 600)


def test_T_L106_1_drawing_the_crop_selection(window, qtbot):
    window.open_image_editor()
    editor = window.image_editor
    editor.open_tool("crop")
    canvas = editor.canvas
    assert canvas.mode == "crop"
    vp = canvas.viewport()
    start = canvas.mapFromScene(QPointF(60, 60))
    end = canvas.mapFromScene(QPointF(360, 460))
    qtbot.mousePress(vp, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(vp, end)
    qtbot.mouseRelease(vp, Qt.MouseButton.LeftButton, pos=end)
    crop = canvas.crop
    tolerance = 3 / canvas.transform().m11()
    assert abs(crop.x - 60) <= tolerance and abs(crop.w - 300) <= 2 * tolerance
    assert editor.paper.currentData() is None  # dimensiune personalizata
    assert editor.crop_fields["width"].value() == pytest.approx(crop.w / 300 * 25.4, abs=0.1)


def test_T_L105_1_dark_gray_background(window):
    window.open_image_editor()
    assert window.image_editor.canvas.backgroundBrush().color() == BACKGROUND
    assert BACKGROUND.red() < 100 and BACKGROUND.red() == BACKGROUND.green()


def test_T_L107_1_trapezoid_grid_and_correct(window):
    window.open_image_editor()
    editor = window.image_editor
    editor.open_tool("trapezoid")
    assert editor.canvas.mode == "trapezoid" and len(editor.canvas.corners) == 4
    assert editor.buttons["trapezoid"].text() == "Corectează"
    editor.canvas.set_corners([[20, 10], [580, 30], [590, 790], [5, 780]])
    assert editor.apply("trapezoid")
    assert ops(window, 1) == [PreprocessOp.TRAPEZOID]


def test_T_L108_1_levels_histogram_and_cursors(window):
    window.open_image_editor()
    editor = window.image_editor
    editor.open_tool("levels")
    levels = editor.levels
    assert set(levels.sliders) == {"black", "gray", "white", "output"}
    assert levels.histogram[255] > levels.histogram[0] > 0  # pagina alba cu un bloc negru
    assert not levels.chart.pixmap().isNull()
    levels.sliders["white"].setValue(100)
    levels.sliders["black"].setValue(150)  # nu poate trece de alb
    assert levels.sliders["black"].value() == 99
    levels.sliders["gray"].setValue(200)
    levels.sliders["output"].setValue(240)
    assert levels.params() == {"black": 99, "white": 100, "gamma": 2.0, "out_black": 0,
                               "out_white": 240}
    editor.buttons["levels"].click()
    assert ops(window, 1) == [PreprocessOp.LEVELS]


def test_eraser_path_from_the_mouse(window, qtbot):
    window.open_image_editor()
    editor = window.image_editor
    editor.open_tool("eraser")
    canvas = editor.canvas
    vp = canvas.viewport()
    qtbot.mousePress(vp, Qt.MouseButton.LeftButton, pos=canvas.mapFromScene(QPointF(120, 120)))
    qtbot.mouseMove(vp, canvas.mapFromScene(QPointF(200, 120)))
    qtbot.mouseMove(vp, canvas.mapFromScene(QPointF(280, 120)))
    qtbot.mouseRelease(vp, Qt.MouseButton.LeftButton,
                       pos=canvas.mapFromScene(QPointF(280, 120)))
    assert len(canvas.erase_path) >= 2
    editor.brush.setValue(60)
    editor.buttons["eraser"].click()
    with Image.open(window.project.page(1).image_path) as img:
        assert img.convert("L").getpixel((200, 120)) > 200  # blocul negru s-a sters


def test_every_tool_builds_a_valid_chain(window):
    """Fiecare unealta da un lant pe care nucleul il accepta."""
    from app.core.images.preprocess import default_pipeline

    window.open_image_editor()
    editor = window.image_editor
    editor.canvas.erase_path = [[10, 10], [20, 20]]
    editor.crop_fields["width"].setValue(10)
    editor.crop_fields["height"].setValue(10)
    pipeline = default_pipeline()
    for key in TOOLS:
        if key == "rotate_flip":
            continue
        editor.open_tool(key)
        if key == "eraser":
            editor.canvas.erase_path = [[10, 10], [20, 20]]
        chain = editor.chain_for(key)
        if chain is None:
            assert key == "recommended"
            continue
        for op, params in chain:
            pipeline.tool_for(op).validate_params(params)


def test_invalid_parameters_show_a_message(window):
    window.open_image_editor()
    editor = window.image_editor
    messages = []
    editor.message.connect(messages.append)
    editor.open_tool("eraser")
    editor.canvas.erase_path = []
    assert not editor.apply("eraser")
    assert messages == ["Parametrii operației nu sunt valizi"]


def test_crop_rect_handles_paint(window):
    window.open_image_editor()
    editor = window.image_editor
    editor.open_tool("crop")
    editor.canvas.crop = Rect(10, 10, 100, 100)
    editor.canvas.viewport().repaint()  # desenarea cu manere nu da erori
    assert editor.canvas.crop == Rect(10, 10, 100, 100)
