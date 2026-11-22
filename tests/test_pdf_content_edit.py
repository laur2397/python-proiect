"""Editarea continutului (faza 9, pasul 9.5): F-002, F-005, F-006, F-008, F-011…F-023."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pikepdf
import pytest
from PIL import Image, ImageDraw
from test_pdf_background import LineEngine

from app.core.context import AppContext
from app.core.model import Rect
from app.core.paths import AppPaths
from app.core.pdf.content import ContentNotEditableError, TextBlock
from app.core.pdf.document import PdfDocument
from app.core.pdf.editor import PdfContentEditor


def paragraph_pdf(path, paragraphs, *, size=12, leading=15):
    """Paragrafe de text Helvetica; randurile unui paragraf la `leading` puncte,
    paragrafele despartite de un spatiu mai mare."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica))
    ops, y = [], 760
    for lines in paragraphs:
        for line in lines:
            ops.append(f"BT /F1 {size} Tf 72 {y} Td ({line}) Tj ET")
            y -= leading
        y -= leading * 3
    pdf.pages.append(pikepdf.Page(pikepdf.Dictionary(
        Type=pikepdf.Name.Page, MediaBox=[0, 0, 595, 842],
        Contents=pdf.make_stream(" ".join(ops).encode()),
        Resources=pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font)))))
    pdf.save(path)
    return path


@pytest.fixture
def doc(tmp_path):
    path = paragraph_pdf(tmp_path / "doc.pdf", [
        ["Cerere de finantare", "pentru proiectul de cercetare"],
        ["Bugetul total este de 1200 lei"],
    ])
    with PdfDocument.open(path) as d:
        yield d


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def find(doc, text):
    hits = doc.search(text, in_comments=False, in_bookmarks=False, in_metadata=False)
    return [h[1] for h in hits]


def pixels(doc, page=1, zoom=1.0):
    return np.asarray(Image.open(io.BytesIO(doc.render_page(page, zoom))).convert("RGB"))


# --- F-001…F-003, F-005, F-006 ----------------------------------------------------------------


def test_T_F001_blocks_of_a_digital_pdf(doc):
    editor = PdfContentEditor(doc)
    assert editor.prepare_page(1).kind == "text"
    assert [b.text for b in editor.blocks(1)] == [
        "Cerere de finantare\npentru proiectul de cercetare", "Bugetul total este de 1200 lei"]
    block = editor.block(1, 1)
    assert block.font_size == pytest.approx(12, abs=0.5) and block.color == "#000000"
    assert block.rect.x == pytest.approx(72, abs=2)


def test_T_F002_vector_text_cannot_be_edited(tmp_path):
    pdf = pikepdf.new()
    pdf.pages.append(pikepdf.Page(pikepdf.Dictionary(
        Type=pikepdf.Name.Page, MediaBox=[0, 0, 595, 842],
        Contents=pdf.make_stream(b"0 g 100 700 m 120 740 l 140 700 l f"))))
    path = tmp_path / "vector.pdf"
    pdf.save(path)
    with PdfDocument.open(path) as vector, pytest.raises(ContentNotEditableError):
        PdfContentEditor(vector).prepare_page(1)


def test_T_F005_font_in_square_brackets_is_embedded_but_not_installed():
    block = TextBlock(1, Rect(0, 0, 10, 10), "x", font_name="Calibri", embedded=True,
                      installed=False)
    assert block.display_font == "[Calibri]"
    assert TextBlock(1, Rect(0, 0, 10, 10), "x", font_name="Arial").display_font == "Arial"


def test_T_F006_missing_font_falls_back_to_the_closest(monkeypatch):
    from app.core import fonts
    from app.core.pdf import content

    calls = []

    def fake(family, bold=False, italic=False):
        calls.append(family)
        return None if family == "Garamond Premier" else Path(f"/f/{family}.ttf")

    monkeypatch.setattr(fonts, "font_file", fake)
    block = TextBlock(1, Rect(0, 0, 10, 10), "x", font_name="Garamond Premier")
    assert content.font_path(block).name == "Times New Roman.ttf"
    assert calls == ["Garamond Premier", "Times New Roman"]


# --- F-008, F-011…F-016 ------------------------------------------------------------------------


def test_T_F008_edit_text_with_reflow(doc):
    editor = PdfContentEditor(doc)
    editor.prepare_page(1)
    long = "Cerere de finantare nerambursabila pentru proiectul de cercetare aplicata " * 2
    editor.set_block_text(1, 1, long.strip())
    text = doc.extract_text(1)
    assert "nerambursabila" in text and "Bugetul total" in text
    block = next(b for b in editor.text_blocks(1) if "nerambursabila" in b.text)
    hits = find(doc, "nerambursabila")
    assert len(hits) == 2
    for rect in hits:  # textul ramane in latimea blocului
        assert rect.x >= block.rect.x - 1 and rect.x + rect.w <= block.rect.x + block.rect.w + 1


def test_T_F011_new_block_must_stay_inside_the_page(doc):
    editor = PdfContentEditor(doc)
    with pytest.raises(ValueError):
        editor.add_text_block(1, Rect(500, 100, 200, 50), "prea lat")
    with pytest.raises(ValueError):
        editor.add_text_block(1, Rect(72, 820, 200, 50), "prea jos")
    editor.add_text_block(1, Rect(72, 400, 300, 40), "Bloc nou adaugat")
    assert "Bloc nou adaugat" in doc.extract_text(1)
    with pytest.raises(ValueError):  # textul care ar curge sub pagina
        editor.add_text_block(1, Rect(72, 800, 30, 20), "un text lung " * 10)


def test_T_F012_delete_a_block(doc):
    editor = PdfContentEditor(doc)
    editor.prepare_page(1)
    editor.delete_block(1, 2)
    text = doc.extract_text(1)
    assert "Bugetul" not in text and "Cerere de finantare" in text
    assert [b.id for b in editor.text_blocks(1)] == [1]


def test_T_F013_F014_resize_and_move(doc):
    editor = PdfContentEditor(doc)
    editor.prepare_page(1)
    before = find(doc, "Bugetul")[0]
    editor.move_block(1, 2, 100, 50)
    after = find(doc, "Bugetul")[0]
    assert after.x - before.x == pytest.approx(100, abs=2)
    assert after.y - before.y == pytest.approx(50, abs=3)
    moved = next(b for b in editor.text_blocks(1) if "Bugetul" in b.text)
    editor.resize_block(1, moved.id, Rect(moved.rect.x, moved.rect.y, 80, moved.rect.h))
    resized = next(b for b in editor.text_blocks(1) if "Bugetul" in b.text)
    assert resized.rect.h > moved.rect.h * 1.4  # mai ingust: mai multe randuri
    with pytest.raises(ValueError):
        editor.resize_block(1, resized.id, Rect(72, 300, 5, 20))
    with pytest.raises(ValueError):
        editor.move_block(1, resized.id, 0, 2000)


def test_T_F015_F016_font_size_style_alignment_color(doc):
    editor = PdfContentEditor(doc)
    editor.prepare_page(1)
    with pytest.raises(ValueError):
        editor.apply_text_format(1, 2, font_size=1639)
    with pytest.raises(ValueError):
        editor.apply_text_format(1, 2, weight="heavy")
    editor.apply_text_format(1, 2, font_size=24, color="#cc0000", alignment="right",
                             bold=True, underline=True)
    rect = find(doc, "Bugetul")[0]
    assert rect.h == pytest.approx(24, abs=8)
    formatted = next(b for b in editor.text_blocks(1) if "Bugetul" in b.text)
    end = max(r.x + r.w for r in find(doc, "lei"))
    assert end == pytest.approx(formatted.rect.x + formatted.rect.w, abs=3)  # la dreapta
    image = pixels(doc)
    scale = image.shape[1] / doc.page_size(1)[0]
    patch = image[int(rect.y * scale):int((rect.y + rect.h) * scale),
                  int(rect.x * scale):int((rect.x + rect.w) * scale)].reshape(-1, 3)
    assert ((patch[:, 0] > 150) & (patch[:, 1] < 80)).any()


def test_failed_edit_leaves_the_page_unchanged(doc):
    editor = PdfContentEditor(doc)
    editor.prepare_page(1)
    before = doc.extract_text(1)
    with pytest.raises(ValueError):
        editor.set_block_text(1, 2, "foarte lung " * 400)  # ar curge sub pagina
    assert doc.extract_text(1) == before


# --- scanari ------------------------------------------------------------------------------------


@pytest.fixture
def scan(tmp_path):
    img = Image.new("L", (1200, 1600), 255)
    img.paste(0, (120, 120, 1080, 200))
    path = tmp_path / "scan.pdf"
    img.save(path, "PDF", resolution=300)
    return path


def test_T_F002_scanned_page_is_edited_over_its_ocr_layer(scan, ctx):
    with PdfDocument.open(scan) as doc:
        editor = PdfContentEditor(doc)
        prepared = editor.prepare_page(1, context=ctx, engine=LineEngine(["Cerere", "veche"]))
        assert prepared.kind == "scan"
        [block] = editor.text_blocks(1)
        assert block.text == "Cerere veche" and block.source == "ocr"
        editor.set_block_text(1, block.id, "Cerere aprobata")
        assert "Cerere aprobata" in doc.extract_text(1)
        image = pixels(doc)
        scale = image.shape[1] / doc.page_size(1)[0]
        old = block.rect
        corner = image[int((old.y + 2) * scale), int((old.x + old.w - 4) * scale)]
        assert corner.min() > 200  # banda neagra din imagine e acoperita cu fondul
        with pytest.raises(ValueError):  # F-023: imaginea paginii scanate ramane
            editor.delete_picture(1, 1)


# --- F-019 ------------------------------------------------------------------------------------


def test_T_F019_edit_a_table_cell_keeps_the_structure(tmp_path):
    from app.core.pdf.content import _objects, _raw

    pdf = pikepdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica))
    grid = "0.8 w " + " ".join(f"100 {y} m 400 {y} l S" for y in (700, 650, 600)) + " " + \
        " ".join(f"{x} 600 m {x} 700 l S" for x in (100, 250, 400))
    cells = ("BT /F1 12 Tf 110 670 Td (Nume) Tj ET BT /F1 12 Tf 260 670 Td (Suma) Tj ET "
             "BT /F1 12 Tf 110 620 Td (Ana) Tj ET BT /F1 12 Tf 260 620 Td (100) Tj ET")
    pdf.pages.append(pikepdf.Page(pikepdf.Dictionary(
        Type=pikepdf.Name.Page, MediaBox=[0, 0, 595, 842],
        Contents=pdf.make_stream((grid + " " + cells).encode()),
        Resources=pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font)))))
    path = tmp_path / "tabel.pdf"
    pdf.save(path)
    with PdfDocument.open(path) as doc:
        def paths():
            return sum(1 for o in _objects(doc, 1) if o.type == _raw().FPDF_PAGEOBJ_PATH)

        before = paths()
        PdfContentEditor(doc).edit_table_cell(1, Rect(100, 142, 300, 100), 1, 1, "250")
        text = doc.extract_text(1)
        assert "250" in text and "100" not in text and "Ana" in text and "Suma" in text
        assert paths() == before  # liniile tabelului raman


# --- F-020…F-023 -------------------------------------------------------------------------------


def logo(path, color):
    Image.new("RGB", (192, 96), color).save(path)
    return path


def test_T_F020_F021_F022_F023_pictures(doc, tmp_path):
    editor = PdfContentEditor(doc)
    assert editor.add_picture(1, logo(tmp_path / "rosu.png", "red"), (300, 400)) == 1
    [picture] = editor.pictures(1)
    assert picture.rect.x == pytest.approx(300, abs=1) and picture.rect.w == pytest.approx(144)
    editor.add_picture(1, logo(tmp_path / "albastru.png", "blue"), (350, 420))
    image = pixels(doc)
    scale = image.shape[1] / doc.page_size(1)[0]
    overlap = image[int(440 * scale), int(380 * scale)]
    assert overlap[2] > 200 and overlap[0] < 60  # albastrul, adaugat ultimul, e deasupra
    editor.bring_to_front(1, 1)  # F-022
    overlap = pixels(doc)[int(440 * scale), int(380 * scale)]
    assert overlap[0] > 200 and overlap[2] < 60
    editor.transform_picture(1, 2, rect=Rect(100, 600, 72, 36))  # F-021
    moved = [p.rect for p in editor.pictures(1) if p.rect.y > 550]
    assert moved and moved[0].x == pytest.approx(100, abs=1)
    assert moved[0].w == pytest.approx(72, abs=1)
    editor.transform_picture(1, 2, rotation=90)
    rotated = next(p.rect for p in editor.pictures(1) if p.rect.y > 550)
    assert rotated.h == pytest.approx(72, abs=1)
    editor.delete_picture(1, 1)  # F-023
    assert len(editor.pictures(1)) == 1
    with pytest.raises(KeyError):
        editor.delete_picture(1, 5)


# --- F-017, F-018 -------------------------------------------------------------------------------


def skewed_scan(path):
    img = Image.new("L", (1240, 1754), 255)
    draw = ImageDraw.Draw(img)
    for y in range(300, 1400, 60):
        draw.rectangle((150, y, 1100, y + 18), fill=0)
    img.rotate(3, fillcolor=255, expand=False).save(path, "PDF", resolution=150)
    return path


def test_T_F017_correct_skew(tmp_path, ctx):
    with PdfDocument.open(skewed_scan(tmp_path / "strmb.pdf")) as doc:
        editor = PdfContentEditor(doc)
        before = abs(editor.skew_angle(1))
        assert before > 1
        editor.correct_skew(1, context=ctx)
        assert abs(editor.skew_angle(1)) < before / 2
        assert doc.page_count == 1


def test_T_F018_replace_the_text_layer(scan, ctx):
    with PdfDocument.open(scan) as doc:
        doc.recognize_and_store(context=ctx, engine=LineEngine(["Vechi"]))
        assert "Vechi" in doc.extract_text(1)
        PdfContentEditor(doc).replace_text_layer(1, context=ctx,
                                                 engine=LineEngine(["Nou", "strat"]))
        text = doc.extract_text(1)
        assert "Nou strat" in text and "Vechi" not in text
