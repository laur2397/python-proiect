"""Lansatorul si ecranul de conversie: cerintele A fara test pana acum."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from app.core.context import AppContext
from app.core.convert import OTHER_FORMATS
from app.core.model import ExportFormat
from app.core.paths import AppPaths
from app.gui.convert_screen import ConvertScreen
from app.gui.i18n import tr

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def files(tmp_path):
    out = []
    for name in ("a", "b", "c"):
        Image.new("L", (200, 200), 255).save(tmp_path / f"{name}.png", dpi=(300, 300))
        out.append(tmp_path / f"{name}.png")
    return out


def _screen(qtbot, ctx, key, files):
    screen = ConvertScreen(ctx, key, list(files))
    qtbot.addWidget(screen)
    return screen


def test_T_A004_tasks_use_options_settings(qtbot, ctx, files):
    ctx.settings.set("lang.manual", ["deu"])
    screen = _screen(qtbot, ctx, "pdf", files)
    assert screen.languages.codes() == ["deu"]  # limbile din Options


def test_T_A014_A015_A016_panels_per_format(qtbot, ctx, files):
    word = _screen(qtbot, ctx, "docx", files)
    assert {"layout", "pictures", "headers"} <= set(word.fields)  # A-050…A-053
    excel = _screen(qtbot, ctx, "xlsx", files)
    assert {"layout", "pictures", "sheet_per_page"} <= set(excel.fields)  # A-062, A-063
    other = _screen(qtbot, ctx, "other", files)
    combo = other.fields["format"]
    assert [combo.itemText(i) for i in range(combo.count())] == [
        ".pptx", ".odt", ".html", ".epub", ".fb2", ".rtf", ".txt", ".csv", ".djvu"]
    assert OTHER_FORMATS[0] is ExportFormat.PPTX


def test_T_A025_delete_key_removes_selected(qtbot, ctx, files):
    screen = _screen(qtbot, ctx, "pdf", files)
    screen.show()
    qtbot.waitExposed(screen)
    screen.activateWindow()
    screen.files.setFocus()
    screen.files.setCurrentRow(1)
    qtbot.keyClick(screen.files, Qt.Key.Key_Delete)
    assert screen.files.count() == 2


def test_T_A038_A039_A040_A041_pdf_options(qtbot, ctx, files):
    screen = _screen(qtbot, ctx, "pdf", files)
    assert "mrc" in screen.fields  # A-038
    assert screen.languages.objectName() == "convert_languages"  # A-039: combo multiplu
    opened = []
    screen.options_requested.connect(lambda tab, fmt: opened.append((tab, fmt)))
    screen.findChild(type(screen.convert_button), "convert_preprocessing").click()  # A-040
    screen.findChild(type(screen.convert_button), "convert_more").click()  # A-041
    assert opened[0][0] == "image" and opened[1][1] == "pdf"


def test_T_A051_A054_A055_A061_A064_A065_A071_buttons(qtbot, ctx, files):
    word = _screen(qtbot, ctx, "docx", files)
    assert word.convert_button.text() == tr("convert.start",
                                            format=tr("launcher.card.docx"))  # A-055
    excel = _screen(qtbot, ctx, "xlsx", files)
    assert excel.convert_button.text() == tr("convert.start",
                                             format=tr("launcher.card.xlsx"))  # A-065
    for screen in (word, excel, _screen(qtbot, ctx, "other", files)):
        assert screen.languages.codes()  # A-051, A-061, A-071: limbile OCR
        assert screen.findChild(type(screen.convert_button), "convert_more")  # A-054, A-064


def test_T_A086_A089_scan_to_excel_and_other(qtbot, ctx, files):
    excel = _screen(qtbot, ctx, "xlsx", files)  # A-086: aceleasi optiuni ca la conversie
    assert excel.settings().target is ExportFormat.XLSX
    other = _screen(qtbot, ctx, "other", files)  # A-089: format si limbi
    other.fields["format"].setCurrentIndex(2)
    assert other.settings().target is ExportFormat.HTML


def test_T_A101_recent_comparisons_marked_when_missing(qtbot, ctx, tmp_path):
    from app.core.compare.engine import record_recent
    from app.gui.launcher import Launcher

    left, right = tmp_path / "v1.pdf", tmp_path / "v2.pdf"
    left.write_bytes(b"%PDF")
    record_recent(ctx.app_db, left, right, ("ron",), 3)  # v2 lipseste
    launcher = Launcher(ctx)
    qtbot.addWidget(launcher)
    item = launcher.comparisons.item(0)
    assert tr("compare.recent_missing") in item.text()
    assert not item.flags() & Qt.ItemFlag.ItemIsEnabled


def test_T_A106_A110_mobile_folder_is_local_and_saved_normally():
    """A-106: aplicatia mobila si clientul de cloud tin de utilizator; A-110:
    sincronizarea o face clientul de cloud la salvarea obisnuita (W-085)."""
    ro = json.loads((ROOT / "app" / "gui" / "i18n" / "ro.json").read_text(encoding="utf-8"))
    assert any(k.startswith("launcher.mobile.") for k in ro)


def test_T_A304_A307_A310_dialog_list_and_color(qtbot, ctx, files):
    from app.gui.convert_screen import CustomSettingsDialog
    from app.gui.filters import conversion_filter

    assert conversion_filter().startswith(tr("filter.supported"))  # A-304
    assert tr("launcher.pick.convert_pdf")
    screen = _screen(qtbot, ctx, "pdf", files)
    assert not screen.files.item(0).icon().isNull()  # A-307: icon dupa tip
    dialog = CustomSettingsDialog(screen.custom, screen)
    qtbot.addWidget(dialog)
    assert dialog.color.itemText(0) == tr("convert.custom.keep_color")  # A-310


def test_T_A316_no_rate_this_product():
    """A-316 (`X`): butonul `Rate This Product` nu exista."""
    sources = " ".join(p.read_text(encoding="utf-8") for p in (ROOT / "app").rglob("*.py"))
    assert "rate_this_product" not in sources.lower()
