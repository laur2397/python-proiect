"""Faza 6b, pasul 6b.1: fereastra principala si traducerile (J-400..J-420,
Q-001, X-140, CLAUDE.md §4, §6.5)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from app.core.context import AppContext
from app.core.model import AutoProcessMode
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.gui import i18n
from app.gui.main_window import SAVE_FORMATS, TOOLBAR_ORDER, MainWindow

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "app" / "gui"


def keys(language: str) -> set[str]:
    return set(json.loads((GUI / "i18n" / f"{language}.json").read_text(encoding="utf-8")))


# =============================================================================
# CLAUDE.md §6.5: traducerile
# =============================================================================


def test_romanian_and_english_have_the_same_keys():
    assert keys("ro") == keys("en")


def test_every_used_key_is_translated():
    """Cheile scrise direct in cod si cele compuse (action.*, format.*, layout.*)."""
    from app.core.model import LayoutMode, PageStatus

    used = set()
    for path in GUI.rglob("*.py"):
        used |= set(re.findall(r'tr\("([a-z0-9_.]+)"', path.read_text(encoding="utf-8")))
    window_actions = ("new_task", "new_project", "open_project", "open", "scan", "page_up",
                      "page_down", "recognize", "undo", "redo", "arrange_side",
                      "arrange_stacked", "verify", "options", "exit", "save_project",
                      "save_project_as", "close_project")
    used |= {f"action.{k}" for k in window_actions}
    used |= {f"format.{k}" for k in SAVE_FORMATS}
    used |= {f"layout.{m.value}" for m in LayoutMode}
    used |= {f"page.status.{s.value}" for s in PageStatus}
    used |= {f"menu.{m}" for m in ("file", "edit", "view", "recognize", "area", "tools", "help")}
    used |= {f"panel.{p}" for p in ("pages", "text", "zoom")}
    assert used - keys("ro") == set()


def test_translation_fallbacks_and_parameters():
    i18n.set_language("en")
    try:
        assert i18n.tr("menu.file") == "&File"
        assert i18n.tr("action.page_counter", n=2, total=5) == "[ 2 / 5 ]"
        assert i18n.tr("cheie.inexistenta") == "cheie.inexistenta"
    finally:
        i18n.set_language("ro")
    assert i18n.tr("panel.pages") == "Pagini"
    with pytest.raises(ValueError):
        i18n.set_language("fr")


def test_core_never_imports_the_gui():
    """CLAUDE.md §4: `core` nu importa `gui`. Niciodata."""
    for path in (ROOT / "app" / "core").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", text, re.MULTILINE)
        bad = [m for m in imports if m.startswith(("app.gui", "PySide6"))]
        assert not bad, (path, bad)


# =============================================================================
# J-400..J-420: fereastra
# =============================================================================


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    paths = []
    for n in (1, 2):
        Image.new("L", (600, 800), 255).save(tmp_path / f"p{n}.png", dpi=(300, 300))
        paths.append(tmp_path / f"p{n}.png")
    project = OcrProject.create(context=ctx)
    project.add_images(paths, auto_process=AutoProcessMode.NONE)
    w = MainWindow(ctx, project)
    qtbot.addWidget(w)
    yield w
    project.close()


def test_T_J400_1_title_of_a_new_project(qtbot, ctx):
    w = MainWindow(ctx)
    qtbot.addWidget(w)
    assert re.fullmatch(r"Proiect fără titlu \d+ - DocuLens OCR Editor", w.windowTitle())
    w.project.close()


def test_T_J401_1_main_toolbar_order(window):
    assert tuple(window.toolbar_items) == TOOLBAR_ORDER


def test_T_Q001_6_save_formats_follow_the_layout_mode(window):
    """Q-001: modul limiteaza formatele; `Flexible layout` = numai HTML."""
    from app.core.model import LayoutMode

    combo = window.layout_combo
    combo.setCurrentIndex(list(LayoutMode).index(LayoutMode.FLEXIBLE))
    enabled = {k for k, a in window.save_actions.items() if a.isEnabled()}
    assert enabled == {"html", "pdf_image"}
    combo.setCurrentIndex(list(LayoutMode).index(LayoutMode.EXACT))
    enabled = {k for k, a in window.save_actions.items() if a.isEnabled()}
    assert {"pdf", "pdfa", "pdfua", "docx", "pptx", "djvu"} <= enabled and "txt" not in enabled


def test_T_J420_1_verify_is_grey_without_uncertain_words(window):
    assert not window.actions["verify"].isEnabled()


def test_page_counter_and_navigation(window):
    """J-401: contorul [ N / M ] cu sageti sus si jos."""
    assert window.page_counter.text() == "[ 1 / 2 ]"
    assert not window.actions["page_up"].isEnabled()
    window.actions["page_down"].trigger()
    assert window.page_counter.text() == "[ 2 / 2 ]" and window.pages_list.currentRow() == 1
    window.pages_list.setCurrentRow(0)
    assert window.page_counter.text() == "[ 1 / 2 ]"


def test_T_J409_1_panels_exist_and_move(window):
    from PySide6.QtCore import Qt

    for dock in (window.pages_dock, window.text_dock, window.zoom_dock):
        assert dock.isAreaAllowed(Qt.DockWidgetArea.LeftDockWidgetArea)
        assert dock.isAreaAllowed(Qt.DockWidgetArea.RightDockWidgetArea)
    assert window.pages_list.count() == 2
    assert window.pages_list.item(0).toolTip() == "Neprocesată"  # J-405
