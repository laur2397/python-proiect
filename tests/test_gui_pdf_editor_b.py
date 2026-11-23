"""PDF Editor: cerintele B fara test pana acum. Vizualizarea (B-003, B-004,
B-008, B-012, B-015), panourile (B-019, B-020, B-022, B-025…B-027), depanarea
recunoasterii (B-031), modul intunecat (B-044), ribbon-ul (B-201, B-202,
B-204…B-206), unealta Hand (B-301), panoul Pages (B-307, B-309, B-310), zona
de pagina (B-311) si editarea blocurilor (B-312…B-314)."""

from __future__ import annotations

import os

import pytest
from test_gui_pdf_editor import ctx, pdf  # noqa: F401  (fixture-uri)
from test_pdf_content_edit import paragraph_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPalette
from PySide6.QtWidgets import QApplication, QInputDialog, QToolButton

from app.core.model import Rect
from app.core.pdf.background import WARNING_CHECK_LANGUAGES
from app.gui import pdf_edit, pdf_panels, pdf_view, theme
from app.gui.i18n import tr
from app.gui.pdf_editor import (
    PAGE_MENU_COMMANDS,
    PANES,
    RIBBON_TABS,
    SHORTCUTS,
    PdfEditorWindow,
)
from app.gui.pdf_view import FitMode, Tool, ViewMode


@pytest.fixture
def window(qtbot, ctx):  # noqa: F811
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    yield w
    w.close()


# --- vizualizarea ---------------------------------------------------------------------


def test_T_B003_B004_scrolling_and_two_page_view(window, pdf):  # noqa: F811
    entry = window.open_path(pdf)
    assert SHORTCUTS["one_page_scroll"] == "Ctrl+6" and SHORTCUTS["two_page"] == "Ctrl+7"
    window.actions["one_page_scroll"].trigger()
    assert entry.view.mode is ViewMode.ONE_PAGE_SCROLLING
    assert entry.view.spreads() == [(n, None) for n in range(1, 6)]  # una dupa alta
    window.actions["two_page"].trigger()
    assert entry.view.mode is ViewMode.TWO_PAGE
    assert entry.view.spreads() == [(1, 2), (3, 4), (5, None)]  # impare in stanga


def test_T_B008_full_screen_bar_appears_at_bottom_edge(window, pdf):  # noqa: F811
    entry = window.open_path(pdf)
    window.actions["full_screen"].trigger()
    viewport = entry.view.viewport()
    assert not window.bottom_bar.isVisible()

    def move(y: float) -> None:
        event = QMouseEvent(QEvent.Type.MouseMove, QPointF(10, y), QPointF(10, y),
                            Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier)
        window.eventFilter(viewport, event)

    move(viewport.height() - 2)
    assert window.bottom_bar.isVisible()
    assert window.page_field.isVisibleTo(window.bottom_bar)  # campul de numar de pagina
    assert window.actions["one_page"].isEnabled()  # modurile de vizualizare
    move(5)
    assert not window.bottom_bar.isVisible()
    window.exit_full_screen()


def test_T_B012_actual_size_is_100_percent(window, pdf):  # noqa: F811
    entry = window.open_path(pdf)
    assert SHORTCUTS["actual_size"] == "Ctrl+1"
    window.set_zoom(250)
    window.actions["actual_size"].trigger()
    assert entry.view.zoom == 100 and entry.view.fit is FitMode.ACTUAL_SIZE


def test_T_B015_go_to_page_number(window, pdf, monkeypatch):  # noqa: F811
    entry = window.open_path(pdf)
    assert SHORTCUTS["go_to_page"] == "Ctrl+G"
    asked = {}

    def get_int(parent, title, label, value, low, high):
        asked.update(low=low, high=high)
        return 3, True

    monkeypatch.setattr(QInputDialog, "getInt", get_int)
    window.actions["go_to_page"].trigger()
    assert entry.view.current_page == 3 and asked == {"low": 1, "high": 5}


# --- panourile ------------------------------------------------------------------------


def test_T_B019_six_panes_and_f5(window, pdf):  # noqa: F811
    window.open_path(pdf)
    # cinci panouri in bara verticala; `Comments` e al saselea, in dreapta (F7)
    assert PANES == ("pages", "bookmarks", "search", "attachments", "signatures")
    assert window.comments_panel is not None
    assert SHORTCUTS["navigation_pane"] == "F5"
    window.actions["navigation_pane"].trigger()
    window.actions["navigation_pane"].trigger()
    assert window.nav_stack.isVisible()


def test_T_B020_pages_thumbnails_are_lazy(window, pdf):  # noqa: F811
    assert SHORTCUTS["pane_pages"] == "Alt+Shift+1"
    window.open_path(pdf)
    window.actions["pane_pages"].trigger()
    panel = window.pages_panel
    assert window.nav_stack.currentWidget() is panel and panel.list.count() == 5
    assert panel._timer.interval() == 0  # se randeaza una cate una, in bucla de evenimente


def test_T_B022_search_pane(window, pdf):  # noqa: F811
    window.open_path(pdf)
    assert SHORTCUTS["pane_search"] == "Alt+Shift+3"
    window.actions["pane_search"].trigger()
    assert window.nav_stack.currentWidget() is window.search_panel


def test_T_B025_comments_pane(window, pdf):  # noqa: F811
    window.open_path(pdf)
    assert SHORTCUTS["comments_pane"] == "F7"
    window.actions["comments_pane"].trigger()
    assert window.comments_panel.isVisible()


def test_T_B026_bars_cannot_be_hidden_separately(window):
    assert window.createPopupMenu() is None  # nu exista meniul de bare al ferestrei
    assert not any("toolbar" in key or "status_bar" in key for key in window.actions)
    assert "full_screen" in window.actions  # pentru asta e ecranul complet


def test_T_B027_navigation_width_limits_and_memory(window, ctx, qtbot):  # noqa: F811
    assert window.nav_stack.minimumWidth() == 150 and window.nav_stack.maximumWidth() == 600
    window.nav_stack.resize(320, window.nav_stack.height())
    window.remember_navigation_width()
    assert ctx.settings.get("ui.pdf_navigation_width") == 320
    with pytest.raises(ValueError):
        ctx.settings.set("ui.pdf_navigation_width", 900)
    second = PdfEditorWindow(ctx)
    qtbot.addWidget(second)
    assert second.navigation_width() == 320  # la deschiderea urmatoare


def test_T_B031_search_without_results_suggests_checking_languages(window, pdf):  # noqa: F811
    window.open_path(pdf)
    window.actions["pane_search"].trigger()
    window.search_panel.set_hits([])
    hint = tr(WARNING_CHECK_LANGUAGES)
    assert hint in window.search_panel.empty.text()


# --- B-044 ----------------------------------------------------------------------------


def test_T_B044_dark_mode_switches_the_whole_interface(window, ctx):  # noqa: F811
    from app.gui.application import Application

    app = QApplication.instance()
    assert "ui.dark_theme" in __import__("app.gui.options_dialog",
                                         fromlist=["OTHER_KEYS"]).OTHER_KEYS
    application = Application(ctx)  # asculta setarile
    try:
        assert application.context is ctx
        ctx.settings.set("ui.dark_theme", True)
        assert app.property("dark_mode") is True
        window_color = app.palette().color(QPalette.ColorRole.Window)
        assert window_color == QColor(theme.DARK_COLORS["bg"])
        assert theme.DARK_COLORS["bg"] in app.styleSheet()
        ctx.settings.set("ui.dark_theme", False)
        assert app.property("dark_mode") is False
        assert app.palette().color(QPalette.ColorRole.Window) == QColor(theme.COLORS["bg"])
    finally:
        theme.apply(app)
    assert set(theme.DARK_COLORS) == set(theme.COLORS)


# --- ribbon-ul ------------------------------------------------------------------------


def test_T_B201_settings_help_and_collapse_top_right(window):
    buttons = [b for b in window.findChildren(QToolButton) if b.defaultAction() in
               (window.actions["options"], window.actions["help"])]
    assert len(buttons) >= 2
    assert window.collapse_button.isCheckable()


def test_T_B202_undo_redo_and_comments_on_second_row(window, pdf):  # noqa: F811
    window.open_path(pdf)
    for key in ("undo", "redo", "comments_pane"):
        assert any(isinstance(o, QToolButton) for o in window.actions[key].associatedObjects())
    assert window.actions["comments_pane"].text().endswith("(1)")


def test_T_B204_B205_B206_tab_commands(window):
    assert RIBBON_TABS["organize"][0] == "selected_pages"
    for key in ("delete_pages", "rotate_left", "rotate_right", "correct_orientation",
                "crop_pages", "move_pages", "replace_pages", "split", "delete_blank_pages",
                "recognize_document", "enhance", "save_as"):
        assert key in RIBBON_TABS["organize"]
    for key in ("header_footer", "picture", "add_text"):
        assert key in RIBBON_TABS["content"]
    names = {w.objectName() for w in (window.text_font, window.text_size,
                                      window.text_line_spacing, window.text_paragraph_spacing)}
    assert names == {"text_font", "text_size", "text_line_spacing", "text_paragraph_spacing"}
    for key in ("bigger", "smaller", "bold", "italic", "underline", "align_left",
                "align_center", "align_right", "align_justify", "rtl", "color"):
        assert key in window.text_controls  # A+, A-, B, I, U, alinieri, directie, culoare
    assert RIBBON_TABS["security"] == ("signature", "password_security", "watermark", "erase",
                                       "redact", "delete_objects", "select", "hand")


def test_T_B301_hand_tool_on_document_and_security(window, pdf):  # noqa: F811
    assert "hand" in RIBBON_TABS["security"]
    assert window.actions["hand"] in window.toolbars["document"].actions() or \
        window.actions["hand"] in window.toolbars["security"].actions()
    on_document = any(window.actions["hand"] is a for a in window.toolbars["document"].actions())
    entry = window.open_path(pdf)
    window.actions["hand"].trigger()
    assert entry.view.tool is Tool.HAND
    assert on_document or "hand" in RIBBON_TABS["document"]


# --- panoul Pages si zona de pagina ---------------------------------------------------


def test_T_B307_B309_pages_panel_thumbnails(window):
    assert 100 <= pdf_panels.THUMB + 36 <= 140  # panoul are circa 120 px
    image = QImage(60, 85, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    with_text = pdf_panels.thumbnail(image, True).pixmap(pdf_panels.THUMB, 119).toImage()
    without = pdf_panels.thumbnail(image, False).pixmap(pdf_panels.THUMB, 119).toImage()
    corner = (8 * with_text.width() // pdf_panels.THUMB,
              with_text.height() - 8 * with_text.height() // 119)
    assert with_text.pixelColor(*corner) == QColor(pdf_panels.TEXT_BADGE)  # stanga-jos
    assert without.pixelColor(*corner) != QColor(pdf_panels.TEXT_BADGE)
    assert pdf_panels.CURRENT_BACKGROUND in window.pages_panel.list.styleSheet()


def test_T_B310_pages_context_menu_has_all_organize_commands(window):
    menu_actions = window.panel_menu.actions()
    organize = [k for k in RIBBON_TABS["organize"] if k not in ("selected_pages", "save_as")]
    names = {a.objectName() for a in menu_actions}
    for key in organize:
        present = window.actions.get(key) in menu_actions or any(
            key.split("_")[0] in n for n in names)
        assert present, key
    for key in PAGE_MENU_COMMANDS:
        assert window.actions[key] in menu_actions


def test_T_B311_light_grey_page_background():
    assert QColor(pdf_view.CANVAS).lightness() > 200
    assert QColor(pdf_view.CANVAS).saturation() < 40


# --- editarea blocurilor --------------------------------------------------------------


@pytest.fixture
def editing(qtbot, ctx, tmp_path):  # noqa: F811
    path = paragraph_pdf(tmp_path / "doc.pdf", [["Cerere de finantare"],
                                                ["Bugetul total este de 1200 lei"]])
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    w.open_path(path)
    w.actions["edit_content"].trigger()
    yield w, w.content_edit
    w.close()


def test_T_B312_blocks_have_thin_pink_purple_outline(editing):
    window, controller = editing
    color = pdf_edit.OUTLINE
    assert color.red() > color.green() and color.blue() > color.green()  # roz-mov
    image = window.current().view.viewport().grab().toImage()
    assert not image.isNull() and len(controller.blocks()) == 2


def test_T_B313_B314_dragged_block_overlay_and_eight_handles(editing):
    _window, controller = editing
    block = controller.blocks()[0]
    controller.select_block(block.id)
    controller._drag = ("move", block.id, block.rect.x, block.rect.y, block.rect)
    controller._drag_to = (block.rect.x + 20, block.rect.y + 10)
    old, new = controller.drag_preview()
    assert old == block.rect  # locul vechi, punctat
    assert new == Rect(block.rect.x + 20, block.rect.y + 10, block.rect.w, block.rect.h)
    assert pdf_edit.DRAG_FILL.alpha() < 255 and pdf_edit.DRAG_FILL.blue() > 200
    from PySide6.QtCore import QRectF

    assert len(pdf_edit._handle_points(QRectF(0, 0, 50, 30))) == 8  # opt manere
    controller._drag = None
    assert controller.drag_preview() is None
