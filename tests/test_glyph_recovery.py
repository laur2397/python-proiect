"""F-057: GlyphRecovery. Un PDF cu fontul corect pe pagina, dar cu tabelul cod →
caracter stricat (textul se copiaza `Braºov`), se repara: textul se copiaza
`Brașov`, iar aspectul paginii ramane acelasi."""

from __future__ import annotations

from pathlib import Path

import pikepdf
import pytest

from app.core.context import AppContext
from app.core.model import Rect
from app.core.ocr.engine import find_tesseract
from app.core.paths import AppPaths
from app.core.pdf.document import PdfDocument
from app.core.pdf.embedded_font import embed_text_font
from app.core.pdf.glyph_recovery import (
    _words,
    code_map,
    page_chars,
    parse_to_unicode,
    recover_glyphs,
    to_unicode_stream,
)

LINES = ["Județul Brașov, strada Ștefan cel Mare", "Asociația Țara Bârsei și școala",
         "Cererea de finanțare se depune până în iulie"]
BAD = {"ș": "º", "ț": "þ", "Ș": "ª", "Ț": "Þ"}


def _pdf(path: Path, *, broken: bool) -> Path:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(595, 842))
    font = embed_text_font(pdf, LINES)
    ops = [f"BT /F1 16 Tf 60 {760 - i * 40} Td {font.encode(line)} Tj ET"
           for i, line in enumerate(LINES)]
    page = pdf.pages[0]
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font.font))
    page.Contents = pdf.make_stream("\n".join(ops).encode("latin-1"))
    if broken:
        mapping, width = parse_to_unicode(font.font.ToUnicode.read_bytes())
        font.font.ToUnicode = pdf.make_stream(to_unicode_stream(
            {c: BAD.get(t, t) for c, t in mapping.items()}, width))
    pdf.save(path)
    return path


def _truth_ocr(good: Path):
    """OCR fals: cuvintele corecte, in pozitiile lor, citite din PDF-ul intact."""
    doc = PdfDocument.open(good)
    words = [("".join(c.text for c in w),
              Rect(min(c.box.x for c in w), min(c.box.y for c in w),
                   max(c.box.right for c in w) - min(c.box.x for c in w),
                   max(c.box.bottom for c in w) - min(c.box.y for c in w)))
             for w in _words(page_chars(doc, 1))]
    doc.close()

    def ocr(_image, dpi):
        k = dpi / 72
        return [(t, Rect(b.x * k, b.y * k, b.w * k, b.h * k)) for t, b in words]

    return ocr


@pytest.fixture
def pair(tmp_path):
    return _pdf(tmp_path / "bun.pdf", broken=False), _pdf(tmp_path / "stricat.pdf", broken=True)


def test_T_F057_broken_encoding_is_repaired(pair, tmp_path):
    good, broken = pair
    doc = PdfDocument.open(broken)
    assert "Braºov" in doc.extract_text(1)
    report = recover_glyphs(doc, ocr=_truth_ocr(good))
    assert report.changed and report.pages == [1]
    assert report.fonts["DocuLensText"] == {"º": "ș", "þ": "ț", "ª": "Ș", "Þ": "Ț"}
    text = doc.extract_text(1)
    for line in LINES:
        assert line in text
    assert doc.is_modified
    doc.save_as(tmp_path / "reparat.pdf")  # repararea ramane in fisier
    doc.close()
    again = PdfDocument.open(tmp_path / "reparat.pdf")
    assert "Județul Brașov, strada Ștefan" in again.extract_text(1)
    again.close()


def test_T_F057_page_looks_the_same(pair):
    good, broken = pair
    doc = PdfDocument.open(broken)
    before = doc.render_page(1, 1.0, annotations=False)
    recover_glyphs(doc, ocr=_truth_ocr(good))
    assert doc.render_page(1, 1.0, annotations=False) == before  # numai ToUnicode
    doc.close()


def test_T_F057_correct_document_is_not_touched(pair):
    good, _broken = pair
    doc = PdfDocument.open(good)
    report = recover_glyphs(doc, ocr=_truth_ocr(good))
    assert not report.changed and not doc.is_modified


def test_T_F057_ocr_mistakes_do_not_change_a_good_font(pair):
    good, _broken = pair
    truth = _truth_ocr(good)

    def sloppy(image, dpi):  # OCR-ul greseste o data `a` → `o`
        words = truth(image, dpi)
        text, box = words[2]
        return [*words[:2], (text.replace("a", "o", 1), box), *words[3:]]

    doc = PdfDocument.open(good)
    assert not recover_glyphs(doc, ocr=sloppy).changed
    doc.close()


def test_T_F057_simple_font_encoding_is_inverted():
    """Un font simplu fara ToUnicode: codificarea WinAnsi se inverseaza (0xBA = `º`)."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Times,
        Encoding=pikepdf.Name.WinAnsiEncoding))
    mapping, width = code_map(font)
    assert width == 1 and mapping[0xBA] == "º" and mapping[ord("a")] == "a"
    differences = pikepdf.Dictionary(Type=pikepdf.Name.Encoding,
                                     BaseEncoding=pikepdf.Name.WinAnsiEncoding,
                                     Differences=[0xBA, pikepdf.Name("/scommaaccent")])
    font.Encoding = differences
    assert code_map(font)[0][0xBA] == "ș"


def test_T_F057_to_unicode_round_trip():
    mapping = {0x41: "A", 0x0219: "ș", 0x12: "fi"}
    parsed, width = parse_to_unicode(to_unicode_stream(mapping, 2))
    assert parsed == mapping and width == 2
    ranges = (b"1 begincodespacerange <00> <FF> endcodespacerange\n"
              b"1 beginbfrange <41> <43> <0041> endbfrange\n"
              b"1 beginbfrange <61> <62> [<0219> <021B>] endbfrange")
    parsed, width = parse_to_unicode(ranges)
    assert parsed == {0x41: "A", 0x42: "B", 0x43: "C", 0x61: "ș", 0x62: "ț"} and width == 1


@pytest.mark.skipif(find_tesseract() is None, reason="Tesseract nu e instalat")
def test_T_F057_with_real_recognition(pair, tmp_path):
    _good, broken = pair
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    try:
        doc = PdfDocument.open(broken)
        report = doc.recover_glyphs(context=ctx)
        assert report["fonts"]
        text = doc.extract_text(1)
        assert "Brașov" in text and "Județul" in text and "Ștefan" in text
        doc.close()
    finally:
        ctx.close()


def test_T_F057_repair_command_in_the_pdf_editor(qtbot, pair, tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from app.core.pdf import glyph_recovery
    from app.gui.i18n import tr
    from app.gui.pdf_editor import PdfEditorWindow

    good, broken = pair
    monkeypatch.setattr(glyph_recovery, "_default_ocr",
                        lambda context, engine, languages: _truth_ocr(good))
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    try:
        ctx.settings.set("image.background_recognition_pdf", False)
        window = PdfEditorWindow(ctx)
        qtbot.addWidget(window)
        messages = []
        window.show_message = messages.append
        window.open_path(broken)
        action = next(a for a in window.recognize_menu.actions()
                      if a.objectName() == "pdf_glyph_recovery")
        action.trigger()
        assert "Brașov" in window.current().document.extract_text(1)
        assert messages[-1] == tr("pdf.glyph_recovery.done", fonts=1, chars=4)
        window.undo()  # un pas de Undo
        assert "Braºov" in window.current().document.extract_text(1)
        window.repair_text()
        window.repair_text()  # a doua oara: nimic de reparat
        assert messages[-1] == tr("pdf.glyph_recovery.nothing")
        window.close()
    finally:
        ctx.close()


def test_T_F057_known_alphabet():
    from app.core.pdf.glyph_recovery import ROMANIAN_TEXT, _alphabet

    assert _alphabet(["ron"]) is ROMANIAN_TEXT and _alphabet(["ron", "eng"]) is ROMANIAN_TEXT
    assert _alphabet(["ron", "deu"]) is None and _alphabet(["eng"]) is None
    assert "ș" in ROMANIAN_TEXT and "º" not in ROMANIAN_TEXT and "Þ" not in ROMANIAN_TEXT
