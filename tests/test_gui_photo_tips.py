"""Faza 6d, pasul 6d.4: recomandarile pentru fotografierea documentelor
(K-014…K-017)."""

from __future__ import annotations

import os

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton

from app.core.context import AppContext
from app.core.model import AutoProcessMode
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.gui.launcher import Launcher
from app.gui.main_window import MainWindow
from app.gui.photo_tips import SECTIONS, PhotoTipsDialog, tips


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def text_of(dialog):
    return "\n".join(label.text() for label in dialog.findChildren(QLabel))


def test_T_K014_1_camera_and_resolution(qtbot):
    dialog = PhotoTipsDialog()
    qtbot.addWidget(dialog)
    text = text_of(dialog)
    for fragment in ("5 milioane de pixeli", "2 milioane de pixeli", "blițul",
                     "diafragma manuală", "focalizarea manuală", "trepied", "zoomul optic"):
        assert fragment in text, fragment


def test_T_K015_1_lighting():
    assert len(tips("light")) == SECTIONS["light"] == 4
    text = " ".join(tips("light"))
    for fragment in ("naturală", "două surse", "hârtie lucioasă", "50 cm"):
        assert fragment in text, fragment


def test_T_K016_1_positioning():
    text = " ".join(tips("position"))
    for fragment in ("paralelă", "50–60 cm", "20 de grade", "centrul",
                     "declanșarea automată"):
        assert fragment in text, fragment


def test_three_groups_in_the_dialog(qtbot):
    dialog = PhotoTipsDialog()
    qtbot.addWidget(dialog)
    assert [g.title() for g in dialog.findChildren(QGroupBox)] == [
        "Camera și rezoluția", "Iluminarea", "Poziționarea"]
    assert not dialog.correct.isEnabled()  # fara pagini nu are ce corecta


def test_T_K017_1_photo_correction_from_the_tips(qtbot, ctx, tmp_path):
    Image.new("L", (400, 600), 200).save(tmp_path / "foto.jpg", dpi=(150, 150))
    project = OcrProject.create(context=ctx)
    project.add_images([tmp_path / "foto.jpg"], auto_process=AutoProcessMode.NONE)
    window = MainWindow(ctx, project)
    qtbot.addWidget(window)
    assert window.actions["photo_tips"] in window.menus["help"].actions()
    dialog = window.show_photo_tips(modal=False)
    assert dialog.correct.isEnabled()
    dialog.correct.click()
    assert window.editing_images
    assert window.image_editor.toolbox.currentWidget().objectName() == "editor_photo"
    project.close()


def test_tips_from_the_launcher_scan_tab(qtbot, ctx):
    launcher = Launcher(ctx)
    qtbot.addWidget(launcher)
    launcher.findChild(QPushButton, "scan_photo_tips").click()
    assert launcher.photo_dialog.isVisible()
    launcher.photo_dialog.close()
