"""Faza 6d, pasul 6d.3: scanarea in interfata (K-002…K-012, A-080…A-090,
X-404, X-407)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel, QPushButton
from test_scanner import FakeScanner

from app.core.context import AppContext
from app.core.images.scanner import ScanSettings
from app.core.model import ColorMode
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.gui.application import Application
from app.gui.convert_screen import ConvertScreen
from app.gui.document_actions import DocumentActions
from app.gui.launcher import SCAN_CARDS, Launcher
from app.gui.main_window import MainWindow
from app.gui.options_dialog import OptionsDialog
from app.gui.scan_dialog import DeviceDialog, ImageFilesDialog, ScanDialog


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.auto_process", False)
    yield c
    c.close()


@pytest.fixture
def scanner(tmp_path):
    folder = tmp_path / "scanari"
    folder.mkdir()
    return FakeScanner(folder)


@pytest.fixture
def project(ctx):
    p = OcrProject.create(context=ctx)
    yield p
    p.close()


def dialog_for(qtbot, ctx, scanner, project=None, **kw):
    d = ScanDialog(ctx, scanner, project=project, **kw)
    qtbot.addWidget(d)
    return d


def test_T_K002_2_scan_into_the_project_then_scan_again(qtbot, ctx, scanner, project):
    d = dialog_for(qtbot, ctx, scanner, project)
    assert [d.device.itemText(i) for i in range(d.device.count())] == [
        "Scaner birou (ADF)", "Scaner plat"]
    assert ColorMode(d.color.currentData()) is ColorMode.GRAY  # K-005
    assert d.scan_button.text() == "Scanează"
    d.device.setCurrentIndex(1)
    assert d.scan() == 1 and len(project.pages) == 1
    assert d.scan_button.text() == "Scanează din nou"  # A-082
    assert d.scan() == 1 and len(project.pages) == 2
    assert ctx.settings.get("general.capture_device") == "flat"


def test_T_K009_3_and_K010_5_options_follow_the_device(qtbot, ctx, scanner, project):
    d = dialog_for(qtbot, ctx, scanner, project)
    d.device.setCurrentIndex(0)  # ADF cu duplex
    assert d.duplex.isEnabled() and d.adf.isEnabled()
    assert [d.dpi.itemData(i) for i in range(d.dpi.count())] == [150, 200, 300, 600]
    d.adf.setChecked(True)
    d.duplex.setChecked(True)
    assert not d.pause.isEnabled()  # K-011: pauza numai pe geam
    assert d.scan() == 6
    d.device.setCurrentIndex(1)  # scaner plat
    assert not d.duplex.isEnabled() and not d.adf.isChecked()


def test_T_K006_2_and_K007_3_warnings_in_the_dialog(qtbot, ctx, scanner):
    d = dialog_for(qtbot, ctx, scanner)
    d.brightness.setValue(10)
    assert "Luminozitatea e prea mică" in d.message.text()
    d.brightness.setValue(50)
    d.device.setCurrentIndex(1)
    d.dpi.setCurrentIndex(d.dpi.findData(1200))
    assert "peste 600 dpi" in d.message.text()


def test_no_scanner_shows_a_message(qtbot, ctx, tmp_path):
    d = dialog_for(qtbot, ctx, FakeScanner(tmp_path, devices=[]))
    assert not d.scan_button.isEnabled()
    assert d.message.text().startswith("Nu a fost găsit niciun scaner.")
    assert "Opțiuni" in d.message.text()  # A-081: trimitere la Options


def test_T_K012_3_preview(qtbot, ctx, scanner):
    d = dialog_for(qtbot, ctx, scanner)
    assert d.preview() and not d.preview_label.pixmap().isNull()
    assert scanner.scans[-1].dpi == 75


def test_acquire_mode_collects_images(qtbot, ctx, scanner):
    d = dialog_for(qtbot, ctx, scanner)
    d.device.setCurrentIndex(1)
    d.scan()
    d.scan()
    assert len(d.images) == 2 and all(p.is_file() for p in d.images)


def test_T_A083_1_auto_processing_choice_is_saved(qtbot, ctx, scanner, project):
    d = dialog_for(qtbot, ctx, scanner, project, auto_process=True)
    d.auto_process.setChecked(True)
    d.auto_mode.setCurrentIndex(d.auto_mode.findData("analyze"))
    d.device.setCurrentIndex(1)
    d.scan()
    assert project.settings().get("image.auto_mode") == "analyze"
    assert project.page(1).status.value == "analyzed"


def test_ocr_editor_scan_action(qtbot, ctx, scanner):
    window = MainWindow(ctx)
    window.scanner_service = scanner
    qtbot.addWidget(window)
    assert window.actions["scan"].shortcut().toString() == "Ctrl+K"
    dialog = window.scan_pages(modal=False)
    dialog.device.setCurrentIndex(1)
    dialog.scan()
    dialog.accept()
    assert window.page_counter.text() == "[ 1 / 1 ]"
    window.project.close()


def test_T_X407_1_select_device_dialog(qtbot, ctx, scanner, monkeypatch):
    d = DeviceDialog(scanner, "flat")
    qtbot.addWidget(d)
    assert d.devices.count() == 2 and d.chosen()[0] == "flat"
    assert "(WIA)" in d.devices.item(0).text()
    assert "conectat la calculator" in d.findChild(QLabel, "device_help").text()
    options = OptionsDialog(ctx)
    qtbot.addWidget(options)
    assert options.select_device.isEnabled()
    monkeypatch.setattr(DeviceDialog, "exec", lambda self: 1)
    assert options.choose_device(scanner)
    assert options.fields["general.capture_device"][1]() == "adf"


def test_T_A080_1_launcher_scan_tab(qtbot, ctx):
    launcher = Launcher(ctx)
    qtbot.addWidget(launcher)
    assert SCAN_CARDS == ("ocr_editor", "pdf", "docx", "xlsx", "images", "other")
    with qtbot.waitSignal(launcher.scan_requested) as signal:
        launcher.cards["scan_docx"].click()
    assert signal.args == ["docx"]
    with qtbot.waitSignal(launcher.options_tab_requested) as signal:  # A-090
        launcher.findChild(QPushButton, "scan_preprocessing").click()
    assert signal.args == ["image"]


def test_T_A088_2_image_files_dialog(qtbot):
    d = ImageFilesDialog()
    qtbot.addWidget(d)
    assert [d.compression.itemData(i) for i in range(d.compression.count())] == [
        "packbits", "jpeg", "zip", "lzw"]
    d.format.setCurrentIndex(2)  # PNG: fara compresie
    assert not d.compression.isEnabled()
    assert d.choice() == {"format": "png", "compression": None, "multipage": False}


@pytest.fixture
def app(qtbot, ctx, scanner):
    application = Application(ctx)
    application.scanner_service = scanner
    yield application
    for window in application.windows():
        window.hide()
        if hasattr(window, "project"):
            window.project.close()


def scanned(scanner, n=2):
    return [next(iter(scanner.scan(ScanSettings("flat")))).path for _ in range(n)]


def test_T_A080_2_routes_after_scanning(app, scanner, tmp_path, monkeypatch):
    images = scanned(scanner)
    editor = app.scan("ocr_editor", images)  # A-083
    assert len(editor.project.pages) == 2
    screen = app.scan("docx", images)  # A-085
    assert isinstance(screen, ConvertScreen) and screen.target().value == "docx"
    saved = app.save_scanned_images(images, {"format": "tiff", "compression": "packbits",
                                             "multipage": True}, tmp_path / "img")
    assert len(saved) == 1 and saved[0].suffix == ".tif"  # A-087, A-088
    calls = []
    monkeypatch.setattr(DocumentActions, "save_document",
                        lambda self, key=None, **kw: calls.append(key))
    app.scan("pdf", images)  # A-084: OCR Editor, apoi salvarea ca PDF
    assert calls == ["pdf"] and len(app.editor.project.pages) == 2
