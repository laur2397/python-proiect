"""Faza 4b, pasul 4b.3: sabloanele de caractere (P-050..P-066)."""

from __future__ import annotations

import io
import json
import zipfile

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.core.context import AppContext
from app.core.errors import PatternLimitError, ProjectVersionError
from app.core.model import AutoProcessMode, BlockData, LineData, Rect, WordData
from app.core.ocr.engine import RecognitionResult
from app.core.ocr.languages import LanguageRegistry
from app.core.ocr.patterns import PatternMatcher, PatternStore
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def store(ctx):
    return PatternStore(ctx.app_db)


def glyph_png(size=40, kind="sun") -> bytes:
    """Un simbol care nu e litera: un cerc cu cruce (sau un triunghi)."""
    img = Image.new("L", (size + 10, size + 10), 255)
    d = ImageDraw.Draw(img)
    if kind == "sun":
        d.ellipse([5, 5, 5 + size, 5 + size], outline=0, width=max(2, size // 10))
        d.line([(5 + size // 2, 5), (5 + size // 2, 5 + size)], fill=0, width=max(2, size // 10))
    else:
        d.polygon([(5, 5 + size), (5 + size // 2, 5), (5 + size, 5 + size)], fill=0)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


# =============================================================================
# P-053, P-054, P-059, P-061, P-063: seturile
# =============================================================================


def test_T_P061_1_one_active_set(store):
    """T-P061.1: un singur sablon activ; cel activ nu se sterge."""
    store.create_set("Simboluri")
    store.create_set("Decorativ", "ron")
    assert store.sets() == ["Decorativ", "Simboluri"] and store.active_set() is None
    store.set_active("Simboluri")
    store.set_active("Decorativ")
    assert store.active_set() == "Decorativ"
    with pytest.raises(ValueError, match="activ"):
        store.delete_set("Decorativ")
    store.delete_set("Simboluri")
    assert store.sets() == ["Decorativ"]
    with pytest.raises(ValueError, match="exista deja"):
        store.create_set("Decorativ")


def test_T_P059_1_no_training_for_asian_languages(store):
    for code in ("jpn", "chi_sim", "kor", "tha"):
        with pytest.raises(ValueError, match="asiatice"):
            store.create_set(f"s-{code}", code)


# =============================================================================
# P-055..P-058, P-060, P-062, P-063: caracterele
# =============================================================================


def test_T_P056_1_effects_are_kept_and_edited(store):
    """T-P056.1 / P-062: efectele (bold, italic, exponent, indice) se pastreaza
    si se schimba din `Properties...`."""
    store.create_set("S")
    cid = store.add_pattern("S", glyph_png(), "☼", effects=["italic", "bold"], dpi=300)
    (char,) = store.characters("S")
    assert (char.id, char.character, char.effects, char.dpi) == (cid, "☼", ("bold", "italic"),
                                                                  300)
    store.edit(cid, character="Ⓞ", effects=["superscript"])
    (char,) = store.characters("S")
    assert char.character == "Ⓞ" and char.effects == ("superscript",)
    with pytest.raises(ValueError):
        store.edit(cid, effects=["superscript", "subscript"])
    with pytest.raises(ValueError):
        store.add_pattern("S", glyph_png(), "x", effects=["subliniat"])
    store.delete_pattern(cid)  # P-063
    assert store.characters("S") == []


def test_T_P060_1_one_or_two_characters(store):
    store.create_set("S")
    store.add_pattern("S", glyph_png(), "fi")  # ligatura: doua caractere
    for bad in ("", "abc", "a b", " "):
        with pytest.raises(ValueError, match="P-060"):
            store.add_pattern("S", glyph_png(), bad)


def test_T_P058_1_limit_of_1000_characters(store):
    """T-P058.1: al 1001-lea caracter ridica PatternLimitError."""
    store.create_set("Mare")
    png = glyph_png(8)
    for i in range(PatternStore.MAX_CHARS_PER_SET):
        store.add_pattern("Mare", png, chr(0x4E00 + i))
    with pytest.raises(PatternLimitError):
        store.add_pattern("Mare", png, "x")


def test_T_P055_1_train_from_the_page_image(store, tmp_path):
    page = Image.new("L", (300, 200), 255)
    page.paste(Image.open(io.BytesIO(glyph_png())), (100, 50))
    page.save(tmp_path / "p.png")
    store.create_set("S")
    store.train("S", tmp_path / "p.png", Rect(100, 50, 50, 50), "☼", dpi=300)
    (char,) = store.characters("S")
    assert char.image.size == (50, 50) and char.character == "☼"


# =============================================================================
# P-065, P-066: fisierul de sabloane si limbi
# =============================================================================


def test_T_P065_1_bundle_round_trip(ctx, store, tmp_path):
    """T-P065.1 / P-066: sabloanele si limbile proprii trec pe alt calculator."""
    LanguageRegistry(con=ctx.app_db).create_user_language("Coduri", "eng", alphabet="0123456789")
    store.create_set("Simboluri")
    store.add_pattern("Simboluri", glyph_png(), "☼", effects=["bold"])
    store.set_active("Simboluri")
    bundle = tmp_path / "comun.fbtx"
    store.save_bundle(bundle)
    with pytest.raises(ValueError):
        store.save_bundle(tmp_path / "x.zip")
    other = AppContext.start(AppPaths.portable(tmp_path / "pc2"))
    try:
        second = PatternStore(other.app_db)
        second.load_bundle(bundle, patterns=False)  # numai limbile
        assert second.sets() == [] and "user:coduri" in LanguageRegistry(
            con=other.app_db).all()
        second.load_bundle(bundle)
        assert second.sets() == ["Simboluri"] and second.active_set() == "Simboluri"
        (char,) = second.characters("Simboluri")
        assert char.character == "☼" and char.effects == ("bold",)
        second.load_bundle(bundle)  # acelasi nume: se inlocuieste, nu se dubleaza
        assert len(second.characters("Simboluri")) == 1
    finally:
        other.close()


def test_T_P066_1_foreign_and_newer_files_are_refused(store, tmp_path):
    (tmp_path / "abbyy.fbt").write_bytes(b"\x00binar")
    with pytest.raises(ValueError, match="fbt"):
        store.load_bundle(tmp_path / "abbyy.fbt")
    (tmp_path / "rau.fbtx").write_bytes(b"nu e zip")
    with pytest.raises(ValueError):
        store.load_bundle(tmp_path / "rau.fbtx")
    with zipfile.ZipFile(tmp_path / "nou.fbtx", "w") as z:
        z.writestr("manifest.json", json.dumps({"format": "doculens-patterns", "version": 99,
                                                "languages": [], "sets": []}))
    with pytest.raises(ProjectVersionError):
        store.load_bundle(tmp_path / "nou.fbtx")


# =============================================================================
# P-050..P-052, P-064: aplicarea
# =============================================================================


def page_with_symbols(size=40) -> np.ndarray:
    """Doua simboluri unul langa altul: soare, triunghi."""
    img = Image.new("L", (400, 120), 255)
    img.paste(Image.open(io.BytesIO(glyph_png(size, "sun"))), (50, 30))
    img.paste(Image.open(io.BytesIO(glyph_png(size, "tri"))), (120, 30))
    return np.asarray(img)


def trained(store):
    store.create_set("Simboluri")
    store.add_pattern("Simboluri", glyph_png(40, "sun"), "☼", dpi=300)
    store.add_pattern("Simboluri", glyph_png(40, "tri"), "▲", dpi=300)
    store.set_active("Simboluri")
    return PatternMatcher.from_store(store)


def word(text, uncertain=True):
    return WordData(None, text, 30.0, bbox=Rect(40, 20, 150, 70), is_uncertain=uncertain)


def test_T_P051_1_user_patterns_read_trained_symbols(store):
    """T-P051.1: un cuvant nesigur format din simboluri antrenate se reciteste."""
    matcher = trained(store)
    w = word("O^")
    assert matcher.apply(page_with_symbols(), [w], dpi=300) == 1
    assert w.text == "☼▲" and not w.is_uncertain and w.confidence >= 85


def test_T_P064_1_same_size_and_resolution_only(store):
    """T-P064.1: alta rezolutie sau alta dimensiune: sablonul nu se aplica."""
    matcher = trained(store)
    w = word("O^")
    assert matcher.apply(page_with_symbols(), [w], dpi=150) == 0 and w.text == "O^"
    big = WordData(None, "O^", 30.0, bbox=Rect(40, 20, 300, 100), is_uncertain=True)
    assert matcher.apply(page_with_symbols(80), [big], dpi=300) == 0 and big.text == "O^"


def test_T_P052_1_certain_words_untouched_unless_user_patterns_only(store):
    matcher = trained(store)
    sure = word("O^", uncertain=False)
    assert matcher.apply(page_with_symbols(), [sure], dpi=300) == 0 and sure.text == "O^"
    assert matcher.apply(page_with_symbols(), [sure], dpi=300, all_words=True) == 1
    assert sure.text == "☼▲"


class SymbolEngine:
    """Motor fals: citeste simbolurile ca „O^”, nesigur."""

    name = "fals"

    def recognize_page(self, page, settings, cancel=None):
        w = WordData(None, "O^", 30.0, bbox=Rect(40, 20, 150, 70), is_uncertain=True,
                     language_code="ron")
        block = BlockData(None, lines=[LineData(None, words=[w], bbox=w.bbox)], bbox=w.bbox)
        area_id = page.areas[0].id if page.areas else None
        return RecognitionResult(page.page_number, blocks=[block], uncertain_count=1,
                                 area_blocks={area_id: [block]})

    def recognize_area(self, page, area, settings, cancel=None):
        return RecognitionResult(page.page_number, area_blocks={area.id: []})


def test_T_P050_1_service_uses_patterns_only_when_chosen(ctx, store, tmp_path):
    """T-P050.1: implicit (`Use built-in patterns`) sablonul nu se foloseste;
    cu `Use user patterns`, da."""
    trained(store)
    Image.fromarray(page_with_symbols()).save(tmp_path / "s.png", dpi=(300, 300))
    ctx.settings.set("lang.mode", "manual")
    ctx.settings.set("lang.manual", ["ron"])
    project = OcrProject.create(context=ctx)
    try:
        project.add_images([tmp_path / "s.png"], auto_process=AutoProcessMode.NONE)
        service = RecognitionService(project, engine=SymbolEngine())
        service.recognize_pages()
        assert project.page(1).text.strip() == "O^"
        ctx.settings.set("ocr.patterns", "user")
        service.recognize_pages(skip_recognized=False)
        assert project.page(1).text.strip() == "☼▲" and project.page(1).uncertain_count == 0
    finally:
        project.close()
