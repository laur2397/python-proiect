"""OCR Editor: scurtaturile si comenzile din SPEC_09 A.3 (X-202). Tabelul e
comparat rand cu rand cu actiunile ferestrei; comenzile adaugate (Edit, View,
Recognize, Help) se verifica pe un proiect recunoscut."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from test_gui_dialogs import ScriptEngine, ctx, project, select, window  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from app.core.model import AreaType
from app.gui.main_window import EDIT_COMMANDS, SHORTCUTS
from app.gui.text_panel import FORMAT_KEYS

SPEC_09 = Path(__file__).resolve().parents[1] / "docs" / "spec" / "SPEC_09_anexe_referinta.md"

COMMANDS = {
    "New Task...": "new_task", "Open Image...": "open", "Scan Pages...": "scan",
    "Save Page Images As...": "save_page_images", "Close": "close_project",
    "New OCR Project": "new_project", "Open OCR Project...": "open_project",
    "Save OCR Project...": "save_project", "E-mail document": "email_document",
    "E-mail images": "email_images", "Print text": "print_text", "Print image": "print_image",
    "Exit": "exit", "Undo": "undo", "Redo": "redo", "Cut": "cut",
    "Recognize and Copy Text": "copy_text", "Copy Area as Image": "copy_area_image",
    "Paste": "paste", "Delete": "delete", "Select All": "select_all",
    "Cancel Selection": "cancel_selection", "Delete Pages...": "delete_pages",
    "Delete Areas and Text": "delete_areas_text", "Delete Text": "delete_text",
    "Rotate Pages Right": "rotate_right", "Rotate Pages Left": "rotate_left",
    "Edit Page Images...": "edit_images", "Find...": "find", "Find Next": "find_next",
    "Replace...": "replace", "Show Navigation Pane": "navigation_pane",
    "Show Zoom Pane": "zoom_pane", "Image Pane Only": "image_only",
    "Image and Text Panes": "image_text", "Text Pane Only": "text_only",
    "Next Pane": "next_pane", "Previous Pane": "previous_pane", "Zoom In": "zoom_in",
    "Zoom Out": "zoom_out", "Best Fit": "best_fit", "Go to Page Number...": "go_to_page",
    "Go to Next Page": "page_down", "Go to Previous Page": "page_up",
    "Go to First Page": "first_page", "Go to Last Page": "last_page",
    "Close Page": "close_page", "Recognize All Pages": "recognize",
    "Recognize Page": "recognize_page", "Analyze All Pages": "analyze",
    "Analyze Page": "analyze_page", "Verify Text...": "verify", "Next Error": "next_error",
    "Previous Error": "previous_error", "Mark Text as Verified": "mark_verified",
    "Recognize Area": "recognize_area",
    "Change Area Type to Recognition Area": "area_type_recognition",
    "Change Area Type to Text": "area_type_text", "Change Area Type to Table":
    "area_type_table", "Change Area Type to Picture": "area_type_picture",
    "Change Area Type to Barcode": "area_type_barcode",
    "Change Area Type to Background Picture": "area_type_background_picture",
    "View Dictionaries...": "view_dictionaries", "Redaction Mode": "redaction_mode",
    "Hot Folder": "hot_folder", "Options...": "options", "Focus pe panoul Pages":
    "focus_pages", "Focus pe panoul Image": "focus_image", "Focus pe panoul Text":
    "focus_text", "Focus pe panoul Zoom": "focus_zoom", "Help": "help",
}
TEXT_FORMAT = {"Bold pe textul selectat": "Ctrl+B", "Italic pe textul selectat": "Ctrl+I",
               "Underline pe textul selectat": "Ctrl+U"}


def _a3() -> dict[str, str]:
    text = SPEC_09.read_text(encoding="utf-8")
    body = text.split("### A.3", 1)[1].split("\n### ", 1)[0]
    rows = {}
    for line in body.splitlines():
        cells = [c.strip(" *`") for c in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[1] and cells[0] not in ("Comanda", "---"):
            rows[cells[0]] = cells[1]
    return rows


def _normal(key: str) -> str:
    for ro, en in (("Sus", "Up"), ("Jos", "Down")):
        key = re.sub(rf"\b{ro}\b", en, key)
    return key


def test_T_X202_1_every_a3_row_is_an_action_with_its_shortcut(window):  # noqa: F811
    table = _a3()
    covered = set(COMMANDS) | set(TEXT_FORMAT) | {"Navigare intre celulele de tabel"}
    assert covered == set(table)
    for name, key in COMMANDS.items():
        action = window.actions[key]
        assert action.shortcut().toString() == _normal(table[name]), name
        assert SHORTCUTS.get(key, action.shortcut().toString()) == _normal(table[name])
    for name, shortcut in TEXT_FORMAT.items():
        assert table[name] == shortcut
    assert set(FORMAT_KEYS.values()) == {"bold", "italic", "underline"}


def test_T_X202_2_new_commands_are_in_the_menus(window):  # noqa: F811
    in_menus = {a.objectName() for m in window.menus.values() for a in m.actions()}
    assert set(EDIT_COMMANDS) <= in_menus


def test_T_X202_3_select_cut_paste_and_delete_areas(window, project):  # noqa: F811
    view = window.image_view
    window.edit_command("select_all")
    assert view.selected == [a.id for a in view.areas] and view.selected
    window.edit_command("cancel_selection")
    assert view.selected == []
    view.select([view.areas[0].id])
    window.edit_command("cut")
    assert view.areas == [] and len(window.area_clipboard) == 1
    window.edit_command("paste")
    assert len(view.areas) == 1 and view.areas[0].area_type is AreaType.TEXT
    window.edit_command("delete_text")
    assert project.page(1).text.strip() == "" and len(project.page(1).areas) == 1
    window.edit_command("delete_areas_text")
    assert project.page(1).areas == []


def test_T_X202_4_recognize_and_copy_text_and_area_image(window, project):  # noqa: F811
    view = window.image_view
    view.select([view.areas[0].id])
    text = window.edit_command("copy_text")
    assert "Cerere" in text and QApplication.clipboard().text() == text
    image = window.edit_command("copy_area_image")
    assert image is not None and not image.isNull()
    assert image.width() == int(view.areas[0].bbox.w)


class AreaEngine(ScriptEngine):
    def recognize_area(self, page, area, settings, cancel=None):
        result = self.recognize_page(page, settings)
        result.area_blocks = {area.id: result.blocks}
        return result


def test_T_X202_5_recognize_area_only(window, project):  # noqa: F811
    window.ocr_engine = AreaEngine()
    view = window.image_view
    window.edit_command("delete_text")  # textul dispare, zona ramane
    assert project.page(1).text.strip() == ""
    view.select([view.areas[0].id])
    window.edit_command("recognize_area")  # Ctrl+Shift+B
    assert "Cerere" in project.page(1).text
    assert project.page(2).text  # celelalte pagini raman cum erau


def test_T_X202_6_next_and_previous_error(window, project):  # noqa: F811
    first = window.go_to_error(1)
    assert first.text == "finantere"
    second = window.go_to_error(1)
    assert second.text == "Brasov" and window._current == 2
    back = window.go_to_error(-1)
    assert back.text == "finantere" and window._current == 1


def test_T_X202_7_find_replace_zoom_and_rotate(window, project):  # noqa: F811
    window.edit_command("find")
    assert window.text_panel.find_bar.isVisible()
    window.edit_command("replace")
    assert window.text_panel.replace_edit.hasFocus() or window.text_panel.find_bar.isVisible()
    before = window.image_view.zoom
    window.edit_command("zoom_in")
    assert window.image_view.zoom > before
    window.edit_command("zoom_out")
    window.pages_panel.list.setCurrentRow(0)
    rotation = project.page(1).rotation
    window.edit_command("rotate_right")
    assert project.page(1).rotation == (rotation + 90) % 360


def test_T_X202_8_ctrl_i_formats_text_instead_of_editing_images(window, project, monkeypatch):  # noqa: F811
    opened = []
    monkeypatch.setattr(type(window), "open_image_editor", lambda self: opened.append(1))
    panel = window.text_panel
    select(panel, "Cerere")
    override = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_I,
                         Qt.KeyboardModifier.ControlModifier)
    assert panel.eventFilter(panel.view, override) and override.isAccepted()
    press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
    panel.eventFilter(panel.view, press)
    word = next(w for w in project.page(1).iter_words() if w.text == "Cerere")
    assert word.is_italic and not opened


def test_T_M108_copy_tool_then_paste_on_another_page(window, project):  # noqa: F811
    view = window.image_view
    view.select([view.areas[0].id])
    window.image_panel.actions["copy"].trigger()
    assert len(window.area_clipboard) == 1 and len(view.areas) == 1  # copierea nu sterge
    window.go_to_page(2)
    window.edit_command("delete_areas_text")
    window.edit_command("paste")
    assert len(project.page(2).areas) == 1
