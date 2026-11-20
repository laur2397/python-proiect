"""Teste pentru tabele (faza 3, pasul 3d): TableAnalyzer si salvarea lor."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.errors import CellsNotRectangularError, WrongAreaTypeError
from app.core.layout.areas import AreaEditor
from app.core.layout.tables import WARNING_CODE, TableAnalyzer, from_separators
from app.core.model import AreaType, AutoProcessMode, PageStatus, Rect
from app.core.paths import AppPaths
from app.core.project import OcrProject

T = AreaType
TA = TableAnalyzer()
FONT = ImageFont.load_default(size=18)


def spans(table):
    return sorted((c.row, c.col, c.row_span, c.col_span) for c in table.cells)


@pytest.fixture
def grid3():
    """3x3, celule de 100 px, de la (0, 0)."""
    return from_separators(Rect(0, 0, 300, 300), [100, 200], [100, 200])


# =============================================================================
# Operatiile pe structura
# =============================================================================


def test_grid_and_cells(grid3):
    assert (grid3.rows, grid3.cols, len(grid3.cells)) == (3, 3, 9)
    assert grid3.cell_at(1, 2).bbox == Rect(200, 100, 100, 100)


def test_T_M043_1_merge_cells(grid3):
    """T-M043.1: o selectie dreptunghiulara devine o celula."""
    t = TA.merge_cells(grid3, [grid3.cell_at(0, 0), grid3.cell_at(0, 1),
                               grid3.cell_at(1, 0), grid3.cell_at(1, 1)])
    merged = t.cell_at(1, 1)
    assert (merged.row, merged.col, merged.row_span, merged.col_span) == (0, 0, 2, 2)
    assert merged.bbox == Rect(0, 0, 200, 200) and len(t.cells) == 6


def test_T_M043_2_non_rectangular_selection_is_refused(grid3):
    """T-M043.2: o selectie in forma de L ridica CellsNotRectangularError."""
    with pytest.raises(CellsNotRectangularError):
        TA.merge_cells(grid3, [grid3.cell_at(0, 0), grid3.cell_at(0, 1), grid3.cell_at(1, 0)])
    with pytest.raises(ValueError):
        TA.merge_cells(grid3, [grid3.cell_at(0, 0)])


def test_T_M042_1_only_merged_cells_can_be_split(grid3):
    """T-M042.1: numai celulele unite anterior se pot separa."""
    t = TA.merge_cells(grid3, [grid3.cell_at(0, 0), grid3.cell_at(0, 1)])
    assert spans(TA.split_cells(t, t.cell_at(0, 0))) == spans(grid3)
    with pytest.raises(WrongAreaTypeError):
        TA.split_cells(grid3, grid3.cell_at(2, 2))


def test_T_M045_M046_add_separators(grid3):
    """T-M045, T-M046: separator nou; o celula unita prin care trece se taie."""
    t = TA.add_separator(grid3, "horizontal", 150)
    assert t.rows == 4 and t.h_separators == [100, 150, 200]
    merged = TA.merge_cells(grid3, [grid3.cell_at(0, 0), grid3.cell_at(0, 1)])
    cut = TA.add_separator(merged, "vertical", 50)
    assert cut.cols == 4
    assert (0, 0, 1, 1) in spans(cut) and (0, 1, 1, 2) in spans(cut)  # celula taiata


@pytest.mark.parametrize(("axis", "pos"), [("horizontal", 0), ("horizontal", 300),
                                           ("horizontal", 100), ("diagonal", 50)])
def test_add_separator_validation(grid3, axis, pos):
    with pytest.raises(ValueError):
        TA.add_separator(grid3, axis, pos)


def test_T_M047_1_removing_a_separator_joins_rows(grid3):
    """T-M047.1: randurile de o parte si de alta a liniei se unesc."""
    t = TA.remove_separator(grid3, "horizontal", 100)
    assert t.rows == 2 and len(t.cells) == 6
    assert t.cell_at(0, 0).bbox == Rect(0, 0, 100, 200)
    merged = TA.merge_cells(grid3, [grid3.cell_at(0, 0), grid3.cell_at(0, 1)])
    t = TA.remove_separator(merged, "horizontal", 100)
    assert (0, 0, 1, 2) in spans(t)  # celula unita se prelungeste
    with pytest.raises(ValueError):
        TA.remove_separator(grid3, "vertical", 150)


def test_T_M044_1_merge_rows(grid3):
    """T-M044.1: randurile consecutive devin unul."""
    t = TA.merge_rows(grid3, [1, 2])
    assert t.rows == 2 and t.cell_at(1, 0).bbox == Rect(0, 100, 100, 200)
    for bad in ([1], [0, 2], [2, 3]):
        with pytest.raises(ValueError):
            TA.merge_rows(grid3, bad)


def test_T_M048_1_cells_as_picture(grid3):
    """T-M048.1: celulele cu imagine se marcheaza; marcajul ramane la alte operatii."""
    t = TA.set_as_picture(grid3, [grid3.cell_at(2, 2)])
    assert t.cell_at(2, 2).as_picture and not t.cell_at(0, 0).as_picture
    t = TA.add_separator(t, "horizontal", 50)
    assert t.cell_at(3, 2).as_picture


# =============================================================================
# M-040, M-049: detectarea din imagine
# =============================================================================


def draw_ruled(path, merged_first_row=False):
    """Tabel desenat: 3 randuri x 4 coloane, chenar si linii de 3 px."""
    img = Image.new("L", (900, 700), 255)
    d = ImageDraw.Draw(img)
    x0, y0, cw, rh = 50, 50, 200, 150
    d.rectangle((x0, y0, x0 + 4 * cw, y0 + 3 * rh), outline=0, width=3)
    for r in range(1, 3):
        d.line((x0, y0 + r * rh, x0 + 4 * cw, y0 + r * rh), fill=0, width=3)
    for c in range(1, 4):
        top = y0 + (rh if merged_first_row and c == 1 else 0)
        d.line((x0 + c * cw, top, x0 + c * cw, y0 + 3 * rh), fill=0, width=3)
    for r in range(3):
        for c in range(4):
            d.text((x0 + c * cw + 20, y0 + r * rh + 60), f"{r}-{c}", fill=0, font=FONT)
    img.save(path, dpi=(300, 300))
    return path


def draw_borderless(path):
    """Tabel fara linii: trei coloane de text separate prin spatii goale."""
    img = Image.new("L", (900, 700), 255)
    d = ImageDraw.Draw(img)
    for r in range(4):
        for c, x in enumerate((60, 360, 660)):
            d.text((x, 80 + r * 120), f"val {r}{c}", fill=0, font=FONT)
    img.save(path, dpi=(300, 300))
    return path


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def project_with(ctx, path):
    p = OcrProject.create(context=ctx)
    p.add_images([path], auto_process=AutoProcessMode.NONE)
    return p


def table_area(project, box=(40, 40, 820, 470)):
    ed = AreaEditor(project)
    x, y, w, h = box
    a = ed.create(project.page(1), [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], T.TABLE)
    return ed, a


def test_T_M040_1_ruled_table_is_detected(ctx, tmp_path):
    """T-M040.1: randurile si coloanele din liniile tabelului."""
    p = project_with(ctx, draw_ruled(tmp_path / "t.png"))
    ed, a = table_area(p)
    a = ed.analyze_table(p.page(1), a)
    assert (a.table.rows, a.table.cols) == (3, 4)
    assert all(abs(got - exp) <= 3 for got, exp in zip(a.table.h_separators, (201, 351),
                                                        strict=True))
    assert all(abs(got - exp) <= 3 for got, exp in zip(a.table.v_separators, (251, 451, 651),
                                                        strict=True))
    assert len(a.table.cells) == 12 and p.page(1).warnings == []
    p.close()


def test_merged_cell_is_detected_from_the_missing_line(ctx, tmp_path):
    p = project_with(ctx, draw_ruled(tmp_path / "t.png", merged_first_row=True))
    ed, a = table_area(p)
    a = ed.analyze_table(p.page(1), a)
    first = a.table.cell_at(0, 0)
    assert (first.row_span, first.col_span) == (1, 2) and len(a.table.cells) == 11
    p.close()


def test_borderless_table_from_white_space(ctx, tmp_path):
    p = project_with(ctx, draw_borderless(tmp_path / "b.png"))
    ed, a = table_area(p, (40, 40, 820, 560))
    a = ed.analyze_table(p.page(1), a)
    assert (a.table.rows, a.table.cols) == (4, 3)
    p.close()


def test_T_M049_1_undetectable_structure(ctx, tmp_path):
    """T-M049.1: structura nedetectabila: o celula si un avertisment, nu o eroare."""
    path = tmp_path / "gol.png"
    Image.new("L", (900, 700), 255).save(path, dpi=(300, 300))
    p = project_with(ctx, path)
    ed, a = table_area(p)
    a = ed.analyze_table(p.page(1), a)
    assert (a.table.rows, a.table.cols, len(a.table.cells)) == (1, 1, 1)
    (w,) = p.page(1).warnings
    assert w.code == WARNING_CODE and w.severity == "warning"
    p.undo()  # avertismentul pleaca odata cu analiza
    assert p.page(1).warnings == [] and p.page(1).areas[0].table is None
    p.close()


# =============================================================================
# Salvarea in proiect
# =============================================================================


def test_T_M040_2_analysis_only_on_table_areas(ctx, tmp_path):
    """T-M040.2: zona trebuie sa fie de tip tabel; M-041: se transforma intai."""
    p = project_with(ctx, draw_ruled(tmp_path / "t.png"))
    ed = AreaEditor(p)
    a = ed.create(p.page(1), [(40, 40), (860, 40), (860, 510), (40, 510)], T.TEXT)
    with pytest.raises(WrongAreaTypeError):
        ed.analyze_table(p.page(1), a)
    a = ed.change_type(p.page(1), a, T.TABLE)  # M-041
    assert ed.analyze_table(p.page(1), a).table.rows == 3
    p.close()


def test_edited_table_is_saved_and_reloaded(ctx, tmp_path):
    p = project_with(ctx, draw_ruled(tmp_path / "t.png"))
    ed, a = table_area(p)
    a = ed.analyze_table(p.page(1), a)
    t = TA.merge_cells(a.table, [a.table.cell_at(0, 0), a.table.cell_at(0, 1)])
    t = TA.set_as_picture(t, [t.cell_at(2, 3)])
    a = ed.set_table(p.page(1), a, t)
    assert spans(a.table) == spans(t) and a.table.cell_at(2, 3).as_picture
    assert p.undo_description() == "undo.edit_table"
    p.save(tmp_path / "P")
    again = OcrProject.open(tmp_path / "P", context=ctx)
    assert spans(again.page(1).areas[0].table) == spans(t)
    again.close()
    p.close()


def test_table_changes_invalidate_recognition_and_follow_type_changes(ctx, tmp_path):
    p = project_with(ctx, draw_ruled(tmp_path / "t.png"))
    ed, a = table_area(p)
    with p._con:
        p._con.execute("UPDATE page SET status = 'recognized'")
    p._reload_pages()
    a = ed.analyze_table(p.page(1), a)
    assert p.page(1).status is PageStatus.ANALYZED
    a = ed.change_type(p.page(1), a, T.TEXT)
    assert a.table is None  # celulele pleaca odata cu tipul
    assert p._con.execute("SELECT COUNT(*) FROM table_cell").fetchone()[0] == 0
    p.close()
