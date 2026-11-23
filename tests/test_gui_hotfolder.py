"""Faza 13, pasul 13.4: Hot Folder in interfata (S-002…S-004, S-015…S-020,
S-060…S-071, S-200…S-217)."""

from __future__ import annotations

import os

import pytest
from test_automated_tasks import ScriptEngine
from test_hotfolder import _image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from app.core.automation.hotfolder import FILE_TYPES, HotFolderStep, HotFolderTask
from app.core.context import AppContext
from app.core.paths import AppPaths
from app.gui.hotfolder_window import (
    COLUMNS,
    HotFolderWindow,
    LogDialog,
    TaskSettingsDialog,
)
from app.gui.i18n import tr


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx):
    w = HotFolderWindow(ctx, engine=ScriptEngine())
    qtbot.addWidget(w)
    w.confirm = lambda text: True
    yield w
    w.shutdown()


def _saved(window, tmp_path, name="Dosare"):
    (tmp_path / "in").mkdir(exist_ok=True)
    window.service.save(HotFolderTask(name, "folder", str(tmp_path / "in"), steps=[
        HotFolderStep("save", {}, "docx", str(tmp_path / "out"))]))
    window.refresh()
    window.select(name)


def test_T_S200_toolbar_and_S003_columns(window):
    names = [a.objectName() for a in window.toolbar.actions() if a.objectName()]
    assert names == ["hf_new", "hf_start_now", "hf_start_schedule", "hf_stop", "hf_modify",
                     "hf_copy", "hf_delete", "hf_logging", "hf_notifications", "hf_log"]
    assert window.findChild(object, "hf_import_export") is not None
    headers = [window.table.horizontalHeaderItem(i).text() for i in range(len(COLUMNS))]
    assert headers == [tr(f"hotfolder.col.{c}") for c in COLUMNS]
    assert window.actions["logging"].isCheckable() and window.actions["logging"].isChecked()


def test_T_S202_status_bar_counter(window, ctx):
    assert window.counter.text() == tr("hotfolder.counter", pages=5000, days=30)
    assert window.counter_info.toolTip() == tr("hotfolder.counter.info")
    ctx.settings.set("hotfolder.monthly_page_limit", 0)
    window.refresh()
    assert window.counter.text() == tr("hotfolder.counter.unlimited")


def test_T_S201_row_and_S017_statuses(window, tmp_path):
    _saved(window, tmp_path)
    assert window.table.item(0, 0).text() == "Dosare"
    assert window.table.item(0, 2).text() == tr("hotfolder.status.stopped")
    window.start_schedule()
    assert window.table.item(0, 2).text() == tr("hotfolder.status.watching")
    assert window.table.item(0, 3).text()  # `Next Start Time`
    assert not window.actions["modify"].isEnabled()  # S-062
    window.stop_task()
    assert window.table.item(0, 2).text() == tr("hotfolder.status.stopped")


def test_T_S060_S066_start_now_and_notification(window, tmp_path):
    _saved(window, tmp_path)
    _image(tmp_path / "in" / "cerere.png")
    summary = window.start_now()
    assert summary.files == 1 and (tmp_path / "out" / "cerere.docx").exists()
    assert window.table.item(0, 2).text() == tr("hotfolder.status.completed")
    assert window.notifications == [tr("hotfolder.notify.done", task="Dosare", files=1,
                                       pages=1, errors=0)]
    window.actions["notifications"].trigger()  # comutatorul (S-066)
    assert window.context.settings.get("hotfolder.notifications") is False


def test_T_S070_log_dialog(window, tmp_path, qtbot):
    _saved(window, tmp_path)
    _image(tmp_path / "in" / "a.png")
    window.start_now()
    dialog = window.view_log()
    qtbot.addWidget(dialog)
    assert isinstance(dialog, LogDialog) and dialog.table.rowCount() == 1
    assert dialog.table.item(0, 2).text() == tr("hotfolder.log.status.success")
    assert dialog.open_button.isEnabled()  # S-068: fisierul TXT exista


def test_T_S063_S064_S065_copy_delete_export_import(window, tmp_path):
    _saved(window, tmp_path)
    copy = window.copy_task()
    assert copy.name == "Dosare (2)" and window.table.rowCount() == 2
    assert window.delete_task() and window.table.rowCount() == 1
    path = tmp_path / "x.hft"
    window.pick_save = lambda name: path
    window.select("Dosare")
    assert window.export_task() == path
    window.pick_open = lambda: path
    assert window.import_task().name == "Dosare (2)"


def test_T_S204_S208_S217_dialog_and_create_task(qtbot, window, ctx, tmp_path):
    dialog = TaskSettingsDialog(window.service, ctx)
    qtbot.addWidget(dialog)
    assert dialog.placeholder.text() == tr("hotfolder.select_steps")  # S-208
    assert not dialog.create_button.isEnabled()  # S-217: gri pana e valida
    # S-205: FTP si Outlook sunt in paleta, dezactivate; S-206: SharePoint la fel
    assert not dialog.palette_buttons["ftp"].isEnabled()
    assert not dialog.palette_buttons["outlook"].isEnabled()
    assert [a.text() for a in dialog.save_actions.values()] == [
        tr(f"hotfolder.palette.save_{k}") for k in ("document", "sharepoint", "images",
                                                     "project")]
    assert not dialog.save_actions["sharepoint"].isEnabled()
    dialog.name.setText("Facturi")
    dialog.add_step("recurring")
    folder = dialog.add_step("folder")
    (tmp_path / "in").mkdir()
    folder.path.setText(str(tmp_path / "in"))
    dialog.add_step("process")
    save = dialog.add_save("document")
    save.folder.setText(str(tmp_path / "out"))
    assert dialog.boxes[0].title.text() == tr(
        "hotfolder.step_n", n=1, name=tr("hotfolder.palette.recurring"))  # S-207
    assert dialog.create_button.isEnabled()
    assert dialog.create_task()
    task = window.service.task("Facturi")
    assert task.schedule_kind == "interval" and task.steps[0].output_format == "pdf"


def test_T_S209_recurring_choices(qtbot, window, ctx):
    dialog = TaskSettingsDialog(window.service, ctx)
    qtbot.addWidget(dialog)
    box = dialog.add_step("recurring")
    assert [r.text() for r in box.radios.values()] == [
        tr(f"hotfolder.recurring.{k}") for k in ("interval", "daily", "weekly", "monthly")]
    box.radios["weekly"].setChecked(True)
    box.weekday.setCurrentIndex(4)
    task = dialog.build()
    assert task.schedule_kind == "weekly" and task.schedule_days == (4,)
    once = dialog.add_step("once")  # inlocuieste planificarea recurenta
    assert dialog.box("recurring") is None and dialog.box("once") is once


def test_T_S211_file_types_and_S213_blank_pages(qtbot, window, ctx):
    dialog = TaskSettingsDialog(window.service, ctx)
    qtbot.addWidget(dialog)
    folder = dialog.add_step("folder")
    assert folder.types.count() == len(FILE_TYPES) == 15
    assert folder.types.itemText(1) == tr("hotfolder.file_type.images_pdf")
    process = dialog.add_step("process")
    assert not process.move_blank.isEnabled()  # S-045: activ doar cu S-044
    process.delete_blank.setChecked(True)
    assert process.move_blank.isEnabled()


def test_T_S216_name_macros_and_live_example(qtbot, window, ctx):
    from datetime import datetime

    dialog = TaskSettingsDialog(window.service, ctx)
    qtbot.addWidget(dialog)
    save = dialog.add_save("document")
    assert list(save.macro_buttons) == ["[F]", "[X]", "[D]", "[T]", "[#]"]
    save.name.setText("")
    save.macro_buttons["[F]"].click()
    save.name.insert("_")
    save.macro_buttons["[D]"].click()
    day = datetime.now().strftime("%Y-%m-%d")
    assert save.example.text() == tr("hotfolder.example", name=f"Document_{day}.pdf")
    save.format.setCurrentIndex(save.format.findData("docx"))
    assert save.example.text().endswith(".docx")
    assert not save.image_pdf.isEnabled()  # S-046: numai pentru PDF


def test_T_S062_modify_existing_task(qtbot, window, tmp_path):
    _saved(window, tmp_path)

    def change(dialog):
        dialog.name.setText("Dosare noi")
        return dialog.create_task()
    window.exec_dialog = change
    assert window.modify_task().name == "Dosare noi"
    assert [t.name for t in window.service.tasks()] == ["Dosare noi"]


def test_T_S002_application_opens_hot_folder_and_autostart(qtbot, ctx, tmp_path):
    from app.gui.application import Application

    app = Application(ctx)
    assert app.start_hot_folder() is None  # nicio sarcina: nimic de pornit
    window = app.open_hot_folder()
    qtbot.addWidget(window)
    assert window.isVisible()
    _saved(window, tmp_path)
    assert app.start_hot_folder() is window
    ctx.settings.set("hotfolder.autostart", False)  # S-071
    assert app.start_hot_folder() is None
    window.shutdown()
