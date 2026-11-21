"""Faza 4b, pasul 4b.2: dictionarele utilizatorului (P-040..P-045,
J-080..J-085)."""

from __future__ import annotations

import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.model import AutoProcessMode, BlockData, LineData, Rect, WordData
from app.core.ocr.dictionary import WARNING_SHARED_UNAVAILABLE, DictionaryService
from app.core.ocr.engine import RecognitionResult
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def dic(ctx):
    return DictionaryService(ctx.app_db)


def test_T_P041_1_add_duplicate_and_spaces(dic):
    """T-P041.1: adaugare; duplicatul da avertisment (False); spatiile nu."""
    assert dic.add("Făgăraș", "ron") is True
    assert dic.contains("Făgăraș", "ron") and not dic.contains("Făgăraș", "eng")
    assert dic.add("Făgăraș", "ron") is False
    for bad in ("doua cuvinte", "", "   "):
        with pytest.raises(ValueError):
            dic.add(bad, "ron")


def test_T_P042_1_remove(dic):
    dic.add("POCU", "ron")
    dic.remove("POCU", "ron")
    assert not dic.contains("POCU", "ron")


def test_suggestions_from_the_user_dictionary(dic):
    for w in ("Făgăraș", "Brașov", "Sibiu"):
        dic.add(w, "ron")
    assert dic.suggest("Fagaras", "ron")[0] == "Făgăraș"


def test_T_P043_1_import_text_files_and_encodings(dic, tmp_path):
    """T-P043.1 / P-023: `.txt` in UTF-8, UTF-16 si Windows-1252; `.dic` cu
    numarul de cuvinte pe prima linie si marcaje dupa `/`."""
    (tmp_path / "u8.txt").write_text("Ștefan\nBrașov\n\nȘtefan\n", encoding="utf-8")
    assert dic.import_words(tmp_path / "u8.txt", "ron") == 2
    (tmp_path / "u16.txt").write_text("Țară\n", encoding="utf-16")
    assert dic.import_words(tmp_path / "u16.txt", "ron") == 1
    (tmp_path / "w.txt").write_bytes("café\nnaïve\n".encode("cp1252"))
    assert dic.import_words(tmp_path / "w.txt", "fra") == 2
    assert dic.contains("café", "fra") and dic.contains("naïve", "fra")
    (tmp_path / "h.dic").write_text("3\nlucru/S\nlucrare/AB\ndoua cuvinte\n", encoding="utf-8")
    assert dic.import_words(tmp_path / "h.dic", "ron") == 2
    assert dic.contains("lucrare", "ron")
    (tmp_path / "p.pmd").write_text("Craiova\n", encoding="utf-8")
    assert dic.import_words(tmp_path / "p.pmd", "ron") == 1


def test_T_P044_1_binary_and_unknown_files_are_refused(dic, tmp_path):
    """T-P044.1: un dictionar binar (vechile versiuni) sau alt tip de fisier
    se refuza cu ValueError (SPEC_05)."""
    (tmp_path / "vechi.pmd").write_bytes(b"ABBYY\x00\x01\x02binar")
    with pytest.raises(ValueError, match="text"):
        dic.import_words(tmp_path / "vechi.pmd", "ron")
    (tmp_path / "x.doc").write_text("cuvant", encoding="utf-8")
    with pytest.raises(ValueError):
        dic.import_words(tmp_path / "x.doc", "ron")


def test_export_words(dic, tmp_path):
    for w in ("b", "a"):
        dic.add(w, "ron")
    assert dic.export_words(tmp_path / "out.txt", "ron") == 2
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "a\nb\n"


# =============================================================================
# P-045, J-080..J-085: folderul partajat
# =============================================================================


def test_T_P045_1_shared_folder_between_two_users(tmp_path):
    """T-P045.1 / J-084, J-085: doi utilizatori, acelasi folder. Cel care
    editeaza tine dictionarul; celalalt il foloseste, dar nu il modifica;
    cuvintele noi se vad dupa repornire."""
    shared = tmp_path / "retea"
    shared.mkdir()
    a = AppContext.start(AppPaths.portable(tmp_path / "a"))
    b = AppContext.start(AppPaths.portable(tmp_path / "b"))
    try:
        for c in (a, b):
            c.settings.set("areas.user_dictionaries_folder", str(shared))
        da, db = DictionaryService(a.app_db, a.settings), DictionaryService(b.app_db, b.settings)
        assert da.shared_folder == shared and not da.warnings
        da.add("Răcădău", "ron")
        assert (shared / "ron.txt").read_text(encoding="utf-8") == "Răcădău\n"
        assert db.is_locked_by_other("ron")
        with pytest.raises(PermissionError):
            db.add("Bartolomeu", "ron")
        assert not db.contains("Răcădău", "ron")  # J-085: abia dupa repornire
        da.end_edit()
        restarted = DictionaryService(b.app_db, b.settings)
        assert restarted.contains("Răcădău", "ron")
        assert restarted.add("Bartolomeu", "ron") is True
        restarted.close()
    finally:
        a.close()
        b.close()


def test_T_P045_2_unreachable_shared_folder_falls_back(ctx, tmp_path):
    """T-P045.2: folder inaccesibil → dictionarul local si un avertisment."""
    ctx.settings.set("areas.user_dictionaries_folder", str(tmp_path / "nu-exista"))
    dic = DictionaryService(ctx.app_db, ctx.settings)
    assert dic.shared_folder is None and dic.warnings == [WARNING_SHARED_UNAVAILABLE]
    assert dic.add("Local", "ron") and dic.contains("Local", "ron")


# =============================================================================
# Recunoasterea: cuvintele din dictionar nu sunt nesigure
# =============================================================================


class UncertainEngine:
    """Motor fals: doua cuvinte nesigure, unul din dictionarul utilizatorului."""

    name = "fals"

    def recognize_page(self, page, settings, cancel=None):
        words = [WordData(None, w, 40.0, bbox=Rect(10, 10, 50, 20), is_uncertain=True,
                          language_code="ron") for w in ("Răcădău,", "Xqzt")]
        block = BlockData(None, lines=[LineData(None, words=words, bbox=Rect(10, 10, 100, 20))],
                          bbox=Rect(10, 10, 100, 20))
        area_id = page.areas[0].id if page.areas else None
        return RecognitionResult(page.page_number, blocks=[block], uncertain_count=2,
                                 area_blocks={area_id: [block]})

    def recognize_area(self, page, area, settings, cancel=None):
        return RecognitionResult(page.page_number, area_blocks={area.id: []})


def test_T_P006_3_user_dictionary_words_are_not_uncertain(ctx, tmp_path):
    ctx.settings.set("lang.mode", "manual")
    ctx.settings.set("lang.manual", ["ron"])
    DictionaryService(ctx.app_db).add("Răcădău", "ron")
    image = tmp_path / "p.png"
    Image.new("L", (800, 400), 255).save(image, dpi=(300, 300))
    project = OcrProject.create(context=ctx)
    try:
        project.add_images([image], auto_process=AutoProcessMode.NONE)
        RecognitionService(project, engine=UncertainEngine()).recognize_pages()
        words = list(project.page(1).iter_words())
        assert [(w.text, w.is_uncertain) for w in words] == [("Răcădău,", False),
                                                            ("Xqzt", True)]
        assert project.page(1).uncertain_count == 1
    finally:
        project.close()
