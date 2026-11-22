"""Recunoasterea in fundal si stratul de text permanent (faza 7, pasul 7.6):
B-028…B-033, plus folosirea stratului temporar la cautare, copiere, marcaje."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.model import (
    AnnotationData,
    AnnotationType,
    BlockData,
    LineData,
    Rect,
    WordData,
)
from app.core.ocr.engine import RecognitionResult
from app.core.paths import AppPaths
from app.core.pdf import background, copying, navigation
from app.core.pdf.document import PdfDocument


class LineEngine:
    """Motor OCR fals: un rand cu cuvintele date, in pixelii paginii (300 dpi)."""

    name = "fals"

    def __init__(self, words, fail=False):
        self.words = words
        self.fail = fail
        self.calls = 0

    def _block(self):
        words = [WordData(None, w, 95.0, bbox=Rect(120 + i * 400, 120, 360, 80))
                 for i, w in enumerate(self.words)]
        line = LineData(None, words=words, bbox=Rect(120, 120, 400 * len(words), 80))
        return BlockData(None, lines=[line], bbox=line.bbox)

    def recognize_page(self, page, settings, cancel=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("motorul a cazut")
        block = self._block()
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=95.0,
                                 area_blocks={a.id: [block] for a in page.areas[:1]})

    def recognize_area(self, page, area, settings, cancel=None):
        result = self.recognize_page(page, settings)
        return RecognitionResult(page.page_number, blocks=result.blocks,
                                 avg_confidence=95.0, area_blocks={area.id: result.blocks})


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def scan(tmp_path):
    """Un PDF scanat: 1200x1600 px la 300 dpi (288x384 pt), cu o banda neagra."""
    img = Image.new("L", (1200, 1600), 255)
    img.paste(0, (120, 120, 1080, 200))
    path = tmp_path / "scan.pdf"
    img.save(path, "PDF", resolution=300)
    return path


def ocr(doc, ctx, words=("Cerere", "aprobata"), **kw):
    engine = LineEngine(list(words), **kw)
    done = doc.recognize_in_background(context=ctx, engine=engine)
    return engine, done


def text_only(doc, query):
    return doc.search(query, in_comments=False, in_bookmarks=False, in_metadata=False)


# --- B-028, B-029 ---------------------------------------------------------------------


def test_T_B028_1_temporary_layer_makes_scan_searchable(scan, ctx):
    with PdfDocument.open(scan) as doc:
        assert background.pages_without_text(doc) == [1]
        assert text_only(doc, "Cerere") == []
        _engine, done = ocr(doc, ctx)
        assert done == [1]
        assert background.pages_without_text(doc) == []
        [hit] = text_only(doc, "cerere")
        assert hit.page == 1
        assert (hit.rect.x, hit.rect.y) == pytest.approx((120 * 72 / 300, 120 * 72 / 300))
        assert hit.rect.w == pytest.approx(360 * 72 / 300)
        assert not doc.has_text_layer(1)  # stratul temporar nu e in fisier
        assert not doc.is_modified


def test_T_B029_1_temporary_layer_is_never_saved(scan, ctx, tmp_path):
    with PdfDocument.open(scan) as doc:
        ocr(doc, ctx)
        doc.save_as(tmp_path / "copie.pdf")
    with PdfDocument.open(tmp_path / "copie.pdf") as saved:
        assert not saved.has_text_layer(1)
        assert text_only(saved, "Cerere") == []


def test_T_B028_2_failure_is_silent(scan, ctx):
    with PdfDocument.open(scan) as doc:
        engine, done = ocr(doc, ctx, fail=True)
        assert done == [] and engine.calls >= 1
        assert background.pages_without_text(doc) == [1]


def test_T_B028_3_pages_with_text_are_skipped(tmp_path, ctx):
    from test_pdf_search import text_pdf

    with PdfDocument.open(text_pdf(tmp_path / "t.pdf", [["Text"]])) as doc:
        engine, done = ocr(doc, ctx)
        assert done == [] and engine.calls == 0


def test_T_B030_1_single_core_disables_it(scan, ctx, monkeypatch):
    monkeypatch.setattr(background.os, "cpu_count", lambda: 1)
    assert not background.available()
    assert not background.enabled(ctx.settings)
    with PdfDocument.open(scan) as doc:
        engine, done = ocr(doc, ctx)
        assert done == [] and engine.calls == 0


def test_T_B033_1_can_be_disabled_in_options(ctx, monkeypatch):
    monkeypatch.setattr(background.os, "cpu_count", lambda: 8)
    assert background.enabled(ctx.settings)  # activa implicit
    ctx.settings.set(background.SETTING, False)
    assert not background.enabled(ctx.settings)


# --- folosirea stratului temporar -----------------------------------------------------


def test_temporary_layer_feeds_copy_links_and_markup(scan, ctx):
    with PdfDocument.open(scan) as doc:
        ocr(doc, ctx, words=("Vezi", "www.exemplu.ro"))
        copied = copying.area_text(doc, 1, Rect(20, 20, 250, 40))
        assert copied.text == "Vezi www.exemplu.ro" and not copied.from_ocr
        assert [link.uri for link in navigation.detect_links(doc, 1)] == \
            ["http://www.exemplu.ro"]
        hit = text_only(doc, "Vezi")[0]
        created = doc.add_annotation(AnnotationData(None, AnnotationType.HIGHLIGHT, 1,
                                                    {"rects": list(hit.rects)}))
        assert created.annot_type is AnnotationType.HIGHLIGHT  # D-002: pe scanari, cu OCR


# --- B-032 ----------------------------------------------------------------------------


def test_T_B032_1_store_the_text_layer_permanently(scan, ctx, tmp_path):
    with PdfDocument.open(scan) as doc:
        engine, _done = ocr(doc, ctx)
        calls = engine.calls
        stored = doc.recognize_and_store(context=ctx, engine=engine)
        assert stored == [1]
        assert engine.calls == calls  # stratul temporar s-a refolosit
        assert doc.is_modified and doc.has_text_layer(1)
        assert "Cerere aprobata" in doc.extract_text(1)
        image = Image.open(io.BytesIO(doc.render_page(1, 1.0))).convert("L")
        assert image.getpixel((round(150 * 96 / 300), round(150 * 96 / 300))) < 50  # banda
        doc.save_as(tmp_path / "cautabil.pdf")
    with PdfDocument.open(tmp_path / "cautabil.pdf") as saved:
        [hit] = text_only(saved, "aprobata")
        assert hit.rect.x == pytest.approx(520 * 72 / 300, abs=2)
        assert saved.recognize_and_store(context=ctx, engine=LineEngine(["x"])) == []


def test_T_B032_2_store_with_chosen_languages_recognizes_again(scan, ctx):
    with PdfDocument.open(scan) as doc:
        ocr(doc, ctx)
        engine = LineEngine(["Altceva"])
        assert doc.recognize_and_store(languages=["ron"], context=ctx, engine=engine) == [1]
        assert engine.calls >= 1  # alte limbi: se recunoaste din nou
        assert "Altceva" in doc.extract_text(1)
        with pytest.raises(ValueError):
            doc.recognize_and_store(pages=[3], context=ctx, engine=engine)
