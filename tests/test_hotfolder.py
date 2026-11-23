"""Faza 13, pasul 13.2: nucleul Hot Folder (S-005…S-073)."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta

import pytest
from PIL import Image, ImageDraw, ImageFont
from test_automated_tasks import ScriptEngine

from app.core.automation.hotfolder import (
    ERRORS_FOLDER,
    FILE_TYPES,
    HotFolderService,
    HotFolderStep,
    HotFolderTask,
    display_status,
    expand_name,
    matches,
    next_start,
)
from app.core.context import AppContext
from app.core.errors import CoreError, ProjectVersionError, TaskValidationError
from app.core.paths import AppPaths


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


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


def _image(path, *, old=True):
    img = Image.new("L", (1200, 1600), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=36)
    for row in range(5):
        draw.text((100, 120 + row * 60), "Cererea de rambursare", fill=0, font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, dpi=(300, 300))
    if old:  # S-073: copiat complet de mai mult de 3 secunde
        past = time.time() - 10
        os.utime(path, (past, past))
    return path


def _task(tmp_path, name="Dosare", **kw):
    out = tmp_path / "out"
    steps = kw.pop("steps", None) or [HotFolderStep(
        "save", {"output": kw.pop("output", "per_file")}, "docx", str(out),
        kw.pop("name_template", "[F]"))]
    return HotFolderTask(name, "folder", str(tmp_path / "in"), steps=steps, **kw)


# --- planificarea ---

def test_T_S031_S032_next_start_for_each_schedule():
    now = datetime(2026, 11, 23, 10, 0)  # luni
    once = HotFolderTask("a", "folder", "x", schedule_kind="once",
                         schedule_at="2026-11-24T08:30:00")
    assert next_start(once, now) == datetime(2026, 11, 24, 8, 30)
    assert next_start(once, now, last_run=now) is None
    minute = HotFolderTask("a", "folder", "x", schedule_kind="interval")
    assert next_start(minute, now) == now
    assert next_start(minute, now, last_run=now) == now + timedelta(minutes=1)
    daily = HotFolderTask("a", "folder", "x", schedule_kind="daily", schedule_time="09:00")
    assert next_start(daily, now) == datetime(2026, 11, 24, 9, 0)
    weekly = HotFolderTask("a", "folder", "x", schedule_kind="weekly", schedule_time="18:00",
                           schedule_days=(4,))
    assert next_start(weekly, now) == datetime(2026, 11, 27, 18, 0)
    monthly = HotFolderTask("a", "folder", "x", schedule_kind="monthly",
                            schedule_time="07:00", schedule_days=(31,))
    assert next_start(monthly, now) == datetime(2026, 11, 30, 7, 0)  # luna are 30 de zile


def test_T_S032_no_trigger_on_new_file_and_only_every_minute(service, tmp_path):
    with pytest.raises(TaskValidationError) as caught:
        service.validate(_task(tmp_path, schedule_kind="on_new_file"))
    assert caught.value.params["reason"] == "schedule_kind"
    with pytest.raises(TaskValidationError) as caught:
        service.validate(_task(tmp_path, schedule_interval_minutes=5))
    assert caught.value.params["reason"] == "schedule_interval"


def test_T_S005_no_system_service(service):
    with pytest.raises(CoreError) as caught:
        service.install_service()
    assert caught.value.params["requirement"] == "S-005"


# --- validarea (S-030…S-053) ---

@pytest.mark.parametrize(("changes", "reason"), [
    ({"name": " "}, "name"),
    ({"source_kind": "ftp"}, "source_unavailable"),
    ({"source_kind": "outlook"}, "source_unavailable"),
    ({"schedule_kind": "once"}, "schedule_at"),
    ({"original_action": "move"}, "original_move_to"),
    ({"process": {"mode": "recognize", "languages": []}}, "languages"),
    ({"process": {"mode": "recognize", "languages": ["ron"], "blank_folder": "x"}},
     "blank_folder"),
    ({"process": {"mode": "analyze", "languages": ["ron"]}}, "save_needs_recognize"),
    ({"steps": [HotFolderStep("save", {}, "docx", None)]}, "save_target"),
])
def test_T_S053_incomplete_task_is_refused(service, tmp_path, changes, reason):
    task = _task(tmp_path)
    for key, value in changes.items():
        setattr(task, key, value)
    with pytest.raises(TaskValidationError) as caught:
        service.validate(task)
    assert caught.value.params["reason"] == reason


def test_T_S053_task_without_save_is_refused(service, tmp_path):
    task = _task(tmp_path)
    task.steps = []
    with pytest.raises(TaskValidationError) as caught:
        service.validate(task)
    assert caught.value.params["reason"] == "no_output"


def test_T_S046_image_only_pdf_without_recognition(service, tmp_path):
    task = _task(tmp_path, steps=[HotFolderStep("save", {"image_only": True}, "pdf",
                                                str(tmp_path / "out"))])
    task.process = {"mode": "preprocess", "languages": ["ron"]}
    service.validate(task)


def test_T_S033_S047_test_source(service, tmp_path):
    task = _task(tmp_path)
    with pytest.raises(CoreError):
        service.test_source(task)  # folderul sursa nu exista
    (tmp_path / "in").mkdir()
    service.test_source(task)
    assert (tmp_path / "out").is_dir()  # S-047: folderul de iesire e scriibil


# --- operatiile (S-060…S-065) ---

def test_T_S060_S062_S063_S064_start_modify_copy_delete(service, tmp_path):
    service.save(_task(tmp_path))
    service.start("Dosare")
    task = service.task("Dosare")
    assert task.status == "running" and display_status(task) == "watching"
    with pytest.raises(TaskValidationError) as caught:
        service.save(task)  # S-062: se opreste intai
    assert caught.value.params["reason"] == "running"
    service.stop("Dosare")
    assert display_status(service.task("Dosare")) == "stopped"
    copy = service.duplicate("Dosare")
    assert copy.name == "Dosare (2)" and copy.status == "stopped"
    service.delete("Dosare (2)")
    assert [t.name for t in service.tasks()] == ["Dosare"]


def test_T_S016_run_once_is_scheduled_then_completed(service, tmp_path, clock):
    _image(tmp_path / "in" / "a.png")
    at = clock.now + timedelta(minutes=30)
    service.save(_task(tmp_path, schedule_kind="once", schedule_at=at.isoformat()))
    service.start("Dosare")
    assert display_status(service.task("Dosare")) == "scheduled"
    assert service.tick() == []  # inca nu e ora
    clock.now = at + timedelta(minutes=1)
    [summary] = service.tick()
    assert summary.files == 1 and service.task("Dosare").status == "completed"


def test_T_S017_recurring_task_keeps_watching(service, tmp_path, clock):
    _image(tmp_path / "in" / "a.png")
    service.save(_task(tmp_path))
    service.start("Dosare")
    [summary] = service.tick()
    task = service.task("Dosare")
    assert summary.files == 1 and display_status(task) == "watching"
    assert task.next_run_at == (clock.now + timedelta(minutes=1)).isoformat()


def test_T_S065_export_import_hft(service, tmp_path):
    service.save(_task(tmp_path))
    service.start("Dosare")
    path = tmp_path / "dosare.hft"
    service.export_task("Dosare", path)
    imported = service.import_task(path)
    assert imported.name == "Dosare (2)" and imported.status == "stopped"
    assert imported.steps[0].output_format == "docx"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["format_version"] = 7
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ProjectVersionError):
        service.import_task(path)


# --- procesarea ---

def test_T_S009_processed_files_are_not_reprocessed(service, tmp_path, clock):
    source = _image(tmp_path / "in" / "cerere.png")
    past = time.time() - 3600  # copiat acum o ora
    os.utime(source, (past, past))
    clock.now = datetime.now().replace(microsecond=0) - timedelta(minutes=30)
    service.save(_task(tmp_path))
    first = service.run_now("Dosare")
    assert first.files == 1 and (tmp_path / "out" / "cerere.docx").exists()
    assert service.run_now("Dosare").files == 0  # S-009
    entries = service.log_entries("Dosare")
    assert entries[0]["status"] == "success" and entries[0]["source_file"].endswith("cerere.png")
    _image(source)  # fisierul e inlocuit dupa procesare (acum 10 secunde)
    service._seen.clear()
    assert [p.name for p in service.pending_files(service.task("Dosare"))] == ["cerere.png"]


def test_T_S073_file_still_being_copied_waits(service, tmp_path):
    fresh = _image(tmp_path / "in" / "nou.png", old=False)
    assert not service.is_file_ready(fresh)
    past = time.time() - 10
    os.utime(fresh, (past, past))
    assert service.is_file_ready(fresh)
    with fresh.open("ab") as fh:  # dimensiunea s-a schimbat de la ultima observatie
        fh.write(b"0")
    os.utime(fresh, (past, past))
    assert not service.is_file_ready(fresh)


def test_T_S072_three_failures_move_file_to_errors(service, tmp_path):
    bad = tmp_path / "in" / "stricat.png"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"nu e imagine")
    past = time.time() - 10
    os.utime(bad, (past, past))
    service.save(_task(tmp_path))
    for _ in range(2):
        summary = service.run_now("Dosare")
        assert summary.errors == 1 and bad.exists()
    assert service.task("Dosare").status == "error"  # S-020
    service.run_now("Dosare")
    assert not bad.exists() and (tmp_path / "in" / ERRORS_FOLDER / "stricat.png").exists()
    assert [e["retry_count"] for e in service.log_entries("Dosare")] == [2, 1, 0]
    assert service.run_now("Dosare").files == 0  # nu se mai reproceseaza


def test_T_S037_S049_subfolders_and_document_per_folder(service, tmp_path):
    _image(tmp_path / "in" / "firma A" / "1.png")
    _image(tmp_path / "in" / "firma A" / "2.png")
    _image(tmp_path / "in" / "firma B" / "acte" / "3.png")
    service.save(_task(tmp_path, include_subfolders=True, output="per_folder"))
    summary = service.run_now("Dosare")
    assert summary.files == 3
    out = tmp_path / "out"
    assert (out / "firma A.docx").exists()
    assert (out / "firma B" / "acte.docx").exists()  # ierarhia se pastreaza


def test_T_S037_subfolders_off_by_default(service, tmp_path):
    _image(tmp_path / "in" / "a.png")
    _image(tmp_path / "in" / "sub" / "b.png")
    service.save(_task(tmp_path))
    assert [p.name for p in service.pending_files(service.task("Dosare"))] == ["a.png"]


def test_T_S050_S052_single_document_and_several_formats(service, tmp_path, clock):
    _image(tmp_path / "in" / "1.png")
    _image(tmp_path / "in" / "2.png")
    out = tmp_path / "out"
    service.save(_task(tmp_path, steps=[
        HotFolderStep("save", {"output": "single"}, "pdf", str(out), "Dosar_[D]"),
        HotFolderStep("save", {"output": "single"}, "txt", str(out), "Dosar_[D]")]))
    summary = service.run_now("Dosare")
    day = clock.now.strftime("%Y-%m-%d")
    assert sorted(p.name for p in summary.outputs) == [f"Dosar_{day}.pdf", f"Dosar_{day}.txt"]
    assert summary.files == 2 and summary.pages == 2


def test_T_S038_original_moved_or_deleted(service, tmp_path):
    _image(tmp_path / "in" / "a.png")
    _image(tmp_path / "in" / "b.png")
    done = tmp_path / "procesate"
    service.save(_task(tmp_path, original_action="move", original_move_to=str(done)))
    service.run_now("Dosare")
    assert sorted(p.name for p in done.iterdir()) == ["a.png", "b.png"]
    _image(tmp_path / "in" / "c.png")
    service.save(_task(tmp_path, name="Sterge", original_action="delete"))
    service.run_now("Sterge")
    assert not (tmp_path / "in" / "c.png").exists()


def test_T_S044_S045_S214_blank_pages_deleted_without_confirmation(service, tmp_path):
    folder = tmp_path / "in"
    _image(folder / "plin.png")
    Image.new("L", (1200, 1600), 255).save(folder / "gol.png", dpi=(300, 300))
    past = time.time() - 10
    os.utime(folder / "gol.png", (past, past))
    blank = tmp_path / "goale"
    task = _task(tmp_path, output="single")
    task.process = {"mode": "recognize", "languages": ["ron"], "delete_blank": True,
                    "blank_folder": str(blank)}
    service.save(task)
    summary = service.run_now("Dosare")
    assert summary.pages == 1  # pagina goala nu ajunge in document
    assert [p.name for p in blank.iterdir()] == ["gol.png"]


def test_T_S036_source_is_an_ocr_project(service, ctx, tmp_path):
    from app.core.model import AutoProcessMode
    from app.core.project import OcrProject

    project = OcrProject.create(context=ctx)
    project.add_images([_image(tmp_path / "img" / "x.png")], auto_process=AutoProcessMode.NONE)
    project.save(tmp_path / "proiect")
    project.close()
    service.save(HotFolderTask("Proiect", "folder", str(tmp_path / "proiect"), steps=[
        HotFolderStep("save", {}, "txt", str(tmp_path / "out"))]))
    summary = service.run_now("Proiect")
    assert summary.pages == 1 and (tmp_path / "out" / "proiect.txt").exists()


def test_T_S006_S202_S203_page_limit_and_counter(service, ctx, tmp_path, clock):
    ctx.settings.set("hotfolder.monthly_page_limit", 1)
    _image(tmp_path / "in" / "a.png")
    _image(tmp_path / "in" / "b.png")
    service.save(_task(tmp_path))
    assert service.pages_remaining() == 1 and service.days_to_renew() == 30
    summary = service.run_now("Dosare")
    assert summary.files == 1 and summary.limit_reached  # S-006: se opreste la limita
    assert service.pages_remaining() == 0
    assert service.task("Dosare").status == "error"
    clock.now += timedelta(days=30)  # contorul se reinnoieste
    assert service.pages_remaining() == 1
    ctx.settings.set("hotfolder.monthly_page_limit", 0)
    assert service.pages_remaining() is None  # fara limita


def test_T_S068_S069_log_file_next_to_results(service, tmp_path):
    _image(tmp_path / "in" / "a.png")
    service.save(_task(tmp_path))
    service.run_now("Dosare")
    log = (tmp_path / "out" / "Dosare.log.txt").read_text(encoding="utf-8")
    assert "hotfolder.log.header" in log and "hotfolder.log.stats" in log
    assert '"pages": 1' in log and '"errors": 0' in log and '"uncertain"' in log


def test_T_S211_S216_file_types_and_name_macros(tmp_path):
    assert list(FILE_TYPES)[:2] == ["all", "images_pdf"]
    assert matches(tmp_path / "A.TIF", "tiff") and not matches(tmp_path / "a.docx", "images_pdf")
    assert matches(tmp_path / "a.docx", "*.docx;*.odt")
    when = datetime(2026, 11, 23, 14, 5, 9)
    assert expand_name("[F]_[X]_[D]_[T]_[#]", tmp_path / "Cerere.pdf", when, 7) == \
        "Cerere_pdf_2026-11-23_14-05-09_7"
    assert expand_name("a/b", tmp_path / "x.png", when, 1) == "a_b"


def test_T_S206_save_images_and_ocr_project(service, tmp_path):
    from app.core.automation.hotfolder import PROJECT_FORMAT

    _image(tmp_path / "in" / "a.png")
    _image(tmp_path / "in" / "b.png")
    out = tmp_path / "out"
    task = _task(tmp_path, steps=[
        HotFolderStep("save", {"kind": "images", "output": "single", "multipage": True},
                      "tiff", str(out), "scan"),
        HotFolderStep("save", {"kind": "project", "output": "single"}, PROJECT_FORMAT,
                      str(out), "proiect")])
    task.process = {"mode": "preprocess", "languages": ["ron"]}  # imaginile nu cer OCR
    service.save(task)
    summary = service.run_now("Dosare")
    names = sorted(p.name for p in summary.outputs)
    assert names == ["proiect", "scan.tif"]
    with Image.open(out / "scan.tif") as img:
        assert img.n_frames == 2
    assert (out / "proiect" / "project.db").exists()
    bad = _task(tmp_path, name="Rau", steps=[
        HotFolderStep("save", {"kind": "images"}, "docx", str(out))])
    with pytest.raises(TaskValidationError):
        service.validate(bad)
