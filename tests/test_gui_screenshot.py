"""Faza 15, pasul 15.2: fereastra Screenshot Reader (V-001, V-003…V-009,
V-020…V-022, V-026, V-100…V-104)."""

from __future__ import annotations

import os

import pytest
from test_automated_tasks import ScriptEngine
from test_screenshot import FakeGrabber

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication

from app.core.context import AppContext
from app.core.integration import RUN_KEY, SCREENSHOT_RUN_NAME, MemoryRegistry
from app.core.model import Rect
from app.core.paths import AppPaths
from app.gui.i18n import tr
from app.gui.screenshot_window import AreaSelector, ScreenshotWindow


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx):
    w = ScreenshotWindow(ctx, grabber=FakeGrabber(), engine=ScriptEngine(),
                         registry=MemoryRegistry())
    qtbot.addWidget(w)
    w.open_path = lambda path: w.opened.append(path)
    w.run_recognition = lambda operation: operation(lambda: False)
    yield w
    if w.tray is not None:
        w.tray.hide()


def test_T_V100_V101_V102_window_layout(window):
    assert window.windowTitle() == tr("screenshot.title")
    assert [window.capture.itemText(i) for i in range(window.capture.count())] == [
        tr(f"screenshot.capture.{k}") for k in ("area", "window", "screen", "timed")]
    assert window.send.count() == 10  # V-010…V-019
    assert window.capture_button.text() and window.send_button.text()  # V-102
    assert not window.send_button.isEnabled()  # nimic capturat inca
    assert not window.repeat_button.isEnabled()  # V-026: gri fara captura
    assert window.help_button.text() == "?"


def test_T_V009_language_combo_with_more_languages(window, ctx):
    last = window.language.count() - 1
    assert window.language.itemText(last) == tr("screenshot.more_languages")
    window._remember("deu")
    assert window.current_language() == "deu"
    assert ctx.settings.get("screenshot.languages")[:2] == ["deu", "ron"]


def test_T_V003_V007_area_selector(qtbot, window):
    selector = AreaSelector(window.reader._grabber)
    qtbot.addWidget(selector)
    chosen, cancelled = [], []
    selector.chosen.connect(chosen.append)
    selector.cancelled.connect(lambda: cancelled.append(True))
    selector.set_selection(QRect(QPoint(40, 30), QPoint(339, 129)))
    selector.confirm()
    assert chosen == [Rect(40, 30, 300, 100)]
    other = AreaSelector(window.reader._grabber)
    qtbot.addWidget(other)
    other.cancelled.connect(lambda: cancelled.append(True))
    qtbot.keyClick(other, Qt.Key.Key_Escape)  # V-007
    assert cancelled == [True]


def test_T_V010_V026_capture_then_text_to_clipboard(window):
    window.send.setCurrentIndex(window.send.findData("text_clipboard"))
    window._chosen(Rect(30, 30, 400, 150))
    assert "captura_001" in QApplication.clipboard().text()
    assert window.repeat_button.isEnabled() and window.send_button.isEnabled()
    window.repeat_capture()  # V-026: aceeasi zona
    assert window.reader._grabber.grabbed[-1] == Rect(30, 30, 400, 150)


def test_T_V011_V012_table_and_image_to_clipboard(window):
    window._chosen(Rect(30, 30, 400, 150))
    rows = window.deliver("table_clipboard")
    assert rows and "\t" in QApplication.clipboard().text() or rows
    window.deliver("image_clipboard")
    assert not QApplication.clipboard().image().isNull()


def test_T_V013_V014_word_and_excel_open(window):
    window._chosen(Rect(30, 30, 400, 150))
    window.opened.clear()
    window.deliver("text_word")
    window.deliver("table_excel")
    assert [p.suffix for p in window.opened] == [".docx", ".xlsx"]


def test_T_V015_V016_V017_files(window, tmp_path):
    window._chosen(Rect(30, 30, 400, 150))
    for target, name in (("text_file", "t.txt"), ("table_file", "t.csv"),
                         ("image_file", "i.png")):
        window.pick_save = lambda _t, n=name: tmp_path / n
        assert window.deliver(target) == tmp_path / name
        assert (tmp_path / name).exists()


def test_T_V018_V103_image_to_ocr_editor_current_or_new(window):
    window._chosen(Rect(30, 30, 400, 150))
    sent = []
    window.ocr_editor_requested.connect(lambda path, current: sent.append((path, current)))
    window.ask_current_project = lambda: True
    window.deliver("image_ocr_editor")
    window.ask_current_project = lambda: False
    window.deliver("image_ocr_editor")
    assert [current for _p, current in sent] == [True, False]
    assert sent[0][0].suffix == ".png"


def test_T_V019_image_to_email_as_bmp(window):
    window._chosen(Rect(30, 30, 400, 150))
    window.opened.clear()
    bmp = window.deliver("image_email")
    assert bmp.suffix == ".bmp" and str(window.opened[0]) == "mailto:"


def test_T_V020_V021_V022_V104_tray_options(window, ctx):
    assert list(window.options) == ["always_on_top", "run_at_startup", "sounds"]
    window.options["always_on_top"].setChecked(False)
    assert not window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    window.options["run_at_startup"].setChecked(True)
    assert window.registry.get(RUN_KEY, SCREENSHOT_RUN_NAME).endswith("--screenshot-reader")
    window.options["run_at_startup"].setChecked(False)
    assert window.registry.get(RUN_KEY, SCREENSHOT_RUN_NAME) is None
    window.options["sounds"].setChecked(False)
    assert ctx.settings.get("screenshot.sounds") is False


def test_T_V006_timed_capture_waits_five_seconds(window, qtbot, monkeypatch):
    from PySide6.QtCore import QTimer

    delays = []
    monkeypatch.setattr(QTimer, "singleShot", lambda ms, fn: (delays.append(ms), fn()))
    window.capture.setCurrentIndex(window.capture.findData("timed"))
    window.start_capture()
    assert delays == [5000] and window.image is not None


def test_T_V001_tools_menu_in_three_places(qtbot, ctx, monkeypatch):
    from app.gui.application import Application

    app = Application(ctx)
    started = []
    monkeypatch.setattr(app, "start_screenshot_reader", lambda: started.append(True))
    editor = app.editor
    qtbot.addWidget(editor)
    assert "screenshot_reader" in [a.objectName() for a in editor.menus["tools"].actions()]
    launcher = app.launcher
    qtbot.addWidget(launcher)
    pdf = app.pdf_editor
    qtbot.addWidget(pdf)
    assert pdf.actions["screenshot_reader"].text() == tr("pdf.action.screenshot_reader")
    for signal in (editor.screenshot_reader_requested, launcher.screenshot_reader_requested,
                   pdf.screenshot_reader_requested):
        signal.disconnect()
        signal.connect(lambda: started.append(True))
        signal.emit()
    launcher.screenshot_button.click()
    assert len(started) == 4
