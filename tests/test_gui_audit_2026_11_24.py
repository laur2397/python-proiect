"""Interfata: defectele gasite la auditul din 24.11.2026."""

from __future__ import annotations

import os

import pytest
from test_gui_dialogs import ctx, project, window  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt


def test_arrange_buttons_move_the_text_pane(window):  # noqa: F811
    window.actions["arrange_stacked"].trigger()
    assert window.dockWidgetArea(window.text_dock) is Qt.DockWidgetArea.BottomDockWidgetArea
    assert window.actions["arrange_stacked"].isChecked()
    window.actions["arrange_side"].trigger()
    assert window.dockWidgetArea(window.text_dock) is Qt.DockWidgetArea.RightDockWidgetArea
    assert not window.actions["arrange_stacked"].isChecked()


def test_text_panel_style_editor_button_opens_the_editor(window, monkeypatch):  # noqa: F811
    opened = []
    monkeypatch.setattr(type(window), "open_style_editor", lambda self: opened.append(1))
    button = window.text_panel.actions["style_editor"]
    assert button.isEnabled()
    button.trigger()
    assert opened == [1]


def test_full_screen_menu_edits_text_and_images(qtbot, tmp_path, monkeypatch):
    from test_pdf_search import text_pdf

    from app.core.context import AppContext
    from app.core.paths import AppPaths
    from app.gui.pdf_editor import PdfEditorWindow

    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    try:
        w = PdfEditorWindow(c)
        qtbot.addWidget(w)
        w.open_path(text_pdf(tmp_path / "d.pdf", [["Cerere"]]))
        entered = []
        monkeypatch.setattr(PdfEditorWindow, "enter_edit_content",
                            lambda self: entered.append(1))
        menu = w.full_screen_menu()
        edit = next(a for a in menu.actions() if a.objectName() == "full_screen_edit_content")
        assert edit.isEnabled()
        edit.trigger()
        assert entered == [1]
        w.close()
    finally:
        c.close()


def test_exceptions_are_shown_in_the_interface_language():
    from app.core.errors import CoreError
    from app.gui import i18n

    plain = ValueError("trebuie selectata cel putin o limba")
    assert i18n.tr_exception(plain) == "trebuie selectata cel putin o limba"  # interfata ro
    i18n.set_language("en")
    try:
        shown = i18n.tr_exception(plain)
        assert shown.startswith("The operation could not be completed")
        assert "limba" in shown  # detaliul ramane, pentru raportare
        assert i18n.tr_exception(CoreError("x")) == i18n.tr_error(CoreError("x"))
    finally:
        i18n.set_language("ro")
