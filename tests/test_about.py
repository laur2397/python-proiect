"""Faza 16, pasul 16.2: `Help > About`, `System Info... > Save...` (Y-014, Y-015)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core import sysinfo
from app.core.context import APP_VERSION, AppContext
from app.core.paths import AppPaths
from app.gui.i18n import tr


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def test_T_Y015_build_number(tmp_path, monkeypatch):
    monkeypatch.setattr(sysinfo, "BUILD_FILE", tmp_path / "lipsa.txt")
    assert sysinfo.build_number() == "dev"  # din sursa
    (tmp_path / "build.txt").write_text("2026.11.24-4c794b7", encoding="utf-8")
    monkeypatch.setattr(sysinfo, "BUILD_FILE", tmp_path / "build.txt")
    assert sysinfo.build_number() == "2026.11.24-4c794b7"


def test_T_Y014_system_info_report(ctx, tmp_path):
    rows = dict(sysinfo.system_info(ctx))
    assert rows["version"] == APP_VERSION and rows["processors"]
    assert {"os", "python", "tesseract", "data_dir", "free_space"} <= set(rows)
    report = sysinfo.write_report(ctx, tmp_path / "raport.txt",
                                  {"version": tr("sysinfo.version")})
    assert f"{tr('sysinfo.version')}: {APP_VERSION}" in report.read_text(encoding="utf-8")


def test_T_Y014_Y015_about_dialog_in_both_editors(qtbot, ctx, tmp_path, monkeypatch):
    from app.core.project import OcrProject
    from app.gui.about_dialog import AboutDialog
    from app.gui.main_window import MainWindow
    from app.gui.pdf_editor import PdfEditorWindow

    dialog = AboutDialog(ctx)
    qtbot.addWidget(dialog)
    assert dialog.version.text() == tr("about.version", version=APP_VERSION,
                                       build=sysinfo.build_number())
    info = dialog.show_system_info()
    qtbot.addWidget(info)
    assert tr("sysinfo.version") in info.text.toPlainText()
    assert info.save(tmp_path / "s.txt").exists()  # Save...
    project = OcrProject.create(context=ctx)
    editor = MainWindow(ctx, project)
    qtbot.addWidget(editor)
    help_actions = [a.objectName() for a in editor.menus["help"].actions()]
    assert "about" in help_actions and "supported_formats" in help_actions
    monkeypatch.setattr(MainWindow, "exec_dialog", lambda self, d: True)
    assert isinstance(editor.show_about(), AboutDialog)
    pdf = PdfEditorWindow(ctx)
    qtbot.addWidget(pdf)
    assert pdf.actions["about"].text() == tr("pdf.action.about")
    editor.close()
    project.close()
