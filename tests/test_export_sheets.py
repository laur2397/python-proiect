"""Faza 6, pasul 6.5: XLSX, CSV, PPTX (Q-015, Q-016, Q-017, X-120..X-122)."""

from __future__ import annotations

import openpyxl
import pytest
from PIL import Image
from pptx import Presentation

from app.core.errors import IncompatibleLayoutError
from app.core.export.base import ExportOptions, default_service
from app.core.export.xlsx import to_number
from app.core.model import (
    AreaData,
    AreaType,
    BlockData,
    ColorMode,
    ExportFormat,
    LayoutMode,
    LineData,
    PageData,
    PageStatus,
    Rect,
    TableCellData,
    TableData,
    WordData,
)


def block(text, y=300):
    words = [WordData(None, t, 95.0, bbox=Rect(100 + 120 * i, y, 100, 50))
             for i, t in enumerate(text.split())]
    return BlockData(None, lines=[LineData(None, words=words)], bbox=Rect(100, y, 1000, 60))


def page(tmp_path, number, title, rows):
    path = tmp_path / f"p{number}.png"
    Image.new("RGB", (2480, 3508), (250, 250, 250)).save(path, dpi=(300, 300))
    p = PageData(number, number, path, path, 2480, 3508, 300, 300, ColorMode.COLOR,
                 status=PageStatus.RECOGNIZED)
    b = block(title, y=200)
    p.areas.append(AreaData(1, AreaType.TEXT, [], 0, bbox=b.bbox, blocks=[b]))
    cells = [TableCellData(100 * number + 1, 0, 0, col_span=2, is_header=True,
                           blocks=[block("Buget Brașov")])] if number == 1 else []
    start = 1 if number == 1 else 0
    for r, (name, value) in enumerate(rows, start=start):
        cells += [TableCellData(100 * number + 10 + 2 * r, r, 0, blocks=[block(name)]),
                  TableCellData(100 * number + 11 + 2 * r, r, 1, blocks=[block(value)])]
    table = TableData(rows=len(rows) + start, cols=2, cells=cells)
    p.areas.append(AreaData(2, AreaType.TABLE, [], 1, bbox=Rect(100, 500, 1200, 400),
                            table=table))
    p.areas.append(AreaData(3, AreaType.PICTURE, [], 2, bbox=Rect(100, 1000, 300, 200)))
    return p


@pytest.fixture
def pages(tmp_path):
    return [page(tmp_path, 1, "Anexa 1 buget", [("Lucrări", "1.250,50"), ("TVA", "19%")]),
            page(tmp_path, 2, "Anexa 2", [("Total", "1500")])]


def export(pages, path, fmt, mode, **kw):
    (out,) = default_service().export(pages, path, fmt, ExportOptions(layout_mode=mode, **kw))
    return out


def test_T_X120_1_numbers_in_romanian_format():
    assert to_number("1250") == 1250 and to_number("1.250,50") == 1250.5
    assert to_number("-3,5") == -3.5 and to_number("19%") == pytest.approx(0.19)
    assert to_number("12.5") == 12.5 and to_number("Brașov") is None
    assert to_number("1 250") == 1250


def test_T_Q015_1_xlsx(pages, tmp_path):
    """T-Q015.1 / X-120: tabelele pe celule, unite, numere, textul din afara."""
    out = export(pages, tmp_path / "d.xlsx", ExportFormat.XLSX, LayoutMode.FORMATTED)
    ws = openpyxl.load_workbook(out).active
    flat = [c.value for row in ws.iter_rows() for c in row if c.value is not None]
    assert "Anexa 1 buget" in flat and "Buget Brașov" in flat and "Lucrări" in flat
    assert 1250.5 in flat and 1500 in flat
    assert len(ws.merged_cells.ranges) == 1
    assert len(ws._images) == 2  # Keep pictures


def test_T_X120_2_xlsx_options(pages, tmp_path):
    out = export(pages, tmp_path / "s.xlsx", ExportFormat.XLSX, LayoutMode.PLAIN,
                 format_options={"sheet_per_page": True, "ignore_text_outside_tables": True,
                                 "numbers_as_numbers": False})
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["Pagina 1", "Pagina 2"]
    flat = [c.value for row in wb["Pagina 1"].iter_rows() for c in row if c.value]
    assert "Anexa 1 buget" not in flat and "1.250,50" in flat
    assert wb["Pagina 1"]._images == []  # plain: fara imagini


def test_T_Q015_2_document_without_tables_warns(pages):
    pages[0].areas = [a for a in pages[0].areas if a.area_type is not AreaType.TABLE]
    warnings = default_service().check_before_export(pages[:1], ExportOptions(),
                                                     ExportFormat.XLSX)
    assert warnings


def test_T_Q016_1_csv(pages, tmp_path):
    """T-Q016.1 / X-122: numai tabelele, delimitatorul, #12, codificarea."""
    out = export(pages, tmp_path / "d.csv", ExportFormat.CSV, LayoutMode.PLAIN,
                 format_options={"delimiter": ";", "page_break_char": True})
    text = out.read_text(encoding="utf-8")
    assert "Lucrări;1.250,50" in text and "Anexa" not in text and "\f" in text
    out = export(pages, tmp_path / "w.csv", ExportFormat.CSV, LayoutMode.PLAIN,
                 encoding="windows-1250", format_options={"delimiter": "tab"})
    legacy = out.read_bytes().decode("windows-1250")
    assert "Lucrări\t1.250,50" in legacy and "Braşov" in legacy
    with pytest.raises(IncompatibleLayoutError):  # Q-005: CSV numai in plain
        export(pages, tmp_path / "x.csv", ExportFormat.CSV, LayoutMode.FORMATTED)


def test_T_Q017_1_pptx(pages, tmp_path):
    """T-Q017.1 / X-121: un diapozitiv pe pagina, text, tabel, imagine."""
    out = export(pages, tmp_path / "d.pptx", ExportFormat.PPTX, LayoutMode.EXACT)
    deck = Presentation(str(out))
    assert len(deck.slides) == 2
    first = deck.slides[0]
    texts = [s.text_frame.text for s in first.shapes if s.has_text_frame]
    assert "Anexa 1 buget" in texts
    (table,) = [s.table for s in first.shapes if s.has_table]
    assert table.cell(0, 0).text == "Buget Brașov" and table.cell(1, 1).text == "1.250,50"
    assert any(s.shape_type == 13 for s in first.shapes)  # imagine
    assert deck.slide_width.inches == pytest.approx(8.27, abs=0.01)
    with pytest.raises(IncompatibleLayoutError):  # Q-002: PPTX numai in exact
        export(pages, tmp_path / "x.pptx", ExportFormat.PPTX, LayoutMode.EDITABLE)
