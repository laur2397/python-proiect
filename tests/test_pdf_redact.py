"""Redactarea si inlocuirea in PDF (faza 7, pasul 7.2b): C-015…C-018, C-025,
C-026, G-020, G-021."""

from __future__ import annotations

import io
import random

import pikepdf
import pytest
from PIL import Image
from test_pdf_search import TextEngine, text_pdf

from app.core.context import AppContext
from app.core.errors import RedactionVerificationError
from app.core.export.base import ExportOptions
from app.core.model import LayoutMode, Rect
from app.core.paths import AppPaths
from app.core.pdf import redact
from app.core.pdf.document import PdfDocument
from app.core.pdf.security import SecurityService
from app.core.pdf.text import SOURCE_TEXT


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def path(tmp_path):
    return text_pdf(tmp_path / "dosar.pdf", [
        ["Cerere de finantare", "Bugetul total: 1200 lei"],
        ["Anexa 2: buget detaliat", "Bugetare si BUGET"],
    ])


def all_stream_bytes(pdf_path) -> bytes:
    """Toate fluxurile decodate din fisier, ca textul ascuns sa nu scape."""
    out = []
    with pikepdf.open(pdf_path) as pdf:
        for obj in pdf.objects:
            if isinstance(obj, pikepdf.Stream):
                try:
                    out.append(obj.read_bytes())
                except pikepdf.PdfError:
                    out.append(obj.read_raw_bytes())
    return b"\n".join(out)


def text_hits(doc, query, **kw):
    return [h for h in doc.search(query, **kw) if h.source == SOURCE_TEXT]


# --- G-020, G-021 ---------------------------------------------------------------------


def test_T_G020_1_redacted_text_is_gone_from_page_and_file(path, tmp_path):
    with PdfDocument.open(path) as doc:
        hit = text_hits(doc, "1200")[0]
        page2_before = doc.extract_text(2)
        SecurityService().redact_regions(doc, [(1, r) for r in hit.rects])
        text = doc.extract_text(1)
        assert "1200" not in text
        for word in ("Cerere", "finantare", "Bugetul", "total:", "lei"):
            assert word in text
        assert doc.extract_text(2) == page2_before
        assert doc.page_count == 2
        assert doc.is_modified
        image = Image.open(io.BytesIO(doc.render_page(1, 2.0)))
        x = (hit.rect.x + hit.rect.w / 2) * 2 * 96 / 72
        y = (hit.rect.y + hit.rect.h / 2) * 2 * 96 / 72
        assert image.convert("L").getpixel((round(x), round(y))) < 40
        doc.save_as(tmp_path / "redactat.pdf")
    assert b"1200" not in all_stream_bytes(tmp_path / "redactat.pdf")
    with PdfDocument.open(tmp_path / "redactat.pdf") as saved:
        assert "1200" not in saved.extract_text(1)
        assert "Bugetul" in saved.extract_text(1)


def test_T_G020_2_annotations_in_the_area_are_deleted(path):
    with PdfDocument.open(path) as doc:
        # nota din fixture e la (300,500)-(320,520) in PDF → sus-stanga (300, 322)
        SecurityService().redact_regions(doc, [(1, Rect(295, 318, 30, 30))], "#202020")
        assert not doc._pike().pages[0].obj.Annots
        assert not [h for h in doc.search("verificat") if h.page == 1]


def test_T_G021_1_failed_verification_restores_the_document(path, monkeypatch):
    with PdfDocument.open(path) as doc:
        hit = text_hits(doc, "1200")[0]
        monkeypatch.setattr("app.core.pdf.security.rebuild_page", lambda *a, **k: None)
        with pytest.raises(RedactionVerificationError) as info:
            SecurityService().redact_regions(doc, [(1, hit.rect)])
        assert info.value.code == "REDACTION_VERIFICATION_FAILED"
        assert info.value.params["page_number"] == 1
        assert "1200" in doc.extract_text(1)
        assert not doc.is_modified


def test_T_G021_2_verification_checks_the_words(path, monkeypatch):
    with PdfDocument.open(path) as doc:
        real = redact.rebuild_page

        def wrong_area(document, number, edits, **kw):  # redacteaza alt loc decat trebuie
            real(document, number, [redact.PageEdit(Rect(400, 700, 20, 20))], **kw)

        monkeypatch.setattr("app.core.pdf.security.rebuild_page", wrong_area)
        with pytest.raises(RedactionVerificationError):
            SecurityService().redact_by_keywords(doc, ["1200"])
        assert "1200" in doc.extract_text(1)


def test_invalid_regions(path):
    with PdfDocument.open(path) as doc:
        with pytest.raises(ValueError):
            SecurityService().redact_regions(doc, [(3, Rect(0, 0, 10, 10))])
        with pytest.raises(ValueError):
            SecurityService().redact_regions(doc, [(1, Rect(0, 0, 0, 10))])
        with pytest.raises(ValueError):
            SecurityService().redact_regions(doc, [(1, Rect(0, 0, 10, 10))], "negru")
        assert not doc.is_modified


# --- C-025, C-026 ---------------------------------------------------------------------


def test_T_C026_1_redact_by_keywords(path):
    with PdfDocument.open(path) as doc:
        count = SecurityService().redact_by_keywords(doc, ["buget"], whole_word=True)
        assert count == 2  # "buget" si "BUGET", nu "Bugetul" / "Bugetare"
        assert text_hits(doc, "buget", whole_word=True) == []
        assert len(text_hits(doc, "Bugetul")) == 1
        assert len(text_hits(doc, "Bugetare")) == 1
        assert SecurityService().redact_by_keywords(doc, ["inexistent"]) == 0


def test_T_C026_2_redact_selected_hits_only(path):
    with PdfDocument.open(path) as doc:
        hits = doc.search("buget")
        chosen = [h for h in hits if h.source == SOURCE_TEXT and h.page == 2][:1]
        assert SecurityService().redact_hits(doc, chosen + [hits[-1]]) == 1
        assert [h.found for h in text_hits(doc, "buget")] == ["Buget", "Buget", "BUGET"]


def test_redaction_keeps_romanian_diacritics(tmp_path, ctx):
    image = tmp_path / "scan.png"
    img = Image.new("L", (600, 800), 255)
    img.paste(0, (60, 60, 540, 100))
    img.save(image, dpi=(300, 300))
    with PdfDocument.from_images([image], options=ExportOptions(layout_mode=LayoutMode.EXACT),
                                 context=ctx, engine=TextEngine(["ştampila", "țară"])) as doc:
        assert SecurityService().redact_by_keywords(doc, ["tara"]) == 0
        assert SecurityService().redact_by_keywords(doc, ["țară"]) == 1
        assert "ştampila" in doc.extract_text(1)
        assert "țară" not in doc.extract_text(1)


def test_redaction_on_rotated_page(tmp_path):
    path = text_pdf(tmp_path / "rotit.pdf", [["Cerere de finantare", "Suma 1200 lei"]])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.pages[0].obj.Rotate = 90
        pdf.save(path)
    with PdfDocument.open(path) as doc:
        assert SecurityService().redact_by_keywords(doc, ["1200"]) == 1
        text = doc.extract_text(1)
        assert "1200" not in text and "Suma" in text and "lei" in text
        assert doc._pike().pages[0].obj.Rotate == 90


# --- C-015…C-018 ----------------------------------------------------------------------


def test_T_C015_1_replace_text(path):
    original = path.read_bytes()
    with PdfDocument.open(path) as doc:
        hits = text_hits(doc, "1200")
        assert doc.replace_text(hits, "1500") == 1
        text = doc.extract_text(1)
        assert "1500" in text and "1200" not in text
        assert "Bugetul" in text and "lei" in text
        assert doc.is_modified  # C-017: se salveaza explicit
    assert path.read_bytes() == original


def test_T_C015_2_replace_with_empty_text_and_with_words(path):
    with PdfDocument.open(path) as doc:
        assert doc.replace_text(text_hits(doc, "Cerere"), "") == 1
        assert "Cerere" not in doc.extract_text(1)
        assert doc.replace_text(text_hits(doc, "lei"), "lei noi") == 1
        assert "noi" in doc.extract_text(1)


def test_T_C018_1_background_uniformity(tmp_path):
    from _pdftext import make_text_pdf

    rng = random.Random(7)
    noise = Image.new("L", (200, 100))
    noise.putdata([rng.randrange(256) for _ in range(200 * 100)])
    path = make_text_pdf(tmp_path / "fond.pdf", ["Text pe alb"], image=noise,
                         image_box=(72, 300, 300, 150))
    with PdfDocument.open(path) as doc:
        assert redact.background_is_uniform(doc, 1, Rect(72, 70, 100, 20))
        # zona peste imaginea cu zgomot: 842 - 450 = 392 sus, 150 inaltime
        assert not redact.background_is_uniform(doc, 1, Rect(120, 430, 60, 30))


def test_text_font_has_romanian_letters():
    path = redact.text_font_file()
    if path is None:
        pytest.skip("niciun font de sistem cu diacritice romanesti")
    from fontTools.ttLib import TTFont

    with TTFont(str(path), fontNumber=0, lazy=True) as font:
        cmap = font.getBestCmap()
    assert all(ord(ch) in cmap for ch in "șțȘȚăâî")
