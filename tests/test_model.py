"""Teste pentru app/core/model.py (SPEC_05 sectiunile 0, 1, 3).

Numele testelor urmeaza SPEC_06: cerinta M-009 -> testul T-M009.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core import model as m
from app.core.model import (
    AreaData,
    AreaType,
    BlockData,
    ColorMode,
    ExportFormat,
    LayoutMode,
    LineData,
    PageData,
    Progress,
    Rect,
    TableCellData,
    TableData,
    WordData,
)

SPEC_DIR = Path(__file__).resolve().parent.parent / "docs" / "spec"


# --- Rect ----------------------------------------------------------------------


def test_rect_right_bottom():
    r = Rect(10, 20, 30, 40)
    assert (r.right, r.bottom) == (40, 60)


def test_rect_is_immutable():
    with pytest.raises(AttributeError):
        Rect(0, 0, 1, 1).x = 5  # type: ignore[misc]


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (Rect(0, 0, 10, 10), Rect(5, 5, 10, 10), True),  # suprapunere partiala
        (Rect(0, 0, 10, 10), Rect(2, 2, 3, 3), True),  # una in alta
        (Rect(0, 0, 10, 10), Rect(10, 0, 10, 10), False),  # se ating pe latura
        (Rect(0, 0, 10, 10), Rect(0, 10, 10, 10), False),  # se ating jos
        (Rect(0, 0, 10, 10), Rect(20, 20, 5, 5), False),  # departe
    ],
)
def test_T_M009_1_rect_intersects(a, b, expected):
    """T-M009.1: verificarea suprapunerii zonelor; simetrica."""
    assert a.intersects(b) is expected
    assert b.intersects(a) is expected


def test_rect_contains_is_half_open():
    r = Rect(0, 0, 10, 10)
    assert r.contains((0, 0))
    assert r.contains((9, 9))
    assert not r.contains((10, 5))
    assert not r.contains((5, 10))


def test_T_M041_1_rect_scaled():
    """T-M041.1: sablon pe pagina de alta dimensiune."""
    assert Rect(10, 20, 30, 40).scaled(2.0) == Rect(20, 40, 60, 80)
    assert Rect(10, 20, 30, 40).scaled(0.5) == Rect(5, 10, 15, 20)


def test_T_M041_2_scaled_adjacent_rects_stay_adjacent():
    """T-M041.2: doua zone lipite raman lipite dupa scalare, fara gol si fara suprapunere."""
    left, right = Rect(0, 0, 33, 10), Rect(33, 0, 33, 10)
    for factor in (0.3, 0.75, 1.37, 2.5):
        a, b = left.scaled(factor), right.scaled(factor)
        assert a.right == b.x
        assert not a.intersects(b)


@pytest.mark.parametrize("factor", [0, -1.0])
def test_rect_scaled_rejects_non_positive(factor):
    with pytest.raises(ValueError):
        Rect(0, 0, 10, 10).scaled(factor)


def test_progress_defaults():
    p = Progress(1, 10, "stage.recognizing")
    assert p.detail == "" and p.indeterminate is False


# --- enumerari = valorile din SPEC_04 ------------------------------------------


def _check_values(table: str, column: str) -> set[str]:
    """Valorile din CHECK (column IN (...)) al tabelei `table` din SPEC_04."""
    sql = (SPEC_DIR / "SPEC_04_schema_bd.sql").read_text(encoding="utf-8")
    start = sql.index(f"CREATE TABLE {table} (")
    body = sql[start : sql.index("\n);", start)]
    found = re.search(rf"\b{column} IN \(([^)]*)\)", body)
    assert found, f"nu gasesc CHECK pentru {table}.{column} in SPEC_04"
    return {v.strip().strip("'") for v in found.group(1).split(",")}


@pytest.mark.parametrize(
    ("enum_cls", "table", "column"),
    [
        (m.LayoutMode, "project", "layout_mode"),
        (m.AreaType, "area", "area_type"),
        (m.TextFunction, "area", "text_function"),
        (m.Orientation, "area", "orientation"),
        (m.PrintType, "area", "print_type"),
        (m.ColorMode, "page", "color_mode"),
        (m.PageStatus, "page", "status"),
    ],
)
def test_enum_values_match_spec04(enum_cls, table, column):
    assert {e.value for e in enum_cls} == _check_values(table, column)


def test_enums_are_str():
    assert AreaType.TEXT == "text"
    assert AreaType("table") is AreaType.TABLE


# --- Q-001..Q-006: matricea mod de layout -> formate ----------------------------

F = ExportFormat
EXPECTED_MATRIX = {
    LayoutMode.EXACT: {F.RTF, F.DOCX, F.PDF, F.PPTX, F.ODT, F.DJVU},  # Q-002
    LayoutMode.EDITABLE: {F.RTF, F.DOCX, F.ODT},  # Q-003
    LayoutMode.FORMATTED: {F.RTF, F.DOCX, F.XLSX, F.TXT, F.HTML, F.ODT, F.FB2, F.EPUB},  # Q-004
    LayoutMode.PLAIN: {F.RTF, F.DOCX, F.XLSX, F.TXT, F.CSV, F.HTML, F.ODT, F.FB2, F.EPUB},  # Q-005
    LayoutMode.FLEXIBLE: {F.HTML},  # Q-006
}


@pytest.mark.parametrize("mode", list(LayoutMode))
def test_T_Q002_Q006_allowed_formats_per_mode(mode):
    """T-Q002..T-Q006: fiecare mod permite exact formatele din tabelul Q din SPEC_02."""
    assert ExportFormat.allowed_for(mode) == EXPECTED_MATRIX[mode]


def test_T_Q001_1_all_90_combinations():
    """T-Q001.1: 5 moduri x 18 formate = 90 de combinatii.

    Tabelul Q-002..Q-006 din SPEC_02 da 27 de combinatii valide
    (6 + 3 + 8 + 9 + 1). CLAUDE.md spune 29; tabelul din specificatie decide.
    """
    combos = [(mode, fmt) for mode in LayoutMode for fmt in ExportFormat]
    assert len(combos) == 90
    valid = [(mode, fmt) for mode, fmt in combos if fmt in ExportFormat.allowed_for(mode)]
    assert len(valid) == 27


def test_T_Q006_1_flexible_layout_is_html_only():
    assert ExportFormat.allowed_for(LayoutMode.FLEXIBLE) == frozenset({ExportFormat.HTML})


def test_allowed_for_accepts_raw_value_and_is_frozen():
    result = ExportFormat.allowed_for("plain")  # type: ignore[arg-type]
    assert ExportFormat.CSV in result
    assert isinstance(result, frozenset)


def test_allowed_for_rejects_unknown_mode():
    with pytest.raises(ValueError):
        ExportFormat.allowed_for("nu-exista")  # type: ignore[arg-type]


# --- modelul de date -----------------------------------------------------------


def _w(text: str, **kw) -> WordData:
    return WordData(id=None, text=text, confidence=95.0, **kw)


def _block(*lines: str) -> BlockData:
    return BlockData(id=None, lines=[LineData(id=None, words=[_w(t) for t in ln.split()]) for ln in lines])


def _area(order: int, bbox: Rect, *lines: str, polygon=None, area_type=AreaType.TEXT) -> AreaData:
    if polygon is None:
        polygon = [(bbox.x, bbox.y), (bbox.right, bbox.y), (bbox.right, bbox.bottom), (bbox.x, bbox.bottom)]
    return AreaData(
        id=None, area_type=area_type, polygon=polygon, order_index=order, bbox=bbox,
        blocks=[_block(*lines)] if lines else [],
    )


def _page(*areas: AreaData) -> PageData:
    return PageData(
        id=None, page_number=1, image_path=Path("i.png"), original_path=Path("o.png"),
        width_px=1000, height_px=1000, dpi_x=300, dpi_y=300, color_mode=ColorMode.GRAY,
        areas=list(areas),
    )


def test_line_and_block_text_with_romanian_diacritics():
    block = _block("Șoseaua Țării", "ştiinţă și țară")
    assert block.lines[0].text == "Șoseaua Țării"
    assert block.text == "Șoseaua Țării\nştiinţă și țară"


def test_word_defaults_are_independent():
    a = _w("a")
    assert a.bbox == Rect(0, 0, 0, 0)
    assert a.char_confidences == () and a.is_uncertain is False
    assert LineData(id=None).words is not LineData(id=None).words


def test_T_M022_1_page_text_follows_area_order_not_list_order():
    """T-M022.1: textul paginii urmeaza numerotarea zonelor."""
    second = _area(1, Rect(0, 500, 100, 100), "al doilea")
    first = _area(0, Rect(0, 0, 100, 100), "primul")
    page = _page(second, first)
    assert page.text == "primul\nal doilea"
    assert [w.text for w in page.iter_words()] == ["primul", "al", "doilea"]


def test_page_text_skips_redacted_words():
    area = _area(0, Rect(0, 0, 100, 100), "CNP 1234567890123")
    area.blocks[0].lines[0].words[1].is_redacted = True
    assert _page(area).text == "CNP"


def test_page_iter_words_includes_table_cells_in_row_order():
    table = TableData(
        rows=2, cols=1,
        cells=[
            TableCellData(id=None, row=1, col=0, blocks=[_block("jos")]),
            TableCellData(id=None, row=0, col=0, blocks=[_block("sus")]),
        ],
    )
    area = _area(0, Rect(0, 0, 100, 100), area_type=AreaType.TABLE)
    area.table = table
    assert [w.text for w in _page(area).iter_words()] == ["sus", "jos"]


def test_table_cell_at_handles_spans_and_bounds():
    merged = TableCellData(id=1, row=0, col=0, row_span=2, col_span=2)
    lone = TableCellData(id=2, row=0, col=2)
    t = TableData(rows=2, cols=3, cells=[merged, lone])
    assert t.cell_at(0, 0) is merged
    assert t.cell_at(1, 1) is merged
    assert t.cell_at(0, 2) is lone
    assert t.cell_at(1, 2) is None  # neacoperita
    assert t.cell_at(2, 0) is None  # in afara
    assert t.cell_at(-1, 0) is None


def test_area_is_polygon():
    rect_area = _area(0, Rect(0, 0, 10, 10))
    assert rect_area.is_polygon is False
    assert _area(0, Rect(0, 0, 10, 10), polygon=[]).is_polygon is False
    l_shape = [(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)]
    assert _area(0, Rect(0, 0, 10, 10), polygon=l_shape).is_polygon is True


def test_page_area_at_respects_polygon_shape():
    l_shape = [(0, 0), (100, 0), (100, 50), (50, 50), (50, 100), (0, 100)]
    area = _area(0, Rect(0, 0, 100, 100), "x", polygon=l_shape)
    page = _page(area)
    assert page.area_at((10, 10)) is area
    assert page.area_at((75, 75)) is None  # in scobitura
    assert page.area_at((500, 500)) is None


def test_page_area_at_finds_right_area():
    a = _area(0, Rect(0, 0, 100, 100))
    b = _area(1, Rect(200, 0, 100, 100))
    page = _page(a, b)
    assert page.area_at((250, 50)) is b
    assert page.area_at((150, 50)) is None
