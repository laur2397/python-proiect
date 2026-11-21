"""Faza 5, pasul 5.1: editarea si verificarea textului (O-001..O-012, O-020,
O-108)."""

from __future__ import annotations

import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.layout.areas import AreaEditor
from app.core.model import (
    AreaType,
    AutoProcessMode,
    BlockData,
    LineData,
    PageStatus,
    Rect,
    WordData,
)
from app.core.ocr.dictionary import DictionaryService
from app.core.ocr.engine import RecognitionResult
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.core.text.editor import TextEditor, cjk_variants, fix_punctuation_spaces

# cuvintele fiecarei pagini: (text, nesigur)
PAGES = {
    1: [("Cerere", False), ("finantere", True), ("nr.", False), ("4S21", True)],
    2: [("Brasov", True), ("judet", False), ("ante-proiect", True), ("Sibiu,", True)],
}


class ScriptEngine:
    name = "fals"

    def __init__(self, pages=PAGES):
        self.pages = pages
        self.calls = 0

    def _block(self, n):
        words = [WordData(None, t, 40.0 if u else 95.0, bbox=Rect(10 + 60 * i, 10, 50, 20),
                          is_uncertain=u, language_code="ron")
                 for i, (t, u) in enumerate(self.pages[n])]
        return BlockData(None, lines=[LineData(None, words=words, bbox=Rect(10, 10, 300, 20))],
                         bbox=Rect(10, 10, 300, 20))

    def recognize_page(self, page, settings, cancel=None):
        block = self._block(page.page_number)
        area_id = page.areas[0].id if page.areas else None
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=70.0,
                                 area_blocks={area_id: [block]})

    def recognize_area(self, page, area, settings, cancel=None):
        self.calls += 1
        w = WordData(None, "nou", 99.0, bbox=area.bbox, language_code="ron")
        block = BlockData(None, lines=[LineData(None, words=[w], bbox=area.bbox)],
                          bbox=area.bbox)
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=99.0,
                                 area_blocks={area.id: [block]})


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("lang.mode", "manual")
    c.settings.set("lang.manual", ["ron"])
    yield c
    c.close()


@pytest.fixture
def project(ctx, tmp_path):
    paths = []
    for n in (1, 2):
        Image.new("L", (800, 400), 255).save(tmp_path / f"p{n}.png", dpi=(300, 300))
        paths.append(tmp_path / f"p{n}.png")
    p = OcrProject.create(context=ctx)
    p.add_images(paths, auto_process=AutoProcessMode.NONE)
    ed = AreaEditor(p)
    for n in (1, 2):
        ed.create(p.page(n), [(5, 5), (400, 5), (400, 40), (5, 40)], AreaType.TEXT)
        ed.create(p.page(n), [(5, 100), (400, 100), (400, 200), (5, 200)], AreaType.TEXT)
    RecognitionService(p, engine=ScriptEngine()).recognize_pages()
    yield p
    p.close()


def words(project, n):
    return list(project.page(n).iter_words())


def texts(project, n):
    return [w.text for w in words(project, n)]


# =============================================================================
# O-020: editarea directa
# =============================================================================


def test_T_O020_1_edit_keeps_the_original_and_is_undoable(project):
    """T-O020.1: textul nou se salveaza, originalul ramane, un pas de undo."""
    ed = TextEditor(project)
    target = words(project, 1)[1]
    ed.set_word_text(target, "finantare")
    w = words(project, 1)[1]
    assert (w.text, w.original_text, w.is_edited, w.is_uncertain) == (
        "finantare", "finantere", True, False)
    ed.set_word_text(w, "finanțare")  # a doua editare nu pierde originalul
    assert words(project, 1)[1].original_text == "finantere"
    project.undo()
    project.undo()
    assert words(project, 1)[1].text == "finantere"


def test_T_O012_3_punctuation_spaces():
    assert fix_punctuation_spaces("Brasov , judet ( Romania ) !") == "Brasov, judet (Romania)!"


def test_T_O008_1_insert_symbol(project):
    ed = TextEditor(project)
    ed.insert_symbol(words(project, 1)[0], 6, "§")
    assert texts(project, 1)[0] == "Cerere§"


# =============================================================================
# O-001, O-002, O-012: cuvintele nesigure
# =============================================================================


def test_T_O002_1_next_and_previous_uncertain(project):
    """T-O002.1: pe toate paginile, in ordine; dupa ultimul, None (mesaj).
    O-012: cuvintele cu cifre („4S21”) se ignora implicit."""
    ed = TextEditor(project)
    pages = project.pages
    first = ed.next_uncertain(pages)
    assert first.text == "finantere"
    second = ed.next_uncertain(pages, first)
    assert second.text == "Brasov"
    seq = [first.text, second.text]
    w = second
    while (w := ed.next_uncertain(pages, w)) is not None:
        seq.append(w.text)
    assert seq == ["finantere", "Brasov", "ante-proiect", "Sibiu,"]
    assert ed.previous_uncertain(pages).text == "Sibiu,"
    assert ed.previous_uncertain(pages, second).text == "finantere"
    assert ed.previous_uncertain(pages, first) is None


def test_T_O012_1_verification_options(project, ctx):
    """T-O012.1: cifrele si cuvintele compuse, dupa setari."""
    ed = TextEditor(project)
    ctx.settings.set("areas.ignore_words_with_digits", False)
    ctx.settings.set("areas.check_compound_words", False)
    seq, w = [], None
    while (w := ed.next_uncertain(project.pages, w)) is not None:
        seq.append(w.text)
    assert seq == ["finantere", "4S21", "Brasov", "Sibiu,"]
    ctx.settings.set("areas.check_uncertain", False)
    assert ed.next_uncertain(project.pages) is None


# =============================================================================
# O-003..O-006, O-010, O-011: dialogul de verificare
# =============================================================================


def test_T_O004_1_skip_removes_the_highlight_only(project):
    ed = TextEditor(project)
    w = ed.next_uncertain(project.pages)
    ed.skip(w)
    again = words(project, 1)[1]
    assert again.text == "finantere" and again.is_verified
    assert ed.next_uncertain(project.pages).text == "Brasov"


def test_T_O006_1_add_to_dictionary(project, ctx):
    """T-O006.1: cuvantul intra in dictionar si nu mai e semnalat, pe nicio pagina."""
    ed = TextEditor(project)
    w = next(x for x in words(project, 2) if x.text == "Sibiu,")
    assert ed.add_to_dictionary(w) is True
    assert DictionaryService(ctx.app_db).contains("Sibiu", "ron")
    w = next(x for x in words(project, 2) if x.text == "Sibiu,")
    assert not w.is_uncertain and w.in_dictionary
    assert ed.add_to_dictionary(w) is False  # P-041: duplicat


def test_T_O005_1_suggestions(project, ctx):
    DictionaryService(ctx.app_db).add("Brașov", "ron")
    ed = TextEditor(project)
    w = next(x for x in words(project, 2) if x.text == "Brasov")
    assert ed.suggestions(w)[0] == "Brașov"


def test_T_O010_1_cjk_lookalikes():
    assert "末来" in cjk_variants("未来")
    assert "已经" in cjk_variants("己经")


def test_T_O011_1_mark_verified(project):
    ed = TextEditor(project)
    ed.mark_verified(project.page(1))
    assert project.page(1).status is PageStatus.VERIFIED
    assert all(w.is_verified for w in words(project, 1))
    assert ed.next_uncertain(project.pages).text == "Brasov"
    ed.set_word_text(words(project, 1)[0], "Cererea")  # editarea scoate verificarea
    assert project.page(1).status is PageStatus.RECOGNIZED


# =============================================================================
# O-108: re-recunoasterea unei zone
# =============================================================================


def test_T_O108_1_one_area_is_recognized_again(project):
    engine = ScriptEngine()
    page = project.page(1)
    first, second = sorted(page.areas, key=lambda a: a.bbox.y)
    before = [b.text for b in first.blocks]
    RecognitionService(project, engine=engine).recognize_area_again(1, second.id)
    page = project.page(1)
    first2, second2 = sorted(page.areas, key=lambda a: a.bbox.y)
    assert engine.calls == 1 and [b.text for b in first2.blocks] == before
    assert [b.text for b in second2.blocks] == ["nou"]
    with pytest.raises(ValueError):
        RecognitionService(project, engine=engine).recognize_area_again(1, 999999)
