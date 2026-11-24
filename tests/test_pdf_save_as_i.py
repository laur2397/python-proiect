"""PDF Editor: `Save As` in alte formate (I-013), `File options` (I-014) si
conversia unor pagini (I-015)."""

from __future__ import annotations

import os

import pytest
from docx import Document
from PIL import Image
from test_convert import ScriptEngine
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from app.core.context import AppContext
from app.core.convert import PDF_SAVE_AS_FORMATS, save_pdf_as
from app.core.model import ExportFormat
from app.core.paths import AppPaths
from app.gui.pdf_editor import PdfEditorWindow


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    yield c
    c.close()


@pytest.fixture
def pdf(tmp_path):
    return text_pdf(tmp_path / "dosar.pdf", [["Cerere"], ["Anexa"], ["Buget"]])


def test_T_I013_formats():
    assert PDF_SAVE_AS_FORMATS == (ExportFormat.DOCX, ExportFormat.XLSX, ExportFormat.PPTX,
                                   ExportFormat.HTML, ExportFormat.TIFF, ExportFormat.JPEG,
                                   ExportFormat.PNG)
    with pytest.raises(ValueError):
        save_pdf_as(None, None, ExportFormat.EPUB)


def test_T_I013_word_document(ctx, pdf, tmp_path):
    written = save_pdf_as(pdf, tmp_path / "out" / "rezultat.docx", ExportFormat.DOCX,
                          context=ctx, engine=ScriptEngine())
    assert [p.name for p in written] == ["rezultat.docx"]
    assert Document(written[0]).paragraphs  # textul recunoscut, in Word


def test_T_I014_one_file_per_page(ctx, pdf, tmp_path):
    written = save_pdf_as(pdf, tmp_path / "out" / "pagini.html", ExportFormat.HTML,
                          separate=True, context=ctx, engine=ScriptEngine())
    assert [p.name for p in written] == ["pagini-1.html", "pagini-2.html", "pagini-3.html"]


def test_T_I014_images_single_tiff_or_one_per_page(ctx, pdf, tmp_path):
    [tif] = save_pdf_as(pdf, tmp_path / "img" / "toate.tif", ExportFormat.TIFF, context=ctx)
    with Image.open(tif) as image:
        assert image.n_frames == 3
    pngs = save_pdf_as(pdf, tmp_path / "img" / "pagina.png", ExportFormat.PNG, context=ctx)
    assert len(pngs) == 3


def test_T_I015_only_some_pages(ctx, pdf, tmp_path):
    [tif] = save_pdf_as(pdf, tmp_path / "img" / "doua.tif", ExportFormat.TIFF,
                        pages=[1, 3], context=ctx)
    with Image.open(tif) as image:
        assert image.n_frames == 2


def test_T_I013_I015_from_the_window(qtbot, ctx, pdf, tmp_path, monkeypatch):
    window = PdfEditorWindow(ctx)
    qtbot.addWidget(window)
    window.open_path(pdf)
    names = {a.objectName() for a in window.save_menu.actions()}
    assert {f"pdf_save_as_{f.value}" for f in PDF_SAVE_AS_FORMATS} <= names
    monkeypatch.setattr(PdfEditorWindow, "ask_format_target",
                        lambda self, doc, fmt: tmp_path / "out" / f"ales.{fmt.value}")
    monkeypatch.setattr(PdfEditorWindow, "ask_file_options", lambda self, fmt: False)
    [png1, png2] = window.save_as_format("png", pages=[2, 3])  # meniul paginilor (I-015)
    assert png1.suffix == ".png" and png2.exists()
    menu = window.pages_menu(lambda: [1])
    convert = next(a.menu() for a in menu.actions() if a.menu() is not None)
    assert convert.objectName() == "organize_convert_menu"
    assert len(convert.actions()) == len(PDF_SAVE_AS_FORMATS)
    monkeypatch.setattr(PdfEditorWindow, "ask_file_options", lambda self, fmt: None)
    assert window.save_as_format("docx") == []  # renuntare la `File options`
    window.close()
