"""Faza 6c, pasul 6c.2: fereastra Lansatorului (A-001…A-012, A-100…A-111,
A-300…A-303)."""

from __future__ import annotations

import os
import shutil
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QToolButton, QWidget

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.core.recent import RecentDocuments
from app.gui.launcher import TASKS, Launcher

ROLE = Qt.ItemDataRole.UserRole


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def launcher(qtbot, ctx):
    w = Launcher(ctx)
    qtbot.addWidget(w)
    return w


def add_recent(ctx, tmp_path, name, kind, *, exists=True):
    path = tmp_path / name
    if exists:
        path.write_bytes(b"x")
    RecentDocuments(ctx.app_db).add(path, kind)
    time.sleep(0.01)
    return path


def test_T_A003_1_five_tasks_and_open_first(launcher):
    tasks = launcher.findChild(QListWidget, "launcher_tasks")
    assert [tasks.item(i).text() for i in range(tasks.count())] == [
        "Deschide", "Scanează", "Compară", "Recente", "Aplicația mobilă"]
    assert TASKS == ("open", "scan", "compare", "recent", "mobile")
    assert launcher.current_task == "open"  # A-001
    launcher.show_task("recent")
    assert launcher.pages.currentWidget().objectName() == "launcher_recent"


def test_T_A007_1_scenarios_on_hover(launcher):
    tasks = launcher.findChild(QListWidget, "launcher_tasks")
    assert all(tasks.item(i).toolTip() for i in range(tasks.count()))


def test_T_A005_1_options_button(launcher, qtbot):
    with qtbot.waitSignal(launcher.options_requested):
        launcher.options_button.click()


def test_T_A006_1_help_without_manual(launcher, monkeypatch, tmp_path):
    import app.gui.launcher as module

    monkeypatch.setattr(module, "MANUAL", tmp_path / "lipsa" / "index.html")
    assert not launcher.show_help()


def test_T_A301_1_card_groups(launcher):
    page = launcher.findChild(QWidget, "launcher_open")
    sections = [w.text() for w in page.findChildren(QLabel)
                if w.objectName().startswith("section_")]
    assert sections == ["Deschide și editează", "Convertește în"]
    names = [b.objectName() for b in page.findChildren(QToolButton)]
    assert names == ["card_pdf_document", "card_ocr_editor", "card_pdf", "card_docx",
                     "card_xlsx", "card_other"]
    assert launcher.cards["ocr_editor"].text() == \
        "OCR Editor\nConversie avansată și verificare"


def test_cards_emit_requests(launcher, qtbot, tmp_path):
    files = [tmp_path / "a.png"]
    with qtbot.waitSignal(launcher.convert_requested) as signal:
        launcher.convert("docx", files)
    assert signal.args == ["docx", files]
    with qtbot.waitSignal(launcher.ocr_editor_requested) as signal:
        launcher.open_in_ocr_editor(files)  # A-012
    assert signal.args == [files]
    with qtbot.waitSignal(launcher.pdf_requested):
        launcher.open_pdf(tmp_path / "d.pdf")


def test_T_A303_1_compare_tab(launcher, qtbot):
    assert launcher.cards["compare"].isEnabled()  # R-001
    assert launcher.comparisons.count() == 0
    with qtbot.waitSignal(launcher.compare_requested) as signal:
        launcher.cards["compare"].click()
    assert signal.args == [None, None]


def test_T_A111_1_empty_state(launcher):
    launcher.show_task("recent")
    assert launcher.recent_list.isHidden() and not launcher.recent_empty.isHidden()


def test_T_A102_3_recent_list_opens_in_the_right_module(launcher, ctx, tmp_path, qtbot):
    pdf = add_recent(ctx, tmp_path, "dosar.pdf", "pdf")
    project = tmp_path / "Proiect"
    project.mkdir()
    RecentDocuments(ctx.app_db).add(project, "ocr_project")
    time.sleep(0.01)
    add_recent(ctx, tmp_path, "mutat.pdf", "pdf", exists=False)
    launcher.show_task("recent")
    texts = [launcher.recent_list.item(i).text() for i in range(launcher.recent_list.count())]
    assert texts == ["mutat.pdf (lipsește)", "Proiect", "dosar.pdf"]
    with qtbot.waitSignal(launcher.project_requested) as signal:
        launcher.recent_list.itemActivated.emit(launcher.recent_list.item(1))
    assert signal.args == [project.resolve()]
    with qtbot.waitSignal(launcher.pdf_requested) as signal:
        launcher.recent_list.itemActivated.emit(launcher.recent_list.item(2))
    assert signal.args == [pdf.resolve()]


def test_moved_file_can_be_located(launcher, ctx, tmp_path, monkeypatch):
    add_recent(ctx, tmp_path, "vechi.pdf", "pdf", exists=False)
    new = tmp_path / "nou.pdf"
    new.write_bytes(b"x")
    monkeypatch.setattr(Launcher, "pick_moved_file", lambda self, doc: new)
    launcher.show_task("recent")
    launcher.open_recent(launcher.recent_list.item(0).data(ROLE))
    assert launcher.recent_list.item(0).text() == "nou.pdf"


def test_T_A103_2_search_and_A104_A105(launcher, ctx, tmp_path, monkeypatch):
    add_recent(ctx, tmp_path, "Cerere Brașov.pdf", "pdf")
    add_recent(ctx, tmp_path, "Ofertă.pdf", "pdf")
    launcher.show_task("recent")
    launcher.recent_search.setText("brasov")
    assert launcher.recent_list.count() == 1
    launcher.recent_search.setText("")
    launcher.remove_recent(launcher.recent_list.item(0).data(ROLE))
    assert launcher.recent_list.count() == 1 and (tmp_path / "Ofertă.pdf").exists()
    monkeypatch.setattr(Launcher, "confirm_clear", lambda self: False)
    assert not launcher.clear_recent() and launcher.recent_list.count() == 1
    monkeypatch.setattr(Launcher, "confirm_clear", lambda self: True)
    assert launcher.clear_recent() and not launcher.recent_empty.isHidden()


def test_T_A107_1_to_A109_1_mobile_folder(launcher, ctx, tmp_path, qtbot):
    folder = tmp_path / "telefon"
    folder.mkdir()
    (folder / "chitanta.pdf").write_bytes(b"%PDF")
    time.sleep(0.05)
    album = folder / "poze"
    album.mkdir()
    for name in ("b.jpg", "a.jpg", "nota.txt"):
        (album / name).write_bytes(b"x")
    launcher.select_mobile_folder(folder)
    launcher.show_task("mobile")
    assert launcher.mobile_list.count() == 2
    assert launcher.mobile_items()[0].name == "poze"  # A-108: cel mai nou primul
    with qtbot.waitSignal(launcher.convert_requested) as signal:
        launcher.open_mobile(album)
    assert signal.args[0] == "pdf" and [p.name for p in signal.args[1]] == ["a.jpg", "b.jpg"]
    with qtbot.waitSignal(launcher.pdf_requested):
        launcher.open_mobile(folder / "chitanta.pdf")
    shutil.rmtree(folder)
    launcher.refresh_mobile()  # A-107: folder sters → se cere din nou
    assert ctx.settings.get("launcher.mobile_folder") is None
    assert launcher.mobile_folder.text() == "Niciun folder ales"
