"""Faza 6c, pasul 6c.3: ecranul de conversie (A-017, A-020…A-073,
A-305…A-315)."""

from __future__ import annotations

import os

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel, QPushButton, QToolBar

from app.core.context import AppContext
from app.core.convert import FullTextSearch
from app.core.model import (
    BlockData,
    ExportFormat,
    ImageQuality,
    LayoutMode,
    LineData,
    Rect,
    WordData,
)
from app.core.ocr.engine import RecognitionResult
from app.core.paths import AppPaths
from app.gui.convert_screen import ConvertScreen, CustomSettingsDialog


class ScriptEngine:
    name = "fals"

    def recognize_page(self, page, settings, cancel=None):
        word = WordData(None, page.source_file.stem, 95.0, bbox=Rect(50, 50, 300, 40))
        block = BlockData(None, lines=[LineData(None, words=[word], bbox=Rect(50, 50, 300, 40))],
                          bbox=Rect(50, 50, 300, 40))
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=95.0,
                                 area_blocks={a.id: [block] for a in page.areas[:1]})


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("lang.manual", ["ron"])
    yield c
    c.close()


@pytest.fixture
def files(tmp_path):
    out = []
    for name in ("cerere", "anexa", "buget"):
        img = Image.new("L", (600, 800), 255)
        img.paste(0, (50, 50, 350, 90))
        img.save(tmp_path / f"{name}.png", dpi=(300, 300))
        out.append(tmp_path / f"{name}.png")
    return out


def screen(qtbot, ctx, key, files):
    s = ConvertScreen(ctx, key, files)
    s.engine = ScriptEngine()
    qtbot.addWidget(s)
    return s


def names(s):
    return [p.name for p in s.file_paths()]


def test_T_A305_1_layout_and_A306_toolbar(qtbot, ctx, files):
    s = screen(qtbot, ctx, "pdf", files)
    assert s.back.text() == "< Înapoi"
    bar = s.findChild(QToolBar, "convert_file_toolbar")
    assert [a.text() for a in bar.actions()] == ["Adaugă fișiere", "Elimină", "Mută sus",
                                                 "Mută jos"]
    assert not s.file_actions["remove"].isEnabled()  # gri fara selectie
    s.files.item(0).setSelected(True)
    assert s.file_actions["remove"].isEnabled()
    assert s.files.item(0).text().startswith("cerere.png  (")


def test_T_A022_1_and_A023_1_remove_and_move(qtbot, ctx, files):
    s = screen(qtbot, ctx, "pdf", files)
    s.files.item(0).setSelected(True)
    s.move(-1)  # primul nu urca
    assert names(s) == ["cerere.png", "anexa.png", "buget.png"]
    s.move(1)
    assert names(s) == ["anexa.png", "cerere.png", "buget.png"]
    s.files.clearSelection()
    s.files.item(2).setSelected(True)
    s.move(1)  # ultimul nu coboara
    assert names(s)[-1] == "buget.png"
    s.files.selectAll()  # A-026
    s.remove_selected()  # macar un fisier ramane
    assert len(names(s)) == 3
    s.files.clearSelection()
    s.files.item(1).setSelected(True)
    s.remove_selected()
    assert names(s) == ["anexa.png", "buget.png"]


def test_T_A024_2_combine_needs_two_files(qtbot, ctx, files):
    s = screen(qtbot, ctx, "pdf", files[:1])
    assert not s.combine.isEnabled()
    s.add_files(files[1:2])  # A-021: la sfarsit
    assert s.combine.isEnabled() and names(s) == ["cerere.png", "anexa.png"]


def test_T_A035_to_A042_pdf_settings(qtbot, ctx, files):
    s = screen(qtbot, ctx, "pdf", files)
    quality = s.fields["quality"]
    assert [ImageQuality(quality.itemData(i)) for i in range(quality.count())] == [
        ImageQuality.BEST, ImageQuality.BALANCED, ImageQuality.COMPACT, ImageQuality.CUSTOM]
    search = s.fields["search"]
    assert [search.itemText(i) for i in range(search.count())] == [
        "Ca în documentul original", "Caută în text și în imagini", "Fără căutare în text"]
    s.fields["pdfa"].setChecked(True)
    s.languages.set_checked("eng", True)
    settings = s.settings()
    assert settings.target is ExportFormat.PDF and settings.pdfa
    assert settings.languages == ("ron", "eng")
    assert settings.full_text_search is FullTextSearch.TEXT_AND_IMAGES
    assert s.convert_button.text() == "Convertește în PDF"


def test_T_A050_A060_A070_word_excel_other(qtbot, ctx, files):
    word = screen(qtbot, ctx, "docx", files)
    layout = word.fields["layout"]
    assert [LayoutMode(layout.itemData(i)) for i in range(layout.count())] == [
        LayoutMode.EXACT, LayoutMode.EDITABLE, LayoutMode.FORMATTED, LayoutMode.PLAIN]
    assert word.convert_button.text() == "Convertește în Microsoft Word"
    excel = screen(qtbot, ctx, "xlsx", files)
    assert excel.fields["layout"].count() == 2  # A-060
    excel.fields["sheet_per_page"].setChecked(True)
    assert excel.settings().sheet_per_page
    other = screen(qtbot, ctx, "other", files)
    fmt = other.fields["format"]
    assert [fmt.itemText(i) for i in range(fmt.count())] == [
        ".pptx", ".odt", ".html", ".epub", ".fb2", ".rtf", ".txt", ".csv", ".djvu"]
    fmt.setCurrentIndex(6)
    assert other.convert_button.text() == "Convertește în .txt"  # A-073
    with qtbot.waitSignal(other.options_requested) as signal:  # A-072
        other.findChild(QPushButton, "convert_more").click()
    assert signal.args == ["format", "txt"]


def test_T_A308_to_A314_custom_settings(qtbot):
    dialog = CustomSettingsDialog()
    qtbot.addWidget(dialog)
    assert [b.text() for b in dialog.dpi_buttons.values()] == ["300 dpi", "150 dpi", "96 dpi"]
    assert not dialog.dpi_buttons[150].isEnabled()
    dialog.reduce.setChecked(True)
    dialog.dpi_buttons[150].setChecked(True)
    dialog.slider.setValue(45)
    assert dialog.slider_label.text() == "Calitate (45%)"  # A-313
    dialog.loss.setCurrentIndex(1)  # `Quality loss not allowed`
    assert not dialog.slider.isEnabled()  # A-311
    assert dialog.values() == {"reduce": True, "dpi": 150, "lossless": True, "quality": 45}
    assert "JBIG2" in dialog.findChild(QLabel, "custom_codecs").text()  # A-312
    dialog.reset_button.click()  # A-314
    assert dialog.values() == CustomSettingsDialog.DEFAULTS


def test_custom_values_reach_the_settings(qtbot, ctx, files):
    s = screen(qtbot, ctx, "pdf", files)
    s.fields["quality"].setCurrentIndex(3)
    s.custom = {"reduce": True, "dpi": 96, "lossless": False, "quality": 30}
    settings = s.settings()
    assert settings.image_quality is ImageQuality.CUSTOM
    assert (settings.custom_dpi, settings.custom_quality) == (96, 30)


def test_T_A027_1_and_A315_1_conversion_with_progress(qtbot, ctx, files, tmp_path):
    s = screen(qtbot, ctx, "pdf", files)
    with qtbot.waitSignal(s.finished):
        result = s.start((tmp_path / "out", None))
    assert [p.name for p in result.written] == ["cerere.pdf", "anexa.pdf", "buget.pdf"]
    assert s.progress_lines[-1].splitlines() == [
        "Se convertește în .pdf...", "Se procesează fișierul: buget.png",
        "3 din 3 fișiere procesate"]
    assert s.report_text(result) == "Fișiere create: 3"


def test_combined_conversion_and_report_of_failures(qtbot, ctx, files, tmp_path):
    bad = tmp_path / "stricat.png"
    bad.write_bytes(b"nu")
    s = screen(qtbot, ctx, "pdf", [files[0], bad, files[1]])
    s.combine.setChecked(True)
    result = s.start((tmp_path / "out", "Dosar"))
    assert [p.name for p in result.written] == ["Dosar.pdf"]
    assert s.report_text(result).splitlines()[1].startswith("stricat.png:")


def test_T_A029_1_back_warns_when_the_list_has_files(qtbot, ctx, files, monkeypatch):
    s = screen(qtbot, ctx, "pdf", files)
    monkeypatch.setattr(ConvertScreen, "confirm_back", lambda self: False)
    assert not s.go_back()
    monkeypatch.setattr(ConvertScreen, "confirm_back", lambda self: True)
    with qtbot.waitSignal(s.back_requested):
        assert s.go_back()


def test_T_A017_1_complex_documents_go_to_the_ocr_editor(qtbot, ctx, files):
    s = screen(qtbot, ctx, "docx", files)
    with qtbot.waitSignal(s.ocr_editor_requested) as signal:
        s.findChild(QLabel, "convert_complex").linkActivated.emit("#")
    assert [p.name for p in signal.args[0]] == ["cerere.png", "anexa.png", "buget.png"]
