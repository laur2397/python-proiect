"""Adnotarile si comentariile din PDF Editor (faza 7, pasul 7.4a): D-001…D-044."""

from __future__ import annotations

import io

import pikepdf
import pytest
from PIL import Image
from test_pdf_search import text_pdf

from app.core.errors import NoTextFoundError
from app.core.model import AnnotationData, AnnotationType, Rect, ReviewStatus
from app.core.pdf import annotations as ann
from app.core.pdf.document import PdfDocument

T = AnnotationType


@pytest.fixture
def path(tmp_path):
    path = text_pdf(tmp_path / "dosar.pdf", [
        ["Cerere de finantare", "Bugetul total: 1200 lei"],
        ["Anexa 2: buget detaliat"],
    ])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:  # un link, care nu e comentariu
        link = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link, Rect=[72, 72, 120, 90]))
        pdf.pages[1].obj.Annots = pdf.make_indirect(pikepdf.Array([link]))
        pdf.save(path)
    return path


@pytest.fixture
def doc(path):
    with PdfDocument.open(path) as d:
        yield d


def note(page=1, **kw):
    return AnnotationData(None, T.NOTE, page, {"point": (100, 100)}, **kw)


def pixel(doc, page, x, y):
    image = Image.open(io.BytesIO(doc.render_page(page, 1.0))).convert("RGB")
    return image.getpixel((round(x * 96 / 72), round(y * 96 / 72)))


# --- D-001…D-007 ----------------------------------------------------------------------


def test_T_D001_1_note_is_created_and_read_back(doc, tmp_path):
    before = len(doc.annotations())  # nota din fixture
    created = doc.add_annotation(note(content="De completat", author="Ana", color="#FFD84D"))
    assert created.id is not None
    assert created.annot_type is T.NOTE
    assert created.geometry == {"point": (100.0, 100.0)}
    assert (created.content, created.author, created.color) == ("De completat", "Ana", "#FFD84D")
    assert created.created_at.endswith("Z")
    assert doc.is_modified
    assert len(doc.annotations()) == before + 1
    assert pixel(doc, 1, 102, 110) != (255, 255, 255)  # iconul se vede
    doc.save_as(tmp_path / "nota.pdf")
    with pikepdf.open(tmp_path / "nota.pdf") as pdf:
        texts = [a for a in pdf.pages[0].Annots if a.Subtype == "/Text" and "/T" in a]
        assert str(texts[0].Contents) == "De completat" and "/N" in texts[0].AP


def test_T_D001_2_empty_note_text_is_allowed(doc):
    assert doc.add_annotation(note()).content is None


def test_T_D003_1_markup_needs_a_text_layer(tmp_path):
    image = tmp_path / "scan.pdf"
    Image.new("L", (600, 800), 255).save(image, "PDF", resolution=300)
    with PdfDocument.open(image) as scan:
        with pytest.raises(NoTextFoundError) as info:
            scan.add_annotation(AnnotationData(None, T.HIGHLIGHT, 1,
                                               {"rects": [Rect(10, 10, 50, 10)]}))
        assert info.value.params["page_number"] == 1
        assert not scan.is_modified


@pytest.mark.parametrize(("kind", "subtype"), [
    (T.HIGHLIGHT, "/Highlight"), (T.UNDERLINE, "/Underline"), (T.STRIKETHROUGH, "/StrikeOut")])
def test_T_D004_1_text_markups(doc, kind, subtype):
    from app.core.settings import MARKUP_COLORS

    hit = next(h for h in doc.search("Bugetul") if h.source == "text")
    created = doc.add_annotation(AnnotationData(None, kind, 1, {"rects": list(hit.rects)},
                                                opacity=0.6))
    assert created.annot_type is kind
    got, want = created.geometry["rects"][0], hit.rects[0]
    assert (got.x, got.y, got.w, got.h) == pytest.approx((want.x, want.y, want.w, want.h))
    assert created.opacity == pytest.approx(0.6)
    assert str(ann._find(doc, created.id)[1].Subtype) == subtype
    assert created.color == MARKUP_COLORS[kind.value]  # C-010: culoarea implicita


def test_T_D007_1_insert_text_caret(doc):
    created = doc.add_annotation(AnnotationData(None, T.INSERT_TEXT, 1, {"point": (200, 300)},
                                                content="si anexele"))
    assert created.annot_type is T.INSERT_TEXT and created.content == "si anexele"
    assert created.geometry["point"] == pytest.approx((200, 300))


# --- D-009…D-016 ----------------------------------------------------------------------


def _flat(values, depth):
    for _ in range(depth):
        values = [c for v in values for c in v]
    return values


@pytest.mark.parametrize(("kind", "geometry"), [
    (T.INK, {"paths": [[(100, 400), (120, 410), (140, 400)], [(150, 400), (160, 420)]]}),
    (T.LINE, {"points": [(100, 300), (200, 320)]}),
    (T.ARROW, {"points": [(100, 330), (200, 350)]}),
    (T.POLYGON, {"points": [(300, 400), (350, 420), (320, 460)]}),
    (T.CLOUD, {"points": [(400, 400), (480, 400), (480, 460), (400, 460)]}),
    (T.POLYLINE, {"points": [(100, 500), (150, 520), (200, 500)]}),
])
def test_T_D009_1_shapes_round_trip(doc, kind, geometry):
    created = doc.add_annotation(AnnotationData(None, kind, 1, geometry, line_width=2))
    assert created.annot_type is kind
    key = next(iter(geometry))
    depth = 2 if kind is T.INK else 1
    assert _flat(created.geometry[key], depth) == pytest.approx(_flat(geometry[key], depth))
    assert created.line_width == 2


@pytest.mark.parametrize("kind", [T.RECTANGLE, T.OVAL])
def test_T_D012_1_rectangle_and_oval(doc, kind):
    created = doc.add_annotation(AnnotationData(None, kind, 1, {}, bbox=Rect(100, 200, 120, 60),
                                                color="#2F6DF6", fill_color="#EEEEEE",
                                                line_width=3))
    assert created.bbox == Rect(100, 200, 120, 60)
    assert created.fill_color == "#EEEEEE"
    assert pixel(doc, 1, 160, 230) == (238, 238, 238)  # fundalul
    edge = pixel(doc, 1, 101, 230) if kind is T.RECTANGLE else pixel(doc, 1, 160, 201)
    assert edge[2] > edge[0]  # conturul albastru


def test_T_D016_1_line_width_limits(doc):
    for width in (0.4, 12.5):
        with pytest.raises(ValueError):
            doc.add_annotation(AnnotationData(None, T.LINE, 1,
                                              {"points": [(0, 0), (10, 10)]}, line_width=width))
    with pytest.raises(ValueError):
        doc.add_annotation(AnnotationData(None, T.POLYGON, 1, {"points": [(0, 0), (1, 1)]}))
    with pytest.raises(ValueError):
        doc.add_annotation(note(color="rosu"))
    assert not doc.is_modified


# --- D-017…D-023 ----------------------------------------------------------------------


def test_T_D017_1_text_box_with_romanian_text(doc, tmp_path):
    from app.core.pdf.redact import text_font_file

    text = "Ștampila și semnătura țin de beneficiar"
    created = doc.add_annotation(AnnotationData(
        None, T.TEXT_BOX, 1, {"font_size": 11, "text_color": "#15803D"},
        bbox=Rect(250, 500, 200, 60), content=text, color="#000000"))
    assert created.content == text
    assert created.geometry == {"font_size": 11.0, "text_color": "#15803D", "text_block": False}
    assert created.fill_color is None  # D-020: fundal transparent implicit
    doc.save_as(tmp_path / "caseta.pdf")
    with pikepdf.open(tmp_path / "caseta.pdf") as pdf:
        box = next(a for a in pdf.pages[0].Annots if a.Subtype == "/FreeText")
        font = box.AP.N.Resources.Font.F1
        if text_font_file() is not None:  # fontul incorporat are ToUnicode cu ș si ț
            cmap = font.ToUnicode.read_bytes().decode("ascii")
            assert "0218" in cmap and "0219" in cmap and "021B" in cmap
    image = Image.open(io.BytesIO(doc.render_page(1, 1.0))).convert("L")
    inside = image.crop((round(252 * 4 / 3), round(502 * 4 / 3), round(448 * 4 / 3),
                         round(520 * 4 / 3)))
    assert inside.getextrema()[0] < 128  # textul se vede in caseta


def test_T_D019_1_text_block_is_an_annotation(doc):
    before = doc.extract_text(1)
    created = doc.add_annotation(AnnotationData(None, T.TEXT_BOX, 1, {"text_block": True},
                                                bbox=Rect(100, 600, 150, 30), content="Bloc"))
    assert created.geometry["text_block"] is True
    assert doc.extract_text(1) == before  # D-021: nu e text de corp
    assert created.id in [a.id for a in doc.annotations()]  # D-023: apare in Comments


# --- D-024…D-032 ----------------------------------------------------------------------


def test_T_D024_1_links_are_not_comments(doc):
    assert all(a.page_number == 1 for a in doc.annotations())
    assert doc.annotations(page=2) == []


def test_T_D026_1_replies_are_nested(doc):
    parent = doc.add_annotation(note(content="Intrebare", author="Ana"))
    first = doc.add_reply(parent.id, "Raspuns", "Ion")
    doc.add_reply(first.id, "Raspuns la raspuns", "Ana")
    doc.add_reply(parent.id, "Al doilea", "Maria")
    item = next(a for a in doc.annotations() if a.id == parent.id)
    assert [(r.content, r.author) for r in item.replies] == [("Raspuns", "Ion"),
                                                             ("Al doilea", "Maria")]
    assert item.replies[0].replies[0].content == "Raspuns la raspuns"
    assert item.replies[0].parent_id == parent.id
    assert len(doc.annotations()) == 2  # nota din fixture si cea noua; raspunsurile nu


def test_T_D027_D028_delete_reply_and_annotation(doc):
    parent = doc.add_annotation(note(content="Intrebare"))
    reply = doc.add_reply(parent.id, "Raspuns", "Ion")
    doc.add_reply(reply.id, "Sub-raspuns", "Ana")
    doc.set_review_status(parent.id, ReviewStatus.ACCEPTED, "Ion")
    doc.delete_annotations([reply.id])  # D-027: raspunsul cu ale lui
    assert next(a for a in doc.annotations() if a.id == parent.id).replies == []
    doc.delete_annotations([parent.id])  # D-028: adnotarea cu tot
    assert parent.id not in [a.id for a in doc.annotations()]
    remaining = [a for page in doc._pike().pages for a in page.obj.get("/Annots", [])
                 if "/IRT" in a]
    assert remaining == []
    with pytest.raises(KeyError):
        doc.delete_annotations([parent.id])


def test_T_D029_1_delete_all_comments_keeps_links(doc):
    doc.add_annotation(note())
    doc.add_annotation(AnnotationData(None, T.RECTANGLE, 2, {}, bbox=Rect(10, 10, 20, 20)))
    assert doc.delete_all_annotations() == 3
    assert doc.annotations() == []
    assert [str(a.Subtype) for a in doc._pike().pages[1].obj.Annots] == ["/Link"]
    assert doc.delete_all_annotations() == 0


def test_T_D030_D031_checkmark_and_status_history(doc):
    created = doc.add_annotation(note(content="De verificat"))
    ann.set_checked(doc, created.id, True, "Ana")
    doc.set_review_status(created.id, ReviewStatus.ACCEPTED, "Ion")
    doc.set_review_status(created.id, ReviewStatus.COMPLETED, "Maria")
    item = ann.read_annotation(doc, created.id)
    assert item.is_checked and item.review_status is ReviewStatus.COMPLETED
    history = ann.status_history(doc, created.id)
    assert [(s, a) for s, a, _ in history] == [(ReviewStatus.ACCEPTED, "Ion"),
                                               (ReviewStatus.COMPLETED, "Maria")]
    ann.set_checked(doc, created.id, False, "Ana")
    doc.set_review_status(created.id, None, "Ion")
    item = ann.read_annotation(doc, created.id)
    assert not item.is_checked and item.review_status is None
    assert item.replies == []  # starile nu sunt raspunsuri


def test_T_D052_1_update_moves_and_restyles(doc):
    created = doc.add_annotation(AnnotationData(None, T.RECTANGLE, 1, {},
                                                bbox=Rect(100, 200, 50, 50)))
    doc.add_reply(created.id, "Ok", "Ion")
    moved = doc.update_annotation(AnnotationData(
        created.id, T.RECTANGLE, 1, {}, bbox=Rect(300, 400, 80, 40), color="#15803D",
        line_width=4, content="mutat"))
    assert moved.id == created.id
    assert moved.bbox == Rect(300, 400, 80, 40)
    assert (moved.color, moved.line_width, moved.content) == ("#15803D", 4.0, "mutat")
    assert [r.content for r in moved.replies] == ["Ok"]
    assert moved.created_at == created.created_at


def test_annotations_survive_saving(doc, tmp_path):
    doc.add_annotation(note(content="Persistenta", author="Ana"))
    doc.add_annotation(AnnotationData(None, T.CLOUD, 1,
                                      {"points": [(100, 100), (200, 100), (150, 180)]}))
    doc.save_as(tmp_path / "salvat.pdf")
    with PdfDocument.open(tmp_path / "salvat.pdf") as saved:
        kinds = sorted(a.annot_type.value for a in saved.annotations())
        assert kinds == ["cloud", "note", "note"]
        assert "Persistenta" in [a.content for a in saved.annotations()]


# --- D-033…D-044 ----------------------------------------------------------------------


def _items():
    def item(i, kind, page, author, date, content, **kw):
        return AnnotationData(i, kind, page, {}, author=author, content=content,
                              created_at=date, **kw)

    reply = item(10, T.NOTE, 1, "Maria", "2026-11-03T08:00:00Z", "de acord cu bugetul")
    return [
        item(1, T.NOTE, 1, "Ana", "2026-11-01T10:00:00Z", "Lipsește anexa",
             replies=[reply]),
        item(2, T.HIGHLIGHT, 2, "Ion", "2026-11-02T10:00:00Z", None, is_checked=True),
        item(3, T.RECTANGLE, 3, "ana", "2026-11-05T10:00:00Z", "Semnătura",
             review_status=ReviewStatus.ACCEPTED),
    ]


def test_T_D034_1_search_in_text_replies_and_authors():
    items = _items()
    f = ann.CommentFilter()
    assert [a.id for a in ann.filter_comments(items, f, "bugetul")] == [1]  # din raspuns
    assert [a.id for a in ann.filter_comments(items, f, "ION")] == [2]
    assert [a.id for a in ann.filter_comments(items, f, "lipseşte")] == [1]  # sedila = virgula


def test_T_D036_D043_filters_and_reset():
    items = _items()
    f = ann.CommentFilter(types={T.NOTE, T.RECTANGLE})
    assert [a.id for a in ann.filter_comments(items, f)] == [1, 3]
    f.authors = {"Ana"}
    assert [a.id for a in ann.filter_comments(items, f)] == [1]
    f.reset()
    f.pages = (2, 3)
    assert [a.id for a in ann.filter_comments(items, f)] == [2, 3]
    f.reset()
    f.dates = ("2026-11-02", "2026-11-04")
    assert [a.id for a in ann.filter_comments(items, f)] == [2]
    f.reset()
    f.checked = True
    assert [a.id for a in ann.filter_comments(items, f)] == [2]
    f.reset()
    f.statuses = {ReviewStatus.ACCEPTED}
    assert [a.id for a in ann.filter_comments(items, f)] == [3]
    f.reset()
    f.hidden = {1, 2}  # D-036 `Hide Current Comments`
    assert [a.id for a in ann.filter_comments(items, f)] == [3]
    f.reset()
    assert len(ann.filter_comments(items, f)) == 3


def test_T_D035_1_sorting():
    items = _items()
    assert [a.id for a in ann.sort_comments(items, "date")] == [1, 2, 3]
    assert [a.id for a in ann.sort_comments(items, "author")] == [1, 3, 2]
    assert [a.id for a in ann.sort_comments(items, "type")] == [2, 1, 3]
    with pytest.raises(ValueError):
        ann.sort_comments(items, "culoare")


def test_iso_date_conversion():
    assert ann.iso_date("D:20261122093015+02'00'") == "2026-11-22T07:30:15Z"
    assert ann.iso_date("D:20261122093015Z") == "2026-11-22T09:30:15Z"
    assert ann.iso_date("D:2026") == "2026-01-01T00:00:00Z"
    assert ann.iso_date("") == "" and ann.iso_date("ieri") == ""
