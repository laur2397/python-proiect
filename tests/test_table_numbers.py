"""Coloanele de numere din tabele (M-003, N-005): o celula scurta citita ca litera
(`l` pentru 1, `a` pentru 3) se reciteste cu alfabetul cifrelor, pe caseta stransa
in jurul cernelii. Defect gasit la auditul din 24.11.2026 pe o anexa de buget."""

from __future__ import annotations

from types import SimpleNamespace

from PIL import Image, ImageDraw

from app.core.model import BlockData, LineData, Rect, WordData
from app.core.ocr.engine import RecognitionResult
from app.core.ocr.service import RecognitionService, _ink_box


def _block(text, box):
    word = WordData(None, text, 60.0, bbox=box)
    return BlockData(None, lines=[LineData(None, words=[word], bbox=box)], bbox=box)


class DigitsEngine:
    """Citeste `l`/`a` normal si cifra corecta numai cu alfabetul cifrelor."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def recognize_area(self, page, area, settings, cancel=None):
        self.calls.append(area.language_codes)
        row = next(r for r, (y0, y1) in self.answers.items() if y0 <= area.bbox.y <= y1)
        return RecognitionResult(1, blocks=[_block(str(row), area.bbox)])


def _setup(tmp_path, header="Nr.", values=("l", "2", "a")):
    img = Image.new("L", (400, 400), 255)
    draw = ImageDraw.Draw(img)
    cells, blocks = [], {}
    rows = [header, *values]
    for r, value in enumerate(rows):
        box = Rect(20, 20 + r * 80, 120, 80)
        draw.rectangle((box.x, box.y, box.right, box.bottom), outline=0, width=2)
        draw.rectangle((70, box.y + 25, 85, box.y + 55), fill=0)  # glif
        cell = SimpleNamespace(id=r + 1, row=r, col=0, bbox=box, as_picture=False)
        cells.append(cell)
        blocks[cell.id] = [_block(value, box)]
    img.save(tmp_path / "p.png")
    page = SimpleNamespace(image_path=tmp_path / "p.png", dpi_x=300)
    area = SimpleNamespace(table=SimpleNamespace(cells=cells))
    result = RecognitionResult(1, blocks=[b for bl in blocks.values() for b in bl],
                               cell_blocks=blocks)
    answers = {r: (20 + r * 80, 100 + r * 80) for r in range(len(rows))}
    return page, area, result, answers


def _cell_text(result, cid):
    return "".join(w.text for b in result.cell_blocks[cid] for ln in b.lines for w in ln.words)


def test_numbering_column_letters_become_digits(tmp_path):
    page, area, result, answers = _setup(tmp_path)
    engine = DigitsEngine(answers)
    service = RecognitionService.__new__(RecognitionService)
    service._engine = engine
    service._numeric_columns(page, area, None, result, None)
    assert [_cell_text(result, c) for c in (2, 3, 4)] == ["1", "2", "3"]
    assert engine.calls == [("digits",), ("digits",)]  # numai celulele gresite
    assert _cell_text(result, 1) == "Nr."  # antetul ramane


def test_text_column_is_left_alone(tmp_path):
    page, area, result, answers = _setup(tmp_path, header="Denumire",
                                         values=("Echipamente", "IT", "Servicii"))
    engine = DigitsEngine(answers)
    service = RecognitionService.__new__(RecognitionService)
    service._engine = engine
    service._numeric_columns(page, area, None, result, None)
    assert engine.calls == []


def test_ink_box_is_tight_and_ignores_borders(tmp_path):
    page, area, _result, _answers = _setup(tmp_path)
    box = _ink_box(page, area.table.cells[1].bbox)
    assert box is not None and box.w < 40 and box.h < 45  # glif 16x31, cu margine 4
