"""Finisarea vizuala dupa prototip (faza 6b, pasul 6b.7): tema, iconitele
proprii, bara principala, miniaturile, bara de stare, Lansatorul
(J-401, J-403…J-408, J-410…J-412, M-101, A-300…A-302)."""

from __future__ import annotations

import os

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QToolBar

from app.core.context import AppContext
from app.core.model import AutoProcessMode, PageStatus
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.core.settings import definition
from app.gui import icons, theme
from app.gui.launcher import Launcher
from app.gui.main_window import ICON_ONLY, MainWindow
from app.gui.pages_panel import STATUS_COLORS, thumbnail


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.auto_process", False)
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    paths = []
    for n in (1, 2):
        Image.new("L", (600, 800), 255).save(tmp_path / f"p{n}.png", dpi=(300, 300))
        paths.append(tmp_path / f"p{n}.png")
    project = OcrProject.create(context=ctx)
    project.add_images(paths, auto_process=AutoProcessMode.NONE)
    w = MainWindow(ctx, project)
    qtbot.addWidget(w)
    w.resize(1400, 900)
    yield w
    w.hide()
    project.close()


def test_every_icon_renders(qapp):
    for name in icons.names():
        image = icons.icon(name).pixmap(QSize(24, 24)).toImage()
        assert not image.isNull(), name
        assert any(image.pixelColor(x, y).alpha() for x in range(image.width())
                   for y in range(image.height())), name


def test_theme_applies_the_prototype_palette(qapp):
    app = QApplication.instance()
    old_sheet, old_palette = app.styleSheet(), app.palette()
    try:
        theme.apply(app)
        assert theme.COLORS["accent"] in app.styleSheet()
        assert app.palette().highlight().color().name() == theme.COLORS["accent"]
    finally:
        app.setStyleSheet(old_sheet)
        app.setPalette(old_palette)


def test_T_M101_2_default_zone_colors_are_our_own():
    """M-101: setul implicit propriu (cel din prototip), nu cel ABBYY."""
    assert definition("areas.color.text").default.upper() == "#2F6DF6"
    assert definition("areas.color.table").default.upper() == "#15803D"
    assert definition("areas.color.picture").default.upper() == "#C026A3"


def test_main_toolbar_icons_and_primary_button(window):
    bar = window.findChild(QToolBar, "main_toolbar")
    assert bar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    assert bar.widgetForAction(window.actions["recognize"]).property("primary") is True
    for key in ICON_ONLY:
        button = bar.widgetForAction(window.actions[key])
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly, key
        assert not window.actions[key].icon().isNull(), key
    assert not window.save_button.icon().isNull()


def test_zone_tools_show_the_zone_color(window):
    image = window.image_panel.actions["tool.text"].icon().pixmap(QSize(12, 12)).toImage()
    color = image.pixelColor(image.width() // 2, image.height() // 2)
    assert (color.red(), color.green(), color.blue()) == (0x2F, 0x6D, 0xF6)


def test_status_bar_shows_page_and_uncertain_words(window):
    window.refresh()
    assert window.page_info.text() == "Pagina 1 — p1.png · 0 zone · Neprocesată"
    assert window.uncertain_info.text() == ""


def test_zoom_pane_is_hidden_until_asked(window, qtbot):
    window.show()
    qtbot.waitUntil(window.isVisible)
    assert not window.zoom_dock.isVisible()
    window.image_panel.zoom_pane_toggle.setChecked(True)
    assert window.zoom_dock.isVisible()


def test_new_page_fits_the_width_until_the_user_zooms(window, qtbot):
    window.show()
    view = window.image_view
    window.go_to_page(2)
    qtbot.waitUntil(lambda: view.zoom != 100, timeout=2000)
    assert view.auto_fit
    view.set_zoom(150)
    assert not view.auto_fit
    window.go_to_page(1)
    qtbot.wait(50)
    assert view.zoom == 150


def test_T_J405_2_thumbnail_badge_and_selection(window):
    icon = thumbnail(window.project.page(1), window.style())
    size = QSize(84, 118)
    normal = icon.pixmap(size, QIcon.Mode.Normal).toImage()
    assert normal == icon.pixmap(size, QIcon.Mode.Selected).toImage()  # foaia nu se coloreaza
    badge = normal.pixelColor(int(normal.width() * 5 / 84), int(normal.height() * 103 / 118))
    assert badge.name() == STATUS_COLORS[PageStatus.IMPORTED].lower()


def test_T_A300_2_launcher_tasks_and_cards_have_icons(qtbot, ctx):
    launcher = Launcher(ctx)
    qtbot.addWidget(launcher)
    for i in range(launcher.tasks.count()):
        assert not launcher.tasks.item(i).icon().isNull()
    for key, card in launcher.cards.items():
        assert not card.icon().isNull(), key
        assert card.property("card") is True
    assert launcher.cards["pdf"].toolButtonStyle() == \
        Qt.ToolButtonStyle.ToolButtonTextUnderIcon
