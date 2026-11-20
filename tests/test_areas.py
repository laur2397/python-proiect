"""Teste pentru AreaEditor (faza 3, pasul 3a)."""

from __future__ import annotations

import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.errors import (
    AreaOutOfBoundsError,
    AreaOverlapError,
    AreaTooSmallError,
    WrongAreaTypeError,
)
from app.core.layout.areas import BARCODE_AUTODETECT, AreaEditor, column_order
from app.core.model import (
    AreaType,
    AutoProcessMode,
    Orientation,
    PageStatus,
    PrintType,
    Rect,
    TextFunction,
)
from app.core.paths import AppPaths
from app.core.project import OcrProject

T = AreaType


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
    p.add_images([path, path], auto_process=AutoProcessMode.NONE)
    yield p
    p.close()


@pytest.fixture
def ed(project):
    return AreaEditor(project)


def rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def page(project, n=1):
    return project.page(n)


def areas(project, n=1):
    return page(project, n).areas


def set_status(project, status, n=1):
    with project._con:
        project._con.execute("UPDATE page SET status = ? WHERE id = ?", (status, page(project, n).id))
    project._reload_pages()


def add_text_block(project, area_id):
    with project._con:
        project._con.execute(
            "INSERT INTO text_block (area_id, order_index, bbox_x, bbox_y, bbox_w, bbox_h)"
            " VALUES (?, 0, 0, 0, 10, 10)", (area_id,))


def text_blocks(project):
    return project._con.execute("SELECT COUNT(*) FROM text_block").fetchone()[0]


# =============================================================================
# M-001..M-008: creare
# =============================================================================


@pytest.mark.parametrize("kind", list(AreaType))
def test_T_M001_M006_every_type_can_be_created(ed, project, kind):
    """T-M001..T-M006: cele sase tipuri de zona."""
    a = ed.create(page(project), rect(100, 100, 300, 200), kind)
    assert a.area_type is kind and a.order_index == 0
    assert a.bbox == Rect(100, 100, 300, 200) and not a.is_polygon
    assert a.barcode_type == (BARCODE_AUTODETECT if kind is T.BARCODE else None)


def test_areas_are_numbered_in_creation_order(ed, project):
    ed.create(page(project), rect(0, 0, 100, 100), T.TEXT)
    ed.create(page(project), rect(200, 0, 100, 100), T.PICTURE)
    assert [a.order_index for a in areas(project)] == [0, 1]
    assert areas(project, 2) == []


@pytest.mark.parametrize(("w", "h"), [(7, 100), (100, 7), (0, 0)])
def test_T_M008_1_too_small_area_is_refused(ed, project, w, h):
    """T-M008.1: sub 8x8 px zona nu se creeaza."""
    with pytest.raises(AreaTooSmallError) as info:
        ed.create(page(project), rect(10, 10, w, h), T.TEXT)
    assert info.value.params["min_size"] == 8
    assert areas(project) == []


@pytest.mark.parametrize("box", [(-1, 0, 50, 50), (960, 0, 50, 50), (0, 1380, 50, 50)])
def test_T_M016_1_area_cannot_leave_the_image(ed, project, box):
    """T-M016.1: zona nu poate iesi din imagine."""
    with pytest.raises(AreaOutOfBoundsError):
        ed.create(page(project), rect(*box), T.TEXT)


def test_area_may_touch_the_image_edges(ed, project):
    ed.create(page(project), rect(0, 0, 1000, 1400), T.TEXT)
    assert len(areas(project)) == 1


# =============================================================================
# M-034, M-110: suprapunerea
# =============================================================================


def test_T_M034_1_overlapping_area_is_refused(ed, project):
    """T-M034.1: o zona noua peste alta e refuzata; una alaturata, nu."""
    first = ed.create(page(project), rect(100, 100, 200, 200), T.TEXT)
    with pytest.raises(AreaOverlapError) as info:
        ed.create(page(project), rect(250, 250, 200, 200), T.TABLE)
    assert info.value.params["other_id"] == first.id
    ed.create(page(project), rect(300, 100, 200, 200), T.TEXT)  # se atinge, nu se suprapune
    assert len(areas(project)) == 2


def test_T_M110_1_background_picture_under_text(ed, project):
    """T-M110.1: zona de fundal peste toata pagina, apoi zone de text deasupra."""
    ed.create(page(project), rect(0, 0, 1000, 1400), T.BACKGROUND_PICTURE)
    ed.create(page(project), rect(100, 100, 300, 100), T.TEXT)
    ed.create(page(project), rect(100, 300, 300, 100), T.TEXT)
    ed.create(page(project), rect(50, 50, 900, 1300), T.BACKGROUND_PICTURE)  # si invers
    assert [a.area_type for a in areas(project)].count(T.TEXT) == 2


# =============================================================================
# M-011, M-016: mutare si redimensionare
# =============================================================================


def test_move_and_resize(ed, project):
    a = ed.create(page(project), rect(100, 100, 200, 100), T.TEXT)
    a = ed.move(page(project), a, 50, 25)
    assert a.bbox == Rect(150, 125, 200, 100)
    a = ed.resize(page(project), a, rect(150, 125, 400, 300))
    assert a.bbox == Rect(150, 125, 400, 300)


def test_move_is_refused_outside_image_or_onto_another_area(ed, project):
    a = ed.create(page(project), rect(100, 100, 200, 100), T.TEXT)
    ed.create(page(project), rect(400, 100, 200, 100), T.TEXT)
    with pytest.raises(AreaOutOfBoundsError):
        ed.move(page(project), a, -200, 0)
    with pytest.raises(AreaOverlapError):
        ed.move(page(project), a, 250, 0)
    with pytest.raises(AreaTooSmallError):
        ed.resize(page(project), a, rect(100, 100, 5, 100))
    assert areas(project)[0].bbox == Rect(100, 100, 200, 100)  # neschimbata


def test_T_N026_1_changing_an_area_invalidates_recognized_page(ed, project):
    """T-N026.1 / M-033: dupa o modificare de zone, recunoasterea trebuie reluata."""
    a = ed.create(page(project), rect(100, 100, 200, 100), T.TEXT)
    add_text_block(project, a.id)
    set_status(project, "recognized")
    ed.move(page(project), a, 10, 0)
    assert page(project).status is PageStatus.ANALYZED
    assert text_blocks(project) == 0


# =============================================================================
# M-017: schimbarea tipului
# =============================================================================


def test_T_M017_1_change_type_invalidates_text(ed, project):
    """T-M017.1: schimbarea tipului invalideaza textul paginii."""
    a = ed.create(page(project), rect(100, 100, 200, 100), T.TEXT)
    a = ed.set_properties(page(project), a, text_function="header")
    add_text_block(project, a.id)
    set_status(project, "recognized")
    a = ed.change_type(page(project), a, T.TABLE)
    assert a.area_type is T.TABLE and a.text_function is None
    assert text_blocks(project) == 0
    assert page(project).status is PageStatus.ANALYZED
    a = ed.change_type(page(project), a, T.BARCODE)
    assert a.barcode_type == BARCODE_AUTODETECT


def test_change_to_background_respects_overlap(ed, project):
    bg = ed.create(page(project), rect(0, 0, 1000, 1400), T.BACKGROUND_PICTURE)
    ed.create(page(project), rect(100, 100, 200, 100), T.TEXT)
    with pytest.raises(AreaOverlapError):
        ed.change_type(page(project), bg, T.PICTURE)  # ar acoperi zona de text


# =============================================================================
# M-018..M-020: stergeri
# =============================================================================


def test_T_M018_1_delete_areas_and_their_text(ed, project):
    """T-M018.1: pe o pagina recunoscuta se sterge si textul zonei."""
    a = ed.create(page(project), rect(0, 0, 100, 100), T.TEXT)
    b = ed.create(page(project), rect(200, 0, 100, 100), T.TEXT)
    c = ed.create(page(project), rect(400, 0, 100, 100), T.PICTURE)
    add_text_block(project, a.id)
    set_status(project, "recognized")
    ed.delete(page(project), [a])
    assert [x.id for x in areas(project)] == [b.id, c.id]
    assert [x.order_index for x in areas(project)] == [0, 1]
    assert text_blocks(project) == 0 and page(project).status is PageStatus.ANALYZED
    with pytest.raises(ValueError):
        ed.delete(page(project), [])


def test_T_M019_1_delete_areas_and_text(ed, project):
    """T-M019.1: toate zonele si tot textul paginii dispar."""
    a = ed.create(page(project), rect(0, 0, 100, 100), T.TEXT)
    ed.create(page(project), rect(200, 0, 100, 100), T.TABLE)
    add_text_block(project, a.id)
    ed.delete_areas_and_text(page(project))
    assert areas(project) == [] and text_blocks(project) == 0


def test_T_M020_1_delete_text_keeps_areas(ed, project):
    """T-M020.1: textul dispare, zonele raman."""
    a = ed.create(page(project), rect(0, 0, 100, 100), T.TEXT)
    add_text_block(project, a.id)
    set_status(project, "recognized")
    ed.delete_text(page(project))
    assert len(areas(project)) == 1 and text_blocks(project) == 0
    assert page(project).status is PageStatus.ANALYZED


# =============================================================================
# M-023..M-030: proprietati
# =============================================================================


def test_T_M023_1_language_per_area(ed, project):
    """T-M023.1: limba zonei poate diferi de a documentului; None = a proiectului."""
    a = ed.create(page(project), rect(0, 0, 100, 100), T.TEXT)
    ed.set_language(page(project), [a], ["deu", "eng"])
    assert areas(project)[0].language_codes == ("deu", "eng")
    ed.set_language(page(project), [a], None)
    assert areas(project)[0].language_codes is None
    with pytest.raises(ValueError):
        ed.set_language(page(project), [a], [])


def test_T_M030_1_language_only_for_areas_of_the_same_type(ed, project):
    """T-M030.1: limba se seteaza deodata numai pe zone de acelasi tip."""
    a = ed.create(page(project), rect(0, 0, 100, 100), T.TEXT)
    b = ed.create(page(project), rect(200, 0, 100, 100), T.TEXT)
    c = ed.create(page(project), rect(400, 0, 100, 100), T.TABLE)
    ed.set_language(page(project), [a, b], ["ron"])
    with pytest.raises(WrongAreaTypeError):
        ed.set_language(page(project), [a, c], ["ron"])


def test_T_M024_1_function_only_for_text(ed, project):
    """T-M024.1: functia (antet, subsol, nota) numai pentru zonele de text."""
    a = ed.create(page(project), rect(0, 0, 100, 100), T.TEXT)
    b = ed.create(page(project), rect(200, 0, 100, 100), T.TABLE)
    for f in ("header", "footer", "footnote"):
        assert ed.set_properties(page(project), a, text_function=f).text_function is TextFunction(f)
    with pytest.raises(WrongAreaTypeError):
        ed.set_properties(page(project), b, text_function="header")


def test_M025_M028_other_properties(ed, project):
    a = ed.create(page(project), rect(0, 0, 100, 100), T.TEXT)
    a = ed.set_properties(page(project), a, orientation="90", print_type="typewriter",
                          is_inverted=True, cjk_direction="vertical")
    assert a.orientation is Orientation.DEG_90 and a.print_type is PrintType.TYPEWRITER
    assert a.is_inverted and a.cjk_direction == "vertical"
    for bad in ({"orientation": "45"}, {"print_type": "laser"}, {"is_inverted": 1},
                {"cjk_direction": "diagonal"}, {"culoare": "rosu"}):
        with pytest.raises(ValueError):
            ed.set_properties(page(project), a, **bad)


def test_T_M056_1_barcode_type(ed, project):
    """T-M056.1: tipul implicit Autodetect; se poate alege manual, doar pe cod de bare."""
    bc = ed.create(page(project), rect(0, 0, 200, 100), T.BARCODE)
    assert bc.barcode_type == "autodetect"
    assert ed.set_properties(page(project), bc, barcode_type="code39").barcode_type == "code39"
    txt = ed.create(page(project), rect(300, 0, 100, 100), T.TEXT)
    with pytest.raises(WrongAreaTypeError):
        ed.set_properties(page(project), txt, barcode_type="code39")


# =============================================================================
# M-021, M-022: ordinea
# =============================================================================


def test_T_M021_1_reorder(ed, project):
    """T-M021.1: clic pe zone in ordinea dorita; numerele se recalculeaza."""
    a = ed.create(page(project), rect(0, 0, 100, 100), T.TEXT)
    b = ed.create(page(project), rect(200, 0, 100, 100), T.TEXT)
    c = ed.create(page(project), rect(400, 0, 100, 100), T.TEXT)
    ed.reorder(page(project), [c.id, a.id, b.id])
    assert [x.id for x in areas(project)] == [c.id, a.id, b.id]
    for bad in ([a.id, b.id], [a.id, a.id, b.id], [a.id, b.id, 999]):
        with pytest.raises(ValueError):
            ed.reorder(page(project), bad)


def _three_columns(ed, project):
    """Titlu peste toata latimea, trei coloane, create intr-o ordine amestecata."""
    boxes = {
        "c3a": (680, 200, 300, 400), "c1b": (20, 650, 300, 400), "titlu": (20, 20, 960, 150),
        "c2a": (350, 200, 300, 600), "c1a": (20, 200, 300, 400), "c3b": (680, 650, 300, 400),
    }
    made = {name: ed.create(page(project), rect(*b), T.TEXT) for name, b in boxes.items()}
    return {a.id: name for name, a in made.items()}


def test_T_M022_1_automatic_numbering_by_columns(ed, project):
    """T-M022.1: coloanele de la stanga la dreapta, apoi de sus in jos."""
    names = _three_columns(ed, project)
    ed.renumber_automatically(page(project))
    assert [names[a.id] for a in areas(project)] == ["titlu", "c1a", "c1b", "c2a", "c3a", "c3b"]
    assert [a.order_index for a in areas(project)] == [0, 1, 2, 3, 4, 5]


def test_column_order_ignores_text_direction():
    """T-M022: aceeasi ordine si pentru ebraica: nu depinde de directia textului."""
    from app.core.model import AreaData
    left = AreaData(1, T.TEXT, rect(0, 0, 100, 100), 0, bbox=Rect(0, 0, 100, 100))
    right = AreaData(2, T.TEXT, rect(200, 0, 100, 100), 1, bbox=Rect(200, 0, 100, 100))
    assert [a.id for a in column_order([right, left])] == [1, 2]


# =============================================================================
# J-041: undo pentru zone
# =============================================================================


def test_T_J041_3_area_operations_can_be_undone(ed, project):
    """T-J041.3: crearea, stergerea si proprietatile zonelor intra in istoric."""
    a = ed.create(page(project), rect(100, 100, 200, 100), T.TEXT)
    assert project.undo_description() == "undo.create_area"
    project.undo()
    assert areas(project) == []
    project.redo()
    a = areas(project)[0]
    a = ed.set_properties(page(project), a, text_function="footer")
    set_status(project, "recognized")
    ed.delete(page(project), [a])
    assert page(project).status is PageStatus.ANALYZED
    project.undo()
    (back,) = areas(project)
    assert back.id == a.id and back.text_function is TextFunction.FOOTER
    assert page(project).status is PageStatus.RECOGNIZED  # starea paginii revine si ea


def test_undo_rotation_restores_areas(ed, project):
    ed.create(page(project), rect(100, 100, 200, 100), T.TEXT)
    project.rotate_pages([1], 90)
    assert areas(project) == []
    project.undo()
    assert len(areas(project)) == 1 and areas(project)[0].bbox == Rect(100, 100, 200, 100)


def test_areas_survive_save_and_reopen(ctx, ed, project, tmp_path):
    ed.create(page(project), rect(100, 100, 200, 100), T.BARCODE)
    project.save(tmp_path / "P")
    again = OcrProject.open(tmp_path / "P", context=ctx)
    (a,) = again.page(1).areas
    assert a.area_type is T.BARCODE and a.barcode_type == BARCODE_AUTODETECT
    again.close()


def test_operations_on_a_foreign_page_or_area(ed, project):
    a = ed.create(page(project), rect(0, 0, 100, 100), T.TEXT)
    with pytest.raises(ValueError):
        ed.move(page(project, 2), a, 1, 1)  # zona nu e pe pagina 2
