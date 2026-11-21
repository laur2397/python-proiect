"""Faza 6b, pasul 6b.6a: proiectul, adaugarea imaginilor, recunoasterea cu
progres si anulare, limbile documentului (J-030…J-032, J-401, N-004, N-027,
N-028)."""

from __future__ import annotations

import os

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from app.core.context import AppContext
from app.core.errors import OperationCancelledError
from app.core.model import (
    BlockData,
    LineData,
    PageStatus,
    Progress,
    Rect,
    WordData,
)
from app.core.ocr.engine import RecognitionResult
from app.core.paths import AppPaths
from app.gui.main_window import MainWindow
from app.gui.progress import ProgressRunner


class ScriptEngine:
    name = "fals"

    def __init__(self):
        self.pages = []

    def recognize_page(self, page, settings, cancel=None):
        self.pages.append(page.page_number)
        word = WordData(None, f"pagina{page.page_number}", 95.0, bbox=Rect(10, 10, 80, 20))
        block = BlockData(None, lines=[LineData(None, words=[word], bbox=Rect(10, 10, 80, 20))],
                          bbox=Rect(10, 10, 80, 20))
        areas = {a.id: [block] for a in page.areas[:1]}
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=95.0,
                                 area_blocks=areas)


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.auto_process", False)
    c.settings.set("lang.mode", "manual")
    c.settings.set("lang.manual", ["ron"])
    yield c
    c.close()


@pytest.fixture
def images(tmp_path):
    paths = []
    for n in (1, 2, 3):
        img = Image.new("L", (600, 800), 255)
        img.paste(0, (100, 100, 400, 140))
        img.save(tmp_path / f"p{n}.png", dpi=(300, 300))
        paths.append(tmp_path / f"p{n}.png")
    return paths


@pytest.fixture
def window(qtbot, ctx):
    w = MainWindow(ctx)
    w.ocr_engine = ScriptEngine()
    qtbot.addWidget(w)
    w.show()
    yield w
    w.hide()
    w.project.close()


def test_open_images_adds_pages(window, images):
    assert window.open_images(images[:2]) == 2
    assert window.page_counter.text() == "[ 1 / 2 ]" and window.pages_list.count() == 2
    assert window.open_images([images[2]]) == 1
    assert window.current == 3  # prima pagina adaugata


def test_open_images_reports_bad_files(window, tmp_path, images):
    (tmp_path / "rau.png").write_bytes(b"nu e imagine")
    assert window.open_images([images[0], tmp_path / "rau.png"]) == 1
    assert window.statusBar().currentMessage().startswith("Fișiere neadăugate: 1.")


def test_recognize_with_progress(window, images):
    window.open_images(images[:2])
    done = window.recognize()
    assert done == [1, 2]
    assert window.ocr_engine.pages == [1, 2]
    assert all(p.status is PageStatus.RECOGNIZED for p in window.project.pages)  # N-004
    assert "pagina1" in window.text_panel.view.toPlainText()
    assert window.recognize() == []  # N-003: cele recunoscute se sar


def test_recognize_page_button(window, images):
    window.open_images(images)
    window.go_to_page(2)
    window.image_panel.actions["recognize_page"].trigger()
    assert window.ocr_engine.pages == [2]
    window.image_panel.actions["analyze_page"].trigger()
    assert window.image_panel.actions["analyze_page"].isEnabled()


def test_analyze_all(window, images):
    window.open_images(images[:2])
    window.analyze()
    assert all(p.status is PageStatus.ANALYZED and p.areas for p in window.project.pages)


def test_progress_runner_reports_and_cancels(qtbot):
    runner = ProgressRunner("Test")
    seen = []

    def work(progress, cancel):
        for i in range(1, 4):
            progress(Progress(i, 3, "stage.recognizing", f"p{i}"))
            seen.append(runner.dialog.labelText())
            if i == 2:
                runner.dialog.cancel()
            if cancel():
                raise OperationCancelledError("anulat")
        return "gata"

    assert runner.run(work) is None  # anulata: ce s-a terminat ramane
    assert seen[0] == "Recunoaștere\np1" and runner.cancelled
    assert ProgressRunner("Test").run(lambda p, c: "gata") == "gata"


def test_save_as_and_open_round_trip(window, images, tmp_path):
    window.open_images(images[:2])
    window.recognize()
    target = tmp_path / "Dosar finantare"
    assert window.save_project_as(target)
    assert window.windowTitle() == "Dosar finantare - DocuLens OCR Editor"
    assert not window.project.is_modified
    assert window.new_project()
    assert len(window.project.pages) == 0
    assert window.open_project(target)
    assert len(window.project.pages) == 2
    assert window.project.page(1).status is PageStatus.RECOGNIZED
    assert "pagina1" in window.text_panel.view.toPlainText()


def test_save_into_a_busy_folder_shows_a_message(window, images, tmp_path):
    window.open_images(images[:1])
    busy = tmp_path / "ocupat"
    busy.mkdir()
    (busy / "altceva.txt").write_text("x")
    assert not window.save_project_as(busy)
    assert window.statusBar().currentMessage() == \
        "Proiectul nu a putut fi salvat aici: alegeți un folder gol"


def test_unsaved_changes_question(window, images, monkeypatch, tmp_path):
    window.open_images(images[:1])
    assert window.project.is_modified
    monkeypatch.setattr(MainWindow, "ask_save", lambda self: "cancel")
    old = window.project
    assert not window.new_project() and window.project is old  # anulare: ramane
    monkeypatch.setattr(MainWindow, "ask_save", lambda self: "save")
    monkeypatch.setattr(MainWindow, "pick_folder", lambda self, key: tmp_path / "salvat")
    assert window.new_project()  # se salveaza intai
    assert (tmp_path / "salvat").is_dir() and window.project is not old


def test_close_event_asks(window, images, monkeypatch):
    window.open_images(images[:1])
    monkeypatch.setattr(MainWindow, "ask_save", lambda self: "cancel")
    assert not window.close()
    monkeypatch.setattr(MainWindow, "ask_save", lambda self: "discard")
    assert window.close()


def test_open_invalid_project_shows_a_message(window, tmp_path):
    (tmp_path / "gol").mkdir()
    assert not window.open_project(tmp_path / "gol")
    assert window.statusBar().currentMessage() != ""


def test_T_J401_2_language_combo(window, ctx):
    combo = window.language_combo
    assert combo.itemText(0) == "Română"
    ctx.settings.set("lang.recent", ["eng", "ron"])
    window.refresh()
    index = next(i for i in range(combo.count()) if combo.itemData(i) == ["eng"])
    combo.activated.emit(index)
    assert window.project.settings().ocr_settings().languages == ("eng",)
    assert combo.itemText(0) == "Engleză"
    assert combo.itemText(combo.count() - 1) == "Mai multe limbi..."


def test_untitled_number_in_the_title(window):
    number = window.project.untitled_number
    assert window.windowTitle() == f"Proiect fără titlu {number} - DocuLens OCR Editor"
    window.new_project()
    assert window.windowTitle() == \
        f"Proiect fără titlu {window.project.untitled_number} - DocuLens OCR Editor"
    assert window.project.untitled_number != number
