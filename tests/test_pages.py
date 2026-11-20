"""Teste pentru operatiile pe pagini din OcrProject (faza 1, pasul 1d)."""

from __future__ import annotations

import io
import random

import pytest
from PIL import Image, ImageDraw

from app.core.context import AppContext
from app.core.errors import LastPageError
from app.core.model import PageStatus
from app.core.paths import AppPaths
from app.core.project import BLANK_THRESHOLD, OcrProject

W, H = 1240, 1754  # A4 la 150 dpi: destul pentru detectie, rapid in teste


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.auto_process", False)  # testele 1c-1e verifica adaugarea fara preprocesare
    yield c
    c.close()


@pytest.fixture
def project(ctx):
    p = OcrProject.create(context=ctx)
    yield p
    p.close()


def _scan(tmp_path, name, frames):
    path = tmp_path / name
    frames[0].save(path, save_all=True, append_images=frames[1:], dpi=(150, 150))
    return path


@pytest.fixture
def six(project, tmp_path):
    """Proiect cu 6 pagini; source_page spune ordinea in care au fost scanate."""
    frames = [Image.new("L", (200 + i, 300), 255) for i in range(6)]
    project.add_images([_scan(tmp_path, "scan.tif", frames)])
    return project


def _order(p):
    return [pg.source_page for pg in p.pages]


def _numbers(p):
    return [pg.page_number for pg in p.pages]


# =============================================================================
# J-055: stergere
# =============================================================================


def test_delete_pages_renumbers(six):
    six.delete_pages([2, 5])
    assert _order(six) == [1, 3, 4, 6] and _numbers(six) == [1, 2, 3, 4]
    assert six.is_modified


def test_T_J055_2_cannot_delete_every_page(six):
    """T-J055.2: proiectul nu se poate goli complet -> LastPageError."""
    with pytest.raises(LastPageError):
        six.delete_pages([1, 2, 3, 4, 5, 6])
    assert len(six.pages) == 6


@pytest.mark.parametrize("bad", [[], [0], [7], [1, 9]])
def test_delete_validates_numbers(six, bad):
    with pytest.raises(ValueError):
        six.delete_pages(bad)
    assert len(six.pages) == 6


def test_delete_removes_page_data(six):
    pid = six.page(3).id
    with six._con:
        six._con.execute(
            "INSERT INTO page_warning (page_id, severity, code, message)"
            " VALUES (?, 'warning', 'LOW_RESOLUTION', 'warning.low_resolution')", (pid,))
    six.delete_pages([3, 3])  # duplicatele conteaza o data
    assert six._con.execute("SELECT COUNT(*) FROM page_warning").fetchone()[0] == 0
    assert len(six.pages) == 5


# =============================================================================
# J-058: rotire
# =============================================================================


@pytest.fixture
def marked(project, tmp_path):
    """O pagina 300x200, cu un pixel negru in coltul stanga-sus."""
    img = Image.new("L", (300, 200), 255)
    img.putpixel((0, 0), 0)
    path = tmp_path / "marcat.png"
    img.save(path, dpi=(300, 200))
    project.add_images([path])
    return project


def _corner_black(path):
    with Image.open(path) as im:
        w, h = im.size
        return [c for c, xy in {"ss": (0, 0), "ds": (w - 1, 0), "sj": (0, h - 1),
                                "dj": (w - 1, h - 1)}.items() if im.getpixel(xy) == 0]


def test_T_J058_1_rotate_clockwise(marked):
    """T-J058.1: rotirea la dreapta muta coltul stanga-sus in dreapta-sus."""
    original = marked.page(1).original_path
    marked.rotate_pages([1], 90)
    pg = marked.page(1)
    assert (pg.width_px, pg.height_px, pg.rotation) == (200, 300, 90)
    assert (pg.dpi_x, pg.dpi_y) == (200, 300)
    assert _corner_black(pg.image_path) == ["ds"]
    assert pg.original_path == original and _corner_black(original) == ["ss"]
    with Image.open(pg.image_path) as im:
        assert im.size == (200, 300)


def test_rotate_counterclockwise_and_cumulative(marked):
    marked.rotate_pages([1], -90)
    assert _corner_black(marked.page(1).image_path) == ["sj"]
    assert marked.page(1).rotation == 270
    marked.rotate_pages([1], 180)
    assert marked.page(1).rotation == 90
    assert _corner_black(marked.page(1).image_path) == ["ds"]


def test_rotate_full_turn_changes_nothing(marked):
    before = marked.page(1).image_path
    marked.rotate_pages([1], 360)
    assert marked.page(1).image_path == before and not marked.page(1).rotation


@pytest.mark.parametrize("degrees", [45, 1, -30])
def test_rotate_needs_multiples_of_90(marked, degrees):
    with pytest.raises(ValueError):
        marked.rotate_pages([1], degrees)


def test_T_J058_2_rotation_invalidates_areas_and_text(marked):
    """T-J058.2: rotirea sterge zonele si textul; recunoscuta -> analyzed."""
    pid = marked.page(1).id
    with marked._con:
        marked._con.execute(
            "INSERT INTO area (page_id, order_index, area_type, bbox_x, bbox_y, bbox_w,"
            " bbox_h, polygon) VALUES (?, 0, 'text', 0, 0, 50, 20, '[]')", (pid,))
        marked._con.execute(
            "UPDATE page SET status='recognized', avg_confidence=90, uncertain_count=3"
            " WHERE id=?", (pid,))
    marked._reload_pages()
    marked.rotate_pages([1], 90)
    pg = marked.page(1)
    assert pg.status is PageStatus.ANALYZED
    assert pg.avg_confidence is None and pg.uncertain_count == 0
    assert marked._con.execute("SELECT COUNT(*) FROM area").fetchone()[0] == 0


def test_rotation_keeps_imported_status(marked):
    marked.rotate_pages([1], 90)
    assert marked.page(1).status is PageStatus.IMPORTED


def test_rotation_updates_thumbnail(marked):
    marked.rotate_pages([1], 90)
    (blob,) = marked._con.execute("SELECT thumbnail_blob FROM page").fetchone()
    thumb = Image.open(io.BytesIO(blob))
    assert thumb.size[1] > thumb.size[0]  # acum in picioare


# =============================================================================
# J-060..J-062, J-064: reordonare
# =============================================================================


def test_T_J060_1_reorder(six):
    """T-J060.1: ordinea se schimba dupa lista data."""
    six.reorder_pages([6, 5, 4, 3, 2, 1])
    assert _order(six) == [6, 5, 4, 3, 2, 1] and _numbers(six) == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize("bad", [[1, 2, 3], [1, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5],
                                 [1, 2, 3, 4, 5, 7]])
def test_reorder_needs_a_full_permutation(six, bad):
    with pytest.raises(ValueError):
        six.reorder_pages(bad)
    assert _order(six) == [1, 2, 3, 4, 5, 6]


def test_reorder_same_order_is_not_a_change(six, tmp_path):
    six.save(tmp_path / "P")
    six.reorder_pages([1, 2, 3, 4, 5, 6])
    assert six.is_modified is False


def test_T_J061_1_duplex_backs_reversed(six):
    """T-J061.1: fetele 1,2,3 apoi versourile scanate invers 6,5,4 -> ordinea cartii."""
    six.interleave_duplex()
    assert _order(six) == [1, 6, 2, 5, 3, 4]


def test_duplex_backs_in_normal_order(six):
    six.interleave_duplex(backs_reversed=False)
    assert _order(six) == [1, 4, 2, 5, 3, 6]


def test_duplex_odd_count_and_selection(six):
    six.interleave_duplex([2, 3, 4, 5, 6])  # 5 pagini: fete 2,3,4; versouri 5,6 inverse
    assert _order(six) == [1, 2, 6, 3, 5, 4]


@pytest.mark.parametrize("sel", [[1, 2], [1, 3, 4], [2, 4, 6]])
def test_T_J061_2_duplex_needs_three_consecutive(six, sel):
    """T-J061.2: minimum trei pagini consecutive."""
    with pytest.raises(ValueError):
        six.interleave_duplex(sel)
    assert _order(six) == [1, 2, 3, 4, 5, 6]


def test_T_J062_1_swap_book_pages(six):
    """T-J062.1: stanga-dreapta inversate, doua cate doua."""
    six.swap_book_pages()
    assert _order(six) == [2, 1, 4, 3, 6, 5]


def test_swap_odd_selection_keeps_last(six):
    six.swap_book_pages([2, 3, 4])
    assert _order(six) == [1, 3, 2, 4, 5, 6]


@pytest.mark.parametrize("sel", [[3], [1, 3]])
def test_T_J062_2_swap_needs_two_consecutive(six, sel):
    """T-J062.2: minimum doua pagini consecutive."""
    with pytest.raises(ValueError):
        six.swap_book_pages(sel)


# =============================================================================
# J-065: mutare in alt proiect
# =============================================================================


def test_T_J065_1_move_pages_to_new_project(ctx, six):
    """T-J065.1: paginile se muta la sfarsitul proiectului tinta, cu imaginile lor."""
    target = OcrProject.create(context=ctx)
    target.add_images([six.page(1).image_path])  # o pagina deja acolo
    six.delete_pages([1])
    six.move_pages_to([2, 4], target)
    assert _order(six) == [2, 4, 6]
    assert [pg.source_page for pg in target.pages] == [1, 3, 5]
    for pg in target.pages:
        assert pg.image_path.is_file() and target._work in pg.image_path.parents
    assert target.is_modified and six.is_modified
    target.close()


def test_move_cannot_empty_the_source(ctx, six):
    target = OcrProject.create(context=ctx)
    with pytest.raises(LastPageError):
        six.move_pages_to([1, 2, 3, 4, 5, 6], target)
    assert len(target.pages) == 0 and len(six.pages) == 6
    target.close()


def test_move_to_itself_or_closed_project(ctx, six):
    with pytest.raises(ValueError):
        six.move_pages_to([1], six)
    closed = OcrProject.create(context=ctx)
    closed.close()
    with pytest.raises(ValueError):
        six.move_pages_to([1], closed)


def test_move_refuses_pages_with_areas_until_phase_3(ctx, six):
    with six._con:
        six._con.execute(
            "INSERT INTO area (page_id, order_index, area_type, bbox_x, bbox_y, bbox_w,"
            " bbox_h, polygon) VALUES (?, 0, 'text', 0, 0, 50, 20, '[]')", (six.page(1).id,))
    target = OcrProject.create(context=ctx)
    with pytest.raises(NotImplementedError):
        six.move_pages_to([1], target)
    assert len(target.pages) == 0
    target.close()


# =============================================================================
# J-056, J-057: pagini goale (grupul `goale/` din SPEC_06)
# =============================================================================


def _page(bg=255, mode="L"):
    return Image.new(mode, (W, H), bg if mode == "L" else (bg, bg, bg))


def _dust(img, n=40, seed=1):
    rnd = random.Random(seed)
    for _ in range(n):
        img.putpixel((rnd.randrange(W), rnd.randrange(H)), 0)
    return img


def _text_line(img):
    d = ImageDraw.Draw(img)
    d.text((100, 200), "Subsemnatul declar pe propria raspundere ca datele sunt corecte. " * 2,
           fill=0)
    return img


def _page_number(img):
    ImageDraw.Draw(img).text((W // 2, H - 60), "12", fill=0)
    return img


def _rule(img):
    ImageDraw.Draw(img).line((100, 800, 1100, 800), fill=0, width=3)
    return img


def _pencil(img):
    d = ImageDraw.Draw(img)
    for i in range(12):
        d.line((200, 400 + i * 30, 900, 420 + i * 30), fill=170, width=2)
    return img


def _highlighter(img):
    ImageDraw.Draw(img).rectangle((200, 600, 700, 640), fill=(255, 255, 0))
    return img


def _photo(img):
    ImageDraw.Draw(img).rectangle((300, 300, 700, 600), fill=(30, 90, 160))
    return img


CASES = [
    ("alba", lambda: _page(), True),
    ("alba_praf", lambda: _dust(_page()), True),
    ("hartie_gri", lambda: _page(232), True),
    ("numar_pagina", lambda: _page_number(_page()), True),
    ("rand_de_text", lambda: _text_line(_page()), False),
    ("linie", lambda: _rule(_page()), False),
    ("creion", lambda: _pencil(_page()), False),
    ("marcaj_galben", lambda: _highlighter(_page(mode="RGB")), False),
    ("imagine", lambda: _photo(_page(mode="RGB")), False),
]


def test_T_J056_1_blank_page_detection(project, tmp_path):
    """T-J056.1 / T-J057.1: paginile goale gasite; cele cu note, marcaje sau
    imagini, nu. Nimic nu se sterge automat."""
    paths = []
    for name, make, _ in CASES:
        path = tmp_path / f"{name}.png"
        make().save(path, dpi=(150, 150))
        paths.append(path)
    project.add_images(paths)
    found = project.find_blank_pages()
    expected = [i for i, (_, _, blank) in enumerate(CASES, start=1) if blank]
    assert found == expected, {CASES[n - 1][0]: project.page(n).blank_score for n in found}
    assert len(project.pages) == len(CASES)  # nicio pagina stearsa


def test_blank_scores_are_cached_and_threshold_is_configurable(project, tmp_path):
    path = tmp_path / "linie.png"
    _rule(_page()).save(path)
    project.add_images([path])
    assert project.find_blank_pages() == []
    score = project.page(1).blank_score
    assert 0 <= score < BLANK_THRESHOLD
    (stored,) = project._con.execute("SELECT blank_score FROM page").fetchone()
    assert stored == score
    assert project.find_blank_pages(threshold=score) == [1]
    with pytest.raises(ValueError):
        project.find_blank_pages(threshold=1.5)


# =============================================================================
# Salvarea dupa operatii
# =============================================================================


def test_saved_project_has_only_used_images(six):
    six.delete_pages([1, 2])
    six.rotate_pages([1], 90)  # pagina rotita: imaginea noua + originalul
    work_images = len(list((six._work / "images").iterdir()))
    target = six._work.parent.parent / "salvat"
    six.save(target)
    saved = {p.name for p in (target / "images").iterdir()}
    assert len(saved) == 5  # 4 pagini + originalul paginii rotite
    assert work_images == 7  # copia de lucru le pastreaza pe toate (pentru undo, 1e)
    for pg in six.pages:
        assert pg.image_path.name in saved and pg.original_path.name in saved
