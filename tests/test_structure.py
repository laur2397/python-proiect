"""Faza 4, pasul 4.5.3: elementele de structura (N-018 antete si subsoluri,
N-019 note de subsol, N-020 cuprins, N-021 liste).

Detectia se testeaza pe pagini construite direct din blocuri (rapid, exact);
salvarea si reincarcarea, prin RecognitionService cu un motor fals; un test
cu Tesseract real verifica tot drumul pe pagini randate.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.layout import structure
from app.core.layout.areas import AreaEditor
from app.core.model import (
    AreaData,
    AreaType,
    AutoProcessMode,
    BlockData,
    ColorMode,
    LineData,
    PageData,
    Rect,
    TextFunction,
    WordData,
)
from app.core.ocr.engine import RecognitionResult, find_tesseract
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject

W, H = 2480, 3508


def block(y: int, lines: list[str], *, x: int = 200, size: int = 40) -> BlockData:
    out = BlockData(None)
    for i, text in enumerate(lines):
        top = int(y + i * size * 1.5)
        words, wx = [], x
        for t in text.split():
            words.append(WordData(None, t, 90.0, bbox=Rect(wx, top, 20 * len(t), size)))
            wx += 20 * len(t) + 15
        out.lines.append(LineData(None, words=words, bbox=Rect(x, top, wx - x, size)))
    last = out.lines[-1].bbox
    out.bbox = Rect(x, y, max(ln.bbox.w for ln in out.lines), last.bottom - y)
    return out


def page(number: int, *blocks: BlockData) -> PageData:
    p = PageData(number, number, Path("x.png"), Path("x.png"), W, H, 300, 300, ColorMode.GRAY)
    for i, b in enumerate(blocks):
        p.areas.append(AreaData(i + 1, AreaType.TEXT, [], i, bbox=b.bbox, blocks=[b]))
    return p


BODY = ["Textul obisnuit al documentului, pe mai multe randuri,"] * 4


# =============================================================================
# N-018
# =============================================================================


def test_T_N018_1_repeated_header_and_page_number_footer():
    """T-N018.1: antetul repetat si numarul de pagina din subsol se marcheaza
    pe toate paginile, chiar daca numarul difera; corpul ramane paragraf."""
    pages = [page(n, block(100, [f"Dosar de finantare - pagina {n} din 3"]),
                  block(800, BODY), block(3300, [str(n)]))
             for n in (1, 2, 3)]
    structure.detect(pages)
    for p in pages:
        head, body, foot = (a.blocks[0] for a in p.areas)
        assert (head.block_type, body.block_type, foot.block_type) == (
            "header", "paragraph", "footer")
        assert [a.text_function for a in p.areas] == [
            TextFunction.HEADER, None, TextFunction.FOOTER]


def test_T_N018_2_ratio_and_single_page():
    """T-N018.2: textul de sus care nu se repeta pe mai mult de jumatate din
    pagini nu e antet; un document de o pagina nu are antete."""
    pages = [page(1, block(100, ["Titlul capitolului intai"]), block(800, BODY)),
             page(2, block(100, ["Alt titlu, diferit"]), block(800, BODY)),
             page(3, block(100, ["Al treilea titlu"]), block(800, BODY))]
    structure.detect(pages)
    assert all(p.areas[0].blocks[0].block_type == "paragraph" for p in pages)
    single = [page(1, block(100, ["Antet"]), block(800, BODY))]
    structure.detect(single)
    assert single[0].areas[0].blocks[0].block_type == "paragraph"


def test_T_N018_3_disabled_detection_leaves_plain_text():
    """T-N018.3: cu detectia dezactivata, se salveaza ca text obisnuit."""
    pages = [page(n, block(100, ["Antet comun"]), block(800, BODY)) for n in (1, 2)]
    structure.detect(pages)
    assert pages[0].areas[0].blocks[0].block_type == "header"
    structure.detect(pages, headers=False)
    assert pages[0].areas[0].blocks[0].block_type == "paragraph"
    assert pages[0].areas[0].text_function is None


# =============================================================================
# N-019
# =============================================================================


def test_T_N019_1_footnote_is_small_marked_and_low():
    """T-N019.1: jos pe pagina, cu un marcaj si cu litera mai mica: nota de
    subsol. Acelasi text cu litera normala nu e nota."""
    p = page(1, block(800, BODY), block(1600, BODY),
             block(3000, ["1 Conform Legii nr. 98/2016 privind achizitiile."], size=28),
             block(3150, ["2 Se aplica numai beneficiarilor privati."], size=40))
    structure.detect([p])
    kinds = [a.blocks[0].block_type for a in p.areas]
    assert kinds == ["paragraph", "paragraph", "footnote", "paragraph"]
    assert p.areas[2].text_function is TextFunction.FOOTNOTE


# =============================================================================
# N-020
# =============================================================================


def test_T_N020_1_table_of_contents():
    """T-N020.1: intrarile cu puncte de legatura si numar de pagina sunt
    cuprins; o singura astfel de linie nu face un cuprins."""
    toc = block(400, ["Capitolul 1 Introducere ........ 3",
                      "Capitolul 2 Bugetul proiectului ....... 7",
                      "Capitolul 3 Calendarul ......... 12",
                      "Anexe ............ 15"])
    p = page(1, block(200, ["Cuprins"]), toc, block(1200, BODY))
    structure.detect([p])
    assert toc.style_name == structure.TOC_STYLE
    assert p.areas[2].blocks[0].style_name is None
    alone = page(1, block(400, ["Vezi capitolul 2 ........ 7"]), block(1200, BODY))
    structure.detect([alone])
    assert alone.areas[0].blocks[0].style_name is None
    structure.detect([p], toc=False)
    assert toc.style_name is None


# =============================================================================
# N-021
# =============================================================================


def test_T_N021_1_bulleted_and_numbered_lists_with_levels():
    """T-N021.1: buline si numerotare; nivelul vine din indentare."""
    items = [block(800, ["• Cererea de finantare semnata"]),
             block(900, ["• Bugetul proiectului"]),
             block(1000, ["a) bugetul pe activitati"], x=320),
             block(1100, ["2. Declaratia de eligibilitate"])]
    p = page(1, block(200, BODY), *items, block(1500, ["Total 1250 lei pentru proiect"]))
    structure.detect([p])
    assert [b.block_type for b in items] == ["list_item"] * 4
    assert [b.list_level for b in items] == [1, 1, 2, 1]
    assert p.areas[0].blocks[0].block_type == "paragraph"
    assert p.areas[-1].blocks[0].block_type == "paragraph"


# =============================================================================
# Salvarea, prin RecognitionService
# =============================================================================


class ScriptEngine:
    """Motor fals: fiecare zona primeste textul din `script` (dupa pagina si y)."""

    name = "fals"

    def __init__(self, script):
        self.script = script
        self.lock = threading.Lock()

    def recognize_area(self, page, area, settings, cancel=None):
        b = block(area.bbox.y, self.script(page.page_number, area.bbox.y))
        return RecognitionResult(page.page_number, blocks=[b], avg_confidence=90.0,
                                 area_blocks={area.id: [b]})

    def recognize_page(self, page, settings, cancel=None):
        result = RecognitionResult(page.page_number)
        for a in page.areas:
            part = self.recognize_area(page, a, settings)
            result.blocks += part.blocks
            result.area_blocks.update(part.area_blocks)
        return result


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("lang.mode", "manual")
    c.settings.set("lang.manual", ["ron"])
    yield c
    c.close()


def test_T_N018_4_structure_is_saved_and_reloaded(ctx, tmp_path):
    """T-N018.4: marcajele ajung in baza de date si se pastreaza la reincarcare;
    recunoasterea unor pagini noi reface antetul si pe paginile vechi."""
    paths = []
    for n in range(3):
        Image.new("L", (W, H), 255).save(tmp_path / f"p{n}.png", dpi=(300, 300))
        paths.append(tmp_path / f"p{n}.png")
    project = OcrProject.create(context=ctx)
    try:
        project.add_images(paths, auto_process=AutoProcessMode.NONE)
        ed = AreaEditor(project)
        for n in (1, 2, 3):
            for y0, y1 in ((80, 200), (800, 1200), (1300, 1500)):
                ed.create(project.page(n), [(200, y0), (2200, y0), (2200, y1), (200, y1)],
                          AreaType.TEXT)

        def script(n, y):
            return {80: [f"Antet comun {n}"], 800: BODY[:2]}.get(y, ["• Element de lista"])

        service = RecognitionService(project, engine=ScriptEngine(script))
        service.recognize_pages([1])
        assert project.page(1).areas[0].blocks[0].block_type == "paragraph"  # o pagina
        service.recognize_pages([2, 3])
        project._reload_pages()
        for n in (1, 2, 3):
            head, body, item = project.page(n).areas
            assert head.blocks[0].block_type == "header"
            assert head.text_function is TextFunction.HEADER
            assert body.blocks[0].block_type == "paragraph"
            assert item.blocks[0].block_type == "list_item" and item.blocks[0].list_level == 1
    finally:
        project.close()


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
def test_T_N021_2_real_pages_header_footer_and_list(ctx, tmp_path):
    """T-N021.2: pe pagini randate si recunoscute cu Tesseract, antetul,
    numarul de pagina si lista numerotata se gasesc."""
    font = ImageFont.truetype(FONT, 48)
    paths = []
    for n in (1, 2):
        img = Image.new("L", (W, H), 255)
        d = ImageDraw.Draw(img)
        d.text((200, 120), "Dosar de finanțare – Primăria Brașov", fill=0, font=font)
        for i in range(6):
            d.text((200, 700 + i * 75), "Textul cererii de finanțare, pe un rând întreg de pagină.",
                   fill=0, font=font)
        for i, item in enumerate(("1. Cererea de finanțare", "2. Bugetul proiectului",
                                  "3. Declarația de eligibilitate")):
            d.text((260, 1500 + i * 140), item, fill=0, font=font)
        d.text((1220, 3300), str(n), fill=0, font=font)
        path = tmp_path / f"r{n}.png"
        img.save(path, dpi=(300, 300))
        paths.append(path)
    project = OcrProject.create(context=ctx)
    try:
        project.add_images(paths, auto_process=AutoProcessMode.NONE)
        RecognitionService(project).recognize_pages()
        for n in (1, 2):
            blocks = [b for a in project.page(n).areas for b in a.blocks]
            kinds = {b.block_type for b in blocks}
            assert {"header", "footer", "list_item"} <= kinds, [
                (b.block_type, b.text) for b in blocks]
            header = next(b for b in blocks if b.block_type == "header")
            assert "Brașov" in header.text
    finally:
        project.close()
