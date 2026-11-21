"""Faza 4, pasul 4.5.5: catalogul limbilor (P-002..P-008, P-100, P-104, P-105,
P-110) si limbile recente (P-004)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.model import AreaData, AreaType, ColorMode, PageData, Rect
from app.core.ocr import languages
from app.core.ocr.engine import RecognitionResult, find_tesseract
from app.core.ocr.languages import LanguageRegistry, tesseract_spec
from app.core.paths import AppPaths
from app.core.settings import OcrSettings


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def test_T_P005_1_three_categories_and_our_own_count():
    """T-P005.1 / P-100: lista e a noastra, in trei categorii; P-104, P-105."""
    reg = LanguageRegistry()
    natural = reg.by_category(languages.NATURAL)
    assert len(natural) > 100 and "ron" in natural and "eng" in natural
    assert set(reg.by_category(languages.ARTIFICIAL)) == {"ido", "ina", "ile", "epo"}
    formal = set(reg.by_category(languages.FORMAL))
    assert {"basic", "cpp", "cobol", "fortran", "java", "pascal", "math", "digits"} <= formal
    assert len(reg.all()) == len(set(reg.all()))


def test_T_P008_1_romanian_and_romanian_moldavia():
    """T-P008.1: `Romanian` si `RomanianMoldavia`, acelasi model, cu dictionar."""
    reg = LanguageRegistry(available=["ron", "eng"])
    assert reg.is_builtin("ron") and reg.is_builtin("ron-MD")
    assert languages.get("ron-MD").models == ("ron",)
    assert reg.is_model_available("ron-MD") and reg.has_dictionary("ron-MD")
    assert reg.display_name("ron-MD") == "language.ron-MD"  # cheie de traducere


def test_T_P006_1_dictionary_flag():
    """T-P006.1 / P-112: fiecare limba isi declara dictionarul."""
    reg = LanguageRegistry()
    assert reg.has_dictionary("ron") and reg.has_dictionary("deu")
    assert not reg.has_dictionary("digits") and not reg.has_dictionary("cpp")
    assert not reg.has_dictionary("necunoscuta")


def test_T_P110_1_minimum_languages_are_declared():
    """T-P110.1: romana (ambele variante), engleza, franceza, germana,
    italiana, spaniola, maghiara si cifrele."""
    reg = LanguageRegistry()
    assert all(reg.is_builtin(c) for c in languages.MINIMUM)


def test_model_availability_follows_installed_models():
    reg = LanguageRegistry(available=["ron", "eng", "osd"])
    assert reg.is_model_available("ron") and reg.is_model_available("digits")
    assert not reg.is_model_available("deu")
    assert "ron-MD" in reg.available() and "deu" not in reg.available()


def test_tesseract_spec_maps_codes_and_alphabets():
    assert tesseract_spec(["ron-MD", "eng"]) == (("ron", "eng"), None)
    models, alphabet = tesseract_spec(["digits"])
    assert models == ("eng",) and alphabet is not None and "7" in alphabet and "a" not in alphabet
    assert tesseract_spec(["ron", "digits"]) == (("ron", "eng"), None)  # fara alfabet


def test_T_P004_1_recent_languages(ctx):
    """T-P004.1: limbile folosite trec in fata listei recente, fara dubluri,
    cel mult RECENT_MAX."""
    reg = LanguageRegistry(settings=ctx.settings)
    assert reg.recent() == []
    reg.remember(["ron", "eng"])
    reg.remember(["deu", "ron"])
    assert reg.recent() == ["deu", "ron", "eng"]
    reg.remember([f"x{i}" for i in range(10)])
    assert len(reg.recent()) == languages.RECENT_MAX
    ctx.settings.set("lang.recent", [])
    with pytest.raises(ValueError):
        ctx.settings.set("lang.recent", ["ron", "ron"])


class ConfidenceEngine:
    """Motor fals: `deu` e mereu cel mai sigur."""

    def recognize_area(self, page, area, settings, cancel=None):
        from app.core.model import BlockData, LineData, WordData

        conf = 95.0 if settings.languages == ("deu",) else 70.0
        w = WordData(None, "wort", conf, bbox=Rect(0, 0, 10, 10))
        b = BlockData(None, lines=[LineData(None, words=[w], bbox=w.bbox)], bbox=w.bbox)
        return RecognitionResult(page.page_number, blocks=[b], avg_confidence=conf)


def test_autodetect_uses_only_languages_with_a_dictionary():
    """SPEC_05 `autodetect`: numai limbile cu dictionar; fara motor, prima."""
    page = PageData(1, 1, Path("x.png"), Path("x.png"), 100, 100, 300, 300, ColorMode.GRAY)
    page.areas.append(AreaData(1, AreaType.TEXT, [], 0, bbox=Rect(0, 0, 100, 100)))
    reg = LanguageRegistry()
    settings = OcrSettings(languages=("digits", "ron", "deu"))
    assert reg.autodetect(page, settings=settings) == ("ron",)
    assert reg.autodetect(page, ConfidenceEngine(), settings) == ("deu",)
    assert reg.autodetect(page, settings=OcrSettings(languages=())) == ()


# =============================================================================
# Tesseract real
# =============================================================================

FONTS = ["/System/Library/Fonts/Supplemental/Times New Roman.ttf", "C:/Windows/Fonts/times.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]
FONT = next((f for f in FONTS if Path(f).is_file()), None)

needs_ocr = pytest.mark.skipif(
    (find_tesseract() is None or FONT is None) and os.environ.get("DOCULENS_REQUIRE_OCR") != "1",
    reason="Tesseract sau fontul lipsesc")


def text_page(path: Path, text: str) -> PageData:
    img = Image.new("L", (1600, 300), 255)
    ImageDraw.Draw(img).text((60, 100), text, fill=0, font=ImageFont.truetype(FONT, 56))
    img.save(path, dpi=(300, 300))
    return PageData(1, 1, path, path, 1600, 300, 300, 300, ColorMode.GRAY)


@needs_ocr
def test_T_P105_1_digits_language_reads_only_digits(tmp_path):
    """T-P105.1: limba formala „cifre” nu produce litere."""
    from app.core.ocr.engine import TesseractEngine

    page = text_page(tmp_path / "n.png", "Total 12.450,00 / 37%")
    result = TesseractEngine().recognize_page(page, OcrSettings(languages=("digits",)))
    text = " ".join(w.text for b in result.blocks for ln in b.lines for w in ln.words)
    assert "12.450,00" in text and not any(ch.isalpha() for ch in text), text


@needs_ocr
def test_T_P008_2_romanian_moldavia_keeps_diacritics(tmp_path):
    """T-P008.2: `RomanianMoldavia` recunoaste cu modelul romanesc."""
    from app.core.ocr.engine import TesseractEngine

    page = text_page(tmp_path / "m.png", "Chișinău, strada Ștefan cel Mare")
    result = TesseractEngine().recognize_page(page, OcrSettings(languages=("ron-MD",)))
    text = " ".join(w.text for b in result.blocks for ln in b.lines for w in ln.words)
    assert "Chișinău" in text and "Ștefan" in text, text
    assert all(w.language_code == "ron-MD" for b in result.blocks for ln in b.lines
               for w in ln.words)
