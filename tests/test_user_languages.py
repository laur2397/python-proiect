"""Faza 4b, pasul 4b.1: expresiile regulate (Z-020..Z-030), limbile proprii
(P-020..P-026, P-030) si grupurile de limbi (P-027..P-029)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.errors import BuiltinNotEditableError
from app.core.model import (
    AutoProcessMode,
    BlockData,
    ColorMode,
    LineData,
    PageData,
    Rect,
    WordData,
)
from app.core.ocr.engine import _check_expression, find_tesseract
from app.core.ocr.languages import GROUP_PREFIX, LanguageRegistry, tesseract_spec
from app.core.ocr.regex import compile_expression, matches
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.core.settings import OcrSettings

# =============================================================================
# Z-020..Z-030: dialectul expresiilor
# =============================================================================


@pytest.mark.parametrize("expression, word, expected", [
    ("a.c", "abc", True),                      # Z-020
    ("[abc]+", "cab", True),                   # Z-021
    ("[abc]+", "cad", False),
    ("[^0-9]+", "abc", True),                  # Z-022
    ("[^0-9]+", "ab1", False),
    ("da|nu", "nu", True),                     # Z-023
    ("ab*c", "ac", True),                      # Z-024
    ("ab+c", "ac", False),                     # Z-025
    ("ab+c", "abbc", True),
    (r"\d+", "2026", True),                    # Z-026
    (r"\a+", "Ștefan", True),
    (r"\U\L+", "Brașov", True),
    (r"\U\L+", "brașov", False),
    ("[A-Z][a-z]+", "Ion", True),              # Z-027, latine
    ("[А-Я][а-я]+", "Москва", True),           # Z-027, chirilice
    ("[а-я]+", "МОСКВА", False),
    (r"\d+\.\d+", "3.14", True),               # Z-029, evadarea
    (r"\d+\.\d+", "3x14", False),
    (r"\a+\@\a+\.\a+", "ion@firma.ro", True),  # Z-030, e-mail
    (r"\d\d\.\d\d\.\d\d\d\d", "21.11.2026", True),  # Z-030, data
])
def test_T_Z020_Z030_dialect(expression, word, expected):
    assert matches(expression, word) is expected


@pytest.mark.parametrize("expression, reason", [
    ("ion@firma", "rezervat"),       # Z-028
    ("[abc", "fara"),
    ("abc]", "fara"),
    ("*a", "nu repeta"),
    ("[z-a]", "inversat"),
    ("a\\", "sfarsitul"),
    ("", "goala"),
])
def test_T_Z028_Z030_invalid_expressions_are_refused(expression, reason):
    with pytest.raises(ValueError, match=reason):
        compile_expression(expression)


# =============================================================================
# P-020..P-026: limbile proprii
# =============================================================================


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def reg(ctx):
    return LanguageRegistry(available=["ron", "eng"], con=ctx.app_db)


def test_T_P020_1_new_language_based_on_an_existing_one(reg):
    """T-P020.1 / P-021, P-022: nume, limba sursa, alfabet, dictionar."""
    code = reg.create_user_language("Coduri CAEN", "ron", alphabet="0123456789",
                                    dictionary_mode="none")
    assert code in reg.all() and code in reg.user_languages()
    assert reg.display_name(code) == "Coduri CAEN" and not reg.is_builtin(code)
    lang = reg.get(code)
    assert lang.models == ("ron",) and lang.alphabet == "0123456789" and lang.is_user
    assert not reg.has_dictionary(code) and reg.is_model_available(code)
    assert tesseract_spec([code], reg) == (("ron",), "0123456789")
    with pytest.raises(ValueError, match="exista deja"):
        reg.create_user_language("Coduri CAEN", "eng")
    with pytest.raises(ValueError):
        reg.create_user_language("Alta", "nu-exista")
    with pytest.raises(ValueError):
        reg.create_user_language("Alta", "ron", dictionary_mode="ghicit")


def test_T_P025_1_regex_dictionary_must_compile(reg):
    """T-P025.1: o expresie invalida se refuza cu mesajul erorii."""
    with pytest.raises(ValueError, match="rezervat"):
        reg.create_user_language("E-mail", "eng", dictionary_mode="regex",
                                 dictionary_regex="ion@firma")
    with pytest.raises(ValueError):
        reg.create_user_language("Data", "eng", dictionary_mode="regex")
    code = reg.create_user_language("Data", "eng", dictionary_mode="regex",
                                    dictionary_regex=r"\d\d\.\d\d\.\d\d\d\d")
    assert reg.get(code).dictionary_regex == r"\d\d\.\d\d\.\d\d\d\d"


def test_T_P026_1_advanced_properties(reg):
    """T-P026.1: proprietatile din `Advanced...`, inclusiv caracterele interzise."""
    code = reg.create_user_language("Fara cifre", "ron", forbidden_chars="|")
    reg.set_advanced(code, chars_ignored="-", allow_roman_numerals=False,
                     chars_forbidden="|0123456789")
    lang = reg.get(code)
    assert lang.advanced["chars_ignored"] == "-"
    assert lang.advanced["allow_roman_numerals"] == 0
    assert lang.forbidden == "|0123456789"
    with pytest.raises(ValueError):
        reg.set_advanced(code, culoare="rosu")


def test_T_P006_2_builtin_languages_are_not_deleted(reg):
    with pytest.raises(BuiltinNotEditableError):
        reg.delete_user_language("ron")
    code = reg.create_user_language("Temporara", "eng")
    reg.delete_user_language(code)
    assert code not in reg.all()
    with pytest.raises(ValueError):
        reg.delete_user_language(code)


def test_regex_dictionary_marks_non_matching_words_uncertain(reg):
    """P-022, Z-030: cu dictionar de tip expresie, cuvintele care nu se
    potrivesc devin nesigure; cele care se potrivesc raman cum erau."""
    code = reg.create_user_language("Date", "eng", dictionary_mode="regex",
                                    dictionary_regex=r"\d\d\.\d\d\.\d\d\d\d")
    words = [WordData(None, "21.11.2026", 95.0, bbox=Rect(0, 0, 1, 1)),
             WordData(None, "21.1l.2026", 95.0, bbox=Rect(0, 0, 1, 1))]
    blocks = [BlockData(None, lines=[LineData(None, words=words)])]
    _check_expression(blocks, [reg.get(code)])
    assert [w.is_uncertain for w in words] == [False, True]


# =============================================================================
# P-027..P-029: grupurile
# =============================================================================


def test_T_P027_1_language_group(reg):
    """T-P027.1 / P-028, P-029: minimum doua limbi; grupul e o singura limba."""
    with pytest.raises(ValueError, match="doua"):
        reg.create_group("Singur", ["ron"])
    code = reg.create_group("Romana si engleza", ["ron", "eng", "ron"], forbidden_chars="~")
    assert code == GROUP_PREFIX + "Romana si engleza" and code in reg.all()
    assert reg.group_members("Romana si engleza") == ["eng", "ron"]
    group = reg.get(code)
    assert set(group.models) == {"ron", "eng"} and group.forbidden == "~"
    assert reg.display_name(code) == "Romana si engleza"
    with pytest.raises(ValueError, match="exista deja"):
        reg.create_group("Romana si engleza", ["ron", "deu"])


# =============================================================================
# P-030: limbile proprii merg cu proiectul
# =============================================================================


def test_T_P030_1_user_languages_travel_with_the_project(tmp_path):
    """T-P030.1: proiectul salvat pe un calculator se deschide pe altul (alt
    profil, alta app.db) si isi aduce limba proprie."""
    first = AppContext.start(AppPaths.portable(tmp_path / "pc1"))
    try:
        code = LanguageRegistry(con=first.app_db).create_user_language(
            "Coduri", "ron", alphabet="0123456789")
        project = OcrProject.create(context=first)
        image = tmp_path / "p.png"
        Image.new("L", (400, 300), 255).save(image, dpi=(300, 300))
        project.add_images([image], auto_process=AutoProcessMode.NONE)
        project.settings().set("lang.mode", "manual")
        project.settings().set("lang.manual", [code])
        project.save(tmp_path / "dosar")
        project.close()
    finally:
        first.close()
    assert (tmp_path / "dosar" / "languages.json").is_file()
    second = AppContext.start(AppPaths.portable(tmp_path / "pc2"))
    try:
        assert code not in LanguageRegistry(con=second.app_db).all()
        OcrProject.open(tmp_path / "dosar", context=second).close()
        reg = LanguageRegistry(con=second.app_db)
        assert code in reg.all() and reg.get(code).alphabet == "0123456789"
    finally:
        second.close()


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


@needs_ocr
def test_T_P021_1_user_alphabet_limits_the_engine(ctx, tmp_path):
    """T-P021.1: o limba proprie cu alfabetul A-F si cifre citeste un cod hex
    fara alte litere."""
    from app.core.ocr.engine import TesseractEngine

    reg = LanguageRegistry(con=ctx.app_db)
    code = reg.create_user_language("Hex", "eng", alphabet="0123456789ABCDEF")
    img = Image.new("L", (1400, 300), 255)
    ImageDraw.Draw(img).text((60, 100), "3FA9 0B7C", fill=0,
                             font=ImageFont.truetype(FONT, 64))
    img.save(tmp_path / "h.png", dpi=(300, 300))
    page = PageData(1, 1, tmp_path / "h.png", tmp_path / "h.png", 1400, 300, 300, 300,
                    ColorMode.GRAY)
    engine = TesseractEngine(registry=reg.snapshot())
    result = engine.recognize_page(page, OcrSettings(languages=(code,)))
    text = " ".join(w.text for b in result.blocks for ln in b.lines for w in ln.words)
    assert set(text.replace(" ", "")) <= set("0123456789ABCDEF") and "3FA9" in text, text
