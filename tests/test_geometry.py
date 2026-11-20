"""Teste pentru zonele poligon (faza 3, pasul 3b): geometry.py si AreaEditor."""

from __future__ import annotations

import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.errors import AreaOutOfBoundsError, AreaOverlapError, WrongAreaTypeError
from app.core.layout.areas import AreaEditor
from app.core.layout.geometry import (
    ShapeError,
    add_rect,
    area_of,
    cut_rect,
    insert_vertex,
    is_rectilinear,
    point_inside,
    polygons_overlap,
)
from app.core.model import AreaType, AutoProcessMode, Rect
from app.core.paths import AppPaths
from app.core.project import OcrProject

T = AreaType
SQ = [(0, 0), (100, 0), (100, 100), (0, 100)]


def rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


# =============================================================================
# geometry.py
# =============================================================================


def test_add_rect_makes_a_polygon():
    poly = add_rect(SQ, Rect(100, 20, 50, 40))
    assert poly == [(0, 0), (100, 0), (100, 20), (150, 20), (150, 60), (100, 60),
                    (100, 100), (0, 100)]
    assert area_of(poly) == 100 * 100 + 50 * 40 and is_rectilinear(poly)


def test_cut_rect_makes_a_notch():
    poly = cut_rect(SQ, Rect(80, 0, 20, 30))
    assert area_of(poly) == 100 * 100 - 20 * 30
    assert (80, 30) in poly


@pytest.mark.parametrize(("r", "why"), [
    (Rect(40, -10, 20, 200), "bucati"),  # o despica in doua
    (Rect(40, 40, 20, 20), "gaura"),  # o gaura in mijloc
    (Rect(-5, -5, 200, 200), "goala"),  # o taie de tot
])
def test_cut_that_breaks_the_area_is_refused(r, why):
    with pytest.raises(ShapeError, match=why):
        cut_rect(SQ, r)


def test_add_must_touch_the_area():
    with pytest.raises(ShapeError):
        add_rect(SQ, Rect(200, 200, 50, 50))  # doua bucati
    with pytest.raises(ShapeError):
        add_rect(SQ, Rect(100, 100, 50, 50))  # se ating doar intr-un colt


def test_cut_outside_changes_nothing():
    assert area_of(cut_rect(SQ, Rect(300, 300, 10, 10))) == area_of(SQ)


def test_only_rectilinear_areas_can_be_combined():
    with pytest.raises(ShapeError):
        add_rect([(0, 0), (100, 0), (50, 80)], Rect(0, 0, 10, 10))


def test_T_M034_2_exact_overlap():
    """T-M034.2: suprapunerea pe poligon; atingerea pe o latura nu conteaza."""
    right = rect(100, 0, 100, 100)
    assert not polygons_overlap(SQ, right)
    assert polygons_overlap(SQ, rect(99, 0, 100, 100))
    l_shape = cut_rect(SQ, Rect(50, 0, 50, 50))  # L: coltul dreapta-sus lipseste
    in_notch = rect(60, 10, 30, 30)
    assert not polygons_overlap(l_shape, in_notch)  # dreptunghiurile se suprapun, zonele nu
    assert polygons_overlap(SQ, in_notch)


def test_oblique_overlap():
    tri = [(0, 0), (100, 0), (0, 100)]
    assert not polygons_overlap(tri, [(100, 0), (100, 100), (0, 100)])  # diagonala comuna
    assert polygons_overlap(tri, rect(40, 40, 60, 60))
    assert not polygons_overlap(tri, rect(60, 60, 40, 40))


def test_point_inside():
    l_shape = cut_rect(SQ, Rect(50, 0, 50, 50))
    assert point_inside((10, 10), l_shape)
    assert not point_inside((75, 25), l_shape)


def test_insert_vertex():
    assert insert_vertex(SQ, (50, 1)) == [(0, 0), (50, 0), (100, 0), (100, 100), (0, 100)]
    assert insert_vertex(SQ, (100, 0)) == SQ  # deja colt
    with pytest.raises(ValueError):
        insert_vertex(SQ, (50, 50))  # nu e pe contur


# =============================================================================
# AreaEditor: M-012..M-014
# =============================================================================


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def project(ctx, tmp_path):
    p = OcrProject.create(context=ctx)
    path = tmp_path / "pagina.png"
    Image.new("L", (1000, 1400), 255).save(path, dpi=(300, 300))
    p.add_images([path], auto_process=AutoProcessMode.NONE)
    yield p
    p.close()


@pytest.fixture
def ed(project):
    return AreaEditor(project)


def pg(project):
    return project.page(1)


def test_T_M013_1_add_area_part(ed, project):
    """T-M013.1: zona de text devine poligon."""
    a = ed.create(pg(project), rect(100, 100, 300, 200), T.TEXT)
    a = ed.add_part(pg(project), a, Rect(400, 150, 100, 100))
    assert a.is_polygon and a.bbox == Rect(100, 100, 400, 200)
    assert area_of(a.polygon) == 300 * 200 + 100 * 100
    (is_poly,) = project._con.execute("SELECT is_polygon FROM area").fetchone()
    assert is_poly == 1


@pytest.mark.parametrize("kind", [T.TABLE, T.BARCODE, T.RECOGNITION])
def test_T_M013_2_add_part_not_for_tables_or_barcodes(ed, project, kind):
    """T-M013.2: pe tabel sau cod de bare unealta nu e disponibila."""
    a = ed.create(pg(project), rect(100, 100, 300, 200), kind)
    with pytest.raises(WrongAreaTypeError):
        ed.add_part(pg(project), a, Rect(400, 150, 100, 100))
    with pytest.raises(WrongAreaTypeError):
        ed.cut_part(pg(project), a, Rect(100, 100, 50, 50))


@pytest.mark.parametrize("kind", [T.TEXT, T.PICTURE, T.BACKGROUND_PICTURE])
def test_T_M014_1_cut_area_part(ed, project, kind):
    """T-M014.1: zona capata o scobitura; o alta zona poate intra in ea."""
    a = ed.create(pg(project), rect(100, 100, 400, 400), kind)
    a = ed.cut_part(pg(project), a, Rect(300, 100, 200, 200))
    assert area_of(a.polygon) == 400 * 400 - 200 * 200
    ed.create(pg(project), rect(320, 120, 150, 150), T.TEXT)  # in scobitura
    assert len(project.page(1).areas) == 2


def test_cut_that_splits_the_area_is_refused(ed, project):
    a = ed.create(pg(project), rect(100, 100, 400, 400), T.TEXT)
    with pytest.raises(ValueError, match="cut_part"):
        ed.cut_part(pg(project), a, Rect(250, 50, 50, 600))
    assert project.page(1).areas[0].bbox == Rect(100, 100, 400, 400)


def test_add_part_respects_image_and_other_areas(ed, project):
    a = ed.create(pg(project), rect(100, 100, 300, 200), T.TEXT)
    ed.create(pg(project), rect(600, 100, 200, 200), T.TEXT)
    with pytest.raises(AreaOutOfBoundsError):
        ed.add_part(pg(project), a, Rect(50, 300, 100, 1200))
    with pytest.raises(AreaOverlapError):
        ed.add_part(pg(project), a, Rect(400, 150, 250, 50))


def test_polygon_operations_can_be_undone(ed, project):
    a = ed.create(pg(project), rect(100, 100, 300, 200), T.TEXT)
    ed.add_part(pg(project), a, Rect(400, 150, 100, 100))
    assert project.undo_description() == "undo.add_area_part"
    project.undo()
    assert not project.page(1).areas[0].is_polygon


def test_T_M012_1_handle_then_drag(ed, project):
    """T-M012.1: un maner nou pe chenar; tras, zona capata o latura oblica."""
    a = ed.create(pg(project), rect(100, 100, 300, 200), T.TEXT)
    a = ed.add_handle(pg(project), a, (250, 101))
    assert (250, 100) in a.polygon and len(a.polygon) == 5
    moved = [(x, y - 50) if (x, y) == (250, 100) else (x, y) for x, y in a.polygon]
    a = ed.resize(pg(project), a, moved)
    assert a.bbox.y == 50 and not is_rectilinear(a.polygon)
    # un varf in plus pe colt nu schimba nimic
    assert len(ed.add_handle(pg(project), a, (100, 100)).polygon) == 5


def test_oblique_area_overlap_is_checked_exactly(ed, project):
    a = ed.create(pg(project), rect(100, 100, 300, 200), T.TEXT)
    a = ed.add_handle(pg(project), a, (250, 100))
    ed.resize(pg(project), a, [(100, 100), (250, 20), (400, 100), (400, 300), (100, 300)])
    ed.create(pg(project), rect(100, 20, 40, 40), T.TEXT)  # deasupra laturii oblice, in afara zonei
    with pytest.raises(AreaOverlapError):
        ed.create(pg(project), rect(230, 40, 40, 40), T.TEXT)  # in varf


def test_area_at_follows_the_polygon(ed, project):
    a = ed.create(pg(project), rect(100, 100, 400, 400), T.TEXT)
    ed.cut_part(pg(project), a, Rect(300, 100, 200, 200))
    page = project.page(1)
    assert page.area_at((150, 150)) is not None
    assert page.area_at((400, 200)) is None
