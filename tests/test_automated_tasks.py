"""Faza 13, pasul 13.1: nucleul sarcinilor automate (T-001…T-021)."""

from __future__ import annotations

import json

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.automation.tasks import (
    BUILTIN_TASKS,
    AutomatedTask,
    AutomatedTaskRunner,
    TaskStep,
    add_step,
    builtin_name,
    remove_step,
    validate_steps,
)
from app.core.context import AppContext
from app.core.errors import (
    BuiltinNotEditableError,
    CoreError,
    ProjectVersionError,
    ShortcutConflictError,
    TaskValidationError,
)
from app.core.model import BlockData, LineData, PageStatus, Rect, WordData
from app.core.ocr.engine import RecognitionResult
from app.core.paths import AppPaths


class ScriptEngine:
    """Motor fals: textul fiecarei zone e numele fisierului-sursa."""

    name = "fals"

    def __init__(self):
        self.pages = []
        """Paginile recunoscute (fara probele de limba, N-013)."""

    def recognize_area(self, page, area, settings, cancel=None):
        if area.id is not None:
            self.pages.append(page.page_number)
        text = page.source_file.stem if page.source_file else f"pagina{page.page_number}"
        box = area.bbox
        word = WordData(None, text, 95.0, bbox=Rect(box.x, box.y, max(box.w, 10), max(box.h, 10)))
        block = BlockData(None, lines=[LineData(None, words=[word], bbox=word.bbox)],
                          bbox=word.bbox)
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=95.0,
                                 area_blocks={area.id: [block]})

    def recognize_page(self, page, settings, cancel=None):
        result = RecognitionResult(page.page_number, avg_confidence=95.0)
        for a in page.areas:
            part = self.recognize_area(page, a, settings)
            result.blocks += part.blocks
            result.area_blocks.update(part.area_blocks)
        return result


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def runner(ctx):
    return AutomatedTaskRunner(ctx, engine=ScriptEngine())


@pytest.fixture
def files(tmp_path):
    out = []
    for name in ("cerere", "anexa"):
        img = Image.new("L", (1200, 1600), 255)
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default(size=36)
        for row in range(6):
            draw.text((100, 120 + row * 60), "Beneficiarul depune cererea de plata", fill=0,
                      font=font)
        img.save(tmp_path / f"{name}.png", dpi=(300, 300))
        out.append(tmp_path / f"{name}.png")
    return out


def _task(name, *steps):
    return AutomatedTask(name, [TaskStep(k, dict(p)) for k, p in steps])


def _word_task(name, folder):
    return _task(name, ("get_images", {"project": "new", "source": "files"}),
                 ("analyze", {"mode": "auto"}), ("recognize", {}),
                 ("save", {"kind": "document", "format": "docx", "folder": str(folder)}))


def test_T_T001_T004_builtin_tasks_listed_first_in_order(runner):
    names = [t.name for t in runner.all_tasks()]
    assert names[:9] == [builtin_name(k) for k in BUILTIN_TASKS]
    assert list(BUILTIN_TASKS) == ["convert_pdf", "convert_searchable_pdf", "convert_word",
                                   "convert_excel", "convert_photo_word", "scan_pdf",
                                   "scan_word", "scan_excel", "scan_images"]
    assert all(t.is_builtin for t in runner.builtin_tasks())
    for task in runner.builtin_tasks():
        validate_steps(task.steps)  # toate sunt coerente
    scan = runner.task(builtin_name("scan_pdf"))
    assert scan.steps[0].parameters["source"] == "scan"


def test_T_T003_builtin_not_edited_or_deleted_but_duplicated(runner):
    name = builtin_name("convert_word")
    task = runner.task(name)
    with pytest.raises(BuiltinNotEditableError):
        runner.save(task)
    with pytest.raises(BuiltinNotEditableError):
        runner.delete(name)
    with pytest.raises(TaskValidationError):
        runner.duplicate(name)  # copia unei sarcini livrate are nevoie de nume
    copy = runner.duplicate(name, "Word pentru dosare")
    assert not copy.is_builtin and [s.step_type for s in copy.steps] == \
        [s.step_type for s in task.steps]
    again = runner.duplicate("Word pentru dosare")
    assert again.name == "Word pentru dosare (2)"


def test_T_T005_unique_nonempty_name_and_rename(runner, tmp_path):
    runner.save(_word_task("Dosar", tmp_path))
    with pytest.raises(TaskValidationError) as caught:
        runner.save(_word_task("", tmp_path))
    assert caught.value.params["reason"] == "name"
    renamed = _word_task("Dosar nou", tmp_path)
    runner.save(renamed, previous_name="Dosar")
    names = [t.name for t in runner.all_tasks()]
    assert "Dosar nou" in names and "Dosar" not in names
    runner.save(_word_task("Altul", tmp_path))
    with pytest.raises(TaskValidationError) as caught:
        runner.save(_word_task("Altul", tmp_path), previous_name="Dosar nou")
    assert caught.value.params["reason"] == "name_taken"
    runner.delete("Altul")
    assert "Altul" not in [t.name for t in runner.all_tasks()]


def test_T_T010_recognize_brings_analyze_and_removing_analyze_drops_recognize():
    task = _task("x", ("get_images", {}))
    add_step(task, TaskStep("recognize"))
    assert [s.step_type for s in task.steps] == ["get_images", "analyze", "recognize"]
    add_step(task, TaskStep("save", {"kind": "document", "format": "pdf"}))
    remove_step(task, 1)
    assert [s.step_type for s in task.steps] == ["get_images", "save"]


def test_T_T017_first_step_cannot_be_removed():
    task = _task("x", ("get_images", {}), ("save", {"kind": "images", "format": "png"}))
    with pytest.raises(TaskValidationError):
        remove_step(task, 0)


@pytest.mark.parametrize(("steps", "reason", "index"), [
    ([("analyze", {})], "first_step", 0),
    ([("get_images", {})], "no_output", 1),
    ([("get_images", {}), ("recognize", {})], "recognize_needs_analyze", 1),
    ([("get_images", {}), ("save", {"kind": "document", "format": "docx"})],
     "save_needs_recognize", 1),
    ([("get_images", {}), ("send_to", {"kind": "email_document"})], "send_needs_save", 1),
    ([("get_images", {}), ("save", {"kind": "images", "format": "png", "multipage": True})],
     "multipage", 1),
    ([("get_images", {"project": "existing"}),
      ("save", {"kind": "images", "format": "png"})], "project_path", 0),
    ([("get_images", {}), ("analyze", {"mode": "template"}), ("recognize", {}),
      ("save", {"kind": "document", "format": "pdf"})], "template", 1),
])
def test_T_T018_incoherent_steps_say_which_step(steps, reason, index):
    with pytest.raises(TaskValidationError) as caught:
        validate_steps([TaskStep(k, dict(p)) for k, p in steps])
    assert caught.value.params == {"step_index": index, "reason": reason}


def test_T_T014_multipage_only_for_listed_formats():
    ok = [TaskStep("get_images"), TaskStep("save", {"kind": "images", "format": "tiff",
                                                    "multipage": True})]
    validate_steps(ok)
    image_only = [TaskStep("get_images"), TaskStep("save", {"kind": "document",
                                                            "format": "pdf",
                                                            "image_only": True})]
    validate_steps(image_only)  # PDF doar-imagine nu cere recunoastere


def test_T_T020_shortcut_conflicts(runner, ctx, tmp_path):
    from app.core.shortcuts import ShortcutStore

    runner.save(_word_task("Dosar", tmp_path))
    runner.set_shortcut("Dosar", "Ctrl+Alt+1")
    assert runner.task("Dosar").shortcut == "Ctrl+Alt+1"
    with pytest.raises(ShortcutConflictError):
        runner.set_shortcut(builtin_name("convert_pdf"), "Ctrl+Alt+1")
    ShortcutStore(ctx.app_db).register([("ocr.recognize", "action.recognize", "recognize",
                                         "Ctrl+Shift+R")])
    with pytest.raises(ShortcutConflictError):
        runner.set_shortcut("Dosar", "Ctrl+Shift+R")
    runner.set_shortcut(builtin_name("convert_pdf"), "Ctrl+Alt+2")  # si la cele livrate
    runner.set_shortcut("Dosar", None)
    assert runner.task("Dosar").shortcut is None


def test_T_T021_export_import_and_version(runner, tmp_path):
    runner.save(_word_task("Dosar", tmp_path))
    path = tmp_path / "dosar.dltask"
    runner.export_task("Dosar", path)
    imported = runner.import_task(path)
    assert imported.name == "Dosar (2)"
    assert [s.step_type for s in imported.steps] == ["get_images", "analyze", "recognize",
                                                    "save"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["format_version"] = 99
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ProjectVersionError):
        runner.import_task(path)
    (tmp_path / "rau.dltask").write_text("nu e json", encoding="utf-8")
    with pytest.raises(CoreError):
        runner.import_task(tmp_path / "rau.dltask")
    runner.export_task(builtin_name("convert_pdf"), tmp_path / "pdf.dltask")
    copy = runner.import_task(tmp_path / "pdf.dltask")
    assert not copy.is_builtin and copy.name == "pdf"


def test_T_T019_run_converts_files_into_one_document(runner, files, tmp_path):
    from docx import Document

    out = tmp_path / "out"
    result = runner.run(_word_task("Dosar", out), files)
    written = runner.last_run.outputs
    assert len(written) == 1 and written[0].suffix == ".docx"
    assert [(i, o, e) for i, o, e in result] == [(f, written[0], None) for f in files]
    text = "\n".join(p.text for p in Document(written[0]).paragraphs)
    assert "cerere" in text and "anexa" in text


def test_T_T019_bad_file_does_not_stop_the_batch(runner, files, tmp_path):
    bad = tmp_path / "stricat.png"
    bad.write_bytes(b"nu e imagine")
    result = runner.run(_word_task("Dosar", tmp_path / "out"), [files[0], bad])
    assert result[0][1] is not None and result[0][2] is None
    assert result[1][1] is None and isinstance(result[1][2], CoreError)


def test_T_T011_timestamped_subfolder_and_multiple_saves(runner, files, tmp_path):
    out = tmp_path / "out"
    task = _task("Doua", ("get_images", {}), ("analyze", {}), ("recognize", {}),
                 ("save", {"kind": "document", "format": "pdf", "folder": str(out),
                           "timestamped_subfolder": True}),
                 ("save", {"kind": "images", "format": "tiff", "folder": str(out),
                           "multipage": True}),
                 ("send_to", {"kind": "email_images"}))
    runner.run(task, files)
    pdf, tif = runner.last_run.outputs
    assert pdf.parent.parent == out and pdf.suffix == ".pdf"  # subfolderul cu data si ora
    assert tif.parent == out and tif.suffix == ".tif"
    with Image.open(tif) as img:
        assert img.n_frames == 2
    assert runner.last_run.sent == [("email_images", None, [tif])]


def test_T_T008_current_project_only_new_pages_recognized(runner, ctx, files, tmp_path):
    from app.core.ocr.service import RecognitionService
    from app.core.project import OcrProject

    project = OcrProject.create(context=ctx)
    try:
        project.add_images(files[:1])
        engine = ScriptEngine()
        RecognitionService(project, engine=engine).recognize_pages()
        runner._engine = engine
        engine.pages.clear()
        task = _task("Curent", ("get_images", {"project": "current"}), ("analyze", {}),
                     ("recognize", {}),
                     ("save", {"kind": "document", "format": "txt", "folder": str(tmp_path)}))
        runner.run(task, files[1:], project=project)
        assert set(engine.pages) == {2}  # numai pagina noua
        assert [p.status for p in project.pages] == [PageStatus.RECOGNIZED] * 2
        with pytest.raises(TaskValidationError):
            runner.run(task, files[1:])  # fara proiect deschis
    finally:
        project.close()


def test_T_T016_save_project_and_T_T106_manual_areas(runner, files, tmp_path):
    target = tmp_path / "proiect"
    task = _task("Proiect", ("get_images", {}), ("analyze", {"mode": "manual"}),
                 ("recognize", {}), ("save", {"kind": "project", "path": str(target)}))
    seen = []
    runner.run(task, files[:1], wait_for_areas=lambda p: (
        seen.append(len(p.pages)), p.analyze_pages([1])))
    assert seen == [1] and runner.last_run.project_path == target and target.exists()
    result = runner.run(task, files[:1])  # fara utilizator: pasul manual se refuza
    assert isinstance(result[0][2], TaskValidationError)
