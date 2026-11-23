"""Hot Folder: cerintele S fara test pana acum: instalarea (S-001), coloanele
(S-003), locul sarcinilor (S-008), statusurile `Stopped` si `Completed` (S-018,
S-019, S-061), pasul de procesare (S-039…S-043, S-212, S-213), iesirea si numele
(S-048, S-051, S-215) si jurnalizarea (S-067)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pytest
from test_automated_tasks import ScriptEngine
from test_hotfolder import Clock, _image, _task

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from app.core.automation.hotfolder import (
    HFT_SUFFIX,
    HotFolderService,
    display_status,
    expand_name,
)
from app.core.context import AppContext
from app.core.errors import TaskValidationError
from app.core.paths import AppPaths
from app.gui.hotfolder_window import COLUMNS, HotFolderWindow, TaskSettingsDialog
from app.gui.i18n import tr

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def clock():
    return Clock(datetime.now().replace(microsecond=0))


@pytest.fixture
def service(ctx, clock):
    return HotFolderService(ctx, engine=ScriptEngine(), clock=clock)


@pytest.fixture
def window(qtbot, ctx):
    w = HotFolderWindow(ctx, engine=ScriptEngine())
    qtbot.addWidget(w)
    w.confirm = lambda text: True
    yield w
    w.shutdown()


def test_T_S001_installed_by_default_optional_in_custom_setup():
    iss = (ROOT / "packaging" / "doculens.iss").read_text(encoding="utf-8")
    assert 'Name: "hotfolder"; Description: "DocuLens Hot Folder"; Types: full' in iss
    assert 'Flags: iscustom' in iss  # instalarea personalizata il poate scoate
    assert '--action hot_folder"; Components: hotfolder' in iss
    source = (ROOT / "app" / "gui" / "application.py").read_text(encoding="utf-8")
    assert 'action == "hot_folder"' in source


def test_T_S001_start_menu_action_opens_hot_folder(qtbot, ctx, monkeypatch):
    from app.gui.application import Application

    application = Application(ctx)
    opened = []
    monkeypatch.setattr(Application, "open_hot_folder", lambda self: opened.append(1))
    application.run_action("hot_folder", [])
    assert opened == [1]


def test_T_S003_columns():
    assert {"path", "status", "next_start"} <= set(COLUMNS)


def test_T_S008_tasks_kept_per_user_and_exported_as_hft(service, ctx, tmp_path):
    service.save(_task(tmp_path))
    rows = ctx.app_db.execute("SELECT name FROM hot_folder_task").fetchall()
    assert rows == [("Dosare",)]  # in profilul utilizatorului (app.db), decizia 3
    target = tmp_path / f"Dosare{HFT_SUFFIX}"
    service.export_task("Dosare", target)
    assert json.loads(target.read_text(encoding="utf-8"))["format"] == "doculens-hotfolder"


def test_T_S018_S061_stop_finishes_current_file(service, tmp_path):
    for name in ("a.png", "b.png", "c.png"):
        _image(tmp_path / "in" / name)
    service.save(_task(tmp_path))
    service.start("Dosare")
    done = []

    def progress(p):
        done.append(p)
        service.stop("Dosare")  # apasat in timpul primului fisier

    summary = service.run_now("Dosare", progress=progress)
    assert summary.stopped and summary.files == 1  # fisierul curent s-a terminat
    assert display_status(service.task("Dosare")) == "stopped"


def test_T_S019_completed_after_processing(service, tmp_path):
    _image(tmp_path / "in" / "a.png")
    service.save(_task(tmp_path))
    service.run_now("Dosare")
    assert display_status(service.task("Dosare")) == "completed"
    assert tr("hotfolder.status.completed")


def test_T_S039_at_least_one_language(service, tmp_path):
    task = _task(tmp_path)
    task.process = {"mode": "recognize", "languages": []}
    with pytest.raises(TaskValidationError):
        service.validate(task)


def test_T_S040_S043_processing_modes_and_template(qtbot, window, ctx, service, tmp_path):
    dialog = TaskSettingsDialog(window.service, ctx)
    qtbot.addWidget(dialog)
    process = dialog.add_step("process")
    assert list(process.mode_radios) == ["recognize", "analyze", "preprocess"]
    asked = []
    process.options_requested.connect(asked.append)
    from PySide6.QtWidgets import QPushButton

    for key in ("recognition_options", "preprocessing_options"):  # S-041, S-042
        process.findChild(QPushButton, f"hf_{key}").click()
    assert asked == ["ocr", "image"]
    task = _task(tmp_path)
    task.process = {"mode": "recognize", "languages": ["ron"], "template": "lipsa"}
    with pytest.raises(TaskValidationError):  # S-043: sablonul trebuie sa existe
        service.validate(task)


def test_T_S212_S213_processing_step_groups(qtbot, window, ctx):
    dialog = TaskSettingsDialog(window.service, ctx)
    qtbot.addWidget(dialog)
    process = dialog.add_step("process")
    assert process.languages.objectName() == "hf_languages"
    assert process.template_check.text() == tr("hotfolder.field.use_template")
    assert process.delete_blank.text() == tr("hotfolder.field.delete_blank")
    assert process.move_blank.text() == tr("hotfolder.field.move_blank")


def test_T_S048_S051_S215_output_and_file_name(qtbot, window, ctx):
    dialog = TaskSettingsDialog(window.service, ctx)
    qtbot.addWidget(dialog)
    save = dialog.add_save("document")
    assert [save.output.itemData(i) for i in range(save.output.count())] == [
        "per_file", "per_folder", "single"]  # S-048: un document per fisier, primul
    assert save.text_pdf.isChecked() and save.image_pdf is not None
    assert save.format is not None and save.folder is not None
    when = datetime(2026, 11, 24, 9, 30)
    assert expand_name("[F]_[D]", Path("cerere.png"), when, 1) == "cerere_2026-11-24"


def test_T_S067_logging_toggle(window, ctx):
    action = window.actions["logging"]
    assert action.isCheckable()
    action.trigger()
    assert ctx.settings.get("hotfolder.logging") is False
    action.trigger()
    assert ctx.settings.get("hotfolder.logging") is True
