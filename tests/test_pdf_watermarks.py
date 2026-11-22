"""Filigranele si stergerea zonelor (faza 9, pasul 9.2): F-024, F-025, F-045…F-050."""

from __future__ import annotations

import io

import numpy as np
import pikepdf
import pytest
from PIL import Image
from test_pdf_search import text_pdf

from app.core.model import Rect
from app.core.pdf.decorate import Watermark
from app.core.pdf.document import PdfDocument
from app.core.pdf.editor import PdfContentEditor


@pytest.fixture
def doc(tmp_path):
    path = text_pdf(tmp_path / "dosar.pdf", [[f"Pagina {n}", "Al doilea rand"]
                                            for n in range(1, 4)])
    with PdfDocument.open(path) as d:
        yield d


def gray(doc, page, zoom=0.5):
    return np.asarray(Image.open(io.BytesIO(doc.render_page(page, zoom))).convert("L"))


def operators(doc, page):
    return [(str(op), operands) for operands, op in
            pikepdf.parse_content_stream(doc._pike().pages[page - 1])]


def watermark_marks(doc, page):
    return [o for op, o in operators(doc, page)
            if op == "BDC" and isinstance(o[1], pikepdf.Dictionary)
            and o[1].get("/Subtype") == "/Watermark"]


def find(doc, text):
    return doc.search(text, in_comments=False, in_bookmarks=False, in_metadata=False)


# --- F-045…F-049 ------------------------------------------------------------------------------


def test_T_F045_text_watermark_in_the_center(doc):
    before = gray(doc, 2)  # pagina 1 are o nota la mijloc
    PdfContentEditor(doc).add_watermark(text="CONFIDENTIAL", opacity=1.0, pages=[2])
    after = gray(doc, 2)
    h, w = after.shape
    middle = (slice(h * 2 // 5, h * 3 // 5), slice(w // 5, w * 4 // 5))
    assert after[middle].min() < 200 and before[middle].min() > 240
    assert "CONFIDENTIAL" in doc.extract_text(2)


@pytest.mark.parametrize("position", ["top_left", "top_right", "bottom_left",
                                      "bottom_right", "middle_left", "center"])
def test_T_F045_nine_positions(doc, position):
    PdfContentEditor(doc).add_watermark(text="FILIGRAN", position=position, rotation=0,
                                        font_size=20, pages=[1])
    [hit] = find(doc, "FILIGRAN")
    rect = hit[1]
    width, height = doc.page_size(1)
    row, _, col = position.partition("_") if position != "center" else ("middle", "", "center")
    cx, cy = rect.x + rect.w / 2, rect.y + rect.h / 2
    assert {"left": cx < width / 3, "center": abs(cx - width / 2) < 5,
            "right": cx > width * 2 / 3}[col]
    assert {"top": cy < height / 3, "middle": abs(cy - height / 2) < 10,
            "bottom": cy > height * 2 / 3}[row]


def test_T_F045_offset_moves_the_watermark(doc):
    editor = PdfContentEditor(doc)
    editor.add_watermark(text="QWERTY", rotation=0, font_size=20, pages=[1])
    editor.add_watermark(text="ZXCVB", rotation=0, font_size=20, offset=(100, 50), pages=[2])
    one, two = find(doc, "QWERTY")[0][1], find(doc, "ZXCVB")[0][1]
    assert (two.x + two.w / 2) - (one.x + one.w / 2) == pytest.approx(100, abs=4)
    assert (two.y + two.h / 2) - (one.y + one.h / 2) == pytest.approx(50, abs=4)


def test_T_F046_rotation_and_transparency(doc):
    PdfContentEditor(doc).add_watermark(text="ROTIT", rotation=90, opacity=0.25,
                                        font_size=40, pages=[1])
    [hit] = find(doc, "ROTIT")
    assert hit[1].h > hit[1].w  # textul sta vertical
    states = doc._pike().pages[0].obj.Resources.ExtGState
    assert any(float(s.ca) == pytest.approx(0.25) for _name, s in states.items())


def test_T_F047_above_or_beneath_the_page_content(doc):
    editor = PdfContentEditor(doc)
    editor.add_watermark(text="SUB", behind_content=True, pages=[1])
    editor.add_watermark(text="PESTE", behind_content=False, pages=[2])
    assert operators(doc, 1)[0][0] == "BDC"  # primul lucru desenat: sub continut
    second = operators(doc, 2)
    assert second[0][0] != "BDC" and any(op == "BDC" for op, _o in second[-30:])


def test_T_F048_F049_pages_and_several_watermarks(doc):
    editor = PdfContentEditor(doc)
    editor.add_watermark(text="CIORNA", pages=[1, 3])
    editor.add_watermark(text="INTERN", pages=[3])
    assert [len(watermark_marks(doc, n)) for n in (1, 2, 3)] == [1, 0, 2]


def test_image_watermark_with_transparency(doc, tmp_path):
    logo = tmp_path / "sigla.png"
    image = Image.new("RGBA", (200, 100), (0, 0, 255, 0))
    image.paste((0, 0, 255, 255), (50, 25, 150, 75))
    image.save(logo)
    PdfContentEditor(doc).add_watermark(image=logo, rotation=0, opacity=1.0, pages=[1])
    rgb = np.asarray(Image.open(io.BytesIO(doc.render_page(1, 0.5))).convert("RGB"))
    blue = (rgb[:, :, 2] > 200) & (rgb[:, :, 0] < 60)
    assert blue.any()
    with pytest.raises(ValueError):
        Watermark(text="A", image=logo).validate()
    with pytest.raises(ValueError):
        Watermark().validate()


# --- F-050 ----------------------------------------------------------------------------------


def foreign_watermarks(doc):
    """Filigrane puse de alte programe: un artefact marcat, o forma de tip
    Acrobat si o adnotare /Watermark."""
    pdf = doc._pike()
    page = pdf.pages[1]
    page.contents_add(pdf.make_stream(
        b"/Artifact <</Type /Pagination /Subtype /Watermark>> BDC "
        b"q 0.5 g 100 100 200 200 re f Q EMC"))
    form = pdf.make_stream(b"0.8 g 0 0 50 50 re f", Type=pikepdf.Name.XObject,
                           Subtype=pikepdf.Name.Form, BBox=[0, 0, 50, 50],
                           PieceInfo=pikepdf.Dictionary(ADBE_CompoundType=pikepdf.Dictionary(
                               Private=pikepdf.Name.Watermark)))
    page.obj.Resources.XObject = pikepdf.Dictionary(Fm0=form)
    page.contents_add(pdf.make_stream(b"q /Fm0 Do Q"))
    annot = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Watermark, Rect=[0, 0, 100, 100]))
    page.obj.Annots = pdf.make_indirect(pikepdf.Array([annot]))
    doc._changed()


def test_T_F050_delete_watermarks_removes_all_of_them(doc):
    editor = PdfContentEditor(doc)
    editor.add_watermark(text="CIORNA")
    foreign_watermarks(doc)
    assert editor.remove_watermarks() == 3 + 3  # ale noastre (3 pagini) + 3 straine
    for n in (1, 2, 3):
        assert watermark_marks(doc, n) == []
        assert "CIORNA" not in doc.extract_text(n)
        assert f"Pagina {n}" in doc.extract_text(n)  # restul paginii ramane
    assert len(doc._pike().pages[1].obj.get("/Annots", [])) == 0
    assert editor.remove_watermarks() == 0


def test_delete_watermarks_keeps_headers(doc):
    editor = PdfContentEditor(doc)
    editor.add_header_footer(position="bottom_center", content="Pagina {page} total")
    editor.add_watermark(text="CIORNA")
    editor.remove_watermarks()
    assert "Pagina 1 total" in doc.extract_text(1)


# --- F-024, F-025 ---------------------------------------------------------------------------


def test_T_F024_F025_erase_removes_content_and_text_and_fills_background(doc):
    rect = find(doc, "Pagina 2")[0][1]
    area = Rect(rect.x - 2, rect.y - 2, rect.w + 4, rect.h + 4)
    PdfContentEditor(doc).erase_region(2, area)
    text = doc.extract_text(2)
    assert "Pagina 2" not in text and "Al doilea rand" in text
    pixels = gray(doc, 2, 1.0)
    scale = pixels.shape[1] / doc.page_size(2)[0]
    patch = pixels[int(rect.y * scale):int((rect.y + rect.h) * scale),
                   int(rect.x * scale):int((rect.x + rect.w) * scale)]
    assert patch.min() > 240  # fundalul alb completat
    with pytest.raises(ValueError):
        PdfContentEditor(doc).erase_region(2, Rect(0, 0, 0, 10))


def test_erase_keeps_annotations(doc):
    PdfContentEditor(doc).erase_region(1, Rect(60, 60, 200, 40))
    assert len(doc.annotations(1)) == 1  # nota de pe pagina 1 ramane
