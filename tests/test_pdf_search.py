"""Cautarea in PDF, marcarea rezultatelor si listele de cuvinte cheie
(faza 7, pasul 7.2a): C-002…C-010, C-027…C-032."""

from __future__ import annotations

import pikepdf
import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.export.base import ExportOptions
from app.core.model import (
    AnnotationType,
    BlockData,
    LayoutMode,
    LineData,
    Rect,
    WordData,
)
from app.core.ocr.engine import RecognitionResult
from app.core.paths import AppPaths
from app.core.pdf.document import PdfDocument
from app.core.pdf.keywords import Keyword, KeywordListStore, search_keywords
from app.core.pdf.markup import default_color
from app.core.pdf.text import (
    SOURCE_BOOKMARKS,
    SOURCE_COMMENTS,
    SOURCE_METADATA,
    SOURCE_TEXT,
    PageText,
    find_all,
    fold,
)


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def text_pdf(path, pages):
    """`pages`: lista de pagini, fiecare o lista de randuri (Helvetica, ASCII)."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica))
    for lines in pages:
        ops = " ".join(f"BT /F1 20 Tf 72 {760 - i * 40} Td ({line}) Tj ET"
                       for i, line in enumerate(lines))
        pdf.pages.append(pikepdf.Page(pikepdf.Dictionary(
            Type=pikepdf.Name.Page, MediaBox=[0, 0, 595, 842],
            Contents=pdf.make_stream(ops.encode()),
            Resources=pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font)))))
    pdf.docinfo["/Title"] = "Dosar de finantare"
    note = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Text, Rect=[300, 500, 320, 520],
        Contents=pikepdf.String("De verificat bugetul")))
    pdf.pages[0].obj.Annots = pdf.make_indirect(pikepdf.Array([note]))
    with pdf.open_outline() as outline:
        outline.root.append(pikepdf.OutlineItem("Bugetul proiectului", len(pages) - 1))
    pdf.save(path)
    return path


@pytest.fixture
def doc(tmp_path):
    path = text_pdf(tmp_path / "dosar.pdf", [
        ["Cerere de finantare", "Bugetul total: 1200 lei"],
        ["Anexa 2: buget detaliat", "Bugetare si BUGET"],
    ])
    with PdfDocument.open(path) as d:
        yield d


class TextEngine:
    """Motor OCR fals: pagina primeste cuvintele date."""

    name = "fals"

    def __init__(self, words):
        self.words = words

    def _block(self):
        words = [WordData(None, w, 95.0, bbox=Rect(60 + i * 160, 60, 140, 40))
                 for i, w in enumerate(self.words)]
        return BlockData(None, lines=[LineData(None, words=words, bbox=Rect(60, 60, 480, 40))],
                         bbox=Rect(60, 60, 480, 40))

    def recognize_area(self, page, area, settings, cancel=None):
        block = self._block()
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=95.0,
                                 area_blocks={area.id: [block]})

    def recognize_page(self, page, settings, cancel=None):
        block = self._block()
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=95.0,
                                 area_blocks={a.id: [block] for a in page.areas[:1]})


# --- potrivirea -----------------------------------------------------------------------


def test_fold_keeps_length_and_unifies_diacritics():
    assert fold("ŞŢşţ", True) == "ȘȚșț"
    assert fold("Ştampilă", False) == "ștampilă"
    assert len(fold("İstanbul", False)) == len("İstanbul")


def test_T_C003_1_exact_match_finds_whole_words_only():
    text = "buget, Bugetul si bugetare; buget"
    assert find_all(text, "buget") == [(0, 5), (7, 5), (18, 5), (28, 5)]
    assert find_all(text, "buget", whole_word=True) == [(0, 5), (28, 5)]


def test_T_C004_1_match_case():
    assert find_all("Buget buget BUGET", "buget", match_case=True) == [(6, 5)]
    assert len(find_all("Buget buget BUGET", "buget")) == 3


def test_T_C002_1_query_needs_one_character(doc):
    with pytest.raises(ValueError):
        doc.search("")


# --- cautarea in document ---------------------------------------------------------------


def test_T_C002_2_results_grouped_by_source(doc):
    hits = doc.search("buget")
    order = [SOURCE_TEXT, SOURCE_COMMENTS, SOURCE_BOOKMARKS, SOURCE_METADATA]
    sources = [h.source for h in hits]
    assert sources == sorted(sources, key=order.index)
    text = [h for h in hits if h.source == SOURCE_TEXT]
    assert [(h.page, h.found) for h in text] == [
        (1, "Buget"), (2, "buget"), (2, "Buget"), (2, "BUGET")]
    assert [h.page for h in hits if h.source == SOURCE_COMMENTS] == [1]
    bookmark = [h for h in hits if h.source == SOURCE_BOOKMARKS]
    assert bookmark[0].page == 2 and bookmark[0].context == "Bugetul proiectului"
    assert not [h for h in hits if h.source == SOURCE_METADATA]
    assert [h.context for h in doc.search("finantare") if h.source == SOURCE_METADATA] == \
        ["title: Dosar de finantare"]


def test_T_C002_3_hit_is_the_contract_tuple_with_position(doc):
    page, rect, context = doc.search("Cerere", in_comments=False)[0]
    assert page == 1
    assert context.startswith("Cerere de finantare")
    # Helvetica 20 pt la x=72, linia de baza la y=760 de jos → sus la ~67 de sus
    assert 70 <= rect.x <= 74
    assert 60 <= rect.y <= 85
    assert 50 < rect.w < 80 and 10 < rect.h < 25


def test_T_C002_4_sources_can_be_excluded(doc):
    hits = doc.search("buget", in_comments=False, in_bookmarks=False, in_metadata=False)
    assert {h.source for h in hits} == {SOURCE_TEXT}


def test_T_C003_C004_options_in_document(doc):
    assert [h.found for h in doc.search("buget", whole_word=True, in_comments=False,
                                        in_bookmarks=False)] == ["buget", "BUGET"]
    assert [h.found for h in doc.search("BUGET", match_case=True)] == ["BUGET"]


def test_romanian_diacritics_match_both_forms(tmp_path, ctx):
    image = tmp_path / "scan.png"
    img = Image.new("L", (600, 800), 255)
    img.paste(0, (60, 60, 540, 100))  # ceva de recunoscut, ca pagina sa aiba o zona
    img.save(image, dpi=(300, 300))
    with PdfDocument.from_images([image], options=ExportOptions(layout_mode=LayoutMode.EXACT),
                                 context=ctx, engine=TextEngine(["ştampila", "țară"])) as d:
        assert [h.found for h in d.search("ștampila")] == ["ştampila"]
        assert [h.found for h in d.search("ŢARĂ")] == ["țară"]


def test_span_rects_split_per_line():
    a, b = Rect(10, 10, 8, 12), Rect(18, 10, 8, 12)
    c = Rect(10, 40, 8, 12)
    page = PageText(1, "ab\nc", (a, b, None, c), 842, 0, 0)
    assert page.span_rects(0, 4) == [Rect(10, 10, 16, 12), Rect(10, 40, 8, 12)]


# --- marcajele (C-007…C-010) ----------------------------------------------------------


@pytest.mark.parametrize(("kind", "subtype"), [
    (AnnotationType.HIGHLIGHT, "/Highlight"),
    (AnnotationType.UNDERLINE, "/Underline"),
    (AnnotationType.STRIKETHROUGH, "/StrikeOut"),
])
def test_T_C007_1_marking_creates_annotations_not_text(doc, tmp_path, kind, subtype):
    before = [doc.extract_text(n) for n in (1, 2)]
    hits = doc.search("buget")
    created = doc.mark_hits(hits, kind, "#FFD84D", author="Ana")
    assert created == 4  # numai rezultatele din textul paginilor
    assert doc.is_modified
    assert [doc.extract_text(n) for n in (1, 2)] == before
    doc.save_as(tmp_path / "marcat.pdf")
    with pikepdf.open(tmp_path / "marcat.pdf") as pdf:
        marks = [a for page in pdf.pages for a in page.get("/Annots", [])
                 if a.Subtype == subtype]
        assert len(marks) == 4
        first = marks[0]
        assert len(first.QuadPoints) == 8
        assert [round(float(v), 3) for v in first.C] == [1.0, 0.847, 0.302]
        assert str(first.T) == "Ana"
        assert "/N" in first.AP
        x0, y0, x1, y1 = (float(v) for v in first.Rect)
        assert 70 <= x0 < x1 and 700 < y0 < y1 < 790


def test_T_C010_1_default_colors_come_from_settings(ctx):
    assert default_color(ctx.settings, AnnotationType.HIGHLIGHT) == "#FFD84D"
    ctx.settings.set("pdf_editor.markup_color.underline", "#123456")
    assert default_color(ctx.settings, AnnotationType.UNDERLINE) == "#123456"


def test_marking_rejects_bad_input(doc):
    hits = [h for h in doc.search("Cerere") if h.source == SOURCE_TEXT]
    with pytest.raises(ValueError):
        doc.mark_hits(hits, AnnotationType.HIGHLIGHT, "galben")
    with pytest.raises(ValueError):
        doc.mark_hits(hits, AnnotationType.NOTE, "#FFD84D")
    metadata_only = [h for h in doc.search("finantare") if h.source == SOURCE_METADATA]
    assert doc.mark_hits(metadata_only, AnnotationType.HIGHLIGHT, "#FFD84D") == 0
    assert not doc.is_modified


# --- listele de cuvinte cheie (C-027…C-032) -------------------------------------------


def test_T_C027_1_add_keyword_creates_list_once(ctx):
    store = KeywordListStore(ctx.app_db)
    store.add("Date personale", "CNP")
    store.add("Date personale", "CNP")
    store.add("Date personale", Keyword("IBAN", match_case=True))
    assert store.names() == ["Date personale"]
    assert store.keywords("Date personale") == [Keyword("CNP"), Keyword("IBAN", match_case=True)]
    with pytest.raises(ValueError):
        store.add("Date personale", "  ")


def test_T_C029_1_edit_and_save_list(ctx):
    import re

    store = KeywordListStore(ctx.app_db)
    store.save("Sume", [Keyword("lei"), Keyword(r"\d{4}", is_regex=True)])
    store.save("Sume", [Keyword("euro", whole_word=True)])
    assert store.keywords("Sume") == [Keyword("euro", whole_word=True)]
    with pytest.raises(ValueError):
        store.save("Sume", [Keyword("a"), Keyword("a")])
    with pytest.raises(ValueError):
        store.create("Sume")
    with pytest.raises(re.error):
        store.save("Sume", [Keyword("(", is_regex=True)])
    assert store.keywords("Sume") == [Keyword("euro", whole_word=True)]
    store.delete("Sume")
    assert store.names() == []
    with pytest.raises(KeyError):
        store.keywords("Sume")


def test_T_C028_1_find_using_keyword_list(doc, ctx):
    store = KeywordListStore(ctx.app_db)
    store.save("Dosar", [Keyword("buget", whole_word=True), Keyword(r"\d{4}", is_regex=True),
                         Keyword("BUGET", match_case=True)])
    hits = search_keywords(doc, store.keywords("Dosar"), in_comments=False,
                           in_bookmarks=False, in_metadata=False)
    assert [(h.page, h.found) for h in hits] == [(1, "1200"), (2, "buget"), (2, "BUGET")]
