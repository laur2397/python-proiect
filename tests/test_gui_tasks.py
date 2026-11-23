"""Faza 13, pasul 13.3: sarcinile automate in interfata (T-001…T-021, T-100…T-107)."""

from __future__ import annotations

import os

import pytest
from test_automated_tasks import ScriptEngine
from test_hotfolder import _image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from app.core.automation.tasks import AutomatedTaskRunner, builtin_name
from app.core.context import AppContext
from app.core.paths import AppPaths
from app.gui.i18n import tr
from app.gui.tasks_window import TaskEditor, TasksManager, task_title


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def runner(ctx):
    return AutomatedTaskRunner(ctx, engine=ScriptEngine())


@pytest.fixture
def manager(qtbot, runner):
    m = TasksManager(runner)
    qtbot.addWidget(m)
    m.confirm = lambda text: True
    return m


def test_T_T001_T002_manager_lists_tasks_with_toolbar(manager):
    assert manager.list.count() == 9
    assert manager.list.item(0).text() == tr("task.builtin.convert_pdf")
    assert [a.objectName() for a in manager.toolbar.actions()] == [
        "tasks_new", "tasks_modify", "tasks_copy", "tasks_delete", "tasks_import",
        "tasks_export", "tasks_run"]
    # T-003: o sarcina livrata nu se modifica si nu se sterge
    assert not manager.actions["modify"].isEnabled()
    assert not manager.actions["delete"].isEnabled()
    assert manager.actions["copy"].isEnabled()


def test_T_T003_copy_builtin_gets_translated_name(manager, runner):
    manager.select(builtin_name("convert_word"))
    copy = manager.copy_task()
    assert copy.name == tr("task.builtin.convert_word")
    assert manager.selected().name == copy.name and manager.actions["modify"].isEnabled()
    assert manager.delete_task()
    assert copy.name not in [t.name for t in runner.all_tasks()]


def test_T_T100_T105_editor_layout_and_first_step(qtbot, runner):
    editor = TaskEditor(runner)
    qtbot.addWidget(editor)
    assert editor.hint.text() == tr("tasks.editor.choose_first")  # T-104
    assert editor.config.currentWidget() is editor.hint
    assert not any(w.isEnabled() for w in editor.groups.values())  # T-103
    assert [editor.help.text(), editor.finish_button.text()] == [
        tr("tasks.editor.help"), tr("tasks.editor.finish")]  # T-105
    editor.choose_project("new")  # T-101
    assert editor.project_buttons["new"].isChecked()
    assert all(w.isEnabled() for w in editor.groups.values())
    assert editor.steps.count() == 1


def test_T_T010_T017_T018_editor_rules_and_finish(qtbot, runner, tmp_path):
    editor = TaskEditor(runner)
    qtbot.addWidget(editor)
    editor.choose_project("new")
    editor.groups["ocr"].click()  # T-010: OCR aduce analiza
    assert [s.step_type for s in editor.task.steps] == ["get_images", "analyze", "recognize"]
    editor.steps.setCurrentRow(0)
    editor.remove_current()  # T-017
    assert editor.message.text() == tr("tasks.error.first_step", n=1)
    editor.name.setText("Dosare Word")
    assert not editor.finish()  # T-018: lipseste salvarea
    assert editor.message.text() == tr("tasks.error.no_output", n=4)
    editor.save_actions[("save", "document")].trigger()
    panel = editor.current_panel()
    panel.fields["format"].setCurrentIndex(panel.fields["format"].findData("docx"))
    panel.fields["folder"].setText(str(tmp_path / "out"))
    assert editor.finish()
    saved = runner.task("Dosare Word")
    assert saved.steps[-1].parameters["format"] == "docx"
    assert saved.steps[-1].parameters["folder"] == str(tmp_path / "out")


def test_T_T020_shortcut_conflict_in_editor(qtbot, runner, tmp_path):
    from PySide6.QtGui import QKeySequence

    runner.set_shortcut(builtin_name("convert_pdf"), "Ctrl+Alt+1")
    editor = TaskEditor(runner)
    qtbot.addWidget(editor)
    editor.choose_project("new")
    editor.save_actions[("save", "images")].trigger()
    editor.name.setText("Imagini")
    editor.shortcut.setKeySequence(QKeySequence("Ctrl+Alt+1"))
    assert not editor.finish()
    assert editor.message.text() == tr("tasks.error.shortcut", shortcut="Ctrl+Alt+1")


def test_T_T005_new_and_modify_through_manager(manager, runner, tmp_path):
    def fill(dialog):
        dialog.choose_project("new")
        dialog.save_actions[("save", "images")].trigger()
        dialog.name.setText("Imagini TIFF")
        return dialog.finish()
    manager.exec_dialog = fill
    created = manager.new_task()
    assert created.name == "Imagini TIFF" and manager.selected().name == "Imagini TIFF"

    def rename(dialog):
        dialog.name.setText("Imagini scanate")
        return dialog.finish()
    manager.exec_dialog = rename
    assert manager.modify_task().name == "Imagini scanate"
    assert "Imagini TIFF" not in [t.name for t in runner.all_tasks()]


def test_T_T021_export_and_import_from_manager(manager, runner, tmp_path):
    manager.select(builtin_name("convert_excel"))
    path = tmp_path / "excel.dltask"
    manager.pick_save = lambda name: path
    assert manager.export_task() == path and path.exists()
    manager.pick_open = lambda: path
    imported = manager.import_task()
    assert not imported.is_builtin and manager.selected().name == imported.name
    (tmp_path / "rau.dltask").write_text("{}", encoding="utf-8")
    manager.pick_open = lambda: tmp_path / "rau.dltask"
    assert manager.import_task() is None and manager.message.text()


def test_T_T019_run_from_application(qtbot, ctx, tmp_path):
    from app.gui.application import Application

    app = Application(ctx)
    app.ocr_engine = ScriptEngine()
    app.quiet = True
    files = [_image(tmp_path / "in" / "cerere.png")]
    name = builtin_name("convert_searchable_pdf")
    result = app.run_automated_task(name, files)
    assert result[0][2] is None and result[0][1].suffix == ".pdf"
    assert result[0][1].parent == tmp_path / "in"  # folderul gol = langa original
    assert tr("tasks.run_done", count=1, files=str(result[0][1])) in app.last_task_message
    manager = app.open_automated_tasks()
    assert manager.list.count() == 9
    manager.close()


def test_T_T019_launcher_card_and_ocr_editor_menu(qtbot, ctx):
    from app.gui.application import Application

    app = Application(ctx)
    launcher = app.launcher
    qtbot.addWidget(launcher)
    assert launcher.cards["automated_tasks"].text().startswith(
        tr("launcher.card.automated_tasks"))
    editor = app.editor
    qtbot.addWidget(editor)
    tools = [a.objectName() for a in editor.menus["tools"].actions()]
    assert tools[:3] == ["compare_documents", "automated_tasks", "hot_folder"]
    assert editor.actions["hot_folder"].shortcut().toString() == "Ctrl+Shift+F"  # S-002
    opened = []
    launcher.automated_tasks_requested.disconnect()
    launcher.automated_tasks_requested.connect(lambda: opened.append("tasks"))
    launcher.cards["automated_tasks"].click()
    assert opened == ["tasks"]


def test_T_T020_task_shortcut_runs_in_ocr_editor(qtbot, ctx):
    from app.gui.application import Application

    app = Application(ctx)
    app.task_runner.set_shortcut(builtin_name("convert_word"), "Ctrl+Alt+7")
    editor = app.editor
    qtbot.addWidget(editor)
    runs = []
    editor.task_run_requested.disconnect()  # fara rularea reala (dialogul de fisiere)
    editor.task_run_requested.connect(runs.append)
    from PySide6.QtWidgets import QWidget

    [action] = [a for a in QWidget.actions(editor)
                if a.objectName() == "task_shortcut_Ctrl+Alt+7"]
    action.trigger()
    assert runs == [builtin_name("convert_word")]
    assert task_title(builtin_name("convert_word")) == tr("task.builtin.convert_word")
