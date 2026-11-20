"""Teste pentru PDF-urile cu strat de text (faza 4, pasul 4.4)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from _pdftext import make_text_pdf
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.model import AutoProcessMode, PdfRecognitionMode, PreprocessOp
from app.core.ocr import textlayer
from app.core.ocr.engine import find_tesseract
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.core.settings import OcrSettings

LINES = ["Cerere de finantare pentru proiectul nr 4521",
         "Beneficiar: Societatea Exemplu, judetul Brasov",
         "Valoarea totala a proiectului este de 125000 lei"]
M = PdfRecognitionMode


class SpyEngine:
    """Motor fals: numara paginile trimise la OCR."""

    name = "spion"

    def __init__(self):
        self.pages = []

    def recognize_page(self, page, settings, cancel=None):
        from app.core.ocr.engine import RecognitionResult
        self.pages.append(page.page_number)
        return RecognitionResult(page.page_number)

    def recognize_area(self, page, area, settings, cancel=None):
        from app.core.ocr.engine import RecognitionResult
        self.pages.append(page.page_number)
        return RecognitionResult(page.page_number, area_blocks={area.id: []})


def scanned_pdf(path: Path) -> Path:
    img = Image.new("L", (1240, 1754), 255)
    ImageDraw.Draw(img).text((100, 100), "Scanare", fill=0)
    img.save(path, "PDF", resolution=150)
    return path


# =============================================================================
# Citire si evaluare (N-011)
# =============================================================================


def test_text_layer_is_read(tmp_path):
    text = textlayer.read_page(make_text_pdf(tmp_path / "d.pdf", LINES), 1)
    words = [w for w, _ in text.words]
    assert words[:4] == ["Cerere", "de", "finantare", "pentru"]
    assert (text.width_pt, text.height_pt) == (595.0, 842.0) and text.image_boxes == []
    left, bottom, right, top = text.words[0][1]
    assert 70 <= left < right and 740 < bottom < top < 790


def test_T_N011_1_text_layer_quality(tmp_path):
    """T-N011.1: un strat de text bun ia nota mare; unul stricat, mica."""
    good = textlayer.read_page(make_text_pdf(tmp_path / "g.pdf", LINES), 1)
    assert textlayer.evaluate(good) >= textlayer.TEXT_LAYER_MIN_QUALITY
    bad = textlayer.read_page(make_text_pdf(tmp_path / "b.pdf", ["#$% 0x3F @@ 1234 ~~ ^^ |||"]), 1)
    assert textlayer.evaluate(bad) < textlayer.TEXT_LAYER_MIN_QUALITY
    assert textlayer.read_page(tmp_path / "lipsa.pdf", 1) is None


# =============================================================================
# Alegerea modului (N-008, N-009, N-010)
# =============================================================================


def test_T_N008_1_mode_for_a_digital_pdf(tmp_path):
    """T-N008.1: PDF digital bun -> textul lui; `Use OCR` il forteaza pe OCR."""
    text = textlayer.read_page(make_text_pdf(tmp_path / "d.pdf", LINES), 1)
    assert textlayer.choose_mode(text, M.AUTO) is M.TEXT_ONLY
    assert textlayer.choose_mode(text, M.TEXT_ONLY) is M.TEXT_ONLY
    assert textlayer.choose_mode(text, M.FORCE_OCR) is M.FORCE_OCR  # N-010


def test_T_N009_1_scanned_pdfs_always_use_ocr(tmp_path):
    """T-N009.1: PDF-urile doar-imagine (si cele cautabile) folosesc mereu OCR."""
    scanned = textlayer.read_page(scanned_pdf(tmp_path / "s.pdf"), 1)
    assert textlayer.is_scanned(scanned)
    for requested in M:
        assert textlayer.choose_mode(scanned, requested) is M.FORCE_OCR
    assert textlayer.choose_mode(None, M.TEXT_ONLY) is M.FORCE_OCR


# =============================================================================
# In serviciul de recunoastere
# =============================================================================


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def project_with(ctx, *paths):
    p = OcrProject.create(context=ctx)
    p.add_images(list(paths), auto_process=AutoProcessMode.NONE)
    return p


def test_digital_pdf_keeps_its_text_without_ocr(ctx, tmp_path):
    p = project_with(ctx, make_text_pdf(tmp_path / "d.pdf", LINES))
    spy = SpyEngine()
    RecognitionService(p, engine=spy).recognize_pages()
    assert spy.pages == []  # niciun OCR
    text = p.page(1).text
    for line in LINES:
        assert line in text.replace("\n", " ")
    assert p.page(1).avg_confidence == 100.0
    p.close()


def test_forced_ocr_and_rotated_pages_use_the_engine(ctx, tmp_path):
    p = project_with(ctx, make_text_pdf(tmp_path / "a.pdf", LINES),
                     make_text_pdf(tmp_path / "b.pdf", LINES))
    p.preprocess_pages([2], [(PreprocessOp.ROTATE, {"angle": 180})])
    spy = SpyEngine()
    RecognitionService(p, engine=spy).recognize_pages([2])
    assert spy.pages == [2]  # pagina transformata: coordonatele nu mai corespund
    ctx.settings.set("ocr.pdf_mode", "ocr")
    RecognitionService(p, engine=spy).recognize_pages([1], skip_recognized=False)
    assert 1 in spy.pages
    p.close()


def test_service_helpers(ctx, tmp_path):
    p = project_with(ctx, make_text_pdf(tmp_path / "d.pdf", LINES))
    s = RecognitionService(p, engine=SpyEngine())
    assert s.evaluate_text_layer(tmp_path / "d.pdf", 1) >= 0.8
    assert s.choose_mode(tmp_path / "d.pdf", 1, OcrSettings()) is M.TEXT_ONLY
    p.close()


needs_ocr = pytest.mark.skipif(
    find_tesseract() is None and os.environ.get("DOCULENS_REQUIRE_OCR") != "1",
    reason="Tesseract nu e instalat")


@needs_ocr
def test_T_N012_1_mixed_document(ctx, tmp_path):
    """T-N012.1: textul digital se extrage, imaginea cu text se recunoaste,
    rezultatele se combina."""
    fonts = ["/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    font_path = next((f for f in fonts if Path(f).is_file()), None)
    if font_path is None:
        pytest.skip("niciun font")
    scan = Image.new("L", (1600, 400), 255)
    ImageDraw.Draw(scan).text((60, 140), "Stampila si semnatura", fill=0,
                              font=ImageFont.truetype(font_path, 90))
    pdf = make_text_pdf(tmp_path / "mixt.pdf", LINES, image=scan, image_box=(72, 300, 450, 112))
    ctx.settings.set("lang.mode", "manual")
    ctx.settings.set("lang.manual", ["ron"])
    p = project_with(ctx, pdf)
    RecognitionService(p).recognize_pages()
    text = p.page(1).text
    assert "Valoarea totala" in text  # din stratul de text
    assert "Stampila" in text and "semnatura" in text  # recunoscut din imagine
    p.close()
