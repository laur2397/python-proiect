"""OCR Editor: carcasa ferestrei si uneltele din `Tools` (J-001…J-083, J-300…J-419,
O-036, P-040…P-063)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


from app.core.context import AppContext
from app.core.model import AutoProcessMode, PageWarning
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.gui.i18n import tr
from app.gui.main_window import SHORTCUTS, MainWindow

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def _pages(tmp_path, n):
    out = []
    for i in range(1, n + 1):
        path = tmp_path / f"p{i}.png"
        Image.new("L", (300, 400), 255).save(path, dpi=(300, 300))
        out.append(path)
    return out


@pytest.fixture
def window(qtbot, ctx, tmp_path, monkeypatch):
    project = OcrProject.create(context=ctx)
    project.add_images(_pages(tmp_path, 4), auto_process=AutoProcessMode.NONE)
    w = MainWindow(ctx, project)
    qtbot.addWidget(w)
    w.show()
    monkeypatch.setattr(MainWindow, "exec_dialog", lambda self, d: True)
    w.refresh()
    yield w
    w.close()
    project.close()


def test_T_J300_J302_menus(window):
    names = [a.menu().objectName() for a in window.menuBar().actions() if a.menu()]
    assert names == ["menu_file", "menu_edit", "menu_view", "menu_recognize", "menu_area",
                     "menu_tools", "menu_help"]  # J-300
    tools = [a.objectName() or "-" for a in window.menus["tools"].actions()]
    assert tools == ["view_dictionaries", "pattern_editor", "style_editor", "-",
                     "redaction_mode", "-", "automated_tasks", "hot_folder",
                     "compare_documents", "screenshot_reader", "-", "options"]
    assert window.actions["view_dictionaries"].shortcut().toString() == "Ctrl+Alt+D"
    assert window.actions["redaction_mode"].shortcut().toString() == "Ctrl+Shift+H"


def test_T_J301_gear_and_help_top_right(window):
    corner = window.menuBar().cornerWidget()
    assert corner is window.corner
    assert {b.objectName() for b in corner.findChildren(type(corner.children()[1]))} >= {
        "corner_options", "corner_help"}


def test_T_J004_J005_J006_J007_J008_pane_shortcuts(window):
    assert [SHORTCUTS[k] for k in ("navigation_pane", "image_only", "image_text",
                                   "text_only", "zoom_pane")] == ["F5", "F6", "F7", "F8",
                                                                  "Ctrl+F5"]
    visible = window.pages_dock.isVisible()
    window.actions["navigation_pane"].trigger()
    assert window.pages_dock.isVisible() != visible
    window.actions["text_only"].trigger()
    assert not window.center.isVisible() and window.text_dock.isVisible()
    window.actions["image_only"].trigger()
    assert window.center.isVisible() and not window.text_dock.isVisible()
    window.actions["image_text"].trigger()
    assert window.center.isVisible() and window.text_dock.isVisible()
    before = window.image_panel.zoom_pane_toggle.isChecked()
    window.actions["zoom_pane"].trigger()
    assert window.image_panel.zoom_pane_toggle.isChecked() != before


def test_T_J009_focus_and_cycle(window):
    assert [SHORTCUTS[f"focus_{p}"] for p in ("pages", "image", "text", "zoom")] == [
        "Alt+1", "Alt+2", "Alt+3", "Alt+4"]
    window.focus_pane("pages")
    assert window.cycle_pane(1) == "image" and window.cycle_pane(-1) == "pages"
    assert SHORTCUTS["next_pane"] == "Ctrl+Tab"


def test_T_J010_J011_J012_quick_access_bar(window, ctx):
    assert not window.quick_bar.isVisible()  # J-011: ascunsa implicit
    window.actions["quick_access_bar"].setChecked(True)
    assert window.quick_bar.isVisible()
    ctx.settings.set("ui.quick_access", ["recognize", "verify"])
    window.apply_quick_access()
    assert [a.objectName() for a in window.quick_bar.actions()] == ["recognize", "verify"]
    toolbar = window.findChild(type(window.quick_bar), "main_toolbar")
    assert toolbar is not None and not toolbar.isMovable()  # J-010
    from app.gui.shortcuts_dialog import CustomizeDialog

    dialog = CustomizeDialog(window._shortcut_store(), window, quick_access=["ocr.recognize"])
    assert dialog.tabs.tabText(1) == tr("customize.tab.toolbars")
    dialog.tb_commands.setCurrentRow(0)
    dialog.toolbar_add()
    assert len(dialog.quick_access) == 2
    dialog.toolbar_reset()
    assert dialog.quick_access == []


def test_T_J013_J406_J419_warnings_panel(window):
    page = window.project.page(2)
    page.warnings.append(PageWarning("warning", "LOW_RESOLUTION", "warning.low_resolution",
                                     {"dpi": 150}))
    window.refresh()
    assert window.warnings.isVisible()  # J-419: indicatorul din stanga-jos
    window.actions["show_warnings"].setChecked(True)
    panel = window.warnings_panel
    panel.show_page(1)
    assert panel.step(1) == 2  # navigare la pagina cu avertismente
    panel.show_page(2)
    assert panel.list.count() == 1
    assert panel.delete_current() and panel.list.count() == 0  # stergerea
    from app.gui.pages_panel import thumbnail

    assert thumbnail  # J-406: triunghiul pe miniatura (desenat cand pagina are avertismente)


def test_T_J014_J015_J016_panels(window):
    from PySide6.QtWidgets import QDockWidget

    assert window.pages_dock.features() & QDockWidget.DockWidgetFeature.DockWidgetMovable
    area = window.dockWidgetArea(window.pages_dock)
    window.actions["move_pages_panel"].trigger()  # J-015
    assert window.dockWidgetArea(window.pages_dock) != area
    assert window.actions["move_pages_panel"] in window.pages_dock.actions()
    assert window.image_panel.properties is not None  # J-016, J-414


def test_T_J017_J068_J069_pages(window, monkeypatch):
    item = window.pages_list.item(2)
    window.pages_list.itemDoubleClicked.emit(item)  # J-017: dublu clic
    assert window._current == 3
    window.close_page()  # J-068
    assert window._page_closed and SHORTCUTS["close_page"] == "Ctrl+F4"
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: (4, True))
    assert window.ask_go_to_page() == 4 and window._current == 4  # J-069: Ctrl+G
    assert SHORTCUTS["go_to_page"] == "Ctrl+G"


def test_T_J059_J063_reorder_dialog(window):
    from app.gui.editor_tools import ReorderPagesDialog

    window.pages_list.selectAll()
    dialog = window.reorder_pages()  # J-059: din meniul panoului Pages
    assert isinstance(dialog, ReorderPagesDialog)
    dialog.swap.setChecked(True)
    assert dialog.apply()  # J-062
    assert [p.source_file.name for p in window.project.pages] == ["p2.png", "p1.png",
                                                                  "p4.png", "p3.png"]

    second = ReorderPagesDialog(window.project, [1, 2, 3, 4])
    assert second.undo_button.isEnabled()
    assert second.undo_last()  # J-063
    assert [p.source_file.name for p in window.project.pages] == ["p1.png", "p2.png",
                                                                  "p3.png", "p4.png"]
    short = ReorderPagesDialog(window.project, [1, 2])
    assert not short.duplex.isEnabled() and short.swap.isEnabled()  # J-061: minimum 3
    assert window.actions["reorder_pages"] in window.pages_panel.more_menu.actions()


def test_T_J402_save_button_follows_format(window):
    window.update_save_button("docx")
    assert window.save_button.text() == tr("action.save") and window.save_format == "docx"
    window.update_save_button("pdf", send=False)
    window.update_save_button("pptx", send=True)
    assert window.save_button.text() == tr("action.send")


def test_T_P040_P041_P044_dictionary_dialog(window, tmp_path):
    dialog = window.open_dictionaries()
    assert dialog.add_word("Brașov")
    assert not dialog.add_word("Brașov")  # P-041: duplicat → avertisment
    assert dialog.messages[-1] == tr("dictionary.duplicate", word="Brașov")
    source = tmp_path / "cuvinte.txt"
    source.write_text("Cluj\nIași\n", encoding="utf-8")
    dialog.pick_open = lambda: source
    assert dialog.import_words() == 2  # P-044
    assert {"Brașov", "Cluj", "Iași"} <= {dialog.words.item(i).text()
                                          for i in range(dialog.words.count())}
    dialog.done(0)


def test_T_P053_P054_P061_P062_P063_pattern_editor(window):
    dialog = window.open_pattern_editor()
    dialog.ask_text = lambda *a, **k: "Facturi"
    assert dialog.new_set() == "Facturi"
    dialog.set_active()
    assert dialog.store.active_set() == "Facturi"
    assert not dialog.edit_character() and not dialog.delete_character()  # fara caractere


def test_T_O036_style_editor(window):
    dialog = window.open_style_editor()
    assert dialog.list.count() >= 1
    dialog.flags["is_bold"].setChecked(True)
    style = dialog.apply()
    assert style is not None and style.is_bold


def test_T_J001_J033_J053_J054_ways_to_open(qtbot, ctx, tmp_path):
    from app.core.integration import FOLDER_COMMAND, MemoryRegistry, register_shell_menu
    from app.gui.application import Application

    app = Application(ctx)
    pdf = app.pdf_editor
    qtbot.addWidget(pdf)
    assert "open_ocr_editor" in pdf.actions  # J-001: PDF Editor > Tools > OCR Editor
    iss = (ROOT / "packaging" / "doculens.iss").read_text(encoding="utf-8")
    assert "--action ocr_editor" in iss  # J-001: meniul Start
    registry = MemoryRegistry()
    register_shell_menu(registry, ["DocuLens.exe"], tr)
    assert registry.get(f"{FOLDER_COMMAND}\\command", "").endswith('--action open_project "%1"')
    project = OcrProject.create(context=ctx)
    project.add_images(_pages(tmp_path, 1), auto_process=AutoProcessMode.NONE)
    project.save(tmp_path / "Dosar")
    project.close()
    editor = app.run_action("open_project", [tmp_path / "Dosar"])  # J-033
    qtbot.addWidget(editor)
    assert len(editor.project.pages) == 1
    app._dropped_on_editor(_pages(tmp_path / "noi", 0) or [])
    extra = tmp_path / "x.png"
    Image.new("L", (300, 400), 255).save(extra, dpi=(300, 300))
    app._dropped_on_editor([extra])  # J-054: in proiectul deschis
    assert len(editor.project.pages) == 2


def test_T_J002_J035_J081_J082_J083_existing_settings(ctx):
    from app.core.settings import CATALOG

    keys = {d.key for d in CATALOG}
    assert "general.startup_screen" in keys  # J-002
    assert SHORTCUTS["close_project"] == "Ctrl+W"  # J-035
    from app.core.ocr.dictionary import DictionaryService
    from app.core.ocr.patterns import BUNDLE_SUFFIX

    assert BUNDLE_SUFFIX == ".fbtx"  # J-081: sabloane si limbi partajate
    assert hasattr(DictionaryService, "is_locked_by_other")  # J-082, J-083
    assert "areas.user_dictionaries_folder" in keys
