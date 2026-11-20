"""Teste pentru undo/redo in OcrProject (faza 1, pasul 1e, J-041)."""

from __future__ import annotations

import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.core.project import HISTORY_MIN_STEPS, OcrProject

DEAD = "999999999-deadbeef0000"


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.auto_process", False)  # testele 1c-1e verifica adaugarea fara preprocesare
    yield c
    c.close()


def _tif(tmp_path, name, n):
    frames = [Image.new("L", (100 + i, 150), 255) for i in range(n)]
    path = tmp_path / name
    frames[0].save(path, save_all=True, append_images=frames[1:])
    return path


@pytest.fixture
def four(ctx, tmp_path):
    p = OcrProject.create(context=ctx)
    p.add_images([_tif(tmp_path, "scan.tif", 4)])
    yield p
    p.close()


def _order(p):
    return [pg.source_page for pg in p.pages]


def _state(p):
    return [(pg.id, pg.page_number, pg.image_path, pg.width_px, pg.height_px, pg.rotation)
            for pg in p.pages]


def _thumbs(p):
    return p._con.execute("SELECT id, thumbnail_blob FROM page ORDER BY id").fetchall()


# =============================================================================
# De baza
# =============================================================================


def test_empty_project_has_nothing_to_undo(ctx):
    p = OcrProject.create(context=ctx)
    assert not p.can_undo() and not p.can_redo()
    assert p.undo_description() is None and p.undo_params() == {}
    with pytest.raises(ValueError):
        p.undo()
    with pytest.raises(ValueError):
        p.redo()
    p.close()


def test_first_pages_of_an_empty_project_cannot_be_undone(four):
    """Anularea ar goli proiectul, iar J-055 nu permite un proiect fara pagini."""
    assert not four.can_undo()


def test_T_J041_1_undo_redo_delete(four):
    """T-J041.1: stergerea se anuleaza: aceleasi pagini, pe aceleasi locuri."""
    before, thumbs = _state(four), _thumbs(four)
    four.delete_pages([2, 3])
    assert four.undo_description() == "undo.delete_pages"
    assert four.undo_params() == {"pages": [2, 3]}
    four.undo()
    assert _state(four) == before and _thumbs(four) == thumbs
    assert four.can_redo() and four.redo_description() == "undo.delete_pages"
    four.redo()
    assert _order(four) == [1, 4]


def test_undo_redo_rotate(four):
    before = _state(four)
    four.rotate_pages([1, 3], 90)
    rotated = _state(four)
    four.undo()
    assert _state(four) == before
    four.redo()
    assert _state(four) == rotated  # acelasi fisier rotit, fara alta rotire
    assert four.page(1).rotation == 90


@pytest.mark.parametrize(("op", "key"), [
    (lambda p: p.reorder_pages([4, 3, 2, 1]), "undo.reorder_pages"),
    (lambda p: p.interleave_duplex(), "undo.interleave_duplex"),
    (lambda p: p.swap_book_pages(), "undo.swap_book_pages"),
])
def test_undo_redo_reorderings(four, op, key):
    op(four)
    after = _order(four)
    assert four.undo_description() == key
    four.undo()
    assert _order(four) == [1, 2, 3, 4]
    four.redo()
    assert _order(four) == after


def test_undo_redo_add_images(four, tmp_path):
    four.add_images([_tif(tmp_path, "doua.tif", 2)], at=2)
    with_new = _state(four)
    assert four.undo_description() == "undo.add_images"
    assert four.undo_params() == {"files": ["doua.tif"]}
    four.undo()
    assert _order(four) == [1, 2, 3, 4]
    four.redo()
    assert _state(four) == with_new
    assert all(pg.image_path.is_file() for pg in four.pages)


def test_new_change_discards_redo(four):
    four.reorder_pages([2, 1, 3, 4])
    four.undo()
    assert four.can_redo()
    four.swap_book_pages()
    assert not four.can_redo()
    assert four.undo_description() == "undo.swap_book_pages"


def test_undo_marks_project_modified(four, tmp_path):
    four.reorder_pages([2, 1, 3, 4])
    four.save(tmp_path / "P")
    assert not four.is_modified
    four.undo()
    assert four.is_modified


# =============================================================================
# J-060, J-065: ce nu se anuleaza
# =============================================================================


def test_T_J060_2_reorder_that_cannot_be_undone(four):
    """T-J060.2: „Reorder pages (cannot be undone)” nu intra in istoric."""
    four.delete_pages([4])
    four.reorder_pages([3, 2, 1], undoable=False)
    assert _order(four) == [3, 2, 1]
    assert not four.can_undo() and not four.can_redo()


def test_move_clears_source_history_and_target_can_undo(ctx, four, tmp_path):
    target = OcrProject.create(context=ctx)
    target.add_images([_tif(tmp_path, "t.tif", 1)])
    four.rotate_pages([1], 90)
    four.move_pages_to([2], target)
    assert not four.can_undo()
    assert target.undo_description() == "undo.receive_pages"
    target.undo()
    assert len(target.pages) == 1
    target.close()


# =============================================================================
# J-041: cel putin 50 de pasi
# =============================================================================


def test_T_J041_2_at_least_50_steps(four):
    """T-J041.2: minimum 50 de pasi de undo."""
    steps = HISTORY_MIN_STEPS + 10
    for _ in range(steps):
        four.reorder_pages([2, 1, 3, 4])  # schimba de fiecare data primele doua pagini
    undone = 0
    while four.can_undo():
        four.undo()
        undone += 1
    assert undone == steps >= 50
    assert _order(four) == [1, 2, 3, 4]
    for _ in range(steps):
        four.redo()
    assert not four.can_redo()


def test_history_is_capped_by_the_schema(four):
    for _ in range(205):
        four.reorder_pages([2, 1, 3, 4])
    (count,) = four._con.execute("SELECT COUNT(*) FROM undo_entry").fetchone()
    assert count == 200


# =============================================================================
# Salvare si cadere
# =============================================================================


def test_saved_project_has_no_history_but_the_open_one_keeps_it(ctx, four, tmp_path):
    four.delete_pages([1])
    four.save(tmp_path / "P")
    assert four.can_undo()  # in sesiunea curenta istoricul ramane
    reopened = OcrProject.open(tmp_path / "P", context=ctx)
    assert not reopened.can_undo()
    reopened.close()
    four.undo()  # imaginea paginii sterse e inca in copia de lucru
    assert _order(four) == [1, 2, 3, 4]
    assert four.page(1).image_path.is_file()


def test_history_survives_a_crash(tmp_path):
    paths = AppPaths.portable(tmp_path / "app")
    crashed = AppContext.start(paths)
    crashed.settings.set("image.auto_process", False)  # testele 1c-1e verifica adaugarea fara preprocesare
    p = OcrProject.create(context=crashed)
    p.add_images([_tif(tmp_path, "scan.tif", 3)])
    p.reorder_pages([3, 2, 1])
    p.delete_pages([1])
    p.undo()  # undo: stergere; redo disponibil
    snap = p.autosave()
    with crashed.app_db:
        crashed.app_db.execute("UPDATE recovery_entry SET session_id = ?", (DEAD,))
    crashed.app_db.close()

    fresh = AppContext.start(paths)
    fresh.settings.set("image.auto_process", False)  # testele 1c-1e verifica adaugarea fara preprocesare
    rec = OcrProject.recover(snap, context=fresh)
    assert [pg.source_page for pg in rec.pages] == [3, 2, 1]
    assert rec.redo_description() == "undo.delete_pages"
    assert rec.undo_description() == "undo.reorder_pages"
    rec.undo()
    assert [pg.source_page for pg in rec.pages] == [1, 2, 3]
    rec.close()
    fresh.close()
