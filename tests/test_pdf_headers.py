"""Antete si subsoluri (faza 9, pasul 9.2): F-039…F-044, Z-001…Z-012."""

from __future__ import annotations

import io
from datetime import datetime

import numpy as np
import pikepdf
import pytest
from PIL import Image
from test_pdf_search import text_pdf

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.core.pdf.decorate import HeaderFooter, HeaderFooterStore, expand_content
from app.core.pdf.document import PdfDocument
from app.core.pdf.editor import PdfContentEditor

MOMENT = datetime(2026, 2, 7, 14, 5, 9)


@pytest.fixture
def doc(tmp_path):
    path = text_pdf(tmp_path / "dosar.pdf", [[f"Pagina {n}"] for n in range(1, 6)])
    with PdfDocument.open(path) as d:
        yield d


def hit(doc, text):
    [found] = doc.search(text, in_comments=False, in_bookmarks=False, in_metadata=False)
    return found


def rendered(doc, page, zoom=1.0):
    return Image.open(io.BytesIO(doc.render_page(page, zoom))).convert("RGB")


# --- F-039, F-040 ----------------------------------------------------------------------------


@pytest.mark.parametrize("position", ["top_left", "top_center", "top_right",
                                      "bottom_left", "bottom_center", "bottom_right"])
def test_T_F039_six_positions_with_exact_margin(doc, position):
    PdfContentEditor(doc).add_header_footer(position=position, content="Antet XYZ",
                                            margin=1, margin_unit="in", pages=[1])
    found = hit(doc, "Antet XYZ")
    assert found[0] == 1
    rect = found[1]
    width, height = doc.page_size(1)
    if position.startswith("top"):
        assert rect.y == pytest.approx(72, abs=4)
    else:
        assert rect.y + rect.h == pytest.approx(height - 72, abs=4)
    horizontal = position.split("_")[1]
    if horizontal == "left":
        assert rect.x == pytest.approx(72, abs=2)
    elif horizontal == "right":
        assert rect.x + rect.w == pytest.approx(width - 72, abs=2)
    else:
        assert rect.x + rect.w / 2 == pytest.approx(width / 2, abs=2)


def test_T_F040_page_and_bates_numbers_and_continue_from(doc):
    editor = PdfContentEditor(doc)
    following = editor.add_header_footer(position="bottom_right",
                                         content="Pag. {page} din {pages} / {bates}",
                                         bates_start=41, bates_digits=6)
    assert following == 46  # `Continue from`
    for n in range(1, 6):
        assert f"Pag. {n} din 5 / {41 + n - 1:06d}" in doc.extract_text(n)
    editor.add_header_footer(position="top_right", content="{bates}", bates_start=following,
                             bates_digits=3, pages=[2])
    assert "046" in doc.extract_text(2)


def test_T_F040_date_and_time_tags(doc):
    PdfContentEditor(doc).add_header_footer(
        position="top_left", content="{date} <time/> <d=ROU/> <date=USA/>", pages=[1],
        moment=MOMENT)
    text = doc.extract_text(1)
    assert "14:05:09" in text and "07.02.2026" in text and "February" in text


# --- F-041, F-042 ----------------------------------------------------------------------------


def test_T_F041_font_size_color_and_effects(doc):
    PdfContentEditor(doc).add_header_footer(
        position="top_center", content="Confidential", font_size=24, text_color="#cc0000",
        bold=True, italic=True, underline=True, pages=[1])
    rect = hit(doc, "Confidential")[1]
    assert rect.h == pytest.approx(24, abs=8)
    image = rendered(doc, 1)
    scale = image.width / doc.page_size(1)[0]
    box = (int(rect.x * scale), int(rect.y * scale), int((rect.x + rect.w) * scale),
           int((rect.y + rect.h) * scale))
    pixels = np.asarray(image.crop(box)).reshape(-1, 3)
    reds = (pixels[:, 0] > 150) & (pixels[:, 1] < 80) & (pixels[:, 2] < 80)
    assert reds.any()  # culoarea textului


def test_T_F042_pages_the_header_applies_to(doc):
    PdfContentEditor(doc).add_header_footer(position="top_left", content="Numai impare",
                                            pages=[1, 3, 5])
    assert ["Numai impare" in doc.extract_text(n) for n in range(1, 6)] == \
        [True, False, True, False, True]
    with pytest.raises(ValueError):
        PdfContentEditor(doc).add_header_footer(position="top_left", content="x", pages=[9])


def test_header_follows_page_rotation(doc):
    from app.core.pdf.organize import PageOrganizer

    PageOrganizer(doc).rotate([2], 90)
    PdfContentEditor(doc).add_header_footer(position="top_center", content="SUS SUS SUS",
                                            font_size=30, pages=[2])
    image = rendered(doc, 2, 0.5).convert("L")
    w, h = image.size
    top = image.crop((0, 0, w, h // 6))
    bottom = image.crop((0, h - h // 6, w, h))
    assert top.getextrema()[0] < 100 and bottom.getextrema()[0] > 200


def test_header_is_a_pagination_artifact(doc):
    PdfContentEditor(doc).add_header_footer(position="bottom_center", content="{page}",
                                            pages=[1])
    ops = [(str(op), operands) for operands, op in
           pikepdf.parse_content_stream(doc._pike().pages[0])]
    assert any(op == "BDC" and operands[1].get("/Subtype") == "/Footer"
               for op, operands in ops)


def test_validation():
    for bad in (HeaderFooter(position="middle"), HeaderFooter(margin_unit="mm"),
                HeaderFooter(font_size=2000), HeaderFooter(content=" "),
                HeaderFooter(bates_digits=11)):
        with pytest.raises(ValueError):
            bad.validate()


# --- F-043, F-044 ----------------------------------------------------------------------------


def test_T_F043_F044_templates(tmp_path):
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    try:
        store = HeaderFooterStore(ctx.app_db)
        hf = HeaderFooter(position="top_right", content="Dosar {bates}", margin=2,
                          margin_unit="cm", font_name="Arial", font_size=9,
                          text_color="#112233", bates_start=1, bates_digits=4)
        store.save("Dosar", hf)
        with pytest.raises(ValueError):
            store.save("Dosar", hf)  # nume duplicat
        assert store.load("Dosar") == hf
        store.copy("Dosar", "Copie")
        changed = HeaderFooter(position="bottom_left", content="{page}")
        store.save("Copie", changed, replace_existing=True)  # `Save` dupa `Edit...`
        assert store.names() == ["Copie", "Dosar"]
        assert store.load("Copie").position == "bottom_left"
        store.delete("Dosar")
        assert store.names() == ["Copie"]
        with pytest.raises(KeyError):
            store.load("Dosar")
    finally:
        ctx.close()


# --- Z-001…Z-012 (etichetele de data folosite in antet) ---------------------------------------


@pytest.mark.parametrize(("content", "expected"), [
    ("<d=ROU/>", "07.02.2026"),                       # Z-001
    ("<date=USA/>", "February 7, 2026"),              # Z-002
    ("<t12=USA/>", "2:05 PM"),                        # Z-003
    ("<t24=ROU/>", "14:05"),                          # Z-004
    ("<time/>", "14:05:09"),                          # Z-005
    ("<d=%Y-%m-%d/>", "2026-02-07"),                  # Z-007
    ("<d=%#m.%#d/>", "2.7"),                          # Z-008, Z-009
    ("<t24=%#H:%M:%#S/>", "14:05:9"),                 # Z-010, Z-011
    ("<d=100%%/>", "100%"),                           # Z-012
])
def test_T_Z001_Z012_date_tags_in_headers(content, expected):
    text = expand_content(content, page=1, pages=1, bates=None, moment=MOMENT, region="ROU")
    assert expected in text
