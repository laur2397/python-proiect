"""Teste pentru preprocesarea pe paginile proiectului (faza 2, pasul 2d)."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.errors import OperationCancelledError
from app.core.images.loader import LoadedImage
from app.core.images.preprocess import default_pipeline, estimate_is_photo, to_array
from app.core.model import AutoProcessMode, ColorMode, PageStatus, PreprocessOp
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.core.settings import PreprocessSettings

FONT = ImageFont.load_default(size=22)
OP = PreprocessOp


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.auto_mode", "preprocess")  # testele 2d verifica doar preprocesarea
    yield c
    c.close()


@pytest.fixture
def project(ctx):
    p = OcrProject.create(context=ctx)
    yield p
    p.close()


def text_page(w=600, h=800, bg=245, lines=10, x0=40):
    img = Image.new("L", (w, h), bg)
    d = ImageDraw.Draw(img)
    for i in range(lines):
        d.text((x0, 60 + i * 60), "Cerere de finantare nr. 4521", fill=0, font=FONT)
    return img


def save(img, path, dpi=(300, 300)):
    img.save(path, dpi=dpi)
    return path


def ops_of(project, number):
    return [op for op, _ in project.applied_operations(number)]


# =============================================================================
# J-051, L-030: preprocesarea automata la adaugare
# =============================================================================


def test_T_J051_1_new_pages_are_preprocessed_automatically(project, tmp_path):
    """T-J051.1: cu setarile implicite, paginile noi se preproceseaza la adaugare."""
    skewed = text_page().rotate(3, fillcolor=245, resample=Image.Resampling.BILINEAR)
    added, _ = project.add_images([save(skewed, tmp_path / "s.png")])
    pg = project.page(1)
    assert added[0].id == pg.id
    assert pg.status is PageStatus.PREPROCESSED
    assert pg.image_path != pg.original_path
    assert pg.skew_angle == pytest.approx(3, abs=0.3)
    assert OP.DESKEW in ops_of(project, 1)


def test_auto_process_can_be_switched_off(project, ctx, tmp_path):
    path = save(text_page(), tmp_path / "a.png")
    project.add_images([path], auto_process=AutoProcessMode.NONE)
    assert project.page(1).status is PageStatus.IMPORTED
    ctx.settings.set("image.auto_process", False)
    project.add_images([path])
    assert project.page(2).status is PageStatus.IMPORTED


def test_T_L030_1_only_new_pages_are_processed(project, tmp_path):
    """T-L030.1: preprocesarea se aplica doar paginilor adaugate acum."""
    path = save(text_page(), tmp_path / "a.png")
    project.add_images([path], auto_process=AutoProcessMode.NONE)
    project.add_images([path])
    assert project.page(1).status is PageStatus.IMPORTED
    assert project.page(2).status is PageStatus.PREPROCESSED


def test_no_preprocessing_mode_leaves_pages_untouched(project, ctx, tmp_path):
    ctx.settings.set("image.preprocess_mode", "none")
    project.add_images([save(text_page(), tmp_path / "a.png")])
    pg = project.page(1)
    assert pg.image_path == pg.original_path and ops_of(project, 1) == []


# =============================================================================
# Lantul dat explicit
# =============================================================================


@pytest.fixture
def plain(project, tmp_path):
    project.add_images([save(text_page(), tmp_path / "a.png", dpi=(300, 200))],
                       auto_process=AutoProcessMode.NONE)
    return project


def test_explicit_chain_is_applied_and_recorded(plain):
    original = plain.page(1).original_path
    (pg,) = plain.preprocess_pages([1], [(OP.ROTATE, {"angle": 90}), (OP.INVERT, {})])
    assert (pg.width_px, pg.height_px) == (800, 600)
    assert (pg.dpi_x, pg.dpi_y) == (200, 300)
    assert pg.status is PageStatus.PREPROCESSED and pg.original_path == original
    assert plain.applied_operations(1) == [(OP.ROTATE, {"angle": 90}), (OP.INVERT, {})]
    with Image.open(pg.image_path) as im:
        assert im.size == (800, 600)
    assert plain.is_modified


def test_operations_accumulate(plain):
    plain.preprocess_pages([1], [(OP.INVERT, {})])
    plain.preprocess_pages([1], [(OP.INVERT, {})])
    assert ops_of(plain, 1) == [OP.INVERT, OP.INVERT]


def test_resolution_and_bw_update_the_page(plain):
    (pg,) = plain.preprocess_pages(
        [1], [(OP.RESOLUTION, {"from_dpi": 300, "dpi": 150}), (OP.TO_BW, {})])
    assert (pg.dpi_x, pg.dpi_y, pg.width_px) == (150, 150, 300)
    assert pg.color_mode is ColorMode.BW


def test_T_N024_1_preprocessing_invalidates_text(plain):
    """T-N024.1: o pagina recunoscuta isi pierde zonele si textul."""
    pid = plain.page(1).id
    with plain._con:
        plain._con.execute(
            "INSERT INTO area (page_id, order_index, area_type, bbox_x, bbox_y, bbox_w,"
            " bbox_h, polygon) VALUES (?, 0, 'text', 0, 0, 50, 20, '[]')", (pid,))
        plain._con.execute("UPDATE page SET status = 'recognized' WHERE id = ?", (pid,))
    plain._reload_pages()
    (pg,) = plain.preprocess_pages([1], [(OP.INVERT, {})])
    assert pg.status is PageStatus.PREPROCESSED
    assert plain._con.execute("SELECT COUNT(*) FROM area").fetchone()[0] == 0


def test_empty_chain_changes_nothing(plain):
    (pg,) = plain.preprocess_pages([1], [])
    assert pg.status is PageStatus.IMPORTED and pg.image_path == pg.original_path


def test_cancel_leaves_the_project_unchanged(plain, tmp_path):
    plain.add_images([save(text_page(), tmp_path / "b.png")], auto_process=AutoProcessMode.NONE)
    answers = iter([False, True])
    with pytest.raises(OperationCancelledError):
        plain.preprocess_pages([1, 2], [(OP.INVERT, {})], cancel=lambda: next(answers))
    assert all(pg.status is PageStatus.IMPORTED for pg in plain.pages)
    assert len(list((plain._work / "images").iterdir())) == 2


# =============================================================================
# L-016: impartirea face doua pagini
# =============================================================================


def test_T_L016_2_split_creates_a_new_page_after(project, tmp_path):
    """T-L016.2: o pagina devine doua; contorul creste si paginile urmatoare se
    renumeroteaza."""
    spread = Image.new("L", (1200, 800), 245)
    spread.paste(text_page(), (0, 0))
    spread.paste(text_page(), (600, 0))
    project.add_images([save(spread, tmp_path / "carte.png"), save(text_page(), tmp_path / "z.png")],
                       auto_process=AutoProcessMode.NONE)
    result = project.preprocess_pages([1], [(OP.INVERT, {}), (OP.SPLIT, {"position": 600})])
    assert [pg.page_number for pg in result] == [1, 2]
    assert len(project.pages) == 3 and project.page(3).source_file.name == "z.png"
    for n in (1, 2):
        pg = project.page(n)
        assert pg.width_px == 600 and pg.status is PageStatus.PREPROCESSED
        assert pg.original_path == pg.image_path  # partea devine noul original
        assert ops_of(project, n) == [OP.INVERT, OP.SPLIT]


def test_T_X016_2_facing_pages_split_automatically(project, ctx, tmp_path):
    """T-X016.2: cu `Split facing pages`, doua pagini alaturate devin doua pagini."""
    ctx.settings.set("image.preprocess_mode", "manual")
    ctx.settings.set("image.split_facing_pages", True)
    spread = Image.new("L", (1200, 800), 245)
    spread.paste(text_page(), (0, 0))
    spread.paste(text_page(), (600, 0))
    added, _ = project.add_images([save(spread, tmp_path / "carte.png")])
    assert len(project.pages) == 2 and len(added) == 2
    single, _ = project.add_images([save(text_page(), tmp_path / "o.png")])
    assert len(project.pages) == 3 and len(single) == 1


# =============================================================================
# Revenirea si undo (L-109)
# =============================================================================


def test_revert_to_original(plain):
    plain.preprocess_pages([1], [(OP.ROTATE, {"angle": 90}), (OP.TO_BW, {})])
    plain.revert_to_original([1])
    pg = plain.page(1)
    assert pg.image_path == pg.original_path
    assert (pg.width_px, pg.height_px, pg.dpi_x, pg.dpi_y) == (600, 800, 300, 200)
    assert pg.status is PageStatus.IMPORTED and pg.color_mode is ColorMode.GRAY
    assert ops_of(plain, 1) == []


def test_T_L109_1_image_operations_can_be_undone(plain):
    """T-L109.1: operatiile pe imagine intra in istoric, cu operatiile aplicate."""
    before = plain.page(1)
    plain.preprocess_pages([1], [(OP.ROTATE, {"angle": 90})])
    after = plain.page(1)
    assert plain.undo_description() == "undo.preprocess_pages"
    plain.undo()
    pg = plain.page(1)
    assert pg.image_path == before.image_path and pg.status is PageStatus.IMPORTED
    assert ops_of(plain, 1) == []
    plain.redo()
    assert plain.page(1).image_path == after.image_path
    assert ops_of(plain, 1) == [OP.ROTATE]


def test_split_and_revert_can_be_undone(plain):
    plain.preprocess_pages([1], [(OP.SPLIT, {"position": 300})])
    assert len(plain.pages) == 2
    plain.undo()
    assert len(plain.pages) == 1 and ops_of(plain, 1) == []
    plain.preprocess_pages([1], [(OP.INVERT, {})])
    plain.revert_to_original([1])
    plain.undo()
    assert ops_of(plain, 1) == [OP.INVERT]


def test_deleted_page_keeps_its_operations_after_undo(plain, tmp_path):
    plain.add_images([save(text_page(), tmp_path / "b.png")], auto_process=AutoProcessMode.NONE)
    plain.preprocess_pages([1], [(OP.INVERT, {})])
    plain.delete_pages([1])
    plain.undo()
    assert ops_of(plain, 1) == [OP.INVERT]


def test_saved_project_keeps_processed_and_original_images(ctx, plain, tmp_path):
    plain.preprocess_pages([1], [(OP.INVERT, {})])
    plain.save(tmp_path / "P")
    again = OcrProject.open(tmp_path / "P", context=ctx)
    pg = again.page(1)
    assert pg.image_path.is_file() and pg.original_path.is_file()
    assert pg.image_path != pg.original_path
    assert again.applied_operations(1) == [(OP.INVERT, {})]
    again.close()


def test_moved_pages_keep_their_operations(ctx, plain, tmp_path):
    plain.add_images([save(text_page(), tmp_path / "b.png")], auto_process=AutoProcessMode.NONE)
    plain.preprocess_pages([2], [(OP.INVERT, {})])
    target = OcrProject.create(context=ctx)
    plain.move_pages_to([2], target)
    assert target.applied_operations(1) == [(OP.INVERT, {})]
    target.close()


def test_pipeline_run_and_revert_delegate_to_the_project(plain):
    pipe = default_pipeline()
    (pg,) = pipe.run(plain.page(1), [(OP.INVERT, {})], project=plain)
    assert pg.status is PageStatus.PREPROCESSED
    assert pipe.revert_to_original(pg, project=plain).status is PageStatus.IMPORTED


# =============================================================================
# L-003: selectia de pagini
# =============================================================================


def test_T_L003_1_page_selection(project, tmp_path):
    """T-L003.1: impare, pare, pagina curenta, paginile selectate."""
    path = save(text_page(100, 100, lines=1), tmp_path / "a.png")
    project.add_images([path] * 5, auto_process=AutoProcessMode.NONE)
    assert project.select_pages("odd") == [1, 3, 5]
    assert project.select_pages("even") == [2, 4]
    assert project.select_pages("current", current=4) == [4]
    assert project.select_pages("selected", selected=[5, 2, 2]) == [2, 5]
    for bad in (("current",), ("all",)):
        with pytest.raises(ValueError):
            project.select_pages(*bad)


# =============================================================================
# L-010, L-032, L-035: lantul recomandat si fotografiile
# =============================================================================


def _loaded(dpi=300, photo=False):
    return LoadedImage(path=None, width_px=100, height_px=100, dpi_x=dpi, dpi_y=dpi,  # type: ignore[arg-type]
                       color_mode=ColorMode.GRAY, is_photo=photo)


def test_T_L010_1_recommended_chain_for_a_scan():
    """T-L010.1: pentru o scanare, fara uneltele de fotografie (L-032)."""
    chain = default_pipeline().recommended_chain(_loaded(), PreprocessSettings())
    assert [op for op, _ in chain] == [OP.INVERT, OP.DESKEW, OP.STRAIGHTEN_LINES]
    assert chain[0][1] == {"auto": True}


def test_T_L032_1_photo_only_tools_for_photos():
    """T-L032.1: uneltele marcate cu asterisc intra doar pentru fotografii."""
    chain = default_pipeline().recommended_chain(_loaded(photo=True), PreprocessSettings())
    ops = [op for op, _ in chain]
    assert ops[0] is OP.DETECT_EDGES
    assert OP.DENOISE in ops and OP.WHITEN_BACKGROUND in ops
    assert OP.DEBLUR not in ops  # X-026 e dezactivat implicit


def test_chain_follows_the_settings():
    pipe = default_pipeline()
    low = [op for op, _ in pipe.recommended_chain(_loaded(dpi=150), PreprocessSettings())]
    assert OP.RESOLUTION in low
    s = PreprocessSettings(convert_to_bw=True, remove_color_marks=True, deskew=False)
    ops = [op for op, _ in pipe.recommended_chain(_loaded(), s)]
    assert ops[-1] is OP.TO_BW and OP.REMOVE_COLOR_MARKS in ops and OP.DESKEW not in ops
    off = PreprocessSettings(**{f: False for f in PreprocessSettings.__dataclass_fields__
                                if f != "auto_mode"})
    assert pipe.recommended_chain(_loaded(), off) == []


def test_T_L035_1_photo_or_scan():
    """T-L035.1: fundalul neuniform sau zgomotul inseamna fotografie."""
    scan = to_array(text_page())
    assert not estimate_is_photo(scan)
    light = np.linspace(0.5, 1.0, scan.shape[1], dtype=np.float32)[None, :]
    lit = np.clip(scan * light, 0, 255).astype(np.uint8)
    assert estimate_is_photo(lit)
    noisy = np.clip(scan + np.random.default_rng(0).normal(0, 12, scan.shape), 0, 255)
    assert estimate_is_photo(noisy.astype(np.uint8))


def test_T_L013_1_photo_correction_group():
    """T-L013.1: grupul aplica randurile, zgomotul, neclaritatea si fundalul."""
    out, meta = default_pipeline().tool_for(OP.PHOTO_CORRECTION).apply(to_array(text_page()), {})
    assert set(meta) == {"straighten_lines", "denoise", "deblur", "whiten_background"}
    assert out.shape == (800, 600)


def test_camera_photos_are_marked_at_import(project, ctx, tmp_path):
    exif = Image.Exif()
    exif[0x010F] = "Telefon"
    path = tmp_path / "foto.jpg"
    text_page().convert("RGB").save(path, exif=exif.tobytes())
    project.add_images([path], auto_process=AutoProcessMode.NONE)
    (kind,) = project._con.execute("SELECT source_kind FROM page").fetchone()
    assert kind == "camera"
