"""Faza 16, pasul 16.1: tabelul formatelor (Y-100…Y-112)."""

from __future__ import annotations

import io
import os

import pytest
from test_hotfolder import _image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.context import AppContext
from app.core.errors import UnsupportedFormatError
from app.core.formats import (
    FORMATS,
    accepted,
    by_extension,
    extensions_for,
    input_only,
    open_in_pdf_editor,
    output_formats,
    status,
)
from app.core.paths import AppPaths


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def test_T_Y100_each_format_has_distinct_capabilities():
    assert len(FORMATS) == 26  # randurile din B.1
    pdf = by_extension("a.PDF")
    assert (pdf.ocr_editor, pdf.pdf_editor, pdf.compare, pdf.output) == (True,) * 4
    word = by_extension("a.docx")
    assert (word.ocr_editor, word.pdf_editor, word.compare, word.output) == \
        (False, True, True, True)
    gif = by_extension("a.gif")
    assert (gif.ocr_editor, gif.pdf_editor, gif.compare, gif.output) == \
        (True, True, True, False)


def test_T_Y101_formats_only_where_the_module_accepts_them():
    assert ".docx" not in extensions_for("ocr_editor")  # editabil: nu in OCR Editor
    assert ".docx" in extensions_for("pdf_editor") and ".docx" in extensions_for("compare")
    assert ".png" in extensions_for("ocr_editor")
    assert ".webp" not in extensions_for("ocr_editor")  # nu e in B.1
    assert status("a.docx", "ocr_editor") == "not_in_module"
    assert status("a.xyz", "pdf_editor") == "unknown"


def test_T_Y102_csv_fb2_epub_only_output():
    for ext in (".csv", ".fb2", ".epub"):
        assert not any(accepted(f"a{ext}", m) for m in ("ocr_editor", "pdf_editor", "compare"))
        assert by_extension(f"a{ext}") in output_formats()
    from app.gui.filters import conversion_filter, open_filter

    assert "*.epub" not in conversion_filter() and "*.epub" not in open_filter("pdf_editor")


def test_T_Y103_input_only_formats():
    keys = {f.key for f in input_only()}
    assert {"gif", "svg", "xps", "powerpoint_old", "ods", "odp", "visio"} <= keys
    assert not any(f.output for f in FORMATS if f.key in keys)


def test_T_Y104_svg_only_in_pdf_editor():
    assert accepted("a.svg", "pdf_editor")
    assert not accepted("a.svg", "ocr_editor") and not accepted("a.svg", "compare")
    assert not by_extension("a.svg").output


def test_T_Y105_visio_in_pdf_editor_not_compare():
    assert accepted("a.vsdx", "pdf_editor") and not accepted("a.vsdx", "compare")


def test_T_Y106_unread_formats_say_so(tmp_path):
    xps = tmp_path / "a.xps"
    xps.write_bytes(b"PK")
    assert status(xps, "pdf_editor") == "not_supported"
    with pytest.raises(UnsupportedFormatError) as caught:
        open_in_pdf_editor(xps)
    assert caught.value.params["reason"] == "not_supported"
    assert status("a.doc", "pdf_editor") == "not_supported"  # Word 97-2003
    assert ".doc" not in extensions_for("pdf_editor") and ".docx" in extensions_for("pdf_editor")


def test_T_Y107_editable_text_without_office(tmp_path):
    from docx import Document

    path = tmp_path / "Cerere.docx"
    doc = Document()
    doc.add_paragraph("Solicitare de rambursare")
    doc.save(path)
    document = open_in_pdf_editor(path)
    try:
        assert document.page_count == 1 and document.path is None and document.is_modified
    finally:
        document.close()


def test_T_Y109_comparison_saves_only_pdf_and_docx():
    from app.cli.main import UsageError, parse_compare

    for ext in (".pdf", ".docx"):
        parse_compare(["/compare", "/file1:a.pdf", "/file2:b.pdf", f"/saveFile:o{ext}"])
    with pytest.raises(UsageError):
        parse_compare(["/compare", "/file1:a.pdf", "/file2:b.pdf", "/saveFile:o.xlsx"])


def test_T_Y111_pdfa_conformance_in_properties(tmp_path):
    import pikepdf

    from app.core.pdf.document import PdfDocument

    path = tmp_path / "a.pdf"
    pdf = pikepdf.new()
    pdf.add_blank_page()
    with pdf.open_metadata() as meta:
        meta["pdfaid:part"] = "2"
        meta["pdfaid:conformance"] = "B"
    pdf.save(path)
    document = PdfDocument.open(path)
    try:
        assert document.properties()["pdfa"] == "PDF/A-2b"
    finally:
        document.close()


def test_T_Y112_listformats_and_dialog(qtbot, ctx):
    from app.cli.main import Services, run_ocr
    from app.gui.formats_dialog import FormatsDialog
    from app.gui.i18n import tr

    out = io.StringIO()
    assert run_ocr(["/listformats"], Services(context=ctx, stdout=out)) == 0
    lines = out.getvalue().splitlines()
    assert any(line.startswith(".pdf") and "xxxx" in line for line in lines)
    assert any(line.startswith(".svg") and "-x--" in line for line in lines)
    dialog = FormatsDialog()
    qtbot.addWidget(dialog)
    assert dialog.table.rowCount() == 26
    assert dialog.table.item(0, 2).text() == tr("formats.yes")


def test_T_Y101_pdf_editor_opens_images_editable_and_svg(qtbot, ctx, tmp_path):
    from app.gui.i18n import tr
    from app.gui.pdf_editor import PdfEditorWindow

    window = PdfEditorWindow(ctx)
    qtbot.addWidget(window)
    window.show_message = lambda text: window.messages.append(text)
    window.messages = []
    assert window.open_path(_image(tmp_path / "scan.png")) is not None  # imagine → PDF
    svg = tmp_path / "desen.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">'
                   '<rect width="200" height="100" fill="blue"/></svg>', encoding="utf-8")
    assert window.open_path(svg) is not None  # Y-104
    xps = tmp_path / "a.xps"
    xps.write_bytes(b"PK")
    assert window.open_path(xps) is None
    assert window.messages == [tr("formats.not_supported", name="a.xps")]
    window.close()
