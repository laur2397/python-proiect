"""Faza 6, pasul 6.2: PDF cautabil si PDF doar-imagine (Q-011, Q-012, Q-033,
Q-104, I-030, I-031, I-033)."""

from __future__ import annotations

from pathlib import Path

import pikepdf
import pypdfium2 as pdfium
import pytest
from PIL import Image

from app.core.export.base import ExportOptions, default_service
from app.core.export.pdf import WARNING_MRC_PRECISESCAN, glyphless_font
from app.core.model import (
    AreaData,
    AreaType,
    BlockData,
    ColorMode,
    ExportFormat,
    LayoutMode,
    LineData,
    PageData,
    PageStatus,
    PdfRecognitionMode,
    Rect,
    WordData,
)
from app.core.ocr import textlayer


def page(tmp_path, number, lines, mode="L", style=None):
    """O pagina A4 la 300 dpi, cu randurile date ca blocuri de cuvinte."""
    path = tmp_path / f"p{number}.png"
    Image.new(mode, (2480, 3508), 255 if mode != "1" else 1).save(path, dpi=(300, 300))
    p = PageData(number, number, path, path, 2480, 3508, 300, 300, ColorMode.GRAY,
                 status=PageStatus.RECOGNIZED)
    for i, (text, redacted) in enumerate(lines):
        words, x = [], 200
        for t in text.split():
            words.append(WordData(None, t, 95.0, bbox=Rect(x, 300 + 120 * i, 40 * len(t), 60),
                                  is_redacted=redacted))
            x += 40 * len(t) + 30
        block = BlockData(None, lines=[LineData(None, words=words)],
                          style_name=style if i == 0 else None)
        p.areas.append(AreaData(i + 1, AreaType.TEXT, [], i, bbox=Rect(0, 300 + 120 * i, 10, 10),
                                blocks=[block]))
    return p


def pdf_text(path: Path, index: int = 0) -> str:
    doc = pdfium.PdfDocument(str(path))
    try:
        return doc[index].get_textpage().get_text_range()
    finally:
        doc.close()


@pytest.fixture
def pages(tmp_path):
    return [page(tmp_path, 1, [("Județul Brașov, cerere de finanțare", False),
                               ("Cod secret 1234", True)], style="Heading 1"),
            page(tmp_path, 2, [("Anexa 2 bugetul proiectului", False)], mode="1",
                 style="Heading 2")]


def export(pages, target, **kw):
    options = ExportOptions(layout_mode=LayoutMode.EXACT, **kw)
    (out,) = default_service().export(pages, target, ExportFormat.PDF, options)
    return out


def test_T_Q011_1_searchable_pdf_text_with_romanian_letters(pages, tmp_path):
    """T-Q011.1 / I-031: textul se cauta si se copiaza cu ș, ț cu virgula."""
    out = export(pages, tmp_path / "c.pdf")
    first = pdf_text(out, 0)
    for w in ("Județul", "Brașov,", "finanțare"):
        assert w in first, first
    assert "secret" not in first and "1234" not in first  # O-072: textul redactat lipseste
    assert "bugetul" in pdf_text(out, 1)
    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 2
        box = [float(v) for v in pdf.pages[0].MediaBox]
        assert box[2] == pytest.approx(595.2, abs=0.5) and box[3] == pytest.approx(842, abs=0.5)
        image = pdf.pages[1].Resources.XObject.Im0
        assert int(image.BitsPerComponent) == 1  # pagina alb-negru, fara pierderi


def test_T_Q012_1_image_only_pdf_has_no_text(pages, tmp_path):
    """T-Q012.1 / Q-033, I-030: fara strat de text; merge in orice mod."""
    options = ExportOptions(layout_mode=LayoutMode.PLAIN, searchable=False)
    (out,) = default_service().export(pages, tmp_path / "i.pdf", ExportFormat.PDF, options)
    assert pdf_text(out, 0).strip() == ""
    with pikepdf.open(out) as pdf:
        assert "/Font" not in pdf.pages[0].Resources


def test_T_I033_1_scanned_pdfs_always_go_through_ocr(pages, tmp_path):
    """T-I033.1: PDF-ul cautabil si cel doar-imagine trec mereu prin OCR."""
    for name, searchable in (("c.pdf", True), ("i.pdf", False)):
        out = export(pages, tmp_path / name, searchable=searchable)
        text = textlayer.read_page(out, 1)
        mode = textlayer.choose_mode(text, PdfRecognitionMode.TEXT_ONLY)
        assert mode is not PdfRecognitionMode.TEXT_ONLY, name


def test_T_O041_2_bookmarks_from_headings(pages, tmp_path):
    out = export(pages, tmp_path / "b.pdf", create_bookmarks_from_headings=True)
    with pikepdf.open(out) as pdf, pdf.open_outline() as outline:
        (top,) = outline.root
        assert top.title.startswith("Județul Brașov")
        assert [c.title for c in top.children] == ["Anexa 2 bugetul proiectului"]
    out = export(pages, tmp_path / "nb.pdf")
    with pikepdf.open(out) as pdf, pdf.open_outline() as outline:
        assert list(outline.root) == []


def test_T_O054_2_links_become_pdf_links(pages, tmp_path):
    from app.core.text.links import Link

    link = Link(1, 1, "https://fonduri.ro", "x", (), Rect(200, 300, 400, 60))
    out = export(pages, tmp_path / "l.pdf", format_options={"links": {1: [link]}})
    with pikepdf.open(out) as pdf:
        (annot,) = pdf.pages[0].Annots
        assert str(annot.A.URI) == "https://fonduri.ro"


def test_T_Q104_1_mrc_with_precisescan_warns(pages):
    options = ExportOptions(layout_mode=LayoutMode.EXACT,
                            format_options={"use_mrc": True, "smooth_characters": True})
    warnings = default_service().check_before_export(pages, options, ExportFormat.PDF)
    assert [w.message for w in warnings] == [WARNING_MRC_PRECISESCAN]


def test_glyphless_font_maps_every_character():
    from io import BytesIO

    from fontTools.ttLib import TTFont

    font = TTFont(BytesIO(glyphless_font(["ș", "ț", "A"])))
    assert font.getBestCmap()[ord("ș")] == "g1" and len(font.getGlyphOrder()) == 4
