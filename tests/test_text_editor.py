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


# =============================================================================
# 5.2 — O-024..O-026: cautarea si inlocuirea
# =============================================================================


def test_T_O024_1_find_ignores_diacritics_and_case(project):
    """T-O024.1: implicit fara diacritice si fara majuscule; cuvant intreg la cerere."""
    ed = TextEditor(project)
    TextEditor(project).set_word_text(words(project, 2)[0], "Brașov")
    assert [w.text for w in ed.find(project.pages, "brasov")] == ["Brașov"]
    assert ed.find(project.pages, "brasov", ignore_diacritics=False) == []
    assert ed.find(project.pages, "BRAȘOV", match_case=True) == []
    assert [w.text for w in ed.find(project.pages, "proiect")] == ["ante-proiect"]
    assert ed.find(project.pages, "proiect", whole_word=True) == []
    assert [w.text for w in ed.find(project.pages, "Sibiu", whole_word=True)] == ["Sibiu,"]


def test_T_O024_2_find_a_phrase(project):
    ed = TextEditor(project)
    found = ed.find(project.pages, "finantere nr.")
    assert [w.text for w in found] == ["finantere", "nr."]


def test_T_O026_1_replace_and_delete(project):
    """T-O026.1: inlocuirea tuturor aparitiilor; textul gol sterge; un pas de undo."""
    ed = TextEditor(project)
    hits = ed.find(project.pages, "judet")
    assert ed.replace(hits, "județ") == 1
    assert "județ" in texts(project, 2)
    assert ed.replace(ed.find(project.pages, "nr."), "") == 1
    assert "nr." not in texts(project, 1)
    project.undo()
    assert "nr." in texts(project, 1)


# =============================================================================
# 5.2 — O-022, O-023: formatarea
# =============================================================================


def test_T_O022_1_formatting(project):
    ed = TextEditor(project)
    w = words(project, 1)[0]
    ed.apply_formatting([w], is_bold=True, font_name="Liberation Serif", font_size=12,
                        text_color="#aa0000", is_superscript=True)
    w = words(project, 1)[0]
    assert (w.is_bold, w.font_name, w.font_size, w.text_color, w.is_superscript) == (
        True, "Liberation Serif", 12.0, "#AA0000", True)
    ed.apply_formatting([w], is_subscript=True, is_bold=None)  # indicele scoate exponentul
    w = words(project, 1)[0]
    assert (w.is_subscript, w.is_superscript, w.is_bold) == (True, False, None)
    for bad in ({"font_size": 0}, {"text_color": "rosu"}, {"culoare": 1},
                {"is_superscript": True, "is_subscript": True}):
        with pytest.raises(ValueError):
            ed.apply_formatting([w], **bad)


# =============================================================================
# 5.2 — O-070..O-072: redactarea
# =============================================================================


def test_T_O071_1_redaction_and_undo(project):
    from app.core.text.editor import redacted_text

    ed = TextEditor(project)
    ed.redact_words(ed.find(project.pages, "Cerere"))
    w = words(project, 1)[0]
    assert w.is_redacted and redacted_text(w) == "••••••"
    assert "Cerere" not in project.page(1).text  # textul redactat nu mai apare
    project.undo()  # O-071: Ctrl+Z anuleaza ultima redactare
    assert not words(project, 1)[0].is_redacted


# =============================================================================
# 5.2 — O-027, O-060..O-063: tabelele in panoul Text
# =============================================================================


@pytest.fixture
def table_page(project):
    """Pagina 1 primeste un tabel 2 x 2 recunoscut, cu textul A, B, C, D."""
    from app.core.layout.tables import from_separators
    from app.core.ocr.store import insert_blocks

    ed = AreaEditor(project)
    area = ed.create(project.page(1), [(450, 50), (750, 50), (750, 350), (450, 350)],
                     AreaType.TABLE)
    area = ed.set_table(project.page(1), area, from_separators(area.bbox, [200], [600]))
    with project._con:
        for i, cell in enumerate(sorted(area.table.cells, key=lambda c: (c.row, c.col))):
            w = WordData(None, "ABCD"[i], 95.0, bbox=cell.bbox)
            insert_blocks(project._con, area.id, [BlockData(None, lines=[LineData(
                None, words=[w], bbox=cell.bbox)], bbox=cell.bbox)], cell.id, start=i)
        project._con.execute("UPDATE page SET status = 'recognized' WHERE id = ?",
                             (project.page(1).id,))
    project._after_change()
    return project


def the_table(project):
    return next(a for a in project.page(1).areas if a.area_type is AreaType.TABLE)


def cells(project):
    return {(c.row, c.col, c.row_span, c.col_span): " ".join(b.text for b in c.blocks)
            for c in the_table(project).table.cells}


def test_T_O060_1_merge_cells_keeps_the_text(table_page):
    ed = TextEditor(table_page)
    area = the_table(table_page)
    top = [c for c in area.table.cells if c.row == 0]
    ed.merge_cells(table_page.page(1), area, top)
    assert cells(table_page) == {(0, 0, 1, 2): "A B", (1, 0, 1, 1): "C", (1, 1, 1, 1): "D"}
    assert table_page.page(1).status is PageStatus.RECOGNIZED
    ed.split_cells(table_page.page(1), the_table(table_page),
                   the_table(table_page).table.cell_at(0, 0))  # O-061
    got = cells(table_page)
    assert got[(0, 0, 1, 1)] == "A B" and got[(0, 1, 1, 1)] == ""
    table_page.undo()
    table_page.undo()
    assert cells(table_page)[(0, 0, 1, 1)] == "A"


def test_T_O062_1_merge_rows(table_page):
    ed = TextEditor(table_page)
    ed.merge_rows(table_page.page(1), the_table(table_page), [0, 1])
    got = cells(table_page)
    assert got == {(0, 0, 1, 1): "A C", (0, 1, 1, 1): "B D"}


def test_T_O063_1_delete_clears_the_cell_not_the_structure(table_page):
    ed = TextEditor(table_page)
    cell = the_table(table_page).table.cell_at(1, 1)
    ed.clear_cell(cell)
    got = cells(table_page)
    assert len(got) == 4 and got[(1, 1, 1, 1)] == "" and got[(0, 0, 1, 1)] == "A"


def test_T_O027_1_arrow_navigation(table_page):
    area = the_table(table_page)
    a = area.table.cell_at(0, 0)
    right = TextEditor.neighbor_cell(area, a, "right")
    assert (right.row, right.col) == (0, 1)
    assert TextEditor.neighbor_cell(area, a, "up") is a  # la margine ramane pe loc
    down = TextEditor.neighbor_cell(area, right, "down")
    assert (down.row, down.col) == (1, 1)


# =============================================================================
# 5.2 — O-080..O-083: copierea
# =============================================================================


def test_T_O081_1_copy_area_text_and_image(table_page):
    ed = TextEditor(table_page)
    page = table_page.page(1)
    text_area = min((a for a in page.areas if a.area_type is AreaType.TEXT), key=lambda a: a.bbox.y)
    assert ed.area_text(page, text_area).startswith("Cerere finantere")
    assert ed.area_text(page, the_table(table_page)) == "A\nB\nC\nD"
    png = ed.area_image(page, the_table(table_page))
    from io import BytesIO

    assert Image.open(BytesIO(png)).size == (300, 300)


def test_T_O081_2_unrecognized_area_is_recognized_first(project):
    """O-081: o zona fara text se recunoaste intai (O-108)."""
    page = project.page(1)
    empty = sorted(page.areas, key=lambda a: a.bbox.y)[1]
    from app.core.ocr import service

    original = service.RecognitionService.__init__

    def fake_init(self, project, engine=None, analyzer=None):
        original(self, project, engine=ScriptEngine(), analyzer=analyzer)

    service.RecognitionService.__init__ = fake_init
    try:
        assert TextEditor(project).area_text(page, empty) == "nou"
    finally:
        service.RecognitionService.__init__ = original


def test_T_O083_1_several_pages(project):
    text = TextEditor(project).pages_text([1, 2])
    assert text.split("\f")[0].startswith("Cerere") and text.split("\f")[1].startswith("Brasov")
