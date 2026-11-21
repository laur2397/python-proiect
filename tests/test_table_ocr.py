"""Faza 4, pasul 4.5.2: tabelele recunoscute pe celule (M-003, M-048, M-049)
si mutarea paginilor intre proiecte impreuna cu textul lor (J-065, J-067).

Testele cu motorul fals ruleaza oriunde; cel cu Tesseract real se sare daca
Tesseract lipseste, in afara de CI (DOCULENS_REQUIRE_OCR=1).
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.layout.areas import AreaEditor
from app.core.layout.tables import TableAnalyzer, from_separators
from app.core.model import (
    AreaType,
    AutoProcessMode,
    BlockData,
    LineData,
    PageStatus,
    WordData,
)
from app.core.ocr.engine import RecognitionResult, find_tesseract
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject

FONTS = ["/System/Library/Fonts/Supplemental/Times New Roman.ttf", "C:/Windows/Fonts/times.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]
FONT = next((f for f in FONTS if Path(f).is_file()), None)

CELLS = [["Județ", "Localitate", "Suma"],
         ["Brașov", "Făgăraș", "1250"]]
X = [100, 500, 900, 1300]
Y = [100, 250, 400]


class CellEngine:
    """Motor fals: fiecare zona primeste un cuvant cu pozitia ei."""

    name = "fals"

    def __init__(self):
        self.areas = []
        self.lock = threading.Lock()

    def _result(self, page, bbox, area_id):
        with self.lock:
            self.areas.append(bbox)
        word = WordData(None, f"z{bbox.x}_{bbox.y}", 88.0, bbox=bbox, language_code="ron")
        block = BlockData(None, lines=[LineData(None, words=[word], bbox=bbox)], bbox=bbox)
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=88.0,
                                 area_blocks={area_id: [block]})

    def recognize_area(self, page, area, settings, cancel=None):
        return self._result(page, area.bbox, area.id)

    def recognize_page(self, page, settings, cancel=None):
        result = RecognitionResult(page.page_number)
        for a in page.areas:
            if a.area_type is AreaType.TEXT:
                part = self._result(page, a.bbox, a.id)
                result.blocks += part.blocks
                result.area_blocks.update(part.area_blocks)
        return result


def ruled_table(path: Path, cells=CELLS) -> Path:
    img = Image.new("L", (1400, 600), 255)
    draw = ImageDraw.Draw(img)
    for x in X:
        draw.line([(x, Y[0]), (x, Y[-1])], fill=0, width=3)
    for y in Y:
        draw.line([(X[0], y), (X[-1], y)], fill=0, width=3)
    # 56 px: cu modelele tessdata din CI, la 48 px „1250” se citeste „1230”
    # (o confuzie de glif, oricum s-ar decupa celula); testul verifica celulele
    font = ImageFont.truetype(FONT, 56) if FONT else ImageFont.load_default(size=56)
    for r, row in enumerate(cells):
        for c, text in enumerate(row):
            draw.text((X[c] + 40, Y[r] + 45), text, fill=0, font=font)
    img.save(path, dpi=(300, 300))
    return path


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("lang.mode", "manual")
    c.settings.set("lang.manual", ["ron"])
    yield c
    c.close()


@pytest.fixture
def project(ctx, tmp_path):
    p = OcrProject.create(context=ctx)
    p.add_images([ruled_table(tmp_path / "t.png"), ruled_table(tmp_path / "u.png")],
                 auto_process=AutoProcessMode.NONE)
    yield p
    p.close()


def table_area(project, n=1):
    ed = AreaEditor(project)
    box = [(X[0], Y[0]), (X[-1], Y[0]), (X[-1], Y[-1]), (X[0], Y[-1])]
    return ed, ed.create(project.page(n), box, AreaType.TABLE)


def with_grid(project, n=1):
    ed, area = table_area(project, n)
    table = from_separators(area.bbox, Y[1:-1], X[1:-1])
    return ed, ed.set_table(project.page(n), area, table)


def the_table(project, n=1):
    (area,) = [a for a in project.page(n).areas if a.area_type is AreaType.TABLE]
    return area


def cell_texts(project, n=1):
    table = the_table(project, n).table
    return {(c.row, c.col): " ".join(b.text for b in c.blocks) for c in table.cells}


# =============================================================================
# M-003, M-048: fiecare celula se recunoaste separat
# =============================================================================


def test_T_M003_1_each_cell_is_recognized_and_saved(project):
    """T-M003.1: textul ajunge pe celule, nu pe zona, si se pastreaza la
    reincarcarea paginilor din baza de date."""
    with_grid(project)
    RecognitionService(project, engine=CellEngine()).recognize_pages([1])
    texts = cell_texts(project)
    assert len(texts) == 6 and all(t.startswith("z") for t in texts.values())
    area = the_table(project)
    assert area.blocks == []  # textul e numai in celule
    for cell in area.table.cells:  # citita in interiorul celulei, fara liniile tabelului
        word = cell.blocks[0].lines[0].words[0]
        assert cell.bbox.x < word.bbox.x and word.bbox.right < cell.bbox.right
    page = project.page(1)
    assert page.status is PageStatus.RECOGNIZED and "z" in page.text


def test_T_M048_1_picture_cells_are_not_recognized(project):
    """T-M048.1: celula marcata ca imagine nu trece prin OCR."""
    ed, area = with_grid(project)
    first = area.table.cell_at(0, 0)
    ed.set_table(project.page(1), area, TableAnalyzer().set_as_picture(area.table, [first]))
    RecognitionService(project, engine=CellEngine()).recognize_pages([1])
    texts = cell_texts(project)
    assert texts[(0, 0)] == "" and all(texts[k] for k in texts if k != (0, 0))


def test_T_M040_2_table_without_structure_is_analyzed_in_one_undo_step(project):
    """T-M040.2: un tabel fara structura se analizeaza la recunoastere; un
    singur pas de undo anuleaza si analiza, si textul."""
    table_area(project)
    RecognitionService(project, engine=CellEngine()).recognize_pages([1])
    assert project.undo_description() == "undo.recognize_pages"
    assert len(cell_texts(project)) == 6  # liniile desenate dau 2 x 3 celule
    project.undo()
    table = the_table(project).table
    assert table is None or not table.cells
    assert project.page(1).status is not PageStatus.RECOGNIZED
    assert project.undo_description() != "undo.recognize_pages"


# =============================================================================
# J-065, J-067: paginile se muta cu tot cu text
# =============================================================================


def test_T_J067_2_moved_pages_keep_text_tables_and_status(ctx, project, tmp_path):
    """T-J067.2: pagina recunoscuta isi pastreaza in proiectul tinta textul,
    tabelul cu celulele lui si starea."""
    with_grid(project, 2)
    AreaEditor(project).create(project.page(2), [(100, 450), (1300, 450), (1300, 560),
                                                 (100, 560)], AreaType.TEXT)
    RecognitionService(project, engine=CellEngine()).recognize_pages([2])
    before_text = project.page(2).text
    before_cells = cell_texts(project, 2)
    target = OcrProject.create(context=ctx)
    try:
        target.add_images([ruled_table(tmp_path / "v.png")], auto_process=AutoProcessMode.NONE)
        project.move_pages_to([2], target)
        moved = target.page(2)
        assert moved.status is PageStatus.RECOGNIZED
        assert before_text and moved.text == before_text
        assert cell_texts(target, 2) == before_cells
        assert len(project.pages) == 1
    finally:
        target.close()


# =============================================================================
# Tesseract real
# =============================================================================

needs_ocr = pytest.mark.skipif(
    (find_tesseract() is None or FONT is None) and os.environ.get("DOCULENS_REQUIRE_OCR") != "1",
    reason="Tesseract sau fontul lipsesc")


@needs_ocr
def test_T_M003_2_real_table_is_read_cell_by_cell(project):
    """T-M003.2: tabelul desenat cu linii se citeste celula cu celula, cu
    diacriticele pastrate si fara liniile tabelului in text."""
    table_area(project)
    RecognitionService(project).recognize_pages([1])
    texts = cell_texts(project)
    for r, row in enumerate(CELLS):
        for c, expected in enumerate(row):
            assert texts[(r, c)] == expected, (r, c, texts)
