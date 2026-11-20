"""Teste cu Tesseract (faza 4, pasul 4.1): recunoasterea, acuratetea, salvarea.

Se sar daca Tesseract nu e instalat, in afara de CI, unde
DOCULENS_REQUIRE_OCR=1 face ca lipsa lui sa fie o eroare.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.errors import LanguageModelMissingError, NoLanguageSelectedError
from app.core.layout.areas import AreaEditor
from app.core.model import (
    AreaType,
    AutoProcessMode,
    ColorMode,
    PageData,
    PageStatus,
    Rect,
)
from app.core.ocr.engine import OcrEngine, TesseractEngine, find_tesseract
from app.core.ocr.store import save_result
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.core.settings import OcrSettings

if find_tesseract() is None:
    if os.environ.get("DOCULENS_REQUIRE_OCR") == "1":
        raise RuntimeError("CI cere Tesseract, dar nu e instalat")
    pytest.skip("Tesseract nu e instalat", allow_module_level=True)

FONTS = [
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "C:/Windows/Fonts/times.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]
FONT_PATH = next((f for f in FONTS if Path(f).is_file()), None)
if FONT_PATH is None:
    pytest.skip("niciun font cu diacritice romanesti", allow_module_level=True)

RON = OcrSettings(languages=("ron",))
TEXT = ("Subsemnatul Popescu Ștefan, domiciliat în municipiul Brașov, strada Ștefan cel Mare "
        "nr. 14, județul Brașov, declar pe propria răspundere că toate informațiile din această "
        "cerere de finanțare sunt corecte și complete. Înțeleg că orice declarație falsă atrage "
        "răspunderea penală prevăzută de lege. Societatea își desfășoară activitatea în domeniul "
        "construcțiilor și al întreținerii clădirilor, având un număr mediu de paisprezece "
        "salariați în ultimii trei ani fiscali.")


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def render(path: Path, text: str = TEXT, dpi: int = 300, size_pt: float = 11.0) -> Path:
    """Pagina A4 latime, text pe randuri, la rezolutia data."""
    font = ImageFont.truetype(FONT_PATH, round(size_pt * dpi / 72))
    width = round(8.27 * dpi)
    img = Image.new("L", (width, round(4 * dpi)), 255)
    draw = ImageDraw.Draw(img)
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font) > width - dpi:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    for i, ln in enumerate(lines):
        draw.text((dpi // 2, dpi // 3 + i * font.size * 1.5), ln, fill=0, font=font)
    img.save(path, dpi=(dpi, dpi))
    return path


def page_of(path: Path, dpi: int = 300) -> PageData:
    with Image.open(path) as im:
        w, h = im.size
    return PageData(None, 1, path, path, w, h, dpi, dpi, ColorMode.GRAY)


def words_of(result):
    return [w for b in result.blocks for line in b.lines for w in line.words]


@pytest.fixture(scope="module")
def engine():
    return TesseractEngine()


# =============================================================================
# Pragurile de calitate (SPEC_06 cap. 3) pe text generat
# =============================================================================


@pytest.fixture(scope="module")
def page300(tmp_path_factory):
    return page_of(render(tmp_path_factory.mktemp("ocr") / "p300.png"))


def test_engine_satisfies_contract(engine):
    assert isinstance(engine, OcrEngine) and engine.name == "tesseract"
    assert {"ron", "eng"} <= set(engine.available_languages())


def test_quality_300_dpi_character_and_word(engine, page300):
    """SPEC_06: >= 98% pe caracter la 300 dpi; >= 96% pe cuvant, cu diacritice.
    INCOMPLET, marcat: masurat pe text generat; corpusul real lipseste."""
    result = engine.recognize_page(page300, RON)
    ocr = " ".join(w.text for w in words_of(result))
    ref = " ".join(TEXT.split())
    assert 1 - levenshtein(ocr, ref) / len(ref) >= 0.98
    ref_words, ocr_words = ref.split(), ocr.split()
    same = sum(a == b for a, b in zip(ref_words, ocr_words, strict=False))
    assert same / len(ref_words) >= 0.96, [
        (a, b) for a, b in zip(ref_words, ocr_words, strict=False) if a != b]


def test_quality_no_cedilla_confusion(engine, page300):
    """SPEC_06: cel mult 2 confuzii ș/ş, ț/ţ la 1.000 de caractere (aici: zero)."""
    text = " ".join(w.text for w in words_of(engine.recognize_page(page300, RON)))
    assert not any(c in text for c in "şţŞŢ")


def test_quality_200_dpi(engine, tmp_path):
    """SPEC_06: >= 94% pe caracter la 200 dpi."""
    result = engine.recognize_page(page_of(render(tmp_path / "p.png", dpi=200), 200), RON)
    ocr = " ".join(w.text for w in words_of(result))
    ref = " ".join(TEXT.split())
    assert 1 - levenshtein(ocr, ref) / len(ref) >= 0.94


# =============================================================================
# N-005, N-024: zone, pozitii, incredere
# =============================================================================


def test_T_N005_1_area_words_are_in_page_coordinates(engine, tmp_path):
    """T-N005.1: doar zona se recunoaste; pozitiile sunt in pixelii paginii."""
    path = render(tmp_path / "p.png", "Cerere de finanțare nr. 4521")
    page = page_of(path)
    from app.core.model import AreaData
    area = AreaData(7, AreaType.TEXT, [], 0, bbox=Rect(100, 50, 2200, 200))
    result = engine.recognize_area(page, area, RON)
    words = words_of(result)
    assert [w.text for w in words][:3] == ["Cerere", "de", "finanțare"]
    assert all(w.bbox.x >= 100 and w.bbox.y >= 50 for w in words)
    assert all(0 <= w.confidence <= 100 and w.language_code == "ron" for w in words)
    assert result.area_blocks.keys() == {7}


def test_T_N024_1_uncertain_words_follow_the_threshold(engine, page300):
    """T-N024.1: cuvintele sub prag se marcheaza nesigure."""
    strict = engine.recognize_page(page300, OcrSettings(languages=("ron",),
                                                         confidence_threshold=100.0))
    assert strict.uncertain_count == len(words_of(strict)) > 0
    lenient = engine.recognize_page(page300, OcrSettings(languages=("ron",),
                                                          confidence_threshold=0.0))
    assert lenient.uncertain_count == 0 and lenient.avg_confidence > 80


def test_Y004_missing_language_model(engine, page300):
    with pytest.raises(LanguageModelMissingError) as info:
        engine.recognize_page(page300, OcrSettings(languages=("xyz",)))
    assert info.value.params["language_code"] == "xyz"
    with pytest.raises(NoLanguageSelectedError):
        engine.recognize_page(page300, OcrSettings(languages=()))


def test_barcodes_come_in_step_4_5(engine, page300):
    with pytest.raises(NotImplementedError):
        engine.read_barcode(page300, None)


# =============================================================================
# Salvarea in proiect
# =============================================================================


@pytest.fixture
def project(tmp_path):
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    p = OcrProject.create(context=ctx)
    yield p
    p.close()
    ctx.close()


def test_recognized_text_is_saved_on_the_page(engine, project, tmp_path):
    project.add_images([render(tmp_path / "p.png", "Județul Brașov, strada Ștefan cel Mare")],
                       auto_process=AutoProcessMode.NONE)
    result = engine.recognize_page(project.page(1), RON)
    save_result(project, 1, result)
    page = project.page(1)
    assert page.status is PageStatus.RECOGNIZED and page.avg_confidence > 50
    assert len(page.areas) == 1  # o zona de text pe toata pagina
    assert "Brașov" in page.text and "Ștefan" in page.text
    assert project.undo_description() == "undo.recognize"


def test_text_goes_into_existing_areas_only(engine, project, tmp_path):
    img = Image.new("L", (2480, 1000), 255)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 46)
    d.text((150, 150), "Text recunoscut", fill=0, font=font)
    d.text((150, 700), "Text ignorat", fill=0, font=font)
    path = tmp_path / "doua.png"
    img.save(path, dpi=(300, 300))
    project.add_images([path], auto_process=AutoProcessMode.NONE)
    AreaEditor(project).create(project.page(1), [(100, 100), (2300, 100), (2300, 300),
                                                 (100, 300)], AreaType.TEXT)
    save_result(project, 1, engine.recognize_page(project.page(1), RON))
    text = project.page(1).text
    assert "recunoscut" in text and "ignorat" not in text


def test_inverted_area_is_read(engine, tmp_path):
    img = Image.new("L", (2480, 300), 0)
    ImageDraw.Draw(img).text((150, 100), "Titlu pe fundal negru", fill=255,
                             font=ImageFont.truetype(FONT_PATH, 46))
    path = tmp_path / "inv.png"
    img.save(path, dpi=(300, 300))
    from app.core.model import AreaData
    area = AreaData(1, AreaType.TEXT, [], 0, bbox=Rect(0, 0, 2480, 300), is_inverted=True)
    words = [w.text for w in words_of(engine.recognize_area(page_of(path), area, RON))]
    assert "Titlu" in words and "negru" in words
