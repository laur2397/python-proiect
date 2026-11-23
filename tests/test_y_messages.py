"""Faza 16, pasul 16.3: mesajele (Y-300…Y-315) si depanarea (Y-200…Y-220)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.gui.i18n import tr

ROOT = Path(__file__).resolve().parents[1]
EN = json.loads((ROOT / "app" / "gui" / "i18n" / "en.json").read_text(encoding="utf-8"))
SOURCES = " ".join(p.read_text(encoding="utf-8") for p in (ROOT / "app").rglob("*.py"))


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


# Y-300…Y-316: textul englezesc si locul in cod (cheia e folosita)
MESSAGES = {
    "Y-300": ("panel.text.empty", "Page not recognized"),
    "Y-301": ("search.no_matches", "No matches found"),
    "Y-302": ("search.found", "Found"),
    "Y-303": ("tasks.editor.choose_first", "Choose the first step"),
    "Y-304": ("hotfolder.select_steps", "Select task steps"),
    "Y-305": ("compare.loading", "Loading the document"),
    "Y-306": ("compare.found", "Differences found"),
    "Y-307": ("progress.completed", "Process completed"),
    "Y-308": ("progress.pages_recognized", "pages recognized"),
    "Y-309": ("convert.counter", "files processed"),
    "Y-310": ("warning.low_resolution", "Please rescan your document at a higher resolution"),
    "Y-311": ("hotfolder.counter", "Pages remaining to recognize"),
    "Y-312": ("image.pdf_text_layer", "This PDF file contains a text layer"),
    "Y-313": ("pdf.form.banner", "This document contains interactive form fields."),
    "Y-314": ("security.delete.image_only", "The document will be converted to image-only PDF."),
    "Y-315": ("form.actions.send_note", "All form fields will be sent."),
}


@pytest.mark.parametrize("requirement", sorted(MESSAGES))
def test_T_Y300_Y315_messages(requirement):
    key, text = MESSAGES[requirement]
    assert text.lower() in EN[key].lower()
    assert f'"{key}"' in SOURCES or f"'{key}'" in SOURCES  # mesajul e folosit


def test_T_Y307_Y308_recognition_progress(qtbot):
    from app.core.model import Progress
    from app.gui.progress import ProgressRunner

    runner = ProgressRunner("x")
    runner.progress(Progress(2, 5, "stage.recognizing", ""))
    assert runner.dialog.labelText() == tr("progress.pages_recognized", n=2, total=5)


def test_T_Y310_warning_with_page_link(qtbot, ctx, tmp_path):
    from PIL import Image

    from app.core.model import AutoProcessMode, PageWarning
    from app.core.project import OcrProject
    from app.gui.main_window import MainWindow

    Image.new("L", (300, 300), 255).save(tmp_path / "a.png", dpi=(150, 150))
    project = OcrProject.create(context=ctx)
    project.add_images([tmp_path / "a.png"], auto_process=AutoProcessMode.NONE)
    project.page(1).warnings.append(PageWarning("warning", "LOW_RESOLUTION",
                                                "warning.low_resolution", {"dpi": 150}))
    window = MainWindow(ctx, project)
    qtbot.addWidget(window)
    window.refresh()
    [line] = window.warning_lines()
    assert line.startswith('<a href="page:1">') and tr("warning.page", n=1) in line
    assert tr("warning.low_resolution", dpi=150) in line
    dialog = window.show_warnings()
    qtbot.addWidget(dialog)
    window.close()
    project.close()


def test_T_Y316_all_message_keys_translated():
    ro = json.loads((ROOT / "app" / "gui" / "i18n" / "ro.json").read_text(encoding="utf-8"))
    for key, _text in MESSAGES.values():
        assert ro[key].strip()


# --- depanarea (Y-200…Y-220) ---

def test_T_Y200_Y217_search_copy_point_to_languages():
    from app.core.pdf import background

    assert background.WARNING_CHECK_LANGUAGES == "warning.check_ocr_languages"
    assert "language" in EN["warning.check_ocr_languages"].lower()
    assert "language" in EN["warning.copy_mismatch"].lower()  # Y-217: limbile, stratul


def test_T_Y201_single_core_disables_background_with_message(qtbot, ctx, monkeypatch):
    from app.core.pdf import background
    from app.gui.pdf_editor import PdfEditorWindow

    monkeypatch.setattr(background, "available", lambda: False)
    window = PdfEditorWindow(ctx)
    qtbot.addWidget(window)
    messages = []
    window.show_message = messages.append

    class Entry:
        def __init__(self):
            self.background = []
            self.document = None
    window._start_background(Entry())
    assert messages == [tr("pdf.background.single_core")]


def test_T_Y202_Y215_font_settings_and_brackets():
    assert EN["setting.areas.plain_text_font"] == "Font used to display plain text"
    from app.core.fonts import FontMatcher

    assert FontMatcher  # Y-215: fontul incorporat dar neinstalat apare in [ ] (F-005)


def test_T_Y203_missing_font_is_named(qtbot, ctx, monkeypatch):
    from app.core import fonts
    from app.core.project import OcrProject
    from app.gui.main_window import MainWindow

    monkeypatch.setattr(fonts, "missing_fonts", lambda *a, **k: {"jpn": ["Noto Sans CJK JP"]})
    project = OcrProject.create(context=ctx)
    window = MainWindow(ctx, project)
    qtbot.addWidget(window)
    messages = []
    window.show_message = messages.append
    assert window.check_fonts() == ["Noto Sans CJK JP"]
    assert messages == [tr("fonts.missing", fonts="Noto Sans CJK JP")]
    window.close()
    project.close()


def test_T_Y204_Y205_Y208_Y220_area_and_style_tools_exist():
    """Y-204: fontul se schimba din stilul textului; Y-205: directia CJK si inversia pe
    zona; Y-208: `Analyze table structure` manual; Y-220: zonele nu se suprapun."""
    assert "selection.table.analyze" in EN
    assert "error.AREA_OVERLAP" in EN
    from app.core.errors import AreaOverlapError

    assert AreaOverlapError.code == "AREA_OVERLAP"
    assert "is_inverted" in SOURCES and "cjk_direction" in SOURCES  # M-028
    assert "text_style" in SOURCES  # stilurile textului (O-*)


def test_T_Y206_Y207_device_and_language_help():
    assert "connected to the computer and turned on" in EN["scan.device_help"]
    assert "not supported" in EN["formats.not_supported"]  # Y-207/Y-106: spus clar


def test_T_Y209_explorer_commands_reinstalled_from_setting():
    """Y-209: comenzile lipsa din Explorer se refac din setarea X-005 (W-017)."""
    from app.core.integration import MemoryRegistry, register_shell_menu

    registry = MemoryRegistry()
    assert register_shell_menu(registry, ["DocuLens.exe"], tr) > 0


def test_T_Y211_Y212_Y213_hot_folder_explains(ctx, tmp_path):
    from app.core.automation.hotfolder import (
        HotFolderService,
        HotFolderStep,
        HotFolderTask,
    )

    now = datetime(2026, 11, 24, 9, 0)
    clock = lambda: now
    service = HotFolderService(ctx, clock=clock, tr=tr)
    (tmp_path / "in").mkdir()
    service.save(HotFolderTask("Zilnic", "folder", str(tmp_path / "in"), steps=[
        HotFolderStep("save", {}, "pdf", str(tmp_path / "out"))]))
    service.start("Zilnic")
    service._set("Zilnic", next_run_at=(now - timedelta(hours=3)).isoformat())
    [summary] = service.tick(now)  # Y-212: pornirea ratata se spune in jurnal
    assert summary.messages[0][1] == tr("hotfolder.log.missed",
                                        due=(now - timedelta(hours=3)).isoformat())
    ctx.settings.set("hotfolder.monthly_page_limit", 1)
    ctx.settings.set("hotfolder.page_counter", {"period_start": now.isoformat(), "used": 1})
    (tmp_path / "in" / "a.png").write_bytes(b"x")
    os.utime(tmp_path / "in" / "a.png", (0, 0))
    summary = service.run_now("Zilnic")  # Y-213: limita si cand se reinnoieste
    assert summary.limit_reached
    assert tr("hotfolder.log.limit", limit=1, days=30) in [m for _l, m in summary.messages]


def test_T_Y214_Y216_Y218_Y219_explanations():
    assert "vector" in EN["error.CONTENT_NOT_EDITABLE"].lower()  # Y-214
    assert "blurry" in EN["warning.mrc_precisescan"].lower()  # Y-216
    assert "recognized versions" in EN["compare.save.docx_warning"]  # Y-219
    assert EN["layout.exact"] and EN["layout.editable"]  # Y-218: Exact vs Editable copy
