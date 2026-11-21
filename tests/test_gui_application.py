"""Faza 6c, pasul 6c.4: pornirea si legaturile dintre Lansator, conversie si
OCR Editor (A-001, A-002, A-010, A-012, A-013, A-102)."""

from __future__ import annotations

import os

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.core.recent import RecentDocuments
from app.gui.application import Application
from app.gui.convert_screen import ConvertScreen


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.auto_process", False)
    yield c
    c.close()


@pytest.fixture
def app(qtbot, ctx, monkeypatch):
    opened = []
    monkeypatch.setattr(Application, "open_external", lambda self, path: opened.append(path))
    application = Application(ctx)
    application.opened = opened
    yield application
    for window in application.windows():
        window.hide()
        if hasattr(window, "project"):
            window.project.close()
        window.deleteLater()


@pytest.fixture
def images(tmp_path):
    out = []
    for n in (1, 2):
        Image.new("L", (300, 400), 255).save(tmp_path / f"p{n}.png", dpi=(300, 300))
        out.append(tmp_path / f"p{n}.png")
    return out


def test_T_A001_1_launcher_by_default(app, ctx):
    assert ctx.settings.get("general.startup_screen") == "new_task"
    window = app.start()
    assert window is app.launcher and window.isVisible()
    assert window.current_task == "open"


def test_T_A001_2_ocr_editor_with_new_project(app, ctx):
    ctx.settings.set("general.startup_screen", "ocr_new_project")
    window = app.start()
    assert window is app.editor and len(window.project.pages) == 0


def test_T_A001_3_last_project_or_new_when_missing(app, ctx, images, tmp_path):
    ctx.settings.set("general.startup_screen", "ocr_last_project")
    assert len(app.start().project.pages) == 0  # niciun proiect recent: proiect nou
    editor = app.editor
    editor.open_images(images)
    assert editor.save_project_as(tmp_path / "Dosar")  # intra in recente (A-102)
    assert RecentDocuments(ctx.app_db).last("ocr_project").display_name == "Dosar"
    editor.new_project()
    second = Application(ctx)
    try:
        window = second.start()
        assert window.project.name == "Dosar" and len(window.project.pages) == 2
    finally:
        second.editor.hide()
        second.editor.project.close()


def test_T_A002_1_new_task_shows_the_launcher(app, ctx):
    ctx.settings.set("general.startup_screen", "ocr_new_project")
    editor = app.start()
    assert editor.actions["new_task"].shortcut().toString() == "Ctrl+N"
    editor.actions["new_task"].trigger()
    assert app.launcher.isVisible() and editor.isVisible()  # editorul ramane deschis


def test_T_A012_2_open_files_in_the_ocr_editor(app, images):
    app.start()
    app.launcher.open_in_ocr_editor(images)
    assert app.editor.isVisible() and len(app.editor.project.pages) == 2
    app.launcher.open_in_ocr_editor(images[:1])  # proiect nou
    assert len(app.editor.project.pages) == 1


def test_T_A013_2_convert_screen_over_the_launcher(app, images):
    app.start()
    app.launcher.convert("pdf", images)
    screen = app.launcher.screens.currentWidget()
    assert isinstance(screen, ConvertScreen) and len(screen.file_paths()) == 2
    screen.back_requested.emit()  # `< Back`
    assert app.launcher.screens.currentWidget() is app.launcher.home


def test_T_A010_1_pdf_opens_and_becomes_recent(app, ctx, tmp_path):
    pdf = tmp_path / "act.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    app.start()
    app.launcher.open_pdf(pdf)
    assert app.opened == [pdf]
    assert RecentDocuments(ctx.app_db).last("pdf").display_name == "act.pdf"


def test_options_from_the_launcher(app):
    app.start()
    dialog = app.open_options("format", "docx")
    assert dialog.current_tab == "format"
    assert dialog.format_pages.currentWidget().objectName() == "format_docx"
    dialog.reject()
