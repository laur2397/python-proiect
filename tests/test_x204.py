"""Scurtaturile reatribuibile (auditul 23.11.2026, defectul 7): X-204…X-207."""

from __future__ import annotations

import os

import pytest

from app.core.context import AppContext
from app.core.errors import ShortcutConflictError
from app.core.paths import AppPaths
from app.core.shortcuts import ShortcutStore

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def store(ctx):
    s = ShortcutStore(ctx.app_db)
    s.register([("ocr.recognize", "action.recognize", "recognize", "Ctrl+Shift+R"),
                ("ocr.analyze", "action.analyze", "recognize", "Ctrl+Shift+E"),
                ("ocr.undo", "action.undo", "edit", "Ctrl+Z")])
    return s


def test_T_X205_assign_and_registration_keeps_the_choice(store):
    store.assign("ocr.recognize", "Ctrl+Alt+R")
    assert store.shortcut("ocr.recognize") == "Ctrl+Alt+R"
    store.register([("ocr.recognize", "action.recognize", "recognize", "Ctrl+Shift+R")])
    assert store.shortcut("ocr.recognize") == "Ctrl+Alt+R"  # alegerea ramane
    with pytest.raises(KeyError):
        store.assign("ocr.lipsa", "Ctrl+J")


def test_T_X207_used_combination_needs_release(store):
    with pytest.raises(ShortcutConflictError) as caught:
        store.assign("ocr.analyze", "Ctrl+Z")
    assert caught.value.params["command"] == "ocr.undo"
    store.assign("ocr.undo", None)  # eliberarea
    store.assign("ocr.analyze", "Ctrl+Z")
    assert store.shortcut("ocr.analyze") == "Ctrl+Z"


def test_T_X206_reset_category_and_all(store):
    store.assign("ocr.recognize", "Ctrl+Alt+R")
    store.assign("ocr.undo", "Ctrl+Alt+Z")
    store.reset_defaults("recognize")
    assert store.shortcut("ocr.recognize") == "Ctrl+Shift+R"
    assert store.shortcut("ocr.undo") == "Ctrl+Alt+Z"
    store.reset_defaults()
    assert store.shortcut("ocr.undo") == "Ctrl+Z"


def test_T_X204_customize_only_in_ocr_editor(qtbot, ctx, monkeypatch):
    """X-204: `View > Toolbars > Customize...` in OCR Editor, tabul `Keyboard
    Shortcuts`; combinatia noua se aplica ferestrei. PDF Editor nu are dialogul."""
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QKeySequence

    from app.core.project import OcrProject
    from app.gui.i18n import tr
    from app.gui.main_window import MainWindow
    from app.gui.pdf_editor import PdfEditorWindow
    from app.gui.shortcuts_dialog import CustomizeDialog

    project = OcrProject.create(context=ctx)
    window = MainWindow(ctx, project)
    qtbot.addWidget(window)
    toolbars = window.findChild(type(window.menus["view"]), "menu_toolbars")
    assert toolbars is not None and window.actions["customize"] in toolbars.actions()
    assert window.actions["recognize"].shortcut().toString() == "Ctrl+Shift+R"

    def run(self, dialog):
        assert isinstance(dialog, CustomizeDialog)
        assert dialog.tabs.tabText(0) == tr("customize.tab.shortcuts")
        dialog.select("ocr.recognize")
        assert dialog.current.text() == "Ctrl+Shift+R"
        dialog.key.setKeySequence(QKeySequence("Ctrl+Z"))
        assert not dialog.assign() and dialog.message.isVisibleTo(dialog)  # X-207
        dialog.key.setKeySequence(QKeySequence("Ctrl+Alt+R"))
        assert dialog.assign() and dialog.current.text() == "Ctrl+Alt+R"
        dialog.accept()
        return True
    monkeypatch.setattr(MainWindow, "exec_dialog", run)
    assert window.customize_shortcuts()
    assert window.actions["recognize"].shortcut().toString() == "Ctrl+Alt+R"
    assert not hasattr(PdfEditorWindow, "customize_shortcuts")
    window.close()
    project.close()
