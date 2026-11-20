"""Teste pentru app/core/images/preprocess.py (faza 2, pasul 2a)."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.core.images.preprocess import (
    PAPER_SIZES_MM,
    BaseTool,
    PreprocessPipeline,
    PreprocessTool,
    crop_params,
    default_pipeline,
    from_array,
    is_bilevel,
    otsu_threshold,
    to_array,
)
from app.core.model import PreprocessOp

SPEC_04 = Path(__file__).resolve().parent.parent / "docs" / "spec" / "SPEC_04_schema_bd.sql"

PIPE = default_pipeline()


def tool(op):
    return PIPE.tool_for(op)


def gray(h=40, w=60, value=200):
    return np.full((h, w), value, dtype=np.uint8)


def color(h=40, w=60):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[..., 0] = np.arange(w, dtype=np.uint8)[None, :]
    img[..., 1] = np.arange(h, dtype=np.uint8)[:, None]
    img[..., 2] = 77
    return img


def marked(h=40, w=60):
    """Gri cu un pixel negru in coltul stanga-sus."""
    img = gray(h, w, 255)
    img[0, 0] = 0
    return img


# =============================================================================
# Contract si registru
# =============================================================================


def test_ops_match_spec04_page_operation():
    """Fiecare PreprocessOp e o valoare permisa in page_operation.operation."""
    sql = SPEC_04.read_text(encoding="utf-8")
    block = sql[sql.index("CREATE TABLE page_operation"):]
    block = block[block.index("CHECK (operation IN"):block.index("parameters")]
    allowed = set(re.findall(r"'([a-z_]+)'", block))
    assert {op.value for op in PreprocessOp} == allowed


PHOTO_ONLY = {PreprocessOp.WHITEN_BACKGROUND, PreprocessOp.DENOISE}
"""L-032: optiunile cu asterisc se aplica automat numai fotografiilor."""


def test_tools_satisfy_contract_and_are_pure():
    for op in PIPE.ops:
        t = PIPE.tool_for(op)
        assert isinstance(t, PreprocessTool) and t.op is op
        assert t.photo_only is (op in PHOTO_ONLY)
        assert isinstance(t.default_params(), dict)


def test_registry():
    pipe = PreprocessPipeline()
    with pytest.raises(ValueError):
        pipe.tool_for(PreprocessOp.INVERT)
    inv = tool(PreprocessOp.INVERT)
    pipe.register(inv)
    assert pipe.tool_for("invert") is inv
    with pytest.raises(TypeError):
        pipe.register(object())  # nu e o unealta


def test_2a_and_2b_tools_are_registered():
    assert PIPE.ops == {
        # 2a
        PreprocessOp.ROTATE, PreprocessOp.FLIP, PreprocessOp.CROP, PreprocessOp.INVERT,
        PreprocessOp.RESOLUTION, PreprocessOp.BRIGHTNESS_CONTRAST, PreprocessOp.LEVELS,
        PreprocessOp.ERASE, PreprocessOp.TO_BW,
        # 2b
        PreprocessOp.DESKEW, PreprocessOp.REMOVE_COLOR_MARKS,
        PreprocessOp.WHITEN_BACKGROUND, PreprocessOp.DENOISE,
    }


@pytest.mark.parametrize("op", sorted(PIPE.ops, key=lambda o: o.value))
def test_tools_do_not_modify_their_input(op):
    img = color()
    before = img.copy()
    params = {"path": [[5, 5]]} if op is PreprocessOp.ERASE else {}
    out, _ = tool(op).apply(img, params)
    assert np.array_equal(img, before)
    assert out is not img and out.dtype == np.uint8


def test_unknown_parameter_is_named():
    with pytest.raises(ValueError, match="rotate.*necunoscuti.*culoare"):
        tool(PreprocessOp.ROTATE).apply(gray(), {"culoare": 1})


@pytest.mark.parametrize("bad", [
    np.zeros((4, 4), dtype=np.float32), np.zeros((4, 4, 4), dtype=np.uint8),
    np.zeros((0, 4), dtype=np.uint8), [[1, 2]],
])
def test_image_format_is_checked(bad):
    with pytest.raises(ValueError):
        tool(PreprocessOp.INVERT).apply(bad, {})


# =============================================================================
# Conversii
# =============================================================================


@pytest.mark.parametrize(("mode", "shape"), [
    ("1", (30, 20)), ("L", (30, 20)), ("RGB", (30, 20, 3)), ("RGBA", (30, 20, 3)),
    ("P", (30, 20, 3)), ("CMYK", (30, 20, 3)), ("I;16", (30, 20)), ("LA", (30, 20)),
])
def test_to_array_formats(mode, shape):
    arr = to_array(Image.new(mode, (20, 30)))
    assert arr.shape == shape and arr.dtype == np.uint8


def test_bilevel_and_transparency():
    bw = to_array(Image.new("1", (4, 4), 1))
    assert is_bilevel(bw) and set(np.unique(bw)) == {255}
    transparent = to_array(Image.new("RGBA", (4, 4), (0, 0, 0, 0)))
    assert (transparent == 255).all()  # compus pe alb
    assert to_array(Image.new("I;16", (2, 2), 65535)).max() == 255


def test_round_trip():
    for arr in (gray(), color()):
        assert np.array_equal(to_array(from_array(arr)), arr)


# =============================================================================
# L-015: rotire si oglindire, fara pierdere
# =============================================================================


@pytest.mark.parametrize(("angle", "corner", "swap"), [
    (90, (0, -1), True), (-90, (-1, 0), True), (270, (-1, 0), True),
    (180, (-1, -1), False), (-180, (-1, -1), False),
])
def test_T_L015_1_rotate(angle, corner, swap):
    """T-L015.1: coltul stanga-sus ajunge unde trebuie; dimensiunile se inverseaza."""
    out, meta = tool(PreprocessOp.ROTATE).apply(marked(), {"angle": angle})
    assert out[corner] == 0 and out.sum() == marked().sum()
    assert out.shape == ((60, 40) if swap else (40, 60))
    assert meta["swap_dpi"] is swap


def test_rotate_is_lossless_both_ways():
    img = color()
    r = tool(PreprocessOp.ROTATE)
    back, _ = r.apply(r.apply(img, {"angle": 90})[0], {"angle": -90})
    assert np.array_equal(back, img)


@pytest.mark.parametrize("bad", [45, 0, 360, "90", 90.0])
def test_rotate_angles(bad):
    with pytest.raises(ValueError):
        tool(PreprocessOp.ROTATE).apply(gray(), {"angle": bad})


def test_flip():
    f = tool(PreprocessOp.FLIP)
    h, _ = f.apply(marked(), {"axis": "horizontal"})
    v, _ = f.apply(marked(), {"axis": "vertical"})
    assert h[0, -1] == 0 and v[-1, 0] == 0
    assert np.array_equal(f.apply(h, {"axis": "horizontal"})[0], marked())


# =============================================================================
# L-017: decupare
# =============================================================================


def test_T_L017_1_crop():
    """T-L017.1: decuparea in pixeli."""
    img = color()
    out, meta = tool(PreprocessOp.CROP).apply(img, {"x": 10, "y": 5, "width": 20, "height": 15})
    assert out.shape == (15, 20, 3)
    assert np.array_equal(out, img[5:20, 10:30])
    assert meta == {"x": 10, "y": 5, "width": 20, "height": 15}


def test_crop_defaults_to_the_rest_of_the_image():
    out, _ = tool(PreprocessOp.CROP).apply(gray(), {"x": 50, "y": 30})
    assert out.shape == (10, 10)


@pytest.mark.parametrize("params", [
    {"x": 50, "width": 20}, {"y": 30, "height": 11}, {"x": 60}, {"width": 61},
])
def test_T_L017_2_crop_cannot_exceed_the_image(params):
    """T-L017.2: valorile nu pot depasi imaginea."""
    with pytest.raises(ValueError, match="depaseste"):
        tool(PreprocessOp.CROP).apply(gray(), params)


def test_crop_negative_values_are_refused():
    with pytest.raises(ValueError, match="crop.x"):
        tool(PreprocessOp.CROP).apply(gray(), {"x": -1})


def test_crop_params_units_and_paper():
    """L-017: inci sau milimetri; formate de hartie."""
    assert crop_params(dpi=(300, 300), unit="in", width=2, height=1, x=0.5, y=0.25) == {
        "x": 150, "y": 75, "width": 600, "height": 300}
    assert crop_params(dpi=(300, 300), unit="mm", width=25.4, height=50.8) == {
        "x": 0, "y": 0, "width": 300, "height": 600}
    a4 = crop_params(dpi=(300, 300), paper="a4")
    assert (a4["width"], a4["height"]) == (2480, 3508)
    assert "letter" in PAPER_SIZES_MM
    with pytest.raises(ValueError):
        crop_params(dpi=(300, 300), unit="cm", width=1)
    with pytest.raises(ValueError):
        crop_params(dpi=(300, 300), paper="a0")


# =============================================================================
# L-018, L-019, L-020, L-021
# =============================================================================


def test_T_L018_1_invert():
    """T-L018.1: text deschis pe fundal inchis devine inchis pe deschis."""
    img = np.array([[0, 10], [200, 255]], dtype=np.uint8)
    out, _ = tool(PreprocessOp.INVERT).apply(img, {})
    assert out.tolist() == [[255, 245], [55, 0]]
    assert np.array_equal(tool(PreprocessOp.INVERT).apply(color(), {})[0], 255 - color())


def test_T_L019_1_resolution():
    """T-L019.1: reesantionare; dimensiunea fizica ramane."""
    out, meta = tool(PreprocessOp.RESOLUTION).apply(gray(100, 200), {"from_dpi": 200, "dpi": 300})
    assert out.shape == (150, 300) and meta == {"dpi": 300}
    same, _ = tool(PreprocessOp.RESOLUTION).apply(gray(), {"from_dpi": 300, "dpi": 300})
    assert same.shape == gray().shape


@pytest.mark.parametrize("dpi", [71, 1201, 0])
def test_T_L019_2_resolution_range(dpi):
    """T-L019.2: intre 72 si 1200 dpi."""
    with pytest.raises(ValueError, match="resolution.dpi"):
        tool(PreprocessOp.RESOLUTION).apply(gray(), {"dpi": dpi, "from_dpi": 300})


def test_resolution_keeps_bilevel_images_bilevel():
    bw = np.zeros((50, 50), np.uint8)
    bw[10:40, 10:40] = 255
    out, _ = tool(PreprocessOp.RESOLUTION).apply(bw, {"from_dpi": 300, "dpi": 200})
    assert is_bilevel(out)


def test_T_L020_1_brightness_contrast():
    """T-L020.1: 0/0 nu schimba nimic; luminozitatea si contrastul actioneaza."""
    bc = tool(PreprocessOp.BRIGHTNESS_CONTRAST)
    img = np.array([[50, 128, 200]], dtype=np.uint8)
    assert np.array_equal(bc.apply(img, {})[0], img)
    brighter, _ = bc.apply(img, {"brightness": 20})
    assert (brighter > img).all()
    contrast, _ = bc.apply(img, {"contrast": 50})
    assert contrast[0, 0] < 50 and contrast[0, 2] > 200 and contrast[0, 1] == 128
    flat, _ = bc.apply(img, {"contrast": -100})
    assert flat.max() - flat.min() <= 2
    with pytest.raises(ValueError, match="brightness"):
        bc.apply(img, {"brightness": 101})


def test_T_L021_1_levels():
    """T-L021.1: punctele de intrare si de iesire; gama ajusteaza tonurile medii."""
    lv = tool(PreprocessOp.LEVELS)
    img = np.array([[0, 50, 100, 150, 200, 255]], dtype=np.uint8)
    assert np.array_equal(lv.apply(img, {})[0], img)
    out, _ = lv.apply(img, {"black": 50, "white": 200})
    assert out.tolist() == [[0, 0, 85, 170, 255, 255]]
    out, _ = lv.apply(img, {"out_black": 20, "out_white": 220})
    assert out[0, 0] == 20 and out[0, -1] == 220
    lighter, _ = lv.apply(img, {"gamma": 2.0})
    assert lighter[0, 2] > 100


@pytest.mark.parametrize(("black", "white"), [(200, 100), (128, 128)])
def test_T_L021_2_black_point_cannot_exceed_white(black, white):
    """T-L021.2: punctul negru nu poate depasi punctul alb."""
    with pytest.raises(ValueError, match="levels.black"):
        tool(PreprocessOp.LEVELS).apply(gray(), {"black": black, "white": white})


# =============================================================================
# L-022: radiera
# =============================================================================


def test_T_L022_1_eraser_fills_with_detected_background():
    """T-L022.1: traseul se umple cu fundalul detectat, nu cu alb."""
    img = gray(100, 100, 230)  # hartie usor gri
    img[40:60, 20:80] = 0  # o pata
    out, meta = tool(PreprocessOp.ERASE).apply(img, {"path": [[20, 50], [80, 50]], "brush": 24})
    assert (out[40:60, 20:80] == 230).all()
    assert out[5, 5] == 230 and meta["erased_pixels"] > 0


def test_eraser_on_color_and_single_point():
    img = np.full((50, 50, 3), (240, 235, 220), dtype=np.uint8)
    img[25, 25] = (0, 0, 0)
    out, _ = tool(PreprocessOp.ERASE).apply(img, {"path": [[25, 25]], "brush": 5})
    assert tuple(out[25, 25]) == (240, 235, 220)


@pytest.mark.parametrize("params", [{}, {"path": []}, {"path": [[1]]}, {"path": [[1.5, 2]]},
                                    {"path": [[1, 2]], "brush": 0}])
def test_eraser_needs_a_valid_path(params):
    with pytest.raises(ValueError, match="erase"):
        tool(PreprocessOp.ERASE).apply(gray(), params)


# =============================================================================
# L-033: alb-negru
# =============================================================================


def test_T_L033_1_to_black_and_white():
    """T-L033.1: conversia da doar 0 si 255 si e marcata ireversibila."""
    img = gray(20, 20, 220)
    img[5:15, 5:15] = 40
    out, meta = tool(PreprocessOp.TO_BW).apply(img, {})
    assert is_bilevel(out)
    assert (out[5:15, 5:15] == 0).all() and out[0, 0] == 255
    assert meta["irreversible"] is True and 40 <= meta["threshold"] < 220


def test_to_bw_color_and_fixed_threshold():
    img = np.zeros((10, 10, 3), np.uint8)
    img[:, 5:] = (200, 200, 200)
    out, meta = tool(PreprocessOp.TO_BW).apply(img, {"threshold": 100})
    assert out.ndim == 2 and meta["threshold"] == 100
    assert (out[:, :5] == 0).all() and (out[:, 5:] == 255).all()


def test_otsu_separates_two_levels():
    img = np.array([[30] * 50 + [210] * 50], dtype=np.uint8)
    assert 30 <= otsu_threshold(img) < 210


def test_base_tool_is_abstract():
    class Nothing(BaseTool):
        op = PreprocessOp.INVERT

    with pytest.raises(NotImplementedError):
        Nothing().apply(gray(), {})
