"""Sarcinile automate: cerintele T fara test pana acum: proiectul (T-006),
sursa imaginilor (T-007), analiza (T-009), trimiterea (T-012, T-013, T-015),
grupurile editorului (T-102) si analiza manuala (T-106)."""

from __future__ import annotations

import os

import pytest
from test_automated_tasks import ScriptEngine, _task, ctx, files, runner  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.automation.tasks import (
    ANALYZE_MODES,
    IMAGE_SOURCES,
    PROJECT_MODES,
    SEND_KINDS,
)
from app.core.errors import TaskValidationError
from app.core.layout.areas import AreaEditor
from app.core.model import AreaType
from app.core.project import OcrProject


def _save(folder):
    return ("save", {"kind": "document", "format": "txt", "folder": str(folder)})


def test_T_T006_project_new_existing_current(runner, ctx, files, tmp_path):  # noqa: F811
    assert PROJECT_MODES == ("new", "existing", "current")
    existing = tmp_path / "existent"
    project = OcrProject.create(context=ctx)
    project.add_images(files[:1])
    project.save(existing)
    project.close()
    task = _task("Existent", ("get_images", {"project": "existing",
                                             "project_path": str(existing)}),
                 ("analyze", {}), ("recognize", {}), _save(tmp_path / "out"))
    runner.run(task, files[1:])
    reopened = OcrProject.open(existing, context=ctx)
    try:
        assert len(reopened.pages) == 2  # paginile noi intra in proiectul ales
    finally:
        reopened.close()


def test_T_T007_sources_files_or_scan(runner, files, tmp_path):  # noqa: F811
    assert IMAGE_SOURCES == ("files", "scan")
    for source in IMAGE_SOURCES:  # `Scan`: interfata scaneaza si da fisierele
        task = _task(f"Sursa {source}", ("get_images", {"source": source}), ("analyze", {}),
                     ("recognize", {}), _save(tmp_path / source))
        runner.run(task, files[:1])
        assert runner.last_run.outputs


def test_T_T009_analyze_modes(runner, ctx, files, tmp_path):  # noqa: F811
    assert ANALYZE_MODES == ("auto", "manual", "template")
    project = OcrProject.create(context=ctx)
    project.add_images(files[:1])
    project.analyze_pages([1])
    AreaEditor(project).save_template(project.page(1), tmp_path / "s.blkx", "Cerere")
    project.close()
    task = _task("Sablon", ("get_images", {}), ("analyze", {"mode": "template",
                                                            "template": "Cerere"}),
                 ("recognize", {}), _save(tmp_path / "out"))
    result = runner.run(task, files[1:])
    assert result[0][2] is None and runner.last_run.outputs
    missing = _task("Fara", ("get_images", {}), ("analyze", {"mode": "template"}),
                    ("recognize", {}), _save(tmp_path / "out"))
    with pytest.raises(TaskValidationError):  # sablonul se cere inainte de pornire
        runner.run(missing, files[:1])


@pytest.mark.parametrize("kind", SEND_KINDS)
def test_T_T012_T013_T015_send_steps(runner, files, tmp_path, kind):  # noqa: F811
    task = _task("Trimite", ("get_images", {}), ("analyze", {}), ("recognize", {}),
                 ("save", {"kind": "document", "format": "docx",
                           "folder": str(tmp_path / "out")}),
                 ("send_to", {"kind": kind, "app": "editor" if kind == "app" else None}))
    runner.run(task, files[:1])
    [(sent_kind, app, sent)] = runner.last_run.sent
    assert sent_kind == kind and sent == runner.last_run.outputs
    assert app == ("editor" if kind == "app" else None)


def test_T_T102_editor_groups_in_order(qtbot, runner):  # noqa: F811
    pytest.importorskip("PySide6")
    from app.gui.tasks_window import TaskEditor

    editor = TaskEditor(runner)
    qtbot.addWidget(editor)
    # `Open image or PDF` si `Scan`; apoi `Analyze`; apoi `OCR`; apoi `Save/Send ▾`
    assert list(editor.groups) == ["open", "scan", "preprocess", "analyze", "ocr", "save"]


def test_T_T106_manual_analysis_waits_for_the_user(runner, files, tmp_path):  # noqa: F811
    task = _task("Manual", ("get_images", {}), ("analyze", {"mode": "manual"}),
                 ("recognize", {}), _save(tmp_path / "out"))
    waited = []

    def draw(project):  # utilizatorul deseneaza zonele, apoi sarcina continua
        waited.append(project.pages[0].status)
        AreaEditor(project).create(project.page(1), [(50, 50), (900, 50), (900, 400),
                                                     (50, 400)], AreaType.TEXT)

    result = runner.run(task, files[:1], wait_for_areas=draw)
    assert len(waited) == 1 and result[0][2] is None and runner.last_run.outputs
